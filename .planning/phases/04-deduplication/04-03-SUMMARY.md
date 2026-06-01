---
phase: 04-deduplication
plan: "03"
subsystem: pipeline-orchestrator
tags: [deduplication, sqlite, registrar, main, connection-lifecycle, wiring]
dependency_graph:
  requires:
    - shipping_tracker/db.py (init_db, is_email_processed, is_tracking_registered, register_and_persist — from Plan 02)
    - shipping_tracker/registrar.py (Registrar Protocol, NullRegistrar — from Plan 02)
    - shipping_tracker/main.py (WR-04 dispatch loop — Phase 3)
  provides:
    - shipping_tracker/main.py (connection lifecycle + dedup-wired dispatch loop + NullRegistrar seam)
    - .env.example (DATABASE_PATH documented with default data/shipping-tracker.db)
    - .gitignore (data/ entry added for consistency with logs/)
  affects:
    - Phase 5 (TrackingMoreRegistrar drops into the Registrar seam at the NullRegistrar injection point — zero changes to db.py or the dispatch loop)
tech_stack:
  added: []
  patterns:
    - "sqlite3 connection lifecycle: open post-load_dotenv, init_db once, close in finally (D-05)"
    - "os.makedirs(os.path.dirname(db_path) or 'data', exist_ok=True) guard (pitfall 3)"
    - "NullRegistrar seam injection at main() scope (D-08/D-09)"
    - "DEDUP-03 is_email_processed check before any parse work"
    - "DEDUP-04 is_tracking_registered + INSERT OR IGNORE mark-processed (D-03)"
    - "DEDUP-05 register_and_persist for fresh tracking numbers"
    - "pipeline.error WR-04 log key (replaces parser.dispatch.error)"
key_files:
  created: []
  modified:
    - shipping_tracker/main.py
    - .env.example
    - .gitignore
    - tests/test_aliexpress_parser.py
decisions:
  - "pipeline.error log key used (replacing parser.dispatch.error) — matches 04-PATTERNS.md §main.py naming convention"
  - "tracking_results only appended when register_and_persist returns True — dispatch.complete count reflects actually-persisted results"
  - "test_main_dispatch_loop_logs_pii_safely_on_error updated: DATABASE_PATH=:memory: monkeypatch prevents side-effect DB file creation during test"
metrics:
  duration_minutes: 3
  completed_date: "2026-06-01"
  tasks_completed: 2
  files_changed: 4
---

# Phase 04 Plan 03: Main Wiring (Wave 3) Summary

**One-liner:** Dedup-wired main() with sqlite3 connection lifecycle, NullRegistrar seam, and DEDUP-03/04/05 checks in the dispatch loop — the MVP vertical slice is closed.

---

## What Was Built

Phase 4 Plan 03 wires the Wave 1+2 modules (db.py + registrar.py) into main() to close the MVP vertical slice. This is the final plan of Phase 4.

**Two source files modified:**

1. **`shipping_tracker/main.py`** — Complete rewrite of `main()` to own the SQLite connection lifecycle and dedup-wired dispatch loop:
   - Opens one `sqlite3.connect(db_path)` per run after `load_dotenv()/configure_logging()`; reads `DATABASE_PATH` from env (default `data/shipping-tracker.db`); creates the parent directory with `os.makedirs(...) or "data"` guard (pitfall 3)
   - Calls `init_db(conn)` once, then injects `registrar: Registrar = NullRegistrar()` (D-08/D-09 seam)
   - Closes connection in `finally: conn.close()` (D-05) — guaranteed even if `fetch_unread_shipping_emails` raises
   - DEDUP-03: `is_email_processed(conn, email.message_id)` check BEFORE any parse work; logs `dedup.email.skip` at debug; continues
   - DEDUP-04: `is_tracking_registered(conn, result.tracking_number)` check after parse; inside the hit-branch uses `INSERT OR IGNORE INTO processed_emails` (D-03 parameterized — T-04-08 mitigated) inside `with conn:` atomic block; logs `dedup.tracking.skip` at debug; continues without calling registrar
   - DEDUP-05: `register_and_persist(conn, email.message_id, result.tracking_number, registrar)` for fresh tracking numbers
   - WR-04 `except Exception as exc:` handler logs `pipeline.error id=%s type=%s` with `type(exc).__name__` only — never `logger.exception`, never body/tracking number (LOG-02)

