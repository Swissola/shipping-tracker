---
phase: 05
slug: pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-02
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0+ |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/test_registrar.py -x -q` |
| **Full suite command** | `pytest -x -q` |
| **Estimated runtime** | ~5 seconds (in-process; respx mock transport, no network) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_registrar.py -x -q`
- **After every plan wave:** Run `pytest -x -q`
- **Before `/gsd-verify-work`:** `pytest -x -q && mypy --strict shipping_tracker/ && ruff check .` all green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

> Task IDs are assigned by the planner; rows below are keyed by requirement + behavior from
> RESEARCH.md "Phase Requirements → Test Map". The planner must bind each row to a concrete task.

| Req | Behavior | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|-----|----------|------------|-----------------|-----------|-------------------|-------------|--------|
| TRACK-01 | POST /v4/trackings/create sent with correct URL + headers | — | N/A | unit | `pytest tests/test_registrar.py::test_create_sends_correct_request -x` | ❌ W0 | ⬜ pending |
| TRACK-01 | Successful 200 → both DB rows written | — | N/A | integration | `pytest tests/test_registrar.py::test_success_creates_tracking -x` | ❌ W0 | ⬜ pending |
| TRACK-02 | `Tracking-Api-Key` header populated from env var | API key exposure | Key read from env only; never logged | unit | `pytest tests/test_registrar.py::test_api_key_in_header -x` | ❌ W0 | ⬜ pending |
| TRACK-02 | Missing/empty `TRACKINGMORE_API_KEY` → main() returns 1, no Gmail/DB work | API key exposure | Fail-closed before any work | integration | `pytest tests/test_registrar.py::test_missing_api_key_exits_1 -x` | ❌ W0 | ⬜ pending |
| TRACK-03 | 4016 already-exists → True + both rows written | — | N/A | unit | `pytest tests/test_registrar.py::test_already_exists_treated_as_success -x` | ❌ W0 | ⬜ pending |
| TRACK-04 | 429 rate-limit → QuotaExceededError raised | — | N/A | unit | `pytest tests/test_registrar.py::test_rate_limit_raises_quota_error -x` | ❌ W0 | ⬜ pending |
| TRACK-04 | 4021 quota → QuotaExceededError raised | — | N/A | unit | `pytest tests/test_registrar.py::test_quota_exhausted_raises_quota_error -x` | ❌ W0 | ⬜ pending |
| TRACK-04 | QuotaExceededError → dispatch loop breaks; remaining numbers unwritten | — | N/A | integration | `pytest tests/test_registrar.py::test_quota_error_breaks_dispatch_loop -x` | ❌ W0 | ⬜ pending |
| TRACK-04 | 5xx transient → one retry, then return False; number not in DB | — | N/A | unit | `pytest tests/test_registrar.py::test_5xx_retries_once_then_defers -x` | ❌ W0 | ⬜ pending |
| TRACK-04 | TimeoutException → one retry, then return False; number not in DB | — | N/A | unit | `pytest tests/test_registrar.py::test_timeout_retries_once_then_defers -x` | ❌ W0 | ⬜ pending |
| TRACK-05 | carrier=None → courier_code omitted from request body | — | N/A | unit | `pytest tests/test_registrar.py::test_no_courier_code_when_carrier_none -x` | ❌ W0 | ⬜ pending |
| TRACK-05 | carrier="aliexpress" → courier_code present in request body | — | N/A | unit | `pytest tests/test_registrar.py::test_courier_code_included_when_carrier_set -x` | ❌ W0 | ⬜ pending |
| LOG-02 | tracking_number never appears in registrar log output | Tracking number in logs | Log lines use message_id only | unit | `pytest tests/test_registrar.py::test_tracking_number_never_logged -x` | ❌ W0 | ⬜ pending |
| D-05 | API key value never logged, even on error | API key in exception messages | Structural exception messages only | unit | `pytest tests/test_registrar.py::test_api_key_never_logged -x` | ❌ W0 | ⬜ pending |
| D-06 | QuotaExceededError caught before broad `except Exception` | — | N/A | unit | `pytest tests/test_registrar.py::test_quota_error_ordering -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_registrar.py` — new file; covers all TRACK-0x requirements above
- [ ] `tests/conftest.py` — add `mock_router` fixture (respx.MockRouter) + synthetic TrackingMore response builders
- [ ] `respx>=0.23` in `pyproject.toml [project.optional-dependencies] dev`
- [ ] `shipping_tracker/registrar.py` — add `QuotaExceededError` and `TrackingMoreRegistrar` (extends existing Registrar Protocol seam from Phase 4)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live end-to-end run registers a real number with TrackingMore | TRACK-01 | Requires a real `TRACKINGMORE_API_KEY` + populated `.env`; cannot run in CI without exposing PII/credentials | Run the tool against a dev `.env` with one synthetic-but-real tracking number; confirm a tracking is created in the TrackingMore dashboard and `registered_tracking` has the row |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
