"""BaseParser abstract interface — all email parsers inherit from this class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TrackingInfo:
    """Structured tracking data extracted from a shipping email."""

    tracking_number: str
    carrier: str | None = None


class BaseParser(ABC):
    """Abstract base class for email shipping parsers.

    Implement `can_parse` and `extract` to register a new parser.
    Phase 3 adds AliExpressParser; further parsers are drop-in additions
    to the parser registry in main.py with no core changes required.
    """

    @abstractmethod
    def can_parse(self, email_body: str, sender: str) -> bool:
        """Return True if this parser handles the given email.

        Args:
            email_body: Plain-text body of the email.
            sender: From address of the email.

        Returns:
            True if this parser should handle the email.
        """
        ...

    @abstractmethod
    def extract(self, email_body: str) -> TrackingInfo | None:
        """Extract tracking info from a matching email.

        Args:
            email_body: Plain-text body of the email.

        Returns:
            TrackingInfo with tracking_number populated, or None if the email
            matches but contains no tracking number (e.g., pre-shipment order
            confirmation emails — expected routine case per D-05).
        """
        ...
