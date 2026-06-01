---
phase: 04-deduplication
plan: "01"
subsystem: test-scaffold
tags: [tdd, nyquist, deduplication, sqlite, fixtures]
dependency_graph:
  requires: []
  provides:
    - tests/test_db.py (15 RED DEDUP test functions — Wave 0 contract)
    - tests/fixtures/fake_db.py (FAKE-prefixed db fixture constants)
    - tests/conftest.py (db_conn in-memory sqlite3 fixture)
  affects:
    - Plan 02 (db.py source must satisfy all 15 test contracts)
    - Plan 03 (main.py wiring must satisfy integration tests)
tech_stack:
  added: []
  patterns:
    - Nyquist Wave 0: tests authored before source modules exist (RED state)
    - in-memory sqlite3 connection fixture (generator form with teardown)
    - spy registrar callables for skip-path assertions (DEDUP-04, D-03)
    - type: ignore[import-not-found] on not-yet-written Wave 1 imports
key_files:
  created:
    - tests/fixtures/fake_db.py
    - tests/test_db.py
  modified:
    - tests/conftest.py
decisions:
  - "FAKE_TRACKING_NUMBER_2 removed from test_db.py imports (unused — test coverage uses only _1)"
  - "Module-level lambda registrars rewritten as def functions (ruff E731); Registrar import dropped (unused after refactor)"
  - "type: ignore[import-not-found] on all shipping_tracker.db/registrar imports in conftest.py and test_db.py — suppresses mypy pre-commit failure in expected RED/Wave 0 state"
metrics:
  duration_minutes: 4
  completed_date: "2026-06-01"
  tasks_completed: 2
  files_changed: 3
---

# Phase 04 Plan 01: DEDUP Test Scaffold (Wave 0) Summary

**One-liner:** 15 RED Nyquist test functions for sqlite3 deduplication state layer, FAKE-prefixed fixture constants, and in-memory db_conn fixture — all authored before source modules exist.

---

## What Was Built

Phase 4 Plan 01 delivers the Nyquist Wave 0 test scaffold for the deduplication layer. All tests intentionally fail RED (collection blocked by `ModuleNotFoundError: No module named 'shipping_tracker.db'`) until Plan 02 writes the source modules. This is the design: tests pin the exact contract Plan 02 must satisfy.

**Three files created/modified:**

1. **`tests/fixtures/fake_db.py`** — Pure constants module with `FAKE_MESSAGE_ID_1/2/DUP` and `FAKE_TRACKING_NUMBER_1/2`. Privacy docstring matching `fake_aliexpress_email.py` pattern. No real tracking numbers, message IDs, or email addresses.

2. **`tests/conftest.py`** — Extended with `db_conn` generator fixture: `sqlite3.connect(":memory:")` + `init_db(conn)` called before yield. Generator form ensures `conn.close()` on teardown. Import of `shipping_tracker.db` annotated `# type: ignore[import-not-found]` to pass mypy pre-commit in Wave 0.

3. **`tests/test_db.py`** — 15 test functions covering DEDUP-01..05, D-03, D-09:
   - **DEDUP-01** (2 tests): table creation, idempotency
   - **DEDUP-02** (2 tests): registered_tracking nullable columns, user_version=1
   - **DEDUP-03** (3 tests): is_email_processed True/False, dispatch-skip integration
   - **DEDUP-04** (2 tests): is_tracking_registered True/False, dispatch-skip with spy
   - **D-03** (1 test): duplicate-notification INSERT OR IGNORE + spy registrar
   - **DEDUP-05** (4 tests): success (both rows), fail (no rows), raises (rollback), retry-proof
   - **D-09** (1 test): NullRegistrar returns False, debug log, no tracking_number in caplog

---

## Test Function Index

| Function | Req | Type |
|----------|-----|------|
| `test_init_db_creates_processed_emails` | DEDUP-01 | unit |
| `test_init_db_idempotent` | DEDUP-01 | unit |
| `test_init_db_creates_registered_tracking` | DEDUP-02 | unit |
| `test_user_version` | DEDUP-02 | unit |
| `test_is_email_processed_known` | DEDUP-03 | unit |
| `test_is_email_processed_unknown` | DEDUP-03 | unit |
| `test_dispatch_skips_processed_email` | DEDUP-03 | integration |
| `test_is_tracking_registered` | DEDUP-04 | unit |
| `test_dispatch_skips_registered_tracking` | DEDUP-04 | integration |
| `test_dup_notification_marks_email_processed` | D-03 | integration |
| `test_register_and_persist_success` | DEDUP-05 | unit |
| `test_register_and_persist_fail_returns_false` | DEDUP-05 | unit |
| `test_register_and_persist_raises_rolls_back` | DEDUP-05 | unit |
| `test_retry_proof` | DEDUP-05 | integration |
| `test_null_registrar_defers` | D-09 | unit |

---

## Verification

- `python -m pytest tests/test_db.py -q --collect-only` — fails RED with `ModuleNotFoundError: No module named 'shipping_tracker.db'` (Wave 0 expected state)
- `python -m ruff check tests/` — passes with no violations
- Both new files and extended conftest.py parse as valid Python
- All pre-commit hooks pass (ruff check, ruff format, mypy strict)

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused `FAKE_TRACKING_NUMBER_2` import**
- **Found during:** Task 2 ruff check
- **Issue:** `FAKE_TRACKING_NUMBER_2` imported from `tests.fixtures.fake_db` but not referenced in any test function (all tests needing two IDs use `FAKE_MESSAGE_ID_1/2`, not a second tracking number)
- **Fix:** Removed from import block; `FAKE_TRACKING_NUMBER_2` remains defined in `fake_db.py` for Plan 02/03 tests
- **Files modified:** `tests/test_db.py`

**2. [Rule 1 - Bug] Rewrote module-level lambda registrars as `def` functions**
- **Found during:** Task 2 ruff check (E731)
- **Issue:** ruff E731 prohibits assigning lambda expressions to names; also the `# type: ignore[assignment]` annotations referencing `Registrar` were no longer needed after the rewrite
- **Fix:** `fail_registrar` and `success_registrar` written as plain `def` functions. `Registrar` type import removed (unused after refactor). `_fail`/`_success` annotation lines dropped.
- **Files modified:** `tests/test_db.py`

**3. [Rule 2 - Missing critical] Added `type: ignore[import-not-found]` on Wave 0 imports**
- **Found during:** Task 1 pre-commit hook (mypy strict)
- **Issue:** mypy pre-commit hook blocks commit on `import-not-found` for `shipping_tracker.db` — this is the intended Wave 0 RED state, but it blocks the commit
- **Fix:** Added `# type: ignore[import-not-found]` to the relevant import lines in `conftest.py` and `test_db.py`. This is the standard Nyquist scaffold pattern for Wave 0 test files.
- **Files modified:** `tests/conftest.py`, `tests/test_db.py`

---

## Known Stubs

None. This plan produces test-only artifacts; no source stubs.

---

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries introduced by this plan. All artifacts are test files only.

All T-04-01 (synthetic data only), T-04-02 (caplog LOG-02 guard in `test_null_registrar_defers`), and T-04-03 (parameterized SQL) mitigations verified present in authored files.

---

## Self-Check: PASSED

Files exist:
- `tests/fixtures/fake_db.py` — FOUND
- `tests/conftest.py` — FOUND (modified)
- `tests/test_db.py` — FOUND

Commits exist:
- `fad212a` — test(04-01): add FAKE-prefixed db fixtures and db_conn in-memory fixture
- `d54951d` — test(04-01): author 15 DEDUP test functions in test_db.py (RED — Wave 0)
