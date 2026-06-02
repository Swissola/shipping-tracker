---
phase: quick
plan: 260602-fv0
subsystem: db
tags: [docstring, idempotency, billing, WR-01]
dependency_graph:
  requires: []
  provides: [register_and_persist accurate contract docstring (WR-01)]
  affects: [shipping_tracker/db.py]
tech_stack:
  added: []
  patterns: [caller-enforced dedup before billable primitive]
key_files:
  modified:
    - shipping_tracker/db.py
decisions:
  - "Fix is docstring-only: register_and_persist deliberately holds no dedup policy (locked decision centralizes it in main.py DEDUP-03/04/05). The defect was the lying docstring, not the code — adding an internal guard would be dead code in the real pipeline."
metrics:
  duration: ~5 min
  completed_date: 2026-06-02
requirements: [WR-01]
---

# Phase quick Plan 260602-fv0: Fix register_and_persist docstring overclaim (WR-01) Summary

**One-liner:** Rewrote the `register_and_persist` docstring so it no longer falsely claims the function is "idempotent / safe to retry" — it always makes a billable TrackingMore call — and now instructs callers to dedup first.

## What Was Built

The prior quick task (260601-pa7) made the two DB writes in `register_and_persist` idempotent via `INSERT OR IGNORE` and documented that as "Idempotent / safe to retry (WR-01): a repeat call ... is a silent no-op ... and still returns True." That claim is wrong at the cost layer: the function calls `registrar(tracking_number, carrier)` **unconditionally** at db.py:92 — a billable TrackingMore API call — *before* any DB lookup. Only the DB writes are idempotent. A caller trusting the docstring and invoking the function directly for an already-registered number would burn free-tier quota.

Per the locked decision, dedup policy is deliberately centralized in the orchestrator (`main.py` DEDUP-03/04/05). `register_and_persist` is a lower-level primitive — "call registrar, persist atomically on success." Adding an internal guard would duplicate policy and be dead code in the real pipeline (main.py:136 always pre-empts it). So the fix is **docstring-only**.

The rewritten docstring now:
- States the function ALWAYS calls the registrar (billable, NOT idempotent / not safe to retry at the cost/API layer).
- Instructs callers to enforce dedup via `is_tracking_registered()` / `is_email_processed()` BEFORE invoking, citing `main.py:136` (DEDUP-04) as the real pipeline's guard.
- Scopes the idempotency that *is* true to the DB-write layer only (`INSERT OR IGNORE` — no `IntegrityError` on duplicate, but the registrar call already happened).
- Preserves the accurate notes: True/False return semantics, atomic failure (D-01), exception propagation to main.py WR-04 single log site, PRIVACY LOG-02 (message_id only), and the D-08 carrier hint.

Zero executable-code changes.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Rewrite register_and_persist docstring to match real behavior | 8a49029 | shipping_tracker/db.py |

## Test Results

- `python -m ruff check .`: **All checks passed!**
- `python -m mypy --strict shipping_tracker/`: **Success: no issues found in 13 source files**
- `python -m pytest -q`: **73 passed** (unchanged — behavior untouched)
- `git diff shipping_tracker/db.py`: changes confined to the docstring; def signature and body untouched.

## Deviations from Plan

None — plan executed exactly as written. Session was interrupted before the edit was applied; on resume the working tree was clean (false docstring still present), so the docstring rewrite was applied fresh and verified.

## Known Stubs

None.
