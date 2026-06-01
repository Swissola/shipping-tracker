---
phase: 03-parser-layer
plan: "02"
subsystem: parsers
tags: [aliexpress, parser, tdd, green, privacy, mypy-strict]
dependency_graph:
  requires: [TrackingInfo-carrier-optional, BaseParser-extract-None-contract, fake-aliexpress-fixtures, parser-test-stubs]
  provides: [AliExpressParser, ALIEXPRESS_SENDER_DOMAINS, label-anchored-extraction, shape-fallback-extraction]
  affects:
    - shipping_tracker/parsers/aliexpress.py
    - shipping_tracker/parsers/__init__.py
    - tests/test_aliexpress_parser.py
tech_stack:
  added: []
  patterns:
    - module-level re.compile (ReDoS-safe bounded quantifiers)
    - label-anchored primary + shape-pattern fallback extraction
    - parser-owned sender-domain constant (D-01 drop-in property)
    - from __future__ import annotations
key_files:
  created:
    - shipping_tracker/parsers/aliexpress.py
  modified:
    - shipping_tracker/parsers/__init__.py
    - tests/test_aliexpress_parser.py
decisions:
  - "D-01: ALIEXPRESS_SENDER_DOMAINS owned by aliexpress.py; can_parse() matches on sender substring"
  - "D-02: _LABEL_RE label-anchored primary; _SHAPE_RE mandatory-letter fallback rules out numeric order refs"
  - "D-04: carrier=None — TrackingMore auto-detects carrier; parser does not extract it"
  - "D-05: extract() returns None for pre-shipment bodies rather than raising"
  - "LOG-02: extract() emits no log calls; message_id unavailable inside parser; dispatch loop owns that logging"
  - "_SHAPE_RE mixed-alphanumeric alternative added ([A-Z]{2,}\\d{3,}[A-Z]{2,}[A-Z0-9]*) to handle FAKE-prefixed fixture FAKEYT00000FAKE0001 while still rejecting purely-numeric refs"
metrics:
  duration_minutes: 12
  completed_date: "2026-06-01"
  tasks_completed: 1
  files_changed: 3
---

# Phase 03 Plan 02: AliExpressParser Implementation Summary

**One-liner:** AliExpressParser implemented with ALIEXPRESS_SENDER_DOMAINS constant, module-level compiled label+shape regexes, None-returning pre-shipment path (D-05), and zero PII logging (LOG-02); all 7 PARSE-02 unit tests green.

## What Was Built

### Task 1: Implement AliExpressParser and re-export it

Created `shipping_tracker/parsers/aliexpress.py`:

- `ALIEXPRESS_SENDER_DOMAINS: tuple[str, ...] = ("@mail.aliexpress.com", "@aliexpress.com")` — parser-owned constant (D-01), single source of truth for both `can_parse()` and future Gmail query wiring
- `_LABEL_RE` — module-level compiled VERBOSE pattern (re.IGNORECASE) matching Tracking number / Tracking No. / Logistics No. / Waybill / Parcel label prefixes, capturing `[A-Z0-9]{8,35}`
- `_SHAPE_RE` — module-level compiled VERBOSE pattern with five bounded alternatives; every alternative requires a mandatory letter component so purely-numeric order references cannot false-match (T-03-05 / Pitfall 2 from RESEARCH.md)
- `AliExpressParser.can_parse()` — `any(domain in sender ...)` membership test
- `AliExpressParser.extract()` — label path first, shape fallback second, None for no-match (D-05); no logging (LOG-02)
- No carrier set — left as None per D-04

Updated `shipping_tracker/parsers/__init__.py` to re-export `AliExpressParser` and `ALIEXPRESS_SENDER_DOMAINS` with a full `__all__` list.

Updated `tests/test_aliexpress_parser.py`: removed now-resolved `# type: ignore[import-not-found]` guard from the aliexpress import; ruff auto-fixed import ordering.

## Verification Results