2. **`.env.example`** — "Database (Phase 4)" section appended with `DATABASE_PATH=data/shipping-tracker.db` and a comment documenting the Pi override use case (D-07)

3. **`.gitignore`** — Explicit `data/` entry added (mirrors `logs/` pattern; `*.db` rule already covered the file content)

4. **`tests/test_aliexpress_parser.py`** — `test_main_dispatch_loop_logs_pii_safely_on_error` updated: log key assertion changed from `parser.dispatch.error` to `pipeline.error`; `monkeypatch.setenv("DATABASE_PATH", ":memory:")` added to avoid side-effect DB file creation during tests

---

## Verification

- `python -m pytest tests/ -q` — 57/57 passed (15 DEDUP tests + 42 prior tests; no regressions)
- `python -m mypy --strict shipping_tracker/` — zero errors across all 13 source files
- `ruff check shipping_tracker/main.py` — zero violations
- `python -c "import shipping_tracker.main"` — clean import
- Anti-pattern audit: no `isolation_level=None`; no f-string SQL; no `logger.exception`; no `tracking_number` in any log call

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test log key assertion parser.dispatch.error → pipeline.error**
- **Found during:** Task 2 (immediately visible — test would fail with new log key)
- **Issue:** `test_main_dispatch_loop_logs_pii_safely_on_error` asserted `"parser.dispatch.error"` in log records; plan renames this key to `"pipeline.error"` per 04-PATTERNS.md §main.py. Keeping the old key would make the test assert on a log line that no longer exists.
- **Fix:** Updated the assertion in `test_aliexpress_parser.py` to check for `"pipeline.error"`; added `monkeypatch.setenv("DATABASE_PATH", ":memory:")` to prevent side-effect DB file creation during test execution
- **Files modified:** `tests/test_aliexpress_parser.py`
- **Commit:** `eb62b96`

**2. [Rule 2 - Missing critical functionality] tracking_results only appended on persisted=True**
- **Found during:** Task 2 (implementation review)
- **Issue:** The plan's target loop shape calls `register_and_persist(...)` but does not explicitly specify when to append to `tracking_results`. Since `NullRegistrar` always returns False (deferred), appending unconditionally would give a misleading `parsed=N` count in `parser.dispatch.complete`.
- **Fix:** Only append `result` to `tracking_results` when `register_and_persist` returns `True`; the `parsed=` count in the summary log now accurately reflects actually-persisted registrations, not just parsed tracking numbers.
- **Files modified:** `shipping_tracker/main.py`
- **Commit:** `eb62b96`

---

## Known Stubs

None. `NullRegistrar` is the intentional Phase 4 placeholder (D-09) — it is the correct live implementation for Phase 4 cron runs. `parsed=0` in the dispatch-complete log is honest (NullRegistrar always returns False). Phase 5 replaces it with `TrackingMoreRegistrar` via the same seam; `parsed=N` will then reflect real registrations.

---

## Threat Surface Scan

T-04-08 (Tampering — D-03 INSERT OR IGNORE in main()): The `INSERT OR IGNORE INTO processed_emails VALUES (?, ?)` call in the DEDUP-04 branch uses parameterized `?` placeholders for both `email.message_id` and the UTC timestamp. No f-strings or string concatenation in any SQL statement. Mitigated as planned.

T-04-09 (Information disclosure — WR-04 per-email error log): `pipeline.error id=%s type=%s` with `type(exc).__name__` only. No `logger.exception`. Verified by grep audit and test assertion (`record.exc_info is None`). Mitigated as planned.

No new threat surface introduced beyond what was in the plan's threat model.

---

## Self-Check: PASSED

Files exist:
- `shipping_tracker/main.py` — FOUND (modified)
- `.env.example` — FOUND (modified)
- `.gitignore` — FOUND (modified)
- `tests/test_aliexpress_parser.py` — FOUND (modified)

Commits exist:
- `f36566b` — chore(04-03): add DATABASE_PATH to .env.example + data/ to .gitignore (D-07)
- `eb62b96` — feat(04-03): wire dedup + connection lifecycle into main() (DEDUP-03/04/05, D-05)
