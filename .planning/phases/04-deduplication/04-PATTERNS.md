# Phase 4: Deduplication - Pattern Map

**Mapped:** 2026-06-01
**Files analyzed:** 7 (4 new, 3 modified)
**Analogs found:** 7 / 7

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `shipping_tracker/db.py` | utility / state | CRUD | `shipping_tracker/logging_config.py` (plain-function module, env-driven config, dir creation) | role-match |
| `shipping_tracker/registrar.py` | service / seam | request-response | `shipping_tracker/parsers/base.py` (Protocol/ABC + placeholder implementor) | exact |
| `tests/test_db.py` | test | CRUD | `tests/test_aliexpress_parser.py` (unit + integration test mix, FAKE-prefixed data) | exact |
| `tests/fixtures/fake_db.py` | test fixture | — | `tests/fixtures/fake_aliexpress_email.py` (FAKE-prefixed constants, privacy docstring) | exact |
| `shipping_tracker/main.py` (modify) | controller / orchestrator | request-response | itself — WR-04 try/except block is the reuse target | exact |
| `tests/conftest.py` (modify) | test fixture | — | itself — existing `@pytest.fixture` pattern | exact |
| `.env.example` (modify) | config | — | itself — existing `KEY=value` comment style | exact |

---

## Pattern Assignments

### `shipping_tracker/db.py` (utility, CRUD)

**Analogs:** `shipping_tracker/logging_config.py` (plain-function module structure, `os.makedirs` dir-creation guard, `os.getenv` env reads); `shipping_tracker/parsers/base.py` (module docstring style, `from __future__ import annotations`)

**Module docstring + import pattern** (modelled on `logging_config.py` lines 1-8 and `parsers/base.py` lines 1-6):
```python
"""SQLite state layer — idempotent schema init and dedup helpers.

Single-threaded: the connection is created in main() and passed in explicitly.
Do not share a connection across threads without setting check_same_thread=False.

PRIVACY (LOG-02): no function in this module may log tracking_number values.
Log only message_id (opaque, non-PII) and row counts.
"""

from __future__ import annotations

import datetime
import sqlite3
```

**`os.makedirs` dir-creation guard** — copy this exact idiom from `logging_config.py` line 23:
```python
# logging_config.py, line 23 — the or-fallback pattern for bare filenames
os.makedirs(os.path.dirname(log_path) or "logs", exist_ok=True)

# db.py applies the same guard:
os.makedirs(os.path.dirname(db_path) or "data", exist_ok=True)
```

**Core function signatures** (mypy `--strict`; `sqlite3.Connection` passed explicitly per D-04):
```python
def init_db(conn: sqlite3.Connection) -> None: ...
def is_email_processed(conn: sqlite3.Connection, message_id: str) -> bool: ...
def is_tracking_registered(conn: sqlite3.Connection, tracking_number: str) -> bool: ...
def register_and_persist(
    conn: sqlite3.Connection,
    message_id: str,
    tracking_number: str,
    registrar: "Registrar",
) -> bool: ...
```

**`init_db` schema + PRAGMAs** (from RESEARCH.md §Pattern 3, verified by probe):
```python
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
```

**Parameterized query pattern** — never f-strings (ASVS V5, from RESEARCH.md §Code Examples):
```python
def is_email_processed(conn: sqlite3.Connection, message_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM processed_emails WHERE message_id = ?", (message_id,)
    ).fetchone()
    return row is not None

def is_tracking_registered(conn: sqlite3.Connection, tracking_number: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM registered_tracking WHERE tracking_number = ?",
        (tracking_number,),
    ).fetchone()
    return row is not None
```

**`with conn:` atomic two-row write** (from RESEARCH.md §Pattern 1):
```python
def register_and_persist(
    conn: sqlite3.Connection,
    message_id: str,
    tracking_number: str,
    registrar: "Registrar",
) -> bool:
    try:
        success = registrar(tracking_number, None)
    except Exception:
        raise  # propagate to main.py WR-04 handler — single log site
    if not success:
        return False
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with conn:  # commits on block exit; rolls back on any exception
        conn.execute(
            "INSERT INTO processed_emails VALUES (?, ?)",
            (message_id, now),
        )
        conn.execute(
            "INSERT INTO registered_tracking VALUES (?, ?, ?, NULL, NULL)",
            (tracking_number, now, message_id),
        )
    return True
```

