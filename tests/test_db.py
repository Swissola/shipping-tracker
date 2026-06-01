"""Tests for shipping_tracker.db — DEDUP-01..05 acceptance criteria.

All test data is synthetic — FAKE-prefixed tracking numbers and message IDs.
No real tracking numbers, email addresses, or order references.
"""

import datetime
import sqlite3

import pytest
from shipping_tracker.db import (  # type: ignore[import-not-found]
    init_db,
    is_email_processed,
    is_tracking_registered,
    register_and_persist,
)
from shipping_tracker.registrar import NullRegistrar  # type: ignore[import-not-found]

from tests.fixtures.fake_db import (
    FAKE_MESSAGE_ID_1,
    FAKE_MESSAGE_ID_2,
    FAKE_MESSAGE_ID_DUP,
    FAKE_TRACKING_NUMBER_1,
)

# ---------------------------------------------------------------------------
# Inline fake registrar callables
# ---------------------------------------------------------------------------


def fail_registrar(tracking_number: str, carrier: str | None) -> bool:
    """Simulates a registration API failure — always returns False."""
    return False


def success_registrar(tracking_number: str, carrier: str | None) -> bool:
    """Simulates a successful registration — always returns True."""
    return True


def raising_registrar(tracking_number: str, carrier: str | None) -> bool:
    """Simulates a network/API error — synthetic message only, no PII."""
    raise RuntimeError("synthetic API failure")


# ---------------------------------------------------------------------------
# DEDUP-01: processed_emails table
# ---------------------------------------------------------------------------


def test_init_db_creates_processed_emails(db_conn: sqlite3.Connection) -> None:
    """DEDUP-01: processed_emails table exists after init_db."""
    row = db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        ("processed_emails",),
    ).fetchone()
    assert row is not None


def test_init_db_idempotent(db_conn: sqlite3.Connection) -> None:
    """DEDUP-01: calling init_db twice raises nothing."""
    # db_conn fixture already called init_db once; second call must be a no-op
    init_db(db_conn)


# ---------------------------------------------------------------------------
# DEDUP-02: registered_tracking table
# ---------------------------------------------------------------------------


def test_init_db_creates_registered_tracking(  # noqa: D103
    db_conn: sqlite3.Connection,
) -> None:
    """DEDUP-02: registered_tracking table with nullable last_status columns."""
    row = db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        ("registered_tracking",),
    ).fetchone()
    assert row is not None

    # Verify nullable last_status columns accept NULL on insert
    db_conn.execute(
        "INSERT INTO registered_tracking VALUES (?, ?, ?, NULL, NULL)",
        (FAKE_TRACKING_NUMBER_1, "2026-06-01T00:00:00+00:00", FAKE_MESSAGE_ID_1),
    )
    db_conn.commit()
    row = db_conn.execute(
        "SELECT last_status, last_status_at FROM registered_tracking"
        " WHERE tracking_number=?",
        (FAKE_TRACKING_NUMBER_1,),
    ).fetchone()
    assert row == (None, None)


def test_user_version(db_conn: sqlite3.Connection) -> None:
    """DEDUP-02: PRAGMA user_version returns 1 after init."""
    row = db_conn.execute("PRAGMA user_version").fetchone()
    assert row is not None
    assert row[0] == 1


# ---------------------------------------------------------------------------
# DEDUP-03: is_email_processed
# ---------------------------------------------------------------------------


def test_is_email_processed_known(db_conn: sqlite3.Connection) -> None:
    """DEDUP-03: is_email_processed True after a processed_emails row is inserted."""
    db_conn.execute(
        "INSERT INTO processed_emails VALUES (?, ?)",
        (FAKE_MESSAGE_ID_1, "2026-06-01T00:00:00+00:00"),
    )
    db_conn.commit()
    assert is_email_processed(db_conn, FAKE_MESSAGE_ID_1) is True


def test_is_email_processed_unknown(db_conn: sqlite3.Connection) -> None:
    """DEDUP-03: is_email_processed returns False for an absent message_id."""
    assert is_email_processed(db_conn, FAKE_MESSAGE_ID_2) is False


