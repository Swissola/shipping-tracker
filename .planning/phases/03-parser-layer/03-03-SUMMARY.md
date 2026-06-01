---
phase: 03-parser-layer
plan: "03"
subsystem: parsers
tags: [dispatch, registry, pipeline, aliexpress, privacy, mypy-strict]
dependency_graph:
  requires:
    - phase: 03-02
      provides: AliExpressParser, ALIEXPRESS_SENDER_DOMAINS
    - phase: 02-gmail
      provides: fetch_unread_shipping_emails, RawEmail
  provides:
    - PARSERS module-level registry in main.py
    - _get_all_sender_domains() helper (D-01 single source of truth)
    - first-match-wins dispatch loop collecting list[TrackingInfo]
    - PII-safe no-match and pre-shipment skip paths (PARSE-03, D-05)
  affects:
    - shipping_tracker/main.py
    - tests/test_aliexpress_parser.py
tech_stack:
  added: []
  patterns:
    - module-level PARSERS registry (instances created once, not in loop)
    - first-match-wins dispatch (D-03)
    - parser-derived sender list as single source of truth (D-01)
    - %-style PII-safe logging (message_id and counts only, LOG-02)
key_files:
  created: []
  modified:
    - shipping_tracker/main.py
    - tests/test_aliexpress_parser.py
key_decisions:
  - "D-01: _get_all_sender_domains() replaces os.getenv GMAIL_SENDER_LIST; parser constants are single source of truth for Gmail query"
  - "D-03: first-match-wins dispatch — PARSERS iterated in order; break on first can_parse() match"
  - "D-05: pre-shipment path (extract returns None) logs at DEBUG and skips; no raise"
  - "PARSE-03: no-match path logs at INFO (message_id only) and skips; no raise"
  - "LOG-02: dispatch loop carries only email.message_id and len() counts; body/sender/tracking_number never logged"
patterns_established:
  - "PARSERS: list[BaseParser] = [...] — typed, mutable, module-level; test_registry_drop_in appends to a copy and re-dispatches"
  - "logger.warning for dispatch summary matches gmail.fetch.complete level and %-style key=value format"
requirements_completed: [PARSE-03]
duration: 2min
completed: "2026-06-01"
---

# Phase 03 Plan 03: Parser Dispatch Wiring Summary

**PARSERS registry + first-match-wins dispatch loop wired into main(); parser-owned ALIEXPRESS_SENDER_DOMAINS replaces env-based GMAIL_SENDER_LIST (D-01); full 32-test suite green end-to-end.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-06-01T10:26:50Z
- **Completed:** 2026-06-01T10:28:23Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- Wired `PARSERS: list[BaseParser] = [AliExpressParser()]` as a module-level registry in `main.py`; instances created once at import, not inside the loop (D-03)
- Added `_get_all_sender_domains()` deriving the Gmail sender list from `ALIEXPRESS_SENDER_DOMAINS`; removed the `os.getenv("GMAIL_SENDER_LIST")` read entirely (D-01)
- Inserted first-match-wins dispatch loop: matched+shipped → `TrackingInfo` collected; matched+pre-shipment → `logger.debug` + skip (D-05); no-match → `logger.info` + skip (PARSE-03); neither path raises
- Turned 4 previously-RED dispatch/registry tests green: `test_dispatch_matched_email`, `test_dispatch_no_match_skips`, `test_dispatch_preshipment_skips`, `test_registry_drop_in`
- Full 32-test pytest suite green; mypy --strict 0 errors; ruff passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Add PARSERS registry, parser-derived sender list, and dispatch loop in main()** - `ea9492f` (feat)

**Plan metadata:** (docs commit follows — see final_commit step)

## Files Created/Modified

- `shipping_tracker/main.py` — added imports, PARSERS registry, `_get_all_sender_domains()`, dispatch loop; removed GMAIL_SENDER_LIST env read
- `tests/test_aliexpress_parser.py` — removed 4 now-unused `# type: ignore[attr-defined]` guards on PARSERS import (Rule 1 auto-fix)

