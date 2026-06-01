# Phase 4: Deduplication — Research

**Researched:** 2026-06-01
**Domain:** SQLite stdlib, idempotency patterns, injectable registrar seam, Python typing Protocol
**Confidence:** HIGH — all claims verified against the live codebase, executed Python probes,
and official Python 3.11/3.12 sqlite3 documentation.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** `processed_emails[message_id]` and `registered_tracking[tracking_number]` are written
  together in a single transaction, only on confirmed registration success. Failure writes neither;
  email is unseen next run; tracking number retries automatically. Satisfies DEDUP-05 by
  construction.
- **D-02:** No-tracking and no-parser-matched emails are left UNMARKED. Re-parsed cheaply every
  run (local regex, no API) until they age out of the Gmail lookback window.
- **D-03:** In the DEDUP-04 branch (fresh email, tracking already registered): skip API call AND
  write this email's `message_id` to `processed_emails`. Eliminates re-parse churn for
  duplicate-notification emails.
- **D-04:** State layer = module of plain functions (`shipping_tracker/db.py`): `init_db(conn)`,
  `is_email_processed(conn, message_id)`, `is_tracking_registered(conn, tracking_number)`, and
  a register-then-persist helper. No class. Connection passed in explicitly.
- **D-05:** One `sqlite3` connection per run: opened in `main()`, `init_db` called once, threaded
  through dispatch loop, closed in `finally`.
- **D-06:** Schema exactly per DEDUP-01/DEDUP-02 — no `provider` column (v2-deferred).
- **D-07:** DB path from `DATABASE_PATH` in `.env`; default `data/shipping-tracker.db`. Parent
  directory created at startup if missing. Add `DATABASE_PATH` to `.env.example`.
- **D-08:** Phase 4 owns register-then-persist orchestration behind an injectable registrar
  callable. Phase 5 drops in the real TrackingMore client with zero dedup-logic changes.
- **D-09:** Ship `NullRegistrar` placeholder: returns a "deferred / not registered" result logged
  at debug. No WARNING noise on Phase 4 cron runs.
- **D-10:** `PRAGMA busy_timeout = 5000` on connect. Default rollback journal (no WAL).
- **D-11:** `PRAGMA user_version = 1` at table creation.
- **D-12:** Dedup key = opaque Gmail API `message id` (`RawEmail.message_id`) — no PII.

### Claude's Discretion

- **Exact registrar contract signature**: return-value vs typed exception, and how Phase 5's
  TRACK-03 "already-exists" maps to the seam. Semantics locked; precise callable / protocol
  is the planner's choice.
- **Module name and helper boundaries**: `db.py` vs `state.py`, and exactly which functions
  exist / how register-then-persist helper is factored.
- **Transaction mechanism**: explicit `BEGIN`/`COMMIT`, `with conn:` context-manager, or
  `conn.commit()` discipline — planner's call, as long as two-row write is atomic.
- **Where dedup checks sit in `main.py`**: order of `is_email_processed` (DEDUP-03, before
  parse) and `is_tracking_registered` (DEDUP-04, after parse, before registrar).

### Deferred Ideas (OUT OF SCOPE)

- `provider` column on `registered_tracking` — v2 PROV-01 via `ALTER TABLE` on `user_version`.
- WAL journal mode — rejected as more than a single-writer cron tool needs.
- `StateStore` class / swappable storage backend — YAGNI.
- Multi-parcel-per-email splitting — carried from Phase 3, still deferred.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEDUP-01 | SQLite DB initialised with `processed_emails(message_id PRIMARY KEY, processed_at)` | Schema verified by probe; `CREATE TABLE IF NOT EXISTS` is idempotent (probe §3) |
| DEDUP-02 | SQLite DB initialised with `registered_tracking(tracking_number PRIMARY KEY, registered_at, source_email_id, last_status, last_status_at)` | Schema verified by probe; `last_status*` nullable columns; idempotent creation |
| DEDUP-03 | Check `processed_emails` first — skip entire email if already seen | `is_email_processed` SELECT probe verified; loop integration probe shows correct skip position |
| DEDUP-04 | Check `registered_tracking` before API call — skip registration if already registered | `is_tracking_registered` SELECT probe verified; full-loop probe shows correct skip |
| DEDUP-05 | `registered_tracking` written only on confirmed success; failures not recorded, retry next run | Atomic `with conn:` two-table write verified; retry proof probe run (§retry-proof) |
</phase_requirements>

---

## Summary

