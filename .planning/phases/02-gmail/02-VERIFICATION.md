---
phase: 02-gmail
verified: 2026-05-31T00:00:00Z
status: human_needed
score: 8/9 must-haves verified
overrides_applied: 0
human_verification:
  - test: "First-run OAuth browser consent on the laptop produces a valid token.json"
    expected: "Browser opens once, consent is granted, token.json is written. Subsequent runs (including Pi) do not open a browser."
    why_human: "Requires interactive Google consent screen and real credentials — cannot run in CI without real OAuth/PII. Documented in 02-VALIDATION.md as Manual-Only."
  - test: "GCP consent screen published to Production (avoids 7-day token expiry)"
    expected: "OAuth consent screen status is Production, not Testing, in Google Cloud Console."
    why_human: "GCP Console operation, external to codebase. Required for long-lived Pi deployment."
---

# Phase 02: Gmail Verification Report

**Phase Goal:** The tool authenticates to Gmail via OAuth2 and retrieves unread emails matching shipping sender patterns, producing a list of raw email objects for downstream processing.
**Verified:** 2026-05-31
**Status:** HUMAN_NEEDED (all automated checks pass; 2 manual-only items per VALIDATION.md remain)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | load_credentials() refreshes an expired token via Request() without opening a browser (Pi path) | VERIFIED | `test_load_credentials_refreshes_expired_token` passes; `mock_creds.refresh.assert_called_once()` confirmed |
| 2 | load_credentials() calls run_local_server(port=0) only when no valid token/refresh token exists (laptop path) | VERIFIED | `test_load_credentials_laptop_path_when_no_token` passes; `mock_flow.run_local_server.assert_called_once_with(port=0)` and `mock_new_creds.refresh.assert_not_called()` confirmed |
| 3 | token.json is written back after a refresh so the cached token persists across runs | VERIFIED | `test_load_credentials_writes_token_after_refresh` passes; `mock_creds.to_json.assert_called_once()` and file content check confirmed |
| 4 | The OAuth scope is hard-coded to gmail.readonly and never read from config | VERIFIED | `SCOPES: list[str] = ["https://www.googleapis.com/auth/gmail.readonly"]` in auth.py line 14; no os.getenv for scope anywhere in gmail package |
| 5 | build_query() produces is:unread from:(...) newer_than:Nd for single and multiple senders | VERIFIED | `build_query(["@aliexpress.com"], 30) == "is:unread from:(@aliexpress.com) newer_than:30d"` — exact match; empty-senders returns `"is:unread newer_than:30d"` (no malformed `from:()`) |
| 6 | RawEmail is a frozen dataclass with PII-safe repr omitting sender/body | VERIFIED | `repr(RawEmail(message_id='FAKEID', sender='x@y.z', body='secret'))` == `"RawEmail(message_id='FAKEID')"` — confirmed empirically |
| 7 | fetch_unread_shipping_emails() returns a list of RawEmail, paginates, decodes base64url, returns [] on no match | VERIFIED | `test_fetch_returns_raw_emails`, `test_fetch_pagination` (2-page), `test_fetch_empty`, `test_decode_base64url_padding` all pass |
| 8 | No sender, subject, or body content is ever written to logs (LOG-02) | VERIFIED | `test_fetch_does_not_log_pii` passes: `"@" not in caplog.text` and `"FAKE1234567890" not in caplog.text` asserted at DEBUG level; source scan confirms only `id=%s` and `count=%d` in log calls |
| 9 | main() invokes the Gmail fetch after load_dotenv()/configure_logging() without changing its signature | VERIFIED | `test_main_calls_fetch_and_returns_zero` passes; `main() -> int`, `GMAIL_SENDER_LIST`/`GMAIL_LOOKBACK_DAYS` parsed from env, `fetch_unread_shipping_emails` called; returns 0 with fetch patched |

