# Phase 2: Gmail - Research

**Researched:** 2026-05-31
**Domain:** Gmail API OAuth2 authentication, message retrieval, Python typing under mypy --strict
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01/D-05:** Sender-matched, unread emails in the Inbox within a configurable lookback window (default 30 days), via a server-side Gmail search query (e.g. `is:unread from:(...) newer_than:30d`).
- **D-02:** Sender list is configuration, not hardcoded. Exact location (dedicated config value vs. derived from parsers) is a planner decision.
- **D-03:** OAuth scope is `https://www.googleapis.com/auth/gmail.readonly` ONLY. The tool must be incapable of modifying the mailbox — no mark-read, no labels, no delete.
- **D-04:** Phase 2 is stateless re "seen" — dedup is Phase 4's job (SQLite by `message_id`). Return matching unread emails every run.
- **D-06/D-07:** First-run OAuth consent happens on the user's laptop (browser); `token.json` is copied to the headless Pi. `credentials.json` and `token.json` are git-ignored secrets.
- **Stack locked:** `google-api-python-client`, `google-auth-oauthlib` (per PROJECT.md). No new heavy dependencies.

### Claude's Discretion

- Exact Gmail query string construction and pagination handling.
- Whether the sender list is a standalone config value or each `BaseParser` declares its own sender domains (the parser-derived approach is architecturally cleaner for Phase 3+; a simple config list is acceptable for v1).
- Library choice details within the locked stack and how the Gmail service client is structured/typed for mypy --strict.
- Shape of the returned "raw email object" (dict vs. small typed dataclass) — must carry at minimum `message_id`, `sender`, and the raw body for Phase 3.

### Deferred Ideas (OUT OF SCOPE)

- Marking emails read / applying a "Tracked" Gmail label — requires `gmail.modify` write scope; deliberately rejected for v1.
- Auto-discovering shipping senders — out of scope; v1 uses an explicit configured list.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GMAIL-01 | Tool authenticates to Gmail via OAuth2 (`google-api-python-client`, `google-auth-oauthlib`) | `InstalledAppFlow` + `Credentials.from_authorized_user_file` + `Request()` refresh flow documented in §OAuth2 Flow |
| GMAIL-02 | Tool polls for unread emails matching known shipping sender patterns | `users().messages().list(q=..., labelIds=["INBOX"])` with pagination documented in §Gmail Query & Fetch |
| GMAIL-03 | OAuth token cache (`token.json`) persists across runs; no browser interaction after initial setup | Auto-refresh via `creds.refresh(Request())` when `creds.expired and creds.refresh_token`; non-interactive path documented in §OAuth2 Flow |

</phase_requirements>

---

## Summary

Phase 2 introduces Gmail API authentication and email retrieval to the shipping-tracker pipeline. The Google ecosystem provides exactly the right libraries (`google-api-python-client`, `google-auth-oauthlib`) for the two distinct execution contexts: interactive first-time auth on a laptop (via `InstalledAppFlow.run_local_server()`), and non-interactive headless refresh on the Raspberry Pi (via `creds.refresh(Request())`). The `token.json` bridge pattern — generate once on the laptop, copy to the Pi — is the official Google pattern for this exact deployment topology and requires no custom code.

The Gmail `users().messages().list()` API accepts a powerful search query string (`q` parameter) that supports the exact pattern the user endorsed: `is:unread from:(<sender1> OR <sender2>) newer_than:<Nd>` scoped to the INBOX label. The API returns only message IDs; a second call per message (`users().messages().get(format="full")`) retrieves the full MIME payload. Body decoding requires `base64.urlsafe_b64decode()` with padding normalisation — a well-known gotcha in the ecosystem.

Under mypy --strict, the dynamically-typed `build()` service object is the key friction point. The solution is to install `google-api-python-client-stubs` (dev dependency) and import `GmailResource` inside a `TYPE_CHECKING` guard for explicit annotation. All our own code can be strictly typed; the boundary with Google's dynamic types is isolated to the service construction function. Testing is done via `unittest.mock.MagicMock` on the chained service calls — no real OAuth, no real network, no real email data.

**Primary recommendation:** Implement a `GmailClient` class with a `build_service()` factory function and a `fetch_unread_shipping_emails()` method. Keep the OAuth credential logic in a separate `load_credentials()` function so it can be unit-tested independently of the service object.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| OAuth2 credential loading / refresh | Backend (cron script) | — | Credentials live on the Pi filesystem; no browser tier exists in cron context |
| Gmail API query execution | Backend (cron script) | — | Server-side query via Google's API; all filtering happens in Gmail's servers |
| Message ID pagination | Backend (cron script) | — | Loop over `nextPageToken` in the Python client before returning results |
| Raw email object construction | Backend (cron script) | — | Extract `message_id`, `sender`, `body` from API response and wrap in typed dataclass |
| Deduplication check | Phase 4 (SQLite) | — | Deliberately out of scope for Phase 2; Phase 2 returns all matching unread emails |
| Sender list configuration | Config layer (`.env`) | — | Config values, not hardcoded; read via `python-dotenv` |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `google-api-python-client` | 2.197.0 | Gmail REST API client (`build`, `users().messages().*`) | Official Google Python client; locked in PROJECT.md [VERIFIED: PyPI registry] |
| `google-auth-oauthlib` | 1.4.0 | OAuth2 consent flow via `InstalledAppFlow` | Official Google auth-oauthlib integration; locked in PROJECT.md [VERIFIED: PyPI registry] |
| `google-auth` | 2.53.0 | Credential objects (`Credentials`), token refresh (`Request`) | Transitive dependency of both above; provides `google.oauth2.credentials.Credentials` and `google.auth.transport.requests.Request` [VERIFIED: PyPI registry] |