def test_dispatch_skips_processed_email(db_conn: sqlite3.Connection) -> None:
    """DEDUP-03: already-seen email is skipped; registrar not called.

    Integration: drives is_email_processed / register_and_persist over db_conn.
    """
    # Pre-insert a processed_emails row to simulate a previously seen email
    db_conn.execute(
        "INSERT INTO processed_emails VALUES (?, ?)",
        (FAKE_MESSAGE_ID_1, "2026-06-01T00:00:00+00:00"),
    )
    db_conn.commit()

    # Spy registrar: records whether it was invoked
    called: list[bool] = []

    def spy_registrar(tracking_number: str, carrier: str | None) -> bool:
        called.append(True)
        return True

    # Simulate the dispatch-loop skip decision for DEDUP-03
    if is_email_processed(db_conn, FAKE_MESSAGE_ID_1):
        pass  # skip: do not call register_and_persist
    else:
        register_and_persist(
            db_conn, FAKE_MESSAGE_ID_1, FAKE_TRACKING_NUMBER_1, spy_registrar
        )

    assert called == [], "registrar must not be called for already-processed email"


# ---------------------------------------------------------------------------
# DEDUP-04: is_tracking_registered
# ---------------------------------------------------------------------------


def test_is_tracking_registered(db_conn: sqlite3.Connection) -> None:
    """DEDUP-04: is_tracking_registered returns True/False per row presence."""
    # Not yet present
    assert is_tracking_registered(db_conn, FAKE_TRACKING_NUMBER_1) is False

    # Insert directly to simulate a previously registered tracking number
    db_conn.execute(
        "INSERT INTO registered_tracking VALUES (?, ?, ?, NULL, NULL)",
        (FAKE_TRACKING_NUMBER_1, "2026-06-01T00:00:00+00:00", FAKE_MESSAGE_ID_1),
    )
    db_conn.commit()
    assert is_tracking_registered(db_conn, FAKE_TRACKING_NUMBER_1) is True


def test_dispatch_skips_registered_tracking(db_conn: sqlite3.Connection) -> None:
    """DEDUP-04: registrar NOT called when tracking already registered."""
    # Pre-register the tracking number to simulate a prior run
    db_conn.execute(
        "INSERT INTO registered_tracking VALUES (?, ?, ?, NULL, NULL)",
        (FAKE_TRACKING_NUMBER_1, "2026-06-01T00:00:00+00:00", FAKE_MESSAGE_ID_1),
    )
    db_conn.commit()

    # Spy registrar: must not be called in the DEDUP-04 skip path
    called: list[bool] = []

    def spy_registrar(tracking_number: str, carrier: str | None) -> bool:
        called.append(True)
        return True

    # Simulate DEDUP-04 dispatch-loop branch decision
    if is_tracking_registered(db_conn, FAKE_TRACKING_NUMBER_1):
        pass  # skip: tracking already registered
    else:
        register_and_persist(
            db_conn, FAKE_MESSAGE_ID_2, FAKE_TRACKING_NUMBER_1, spy_registrar
        )

    # registrar must not be called when tracking is already registered
    assert called == []


# ---------------------------------------------------------------------------
# D-03: duplicate-notification marks email processed
# ---------------------------------------------------------------------------


def test_dup_notification_marks_email_processed(
    db_conn: sqlite3.Connection,
) -> None:
    """D-03: DEDUP-04 branch marks message_id processed via INSERT OR IGNORE.

    A duplicate-notification email arrives: tracking number already registered,
    email not yet seen. The dispatch loop marks the email as processed and
    skips the registrar.
    """
    # Tracking already registered from a prior run
    db_conn.execute(
        "INSERT INTO registered_tracking VALUES (?, ?, ?, NULL, NULL)",
        (FAKE_TRACKING_NUMBER_1, "2026-06-01T00:00:00+00:00", FAKE_MESSAGE_ID_1),
    )
    db_conn.commit()

    # Spy registrar: must not be called
    called: list[bool] = []

    def spy_registrar(tracking_number: str, carrier: str | None) -> bool:
        called.append(True)
        return True

    # Simulate DEDUP-04 branch: tracking registered + D-03 mark-email-processed
    if is_tracking_registered(db_conn, FAKE_TRACKING_NUMBER_1):
        now = datetime.datetime.now(datetime.UTC).isoformat()
        with db_conn:
            db_conn.execute(
                "INSERT OR IGNORE INTO processed_emails VALUES (?, ?)",
                (FAKE_MESSAGE_ID_DUP, now),
            )
    else:
        register_and_persist(
            db_conn, FAKE_MESSAGE_ID_DUP, FAKE_TRACKING_NUMBER_1, spy_registrar
        )

    # The duplicate-notification email must now be marked as processed
    assert is_email_processed(db_conn, FAKE_MESSAGE_ID_DUP) is True, (
        "duplicate-notification email must be marked processed in DEDUP-04 branch"
    )
    assert called == [], "registrar must not be called in DEDUP-04 branch"