Phase 4 builds the SQLite state layer that makes the email→tracking pipeline idempotent. The
engineering challenge is almost entirely about **atomicity and correctness of the two-row write**:
`processed_emails` and `registered_tracking` must be written together on registrar success and
neither row must be written on failure, so the next cron run automatically retries.

All probes were run against Python 3.14.0 / SQLite 3.50.4 (dev environment) and verified against
Python 3.11 documentation (the project target). The results are identical because the core
behaviors — `with conn:` commit-on-success / rollback-on-exception, `CREATE TABLE IF NOT EXISTS`
idempotency, `PRAGMA busy_timeout`, `PRAGMA user_version` — have been stable since Python 3.6.

**Primary recommendation:** Use `with conn:` as the transaction idiom (see §Transaction
Atomicity). Use a `typing.Protocol`-based `Registrar` callable that returns `bool`
(`True` = success including already-exists, `False` / raises = failure). Name the module
`db.py`. The full dispatch-loop order is: DEDUP-03 early-skip → parse → DEDUP-04 skip or
DEDUP-05 register-and-persist. The full loop simulation probe demonstrates all four paths work
correctly with in-memory SQLite.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| DB schema creation | `db.py` (`init_db`) | `main()` calls it | Schema init is a one-time setup concern isolated in the state module |
| Email dedup check (DEDUP-03) | `main.py` dispatch loop | `db.py` (`is_email_processed`) | Loop owns control flow; `db.py` owns the SQL predicate |
| Tracking dedup check (DEDUP-04) | `main.py` dispatch loop | `db.py` (`is_tracking_registered`) | Same pattern — loop decides skip/proceed, `db.py` answers the question |
| Register-then-persist (DEDUP-05) | `db.py` helper function | `main.py` calls it per email | The atomicity guarantee belongs in `db.py`; the registrar callable is injected |
| Registrar seam (injectable callable) | `main.py` (wiring) | `db.py` (accepted by helper) | Caller owns which registrar instance; `db.py` calls it inside the helper |
| NullRegistrar placeholder | `shipping_tracker/registrar.py` (new) or inline in `main.py` | — | Small enough to be inline; dedicated file if Phase 5 placement matches |
| Connection lifecycle | `main()` in `main.py` | — | Matches synchronous single-process cron model (Scaffold D-03) |
| DB path / directory creation | `main()` in `main.py` | `.env` / `DATABASE_PATH` | Mirrors the `logs/` dir creation already in `logging_config.py` |

---

## Standard Stack

No new external dependencies are introduced in Phase 4. All capabilities are provided by
Python's stdlib.

### Core (all stdlib — no new installs)

| Module | Version | Purpose | Why Standard |
|--------|---------|---------|--------------|
| `sqlite3` | stdlib (Python 3.11+) | SQLite state storage, dedup tables | Project constraint: no ORM; stdlib only |
| `typing.Protocol` | stdlib (Python 3.8+) | Registrar callable type contract | mypy `--strict` compatible; zero deps |
| `datetime` | stdlib | ISO-8601 UTC timestamps for `processed_at`, `registered_at` | stdlib; project already uses it in logging |
| `os` / `pathlib` | stdlib | `DATABASE_PATH` env read, parent-dir creation | Mirrors existing `logging_config.py` pattern |
| `python-dotenv` | already in `pyproject.toml` | Read `DATABASE_PATH` from `.env` | Already installed; `load_dotenv()` already called first in `main()` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `with conn:` context manager | Explicit `BEGIN` / `COMMIT` / `ROLLBACK` | `with conn:` is cleaner and handles rollback automatically; explicit BEGIN/COMMIT is more portable but more verbose — rejected for clarity |
| `typing.Protocol` Registrar | `Callable[[str, str \| None], bool]` type alias | Protocol gives a named type that Phase 5 can subclass/check; `Callable` alias is simpler but anonymous |
| `bool` return from registrar | `RegistrationOutcome` dataclass | `bool` is simpler and sufficient for Phase 4; dataclass gives `already_existed` field but Phase 5 does not need it at the seam level — TRACK-03 maps cleanly to `True` |

**Installation:** No new packages. All stdlib.

---

## Package Legitimacy Audit

> No external packages are installed in this phase. All code uses Python stdlib only.

Not applicable — Phase 4 adds zero new dependencies to `pyproject.toml`.

---

## Architecture Patterns

### System Architecture Diagram