**Timestamp convention** (RESEARCH.md §Timestamp Convention):
```python
# Always timezone-aware UTC ISO string — sorts correctly, unambiguous at DST
datetime.datetime.now(datetime.timezone.utc).isoformat()
# e.g. "2026-06-01T15:38:50.840863+00:00"
```

**Anti-patterns to avoid:**
- Never `isolation_level=None` (breaks `with conn:` semantics)
- Never `conn.commit()` inside a `with conn:` block (breaks atomicity)
- Never log `tracking_number` values (LOG-02) — log only `message_id` and counts

---

### `shipping_tracker/registrar.py` (service seam, request-response)

**Analog:** `shipping_tracker/parsers/base.py` — Protocol/ABC defining a callable contract + a concrete implementor as placeholder

**Module docstring + import pattern** (modelled on `parsers/base.py` lines 1-7):
```python
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
```

**`typing.Protocol` pattern** (from RESEARCH.md §Pattern 2 + verified probe):
```python
class Registrar(Protocol):
    def __call__(self, tracking_number: str, carrier: str | None) -> bool:
        """Register a tracking number.

        Returns True on success (including TRACK-03 already-exists responses).
        Returns False or raises on any failure — caller will not persist rows.
        """
        ...
```

**`NullRegistrar` placeholder** (from RESEARCH.md §Pattern 2):
```python
class NullRegistrar:
    """Phase 4 placeholder — logs at debug, always returns False (deferred).

    Phase 5 replaces this with TrackingMoreRegistrar; zero changes to db.py
    or main.py are required.
    """

    def __call__(self, tracking_number: str, carrier: str | None) -> bool:
        logger.debug("registrar.deferred")  # no tracking_number — LOG-02
        return False
```

**Comparison with `parsers/base.py` pattern:**

| parsers/base.py | registrar.py |
|---|---|
| `BaseParser` ABC with `can_parse` + `extract` abstract methods | `Registrar` Protocol with `__call__` |
| `AliExpressParser` concrete implementation | `NullRegistrar` placeholder |
| `TrackingInfo` dataclass as return type | `bool` return (True = success incl. already-exists) |

The `typing.Protocol` approach is preferred over ABC here because tests can inject any callable without subclassing — matching the "injectable registrar" seam design (D-08).

---

### `tests/test_db.py` (test, CRUD)

**Analog:** `tests/test_aliexpress_parser.py` — unit + integration tests, `FAKE`-prefixed synthetic data, `caplog` PII-safety assertions, no real data

**Module docstring pattern** (modelled on `test_aliexpress_parser.py` lines 1-5):
```python
"""Tests for shipping_tracker.db — DEDUP-01..05 acceptance criteria.

All test data is synthetic — FAKE-prefixed tracking numbers and message IDs.
No real tracking numbers, email addresses, or order references.
"""
```

**Import block pattern** (modelled on `test_aliexpress_parser.py` lines 7-20):
```python
import sqlite3

import pytest

from shipping_tracker.db import (
    init_db,
    is_email_processed,
    is_tracking_registered,
    register_and_persist,
)
from shipping_tracker.registrar import NullRegistrar, Registrar
from tests.fixtures.fake_db import (
    FAKE_MESSAGE_ID_1,
    FAKE_MESSAGE_ID_2,
    FAKE_TRACKING_NUMBER_1,
    FAKE_TRACKING_NUMBER_2,
)
```

**In-memory connection fixture pattern** — new in conftest.py, used throughout test_db.py:
```python
# In tests/conftest.py (addition):
@pytest.fixture
def db_conn() -> sqlite3.Connection:
    """In-memory sqlite3.Connection with schema already initialised.

    PRIVACY: never use real tracking numbers or message IDs in tests.
    All test data must use FAKE-prefixed synthetic values.
    """
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    yield conn
    conn.close()
```

