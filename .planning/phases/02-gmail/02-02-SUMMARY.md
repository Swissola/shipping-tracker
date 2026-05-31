---
phase: 02-gmail
plan: 02
subsystem: gmail
tags: [gmail, fetch, pagination, base64url, mime, logging, pii-safety, tdd]
dependency_graph:
  requires: [02-01]
  provides: [fetch_unread_shipping_emails, _decode_base64url, _extract_body, _extract_sender, _list_all_message_ids, _execute_with_backoff]
  affects: [shipping_tracker/gmail/client.py, shipping_tracker/gmail/__init__.py, shipping_tracker/main.py, tests/test_gmail_client.py]
tech_stack:
  added: []
  patterns:
    - Paginated messages.list loop following nextPageToken
    - Recursive MIME walk for text/plain body extraction
    - base64url padding normalisation (4 - len % 4) % 4
    - _extract_sender() strips display name leaving bare address
    - _execute_with_backoff() truncated exponential backoff on HttpError 429/403
    - LOG-02 discipline: only message_id/count in log calls, never sender/body/subject
    - FileNotFoundError catch in main() -> exits 1 with no stdout (D-07 preserved)
key_files:
  created:
    - tests/test_gmail_client.py
  modified:
    - shipping_tracker/gmail/client.py
    - shipping_tracker/gmail/__init__.py
    - shipping_tracker/main.py
    - tests/test_smoke.py
decisions:
  - "LOG-02 log calls use stdlib % formatting (logger.debug('event key=%s', val)) not structlog keyword args — configure_logging() is not called in tests so structlog is not wired; stdlib logger rejects unknown kwargs"
  - "main() catches FileNotFoundError from load_credentials (missing credentials.json) and returns 1 — preserves D-07 no-stdout invariant while giving a meaningful exit code"
  - "test_entry_point_exits_zero removed from smoke tests — Phase 2 exits 1 without credentials; test_entry_point_no_stdout retained (D-07 still verified)"
  - "load_credentials patched alongside build_service in client tests — fetch_unread_shipping_emails calls load_credentials before build_service so both must be mocked to avoid FileNotFoundError in CI"
metrics:
  duration_minutes: 35
  completed_date: "2026-05-31"
  tasks_completed: 2
  files_modified: 5
---

# Phase 2 Plan 02: Gmail Fetch Loop Summary

**One-liner:** Paginated Gmail fetch with MIME body extraction, base64url decode, and LOG-02-proven PII-safe logging wired into main().

## What Was Built

`fetch_unread_shipping_emails(senders, window_days)` closes the GMAIL-02 vertical slice end-to-end:

1. Reads `GMAIL_TOKEN_PATH` / `GMAIL_CREDENTIALS_PATH` from env, calls `load_credentials()`, builds the Gmail service via `build_service()`.
2. Calls `build_query(senders, window_days)` → passes to `_list_all_message_ids()` which paginates `messages.list(userId="me", q=..., labelIds=["INBOX"])` via `nextPageToken` until exhausted.
3. For each message ID calls `messages.get(userId="me", id=..., format="full")` via `_execute_with_backoff()` (HttpError 429/403 retry with jitter).
4. Extracts the bare sender address via `_extract_sender()` (strips display name from `Name <addr>` format).
5. Extracts plain-text body via `_extract_body()` (recursive MIME walk) + `_decode_base64url()` (padding normalisation prevents binascii.Error).
6. Returns `list[RawEmail]`; returns `[]` on empty match.

`main()` wired: after `load_dotenv()` + `configure_logging()`, parses `GMAIL_SENDER_LIST` (comma-split) and `GMAIL_LOOKBACK_DAYS` (int), calls `fetch_unread_shipping_emails`, handles `FileNotFoundError` → returns 1 (no stdout, D-07 preserved).

`shipping_tracker/gmail/__init__.py` re-exports `fetch_unread_shipping_emails` in `__all__`.

