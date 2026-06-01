---
phase: 04-deduplication
verified: 2026-06-01T12:00:00Z
status: human_needed
score: 4/4 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Live NullRegistrar cron run against a dev .env"
    expected: "data/shipping-tracker.db created with both tables present; registered_tracking is empty (NullRegistrar always returns False — honest deferred state)"
    why_human: "Requires a real Gmail OAuth token and a populated .env; cannot be exercised by in-process pytest"
---

# Phase 4: Deduplication Verification Report

**Phase Goal:** SQLite provides the stateful core of the idempotency guarantee — processed emails
and registered tracking numbers are never acted on twice, and failed API calls are retried next
run automatically.

**Verified:** 2026-06-01T12:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | On first run, both `processed_emails` and `registered_tracking` tables are created if they do not exist | VERIFIED | `init_db` uses `CREATE TABLE IF NOT EXISTS` for both tables; `test_init_db_creates_processed_emails` and `test_init_db_creates_registered_tracking` both GREEN |
| 2 | An email whose `message_id` is already in `processed_emails` is skipped entirely without re-parsing or re-querying the API | VERIFIED | `main.py:96-98` checks `is_email_processed` before the parser loop, logs `dedup.email.skip`, and continues; `test_dispatch_skips_processed_email` GREEN (spy registrar asserts not called) |
| 3 | A tracking number already in `registered_tracking` is skipped without calling the TrackingMore API | VERIFIED | `main.py:117-126` checks `is_tracking_registered` after parse, marks email processed via `INSERT OR IGNORE`, and continues without calling registrar; `test_dispatch_skips_registered_tracking` and `test_dup_notification_marks_email_processed` GREEN |
| 4 | A simulated API failure leaves `registered_tracking` unwritten, so the same tracking number is attempted again on the next run | VERIFIED | `register_and_persist` calls registrar first; returns False without any DB write when registrar returns False; `with conn:` atomicity means both rows commit together or not at all; `test_retry_proof` exercises fail-run (zero rows) then success-run (both rows) — GREEN |

**Score:** 4/4 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `shipping_tracker/db.py` | `init_db`, `is_email_processed`, `is_tracking_registered`, `register_and_persist` | VERIFIED | All four functions present, 99 lines, substantive implementations; mypy --strict clean; ruff clean |
| `shipping_tracker/registrar.py` | `Registrar` Protocol + `NullRegistrar` placeholder | VERIFIED | Both exported; `NullRegistrar.__call__` logs no tracking_number (LOG-02); mypy --strict clean |
| `shipping_tracker/main.py` | Connection lifecycle + dedup-wired dispatch loop | VERIFIED | Contains `init_db(conn)`, `is_email_processed(conn`, `is_tracking_registered(conn`, `register_and_persist(conn`, `NullRegistrar()`, `conn.close()` in `finally` |
| `tests/test_db.py` | 15 DEDUP test functions | VERIFIED | All 15 named exactly per validation map, all GREEN (15/15 passed in 0.02s) |
| `tests/fixtures/fake_db.py` | FAKE-prefixed constants | VERIFIED | `FAKE_MESSAGE_ID_1/2/DUP`, `FAKE_TRACKING_NUMBER_1/2`; privacy docstring present |
| `tests/conftest.py` | `db_conn` in-memory fixture | VERIFIED | Generator fixture calls `init_db(conn)` on `:memory:` connection |
| `.env.example` | `DATABASE_PATH` documented | VERIFIED | `DATABASE_PATH=data/shipping-tracker.db` present under "Database (Phase 4)" comment section |
| `.gitignore` | `*.db` and `data/` excluded | VERIFIED | Both `*.db` (line 7) and `data/` (line 14) present |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `tests/conftest.py` | `shipping_tracker.db.init_db` | `db_conn` fixture calls `init_db(conn)` on `:memory:` | WIRED | Line 34: `init_db(conn)` confirmed |
| `tests/test_db.py` | `shipping_tracker.db` | `from shipping_tracker.db import init_db, is_email_processed, is_tracking_registered, register_and_persist` | WIRED | Lines 13-17 confirmed |
| `shipping_tracker/main.py main()` | `shipping_tracker.db` + `shipping_tracker.registrar` | Imports + calls in dispatch loop | WIRED | Lines 13-22 imports; lines 72-133 usage confirmed |
| `shipping_tracker/main.py DEDUP-03 check` | `is_email_processed` | Before parser loop, line 96 | WIRED | `if is_email_processed(conn, email.message_id)` confirmed |
| `shipping_tracker/main.py DEDUP-04 check` | `is_tracking_registered` | After parse, line 117 | WIRED | `if is_tracking_registered(conn, result.tracking_number)` confirmed |
| `register_and_persist` | `with conn:` two-row INSERT | Atomic transaction via context manager | WIRED | Lines 89-97: `with conn:` contains both INSERTs |
| `register_and_persist` | `Registrar` callable | `registrar(tracking_number, None)` at line 83; persists only if True | WIRED | Pattern confirmed |

