---
phase: quick
plan: 260602-p8x
subsystem: registrar
tags: [code-clarity, mypy, unreachable, IN-02]
dependency_graph:
  requires: []
  provides: [explicit unreachable marker in __call__ (IN-02)]
  affects: [shipping_tracker/registrar.py]
tech_stack:
  added: []
  patterns: [raise AssertionError for provably-unreachable code]
key_files:
  modified:
    - shipping_tracker/registrar.py
decisions:
  - "Replace the dead `return False` after the retry loop with `raise AssertionError('unreachable')`: same mypy return-path satisfaction, but the intent is explicit and can't be mistaken for a reachable fallthrough. No test — the line is provably unreachable."
metrics:
  duration: ~4 min
  completed_date: 2026-06-02
requirements: [IN-02]
---

# Phase quick Plan 260602-p8x: Explicit unreachable marker in __call__ (IN-02) Summary

**One-liner:** Replaced the dead `return False  # unreachable; mypy requires it` at the end of `__call__` with `raise AssertionError("unreachable")`, making the intent explicit while still satisfying mypy.

## What Was Built

The final line of `TrackingMoreRegistrar.__call__` was `return False  # unreachable; mypy requires it`. Both iterations of the `for attempt in range(2)` loop return on every path, so the line is dead code that exists only to satisfy mypy's return-path analysis. A bare `return False` there can be mistaken for a reachable fallthrough during future edits (IN-02).

It is now:

```python
# Unreachable: both attempts in the loop above return on every path. The
# explicit raise (vs a silent `return False`) makes that intent clear and
# still satisfies mypy's return-path analysis (IN-02).
raise AssertionError("unreachable")
```

`raise` terminates the function, so mypy's return-path analysis is still satisfied. No behavior change: the statement remains unreachable. No regression test is added because the line is provably unexecutable — correctness is established by mypy accepting the function and all existing tests passing unchanged.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Replace unreachable return False with raise AssertionError | 8fcbd3e | shipping_tracker/registrar.py |

## Test Results

- `python -m ruff check .`: **All checks passed!**
- `python -m mypy .` (whole project): **Success: no issues found in 28 source files**
- `python -m pytest -q`: **86 passed** (unchanged — behavior untouched)
- `git diff`: a single line changed in `__call__`; nothing else.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Note

This closes IN-02. Phase 05 review remaining: IN-03 (unused/duplicated conftest.py response builders vs inline fixtures in test_registrar.py) and IN-04 (unused synthetic_email_body fixture) — both test-hygiene cleanups; flag if you want them.
