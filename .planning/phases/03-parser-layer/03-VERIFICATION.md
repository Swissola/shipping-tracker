---
phase: 03-parser-layer
verified: 2026-06-01T00:00:00Z
status: passed
score: 9/9 must-haves verified
overrides_applied: 0
---

# Phase 3: Parser Layer Verification Report

**Phase Goal:** AliExpress shipping notification emails are parsed to extract
tracking number and carrier via a pluggable BaseParser architecture that makes
adding future parsers a drop-in operation.
**Verified:** 2026-06-01T00:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A synthetic AliExpress fixture email passed through `AliExpressParser` returns a correct `TrackingInfo` with tracking number and carrier | VERIFIED | `test_extract_label_anchored` passes: `FAKE_ALIEXPRESS_SHIPPED_BODY` yields `TrackingInfo(tracking_number="FAKELP00FAKE00001")`; `test_extract_carrier_none` confirms `carrier is None` (D-04 best-effort — TrackingMore auto-detects) |
| 2 | An email that matches no parser is logged and skipped without raising an exception | VERIFIED | `test_dispatch_no_match_skips` passes; `main.py:88` logs `parser.no_match id=%s` at INFO and does not raise; pre-shipment path (`extract -> None`) uses `logger.debug` and does not raise (D-05); WR-04 per-email `try/except` in dispatch loop isolates any future raise |
| 3 | `BaseParser` enforces the `can_parse`/`extract` interface so a third-party parser can be registered by appending to PARSERS with no other changes, including to the Gmail sender query | VERIFIED | CR-02 fix confirmed in code and tests: `base.py` declares `sender_domains: tuple[str, ...] = ()`; `AliExpressParser.sender_domains = ALIEXPRESS_SENDER_DOMAINS`; `_get_all_sender_domains()` iterates `PARSERS` aggregating each parser's declared domains; `test_get_all_sender_domains_aggregates_across_parsers` asserts a second parser's domain appears in the Gmail query; `test_registry_drop_in` asserts the second parser is found by `can_parse` dispatch; `ALIEXPRESS_SENDER_DOMAINS` is NOT imported in `main.py` (import removed in e839166) — only `AliExpressParser` is |
| 4 | TrackingInfo.carrier is `str | None = None` (D-04) | VERIFIED | `base.py:14` — `carrier: str | None = None`; `test_tracking_info_carrier_optional` and `test_tracking_info_dataclass` both pass |
| 5 | BaseParser.extract() returns `TrackingInfo | None`, not raises ValueError (D-05) | VERIFIED | `base.py:46` — `def extract(self, email_body: str) -> TrackingInfo | None`; docstring says "Returns None when no tracking number"; `test_extract_returns_none_preshipment` passes |
| 6 | Log output from the dispatch layer is PII-safe (LOG-02) — no body, sender, or tracking number text | VERIFIED | All `logger.*` calls in `main.py` carry only `email.message_id` or `len()` counts; `test_main_dispatch_loop_logs_pii_safely_on_error` asserts the error log record carries `FAKEMSGID_PII` but not `SECRETBODY` or `FAKELP00FAKE00001`; extract() emits no log calls |
| 7 | PARSE-01: BaseParser ABC enforces can_parse/extract contract | VERIFIED | `base.py:17-57` is an ABC with `@abstractmethod` decorators on both methods; `test_base_parser_is_abstract` confirms instantiation raises `TypeError` |
| 8 | PARSE-02: AliExpressParser extracts correctly via label-anchored primary and shape-pattern fallback | VERIFIED | `test_extract_label_anchored`, `test_extract_shape_fallback`, `test_extract_shape_still_matches_real_shape` all pass; CR-01 fix adds `(?![A-Z0-9])` boundary so over-length tokens are not silently truncated (`test_extract_overlength_token_not_truncated`); WR-02 fix normalises to upper-case (`test_extract_normalises_lowercase_to_upper`) |
| 9 | PARSE-03: Parser registry uses first-match-wins dispatch; unmatched emails logged and skipped without error | VERIFIED | `main.py:18-20` — `PARSERS: list[BaseParser] = [AliExpressParser()]`; dispatch loop breaks on first match; all four dispatch/registry tests pass |

**Score:** 9/9 truths verified

---

### Locked Decision Compliance (D-01..D-05 from 03-CONTEXT.md)

