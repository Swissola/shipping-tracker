---
phase: quick
plan: 260602-q9z
subsystem: tests
tags: [test-hygiene, dead-code, conftest, IN-03, IN-04]
dependency_graph:
  requires: []
  provides: [conftest.py trimmed to consumed fixtures only (IN-03, IN-04)]
  affects: [tests/conftest.py]
tech_stack:
  added: []
  patterns: [single canonical inline synthetic responses]
key_files:
  modified:
    - tests/conftest.py
decisions:
  - "Deleted the dead code rather than wiring the builders into tests: the inline-response form is already the suite-wide convention, so deletion removes duplication with zero drift risk. Confirmed via grep that nothing outside conftest.py referenced the removed symbols."
metrics:
  duration: ~5 min
  completed_date: 2026-06-02
requirements: [IN-03, IN-04]
---

# Phase quick Plan 260602-q9z: Remove dead conftest scaffolding (IN-03 + IN-04) Summary

**One-liner:** Deleted five unused TrackingMore response builders (IN-03), the unused `synthetic_email_body` fixture (IN-04), and the now-orphaned `import httpx` from `tests/conftest.py`, leaving only the fixtures tests actually consume.

## What Was Built

`tests/conftest.py` carried dead/duplicated scaffolding:
- **IN-03:** `make_success_response`, `make_already_exists_response`, `make_quota_response`, `make_rate_limit_response`, `make_5xx_response` — module-level builders that no test imported. `test_registrar.py` builds its `httpx.Response` objects inline, so the canonical synthetic responses existed twice and could drift.
- **IN-04:** the `synthetic_email_body` fixture, defined but consumed by no test.

A grep across the whole `tests/` tree confirmed **zero references** to any of the five builders or `synthetic_email_body` outside `conftest.py` itself, and no module imports `conftest` directly.

**Decision: delete** (not rewire). The inline-response form is the established suite-wide convention — the review's own "if the inline form is preferred" branch — so removing the duplicates eliminates drift risk with no churn to passing tests.

Removed:
- the `synthetic_email_body` fixture,
- the entire "Synthetic TrackingMore v4 response builders" block and all five functions,
- `import httpx` (referenced only by the deleted builders).

Preserved unchanged: the module docstring, the remaining imports (`sqlite3`, `Generator`, `pytest`, `respx`, `init_db`), and the `db_conn` and `mock_router` fixtures (both are consumed by tests).

Net: 65 lines deleted, no additions.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Remove unused builders + synthetic_email_body + httpx import | _pending_ | tests/conftest.py |

## Test Results

- `python -m ruff check .`: **All checks passed!** (no unused-import warnings remain)
- `python -m mypy .` (whole project): **Success: no issues found in 28 source files**
- `python -m pytest -q`: **86 passed** (unchanged) — proves nothing consumed the removed code.
- `git diff --stat tests/conftest.py`: 65 deletions, 0 insertions.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Note

This closes IN-03 and IN-04 — the final items in the Phase 05 code review (`05-REVIEW.md`). With WR-01..06, IN-01, and IN-02 already done, **every finding in the Phase 05 review is now resolved.**
