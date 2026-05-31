"""Gmail client — service construction, message fetch loop, and RawEmail assembly."""

from __future__ import annotations

import base64
import logging
import os
import random
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from shipping_tracker.gmail.auth import load_credentials
from shipping_tracker.gmail.query import build_query

if TYPE_CHECKING:
    from googleapiclient._apis.gmail.v1 import GmailResource

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RawEmail:
    """A single matching email from Gmail, ready for parser dispatch.

    PRIVACY: Do not log sender or body fields directly. Log only message_id
    (a non-PII opaque identifier) for traceability.
    """

    message_id: str  # Gmail message ID — Phase 4 dedup key
    sender: str  # From: header value — used by BaseParser.can_parse()
    body: str  # Plain-text body — used by BaseParser.extract()

    def __repr__(self) -> str:
        """Return a PII-safe repr that omits sender and body."""
        return f"RawEmail(message_id={self.message_id!r})"


def build_service(creds: Any) -> GmailResource:
    """Build and return a Gmail API service resource.

    Args:
        creds: A valid Credentials object from load_credentials().

    Returns:
        A GmailResource (gmail v1) ready for API calls.
    """
    service: GmailResource = build("gmail", "v1", credentials=creds)
    return service


def _decode_base64url(data: str) -> str:
    """Decode a base64url string, adding padding if needed.

    Gmail API strips padding characters ('=') from base64url data.
    Without padding normalisation, base64.urlsafe_b64decode raises
    binascii.Error for strings whose length is not a multiple of 4.

    Args:
        data: A base64url-encoded string, possibly without trailing '=' padding.

    Returns:
        Decoded UTF-8 string. Replacement characters used for invalid sequences.
    """
    missing = (4 - len(data) % 4) % 4
    padded = data + "=" * missing
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def _extract_body(payload: dict[str, Any]) -> str:
    """Extract plain-text body from a Gmail message payload.

    Walks the MIME tree recursively to find text/plain parts.
    Returns empty string if no plain-text part is found.

    Args:
        payload: The Gmail message payload dict (from messages.get format="full").

    Returns:
        Decoded plain-text body string, or "" if no text/plain part exists.

    PRIVACY: Caller must not log the return value (contains email body content).
    """
    mime_type: str = payload.get("mimeType", "")

    if mime_type == "text/plain":
        data: str = payload.get("body", {}).get("data", "")
        return _decode_base64url(data) if data else ""

    for part in payload.get("parts", []):
        result = _extract_body(part)
        if result:
            return result

    return ""


def _extract_sender(message: dict[str, Any]) -> str:
    """Extract the bare sender email address from a Gmail message.

    Reads the 'From' header. If it contains a display name in the form
    'Display Name <address@example.com>', returns only the address part.
    Otherwise returns the full header value stripped of whitespace.

    Args:
        message: A Gmail message dict (from messages.get format="full").

    Returns:
        Bare email address string, e.g. 'shipping@fakestore.example.com'.

    PRIVACY: Caller must not log the return value (contains email address).
    """
    headers: list[dict[str, str]] = message.get("payload", {}).get("headers", [])
    from_value = ""
    for header in headers:
        if header.get("name", "").lower() == "from":
            from_value = header.get("value", "")
            break

    # Strip display name: "Name <addr>" -> "addr"
    if "<" in from_value and ">" in from_value:
        start = from_value.index("<") + 1
        end = from_value.index(">")
        return from_value[start:end].strip()

    return from_value.strip()


def _execute_with_backoff(request: Any, max_retries: int = 3) -> Any:
    """Execute a Google API request with truncated exponential backoff on 429/403.

    Args:
        request: A Google API request object (has .execute() method).
        max_retries: Number of retry attempts before re-raising.

    Returns:
        The API response dict.

    Raises:
        HttpError: When status is not 429/403, or max retries exhausted.
    """
    for attempt in range(max_retries + 1):
        try:
            return request.execute()
        except HttpError as exc:
            if exc.status_code in (429, 403) and attempt < max_retries:
                wait = (2**attempt) + random.uniform(0, 1)
                # Log status code only — not exc.reason (may contain email metadata)
                logger.warning(
                    "gmail.api.rate_limited status=%s attempt=%d retry_after=%.2f",
                    exc.status_code,
                    attempt + 1,
                    wait,
                )
                time.sleep(wait)
            else:
                raise


def _list_all_message_ids(
    service: GmailResource,
    query: str,
) -> list[str]:
    """Collect all message IDs matching the query, following pagination.

    Args:
        service: Authenticated GmailResource.
        query: Gmail search query string (from build_query).

    Returns:
        List of Gmail message ID strings across all pages.
    """
    ids: list[str] = []
    page_token: str | None = None

    while True:
        kwargs: dict[str, Any] = {
            "userId": "me",
            "q": query,
            "labelIds": ["INBOX"],
        }
        if page_token:
            kwargs["pageToken"] = page_token

        response: dict[str, Any] = _execute_with_backoff(
            service.users().messages().list(**kwargs)
        )
        for msg in response.get("messages", []):
            ids.append(msg["id"])

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return ids


def fetch_unread_shipping_emails(
    senders: list[str],
    window_days: int,
) -> list[RawEmail]:
    """Fetch unread shipping emails matching the given senders within the window.

    Loads credentials from env, builds the Gmail service, issues a paginated
    messages.list query, fetches each message in full, decodes the body, and
    returns a list of RawEmail dataclasses.

    Args:
        senders: List of sender addresses or domains to filter by.
        window_days: How many days back to search (newer_than:Nd).

    Returns:
        List of RawEmail objects. Returns [] if no messages match.

    PRIVACY: Only message_id and count are logged. Sender and body are
    never written to logs (LOG-02).
    """
    token_path = os.getenv("GMAIL_TOKEN_PATH", "token.json")
    credentials_path = os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json")

    creds = load_credentials(token_path, credentials_path)
    service = build_service(creds)

    query = build_query(senders, window_days)
    message_ids = _list_all_message_ids(service, query)

    results: list[RawEmail] = []
    for msg_id in message_ids:
        message: dict[str, Any] = _execute_with_backoff(
            service.users().messages().get(userId="me", id=msg_id, format="full")
        )
        sender = _extract_sender(message)
        body = _extract_body(message.get("payload", {}))
        results.append(RawEmail(message_id=msg_id, sender=sender, body=body))
        logger.debug("gmail.message.fetched id=%s", msg_id)

    logger.info("gmail.fetch.complete count=%d", len(results))
    return results
