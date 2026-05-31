---
phase: 02-gmail
audited: 2026-05-31
asvs_level: 1
auditor: gsd-security-auditor
verdict: SECURED
threats_total: 6
threats_closed: 6
threats_open: 0
---

# Phase 02 — Gmail Security Audit

**Phase:** 02-gmail (plans 02-01 and 02-02)
**Threats Closed:** 6/6
**ASVS Level:** 1
**Verdict:** SECURED

---

## Threat Verification

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-02-scope | Tampering | mitigate | CLOSED | See below |
| T-02-token | Info Disclosure | mitigate | CLOSED | See below |
| T-02-logpii | Info Disclosure | mitigate | CLOSED | See below |
| T-02-input | DoS / Tampering | mitigate | CLOSED | See below |
| T-02-SC | Tampering | accept | CLOSED | See below |
| T-02-quota | Denial of Service | accept | CLOSED | See below |

---

## Per-Threat Findings

### T-02-scope — OAuth scope hard-coded; no mutating Gmail calls

**Mitigation declared:** `SCOPES` hard-coded to `["https://www.googleapis.com/auth/gmail.readonly"]`,
never read from `os.getenv`/config; fetch calls ONLY `messages().list()` / `messages().get()` — no
`modify`/`trash`/`delete`/`batchModify`/`send`/`insert`/label operations in `shipping_tracker/gmail/`.

**Verification:**

1. `SCOPES` constant — `shipping_tracker/gmail/auth.py:14`:
   ```
   SCOPES: list[str] = ["https://www.googleapis.com/auth/gmail.readonly"]
   ```
   Module-level constant. The default parameter `scopes: list[str] = SCOPES` on `load_credentials()`
   references the constant directly — never derived from `os.getenv`.

2. `os.getenv` absent from `auth.py` — grep returned zero matches across the entire file.

3. Mutating-method scan — grep for `modify|trash|delete|batchModify|send|insert|label` across
   `shipping_tracker/gmail/` returned only:
   - `client.py:183`: `"labelIds": ["INBOX"]` — a filter parameter on `messages().list()`, not a
     mutating call.
   No `messages().modify()`, `.trash()`, `.delete()`, `.batchModify()`, `.send()`, or `.insert()`
   calls exist anywhere in the package.

4. All fetch calls are read-only:
   - `client.py:189`: `service.users().messages().list(...)` inside `_list_all_message_ids()`
   - `client.py:233`: `service.users().messages().get(userId="me", id=msg_id, format="full")`

**Status: CLOSED**

---

### T-02-token — token.json / credentials.json never logged; both git-ignored

**Mitigation declared:** Both files git-ignored; `load_credentials()` never logs the Credentials
object or any field from it.

**Verification:**

1. Git-ignore — `git check-ignore -v token.json credentials.json` output:
   ```
   .gitignore:3:token.json    token.json
   .gitignore:4:credentials.json    credentials.json
   ```
   Both entries confirmed in `.gitignore` lines 3–4, with the comment
   `# Secrets and credentials (SETUP-07 — NON-NEGOTIABLE, project will be public)`.

2. `auth.py` log calls — grep for `logger.` across `auth.py` returned zero matches.
   No logging is performed anywhere in `load_credentials()`. The docstring carries
   `LOG SAFETY: Do not log the Credentials object or any field from it.` at line 40.

**Status: CLOSED**

---

### T-02-logpii — No sender/subject/body in any log statement; LOG-02 caplog test passes

**Mitigation declared:** Only opaque fields logged (e.g., `message_id=`, `count=`); no
sender/subject/body/email-address in any log statement. LOG-02 `caplog` test exists, asserts
no `@` and no body token in log output, and passes.

**Verification:**

1. All log calls in `shipping_tracker/gmail/client.py`:
   - Line 152–157: `logger.warning("gmail.api.rate_limited status=%s attempt=%d retry_after=%.2f", exc.status_code, attempt + 1, wait)` — only HTTP status, retry count, delay (opaque numerics).
   - Line 238: `logger.debug("gmail.message.fetched id=%s", msg_id)` — only the opaque Gmail message ID.
   - Line 240: `logger.info("gmail.fetch.complete count=%d", len(results))` — only a count integer.

2. `sender=`, `body=`, `subject=` grep across log call lines — the only matches found were
   `results.append(RawEmail(message_id=msg_id, sender=sender, body=body))` (constructor, not a log)
   and the docstring. Zero log calls contain PII fields.

3. `auth.py` has no log calls at all (verified above under T-02-token).

4. `main.py:36`: `logger.error("gmail.credentials.missing path=%s", exc.filename)` — logs a
   filesystem path, not email content.

5. LOG-02 test — `tests/test_gmail_client.py::test_fetch_does_not_log_pii`:
   - Uses `caplog.at_level(logging.DEBUG, logger="shipping_tracker.gmail.client")`
   - Asserts `"@" not in caplog.text` (no email addresses)
   - Asserts `"FAKE1234567890" not in caplog.text` (no body content)
   - Test passes: confirmed by live pytest run (14/14 passed, 0.32 s).

**Status: CLOSED**

---

### T-02-input — window_days cast to int; _decode_base64url uses errors="replace"

**Mitigation declared:** `window_days` cast to int; `_decode_base64url` normalises padding and
decodes defensively (`errors="replace"`) so malformed bodies cannot raise/crash the run.