---

### Data-Flow Trace (Level 4)

Not applicable to this phase — no dynamic-data rendering components. The phase delivers a state
layer (pure functions writing/reading SQLite) and pipeline wiring. Data flow is verified via the
test suite (in-memory SQLite probing row presence) rather than visual rendering.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Both tables created on first init | `pytest tests/test_db.py::test_init_db_creates_processed_emails tests/test_db.py::test_init_db_creates_registered_tracking -v` | PASSED | PASS |
| Email-already-seen skip (SC2) | `pytest tests/test_db.py::test_dispatch_skips_processed_email -v` | PASSED | PASS |
| Tracking-already-registered skip (SC3) | `pytest tests/test_db.py::test_dispatch_skips_registered_tracking tests/test_db.py::test_dup_notification_marks_email_processed -v` | PASSED | PASS |
| Retry proof: fail leaves no row, success on retry writes both (SC4) | `pytest tests/test_db.py::test_retry_proof -v` | PASSED | PASS |
| Rollback on exception | `pytest tests/test_db.py::test_register_and_persist_raises_rolls_back -v` | PASSED | PASS |
| Full suite: no regressions | `python -m pytest tests/ -q` | 57/57 passed | PASS |
| mypy --strict across 3 source files | `mypy --strict shipping_tracker/db.py shipping_tracker/registrar.py shipping_tracker/main.py` | Success: no issues found in 3 source files | PASS |
| ruff check phase 4 source + test files | `ruff check shipping_tracker/db.py shipping_tracker/registrar.py shipping_tracker/main.py tests/test_db.py` | All checks passed | PASS |
| Clean import | `python -c "import shipping_tracker.main"` | `clean import` | PASS |

---

### Probe Execution

Not applicable — no `scripts/*/tests/probe-*.sh` defined for this phase. Manual-only verification
is tracked under Human Verification Required below (per 04-VALIDATION.md §Manual-Only).

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| DEDUP-01 | Plan 01/02 | `processed_emails(message_id PRIMARY KEY, processed_at)` table created if absent | SATISFIED | `init_db` DDL confirmed; `test_init_db_creates_processed_emails` + `test_init_db_idempotent` GREEN |
| DEDUP-02 | Plan 01/02 | `registered_tracking` table with nullable `last_status`/`last_status_at` | SATISFIED | `init_db` DDL confirmed (5-column schema, last two columns NULL); `test_init_db_creates_registered_tracking` + `test_user_version` GREEN |
| DEDUP-03 | Plan 01/02/03 | Tool checks `processed_emails` first — skips entire email if already seen | SATISFIED | `main.py:96-98` check before parser loop; `test_dispatch_skips_processed_email` GREEN |
| DEDUP-04 | Plan 01/02/03 | Tool checks `registered_tracking` before calling API — skips if already registered | SATISFIED | `main.py:117-126` check + INSERT OR IGNORE mark-processed; `test_dispatch_skips_registered_tracking` + `test_dup_notification_marks_email_processed` GREEN |
| DEDUP-05 | Plan 01/02/03 | `registered_tracking` only written on confirmed API success | SATISFIED | `register_and_persist` writes nothing on False/exception; `test_retry_proof` GREEN |