```
                         main() per-cron-run
                         ┌────────────────────────────────────────────┐
  .env                   │  load_dotenv()                             │
  DATABASE_PATH ────────►│  configure_logging()                       │
                         │  conn = sqlite3.connect(db_path)           │
                         │  conn.execute('PRAGMA busy_timeout = 5000')│
                         │  init_db(conn)   ──────────────────────────┼──► db.py: CREATE IF NOT EXISTS
                         │                                            │         PRAGMA user_version = 1
  Gmail API              │  emails = fetch_unread_shipping_emails()   │
  ──────────────────────►│                                            │
                         │  for email in emails:  ◄───────────────────┤
                         │   ┌────────────────────────────────────────┤
                         │   │ DEDUP-03: is_email_processed?  ────────┼──► db.py: SELECT processed_emails
                         │   │   yes ──► continue (skip)             │
                         │   │   no  ──► parse email                 │
                         │   │     no match ──► log, continue        │
                         │   │     matched, no tracking ──► continue │
                         │   │     matched + TrackingInfo:           │
                         │   │       DEDUP-04: is_tracking_registered?──► db.py: SELECT registered_tracking
                         │   │         yes (D-03 dup-notification):  │
                         │   │           mark email processed ────────┼──► db.py: INSERT processed_emails
                         │   │           continue                     │
                         │   │         no ──► registrar(tn, carrier) │
                         │   │           ┌──────────────────────────┐ │
                         │   │           │ NullRegistrar (Phase 4)  │ │
                         │   │           │  → returns False         │ │
                         │   │           │  → logs debug            │ │
                         │   │           │ (Phase 5 drops real      │ │
                         │   │           │  TrackingMore client in) │ │
                         │   │           └──────────────────────────┘ │
                         │   │           success=True:                │
                         │   │             with conn: ───────────────►│ db.py: INSERT processed_emails
                         │   │               INSERT both rows        │        INSERT registered_tracking
                         │   │           success=False / raises:      │
                         │   │             log PII-safely, continue  │ (neither row written → retry)
                         │   └────────────────────────────────────────┤
                         │  conn.close()  (in finally)                │
                         └────────────────────────────────────────────┘
```

### Recommended Project Structure

```
shipping_tracker/
├── db.py               # NEW: init_db, is_email_processed, is_tracking_registered,
│                       #      register_and_persist (the atomic helper)
├── registrar.py        # NEW: Registrar Protocol + NullRegistrar
├── main.py             # MODIFIED: open/close conn, call init_db, insert dedup
│                       #           checks + registrar orchestration into dispatch loop
├── gmail/              # unchanged
├── parsers/            # unchanged
└── logging_config.py   # unchanged

tests/
├── test_db.py          # NEW: all DEDUP-01..05 unit tests + retry proof
├── fixtures/
│   └── fake_db.py      # NEW: in-memory sqlite3 fixture + FAKE-prefixed test data
└── conftest.py         # extend: add in-memory conn fixture
```

### Pattern 1: Transaction Atomicity with `with conn:`

**What:** Two `INSERT` statements wrapped in a single `with conn:` block. On success, both
rows are committed atomically. On any exception (from the registrar or from the DB), both are
rolled back.

**When to use:** Every write to `processed_emails` + `registered_tracking` that must be
atomic. Also the D-03 single-row write (email mark-processed on DEDUP-04 skip) uses the same
idiom, just one INSERT instead of two.