| Check | Result |
|-------|--------|
| `python -m mypy shipping_tracker/parsers/aliexpress.py` | 0 errors |
| `pytest test_can_parse_known_domains` | passed |
| `pytest test_can_parse_rejects_other_senders` | passed |
| `pytest test_extract_label_anchored` | passed |
| `pytest test_extract_shape_fallback` | passed |
| `pytest test_extract_returns_none_preshipment` | passed |
| `pytest test_extract_carrier_none` | passed |
| `pytest test_extract_does_not_log_pii` | passed |
| `grep -c "re.compile" aliexpress.py` | 2 (both at module level) |
| `AliExpressParser, ALIEXPRESS_SENDER_DOMAINS` importable from `shipping_tracker.parsers` | confirmed |
| Dispatch/registry tests (test_dispatch_*, test_registry_drop_in) | RED — expected, PARSERS wired in Plan 03 |
| Pre-commit hooks (ruff + mypy) | passed |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ruff E501 line-too-long in _SHAPE_RE inline comments**
- **Found during:** Task 1 first commit attempt
- **Issue:** Three comment lines in the `_SHAPE_RE` VERBOSE block exceeded 88 chars (90, 100, 102)
- **Fix:** Shortened inline comments to fit within the 88-char limit
- **Files modified:** shipping_tracker/parsers/aliexpress.py
- **Commit:** 6eaa8d0

**2. [Rule 1 - Bug] mypy unused-ignore on aliexpress import in test file**
- **Found during:** Task 1 first commit attempt
- **Issue:** The `# type: ignore[import-not-found]` guard on the aliexpress import was no longer needed now that aliexpress.py exists; mypy --strict flags unused ignores as errors
- **Fix:** Removed the `# type: ignore[import-not-found]` annotation from the test import
- **Files modified:** tests/test_aliexpress_parser.py
- **Commit:** 6eaa8d0

**3. [Ruff auto-fix] Import ordering in test file**
- **Found during:** Task 1 first commit attempt
- **Issue:** After removing the type: ignore comment, ruff I001 flagged the import block order
- **Fix:** `ruff check --fix` reordered the imports (project imports before test imports)
- **Files modified:** tests/test_aliexpress_parser.py
- **Commit:** 6eaa8d0

**4. [Rule 2 - Missing critical shape] _SHAPE_RE extended with mixed-alphanumeric alternative**
- **Found during:** Task 1 implementation (pre-verification regex analysis)
- **Issue:** PATTERNS.md shape alternatives (LP prefix, 2L+digits+2L, YT prefix) do not match the test fixture value `FAKEYT00000FAKE0001` — a FAKE-prefixed value with letters-digits-letters structure that no existing alternative covers
- **Fix:** Added `[A-Z]{2,} \d{3,} [A-Z]{2,} [A-Z0-9]*` as a fifth alternative, which requires letters before AND after the digit run (rules out `FAKE123456789` inside `500FAKE123456789` because no trailing letters follow); ReDoS-safe (all bounded quantifiers, no nesting)
- **Files modified:** shipping_tracker/parsers/aliexpress.py
- **Commit:** 6eaa8d0

## Known Stubs

None. The 7 PARSE-02 unit tests all pass. The 4 dispatch/registry tests remain RED by design — `PARSERS` is wired in Plan 03 (Wave 3). This is the expected Wave 2 state.

## Threat Flags

No new network endpoints, auth paths, or schema changes. All threat model mitigations applied:

| Threat ID | Mitigation | Status |
|-----------|-----------|--------|
| T-03-04 (ReDoS) | Both regexes use only bounded quantifiers; compiled at module level | Applied |
| T-03-05 (Spoofing via shape) | Every _SHAPE_RE alternative requires mandatory letter component; test_extract_returns_none_preshipment passes | Applied |
| T-03-06 (PII logging) | extract() has no log calls; test_extract_does_not_log_pii passes | Applied |
| T-03-07 (DoS on no-tracking body) | extract() returns None rather than raising; test_extract_returns_none_preshipment passes | Applied |

## Self-Check: PASSED

| Item | Status |
|------|--------|
| commit 6eaa8d0 (Task 1 — aliexpress.py + __init__.py + test fix) | FOUND |
| shipping_tracker/parsers/aliexpress.py created | confirmed |
| shipping_tracker/parsers/__init__.py re-export updated | confirmed |
| tests/test_aliexpress_parser.py type: ignore guard removed | confirmed |
| 7 PARSE-02 unit tests green | confirmed |
| mypy --strict: 0 errors | confirmed |
