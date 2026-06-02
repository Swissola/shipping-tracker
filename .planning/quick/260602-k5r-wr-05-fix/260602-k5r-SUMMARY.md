---
phase: quick
plan: 260602-k5r
subsystem: registrar
tags: [retry, backoff, jitter, robustness, cron, WR-05]
dependency_graph:
  requires: []
  provides: [bounded+jittered registrar retries (WR-05)]
  affects: [shipping_tracker/registrar.py, tests/test_registrar.py]
tech_stack:
  added: []
  patterns: [per-run retry budget + jittered backoff]
key_files:
  modified:
    - shipping_tracker/registrar.py
    - tests/test_registrar.py
decisions:
  - "Budget + jitter (user-selected via AskUserQuestion, see CONTEXT.md): a per-run retry budget bounds total retries across the batch; random.uniform(0, retry_jitter) de-synchronises retries. Addresses both the unbounded cumulative-sleep and the synchronized-retry sub-concerns."
  - "Per-call semantics preserved: still at most one retry per __call__ (attempt==0 guard). New knobs are keyword-only with safe defaults (retry_jitter=1.0, max_total_retries=8)."
metrics:
  duration: ~12 min
  completed_date: 2026-06-02
requirements: [WR-05]
---

# Phase quick Plan 260602-k5r: Bound + jitter registrar retries (WR-05) Summary

**One-liner:** The registrar now caps total retries across a run with a per-instance budget and jitters each retry pause, so a batch of transient failures can no longer accumulate unbounded serial sleep or synchronise retries against a recovering API.

## What Was Built

`shipping_tracker/registrar.py` previously retried transient failures (timeout/connect error, 5xx) with a fixed `time.sleep(self._retry_pause)` (default 2.0s) and no jitter. Each `__call__` retries at most once, but the `TrackingMoreRegistrar` instance is created once per run and reused for every email, so N transient-failing emails accumulated up to N×2s of serial sleep with no upper bound — risking collision with the cron interval and overlapping runs. No jitter meant retries against a recovering API could synchronise (unlike the Gmail client's `random.uniform(0, 1)` backoff).

**Decision (user-selected via AskUserQuestion — see `260602-k5r-CONTEXT.md`): Budget + jitter**, the most complete of the review's offered options.

Changes:
- Added `import random`.
- Two keyword-only `__init__` knobs with safe defaults: `retry_jitter: float = 1.0`, `max_total_retries: int = 8`; stored as `self._retry_jitter` and `self._retry_budget`.
- New `_sleep_for_retry()` helper: returns `False` immediately if the per-run budget is exhausted (caller defers); otherwise decrements the budget, sleeps `retry_pause + random.uniform(0, retry_jitter)`, and returns `True`.
- Both retry sites in `__call__` changed from `if attempt == 0: sleep; continue` to `if attempt == 0 and self._sleep_for_retry(): continue`. Per-call at-most-one-retry semantics are preserved; the budget caps cumulative retries across the batch; when the budget is exhausted, even attempt 0 defers.

Tests:
- `_make_registrar` now also passes `retry_jitter=0` so existing retry tests stay fast and deterministic.
- `test_retry_budget_bounds_cumulative_retries`: with `max_total_retries=1`, the first retry-eligible call spends the only budget unit (2 requests) and the second defers immediately (1 request) → total 3, both return `False`.
- `test_retry_pause_includes_jitter`: patches `registrar.time.sleep` and `registrar.random.uniform`→0.5; one `__call__` against a 500 sleeps exactly once for `2.0 + 0.5 == 2.5`.

Confirmed via `git stash`: both new tests fail on the old code and pass on the fix.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Per-run retry budget + jitter + regression tests | a4f2bd8 | shipping_tracker/registrar.py, tests/test_registrar.py |

## Test Results

- `python -m ruff check .`: **All checks passed!**
- `python -m mypy --strict shipping_tracker/`: **Success: no issues found in 13 source files**
- `python -m pytest -q`: **79 passed** (77 prior + 2 new)
- Regression proof: both new tests fail on old code, pass on fixed code.

## Deviations from Plan

None of substance — one trivial tweak: shortened a 500-response JSON `message` string in the new tests to satisfy ruff's 88-char line limit.

## Known Stubs

None.

## Note

`max_total_retries=8` and `retry_jitter=1.0` are conservative defaults. They are constructor knobs, so a future phase can expose them via env if cron tuning warrants. Worst-case added latency per run is now bounded at roughly `max_total_retries × (retry_pause + retry_jitter)` ≈ 8 × 3s = 24s.