**Verification:**

1. `window_days` int cast — `shipping_tracker/main.py:31`:
   ```python
   window = int(os.getenv("GMAIL_LOOKBACK_DAYS", "30"))
   ```
   `os.getenv` always returns a string; `int()` cast is present and unconditional.
   `build_query` receives this already-cast integer.

2. `_decode_base64url` defensive decode — `shipping_tracker/gmail/client.py:68–70`:
   ```python
   missing = (4 - len(data) % 4) % 4
   padded = data + "=" * missing
   return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
   ```
   Padding normalisation prevents `binascii.Error` on unpadded inputs.
   `errors="replace"` prevents `UnicodeDecodeError` on invalid byte sequences.

3. Decode test — `tests/test_gmail_client.py::test_decode_base64url_padding`:
   - Exercises the known unpadded fixture string
   - Asserts `"FAKE1234567890" in result`
   - Test passes.

**Status: CLOSED**

---

### T-02-SC — Supply chain: pip Google stack packages

**Disposition:** accept

**Acceptance basis:** All four packages cleared the RESEARCH §Package Legitimacy Audit slopcheck
with `[OK]` verdicts (no `[ASSUMED]`, `[SUS]`, or `[SLOP]` findings):

| Package | Age | Verdict |
|---------|-----|---------|
| `google-api-python-client` | ~14 yrs | [OK] — established Google-published package |
| `google-auth-oauthlib` | ~8 yrs | [OK] — Google-published |
| `google-auth` | ~8 yrs | [OK] — Google-published |
| `google-api-python-client-stubs` | ~5 yrs | [OK] — henribru/google-api-python-client-stubs, verified on GitHub |

No packages were rejected or flagged. These are canonical Google-published libraries distributed
under well-known PyPI names. The stubs package has a verified open-source upstream.

**Residual risk:** Supply chain integrity is not pinned at the hash level (no `pip hash` check or
lockfile with hashes). This is an operational deployment concern outside this phase's scope, and is
accepted for a personal-use tool running on a Raspberry Pi with no public exposure.

**Status: CLOSED (accepted risk, documented)**

---

### T-02-quota — Rate limit 429/403 handling

**Disposition:** accept

**Acceptance basis:** Two volume-bounding controls are in place:

1. `newer_than:Nd` + sender-scoped query in `build_query()` limits the candidate message set to
   a bounded window and specific senders — prevents unbounded enumeration of a large inbox.

2. `_execute_with_backoff()` at `shipping_tracker/gmail/client.py:132–160`:
   - Catches `HttpError` where `exc.status_code in (429, 403)` and `attempt < max_retries`
   - Computes truncated exponential backoff: `(2**attempt) + random.uniform(0, 1)` seconds with jitter
   - Retries up to `max_retries=3` times before re-raising
   - All three Gmail API call sites route through this helper

Quota exhaustion on an unusually large mailbox remains a documented operational limit (noted in
RESEARCH as Pitfall 6), not a code defect. The retry logic ensures transient 429s are handled
gracefully; sustained quota exhaustion will propagate as an `HttpError` exception, surface in logs,
and abort the run without data loss.

**Status: CLOSED (accepted risk, documented)**

---

## PII Scan

Source files and test fixtures were scanned for real email addresses, tracking numbers, names, and
order references. All `@` occurrences in `shipping_tracker/` and `tests/` resolve to:

- `@aliexpress.com` — domain placeholder (GMAIL_SENDER_LIST default, synthetic only)
- `@fakestore.example.com` — fixture sender (FAKE-prefixed)
- `@fakeshop.example.com` — pagination fixture sender (FAKE-prefixed)

No real PII was found. `address@example.com` in docstrings is the RFC 5321 documentation domain.

**PII check: PASSED**

---

## Unregistered Flags

SUMMARY.md `## Threat Flags` section (02-02-SUMMARY.md) states:

> No new threat surface beyond what the plan's threat model covers.

All four flags listed (`T-02-logpii`, `T-02-input`, `T-02-scope`, `T-02-quota`) map to registered
threat IDs. No unregistered flags.

---

## Test Run Evidence

```
platform win32 -- Python 3.14.0, pytest-9.0.3
14 passed in 0.32s

tests/test_gmail_client.py::test_fetch_returns_raw_emails         PASSED
tests/test_gmail_client.py::test_fetch_pagination                 PASSED
tests/test_gmail_client.py::test_fetch_empty                      PASSED
tests/test_gmail_client.py::test_decode_base64url_padding         PASSED
tests/test_gmail_client.py::test_fetch_does_not_log_pii           PASSED
tests/test_gmail_client.py::test_main_calls_fetch_and_returns_zero PASSED
tests/test_gmail_auth.py::test_load_credentials_refreshes_expired_token PASSED
tests/test_gmail_auth.py::test_load_credentials_writes_token_after_refresh PASSED
tests/test_gmail_auth.py::test_load_credentials_laptop_path_when_no_token PASSED
tests/test_gmail_query.py::test_build_query_single_sender         PASSED
tests/test_gmail_query.py::test_build_query_multiple_senders      PASSED
tests/test_gmail_query.py::test_build_query_multiple_senders_exact PASSED
tests/test_gmail_query.py::test_build_query_empty_senders_returns_unread_query PASSED
tests/test_gmail_query.py::test_build_query_window_days_in_result PASSED
```
