---
phase: quick
plan: 260602-j4p
subsystem: main
tags: [privacy, pii, logging, credentials, WR-04]
dependency_graph:
  requires: []
  provides: [PII-safe missing-credentials log (WR-04, Phase 05 review)]
  affects: [shipping_tracker/main.py, tests/test_main.py]
tech_stack:
  added: []
  patterns: [log basename not full path for PII safety]
key_files:
  modified:
    - shipping_tracker/main.py
    - tests/test_main.py
decisions:
  - "Missing-credentials branch now logs os.path.basename(exc.filename) instead of the full path, so an absolute GMAIL_CREDENTIALS_PATH cannot leak a directory / OS username into logs destined for a public project."
metrics:
  duration: ~8 min
  completed_date: 2026-06-02
requirements: [WR-04]
---

# Phase quick Plan 260602-j4p: PII-safe missing-credentials log (WR-04) Summary

**One-liner:** `main()` now logs only the basename of the credentials file on the missing-credentials branch, so an absolute path can no longer leak an OS username into the logs.

## What Was Built

`shipping_tracker/main.py:105` logged `logger.error("gmail.credentials.missing path=%s", exc.filename)`. The default (`credentials.json`) is harmless, but operators commonly point `GMAIL_CREDENTIALS_PATH` at an absolute path such as `/home/<username>/.config/shipping-tracker/credentials.json`, so the log could embed an OS username. Given the project's non-negotiable "no PII in logs" constraint and intended public release, that is a privacy regression.

The fix logs only the basename:

```python
logger.error(
    "gmail.credentials.missing name=%s",
    os.path.basename(exc.filename or ""),
)
```

`os` was already imported; the `return 1` and surrounding try/except are unchanged.

New regression test in `tests/test_main.py` drives the real `main()` (configure_logging stubbed to no-op so `caplog` captures; synthetic API key; `DATABASE_PATH=:memory:`; CWD isolated) with `fetch_unread_shipping_emails` raising a `FileNotFoundError` whose `.filename` is `/home/SECRETUSER/.config/shipping-tracker/credentials.json`. It asserts `main()` returns 1, a `gmail.credentials.missing` record exists, no record contains `SECRETUSER` / `/home/` / `.config`, and the basename `credentials.json` is present.

Confirmed via `git stash`: the test fails on the old code (`'SECRETUSER' in '...path=/home/SECRETUSER/.../credentials.json'`) and passes on the fix.

## Scope note — two distinct WR-04s

This is the **Phase 05 review** WR-04 (credentials-path leak in `main()`), which was still open. It is distinct from the **Phase 03 review** WR-04 (dispatch-error PII hardening), already committed as `1c5b347` and retroactively recorded by quick task `260601-kp7`. They share a number but are different findings; both are now addressed.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Log credentials basename only + WR-04 regression test | _pending_ | shipping_tracker/main.py, tests/test_main.py |

## Test Results

- `python -m ruff check .`: **All checks passed!**
- `python -m mypy --strict shipping_tracker/`: **Success: no issues found in 13 source files**
- `python -m pytest -q`: **77 passed** (76 prior + 1 new)
- Regression proof: new test fails on old code (username leaked), passes on fixed code.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.