### Supporting (dev-only)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `google-api-python-client-stubs` | 1.37.0 | Type stubs for `GmailResource` and related types | Required for mypy --strict on any file that annotates the Gmail service object [VERIFIED: PyPI registry] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `google-api-python-client` | `httpx` + raw REST | Stack is locked; raw REST would require hand-rolling auth headers, refresh, pagination — use the official client |
| `InstalledAppFlow` (laptop) | Service account | Service accounts cannot access user mailboxes unless domain-wide delegation is granted (requires G Suite/Workspace); personal Gmail only works with user OAuth |

**Installation additions to `pyproject.toml`:**
```toml
[project]
dependencies = [
    "httpx>=0.28",
    "structlog>=25.5",
    "python-dotenv>=1.2",
    "google-api-python-client>=2.197",
    "google-auth-oauthlib>=1.4",
    "google-auth>=2.53",
]

[project.optional-dependencies]
dev = [
    "ruff>=0.15",
    "mypy>=2.1",
    "pytest>=9.0",
    "pre-commit>=4.6",
    "google-api-python-client-stubs>=1.37",
]
```

---

## Package Legitimacy Audit

| Package | Registry | Age | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|
| `google-api-python-client` | PyPI | ~14 yrs | [OK] (noted: classic naming pattern, established package) | Approved |
| `google-auth-oauthlib` | PyPI | ~8 yrs | [OK] | Approved |
| `google-auth` | PyPI | ~8 yrs | [OK] | Approved |
| `google-api-python-client-stubs` | PyPI | ~5 yrs | [OK] (noted: no linked source repo in metadata, but verified on GitHub: `henribru/google-api-python-client-stubs`) | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none

**Packages flagged as suspicious [SUS]:** none

*All four packages passed slopcheck. `google-api-python-client-stubs` has no source repo in its PyPI metadata but is verifiably maintained at github.com/henribru/google-api-python-client-stubs and auto-generated from Google's Discovery Documents.*

---

## Architecture Patterns

### System Architecture Diagram

```
cron trigger
     |
     v
main.py: load_dotenv() -> configure_logging()
     |
     v
GmailClient.build_service()
  [load_credentials(token_path, creds_path, scopes)]
       |-- token.json exists and valid? --> Credentials.from_authorized_user_file()
       |-- expired + refresh_token?     --> creds.refresh(Request())  [non-interactive Pi path]
       |-- no token / no refresh token? --> InstalledAppFlow.run_local_server()  [laptop only]
       |-- save updated token.json
       v
  build("gmail", "v1", credentials=creds) -> GmailResource
     |
     v
GmailClient.fetch_unread_shipping_emails(senders, window_days)
  |-- build_query(senders, window_days) -> q string
  |-- users().messages().list(userId="me", q=q, labelIds=["INBOX"])
  |-- paginate via nextPageToken until exhausted
  |-- for each message_id: users().messages().get(userId="me", id=id, format="full")
  |-- extract_sender(message) -> str
  |-- extract_body(message) -> str  [base64url decode + MIME walk]
  |-- wrap in RawEmail dataclass
     v
List[RawEmail] -> returned to main.py for Phase 3 parser dispatch
```

### Recommended Project Structure

```
shipping_tracker/
├── gmail/
│   ├── __init__.py          # exports: fetch_unread_shipping_emails, RawEmail
│   ├── auth.py              # load_credentials(), token.json read/write
│   ├── client.py            # GmailClient class, build_service(), fetch loop
│   └── query.py             # build_query() pure function, easy to unit test
tests/
├── fixtures/
│   └── fake_gmail_message.json   # synthetic Gmail API response (FAKE data)
├── test_gmail_auth.py
├── test_gmail_client.py
└── test_gmail_query.py
```

### Pattern 1: Two-Path Credential Loading

**What:** A single `load_credentials()` function handles both execution contexts — interactive (laptop, first run) and headless (Pi, every subsequent run). The function always saves the token back so refresh is persisted.

**When to use:** Called once at startup from `GmailClient.build_service()`.

