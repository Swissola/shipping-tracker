"""Pipeline orchestrator — Gmail fetch and parser dispatch wired in Phase 3."""

import logging
import os

from dotenv import load_dotenv

from shipping_tracker.gmail import fetch_unread_shipping_emails
from shipping_tracker.logging_config import configure_logging
from shipping_tracker.parsers.aliexpress import AliExpressParser
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

    This is the single source of truth for the Gmail from:() query. It
    aggregates the ``sender_domains`` declared by every parser in ``PARSERS``,
    so appending a new parser (a single self-contained file) automatically
    extends the fetch scope — no edit to this function is required (CR-02).

    Domains are de-duplicated while preserving first-seen order so the
    generated query is stable across runs.
    """
    domains: list[str] = []
    for parser in PARSERS:
        for domain in parser.sender_domains:
            if domain not in domains:
                domains.append(domain)
    return domains


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

    # WR-03: gmail.client already logs "gmail.fetch.complete" at INFO — the
    # duplicate WARNING emission that used to live here has been removed so
    # there is a single source of truth for that log line.

    tracking_results: list[TrackingInfo] = []
    for email in emails:
        # WR-04: isolate each email's dispatch so one malformed body that makes
        # a parser raise is logged PII-safely (message_id only — LOG-02),
        # skipped, and the batch continues. One bad email never aborts the run.
        try:
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
        except Exception:
            # PII-safe: log message_id only, never body or sender (LOG-02).
            logger.exception("parser.dispatch.error id=%s", email.message_id)
            continue

    # WR-03: routine end-of-run summary belongs at INFO, not WARNING, so
    # WARNING-level alerting does not false-alarm on every healthy cron run.
    logger.info(
        "parser.dispatch.complete total=%d parsed=%d",
        len(emails),
        len(tracking_results),
    )
    return 0
