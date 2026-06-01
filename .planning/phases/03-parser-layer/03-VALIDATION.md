---
phase: 3
slug: parser-layer
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-01
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `03-RESEARCH.md` §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (installed) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/test_aliexpress_parser.py tests/test_smoke.py -x -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_aliexpress_parser.py tests/test_smoke.py -x -q`
- **After every plan wave:** Run `pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green (zero failures)
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists | Status |
|--------|----------|-----------|-------------------|-------------|--------|
| PARSE-01 | `BaseParser` ABC enforces `can_parse`/`extract` contract | unit (smoke) | `pytest tests/test_smoke.py::test_base_parser_is_abstract -x` | ✅ existing | ⬜ pending |
| PARSE-01 | `TrackingInfo` constructs with optional carrier (D-04) | unit | `pytest tests/test_smoke.py::test_tracking_info_dataclass -x` | ⚠️ needs update | ⬜ pending |
| PARSE-01 | `TrackingInfo(tracking_number=...)` works with carrier omitted | unit | `pytest tests/test_aliexpress_parser.py::test_tracking_info_carrier_optional -x` | ❌ W0 | ⬜ pending |
| PARSE-02 | `can_parse()` True for known AliExpress sender domains | unit | `pytest tests/test_aliexpress_parser.py::test_can_parse_known_domains -x` | ❌ W0 | ⬜ pending |
| PARSE-02 | `can_parse()` False for non-AliExpress sender | unit | `pytest tests/test_aliexpress_parser.py::test_can_parse_rejects_other_senders -x` | ❌ W0 | ⬜ pending |
| PARSE-02 | `extract()` returns correct number for label-anchored body | unit | `pytest tests/test_aliexpress_parser.py::test_extract_label_anchored -x` | ❌ W0 | ⬜ pending |
| PARSE-02 | `extract()` returns number via fallback shape (no label) | unit | `pytest tests/test_aliexpress_parser.py::test_extract_shape_fallback -x` | ❌ W0 | ⬜ pending |
| PARSE-02 | `extract()` returns `None` for pre-shipment body | unit | `pytest tests/test_aliexpress_parser.py::test_extract_returns_none_preshipment -x` | ❌ W0 | ⬜ pending |
| PARSE-02 | Carrier is `None` when email names no courier | unit | `pytest tests/test_aliexpress_parser.py::test_extract_carrier_none -x` | ❌ W0 | ⬜ pending |
| PARSE-02 | LOG-02: parser never logs body, sender, or tracking number | unit | `pytest tests/test_aliexpress_parser.py::test_extract_does_not_log_pii -x` | ❌ W0 | ⬜ pending |
| PARSE-03 | Dispatch: matched email with tracking yields `TrackingInfo` | integration | `pytest tests/test_aliexpress_parser.py::test_dispatch_matched_email -x` | ❌ W0 | ⬜ pending |
| PARSE-03 | Dispatch: no-match email logs and does not raise | integration | `pytest tests/test_aliexpress_parser.py::test_dispatch_no_match_skips -x` | ❌ W0 | ⬜ pending |
| PARSE-03 | Dispatch: pre-shipment email logs debug and does not raise | integration | `pytest tests/test_aliexpress_parser.py::test_dispatch_preshipment_skips -x` | ❌ W0 | ⬜ pending |
| PARSE-03 | Registry drop-in: appending a 2nd fake parser makes it discoverable | unit | `pytest tests/test_aliexpress_parser.py::test_registry_drop_in -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/fixtures/fake_aliexpress_email.py` — synthetic FAKE-prefixed body variants covering: label-anchored shipped email, no-label shipped email (shape fallback), pre-shipment "order confirmed" email, courier-named email, non-AliExpress sender
- [ ] `tests/test_aliexpress_parser.py` — the 13 new test functions listed above
- [ ] Update `tests/test_smoke.py::test_tracking_info_dataclass` to also assert the `carrier=None` default after D-04

*Existing pytest infrastructure is fully adequate — no framework install needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real AliExpress sender domain + label strings match the parser constants | PARSE-02 | Synthetic fixtures mirror but cannot prove the real email format | Before `/gsd-verify-work`, spot-check one real "your order has shipped" AliExpress email; confirm sender domain and tracking-label wording match the parser constants. One-line constant fix if different. |

*All other phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (fixtures + test module)
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