```python
# Source: https://developers.google.com/gmail/api/quickstart/python (adapted)
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def load_credentials(
    token_path: str,
    credentials_path: str,
    scopes: list[str] = SCOPES,
) -> Credentials:
    """Load OAuth2 credentials from token_path, refreshing or re-authorizing as needed.

    Non-interactive (Pi) path: token.json exists and either:
      - creds.valid is True (not expired), OR
      - creds.expired and creds.refresh_token is set -> calls creds.refresh(Request())

    Interactive (laptop) path: token.json missing or refresh_token absent ->
      InstalledAppFlow.run_local_server() opens a browser, writes token.json.

    PRIVACY: token_path and credentials_path must be git-ignored.
    LOG SAFETY: Do not log the Credentials object or any field from it.
    """
    creds: Credentials | None = None

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Non-interactive Pi path — no browser needed
            creds.refresh(Request())
        else:
            # Interactive laptop path — browser opens once
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes)
            creds = flow.run_local_server(port=0)

        with open(token_path, "w") as fh:
            fh.write(creds.to_json())

    return creds
```

### Pattern 2: Gmail Search Query Construction

**What:** Pure function that builds the `q` string from a list of sender domains/addresses and a lookback window. Server-side filtering — no messages fetched unnecessarily.

**When to use:** Called by `fetch_unread_shipping_emails()` before the first API call.

```python
# Source: https://developers.google.com/workspace/gmail/api/guides/list-messages
# Search operator docs: https://support.google.com/mail/answer/7190

def build_query(senders: list[str], window_days: int) -> str:
    """Build a Gmail search query string for unread shipping emails.

    Args:
        senders: List of sender addresses or domains, e.g. ["@aliexpress.com", "ship@store.com"]
        window_days: How many days back to look (e.g. 30 -> newer_than:30d)

    Returns:
        Query string like: is:unread from:(sender1 OR sender2) newer_than:30d

    Note: Gmail OR syntax requires no spaces around OR when inside parentheses.
    """
    from_clause = " OR ".join(senders)
    return f"is:unread from:({from_clause}) newer_than:{window_days}d"
```

### Pattern 3: Paginated Message List + Full Fetch

**What:** Exhausts all pages of `messages.list` (each page gives only IDs), then fetches full message payloads one at a time.

**When to use:** Core of `fetch_unread_shipping_emails()`.

```python
# Source: https://developers.google.com/workspace/gmail/api/guides/list-messages
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from googleapiclient._apis.gmail.v1 import GmailResource

def _list_all_message_ids(
    service: "GmailResource",
    query: str,
) -> list[str]:
    """Collect all message IDs matching the query, following pagination."""
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

        response: dict[str, Any] = (
            service.users().messages().list(**kwargs).execute()
        )
        for msg in response.get("messages", []):
            ids.append(msg["id"])

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return ids
```

### Pattern 4: Body Extraction with MIME Walk

**What:** Navigate the Gmail `full` format MIME payload to find `text/plain` content, then base64url-decode with padding normalisation.

**When to use:** Called per message by `fetch_unread_shipping_emails()`.

```python
# Source: https://googleapis.github.io/google-api-python-client/docs/dyn/gmail_v1.users.messages.html
import base64
from typing import Any


def _extract_body(payload: dict[str, Any]) -> str:
    """Extract plain-text body from a Gmail message payload.

    Walks the MIME tree recursively to find text/plain parts.
    Returns empty string if no plain-text part is found.

    PRIVACY: Caller must not log the return value (contains email body content).
    """
    mime_type: str = payload.get("mimeType", "")

    if mime_type == "text/plain":
        data: str = payload.get("body", {}).get("data", "")
        return _decode_base64url(data)

    # Recurse into multipart/* containers
    for part in payload.get("parts", []):
        result = _extract_body(part)
        if result:
            return result

    return ""


def _decode_base64url(data: str) -> str:
    """Decode a base64url string, adding padding if needed.

    Gmail API strips padding characters ('=') from base64url data.
    Without padding normalisation, base64.urlsafe_b64decode raises
    binascii.Error for strings whose length is not a multiple of 4.
    """
    # Add padding: Python's b64decode requires len % 4 == 0
    missing = (4 - len(data) % 4) % 4
    padded = data + "=" * missing
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
```

### Pattern 5: Typed RawEmail Dataclass

**What:** The typed container Phase 3 will receive. A dataclass is preferred over a plain `dict` because it makes the contract explicit and mypy-checkable.

**When to use:** Returned by `fetch_unread_shipping_emails()`.

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class RawEmail:
    """A single matching email from Gmail, ready for parser dispatch.

    PRIVACY: Do not log sender or body fields directly. Log only message_id
    (a non-PII opaque identifier) for traceability.
    """

    message_id: str   # Gmail message ID — used by Phase 4 as dedup key
    sender: str       # From: header value — used by BaseParser.can_parse()
    body: str         # Plain-text body — used by BaseParser.extract()
```

### Pattern 6: mypy --strict Typing for GmailResource

**What:** Import `GmailResource` only inside `TYPE_CHECKING` to annotate the service variable without runtime errors (the stub types exist only in `.pyi` files, not at runtime).

**When to use:** Any module that holds a reference to the Gmail service object.

```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from googleapiclient._apis.gmail.v1 import GmailResource