| Decision | Claim | Code Evidence | Status |
|----------|-------|---------------|--------|
| D-01 | Parser owns its sender domains; same list drives can_parse AND Gmail query | `AliExpressParser.sender_domains = ALIEXPRESS_SENDER_DOMAINS`; `_get_all_sender_domains()` iterates `PARSERS`; `main.py` does not import `ALIEXPRESS_SENDER_DOMAINS` directly | VERIFIED |
| D-02 | Label-anchored primary + constrained shape-pattern fallback | `_LABEL_RE` and `_SHAPE_RE` compiled at module level in `aliexpress.py`; both regexes use only bounded quantifiers (ReDoS-safe); WR-01 length-gated last alternative; CR-01 trailing boundary | VERIFIED |
| D-03 | First match wins; `extract()` returns single TrackingInfo | `break` in dispatch loop after first `can_parse` match; `extract()` returns `TrackingInfo | None` not a list | VERIFIED |
| D-04 | `TrackingInfo.carrier` is `str | None = None` | `base.py:14`; carrier never set in `extract()` — always defaults to None | VERIFIED |
| D-05 | `extract()` returns None for pre-shipment; non-fatal; logged at debug | `aliexpress.py:101` — `return None`; `main.py:82-83` — `logger.debug("parser.no_tracking id=%s", email.message_id)` | VERIFIED |

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `shipping_tracker/parsers/base.py` | TrackingInfo with `carrier: str | None = None`; `extract() -> TrackingInfo | None`; `sender_domains: tuple[str, ...] = ()` on BaseParser | VERIFIED | All three present; 58 lines; mypy clean |
| `shipping_tracker/parsers/aliexpress.py` | AliExpressParser + ALIEXPRESS_SENDER_DOMAINS + compiled `_LABEL_RE`/`_SHAPE_RE` | VERIFIED | 103 lines; `sender_domains = ALIEXPRESS_SENDER_DOMAINS` class attribute; 2 module-level `re.compile` calls; mypy clean |
| `shipping_tracker/parsers/__init__.py` | Re-export of AliExpressParser, ALIEXPRESS_SENDER_DOMAINS, BaseParser, TrackingInfo | VERIFIED | Full `__all__` list present; all four names exported |
| `shipping_tracker/main.py` | PARSERS registry + `_get_all_sender_domains()` + dispatch loop | VERIFIED | `PARSERS: list[BaseParser] = [AliExpressParser()]`; `_get_all_sender_domains()` iterates PARSERS; no `GMAIL_SENDER_LIST` env read; 102 lines; mypy clean |
| `tests/fixtures/fake_aliexpress_email.py` | FAKE-prefixed synthetic fixtures; PRIVACY docstring; no real domains | VERIFIED | 7 constants; PRIVACY docstring present; all values FAKE-prefixed or `.example.com`; no real `aliexpress.com` in fixture values |
| `tests/test_aliexpress_parser.py` | 12 original + 8 post-review tests = 20 test functions covering PARSE-01/02/03 + CR/WR fixes | VERIFIED | 20 test functions collected and passing; includes `test_get_all_sender_domains_aggregates_across_parsers` and `test_dispatch_isolates_raising_parser` |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `main.py` | `AliExpressParser` | `from shipping_tracker.parsers.aliexpress import AliExpressParser` | WIRED | Import present; PARSERS list instantiates it |
| `main.py` | `_get_all_sender_domains()` | Called at `main.py:57` as `senders = _get_all_sender_domains()` | WIRED | Function defined at :23; called at :57 before `fetch_unread_shipping_emails` |
| `main.py` | `PARSERS` | Iterated in dispatch loop at `main.py:77` | WIRED | `for parser in PARSERS` at line 77 |
| `aliexpress.py` | `BaseParser, TrackingInfo` | `from shipping_tracker.parsers.base import BaseParser, TrackingInfo` | WIRED | Line 8 in aliexpress.py |
| `aliexpress.py` | `ALIEXPRESS_SENDER_DOMAINS` | `sender_domains = ALIEXPRESS_SENDER_DOMAINS` on `AliExpressParser` class | WIRED | Line 73; CR-02 fix |
| `test_aliexpress_parser.py` | `fake_aliexpress_email.py` | `from tests.fixtures.fake_aliexpress_email import ...` | WIRED | Lines 15-20; FAKE_ALIEXPRESS_SHIPPED_BODY, NOLABEL_BODY, PRESHIPMENT_BODY, FAKE_OTHER_SENDER imported |
| `test_aliexpress_parser.py` | `main.PARSERS` | `from shipping_tracker.main import PARSERS` inside test functions | WIRED | 4 dispatch/registry tests import PARSERS directly; no `type: ignore` guards remain |

---

### Data-Flow Trace (Level 4)

