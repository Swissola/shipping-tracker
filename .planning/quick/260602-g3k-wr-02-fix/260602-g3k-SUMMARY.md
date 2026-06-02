---
phase: quick
plan: 260602-g3k
subsystem: main
tags: [filesystem, db-path, side-effects, WR-02]
dependency_graph:
  requires: []
  provides: [main() db-dir creation matches sqlite connect target (WR-02)]
  affects: [shipping_tracker/main.py, tests/test_main.py]
tech_stack:
  added: []
  patterns: [guarded makedirs — create dir only when path has one]
key_files:
  modified:
    - shipping_tracker/main.py
  added:
    - tests/test_main.py
decisions:
  - "Replaced `os.path.dirname(db_path) or \"data\"` with a guarded `if db_dir: makedirs(db_dir)` so the created dir always matches sqlite3.connect's target — no fabricated data/ dir for bare-filename or :memory: paths."
metrics:
  duration: ~6 min
  completed_date: 2026-06-02
requirements: [WR-02]
---

# Phase quick Plan 260602-g3k: Fix spurious data/ dir for bare-filename DB paths (WR-02) Summary

**One-liner:** `main()` no longer fabricates a mismatched `data/` directory for bare-filename or `:memory:` `DATABASE_PATH` — it creates a directory only when the path actually has one.

## What Was Built

`shipping_tracker/main.py:80` ran `os.makedirs(os.path.dirname(db_path) or "data", exist_ok=True)`. When `DATABASE_PATH` had no directory component (e.g. `tracker.db`), `os.path.dirname` returned `""`, so the `or "data"` fallback created a `data/` directory — but `sqlite3.connect(db_path)` then wrote `tracker.db` to the **CWD**, not `data/`. The result was a spurious empty `data/` directory plus a DB file in an unexpected location. For `DATABASE_PATH=:memory:` it needlessly created `data/` on disk for an in-memory DB.

The fix replaces the `or "data"` fallback with a guarded form:

```python
db_dir = os.path.dirname(db_path)
if db_dir:
    os.makedirs(db_dir, exist_ok=True)
```

A directory is now created only when `db_path` actually has one, so the `makedirs` target always matches what `connect()` uses. The default `data/shipping-tracker.db` still yields `db_dir="data"` → created, so default behavior is preserved.

New `tests/test_main.py` adds two regression tests driving the real `main()` (fetch patched to return `[]`, synthetic API key, isolated CWD via `monkeypatch.chdir(tmp_path)`):
- `test_bare_filename_db_path_creates_no_spurious_data_dir`: `DATABASE_PATH=tracker.db` → DB lands at `tmp_path/tracker.db`, no `data/` dir created.
- `test_memory_db_path_creates_no_data_dir`: `DATABASE_PATH=:memory:` → no `data/` dir created.

Both tests were confirmed to FAIL against the pre-fix code (spurious `data/` created) and PASS against the fix.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Guarded makedirs in main() + WR-02 regression tests | _pending_ | shipping_tracker/main.py, tests/test_main.py |

## Test Results

- `python -m ruff check .`: **All checks passed!**
- `python -m mypy --strict shipping_tracker/`: **Success: no issues found in 13 source files**
- `python -m pytest -q`: **75 passed** (73 prior + 2 new)
- Regression proof: new tests fail on old code, pass on fixed code (verified via `git stash`).

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.