def build_service(creds: Credentials) -> "GmailResource":
    from googleapiclient.discovery import build
    # build() return type is inferred from overloads in discovery.pyi
    service: GmailResource = build("gmail", "v1", credentials=creds)
    return service
```

The `pyproject.toml` already contains the `[[tool.mypy.overrides]]` block for `google.*` and `googleapiclient.*` with `ignore_missing_imports = true`. This means mypy will not complain about the runtime import of `build`. The stubs package adds the overload signatures so `build("gmail", "v1")` returns `GmailResource` precisely. [VERIFIED: official stubs README at github.com/henribru/google-api-python-client-stubs]

### Pattern 7: HttpError Handling

**What:** Catch `googleapiclient.errors.HttpError` for 429 (rate limit) and 403 (quota) responses. Log the status code (not the full error body which may contain PII) and re-raise or return empty.

```python
import time
import random
from googleapiclient.errors import HttpError


def _execute_with_backoff(
    request: Any,
    max_retries: int = 3,
) -> Any:
    """Execute a Google API request with truncated exponential backoff on 429/403."""
    for attempt in range(max_retries + 1):
        try:
            return request.execute()
        except HttpError as exc:
            if exc.status_code in (429, 403) and attempt < max_retries:
                wait = (2 ** attempt) + random.uniform(0, 1)
                # LOG: status_code only — not exc.reason (may contain email metadata)
                time.sleep(wait)
            else:
                raise
```

### Anti-Patterns to Avoid

- **Logging the `sender` or `body` fields:** These are PII. Log only `message_id` (opaque ID) and counts. Violates LOG-02.
- **Logging `creds.to_json()` or any Credentials field:** Contains access tokens. Never log.
- **Requesting `gmail.modify` scope:** Blocks D-03. The tool would be capable of mutating the mailbox. Use `gmail.readonly` only and hard-code the scope constant — do not read it from `.env`.
- **Using `format="raw"`:** Returns the raw RFC 822 message as a single base64url blob; requires a full MIME email parser. `format="full"` gives the pre-parsed `payload` tree and is simpler.
- **Using `format="metadata"`:** Does not return the message body. Insufficient for Phase 3.
- **Fetching all messages then filtering in Python:** Use the `q` parameter to do server-side filtering. Never pull all messages.
- **Calling `flow.run_local_server()` on the Pi:** It will block waiting for a browser callback that never comes. The `load_credentials()` function must only call this path when no refresh token exists (i.e., first-run, laptop).
- **Omitting padding normalisation in base64url decode:** `base64.urlsafe_b64decode()` will raise `binascii.Error` on strings with length % 4 != 0, which is common for Gmail body data.
- **Hardcoding sender addresses in source:** Sender list must come from config (`.env` or parser registry). Real email addresses in source code violates the privacy constraint.
- **Storing token.json in a world-readable location on the Pi:** Recommend `chmod 600 token.json` in the README. Token grants read access to the entire mailbox.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OAuth2 token refresh | Custom HTTP refresh loop | `creds.refresh(Request())` from `google-auth` | google-auth handles token expiry, clock skew, retry on transient failures, and `to_json()` serialisation |
| Gmail search pagination | Manual page offset tracking | `nextPageToken` loop as shown in Pattern 3 | Gmail uses opaque cursor tokens, not numeric offsets; rolling your own will miss messages |
| MIME tree walking | Custom `email` stdlib parser on raw bytes | `format="full"` + recursive `_extract_body()` | Gmail pre-parses the MIME tree in the API response; no need to parse raw RFC 822 |
| base64 decode | `base64.b64decode()` directly on Gmail data | `base64.urlsafe_b64decode()` with padding | Gmail uses the URL-safe alphabet (`-_` not `+/`) and strips `=` padding; standard `b64decode` will fail |
| Rate limit retry | Sleep loop on every request | `HttpError` check + exponential backoff | Retry-after semantics require jitter; naive sleep loops cause thundering-herd on shared quotas |

**Key insight:** Google's auth and API client libraries handle the genuinely hard problems (token lifecycle, retries, discovery caching). The value this phase adds is in the query logic, the MIME extraction, the typed dataclass contract, and the privacy-safe logging discipline.

---

## Common Pitfalls

### Pitfall 1: base64url Padding Error

**What goes wrong:** `base64.urlsafe_b64decode(data)` raises `binascii.Error: Incorrect padding`.
**Why it happens:** Gmail strips trailing `=` characters from base64url-encoded body data. Python's decoder requires the string length to be a multiple of 4.
**How to avoid:** Always normalise: `data + "=" * ((4 - len(data) % 4) % 4)` before decoding. See Pattern 4.
**Warning signs:** Error is triggered on some emails but not others (depends on body length modulo 4).

### Pitfall 2: Scope Mismatch Prompts Re-Authorization

**What goes wrong:** On startup the tool opens a browser consent screen even though token.json exists.
**Why it happens:** `Credentials.from_authorized_user_file(token_path, scopes)` validates that the saved token's scopes are a superset of the requested scopes. If the token was issued with a different scope, `creds.valid` will be `False` and there is no refresh path.
**How to avoid:** Always use the exact scope constant `SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]` — never widen it. If the scope ever changes, delete `token.json` and re-authorize.
**Warning signs:** Interactive consent prompt appears on headless Pi (logs will show `InstalledAppFlow` being entered).

### Pitfall 3: GCP Project in "Testing" Status — 7-Day Refresh Token Expiry

**What goes wrong:** The refresh token becomes invalid after 7 days, breaking the headless Pi path.
**Why it happens:** Google OAuth consent screens in "Testing" (not "Production") publishing status issue refresh tokens that expire in 7 days for external user types.
**How to avoid:** Publish the OAuth consent screen to "Production" status in Google Cloud Console before generating the token that will be used on the Pi. Production status does not require Google review for personal-use apps using only `gmail.readonly`.
**Warning signs:** `google.auth.exceptions.RefreshError: Token has been expired or revoked` appears in logs after ~7 days of Pi operation.

### Pitfall 4: Logging PII

**What goes wrong:** A log line includes `sender=` or `subject=` fields, which get written to the rotating log file. If the log file is ever shared or the project is open-sourced, real email addresses and subjects are exposed.
**Why it happens:** structlog makes it easy to pass arbitrary kwargs to `log.info()`; a developer logs the `RawEmail` object for debugging.
**How to avoid:** Log only `message_id=` (opaque) and `count=N`. Never log `sender`, `body`, or any field that could contain personal information. The `RawEmail` dataclass must not have a `__repr__` that emits those fields in production.
**Warning signs:** Grep the log output for `@` (email address indicator) before merging.

### Pitfall 5: run_local_server() on the Pi

**What goes wrong:** The `load_credentials()` function enters the `InstalledAppFlow` branch on the Raspberry Pi, starts a local HTTP server, and blocks waiting for a browser callback that never arrives.
**Why it happens:** `token.json` was not copied to the Pi before the first run, or the refresh token expired.
**How to avoid:** The `load_credentials()` function should distinguish the two paths. On the Pi, if no refresh token is available, raise a clear `RuntimeError` with instructions instead of entering the browser flow. Alternatively, always pre-copy `token.json` before cron starts, and document this in the README.
**Warning signs:** Process hangs indefinitely; no log output; cron job never returns.

### Pitfall 6: Gmail API Quota on Large Mailboxes

**What goes wrong:** A large lookback window with many matching senders returns hundreds of messages. Each `messages.get` costs 20 quota units; at 6,000 units/minute/user, 300 messages consume the per-minute quota.
**Why it happens:** The per-user rate limit is 6,000 quota units/minute. `messages.get` costs 20 units each (300 calls = 6,000 units = 1 minute quota).
**How to avoid:** The `newer_than:30d` default window and the sender-scoped query keep this bounded in practice for a personal shipping tracker. If rate-limit errors occur, the exponential backoff in Pattern 7 handles them. Do not widen the window beyond 90 days without understanding the quota impact.
**Warning signs:** `HttpError 429` in logs; partial results on first run.

---

## Code Examples

### Synthetic Gmail Message Fixture (for tests)

```python
# tests/fixtures/fake_gmail_message.py
# PRIVACY: All values are synthetic. No real addresses, subjects, or tracking numbers.

