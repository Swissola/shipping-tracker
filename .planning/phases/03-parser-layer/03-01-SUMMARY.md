---
phase: 03-parser-layer
plan: "01"
subsystem: parsers
tags: [tdd, red-scaffold, base-contract, fixtures, privacy]
dependency_graph:
  requires: []
  provides: [TrackingInfo-carrier-optional, BaseParser-extract-None-contract, fake-aliexpress-fixtures, parser-test-stubs]
  affects: [shipping_tracker/parsers/base.py, tests/test_smoke.py, tests/fixtures/fake_aliexpress_email.py, tests/test_aliexpress_parser.py]
tech_stack:
  added: []
  patterns: [from __future__ import annotations, str | None = None dataclass default, type: ignore[import-not-found] for Wave 0 stubs]
key_files:
  created:
    - tests/fixtures/fake_aliexpress_email.py
    - tests/test_aliexpress_parser.py
  modified:
    - shipping_tracker/parsers/base.py
    - tests/test_smoke.py
decisions:
  - "D-04: TrackingInfo.carrier is str | None = None — carrier is optional metadata since TrackingMore auto-detects couriers"
  - "D-05: BaseParser.extract() returns TrackingInfo | None (not raises ValueError) for pre-shipment emails — error-free dispatch loop"
  - "Wave 0 type: ignore guards on missing aliexpress module — mypy passes at RED scaffold stage without stub files"
metrics:
  duration_minutes: 8
  completed_date: "2026-06-01"
  tasks_completed: 2
  files_changed: 4
---

# Phase 03 Plan 01: Contract Edits and RED Test Scaffold Summary

**One-liner:** TrackingInfo.carrier made optional (D-04), extract() contract changed to return `TrackingInfo | None` (D-05), 7 FAKE-prefixed AliExpress fixtures created, 12 RED parser test stubs written covering PARSE-01/02/03.

## What Was Built

### Task 1: D-04 + D-05 contract edits to base.py

- Added `from __future__ import annotations` as first import (matches `client.py` convention)
- Changed `TrackingInfo.carrier: str` to `carrier: str | None = None` — required field precedes defaulted field per mypy strict ordering
- Changed `BaseParser.extract()` return type from `-> TrackingInfo` to `-> TrackingInfo | None`
- Removed `Raises: ValueError` clause from extract() docstring; added note that None is returned for pre-shipment emails (D-05)
- Added `test_tracking_info_carrier_optional` to `tests/test_smoke.py` immediately after `test_tracking_info_dataclass`

### Task 2: Synthetic fixtures and 12 failing test stubs

- Created `tests/fixtures/fake_aliexpress_email.py` with 7 constants: `FAKE_ALIEXPRESS_SHIPPED_BODY`, `FAKE_ALIEXPRESS_LOGISTICS_BODY`, `FAKE_ALIEXPRESS_TRACKING_NO_BODY`, `FAKE_ALIEXPRESS_PRESHIPMENT_BODY`, `FAKE_ALIEXPRESS_NOLABEL_BODY`, `FAKE_ALIEXPRESS_SENDER`, `FAKE_OTHER_SENDER` — all FAKE-prefixed, no real domains
- Created `tests/test_aliexpress_parser.py` with 12 test functions covering: `test_tracking_info_carrier_optional`, `test_can_parse_known_domains`, `test_can_parse_rejects_other_senders`, `test_extract_label_anchored`, `test_extract_shape_fallback`, `test_extract_returns_none_preshipment`, `test_extract_carrier_none`, `test_extract_does_not_log_pii`, `test_dispatch_matched_email`, `test_dispatch_no_match_skips`, `test_dispatch_preshipment_skips`, `test_registry_drop_in`
- Suite is RED (ModuleNotFoundError on `shipping_tracker.parsers.aliexpress`) — expected Wave 0 state; goes green after Plans 02 and 03

## Verification Results

| Check | Result |
|-------|--------|
| `python -m mypy shipping_tracker/parsers/base.py` | 0 errors |
| `pytest tests/test_smoke.py -q` | 6 passed |
| `pytest tests/test_smoke.py::test_tracking_info_carrier_optional` | passed |
| `pytest tests/test_smoke.py::test_tracking_info_dataclass` | passed (positional construction still works) |
| `pytest tests/test_aliexpress_parser.py --collect-only` | Import error RED (expected — aliexpress.py not yet created) |
| Privacy check: no real aliexpress.com domains in fixtures | passed |
| Pre-commit hooks (ruff + mypy) | passed on both commits |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pre-commit ruff E501 line-too-long in test docstring**
- **Found during:** Task 2 commit attempt
- **Issue:** Docstring for `test_extract_shape_fallback` was 93 chars (limit: 88)
- **Fix:** Shortened docstring to "extract() returns TrackingInfo via shape-pattern fallback (no label present)."
- **Files modified:** tests/test_aliexpress_parser.py
- **Commit:** 5f9212c

**2. [Rule 2 - Missing functionality] mypy --strict fails on missing aliexpress module import**
- **Found during:** Task 2 commit attempt
- **Issue:** Top-level import of `shipping_tracker.parsers.aliexpress` caused mypy errors (module doesn't exist at Wave 0). Pre-commit hook blocks commit on mypy failure.
- **Fix:** Added `# type: ignore[import-not-found]` to the aliexpress import and `# type: ignore[attr-defined]` to the four `from shipping_tracker.main import PARSERS` lines in dispatch tests — preserves Wave 0 RED intent while satisfying mypy strict
- **Files modified:** tests/test_aliexpress_parser.py
- **Commit:** 5f9212c

**3. [Ruff auto-fix] Import ordering and unused imports**
- **Found during:** Task 2 first commit attempt
- **Issue:** ruff auto-fixed 4 import issues (ordering, grouping) and removed unused fixture imports (`FAKE_ALIEXPRESS_LOGISTICS_BODY`, `FAKE_ALIEXPRESS_TRACKING_NO_BODY`) not referenced by any test in this plan
- **Fix:** Accepted ruff's auto-fixes; the removed constants remain in the fixture file for Plan 02 use
- **Commit:** 5f9212c

## Known Stubs

`tests/test_aliexpress_parser.py` is intentionally a stub suite — all 12 tests fail because `AliExpressParser` (Plan 02) and `main.PARSERS` (Plan 03) are not yet implemented. This is the planned Wave 0 state.

## Threat Flags

No new network endpoints, auth paths, or schema changes introduced. Threat model mitigations T-03-01 (PRIVACY docstring + FAKE-prefix convention in fixtures) and T-03-02 (test_extract_does_not_log_pii stub present) have been applied.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| commit 0b45f07 (Task 1 — base.py + test_smoke.py) | FOUND |
| commit 5f9212c (Task 2 — fixtures + test stubs) | FOUND |
| shipping_tracker/parsers/base.py modified | confirmed via git show |
| tests/test_smoke.py modified | confirmed via git show |
| tests/fixtures/fake_aliexpress_email.py created | confirmed via git show |
| tests/test_aliexpress_parser.py created | confirmed via git show |
