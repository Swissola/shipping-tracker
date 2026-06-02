---
phase: quick
plan: 260602-n7v
subsystem: registrar
tags: [tests, coverage, parametrize, quota-codes, IN-01]
dependency_graph:
  requires: []
  provides: [coverage for 4101 / 4190 / HTTP-402 in _handle (IN-01)]
  affects: [tests/test_registrar.py]
tech_stack:
  added: []
  patterns: [pytest.mark.parametrize for response-code branch coverage]
key_files:
  modified:
    - tests/test_registrar.py
decisions:
  - "Test-only change. The 402 case uses a neutral meta_code (4013) because meta_code 200 would hit the success branch before the status-402 quota check — proving the status-based trigger fires independent of meta_code."
metrics:
  duration: ~7 min
  completed_date: 2026-06-02
requirements: [IN-01]
---

# Phase quick Plan 260602-n7v: Cover 4101 / 4190 / HTTP-402 in _handle (IN-01) Summary

**One-liner:** Added parametrized tests pinning the previously-untested registrar response-code branches (already-exists `4101`, quota `4190`, and the HTTP-402 quota trigger), so a future refactor can't silently drop them.

## What Was Built

`_handle` handled `meta_code in (4016, 4101)` (already-exists → True), `meta_code in (4021, 4190) or resp.status_code == 402` (quota → raise), but the suite only exercised `4016` and `4021`. The `4101`, `4190`, and HTTP-402 paths were unverified (IN-01). This is a pure coverage gap — **no source change**.

Two parametrized tests added to `tests/test_registrar.py`:
- `test_already_exists_codes_return_true[4016|4101]`: a 400 with each meta_code returns `True`.
- `test_quota_triggers_raise[400-4021|400-4190|402-4013]`: each quota trigger raises `QuotaExceededError`. The `402-4013` case uses a neutral meta_code to prove the **status-based** 402 trigger fires regardless of meta_code (an early attempt with meta_code 200 wrongly hit the success branch — corrected to 4013).

## Teeth (mutation check)

Temporarily mutated `_handle` (dropped `4101` from the already-exists tuple and `or resp.status_code == 402` from the quota branch) and reran:
- `test_already_exists_codes_return_true[4101]` → **failed** (as intended)
- `test_quota_triggers_raise[402-4013]` → **failed** (as intended)
- The unmutated codes (4016, 4021, 4190) still passed.

Source restored; `git diff` on `registrar.py` is empty.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Parametrized coverage for 4101 / 4190 / HTTP-402 | 6ab8bf3 | tests/test_registrar.py |

## Test Results

- `python -m ruff check .`: **All checks passed!**
- `python -m mypy .` (whole project): **Success: no issues found in 28 source files**
- `python -m pytest -q`: **86 passed** (81 prior + 5 new parametrized cases)

## Deviations from Plan

Minor: the planned `(402, 200)` parameter was changed to `(402, 4013)` because meta_code 200 short-circuits to the success branch before the status-402 check. The corrected case still proves the status-based trigger.

## Known Stubs

None.

## Note

This clears IN-01. The remaining Phase 05 review item is IN-02 (the unreachable final `return False` in `__call__` carries only an inline rationale) — cosmetic/doc-level; flag if you want it addressed.