FAKE_GMAIL_MESSAGE: dict = {
    "id": "FAKEMESSAGEID001",
    "threadId": "FAKETHREADID001",
    "payload": {
        "mimeType": "multipart/alternative",
        "headers": [
            {"name": "From", "value": "shipping@fakestore.example.com"},
            {"name": "Subject", "value": "Your FAKE order has shipped"},
        ],
        "parts": [
            {
                "mimeType": "text/plain",
                "body": {
                    # base64url of "Your order has shipped!\nTracking: FAKE1234567890\n"
                    "data": "WW91ciBvcmRlciBoYXMgc2hpcHBlZCEKVHJhY2tpbmc6IEZBS0UxMjM0NTY3ODkwCg"
                },
            }
        ],
    },
}
```

### Mocking the Gmail Service in Tests

```python
# tests/test_gmail_client.py
from unittest.mock import MagicMock, patch
from shipping_tracker.gmail.client import fetch_unread_shipping_emails
from tests.fixtures.fake_gmail_message import FAKE_GMAIL_MESSAGE

def test_fetch_returns_raw_emails_for_matching_messages() -> None:
    """fetch_unread_shipping_emails wraps matching messages as RawEmail objects."""
    mock_service = MagicMock()

    # messages().list().execute() returns one page with one message ID
    mock_service.users().messages().list().execute.return_value = {
        "messages": [{"id": "FAKEMESSAGEID001", "threadId": "FAKETHREADID001"}],
        # no nextPageToken -> single page
    }

    # messages().get().execute() returns the full synthetic message
    mock_service.users().messages().get().execute.return_value = FAKE_GMAIL_MESSAGE

    with patch(
        "shipping_tracker.gmail.client.build_service",
        return_value=mock_service,
    ):
        results = fetch_unread_shipping_emails(
            senders=["@fakestore.example.com"],
            window_days=30,
        )

    assert len(results) == 1
    assert results[0].message_id == "FAKEMESSAGEID001"
    assert results[0].sender == "shipping@fakestore.example.com"
    assert "FAKE1234567890" in results[0].body