The dispatch loop in `main()` collects `tracking_results: list[TrackingInfo]` but intentionally does not act on them yet (Phase 4 wires deduplication + TrackingMore registration). This is the correct Wave 3 boundary, not a stub — the data is accumulated and the flow is complete for this phase's scope.

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `main.py` dispatch loop | `tracking_results` | `parser.extract(email.body)` for each matched email | Data flows from `_LABEL_RE`/`_SHAPE_RE` matching against real email bodies | FLOWING (within phase scope) |
| `AliExpressParser.extract()` | `tracking_number` | `_LABEL_RE.search` → `m.group(1).upper()` or `_SHAPE_RE.search` → `m2.group(0).upper()` | Regex against input `email_body`; no hardcoded return; returns `None` only when genuinely no match | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite green | `python -m pytest -q` | 42 passed in 0.69s | PASS |
| mypy --strict clean | `python -m mypy shipping_tracker` | Success: no issues found in 11 source files | PASS |
| ruff clean | `python -m ruff check shipping_tracker tests` | All checks passed! | PASS |
| SC1: AliExpress fixture → correct TrackingInfo | `pytest test_extract_label_anchored -v` | PASSED — tracking_number == "FAKELP00FAKE00001" | PASS |
| SC2: No-match email logged and skipped without raise | `pytest test_dispatch_no_match_skips -v` | PASSED | PASS |
| SC3: Drop-in parser extends BOTH can_parse dispatch AND Gmail sender query | `pytest test_registry_drop_in test_get_all_sender_domains_aggregates_across_parsers -v` | Both PASSED | PASS |
| CR-02 fix: `_get_all_sender_domains()` iterates PARSERS | Code inspection: `main.py:34-38` | `for parser in PARSERS: for domain in parser.sender_domains:` — iterates all parsers, no hardcoded import | PASS |
| CR-02 fix: ALIEXPRESS_SENDER_DOMAINS NOT imported in main.py | Grep for `ALIEXPRESS_SENDER_DOMAINS` in main.py | No matches — import was removed in e839166 | PASS |
| PII safety: dispatch logs carry only message_id | `pytest test_main_dispatch_loop_logs_pii_safely_on_error -v` | PASSED | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| PARSE-01 | 03-01-PLAN.md | BaseParser ABC with can_parse/extract interface | SATISFIED | ABC enforced by `@abstractmethod`; `test_base_parser_is_abstract` passes; `TrackingInfo` dataclass with optional carrier |
| PARSE-02 | 03-02-PLAN.md | AliExpressParser extracts tracking number; carrier best-effort | SATISFIED | All 7 unit tests pass; label-anchored + shape-fallback; carrier=None; CR-01/WR-01/WR-02 fixes improve correctness |
| PARSE-03 | 03-03-PLAN.md | Parser list; first match wins; unknown emails skipped without error | SATISFIED | `PARSERS` list in main.py; dispatch loop with break; 4 integration tests pass; no-match logged at INFO; pre-shipment at DEBUG |

All three phase requirements are satisfied. No orphaned requirements found — the traceability table in REQUIREMENTS.md marks PARSE-01/02/03 as Complete.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tests/test_aliexpress_parser.py` | 88, 125, 280 | `sender="shipping@mail.aliexpress.com"` inline in dispatch tests | Info | Real service domain name used as test input value (not a fixture constant). This is the domain string the parser is actually matching against — using a real domain here is intentional and necessary to test correct dispatch. Not PII (no personal information). The fixture file correctly uses `.example.com`; these inline values are functional inputs to `can_parse()`. |

No TBD, FIXME, or XXX markers found in any Phase 3 source files.

No TODO markers found in Phase 3 modified source files (`base.py`, `aliexpress.py`, `main.py`).

No stub patterns found (empty returns, placeholder renders, or disconnected data flows).

---

### Human Verification Required

None. All phase goal criteria are verifiable programmatically and all checks pass.

The one manual-only verification noted in 03-VALIDATION.md — "spot-check one real AliExpress shipped email to confirm sender domain and tracking-label wording match parser constants" — is an ongoing operational check, not a phase gate. The phase uses synthetic fixtures that mirror the real email structure.

---

### Gaps Summary

No gaps. All 9 must-have truths verified, all artifacts substantive and wired, all key links confirmed, all 3 requirements satisfied.

**CR-02 fix confirmed:** The originally broken `_get_all_sender_domains()` that hardcoded `list(ALIEXPRESS_SENDER_DOMAINS)` was replaced in commit e839166. The current code iterates `PARSERS` and aggregates `parser.sender_domains` across all registered parsers. `ALIEXPRESS_SENDER_DOMAINS` is not imported in `main.py`. Appending a new parser to `PARSERS` now automatically extends both the `can_parse` dispatch path and the Gmail sender query with no other changes to `main.py`. This is confirmed by `test_get_all_sender_domains_aggregates_across_parsers`.

---

_Verified: 2026-06-01T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
