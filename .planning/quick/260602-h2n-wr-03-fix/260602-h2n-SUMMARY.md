---
phase: quick
plan: 260602-h2n
subsystem: logging
tags: [logging, handlers, idempotency, fd-leak, WR-03]
dependency_graph:
  requires: []
  provides: [idempotent configure_logging (WR-03)]
  affects: [shipping_tracker/logging_config.py, tests/test_logging_config.py]
tech_stack:
  added: []
  patterns: [clear-then-add root handlers for idempotent logging config]
key_files:
  modified:
    - shipping_tracker/logging_config.py
  added:
    - tests/test_logging_config.py
decisions:
  - "configure_logging now removes and closes existing root handlers before adding the RotatingFileHandler, making repeated calls idempotent. Per the review's recommended fix."
metrics:
  duration: ~7 min
  completed_date: 2026-06-02
requirements: [WR-03]
---

# Phase quick Plan 260602-h2n: Make configure_logging idempotent (WR-03) Summary

**One-liner:** `configure_logging` now clears and closes existing root handlers before adding its `RotatingFileHandler`, so repeated calls no longer leak handlers/file descriptors or duplicate log lines.

## What Was Built

`shipping_tracker/logging_config.py` previously did `root_logger.addHandler(handler)` without removing existing handlers and unconditionally set the root level. Each `main()` run — and several tests that invoke `main()` — appended another `RotatingFileHandler` and opened another file handle on `logs/shipping-tracker.log`. Within a single process calling `main()` more than once (the test suite does), handlers and open file descriptors accumulated and log lines were emitted multiple times. It also forced the root level mid-test, a `caplog` hazard.

The fix makes configuration idempotent — before adding the new handler:

```python
root_logger = logging.getLogger()
for existing in list(root_logger.handlers):
    root_logger.removeHandler(existing)
    existing.close()
root_logger.addHandler(handler)
root_logger.setLevel(log_level)
```

Cron one-shot behavior is unchanged: a single `RotatingFileHandler`, no `StreamHandler` (LOG-03), root level per D-07.

New `tests/test_logging_config.py` adds a regression test that saves/restores the root logger's handlers and level (so the fix's handler-closing doesn't pollute the rest of the suite), redirects `log_path` into `tmp_path`, calls `configure_logging` twice, and asserts exactly **one** `RotatingFileHandler` remains and the root level is `WARNING`.

Confirmed via `git stash`: the test fails on the old code (2 RotatingFileHandlers after two calls) and passes on the fix.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Make configure_logging idempotent + WR-03 regression test | 29e60a6 | shipping_tracker/logging_config.py, tests/test_logging_config.py |

## Test Results

- `python -m ruff check .`: **All checks passed!**
- `python -m mypy --strict shipping_tracker/`: **Success: no issues found in 13 source files**
- `python -m pytest -q`: **76 passed** (75 prior + 1 new)
- Regression proof: new test fails on old code (`assert 2 == 1`), passes on fixed code.

## Deviations from Plan

None — plan executed exactly as written (plus a trivial ruff cleanup: removed an unused `pytest` import from the new test).

## Known Stubs

None.

## Note

`configure_logging` line 23 uses the same `os.path.dirname(log_path) or "logs"` pattern that WR-02 fixed in `main.py`. It is benign for the default `logs/shipping-tracker.log` (has a dir component), but is the same latent bare-filename hazard. Left out of scope for WR-03 (handler-leak only); flag if a follow-up cleanup is wanted.