def test_fetch_returns_empty_list_when_no_messages() -> None:
    """fetch_unread_shipping_emails returns [] when no matching messages exist."""
    mock_service = MagicMock()
    mock_service.users().messages().list().execute.return_value = {}

    with patch("shipping_tracker.gmail.client.build_service", return_value=mock_service):
        results = fetch_unread_shipping_emails(
            senders=["@fakestore.example.com"],
            window_days=30,
        )

    assert results == []
```

### Query Builder Tests (no mocking needed)

```python
# tests/test_gmail_query.py
from shipping_tracker.gmail.query import build_query

def test_build_query_single_sender() -> None:
    q = build_query(["@aliexpress.com"], 30)
    assert q == "is:unread from:(@aliexpress.com) newer_than:30d"

def test_build_query_multiple_senders() -> None:
    q = build_query(["@aliexpress.com", "ship@store.example.com"], 14)
    assert "OR" in q
    assert "newer_than:14d" in q

def test_build_query_empty_senders_returns_unread_query() -> None:
    # Edge case: no senders configured -> returns unread-only query (no from clause)
    # Implementation should handle this gracefully rather than producing invalid syntax
    q = build_query([], 30)
    assert "newer_than:30d" in q
```

### Credentials Auth Test (isolating load_credentials)

```python
# tests/test_gmail_auth.py
import os
import json
from unittest.mock import MagicMock, patch
from shipping_tracker.gmail.auth import load_credentials

def test_load_credentials_refreshes_expired_token(tmp_path) -> None:
    """load_credentials calls creds.refresh() when token is expired with refresh_token."""
    token_file = tmp_path / "token.json"
    # Write a fake token.json (synthetic, no real values)
    token_file.write_text(json.dumps({
        "token": "FAKEACCESSTOKEN",
        "refresh_token": "FAKEREFRESHTOKEN",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "FAKECLIENTID.apps.googleusercontent.com",
        "client_secret": "FAKECLIENTSECRET",
        "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
    }))

    mock_creds = MagicMock()
    mock_creds.valid = False
    mock_creds.expired = True
    mock_creds.refresh_token = "FAKEREFRESHTOKEN"

    with patch("shipping_tracker.gmail.auth.Credentials.from_authorized_user_file",
               return_value=mock_creds), \
         patch("shipping_tracker.gmail.auth.Request"), \
         patch.object(mock_creds, "to_json", return_value='{"token":"REFRESHED"}'):
        load_credentials(str(token_file), "credentials.json")

    mock_creds.refresh.assert_called_once()
```

---

## New `.env` Variables

Add to `.env.example`:

```bash
# Gmail integration (Phase 2)
GMAIL_TOKEN_PATH=token.json
GMAIL_CREDENTIALS_PATH=credentials.json
GMAIL_SENDER_LIST=@aliexpress.com
GMAIL_LOOKBACK_DAYS=30
```

- `GMAIL_SENDER_LIST`: comma-separated list of sender domains/addresses
- `GMAIL_LOOKBACK_DAYS`: integer, default 30; controls `newer_than:Nd` in the query
- `GMAIL_TOKEN_PATH` / `GMAIL_CREDENTIALS_PATH`: paths (relative to cwd) to the secret files

**Parsing `GMAIL_SENDER_LIST`:** Split on commas and strip whitespace:
```python
senders = [s.strip() for s in os.getenv("GMAIL_SENDER_LIST", "").split(",") if s.strip()]
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `oauth2client` (deprecated) | `google-auth` + `google-auth-oauthlib` | ~2019 | `oauth2client` is unmaintained; all modern Google Python samples use `google-auth` |
| `Credentials.from_authorized_user_info(json.load(...))` | `Credentials.from_authorized_user_file(path, scopes)` | Current | Convenience classmethod; reads and parses the file; prefer this over manual json.load |
| `flow.run_console()` | `flow.run_local_server(port=0)` | Current | `run_console()` requires copying an auth code; `run_local_server(port=0)` handles the redirect automatically and is the current recommended method |

**Deprecated/outdated:**
- `oauth2client`: replaced by `google-auth`; do not install or reference it
- `flow.run_console()`: still available but `run_local_server(port=0)` is the modern equivalent for the laptop first-run path

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `GmailResource` is the correct type name importable from `googleapiclient._apis.gmail.v1` for annotating the `build("gmail", "v1")` return value | Standard Stack, Pattern 6 | Planner should verify by checking the stubs package after install: `python -c "from googleapiclient._apis.gmail.v1 import GmailResource"` inside TYPE_CHECKING guard |
| A2 | Publishing the OAuth consent screen to "Production" in Google Cloud Console does not require a Google review for personal apps using only `gmail.readonly` | Pitfall 3 | If Google review is required, the 7-day token expiry workaround would be to use a "test user" allowlist — user adds their own Google account as a test user in GCP console |