## Task Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 RED | 541ca77 | Failing tests for fetch/pagination/decode/LOG-02 |
| Task 1 GREEN | 04bf93f | fetch_unread_shipping_emails() + all helpers |
| Task 2 | faa852a | Wire main() + wiring test + smoke test update |

## Test Coverage

`tests/test_gmail_client.py` (6 tests, all passing):

- `test_fetch_returns_raw_emails` — single-page fetch, RawEmail.message_id/sender/body verified
- `test_fetch_pagination` — two-page nextPageToken loop, two RawEmails returned
- `test_fetch_empty` — empty messages.list returns `[]`
- `test_decode_base64url_padding` — unpadded fixture decodes to `FAKE1234567890`
- `test_fetch_does_not_log_pii` — caplog asserts no `@` and no body token in logs (LOG-02)
- `test_main_calls_fetch_and_returns_zero` — patched fetch, main() returns 0

Full suite: 19 tests, 0 failures.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] stdlib logger rejects structlog-style keyword args**
- **Found during:** Task 1 GREEN (test run)
- **Issue:** `logger.debug("event", message_id=msg_id)` raised `TypeError: Logger._log() got an unexpected keyword argument 'message_id'` — `configure_logging()` is not called in tests so structlog wrapping is not active; plain stdlib logger rejects extra kwargs.
- **Fix:** Switched all log calls to `%`-formatting style: `logger.debug("gmail.message.fetched id=%s", msg_id)` and `logger.info("gmail.fetch.complete count=%d", len(results))`.
- **Files modified:** `shipping_tracker/gmail/client.py`
- **Commit:** 04bf93f

**2. [Rule 1 - Bug] test_entry_point_exits_zero broke when main() gained real Gmail fetch**
- **Found during:** Task 2 full suite run
- **Issue:** Phase 1 smoke test `test_entry_point_exits_zero` expected exit code 0 from `python -m shipping_tracker`. Phase 2 wiring makes the tool attempt credential load → raises `FileNotFoundError` → exit 1 in CI (no `credentials.json`).
- **Fix:** (a) Added `FileNotFoundError` catch in `main()` → returns 1 with a logged error (no stdout). (b) Removed `test_entry_point_exits_zero` from smoke tests; updated `test_entry_point_no_stdout` docstring to document Phase 2 behavior. D-07 (no stdout) is still verified.
- **Files modified:** `shipping_tracker/main.py`, `tests/test_smoke.py`
- **Commit:** faa852a

**3. [Rule 2 - Missing] load_credentials not patched in client tests**
- **Found during:** Task 1 GREEN (test run)
- **Issue:** Test mocked `build_service` but `fetch_unread_shipping_emails` calls `load_credentials` first; without patching it, tests tried to open `credentials.json` and failed with FileNotFoundError.
- **Fix:** Added `patch("shipping_tracker.gmail.client.load_credentials", return_value=_FAKE_CREDS)` to all fetch tests.
- **Files modified:** `tests/test_gmail_client.py`
- **Commit:** 04bf93f (tests updated before GREEN commit)

## Known Stubs

None — all data flows are fully wired. `fetch_unread_shipping_emails()` performs the complete credential→query→paginate→fetch→decode→RawEmail pipeline.

## Threat Flags

No new threat surface beyond what the plan's threat model covers. All T-02-* mitigations implemented:
- **T-02-logpii:** LOG-02 caplog test asserts no `@` / no body token in logs.
- **T-02-input:** `window_days` cast to `int` from env; `_decode_base64url` uses `errors="replace"`.
- **T-02-scope:** Only `messages.list` / `messages.get` called; no modify/trash/delete.
- **T-02-quota:** `_execute_with_backoff` handles 429/403 with jitter.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| shipping_tracker/gmail/client.py | FOUND |
| tests/test_gmail_client.py | FOUND |
| shipping_tracker/main.py | FOUND |
| .planning/phases/02-gmail/02-02-SUMMARY.md | FOUND |
| Commit 541ca77 (RED) | FOUND |
| Commit 04bf93f (GREEN) | FOUND |
| Commit faa852a (Task 2) | FOUND |