**Unit test function signature style** (modelled on `test_aliexpress_parser.py` lines 23-26):
```python
def test_init_db_creates_processed_emails(db_conn: sqlite3.Connection) -> None:
    """DEDUP-01: processed_emails table exists after init_db."""
    row = db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='processed_emails'"
    ).fetchone()
    assert row is not None
```

**Inline fake registrar pattern** — lambdas / local callables for inject-and-assert tests (from RESEARCH.md §Retry Proof Test Design):
```python
# Failing registrar: returns False
fail_registrar: Registrar = lambda tn, c: False  # type: ignore[assignment]

# Succeeding registrar: returns True
success_registrar: Registrar = lambda tn, c: True  # type: ignore[assignment]

# Raising registrar: simulates network/API error
def raising_registrar(tracking_number: str, carrier: str | None) -> bool:
    raise RuntimeError("synthetic API failure")
```

**caplog PII-safety assertion pattern** (modelled on `test_aliexpress_parser.py` lines 72-79 and `test_gmail_client.py` lines 154-178):
```python
def test_null_registrar_defers(caplog: pytest.LogCaptureFixture) -> None:
    """D-09: NullRegistrar logs at debug, returns False, emits no tracking_number."""
    registrar = NullRegistrar()
    with caplog.at_level("DEBUG"):
        result = registrar(FAKE_TRACKING_NUMBER_1, None)
    assert result is False
    for record in caplog.records:
        assert FAKE_TRACKING_NUMBER_1 not in record.message
```

**Retry-proof integration test** (from RESEARCH.md §Retry Proof Test Design):
```python
def test_retry_proof() -> None:
    """DEDUP-05 / success criterion 4: fail → no row → retry succeeds."""
    conn = sqlite3.connect(":memory:")
    init_db(conn)

    # Run 1: registrar fails — neither row written
    result = register_and_persist(conn, FAKE_MESSAGE_ID_1, FAKE_TRACKING_NUMBER_1,
                                  lambda tn, c: False)
    assert result is False
    assert conn.execute("SELECT 1 FROM processed_emails").fetchone() is None
    assert conn.execute("SELECT 1 FROM registered_tracking").fetchone() is None

    # Run 2: registrar succeeds — both rows appear
    result = register_and_persist(conn, FAKE_MESSAGE_ID_1, FAKE_TRACKING_NUMBER_1,
                                  lambda tn, c: True)
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
```

---

### `tests/fixtures/fake_db.py` (test fixture)

**Analog:** `tests/fixtures/fake_aliexpress_email.py` — privacy docstring, `FAKE`-prefixed module-level constants, no functions

**Module docstring pattern** (copy structure from `fake_aliexpress_email.py` lines 1-7):
```python
"""Synthetic database fixtures for Phase 4 deduplication tests.

PRIVACY: All values are synthetic. No real tracking numbers, Gmail message IDs,
email addresses, or order references. See CLAUDE.md privacy constraints.
Message IDs use FAKEMSGID prefix; tracking numbers use FAKETRACK prefix.
"""
```

**Constant naming convention** (from `fake_aliexpress_email.py` pattern):
```python
# Message IDs — opaque Gmail message IDs (non-PII, FAKE-prefixed for test safety)
FAKE_MESSAGE_ID_1 = "FAKEMSGID001"
FAKE_MESSAGE_ID_2 = "FAKEMSGID002"
FAKE_MESSAGE_ID_DUP = "FAKEMSGID003"  # a duplicate-notification email

# Tracking numbers — FAKE-prefixed, no real carrier format
FAKE_TRACKING_NUMBER_1 = "FAKETRACK001CN"
FAKE_TRACKING_NUMBER_2 = "FAKETRACK002CN"
```

**Key differences from `fake_aliexpress_email.py`:**
- `fake_aliexpress_email.py` has multi-line string fixtures (email bodies); `fake_db.py` has only short string constants
- Both share the same privacy docstring format and `FAKE`-prefix convention
- No functions, no classes — pure module-level constants (the pattern for fixture data files)

---

### `shipping_tracker/main.py` (orchestrator — modifications)

**Analog:** itself — the WR-04 `try/except` block (lines 75-100) is the template for the new registrar error path