---

## Open Questions (RESOLVED)

> All three resolved during Phase 2 planning (2026-05-31); resolutions are implemented in 02-01/02-02-PLAN.md.

1. **Sender list source: `.env` config value vs. parser-derived domains**
   - What we know: `BaseParser.can_parse(email_body, sender)` already takes `sender`; each future parser knows which senders it handles
   - What's unclear: whether to let each parser declare its own `sender_domains: list[str]` and aggregate them, or keep a flat `GMAIL_SENDER_LIST` in `.env`
   - Recommendation: For Phase 2 (v1, AliExpress only), a flat `.env` value is simplest. The planner should add a note that Phase 3 will want to revisit this so the parser registration step can also register sender domains — reduces config drift when new parsers are added.
   - **RESOLVED:** Flat `GMAIL_SENDER_LIST` in `.env` for Phase 2 (parsed in `main()`); Phase 3 can add parser-declared sender domains at parser registration.

2. **`RawEmail.sender` field value: full `From:` header vs. extracted address only**
   - What we know: Gmail `From:` headers often look like `"AliExpress <shipping@mail.aliexpress.com>"`; `BaseParser.can_parse()` receives `sender` as a string
   - What's unclear: whether parsers should match against the full header string or just the email address part
   - Recommendation: Extract just the email address (the part inside `<>` if present, otherwise the whole value) to normalise across senders. This keeps `can_parse()` simple and consistent.
   - **RESOLVED:** Extract the bare address (inside `<>` if present, else the whole value) via `_extract_sender()` in `client.py` (implemented in 02-02).

3. **`token.json` file path on the Pi**
   - What we know: default `GMAIL_TOKEN_PATH=token.json` puts it in the working directory of the cron job
   - What's unclear: whether the cron working directory is predictable enough, or whether an absolute path is safer
   - Recommendation: Document in README that the cron `cd` line should set the working directory, and that `token.json` should be `chmod 600`. The planner can add a `.env.example` note.
   - **RESOLVED:** `GMAIL_TOKEN_PATH` in `.env` (default `token.json`); cron `cd` + `chmod 600 token.json` documented in the Phase 6 README. Not a Phase 2 code concern.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | All code | Assumed (Pi has Bookworm) | — | — |
| `google-api-python-client` | Gmail service | Not yet installed | 2.197.0 (latest) | None — required |
| `google-auth-oauthlib` | OAuth2 flow | Not yet installed | 1.4.0 (latest) | None — required |
| `google-auth` | Credential refresh | Not yet installed | 2.53.0 (latest) | None — required |
| `google-api-python-client-stubs` | mypy --strict typing | Not yet installed | 1.37.0 (latest) | Fallback: use `Any` with `# type: ignore` — acceptable but reduces type safety |
| `credentials.json` | First-run auth | Must be created by user | — | No fallback — user must create a GCP project and OAuth2 client |
| `token.json` | Every run (Pi) | Must be generated on laptop | — | No fallback — user must complete the first-run flow |

**Missing dependencies with no fallback:**
- `google-api-python-client`, `google-auth-oauthlib`, `google-auth` — add to `pyproject.toml` `[project.dependencies]` in Wave 0
- `credentials.json` and `token.json` — documented in README (Phase 6); must exist before the tool can run

