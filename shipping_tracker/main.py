"""Pipeline orchestrator — Gmail fetch and parser dispatch wired in Phase 3."""

import logging
import os

from dotenv import load_dotenv

from shipping_tracker.gmail import fetch_unread_shipping_emails
from shipping_tracker.logging_config import configure_logging
from shipping_tracker.parsers.aliexpress import (
    ALIEXPRESS_SENDER_DOMAINS,
    AliExpressParser,
)
from shipping_tracker.parsers.base import BaseParser, TrackingInfo

logger = logging.getLogger(__name__)

# Parser registry — first-match-wins dispatch order (D-03).
# Instances are created once at module load, not inside the loop.
# Append new parser instances here to extend fetch scope automatically (D-01).
PARSERS: list[BaseParser] = [
    AliExpressParser(),
]


def _get_all_sender_domains() -> list[str]:
    """Return all sender domains declared by registered parsers (D-01).

    This is the single source of truth for the Gmail from:() query.
    Adding a new parser automatically extends the fetch scope.
    """
    return list(ALIEXPRESS_SENDER_DOMAINS)


def main() -> int:
    """Run the shipping-tracker pipeline.

    Returns:
        0 on success, non-zero on unrecoverable error.

    Phase 3: loads environment, configures logging, fetches unread shipping
    emails via Gmail API, dispatches each email through the parser registry
    (first-match-wins, D-03), collects TrackingInfo results, and returns 0.
    Phases 4–5 wire in deduplication and TrackingMore registration without
    changing this function's signature.
    """
    load_dotenv()
    configure_logging()

    senders = _get_all_sender_domains()
    window = int(os.getenv("GMAIL_LOOKBACK_DAYS", "30"))

    try:
        emails = fetch_unread_shipping_emails(senders, window)
    except FileNotFoundError as exc:
        logger.error("gmail.credentials.missing path=%s", exc.filename)
        return 1

    logger.warning("gmail.fetch.complete count=%d", len(emails))

    tracking_results: list[TrackingInfo] = []
    for email in emails:
        matched = False
        for parser in PARSERS:
            if parser.can_parse(email.body, email.sender):
                matched = True
                result = parser.extract(email.body)
                if result is None:
                    # Expected for pre-shipment "order confirmed" emails (D-05)
                    logger.debug("parser.no_tracking id=%s", email.message_id)
                else:
                    tracking_results.append(result)
                break  # first match wins (D-03)
        if not matched:
            logger.info("parser.no_match id=%s", email.message_id)

    logger.warning(
        "parser.dispatch.complete total=%d parsed=%d",
        len(emails),
        len(tracking_results),
    )
    return 0
