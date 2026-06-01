---
phase: quick
plan: 260601-pa7
subsystem: db
tags: [dedup, idempotency, sqlite, WR-01]
dependency_graph:
  requires: []
  provides: [register_and_persist idempotency (WR-01)]
  affects: [shipping_tracker/db.py, tests/test_db.py]
tech_stack:
  added: []
  patterns: [INSERT OR IGNORE for idempotent SQLite writes]
key_files:
  modified:
    - shipping_tracker/db.py
    - tests/test_db.py
decisions:
  - Both INSERT statements in register_and_persist converted to INSERT OR IGNORE — closes WR-01 and aligns with main.py DEDUP-04 branch pattern
metrics:
  duration: ~5 min
  completed_date: 2026-06-01
requirements: [WR-01]
---

# Phase quick Plan 260601-pa7: Make register_and_persist idempotent (WR-01) Summary

**One-liner:** Converted both `INSERT` statements in `register_and_persist` to `INSERT OR IGNORE` so duplicate calls are silent no-ops, closing code-review finding WR-01.

## What Was Built

`register_and_persist` in `shipping_tracker/db.py` previously used bare `INSERT` for both the `processed_emails` and `registered_tracking` writes. A second call with the same `message_id` + `tracking_number` would raise `sqlite3.IntegrityError` (PRIMARY KEY violation), making the function non-reentrant and entirely dependent on callers having run the upstream dedup guard first.

Both `INSERT` statements are now `INSERT OR IGNORE`, matching the pattern already used in `main.py`'s DEDUP-04 mark-processed branch. The function is now idempotent: a repeat call for already-present rows silently succeeds and returns `True`. The docstring documents this contract explicitly.

A regression test (`test_register_and_persist_idempotent`) verifies:
- First call inserts both rows and returns `True`
- Second identical call does not raise, returns `True`
- `COUNT(*)` for each table remains exactly 1

All prior failure/rollback semantics are preserved: the `with conn:` atomic transaction, `fail_registrar` returning `False`, `raising_registrar` re-raising with rollback, and `test_retry_proof` all remain unchanged and green.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Make both register_and_persist writes idempotent and add no-op regression test | 5a58eaf | shipping_tracker/db.py, tests/test_db.py |

## Test Results

- `python -m pytest -q`: **58 passed** (57 prior + 1 new no-op test)
- `python -m ruff check shipping_tracker/db.py tests/test_db.py`: clean
- `python -m mypy shipping_tracker/db.py`: clean
- `grep -c "INSERT OR IGNORE INTO" shipping_tracker/db.py`: 2 (both SQL writes converted)

## Deviations from Plan

None — plan executed exactly as written. TDD RED/GREEN cycle followed: new test was added first and confirmed failing (`IntegrityError`), then implementation was fixed to make it pass.

## Known Stubs

None.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check: PASSED

- `shipping_tracker/db.py` — modified and committed in 5a58eaf
- `tests/test_db.py` — modified and committed in 5a58eaf
- Commit 5a58eaf exists in git log
- 58 tests passing
