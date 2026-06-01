"""SQLite state layer — idempotent schema init and dedup helpers.

Single-threaded: the connection is created in main() and passed in explicitly.
Do not share a connection across threads without setting check_same_thread=False.

PRIVACY (LOG-02): no function in this module may log tracking_number values.
Log only message_id (opaque, non-PII) and row counts.
"""

from __future__ import annotations

import datetime
import logging
import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shipping_tracker.registrar import Registrar

logger = logging.getLogger(__name__)


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables and set PRAGMAs. Idempotent — safe to call on every run."""
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS processed_emails (
            message_id   TEXT PRIMARY KEY,
            processed_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS registered_tracking (
            tracking_number TEXT PRIMARY KEY,
            registered_at   TEXT NOT NULL,
            source_email_id TEXT NOT NULL,
            last_status     TEXT,
            last_status_at  TEXT
        )
        """
    )
    conn.execute("PRAGMA user_version = 1")
    conn.commit()


def is_email_processed(conn: sqlite3.Connection, message_id: str) -> bool:
    """Return True if message_id is already in processed_emails (DEDUP-03)."""
    row = conn.execute(
        "SELECT 1 FROM processed_emails WHERE message_id = ?",
        (message_id,),
    ).fetchone()
    return row is not None


def is_tracking_registered(conn: sqlite3.Connection, tracking_number: str) -> bool:
    """Return True if tracking_number is already in registered_tracking (DEDUP-04)."""
    row = conn.execute(
        "SELECT 1 FROM registered_tracking WHERE tracking_number = ?",
        (tracking_number,),
    ).fetchone()
    return row is not None


def register_and_persist(
    conn: sqlite3.Connection,
    message_id: str,
    tracking_number: str,
    registrar: Registrar,
) -> bool:
    """Call registrar; on success write both rows atomically; on failure write neither.

    Returns True if rows were persisted (registration succeeded).
    Returns False if registrar returned False — neither row is written.
    Re-raises any exception from registrar so main.py WR-04 handler logs once
    (LOG-02 single log site; D-08).

    PRIVACY (LOG-02): this function logs only message_id and never tracking_number.
    """
    try:
        success = registrar(tracking_number, None)  # carrier deferred to Phase 5
    except Exception:
        raise  # propagate to main.py WR-04 handler — single log site (D-08)
    if not success:
        return False
    now = datetime.datetime.now(datetime.UTC).isoformat()
    with conn:  # commits on block exit; rolls back on any exception (D-01)
        conn.execute(
            "INSERT INTO processed_emails VALUES (?, ?)",
            (message_id, now),
        )
        conn.execute(
            "INSERT INTO registered_tracking VALUES (?, ?, ?, NULL, NULL)",
            (tracking_number, now, message_id),
        )
    return True
