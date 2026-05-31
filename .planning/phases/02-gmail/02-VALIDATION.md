---
phase: 02
slug: gmail
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-31
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `02-RESEARCH.md` §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/test_gmail_auth.py tests/test_gmail_query.py tests/test_gmail_client.py -x` |
| **Full suite command** | `pytest` |
| **Estimated runtime** | ~3 seconds (all mocked — no network) |

---

## Sampling Rate

- **After every task commit:** Run the quick command above
- **After every plan wave:** Run `pytest` (full suite)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~3 seconds

---

## Per-Task Verification Map

> Task IDs are assigned by the planner; rows below are the requirement-level
> verification contract every task must satisfy. `❌ W0` = test/source file is a
> Wave 0 dependency that does not yet exist.

| Behavior | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|----------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| `load_credentials()` refreshes an expired token non-interactively | GMAIL-01, GMAIL-03 | T-02-token | Token refresh via `Request()`; never re-prompts on the Pi | unit | `pytest tests/test_gmail_auth.py -x` | ❌ W0 | ⬜ pending |
| `load_credentials()` runs `run_local_server()` only when no refresh token | GMAIL-01 | T-02-scope | Uses fixed `gmail.readonly` SCOPES constant | unit | `pytest tests/test_gmail_auth.py -x` | ❌ W0 | ⬜ pending |
| `token.json` written after refresh, mode 600 | GMAIL-03 | T-02-token | Token never logged; file git-ignored | unit | `pytest tests/test_gmail_auth.py -x` | ❌ W0 | ⬜ pending |
| `build_query()` builds correct `q` for single + multiple senders + window | GMAIL-02 | T-02-input | Sender list / window validated before query build | unit | `pytest tests/test_gmail_query.py -x` | ❌ W0 | ⬜ pending |
| `fetch_unread_shipping_emails()` returns `RawEmail` list from mocked service | GMAIL-02 | — | readonly fetch; `labelIds=["INBOX"]` | unit | `pytest tests/test_gmail_client.py -x` | ❌ W0 | ⬜ pending |
| Fetch follows pagination across multiple pages | GMAIL-02 | — | — | unit | `pytest tests/test_gmail_client.py -x` | ❌ W0 | ⬜ pending |
| Fetch returns `[]` when no messages match | GMAIL-02 | — | — | unit | `pytest tests/test_gmail_client.py -x` | ❌ W0 | ⬜ pending |
| `_decode_base64url()` handles missing padding | GMAIL-02 | — | — | unit | `pytest tests/test_gmail_client.py -x` | ❌ W0 | ⬜ pending |
| No `sender`/`subject`/`body` content appears in logs during a fetch | LOG-02 | T-02-logpii | PII never logged (structlog field discipline) | unit | `pytest tests/test_gmail_client.py -x` (capture logs, assert no PII) | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Test + source files that must exist before behavioral tasks can be sampled:

- [ ] `tests/fixtures/fake_gmail_message.py` — synthetic Gmail message fixture (FAKE data only, no real PII)
- [ ] `tests/conftest.py` — extend with mocked Gmail service fixture (`MagicMock` on chained `users().messages()...` calls)
- [ ] `tests/test_gmail_auth.py` — GMAIL-01 + GMAIL-03 (credential load/refresh/persist)
- [ ] `tests/test_gmail_query.py` — GMAIL-02 query construction
- [ ] `tests/test_gmail_client.py` — GMAIL-02 fetch loop, pagination, base64url decode, LOG-02 PII-safety
- [ ] `shipping_tracker/gmail/__init__.py`
- [ ] `shipping_tracker/gmail/auth.py`
- [ ] `shipping_tracker/gmail/client.py`
- [ ] `shipping_tracker/gmail/query.py`
- [ ] `google-api-python-client-stubs>=1.37` added to the dev dependency group (mypy --strict typing for the Gmail service)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| First-run OAuth browser consent on the laptop produces a valid `token.json` | GMAIL-01, GMAIL-03 | Requires interactive Google consent screen + real browser — cannot run in CI without real credentials/PII | On a dev machine with real `credentials.json`: run the auth flow once, complete consent in the browser, confirm `token.json` is created; copy to the Pi and confirm a subsequent run does NOT open a browser. (Document in README — Phase 6.) |
| Consent screen published to "Production" in GCP (avoids 7-day token expiry) | GMAIL-03 | GCP Console operation, external to the codebase | Verify the OAuth consent screen is not in "Testing" status before relying on the Pi long-term. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