**Score:** 9/9 truths verified (all automated; 2 manual-only items identified — see Human Verification section)

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `shipping_tracker/gmail/auth.py` | load_credentials() two-path OAuth flow + SCOPES constant | VERIFIED | 59 lines; fully implemented; SCOPES hard-coded |
| `shipping_tracker/gmail/query.py` | build_query() pure function | VERIFIED | 22 lines; single/multiple/empty sender cases |
| `shipping_tracker/gmail/client.py` | RawEmail + build_service() + fetch_unread_shipping_emails() + helpers | VERIFIED | 242 lines; pagination, base64url, MIME walk, backoff, PII-safe logging |
| `shipping_tracker/gmail/__init__.py` | Re-exports RawEmail, build_service, fetch_unread_shipping_emails | VERIFIED | `__all__` = ['RawEmail', 'build_service', 'fetch_unread_shipping_emails'] |
| `tests/fixtures/fake_gmail_message.py` | Synthetic FAKE_GMAIL_MESSAGE fixture | VERIFIED | dict[str, object]; all FAKE-prefixed values; no real PII |
| `tests/test_gmail_auth.py` | GMAIL-01 / GMAIL-03 credential tests | VERIFIED | 3 tests: refresh, write-back, laptop path |
| `tests/test_gmail_query.py` | GMAIL-02 query construction tests | VERIFIED | 5 tests: single, multiple, exact, empty, custom window |
| `tests/test_gmail_client.py` | GMAIL-02 fetch/pagination/decode + LOG-02 PII-safety + main() wiring | VERIFIED | 6 tests covering all required behaviors |
| `shipping_tracker/main.py` | Gmail fetch wired into pipeline orchestrator | VERIFIED | fetch_unread_shipping_emails called; GMAIL_SENDER_LIST/GMAIL_LOOKBACK_DAYS from env; returns int |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `shipping_tracker/gmail/auth.py` | `gmail.readonly` SCOPES | module-level constant, never os.getenv | VERIFIED | `SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]`; grep confirms no scope from env |
| `shipping_tracker/gmail/client.py` | `service.users().messages().list / get` | paginated fetch with labelIds=['INBOX'] | VERIFIED | `_list_all_message_ids` calls `.messages().list(**kwargs)` with `labelIds=["INBOX"]`, `userId="me"`; fetch loop calls `.messages().get(userId="me", id=msg_id, format="full")` |
| `shipping_tracker/main.py` | `shipping_tracker.gmail` | `fetch_unread_shipping_emails(senders, window)` | VERIFIED | Import confirmed; call confirmed; env-driven config confirmed |
| `shipping_tracker/gmail/client.py` | `build_query / load_credentials / RawEmail` | imports from auth.py and query.py | VERIFIED | `from shipping_tracker.gmail.auth import load_credentials`; `from shipping_tracker.gmail.query import build_query` |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `fetch_unread_shipping_emails` | `results: list[RawEmail]` | Gmail API via mocked service in tests | Yes — mocked service returns FAKE_GMAIL_MESSAGE; real credentials path exercised via mocked load_credentials | VERIFIED (mocked; real-API path is manual-only by design) |
| `main()` | `emails` from fetch | fetch_unread_shipping_emails() | Yes — wired and tested with mock | VERIFIED |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| ruff lint | `python -m ruff check .` | All checks passed | PASS |
| ruff format | `python -m ruff format --check .` | 18 files already formatted | PASS |
| mypy --strict | `python -m mypy shipping_tracker/ tests/ --strict` | Success: no issues found in 18 source files | PASS |
| Full test suite | `python -m pytest -q` | 19 passed in 0.74s | PASS |
| SCOPES constant | `SCOPES == ["https://www.googleapis.com/auth/gmail.readonly"]` | Confirmed | PASS |
| RawEmail repr PII-safety | repr omits sender/body | Confirmed empirically | PASS |
| base64url unpadded decode | FAKE1234567890 in decoded output | Confirmed | PASS |
| build_query single sender | Exact string equality | Confirmed | PASS |
| Gmail readonly enforcement | Only `.messages().list` and `.messages().get` called | grep confirms — no modify/trash/delete/batchModify/send/insert/label | PASS |
| main() graceful exit on missing credentials | exit code 1, no crash | exit=1, stdout='', stderr='' | PASS |
| main() signature | `() -> int` | Confirmed via inspect | PASS |
| Privacy audit (real email addresses in .py files) | Scan all .py files | `address@example.com` in docstring only (RFC 5321 documentation domain — not PII) | PASS |
| Privacy audit (real tracking numbers) | Scan all .py files | None found | PASS |
| Debt markers (TBD/FIXME/XXX) | Scan all .py files | None found | PASS |

---

## Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| GMAIL-01 | Tool authenticates to Gmail via OAuth2 | SATISFIED | `load_credentials()` implements two-path OAuth2 flow; `test_gmail_auth.py` covers refresh and laptop paths |
| GMAIL-02 | Tool polls for unread emails matching known shipping sender patterns | SATISFIED | `build_query()` constructs server-side query; `fetch_unread_shipping_emails()` paginates and returns `list[RawEmail]`; covered by `test_gmail_client.py` (fetch, pagination, empty, decode) |
| GMAIL-03 | OAuth token cache persists across runs so no browser interaction needed after initial setup | SATISFIED | `load_credentials()` writes token back after every refresh; `test_load_credentials_writes_token_after_refresh` confirms |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | — |

No stub patterns, placeholder returns, empty handlers, or debt markers found in any gmail source or test file.

---

## Privacy Audit Result

**CLEAN — no real PII found.**

- All email addresses in source/tests use FAKE-prefixed synthetic values (`FAKEMESSAGEID001`, `FAKETHREADID001`, `FAKEACCESSTOKEN`, `FAKEREFRESHTOKEN`, `FAKECLIENTID.apps.googleusercontent.com`, `FAKECLIENTSECRET`) or RFC 5321 documentation domains (`@aliexpress.com` as placeholder, `@fakestore.example.com`, `@fakeshop.example.com`, `shipping@fakestore.example.com`, `dispatch@fakeshop.example.com`, `address@example.com` in docstring only).
- No real tracking numbers found.
- No real names or order references found.
- `token.json`, `credentials.json`, and `.env` are all in `.gitignore`.

---

## readonly Enforcement Result

**PASS — the codebase is structurally incapable of mutating the mailbox.**

- Only two Gmail API methods are called: `.messages().list()` and `.messages().get()` — confirmed by source scan.
- No calls to `.modify()`, `.trash()`, `.delete()`, `.batchModify()`, `.send()`, `.insert()`, or any label operations anywhere in `shipping_tracker/gmail/`.
- `SCOPES` is hard-coded to `["https://www.googleapis.com/auth/gmail.readonly"]` at module level in `auth.py` and is the default value for `load_credentials()`. No path reads the scope from `.env` or any config.

---

## Human Verification Required

### 1. First-Run OAuth Browser Consent

**Test:** On a development machine with real `credentials.json` configured, run `python -m shipping_tracker`. Complete the browser consent flow. Confirm `token.json` is created.
**Expected:** Browser opens once. After consent, `token.json` is written to the path specified by `GMAIL_TOKEN_PATH`. Copy `token.json` to the Pi and confirm a subsequent run does NOT open a browser — it refreshes non-interactively.
**Why human:** Requires interactive Google consent screen and real credentials. Cannot run in CI without real OAuth credentials/PII. Documented in `02-VALIDATION.md` §Manual-Only Verifications.

### 2. GCP Consent Screen Published to Production

**Test:** In Google Cloud Console, verify the OAuth consent screen for the shipping-tracker project is in "Production" status (not "Testing").
**Expected:** Status = Production. Refresh tokens do not expire after 7 days.
**Why human:** GCP Console operation external to the codebase. Required for long-lived unattended Pi deployment. Documented in `02-VALIDATION.md` §Manual-Only Verifications.

---

## Gaps Summary

No gaps. All automated must-haves are verified. The two human verification items are documented manual-only requirements per `02-VALIDATION.md` — they are not phase failures.

---

## Overall Verdict

**VERIFIED (pending manual-only OAuth items)**

All three phase success criteria from ROADMAP.md are met by codebase evidence:

1. **SC-1 (token persistence / no-browser subsequent runs):** `load_credentials()` two-path flow is fully implemented and tested. The interactive-consent first run is a manual-only item per design.
2. **SC-2 (query and return unread matching sender patterns):** `fetch_unread_shipping_emails()` implements paginated query, MIME body extraction, base64url decode, and returns `list[RawEmail]`. Covered by 6 tests including pagination and empty-result cases.
3. **SC-3 (synthetic fixture coverage, no real email data):** `tests/fixtures/fake_gmail_message.py` provides FAKE-only data. All 19 tests use only synthetic fixtures. Privacy audit is clean.

Quality gates: ruff PASS, mypy --strict PASS (18 source files), 19/19 tests PASS, readonly enforced, LOG-02 PII-safety test passing.

---

_Verified: 2026-05-31_
_Verifier: Claude (gsd-verifier)_
