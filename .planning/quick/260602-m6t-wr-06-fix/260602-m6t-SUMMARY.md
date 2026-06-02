---
phase: quick
plan: 260602-m6t
subsystem: registrar
tags: [error-handling, exceptions, robustness, WR-06]
dependency_graph:
  requires: []
  provides: [narrowed JSON-decode handling in _handle (WR-06)]
  affects: [shipping_tracker/registrar.py, tests/test_registrar.py]
tech_stack:
  added: []
  patterns: [catch specific decode error, not blanket Exception]
key_files:
  modified:
    - shipping_tracker/registrar.py
    - tests/test_registrar.py
decisions:
  - "Catch (json.JSONDecodeError, ValueError) around resp.json() instead of bare Exception, per the review. json.JSONDecodeError subclasses ValueError; listing both is explicit and matches the recommended fix."
metrics:
  duration: ~6 min
  completed_date: 2026-06-02
requirements: [WR-06]
---

# Phase quick Plan 260602-m6t: Narrow resp.json() except in _handle (WR-06) Summary

**One-liner:** `_handle` now catches only JSON-decode errors around `resp.json()`, so a genuine non-decode error surfaces instead of being masked as an empty body.

## What Was Built

`shipping_tracker/registrar.py` `_handle` used `try: body = resp.json() except Exception: body = {}`. The intent (per the comment) is only to tolerate a non-JSON body, but the blanket `except Exception` also swallowed unrelated failures (e.g. a `TypeError`/`AttributeError` from an unexpected response object), masking genuine programming errors as "empty body → fall through to status checks."

The fix narrows the clause:

```python
import json
...
try:
    body = resp.json()
except (json.JSONDecodeError, ValueError):
    body = {}  # tolerate ONLY a non-JSON body; let non-decode errors propagate
```

`json.JSONDecodeError` subclasses `ValueError`; both are listed for explicitness, matching the review's recommended fix. The intended tolerance is preserved (a non-JSON body still falls through to the status checks and returns False).

New regression tests in `tests/test_registrar.py`:
- `test_non_json_body_tolerated`: a 200 with a non-JSON text body returns False without raising (decode error tolerated). Behavior-lock — passes on both old and new code.
- `test_unexpected_json_error_propagates`: monkeypatches a response's `.json` to raise `TypeError`; asserts `_handle` re-raises it. This is the WR-06-distinguishing test.

Confirmed via `git stash`: the propagate test **fails on the old bare `except Exception`** (TypeError swallowed → `registrar.error code=None` → returns False, "DID NOT RAISE") and **passes on the fix**; the tolerated test passes on both.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Narrow resp.json() except + WR-06 regression tests | 273978c | shipping_tracker/registrar.py, tests/test_registrar.py |

## Test Results

- `python -m ruff check .`: **All checks passed!**
- `python -m mypy .` (whole project): **Success: no issues found in 28 source files**
- `python -m pytest -q`: **81 passed** (79 prior + 2 new)
- Regression proof: propagate test fails on old code, passes on fix.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Note

The Phase 05 review's remaining items are **Info**-level, not WR-*: IN-01 (untested 4101/4190/HTTP-402 quota codes) and IN-02 (the unreachable final `return False` rationale). These are lower priority and out of scope for WR-06; flag if you want them addressed.
