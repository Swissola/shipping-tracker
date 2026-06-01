---
phase: 4
slug: deduplication
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-01
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `04-RESEARCH.md` §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (exists) |
| **Quick run command** | `python -m pytest tests/test_db.py -q` |
| **Full suite command** | `python -m pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds (in-memory sqlite3, no I/O) |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_db.py -q`
- **After every plan wave:** Run `python -m pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists | Status |
|--------|----------|-----------|-------------------|-------------|--------|
| DEDUP-01 | `processed_emails` table created if absent | unit | `pytest tests/test_db.py::test_init_db_creates_processed_emails -x` | ❌ W0 | ⬜ pending |
| DEDUP-01 | `init_db` is idempotent (safe to call twice) | unit | `pytest tests/test_db.py::test_init_db_idempotent -x` | ❌ W0 | ⬜ pending |
| DEDUP-02 | `registered_tracking` table created with nullable `last_status*` | unit | `pytest tests/test_db.py::test_init_db_creates_registered_tracking -x` | ❌ W0 | ⬜ pending |
| DEDUP-02 | `PRAGMA user_version = 1` set after init | unit | `pytest tests/test_db.py::test_user_version -x` | ❌ W0 | ⬜ pending |
| DEDUP-03 | `is_email_processed` returns True for known id | unit | `pytest tests/test_db.py::test_is_email_processed_known -x` | ❌ W0 | ⬜ pending |
| DEDUP-03 | `is_email_processed` returns False for unknown id | unit | `pytest tests/test_db.py::test_is_email_processed_unknown -x` | ❌ W0 | ⬜ pending |
| DEDUP-03 | Dispatch loop skips entire email when already processed | integration | `pytest tests/test_db.py::test_dispatch_skips_processed_email -x` | ❌ W0 | ⬜ pending |
| DEDUP-04 | `is_tracking_registered` returns True/False correctly | unit | `pytest tests/test_db.py::test_is_tracking_registered -x` | ❌ W0 | ⬜ pending |
| DEDUP-04 | Dispatch loop skips API when tracking already registered | integration | `pytest tests/test_db.py::test_dispatch_skips_registered_tracking -x` | ❌ W0 | ⬜ pending |
| D-03 | Duplicate-notification email is marked processed (DEDUP-04 branch) | integration | `pytest tests/test_db.py::test_dup_notification_marks_email_processed -x` | ❌ W0 | ⬜ pending |
| DEDUP-05 | `register_and_persist` writes both rows on success | unit | `pytest tests/test_db.py::test_register_and_persist_success -x` | ❌ W0 | ⬜ pending |
| DEDUP-05 | writes neither row on registrar `False` | unit | `pytest tests/test_db.py::test_register_and_persist_fail_returns_false -x` | ❌ W0 | ⬜ pending |
| DEDUP-05 | writes neither row on registrar exception (rollback) | unit | `pytest tests/test_db.py::test_register_and_persist_raises_rolls_back -x` | ❌ W0 | ⬜ pending |
| DEDUP-05 | **Retry proof**: fail → no row → success on second run | integration | `pytest tests/test_db.py::test_retry_proof -x` | ❌ W0 | ⬜ pending |
| D-09 | NullRegistrar returns False, logs at debug, no PII | unit | `pytest tests/test_db.py::test_null_registrar_defers -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Retry Proof Test Design (Success Criterion 4)

The most important test in the suite. It must prove: inject a fake *failing* registrar
→ assert `registered_tracking` row absent → assert the same tracking number is attempted
again on a second simulated run → assert row present after the second run succeeds. The
atomicity of `with conn:` is what makes the retry safe — no compensating transaction, no
state flag. (Full outline in `04-RESEARCH.md` §Retry Proof Test Design.)

---

## Wave 0 Requirements

- [ ] `tests/test_db.py` — all 15 test functions above (covers DEDUP-01..05, D-03, D-09)
- [ ] `tests/fixtures/fake_db.py` — `FAKE`-prefixed tracking numbers + message IDs; privacy
      docstring matching the existing `fake_aliexpress_email.py` pattern
- [ ] `conftest.py` — add an in-memory `sqlite3.Connection` fixture with `init_db` already
      called (reusable across all `test_db.py` tests)

*Existing infrastructure — pytest 9.0.3, `conftest.py`, `tests/fixtures/` — covers the project
baseline. Wave 0 creates only the new test files above; `shipping_tracker/db.py` and
`shipping_tracker/registrar.py` are Wave 1 source modules.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live `NullRegistrar` cron run creates tables + persists nothing | D-09 | Requires a real Gmail/.env environment; the dedup + retry logic itself is fully covered by automated in-memory tests | Run the tool once against a dev `.env`; confirm `data/shipping-tracker.db` is created with both tables and `registered_tracking` stays empty (NullRegistrar defers) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