All 5 requirement IDs (DEDUP-01 through DEDUP-05) are satisfied. No orphaned or unmapped
requirements found for Phase 4.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `shipping_tracker/registrar.py` | 1, 33 | Word "placeholder" in docstring/class description | INFO | Intentional NullRegistrar design note (D-09); not a code smell — this is the correct Phase 4 live implementation. No action required. |

No `TBD`, `FIXME`, or `XXX` markers found in any Phase 4 modified file. No debt-marker blockers.

**WR-01 (code review): `register_and_persist` bare INSERT vs. `INSERT OR IGNORE` — assessed against SC4.**

The bare `INSERT INTO processed_emails` and `INSERT INTO registered_tracking` at `db.py:91-96`
differ from the `INSERT OR IGNORE` used in `main.py:123`. The review flags this as a
maintainability risk: a future direct caller bypassing the upstream dedup checks would receive an
`IntegrityError` rather than a silent no-op.

Assessment against Success Criterion 4 (retry guarantee): **WR-01 does NOT threaten SC4 as
implemented.** The retry proof works because:

1. A failing registrar (False return) causes `register_and_persist` to return False before reaching
   either INSERT — zero rows written.
2. The `with conn:` context manager makes the two INSERTs atomic. Partial state (one row without
   the other) cannot exist under normal operation.
3. On retry, neither `processed_emails` nor `registered_tracking` has a row for the same
   message_id/tracking_number, so the bare INSERTs succeed cleanly.

The only scenario where bare INSERT would raise is if `register_and_persist` is called directly
for an already-persisted pair — but the upstream `is_tracking_registered` guard in `main.py`
prevents this in the normal dispatch path. WR-01 is a legitimate **robustness warning** (a future
caller without the guard would get a hard error), but it does not constitute a current SC4 failure.

WR-01 classification for this verification: **WARNING** (maintainability gap, not a blocking
defect). The code review finding stands and should be addressed in a follow-up quick task.

---

### Human Verification Required

#### 1. Live NullRegistrar Cron Run

**Test:** With a real Gmail OAuth token and populated `.env` (including `DATABASE_PATH=data/shipping-tracker.db`), run the pipeline once: `python -m shipping_tracker.main` or the configured entry point.

**Expected:** `data/shipping-tracker.db` is created. Both `processed_emails` and `registered_tracking` tables exist (can verify with `sqlite3 data/shipping-tracker.db .tables`). `registered_tracking` is empty — NullRegistrar always returns False so `register_and_persist` writes nothing. Second run skips any emails that were marked processed (DEDUP-03 hit). No crash, no PII in `logs/`.

**Why human:** Requires a real Gmail OAuth2 credential flow (`token.json`) and a populated `.env`. In-memory pytest coverage proves the dedup and retry logic is correct; this checks the connection lifecycle (file-backed DB, `data/` directory creation, `init_db` idempotency on a real file) and the NullRegistrar "honest incomplete pipeline" state against a live environment.

---

### Gaps Summary

No gaps. All four success criteria are observable, tested, and verified in the codebase:

- SC1 (table creation): `init_db` with `CREATE TABLE IF NOT EXISTS`; GREEN tests.
- SC2 (email dedup): `is_email_processed` guard before parse; GREEN tests.
- SC3 (tracking dedup): `is_tracking_registered` guard + `INSERT OR IGNORE` mark-processed; GREEN tests.
- SC4 (retry guarantee): `with conn:` atomic write + registrar-called-first ordering; `test_retry_proof` GREEN.

The one human verification item (live cron run) is the standard end-of-phase live-environment
check that automated in-memory tests cannot substitute for. It does not constitute a gap in the
automated guarantee.

---

_Verified: 2026-06-01T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
