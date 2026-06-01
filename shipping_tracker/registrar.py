"""Registrar Protocol and NullRegistrar placeholder.

PRIVACY (LOG-02): implementations MUST NOT embed tracking_number, carrier, or
any email content in exception messages. The dispatch loop logs only message_id
and type(exc).__name__ — a careless implementation that includes PII in its
exception string would defeat that guarantee.
"""

from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class Registrar(Protocol):
    """Callable protocol for registering a tracking number with an API."""

    def __call__(self, tracking_number: str, carrier: str | None) -> bool:
        """Register a tracking number.

        Returns True on success (including TRACK-03 already-exists responses).
        Returns False or raises on any failure — caller will not persist rows.

        LOG-02: implementations MUST NOT embed tracking_number, carrier, or any
        email content in exception messages.
        """
        ...


class NullRegistrar:
    """Phase 4 placeholder — logs at debug, always returns False (deferred).

    Phase 5 replaces this with TrackingMoreRegistrar; zero changes to db.py
    or main.py are required.
    """

    def __call__(self, tracking_number: str, carrier: str | None) -> bool:
        logger.debug("registrar.deferred")  # no tracking_number — LOG-02
        return False
