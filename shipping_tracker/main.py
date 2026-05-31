"""Pipeline orchestrator — Gmail fetch wired in Phase 2."""

import logging
import os

from dotenv import load_dotenv

from shipping_tracker.gmail import fetch_unread_shipping_emails
from shipping_tracker.logging_config import configure_logging

logger = logging.getLogger(__name__)


def main() -> int:
    """Run the shipping-tracker pipeline.

    Returns:
        0 on success, non-zero on unrecoverable error.

    Phase 2: loads environment, configures logging, fetches unread shipping
    emails via Gmail API, and returns 0. Phases 3–5 wire in email parsing,
    deduplication, and TrackingMore registration without changing this
    function's signature.
    """
    load_dotenv()
    configure_logging()

    senders = [
        s.strip() for s in os.getenv("GMAIL_SENDER_LIST", "").split(",") if s.strip()
    ]
    window = int(os.getenv("GMAIL_LOOKBACK_DAYS", "30"))

    try:
        emails = fetch_unread_shipping_emails(senders, window)
    except FileNotFoundError as exc:
        logger.error("gmail.credentials.missing path=%s", exc.filename)
        return 1

    logger.warning("gmail.fetch.complete count=%d", len(emails))
    return 0
