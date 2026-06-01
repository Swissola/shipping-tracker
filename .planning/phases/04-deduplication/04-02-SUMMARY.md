---
phase: 04-deduplication
plan: "02"
subsystem: state-layer
tags: [tdd, nyquist, deduplication, sqlite, registrar, protocol]
dependency_graph:
  requires:
    - tests/test_db.py (15 RED DEDUP test functions — Wave 0 contract from Plan 01)
    - tests/conftest.py (db_conn in-memory sqlite3 fixture from Plan 01)
  provides:
    - shipping_tracker/db.py (init_db, is_email_processed, is_tracking_registered, register_and_persist)
    - shipping_tracker/registrar.py (Registrar Protocol + NullRegistrar placeholder)
  affects:
    - Plan 03 (main.py wiring will import init_db, is_email_processed, is_tracking_registered, register_and_persist, NullRegistrar, Registrar)
    - Phase 5 (TrackingMoreRegistrar drops into the Registrar seam with zero db.py/main.py changes)
tech_stack:
  added: []
  patterns:
    - "typing.Protocol for injectable seam (Registrar callable contract)"
    - "with conn: atomic two-row write (commit-on-success, rollback-on-exception)"
    - "CREATE TABLE IF NOT EXISTS idempotent schema init"
    - "PRAGMA busy_timeout + PRAGMA user_version"
    - "Parameterized SQL queries only (ASVS V5 — no f-strings)"
    - "Exception re-raise to single log site pattern (WR-04)"
key_files:
  created:
    - shipping_tracker/registrar.py
    - shipping_tracker/db.py
  modified:
    - tests/conftest.py
    - tests/test_db.py
decisions:
  - "Registrar typed as typing.Protocol (not Callable alias) — named type is self-documenting and injectable without subclassing"
  - "register_and_persist re-raises registrar exceptions to main.py WR-04 — single consistent PII-safe log site"
  - "datetime.UTC alias used (UP017) — ruff enforced; equivalent to datetime.timezone.utc on Python 3.11+"
  - "Wave 0 type: ignore[import-not-found] comments removed from conftest.py and test_db.py — pre-commit mypy --strict caught unused ignores once source modules existed"
metrics:
  duration_minutes: 2
  completed_date: "2026-06-01"
  tasks_completed: 2
  files_changed: 4
---

# Phase 04 Plan 02: DEDUP Source Layer (Wave 1) Summary

**One-liner:** SQLite state layer (db.py) + injectable Registrar Protocol/NullRegistrar seam (registrar.py) — turns 15 RED Nyquist tests GREEN with atomic two-row write, idempotent schema, and parameterized dedup predicates.

---

## What Was Built

Phase 4 Plan 02 delivers the Wave 1 source modules that satisfy the 15 DEDUP contract tests authored in Plan 01. Both files are stdlib-only, mypy --strict clean, and ruff clean.

**Two files created, two files modified:**

1. **`shipping_tracker/registrar.py`** — `Registrar` typing.Protocol defining the callable seam (`__call__(tracking_number, carrier) -> bool`) and `NullRegistrar` placeholder (logs `registrar.deferred` at debug with no tracking_number per LOG-02, returns False per D-09). Phase 5 drops `TrackingMoreRegistrar` into this seam with zero changes to db.py or main.py.

2. **`shipping_tracker/db.py`** — Four plain functions (connection passed explicitly per D-04):
   - `init_db(conn)` — sets `PRAGMA busy_timeout = 5000` (D-10), creates both tables with `CREATE TABLE IF NOT EXISTS` (DEDUP-01/DEDUP-02 locked schema, no provider column per D-06), sets `PRAGMA user_version = 1` as final statement before `conn.commit()` (D-11 ordering)
   - `is_email_processed(conn, message_id) -> bool` — `SELECT 1 ... WHERE message_id = ?` parameterized (ASVS V5)
   - `is_tracking_registered(conn, tracking_number) -> bool` — `SELECT 1 ... WHERE tracking_number = ?` parameterized (ASVS V5)
   - `register_and_persist(conn, message_id, tracking_number, registrar) -> bool` — calls registrar; re-raises exceptions (D-08 single log site); returns False on registrar False; on True writes both rows atomically with `with conn:` (D-01), returns True

3. **`tests/conftest.py`** — Removed `# type: ignore[import-not-found]` from `shipping_tracker.db` import (unused once source module exists)

4. **`tests/test_db.py`** — Removed `# type: ignore[import-not-found]` from `shipping_tracker.db` and `shipping_tracker.registrar` imports

---

## Verification

- `python -m pytest tests/test_db.py -q` — 15/15 passed (Wave 0 RED → Wave 1 GREEN)
- `python -m pytest tests/ -q` — 57/57 passed (no regressions in existing suite)
- `mypy --strict shipping_tracker/db.py shipping_tracker/registrar.py` — zero errors
- `ruff check shipping_tracker/db.py shipping_tracker/registrar.py` — zero violations
- Anti-pattern audit: no `isolation_level=None`, no `conn.commit()` inside `with conn:`, no f-string SQL

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed Wave 0 `type: ignore[import-not-found]` comments**
- **Found during:** Pre-commit mypy --strict hook on Task 1+2 commit attempt
- **Issue:** `conftest.py` and `test_db.py` carried `# type: ignore[import-not-found]` on shipping_tracker.db/registrar imports — correct in Wave 0, but now that source modules exist they become `[unused-ignore]` errors under mypy --strict
- **Fix:** Removed from both files; also removed the Wave 0 stash annotations from import blocks
- **Files modified:** `tests/conftest.py`, `tests/test_db.py`
- **Commit:** `7b886c0`

**2. [Rule 1 - Bug] ruff UP037 + UP037: quoted annotation and datetime.UTC alias**
- **Found during:** Pre-commit ruff check on db.py
- **Issue 1:** `registrar: "Registrar"` — UP037: quoted annotation is redundant when `from __future__ import annotations` is present
- **Issue 2:** `datetime.timezone.utc` — UP017: ruff enforces `datetime.UTC` alias (Python 3.11+)
- **Fix:** Removed quotes from Registrar annotation; replaced `datetime.timezone.utc` with `datetime.UTC`
- **Files modified:** `shipping_tracker/db.py`
- **Commit:** `7b886c0`

---

## Known Stubs

None. `NullRegistrar` is an intentional Phase 4 placeholder (D-09), not a stub — it is the correct live implementation for Phase 4 cron runs. Phase 5 replaces it with `TrackingMoreRegistrar` via the same seam.

---

## Threat Surface Scan

T-04-04 (SQL injection): All queries use `?` parameterized placeholders. No f-strings or string concatenation in any SQL statement. Verified by grep audit.

T-04-05 (PII in logs): `registrar.py` logs only `"registrar.deferred"` with no arguments. `db.py` has no logger calls at all. Neither module logs `tracking_number`.

T-04-06 (registrar exception PII): `register_and_persist` re-raises registrar exceptions without wrapping or logging — the exception propagates to `main.py` WR-04 which logs `type(exc).__name__` only.

No new threat surface introduced beyond what was planned.

---

## Self-Check: PASSED

Files exist:
- `shipping_tracker/registrar.py` — FOUND
- `shipping_tracker/db.py` — FOUND
- `tests/conftest.py` — FOUND (modified)
- `tests/test_db.py` — FOUND (modified)

Commits exist:
- `7b886c0` — feat(04-02): implement db.py state layer + registrar.py seam — 15 DEDUP tests GREEN