**WR-04 error pattern to reuse** (`main.py` lines 89-100):
```python
# Existing pattern — copy this exact structure for the registrar error path
except Exception as exc:
    # PII-safe: log message_id + exception TYPE only (LOG-02). We do
    # NOT use logger.exception here — the traceback and the exception's
    # own message could embed email content if a third-party parser
    # raised e.g. ValueError(f"bad body: {body}"). type(exc).__name__
    # is structural, never PII.
    logger.error(
        "parser.dispatch.error id=%s type=%s",
        email.message_id,
        type(exc).__name__,
    )
    continue
```

**New log key names** to maintain the `module.action` naming convention seen in `main.py`:
```python
logger.debug("dedup.email.skip id=%s", email.message_id)       # DEDUP-03 skip
logger.debug("dedup.tracking.skip id=%s", email.message_id)    # DEDUP-04 skip
logger.error("pipeline.error id=%s type=%s", email.message_id, type(exc).__name__)  # WR-04
```

**Connection lifecycle pattern** (`os.getenv` + `os.makedirs` then `sqlite3.connect` + `finally: conn.close()`) — copy the `os.makedirs` guard from `logging_config.py` line 23:
```python
# From logging_config.py line 23 — the same pattern for data/:
os.makedirs(os.path.dirname(log_path) or "logs", exist_ok=True)

# New in main() for DATABASE_PATH:
db_path = os.getenv("DATABASE_PATH", "data/shipping-tracker.db")
os.makedirs(os.path.dirname(db_path) or "data", exist_ok=True)
conn = sqlite3.connect(db_path)
try:
    init_db(conn)
    registrar: Registrar = NullRegistrar()
    # ... existing dispatch loop with dedup checks inserted ...
finally:
    conn.close()
```

**D-03 single-row `INSERT OR IGNORE`** (inside DEDUP-04 branch — uses `INSERT OR IGNORE` not plain `INSERT` to be idempotent against cron overlap):
```python
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
with conn:
    conn.execute(
        "INSERT OR IGNORE INTO processed_emails VALUES (?, ?)",
        (email.message_id, now),
    )
```

**Full target dispatch-loop shape** (from RESEARCH.md §Pattern 4 — planner copies this directly):
```python
for email in emails:
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
                break

        if not matched:
            logger.info("parser.no_match id=%s", email.message_id)
            continue
        if result is None:
            logger.debug("parser.no_tracking id=%s", email.message_id)
            continue  # D-02: left unmarked, re-evaluated next run

        # DEDUP-04: tracking already registered (duplicate-notification email)
        if is_tracking_registered(conn, result.tracking_number):
            logger.debug("dedup.tracking.skip id=%s", email.message_id)
            # D-03: mark this email done to avoid re-parse churn
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            with conn:
                conn.execute(
                    "INSERT OR IGNORE INTO processed_emails VALUES (?, ?)",
                    (email.message_id, now),
                )
            continue

        # DEDUP-05: register-then-persist (atomic)
        register_and_persist(conn, email.message_id, result.tracking_number, registrar)

    except Exception as exc:
        # WR-04: PII-safe error — message_id + type only (LOG-02)
        logger.error(
            "pipeline.error id=%s type=%s",
            email.message_id,
            type(exc).__name__,
        )
        continue
```

---

### `tests/conftest.py` (modify — add `db_conn` fixture)

**Analog:** itself (lines 1-18) — existing `@pytest.fixture` returning a synthetic value

**Existing fixture pattern to replicate** (`conftest.py` lines 11-18):
```python
@pytest.fixture
def synthetic_email_body() -> str:
    """A synthetic AliExpress-style email body with fake tracking data."""
    return (
        "Your order has shipped!\n"
        "Tracking number: FAKE1234567890\n"
        "Carrier: FAKECARRIER\n"
    )
```

**New fixture to add** (same style, generator form for connection teardown):
```python
@pytest.fixture
def db_conn() -> sqlite3.Connection:
    """In-memory sqlite3.Connection with schema already initialised via init_db.

    PRIVACY: never use real tracking numbers or message IDs in tests.
    All test data must use FAKE-prefixed synthetic values.
    """
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    yield conn
    conn.close()
```

