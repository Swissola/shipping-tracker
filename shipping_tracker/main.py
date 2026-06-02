"""Pipeline orchestrator — Gmail fetch, parser dispatch, and dedup wiring (Phase 4)."""

from __future__ import annotations

import datetime
import logging
import os
import sqlite3

import httpx
from dotenv import load_dotenv

from shipping_tracker.db import (
    init_db,
    is_email_processed,
    is_tracking_registered,
    register_and_persist,
)
from shipping_tracker.gmail import fetch_unread_shipping_emails
from shipping_tracker.logging_config import configure_logging
from shipping_tracker.parsers.aliexpress import AliExpressParser
from shipping_tracker.parsers.base import BaseParser, TrackingInfo
from shipping_tracker.registrar import (
    QuotaExceededError,
    Registrar,
    TrackingMoreRegistrar,
)

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

    Phase 4: opens one SQLite connection per run, inits the schema once, injects
    a NullRegistrar seam, and threads the connection through the dedup-wired
    dispatch loop. Phase 5 swaps NullRegistrar for TrackingMoreRegistrar with zero
    changes to db.py or this loop.
    """
    load_dotenv()
    configure_logging()

    # D-05: fail-fast before any I/O if TRACKINGMORE_API_KEY is missing/empty.
    # Runs before the Gmail fetch and before the DB open. Never log the key value.
    api_key = os.getenv("TRACKINGMORE_API_KEY", "").strip()
    if not api_key:
        logger.error("config.missing_api_key")  # LOG-02: no key value
        return 1

    db_path = os.getenv("DATABASE_PATH", "data/shipping-tracker.db")
    # WR-02: only create a directory when db_path actually has one, so the
    # makedirs target matches where sqlite3.connect writes. A bare filename
    # (e.g. tracker.db) or ":memory:" must NOT fabricate a spurious data/ dir.
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)

    # Pitfall 4: main() owns the httpx.Client lifetime — named local so it can be
    # closed in finally. Inject it into the registrar (D-04 testable seam).
    http_client = httpx.Client(timeout=10.0)  # D-03: 10s timeout

    try:
        init_db(conn)
        # Phase 5: real registrar against the injected client.
        registrar: Registrar = TrackingMoreRegistrar(
            api_key=api_key, client=http_client
        )

        senders = _get_all_sender_domains()
        window = int(os.getenv("GMAIL_LOOKBACK_DAYS", "30"))

        try:
            emails = fetch_unread_shipping_emails(senders, window)
        except FileNotFoundError as exc:
            # WR-04 / privacy: log only the basename. exc.filename may be an
            # absolute path like /home/<user>/.config/.../credentials.json, which
            # would leak an OS username into a log destined for a public project.
            logger.error(
                "gmail.credentials.missing name=%s",
                os.path.basename(exc.filename or ""),
            )
            return 1

        # WR-03: gmail.client already logs "gmail.fetch.complete" at INFO — the
        # duplicate WARNING emission that used to live here has been removed so
        # there is a single source of truth for that log line.

        tracking_results: list[TrackingInfo] = []
        for email in emails:
            # WR-04: isolate each email's dispatch so one malformed body that makes
            # a parser or registrar raise is logged PII-safely (message_id only —
            # LOG-02), skipped, and the batch continues. One bad email never aborts
            # the run.
            try:
                # DEDUP-03: skip already-processed email (before any parse work)
                if is_email_processed(conn, email.message_id):
                    logger.debug("dedup.email.skip id=%s", email.message_id)
                    continue

                matched = False
                result: TrackingInfo | None = None
                for parser in PARSERS:
                    if parser.can_parse(email.body, email.sender):
                        matched = True
                        result = parser.extract(email.body)
                        break  # first match wins (D-03)

                if not matched:
                    logger.info("parser.no_match id=%s", email.message_id)
                    continue
                if result is None:
                    # Expected for pre-shipment "order confirmed" emails (D-02)
                    logger.debug("parser.no_tracking id=%s", email.message_id)
                    continue  # D-02: left unmarked, re-evaluated next run

                # DEDUP-04: tracking already registered (duplicate-notification email)
                if is_tracking_registered(conn, result.tracking_number):
                    logger.debug("dedup.tracking.skip id=%s", email.message_id)
                    # D-03: mark this email done to avoid re-parse churn
                    now = datetime.datetime.now(datetime.UTC).isoformat()
                    with conn:
                        conn.execute(
                            "INSERT OR IGNORE INTO processed_emails VALUES (?, ?)",
                            (email.message_id, now),
                        )
                    continue

                # DEDUP-05: register-then-persist (atomic)
                persisted = register_and_persist(
                    conn,
                    email.message_id,
                    result.tracking_number,
                    registrar,
                    carrier=result.carrier,  # D-08: optional courier hint
                )
                if persisted:
                    tracking_results.append(result)

            except QuotaExceededError:
                # D-06 CRITICAL: MUST precede the broad except Exception below, or
                # the broad catch swallows this and the loop continues. D-01/D-07:
                # one WARNING summary, no PII; break so remaining numbers retry next
                # cron via DEDUP-05.
                logger.warning("registrar.quota_exceeded")
                break

            except Exception as exc:
                # WR-04: PII-safe — log message_id + exception TYPE only (LOG-02).
                # NOT logger.exception — the traceback and exception message could
                # embed email content if a parser/registrar raised e.g.
                # ValueError(f"bad body: {body}"). type(exc).__name__ is structural,
                # never PII.
                logger.error(
                    "pipeline.error id=%s type=%s",
                    email.message_id,
                    type(exc).__name__,
                )
                continue

        # WR-03: routine end-of-run summary belongs at INFO, not WARNING, so
        # WARNING-level alerting does not false-alarm on every healthy cron run.
        logger.info(
            "parser.dispatch.complete total=%d parsed=%d",
            len(emails),
            len(tracking_results),
        )
    finally:
        conn.close()
        http_client.close()  # Pitfall 4: main() owns and closes the connection pool

    return 0