**Missing dependencies with fallback:**
- `google-api-python-client-stubs` — dev-only; without it, annotate the service as `Any` with a comment

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.x |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_gmail_auth.py tests/test_gmail_query.py tests/test_gmail_client.py -x` |
| Full suite command | `pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GMAIL-01 | `load_credentials()` refreshes expired token non-interactively | unit | `pytest tests/test_gmail_auth.py -x` | ❌ Wave 0 |
| GMAIL-01 | `load_credentials()` invokes `run_local_server()` when no refresh token | unit | `pytest tests/test_gmail_auth.py -x` | ❌ Wave 0 |
| GMAIL-02 | `build_query()` produces correct `q` string for single and multiple senders | unit | `pytest tests/test_gmail_query.py -x` | ❌ Wave 0 |
| GMAIL-02 | `fetch_unread_shipping_emails()` returns `RawEmail` list from mocked service | unit | `pytest tests/test_gmail_client.py -x` | ❌ Wave 0 |
| GMAIL-02 | `fetch_unread_shipping_emails()` follows pagination (multiple pages) | unit | `pytest tests/test_gmail_client.py -x` | ❌ Wave 0 |
| GMAIL-02 | `fetch_unread_shipping_emails()` returns `[]` when no messages | unit | `pytest tests/test_gmail_client.py -x` | ❌ Wave 0 |
| GMAIL-02 | `_decode_base64url()` handles missing padding correctly | unit | `pytest tests/test_gmail_client.py -x` | ❌ Wave 0 |
| GMAIL-03 | `token.json` is written after credential refresh | unit | `pytest tests/test_gmail_auth.py -x` | ❌ Wave 0 |
| LOG-02 | No `sender` or `body` content appears in log output during a fetch | unit | `pytest tests/test_gmail_client.py -x` (capture log output, assert no PII) | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_gmail_auth.py tests/test_gmail_query.py tests/test_gmail_client.py -x`
- **Per wave merge:** `pytest` (full suite)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/fixtures/fake_gmail_message.py` — synthetic message fixture (FAKE data only)
- [ ] `tests/test_gmail_auth.py` — covers GMAIL-01, GMAIL-03
- [ ] `tests/test_gmail_query.py` — covers GMAIL-02 query construction
- [ ] `tests/test_gmail_client.py` — covers GMAIL-02 fetch loop, pagination, body decode, PII log safety
- [ ] `shipping_tracker/gmail/__init__.py`
- [ ] `shipping_tracker/gmail/auth.py`
- [ ] `shipping_tracker/gmail/client.py`
- [ ] `shipping_tracker/gmail/query.py`

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | OAuth2 via google-auth-oauthlib; `gmail.readonly` scope only |
| V3 Session Management | yes | `token.json` = persisted session; `chmod 600`; git-ignored |
| V4 Access Control | yes | `gmail.readonly` scope enforced at API level; never request write scope |
| V5 Input Validation | yes | Sender list and window_days validated before query construction |
| V6 Cryptography | no | Token storage is plaintext JSON (Google standard); encryption not required for single-user Pi |

### Known Threat Patterns for Gmail OAuth Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Token theft (token.json exposed) | Info Disclosure | `chmod 600 token.json`; git-ignore; never log token contents |
| Scope creep (code requests write scope) | Tampering | Hard-code `SCOPES` constant; never read scope from config |
| credentials.json in git history | Info Disclosure | `.gitignore` already excludes it (Phase 1 T-01-01); pre-commit hook |
| Log PII (sender/body in structured logs) | Info Disclosure | LOG-02 discipline; structlog field filtering; test asserts no PII in log output |
| Phishing via widened scope on re-auth | Spoofing | Consistent scope constant prevents scope-upgrade prompts |

---

## Sources

### Primary (HIGH confidence)

- [Google Gmail API Python Quickstart](https://developers.google.com/gmail/api/quickstart/python) — OAuth2 flow, `InstalledAppFlow`, `Credentials`, `build()`, verified code pattern
- [Gmail API users.messages.list Reference](https://developers.google.com/gmail/api/reference/rest/v1/users.messages/list) — `q`, `pageToken`, `labelIds`, response structure
- [Gmail API Format Enum](https://developers.google.com/gmail/api/reference/rest/v1/Format) — full/minimal/raw/metadata definitions
- [Gmail API List Messages Guide](https://developers.google.com/workspace/gmail/api/guides/list-messages) — pagination pattern, Python example
- [google-auth Credentials Reference](https://google-auth.readthedocs.io/en/stable/reference/google.oauth2.credentials.html) — `valid`, `expired`, `refresh_token`, `refresh()`, `from_authorized_user_file()`, `to_json()`
- [google-api-python-client Mocks Guide](https://googleapis.github.io/google-api-python-client/docs/mocks.html) — `HttpMock`, `HttpMockSequence`
- [Gmail API Error Handling Guide](https://developers.google.com/workspace/gmail/api/guides/handle-errors) — 429/403 error codes, exponential backoff guidance
- [Gmail API Quota Reference](https://developers.google.com/workspace/gmail/api/reference/quota) — units/request: `messages.list` = 5, `messages.get` = 20; 6,000 units/min/user
- [google-api-python-client-stubs on PyPI](https://pypi.org/project/google-api-python-client-stubs/) — v1.37.0 confirmed; stubs auto-generated from Discovery Documents
- [github.com/henribru/google-api-python-client-stubs](https://github.com/henribru/google-api-python-client-stubs) — `TYPE_CHECKING` import pattern for `GmailResource`

### Secondary (MEDIUM confidence)

- [gmail_v1.users.messages Dynamic Docs](https://googleapis.github.io/google-api-python-client/docs/dyn/gmail_v1.users.messages.html) — `format="full"` payload structure, `parts` traversal

### Tertiary (LOW confidence)

- Community guidance on base64url padding normalisation — cross-verified against Python `base64` stdlib docs

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified on PyPI registry; versions confirmed
- OAuth2 flow: HIGH — code pattern from official Google quickstart docs
- Gmail query syntax: HIGH — from official API reference
- mypy typing strategy: HIGH — verified against published stubs package
- Test mocking strategy: HIGH — from official mocks guide
- Pitfalls: HIGH — base64 padding verified against stdlib; scope/token pitfalls from official auth docs and error handling guide

**Research date:** 2026-05-31
**Valid until:** 2026-07-01 (Gmail API is stable; stubs version may update sooner)