Additional import needed at top of `conftest.py`:
```python
import sqlite3
from shipping_tracker.db import init_db
```

---

### `.env.example` (modify — add `DATABASE_PATH`)

**Analog:** itself — existing `KEY=value_or_placeholder` comment style

**Existing pattern** (`.env.example` lines 14-19 — Gmail block with comment):
```ini
# Gmail integration (Phase 2)
GMAIL_TOKEN_PATH=token.json
GMAIL_CREDENTIALS_PATH=credentials.json
# GMAIL_LOOKBACK_DAYS: integer; controls newer_than:Nd in the Gmail search query (default 30)
GMAIL_LOOKBACK_DAYS=30
```

**New entry to append** (same style — section comment + default value):
```ini
# Database (Phase 4)
# DATABASE_PATH: path to SQLite DB file. Defaults to data/shipping-tracker.db.
# Override on Pi (e.g. /home/pi/shipping-tracker.db) with no code change.
DATABASE_PATH=data/shipping-tracker.db
```

---

### `.gitignore` (verify only — no change expected)

`.gitignore` lines 6-7 already cover the DB file:
```
# Database
*.db
*.sqlite3
```

The `data/` directory itself is not explicitly listed but is a runtime directory (parallel to `logs/`). Since `logs/` is listed (line 10) and `data/` will be gitignored by the `*.db` rule covering its content, no change is required. However, explicitly adding `data/` mirrors the `logs/` pattern — planner may add it for consistency.

---

## Shared Patterns

### PII-safe logging (LOG-02)
**Source:** `shipping_tracker/main.py` lines 89-100 (WR-04 block)
**Apply to:** `db.py`, `registrar.py`, all new test assertions
```python
# ALWAYS: message_id + type(exc).__name__ only
logger.error("pipeline.error id=%s type=%s", email.message_id, type(exc).__name__)
# NEVER: logger.exception (attaches traceback which may contain PII)
# NEVER: log tracking_number in any module
```

### `from __future__ import annotations`
**Source:** `shipping_tracker/parsers/base.py` line 3, `shipping_tracker/gmail/client.py` line 3
**Apply to:** `db.py`, `registrar.py` (forward-reference compat, mypy `--strict` clean)

### `logger = logging.getLogger(__name__)` module-level logger
**Source:** `shipping_tracker/main.py` line 13, `shipping_tracker/parsers/aliexpress.py` line 10, `shipping_tracker/gmail/client.py` line 22
**Apply to:** `db.py`, `registrar.py`
```python
import logging
logger = logging.getLogger(__name__)
```

### mypy `--strict` typing discipline
**Source:** all existing modules — no `Any` without `TYPE_CHECKING`, explicit return types on every function, no implicit `Optional`
**Apply to:** `db.py`, `registrar.py` — all function signatures must carry full type annotations; `sqlite3.Connection`, `str`, `bool`, `str | None` are the only types needed

### Synthetic fixture privacy docstring
**Source:** `tests/fixtures/fake_aliexpress_email.py` lines 1-7, `tests/conftest.py` lines 1-6
**Apply to:** `tests/fixtures/fake_db.py` module docstring, `tests/test_db.py` module docstring
```python
# Module-level docstring template:
"""...[module purpose]...

PRIVACY: All values are synthetic. No real tracking numbers, email addresses,
[or relevant PII]. See CLAUDE.md privacy constraints.
[FAKE prefix convention statement].
"""
```

### `os.makedirs` dir-creation guard
**Source:** `shipping_tracker/logging_config.py` line 23
**Apply to:** `main.py` for `data/` dir creation
```python
os.makedirs(os.path.dirname(db_path) or "data", exist_ok=True)
```

---

## No Analog Found

None. All seven files have close analogs in the codebase. RESEARCH.md provides verified code examples for the two genuinely new patterns (`with conn:` transaction idiom, `typing.Protocol` Registrar) that have no direct codebase analog.

---

## Metadata

**Analog search scope:** `shipping_tracker/`, `tests/`, `tests/fixtures/`, repo root config files
**Files read:** 12 source files (all .py modules, .env.example, .gitignore)
**Pattern extraction date:** 2026-06-01