## Decisions Made

- D-01 wiring: `_get_all_sender_domains()` returns `list(ALIEXPRESS_SENDER_DOMAINS)` — a new parser adds its domains by extending `PARSERS`, with no changes needed to `main()` beyond the registry append
- dispatch summary log at `logger.warning` to match the existing `gmail.fetch.complete` level/pattern; both are count-only, PII-safe

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed 4 unused `type: ignore[attr-defined]` guards in test file**
- **Found during:** Task 1 first commit attempt (pre-commit mypy hook)
- **Issue:** The `# type: ignore[attr-defined]` annotations on `from shipping_tracker.main import PARSERS` were placed in Plan 02 to silence mypy while `PARSERS` didn't exist yet. Now that `PARSERS` is defined, mypy --strict flags them as `unused-ignore` errors (4 occurrences).
- **Fix:** Removed all four `# type: ignore[attr-defined]` comments from the four dispatch/registry test functions
- **Files modified:** tests/test_aliexpress_parser.py
- **Verification:** mypy --strict: 0 errors; pytest -q: 32/32 passed
- **Committed in:** ea9492f (same task commit)

**2. [Ruff auto-fix] Import ordering in main.py**
- **Found during:** Task 1 first commit attempt (pre-commit ruff-check hook)
- **Issue:** The two new `from shipping_tracker.parsers.*` imports were placed after the `from shipping_tracker.gmail` import; ruff I001 (isort) required alphabetical project-import ordering
- **Fix:** ruff `--fix` reordered to `aliexpress` before `base` and split to two-line import block; applied automatically by the hook
- **Files modified:** shipping_tracker/main.py
- **Verification:** ruff check: Passed; tests still green
- **Committed in:** ea9492f (same task commit)

---

**Total deviations:** 2 auto-fixed (1 Rule 1 bug, 1 ruff auto-fix)
**Impact on plan:** Both fixes necessary for correctness (mypy strict compliance) and style conformance. No scope creep.

## Issues Encountered

None beyond the auto-fixed hook failures above.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

Phase 3 vertical slice is complete end-to-end:
- Gmail fetch → parser dispatch → TrackingInfo collection wired in `main()`
- All 32 tests green including 4 dispatch/registry integration tests
- mypy --strict clean across all modified files
- Phase 4 (deduplication with SQLite) can proceed; it receives `tracking_results: list[TrackingInfo]` from the dispatch loop

---
*Phase: 03-parser-layer*
*Completed: 2026-06-01*

## Known Stubs

None. The dispatch loop collects `tracking_results` but does not yet act on them (Phase 4 wires deduplication + TrackingMore registration). This is the intended Wave 3 deliverable boundary — not a stub, as no data flows to UI or is silently dropped.

## Threat Flags

No new network endpoints, auth paths, or schema changes.

| Threat ID | Mitigation | Status |
|-----------|-----------|--------|
| T-03-08 (DoS — bad email crashes run) | no-match and pre-shipment paths log+skip, never raise; verified by test_dispatch_no_match_skips + test_dispatch_preshipment_skips | Applied |
| T-03-09 (PII in dispatch logs) | All log calls carry only message_id / counts; grep acceptance criterion confirmed; test_extract_does_not_log_pii passes | Applied |
| T-03-10 (sender list drift) | _get_all_sender_domains() derives list from ALIEXPRESS_SENDER_DOMAINS; os.getenv GMAIL_SENDER_LIST read removed | Applied |

## Self-Check: PASSED

| Item | Status |
|------|--------|
| commit ea9492f (Task 1 — main.py + test fix) | FOUND |
| shipping_tracker/main.py PARSERS registry | confirmed |
| shipping_tracker/main.py _get_all_sender_domains() | confirmed |
| os.getenv("GMAIL_SENDER_LIST") read removed | confirmed |
| 4 dispatch/registry tests green | confirmed |
| Full suite: 32/32 passed | confirmed |
| mypy --strict: 0 errors | confirmed |