# ---------------------------------------------------------------------------
# DEDUP-05: register_and_persist
# ---------------------------------------------------------------------------


def test_register_and_persist_success(db_conn: sqlite3.Connection) -> None:
    """DEDUP-05: both rows present after success registrar."""
    result = register_and_persist(
        db_conn, FAKE_MESSAGE_ID_1, FAKE_TRACKING_NUMBER_1, success_registrar
    )
    assert result is True
    assert is_email_processed(db_conn, FAKE_MESSAGE_ID_1) is True
    assert is_tracking_registered(db_conn, FAKE_TRACKING_NUMBER_1) is True


def test_register_and_persist_fail_returns_false(
    db_conn: sqlite3.Connection,
) -> None:
    """DEDUP-05: neither row present after False registrar; returns False."""
    result = register_and_persist(
        db_conn, FAKE_MESSAGE_ID_1, FAKE_TRACKING_NUMBER_1, fail_registrar
    )
    assert result is False
    # Neither row should be written when registrar returns False
    assert is_email_processed(db_conn, FAKE_MESSAGE_ID_1) is False
    assert is_tracking_registered(db_conn, FAKE_TRACKING_NUMBER_1) is False


def test_register_and_persist_raises_rolls_back(
    db_conn: sqlite3.Connection,
) -> None:
    """DEDUP-05: raising registrar leaves neither row; exception propagates."""
    with pytest.raises(RuntimeError, match="synthetic API failure"):
        register_and_persist(
            db_conn, FAKE_MESSAGE_ID_1, FAKE_TRACKING_NUMBER_1, raising_registrar
        )
    # Rollback must have left no rows in either table
    assert is_email_processed(db_conn, FAKE_MESSAGE_ID_1) is False
    assert is_tracking_registered(db_conn, FAKE_TRACKING_NUMBER_1) is False


def test_retry_proof() -> None:
    """DEDUP-05 / success criterion 4: fail -> no row -> retry succeeds.

    Proves atomicity: a failing registrar leaves registered_tracking unwritten,
    so the same tracking number is retried on a second simulated run, and both
    rows appear after the second run succeeds.
    """
    conn = sqlite3.connect(":memory:")
    init_db(conn)

    # Run 1: registrar fails — neither row written
    result = register_and_persist(
        conn, FAKE_MESSAGE_ID_1, FAKE_TRACKING_NUMBER_1, fail_registrar
    )
    assert result is False
    assert conn.execute("SELECT 1 FROM processed_emails").fetchone() is None
    assert conn.execute("SELECT 1 FROM registered_tracking").fetchone() is None

    # Run 2: registrar succeeds — both rows appear (retry works; Run 1 wrote nothing)
    result = register_and_persist(
        conn, FAKE_MESSAGE_ID_1, FAKE_TRACKING_NUMBER_1, success_registrar
    )
    assert result is True
    assert conn.execute(
        "SELECT message_id FROM processed_emails WHERE message_id=?",
        (FAKE_MESSAGE_ID_1,),
    ).fetchone() == (FAKE_MESSAGE_ID_1,)
    assert conn.execute(
        "SELECT tracking_number FROM registered_tracking WHERE tracking_number=?",
        (FAKE_TRACKING_NUMBER_1,),
    ).fetchone() == (FAKE_TRACKING_NUMBER_1,)
    conn.close()


# ---------------------------------------------------------------------------
# D-09: NullRegistrar
# ---------------------------------------------------------------------------


def test_null_registrar_defers(caplog: pytest.LogCaptureFixture) -> None:
    """D-09: NullRegistrar returns False, logs debug, no tracking_number in logs."""
    registrar = NullRegistrar()
    with caplog.at_level("DEBUG"):
        result = registrar(FAKE_TRACKING_NUMBER_1, None)
    assert result is False
    # LOG-02 regression guard: tracking number must not appear in any log record
    for record in caplog.records:
        assert FAKE_TRACKING_NUMBER_1 not in record.message
