"""Gmail client — service construction, message fetch loop, and RawEmail assembly."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from googleapiclient.discovery import build

if TYPE_CHECKING:
    from googleapiclient._apis.gmail.v1 import GmailResource

from google.oauth2.credentials import Credentials

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


def build_service(creds: Credentials) -> GmailResource:
    """Build and return a Gmail API service resource.

    Args:
        creds: A valid Credentials object from load_credentials().

    Returns:
        A GmailResource (gmail v1) ready for API calls.
    """
    service: GmailResource = build("gmail", "v1", credentials=creds)
    return service