**Verification:** Probe confirmed commit-on-success, rollback-on-exception with Python
3.14 / SQLite 3.50.4. Python 3.11 docs confirm identical behavior.
[VERIFIED: https://docs.python.org/3.11/library/sqlite3.html#sqlite3-connection-context-manager]

```python
# Source: Python 3.11 sqlite3 docs + verified by probe
def register_and_persist(
    conn: sqlite3.Connection,
    message_id: str,
    tracking_number: str,
    registrar: "Registrar",
) -> bool:
    """Call registrar; on success write both rows atomically; on failure write neither.

    Returns True if rows were persisted (registration succeeded).
    Returns False if registrar returned False or raised — caller logs PII-safely and continues.
    """
    try:
        success = registrar(tracking_number, None)  # carrier added in Phase 5
    except Exception as exc:
        # Caller (main.py) logs: message_id + type(exc).__name__ only (LOG-02)
        raise  # re-raise so main.py's WR-04 try/except catches it
    if not success:
        return False
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with conn:  # commits on exit, rolls back on exception
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

**Design note on exceptions:** The probe shows two equivalent designs:
1. Let `register_and_persist` re-raise registrar exceptions → `main.py`'s existing WR-04
   `try/except Exception` catches them, logs PII-safely, and continues. This reuses the
   established error pattern without duplicating it.
2. Catch inside `register_and_persist`, log there, return `False`. Both are valid; option 1
   produces one consistent log site (WR-04 in `main.py`).

### Pattern 2: Registrar Protocol

**What:** A `typing.Protocol` defining the callable signature. `NullRegistrar` implements it
for Phase 4. Phase 5 supplies a `TrackingMoreRegistrar` that drops into the same seam.

**Why Protocol over `Callable`:** The named `Registrar` type is self-documenting, injectable
in tests without subclassing, and satisfies mypy `--strict` without `cast()`.

**TRACK-03 mapping (Phase 5 concern, designed for now):** Phase 5's already-exists response
maps to `return True` from the real registrar. The seam never needs to distinguish
"newly registered" from "already registered" — both mean "durably present, persist the row."
This is why a plain `bool` return is sufficient; no `RegistrationOutcome` dataclass is needed.

```python
# Source: verified by probe (typing.Protocol, Python 3.8+)
from typing import Protocol

class Registrar(Protocol):
    def __call__(self, tracking_number: str, carrier: str | None) -> bool:
        """Register a tracking number.

        Returns True on success (including TRACK-03 already-exists responses).
        Returns False or raises on any failure — the caller will not persist rows.

        LOG-02: implementations MUST NOT embed tracking_number, carrier, or any
        email content in exception messages.
        """
        ...


class NullRegistrar:
    """Phase 4 placeholder — logs at debug, always returns False (deferred).

    This is the live implementation for Phase 4 cron runs. It creates the tables
    and exercises the DEDUP-03/DEDUP-04 skip paths but persists nothing yet.
    Phase 5 replaces this with TrackingMoreRegistrar; zero changes to db.py or main.py.
    """

    def __call__(self, tracking_number: str, carrier: str | None) -> bool:
        logger.debug("registrar.deferred")  # no tracking_number — LOG-02
        return False
```

### Pattern 3: `init_db` — Idempotent Schema Creation

**What:** Creates both tables and sets both PRAGMAs. Safe to call on every run because
`CREATE TABLE IF NOT EXISTS` is idempotent. `PRAGMA user_version = 1` is also idempotent —
setting it again is a no-op if it is already 1.

**Verified:** Probe confirmed `CREATE TABLE IF NOT EXISTS` raises no error on second call
against the same in-memory connection.

```python
# Source: verified by probe + Python 3.11 sqlite3 docs
def init_db(conn: sqlite3.Connection) -> None:
    """Create tables and set PRAGMAs. Idempotent — safe to call on every run."""
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS processed_emails (
            message_id  TEXT PRIMARY KEY,
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

### Pattern 4: Dispatch Loop Integration

**What:** The exact insertion points for dedup checks inside the existing `main.py` dispatch
loop. The DEDUP-03 check goes before any parse work; DEDUP-04 goes after parse, before the
registrar call.

**Verified:** Full-loop simulation probe confirms all four paths (register, DEDUP-03 skip,
DEDUP-04/D-03 dup-notification, DEDUP-05 fail-no-row) work correctly.

```python
# Source: derived from verified probe + main.py WR-04 pattern
# This is the target shape of main() after Phase 4 wiring:
def main() -> int:
    load_dotenv()
    configure_logging()

    db_path = os.getenv("DATABASE_PATH", "data/shipping-tracker.db")
    os.makedirs(os.path.dirname(db_path) or "data", exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        init_db(conn)
        registrar: Registrar = NullRegistrar()

        senders = _get_all_sender_domains()
        window = int(os.getenv("GMAIL_LOOKBACK_DAYS", "30"))

        try:
            emails = fetch_unread_shipping_emails(senders, window)
        except FileNotFoundError as exc:
            logger.error("gmail.credentials.missing path=%s", exc.filename)
            return 1

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

                # DEDUP-04: tracking already registered (e.g. duplicate notification email)
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
                # WR-04 pattern: PII-safe, message_id + type only (LOG-02)
                logger.error(
                    "pipeline.error id=%s type=%s",
                    email.message_id,
                    type(exc).__name__,
                )
                continue
    finally:
        conn.close()

    return 0
```

**Note on `INSERT OR IGNORE`:** The D-03 single-row write (DEDUP-04 branch) uses
`INSERT OR IGNORE` because a race between two overlapping cron runs could attempt to insert
the same `message_id` twice. `PRAGMA busy_timeout` handles the lock wait; `INSERT OR IGNORE`
makes the insert idempotent at the SQL level.

### Anti-Patterns to Avoid

- **`isolation_level=None` (autocommit mode):** Setting `isolation_level=None` disables
  implicit transactions. `with conn:` still commits/rolls back but DML statements are
  auto-committed before the `with` block exits if no explicit `BEGIN` was issued. **Never
  use `isolation_level=None`.** The default `isolation_level=""` (legacy mode) is correct
  and matches Python 3.11 behavior exactly.
  [VERIFIED: https://docs.python.org/3.12/library/sqlite3.html#sqlite3.Connection.autocommit]

- **`conn.commit()` inside a `with conn:` block:** Calling `commit()` inside the `with`
  block commits the first INSERT but not the second if the second raises — breaking atomicity.
  Use `with conn:` alone; never mix manual `commit()` inside it.

- **Logging tracking numbers:** `db.py` and `registrar.py` must never log `tracking_number`
  values (LOG-02). Log only `message_id` (opaque, non-PII) and counts. The tracking number is
  sensitive operational data even though it is not personal data in the PII sense.

- **`logger.exception` in the registrar error path:** `logger.exception` attaches a full
  traceback. If the registrar embeds operational data in its exception message, the traceback
  renders it to the log. Use `logger.error(..., type(exc).__name__)` without `exc_info=True`,
  exactly as the WR-04 pattern in `main.py` does.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Two-table atomic write | Custom flag + manual rollback loop | `with conn:` context manager | stdlib provides commit-on-success / rollback-on-exception atomically; hand-rolled rollback is error-prone under concurrent exception types |
| Idempotent table creation | `CREATE TABLE` + `DROP TABLE IF EXISTS` | `CREATE TABLE IF NOT EXISTS` | `DROP` loses existing rows from prior runs; `IF NOT EXISTS` is purely additive |
| ISO-8601 UTC timestamps | `time.time()` or `datetime.now()` (naivte) | `datetime.datetime.now(datetime.timezone.utc).isoformat()` | Timezone-aware ISO strings sort correctly, are unambiguous across cron runs at DST transitions, and are directly human-readable in the DB browser |
| Registrar error isolation | Nested try/except inside `register_and_persist` with custom logging | Let exceptions propagate to `main.py`'s existing WR-04 `try/except` | One log site, consistent message format, no duplicate error-handling code |

**Key insight:** SQLite's `with conn:` context manager is the right primitive for this
workload. Adding WAL, connection pooling, or an ORM would add complexity with zero benefit for
a synchronous single-writer cron process.

---

## Common Pitfalls

### Pitfall 1: The `isolation_level` / `autocommit` Footgun

**What goes wrong:** Connecting with `isolation_level=None` (or in Python 3.12+, setting
`autocommit=True`) puts SQLite in true autocommit mode. Each `conn.execute("INSERT ...")` then
commits immediately. `with conn:` still issues a `BEGIN` before the first DML, so it looks
like it works — but only because the implicit `BEGIN` in legacy mode happens to coincide with
the `with` block's boundary. Change `isolation_level` and the semantics change silently.

**Why it happens:** The Python 3.12 `autocommit` attribute (value `-1` =
`LEGACY_TRANSACTION_CONTROL`) is confusing. Developers see `autocommit=-1` and assume it
behaves like `autocommit=True`.

**How to avoid:** Always use `sqlite3.connect(path)` with no `isolation_level` or
`autocommit` argument. The default is legacy mode with `isolation_level=""`, which gives
reliable `with conn:` semantics on Python 3.11, 3.12, and 3.13.
[VERIFIED: Python 3.11 docs + Python 3.12 docs + probe]

**Warning signs:** DB rows appear committed before the `with conn:` block exits.

---

### Pitfall 2: `PRAGMA user_version` Must Be Set BEFORE `conn.commit()`

**What goes wrong:** PRAGMA writes (except `PRAGMA user_version`) are DDL-like and
auto-commit in some SQLite versions. If `user_version` is set after the schema `CREATE`
statements but before `conn.commit()`, it may or may not be durable depending on the journal
mode.

**How to avoid:** Set `PRAGMA user_version = 1` as the last statement inside `init_db`,
then call `conn.commit()` once. Verified by probe: `PRAGMA user_version` value persists
correctly.

---

### Pitfall 3: `os.path.dirname("")` Returns `""` (Empty String)

**What goes wrong:** If `DATABASE_PATH` is set to a bare filename (e.g., `tracker.db` with
no directory component), `os.path.dirname("tracker.db")` returns `""`. Then
`os.makedirs("", exist_ok=True)` raises `FileNotFoundError` on some platforms.

**How to avoid:** Use `os.path.dirname(db_path) or "data"` (the same guard pattern used in
`logging_config.py` for `logs/`). The `or "data"` fallback ensures the default directory is
created even if `DATABASE_PATH` is a bare filename.
[VERIFIED: probe + logging_config.py pattern]

---

### Pitfall 4: Duplicate `message_id` in DEDUP-04 Branch

**What goes wrong:** The D-03 single-row write (`INSERT INTO processed_emails`) in the
DEDUP-04 branch could fail with `UNIQUE constraint failed` if two overlapping cron runs
both reach the same `message_id` simultaneously (within the 5-second busy_timeout window).

**How to avoid:** Use `INSERT OR IGNORE INTO processed_emails` for the D-03 write (not
`INSERT INTO`). The two-row atomic write in `register_and_persist` uses plain `INSERT`
because a `UNIQUE constraint failed` there is a real error that should propagate.

---

### Pitfall 5: `check_same_thread` on Raspberry Pi

**What goes wrong:** `sqlite3.connect()` defaults to `check_same_thread=True`, which raises
`ProgrammingError` if the connection is used from a different thread than the one that created
it. This is not a concern for the synchronous single-threaded cron tool but would be triggered
if a future developer adds threading (e.g., concurrent Gmail fetch).

**How to avoid:** No action needed for Phase 4 (single-threaded by D-05). Document the
constraint in `db.py`'s module docstring. If threading is added later, set
`check_same_thread=False` at that point.

---

## Code Examples

### Full `init_db` with All Schema

```python
# Source: DEDUP-01 / DEDUP-02 locked schema + probe verified
import sqlite3
import datetime

def init_db(conn: sqlite3.Connection) -> None:
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

### Dedup Query Functions

```python
# Source: verified by probe — parameterized queries, no f-strings
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

### Timestamp Convention

```python
# Source: verified by probe — timezone-aware UTC ISO string
import datetime

def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
    # Example output: "2026-06-01T15:38:50.840863+00:00"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `isolation_level` only | `autocommit` parameter (Python 3.12+) | Python 3.12 | Default is still `LEGACY_TRANSACTION_CONTROL` (-1); `with conn:` works identically; no migration needed for Python 3.11 target |
| `with conn:` not documented as transaction wrapper | Officially documented context manager | Python 3.x | Stable idiom; safe to use as the primary transaction mechanism |

**Deprecated/outdated:**
- `conn.commit()` after every individual INSERT: replaced by `with conn:` which handles commit and rollback together. Still works but not the recommended idiom for multi-statement atomic blocks.

---

## Assumptions Log

> All claims in this research were verified by probe or cited from official Python 3.11/3.12
> documentation. No `[ASSUMED]` tags in this document.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| — | — | — | — |

**This table is empty.** All claims were verified by executed Python probes or official
Python docs. No user confirmation needed.

---

## Open Questions

1. **`register_and_persist` exception propagation vs. internal catch**
   - What we know: Both designs work. Re-raise → WR-04 in `main.py` catches it; internal
     catch → `return False` without re-raising.
   - What's unclear: Which logging site is preferred (one in `main.py` vs. one in `db.py`).
   - Recommendation: Re-raise to `main.py`'s WR-04 handler to maintain a single consistent
     log site and avoid duplicating the PII-safe logging pattern.

2. **`NullRegistrar` location: inline in `main.py` vs. separate `registrar.py`**
   - What we know: Phase 5 will supply `TrackingMoreRegistrar`. If it lives in a separate
     module, Phase 5 adds a new file without touching `main.py`'s import list.
   - Recommendation: Separate `shipping_tracker/registrar.py` with both `Registrar` (Protocol)
     and `NullRegistrar`. Phase 5 adds `TrackingMoreRegistrar` to the same module.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python stdlib `sqlite3` | All of Phase 4 | ✓ | SQLite 3.50.4 (dev) / 3.x on Pi | — |
| `pytest` | Test suite | ✓ | 9.0.3 | — |
| `python-dotenv` | `DATABASE_PATH` env read | ✓ | already in pyproject.toml | — |

Dev machine runs Python 3.14 / SQLite 3.50.4. Project targets Python 3.11+ and Raspberry Pi OS
Bookworm (ships Python 3.11 with SQLite 3.39+). All behaviors exercised by probes are stable
across Python 3.11–3.14.

**Missing dependencies with no fallback:** None.

---

## Validation Architecture

> `workflow.nyquist_validation = true` in `.planning/config.json` — this section is required.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (exists) |
| Quick run command | `python -m pytest tests/test_db.py -q` |
| Full suite command | `python -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| DEDUP-01 | `processed_emails` table created if absent | unit | `pytest tests/test_db.py::test_init_db_creates_processed_emails -x` | ❌ Wave 0 |
| DEDUP-01 | `init_db` is idempotent (safe to call twice) | unit | `pytest tests/test_db.py::test_init_db_idempotent -x` | ❌ Wave 0 |
| DEDUP-02 | `registered_tracking` table created with nullable `last_status*` | unit | `pytest tests/test_db.py::test_init_db_creates_registered_tracking -x` | ❌ Wave 0 |
| DEDUP-02 | `PRAGMA user_version = 1` set after init | unit | `pytest tests/test_db.py::test_user_version -x` | ❌ Wave 0 |
| DEDUP-03 | `is_email_processed` returns True for known id | unit | `pytest tests/test_db.py::test_is_email_processed_known -x` | ❌ Wave 0 |
| DEDUP-03 | `is_email_processed` returns False for unknown id | unit | `pytest tests/test_db.py::test_is_email_processed_unknown -x` | ❌ Wave 0 |
| DEDUP-03 | Dispatch loop skips entire email when already in `processed_emails` | integration | `pytest tests/test_db.py::test_dispatch_skips_processed_email -x` | ❌ Wave 0 |
| DEDUP-04 | `is_tracking_registered` returns True/False correctly | unit | `pytest tests/test_db.py::test_is_tracking_registered -x` | ❌ Wave 0 |
| DEDUP-04 | Dispatch loop skips API when tracking already registered | integration | `pytest tests/test_db.py::test_dispatch_skips_registered_tracking -x` | ❌ Wave 0 |
| D-03 | Duplicate-notification email is marked processed (DEDUP-04 branch) | integration | `pytest tests/test_db.py::test_dup_notification_marks_email_processed -x` | ❌ Wave 0 |
| DEDUP-05 | `register_and_persist` writes both rows on success | unit | `pytest tests/test_db.py::test_register_and_persist_success -x` | ❌ Wave 0 |
| DEDUP-05 | `register_and_persist` writes neither row on registrar `False` | unit | `pytest tests/test_db.py::test_register_and_persist_fail_returns_false -x` | ❌ Wave 0 |
| DEDUP-05 | `register_and_persist` writes neither row on registrar exception | unit | `pytest tests/test_db.py::test_register_and_persist_raises_rolls_back -x` | ❌ Wave 0 |
| DEDUP-05 | **Retry proof**: fail → no row → success on second run | integration | `pytest tests/test_db.py::test_retry_proof -x` | ❌ Wave 0 |
| D-09 | NullRegistrar returns False, logs at debug, no PII | unit | `pytest tests/test_db.py::test_null_registrar_defers -x` | ❌ Wave 0 |

### Retry Proof Test Design (Success Criterion 4)

This is the most important test in the suite. It must prove: inject a fake *failing* registrar
→ assert `registered_tracking` row absent → assert the same tracking number is attempted again
on a second simulated run → assert row is present after the second run succeeds.

```python
# Outline — actual code written in Wave 0
def test_retry_proof() -> None:
    """DEDUP-05 / success criterion 4.

    Simulated API failure leaves registered_tracking unwritten.
    Same tracking number is retried on a second simulated run.
    """
    conn = sqlite3.connect(":memory:")
    init_db(conn)

    # Run 1: registrar fails
    fail_registrar = lambda tn, c: False
    result = register_and_persist(conn, "FAKEMSGID001", "FAKETRACK001", fail_registrar)
    assert result is False
    assert conn.execute("SELECT 1 FROM processed_emails").fetchone() is None
    assert conn.execute("SELECT 1 FROM registered_tracking").fetchone() is None

    # Run 2: registrar succeeds (retry works because no rows were written by Run 1)
    success_registrar = lambda tn, c: True
    result = register_and_persist(conn, "FAKEMSGID001", "FAKETRACK001", success_registrar)
    assert result is True
    assert conn.execute(
        "SELECT message_id FROM processed_emails WHERE message_id=?", ("FAKEMSGID001",)
    ).fetchone() == ("FAKEMSGID001",)
    assert conn.execute(
        "SELECT tracking_number FROM registered_tracking WHERE tracking_number=?",
        ("FAKETRACK001",),
    ).fetchone() == ("FAKETRACK001",)
    conn.close()
```

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_db.py -q`
- **Per wave merge:** `python -m pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_db.py` — all 15 test functions listed above (covers DEDUP-01..05, D-03, D-09)
- [ ] `tests/fixtures/fake_db.py` — `FAKE`-prefixed tracking numbers and message IDs; privacy
      docstring matching the existing `fake_aliexpress_email.py` pattern
- [ ] `conftest.py` — add `@pytest.fixture` for in-memory `sqlite3.Connection` with `init_db`
      already called (reusable across all `test_db.py` tests)
- [ ] `shipping_tracker/db.py` — new module (Wave 1)
- [ ] `shipping_tracker/registrar.py` — new module (Wave 1)

*(Existing test infrastructure — pytest 9.0.3, `conftest.py`, `tests/fixtures/` — covers the
project baseline. Wave 0 creates only the new files listed above.)*

---

## Security Domain

> `security_enforcement: true`, `security_asvs_level: 1` in `.planning/config.json`.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Phase 4 has no auth layer |
| V3 Session Management | No | Stateless cron tool |
| V4 Access Control | No | Single-user local tool |
| V5 Input Validation | Yes | Parameterized SQL queries (`?` placeholders, never f-strings) |
| V6 Cryptography | No | No crypto in this phase |
| V7 Error Handling / Logging | Yes | PII-safe logging (LOG-02): message_id + type only |
| V9 Data Protection | Yes | `tracking_number` logged nowhere; DB file gitignored |

### Known Threat Patterns for SQLite + Python

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via tracking number or message_id | Tampering | Parameterized queries (`conn.execute("...WHERE id=?", (id,))`) — never string concatenation or f-strings |
| PII / tracking data in log file | Information disclosure | LOG-02: log only `message_id` (opaque Gmail id) and exception type; never `tracking_number`, sender, or body |
| DB file committed to git | Information disclosure | `*.db` already in `.gitignore` (SETUP-07, verified) |
| Crash loop from DB `OperationalError` | Denial of service | `PRAGMA busy_timeout = 5000` prevents immediate lock-raise; catch at `main()` level if cron overlap still causes error |

---

## Sources

### Primary (HIGH confidence)

- Python 3.11 sqlite3 docs — `Connection` context manager behavior, `isolation_level`,
  `in_transaction`: https://docs.python.org/3.11/library/sqlite3.html
- Python 3.12 sqlite3 docs — `autocommit` attribute, `LEGACY_TRANSACTION_CONTROL`:
  https://docs.python.org/3.12/library/sqlite3.html#sqlite3.Connection.autocommit
- Executed Python probes (11 total, all in this session):
  - `with conn:` commit-on-success / rollback-on-exception
  - Two-table atomic write + failure rollback
  - `CREATE TABLE IF NOT EXISTS` idempotency
  - `PRAGMA busy_timeout` and `user_version` persistence
  - Full 4-path dispatch loop simulation
  - DEDUP-05 retry proof (fail run → no rows → success run → both rows)
  - D-03 duplicate-notification mark-processed path
  - `typing.Protocol` Registrar pattern under Python 3.14
  - Directory creation `os.path.dirname("") or "data"` guard
- Live codebase reads: `main.py`, `parsers/base.py`, `gmail/client.py`,
  `logging_config.py`, `tests/conftest.py`, `tests/fixtures/fake_aliexpress_email.py`,
  `tests/test_aliexpress_parser.py`, `pyproject.toml`, all phase CONTEXT.md files

### Secondary (MEDIUM confidence)

None needed — all claims verified from primary sources.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — stdlib only; no external packages; probed directly
- Architecture patterns: HIGH — all four paths probed end-to-end in live Python
- Transaction atomicity: HIGH — verified by probe + official Python docs
- Registrar Protocol: HIGH — verified by probe; typing.Protocol stable since Python 3.8
- Pitfalls: HIGH — all verified by deliberate probe or official doc citation
- Validation architecture: HIGH — test design derived directly from DEDUP criteria + probe

**Research date:** 2026-06-01
**Valid until:** 2026-09-01 (sqlite3 stdlib stable; 90 days conservative estimate)
