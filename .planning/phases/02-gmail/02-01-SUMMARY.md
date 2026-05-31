---
phase: 02-gmail
plan: 01
subsystem: auth
tags: [gmail, oauth2, google-api-python-client, google-auth-oauthlib, mypy-strict, pytest]

# Dependency graph
requires:
  - phase: 01-scaffold
    provides: pyproject.toml with mypy --strict, pytest, ruff; parsers/base.py dataclass pattern; conftest.py FAKE-prefix fixture pattern
provides:
  - shipping_tracker/gmail/ package with load_credentials(), build_query(), RawEmail, build_service() contracts
  - gmail.readonly SCOPES hard-coded constant (never from config)
  - Synthetic FAKE_GMAIL_MESSAGE fixture for plan 02-02 tests
  - tests/test_gmail_auth.py (GMAIL-01, GMAIL-03 green)
  - tests/test_gmail_query.py (GMAIL-02 query half green)
affects: [02-02, 03-parsers, 04-dedup]

# Tech tracking
tech-stack:
  added:
    - google-api-python-client>=2.197 (runtime)
    - google-auth-oauthlib>=1.4 (runtime)
    - google-auth>=2.53 (runtime)
    - google-api-python-client-stubs>=1.37 (dev)
  patterns:
    - TYPE_CHECKING guard for GmailResource stub import
    - frozen dataclass with custom PII-safe __repr__
    - Two-path OAuth2 flow (Pi refresh / laptop browser) in load_credentials()
    - type: ignore[no-untyped-call] on google-auth untyped methods

key-files:
  created:
    - shipping_tracker/gmail/__init__.py
    - shipping_tracker/gmail/auth.py
    - shipping_tracker/gmail/query.py
    - shipping_tracker/gmail/client.py
    - tests/fixtures/__init__.py
    - tests/fixtures/fake_gmail_message.py
    - tests/test_gmail_auth.py
    - tests/test_gmail_query.py
  modified:
    - pyproject.toml
    - .env.example

key-decisions:
  - "SCOPES constant hard-coded to gmail.readonly in auth.py — never read from .env (T-02-scope mitigation)"
  - "google_auth_oauthlib.* added to mypy overrides block — library has no stubs"
  - "type: ignore[no-untyped-call] on Credentials.from_authorized_user_file and creds.refresh — google-auth untyped under strict"
  - "Empty-senders build_query() returns is:unread newer_than:Nd without from:() clause"
  - "tests/fixtures/ package created with __init__.py for clean imports in 02-02 tests"

patterns-established:
  - "FAKE-prefixed synthetic values in all tests and fixtures (no real credentials or addresses)"
  - "Privacy docstring: PRIVACY + LOG SAFETY annotations on credential-handling functions"
  - "TYPE_CHECKING guard pattern for GmailResource to avoid runtime import of stub-only types"
  - "frozen=True dataclass + custom __repr__ that omits PII fields (sender, body)"

requirements-completed: [GMAIL-01, GMAIL-02, GMAIL-03]

# Metrics
duration: 25min
completed: 2026-05-31
---

# Phase 2 Plan 01: Gmail Foundation + Contracts Summary

**Gmail OAuth2 two-path credential loading, server-side query builder, and typed RawEmail dataclass skeleton — Google stack installed, gmail.readonly scope hard-coded, 8 tests green under mypy --strict**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-31T00:00:00Z
- **Completed:** 2026-05-31T00:25:00Z
- **Tasks:** 3
- **Files modified:** 10

## Accomplishments

- Installed the locked Google runtime stack (google-api-python-client 2.197, google-auth-oauthlib 1.4, google-auth 2.53) and dev stubs
- Created `shipping_tracker/gmail/` package skeleton with fully-typed `load_credentials()`, `build_query()`, `RawEmail`, and `build_service()` contracts for plan 02-02 to consume
- Delivered 8 passing, mypy-strict unit tests covering GMAIL-01 (non-interactive Pi refresh), GMAIL-03 (token write-back), and GMAIL-02 (query string construction including edge cases); zero PII anywhere

## Task Commits

Each task was committed atomically:

1. **Task 1: Install Google stack + add Gmail .env vars** - `236ccd4` (chore)
2. **Task 2: Create gmail package skeleton + synthetic fixture** - `173a33e` (feat)
3. **Task 3: Auth + query unit tests** - `2132dc1` (feat)

## Files Created/Modified

- `pyproject.toml` — added 3 runtime deps + 1 dev stub; extended mypy overrides to cover google_auth_oauthlib.*
- `.env.example` — added GMAIL_TOKEN_PATH, GMAIL_CREDENTIALS_PATH, GMAIL_SENDER_LIST, GMAIL_LOOKBACK_DAYS with synthetic placeholder values
- `shipping_tracker/gmail/__init__.py` — subpackage init; re-exports RawEmail and build_service
- `shipping_tracker/gmail/auth.py` — load_credentials() two-path OAuth + hard-coded SCOPES constant
- `shipping_tracker/gmail/query.py` — build_query() pure function, empty-senders edge case handled
- `shipping_tracker/gmail/client.py` — RawEmail frozen dataclass with PII-safe __repr__ + build_service() factory
- `tests/fixtures/__init__.py` — fixtures subpackage init
- `tests/fixtures/fake_gmail_message.py` — FAKE_GMAIL_MESSAGE synthetic fixture (dict[str, object])
- `tests/test_gmail_auth.py` — 3 tests: expired-token refresh, token write-back, laptop no-token path
- `tests/test_gmail_query.py` — 5 tests: single sender exact, multiple senders, exact two-sender, empty senders, custom window

## Decisions Made

- **SCOPES hard-coded**: `SCOPES: list[str] = ["https://www.googleapis.com/auth/gmail.readonly"]` defined as a module-level constant in `auth.py`; never read from `.env`. This is the T-02-scope threat mitigation.
- **google_auth_oauthlib mypy override**: `google_auth_oauthlib.*` has no type stubs and is not covered by the existing override block; extended the module list to avoid false mypy failures.
- **type: ignore[no-untyped-call]**: `Credentials.from_authorized_user_file` and `creds.refresh` in google-auth are untyped; annotated with targeted ignores rather than suppressing the entire module.
- **Empty senders edge case**: `build_query([], 30)` returns `"is:unread newer_than:30d"` — omits the `from:()` clause entirely to avoid malformed Gmail query syntax.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Extended mypy overrides to cover google_auth_oauthlib.**
- **Found during:** Task 2 (gmail package creation)
- **Issue:** `python -m mypy shipping_tracker/gmail/` reported `import-untyped` error on `google_auth_oauthlib.flow` — not covered by the existing `google.*`/`googleapiclient.*` override block
- **Fix:** Extended the `[[tool.mypy.overrides]]` module list to include `google_auth_oauthlib.*`
- **Files modified:** `pyproject.toml`
- **Verification:** `python -m mypy shipping_tracker/gmail/` exits 0 after change
- **Committed in:** 173a33e (Task 2 commit)

**2. [Rule 1 - Bug] Added type: ignore[no-untyped-call] on google-auth untyped methods.**
- **Found during:** Task 2 (gmail package creation)
- **Issue:** `Credentials.from_authorized_user_file` and `creds.refresh(Request())` are untyped in google-auth — mypy --strict flagged them as `no-untyped-call`
- **Fix:** Added targeted `# type: ignore[no-untyped-call]` comments on the two call sites in `auth.py`
- **Files modified:** `shipping_tracker/gmail/auth.py`
- **Verification:** `python -m mypy shipping_tracker/gmail/` exits 0
- **Committed in:** 173a33e (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — mypy correctness for untyped Google libs)
**Impact on plan:** Both fixes necessary for mypy --strict compliance. No scope creep; no behavioral changes.

## Issues Encountered

None beyond the mypy untyped-call issues documented above as deviations.

## User Setup Required

External services require manual configuration before the tool can authenticate at runtime (not required for this plan's tests):

- **GMAIL_CREDENTIALS_PATH**: Google Cloud Console → APIs & Services → Credentials → OAuth client ID (Desktop app) → Download JSON as `credentials.json`
- **GMAIL_TOKEN_PATH**: Generated on first laptop run via `run_local_server()`; copy `token.json` to the Pi
- **Google Cloud Console**: Enable Gmail API and create a Desktop OAuth client; publish the consent screen to Production to avoid 7-day refresh-token expiry

## Next Phase Readiness

- Plan 02-02 can import `RawEmail`, `build_query`, `load_credentials`, `SCOPES`, and `build_service` from `shipping_tracker.gmail` immediately
- `FAKE_GMAIL_MESSAGE` fixture in `tests/fixtures/fake_gmail_message.py` is available for 02-02 client tests
- The `fetch_unread_shipping_emails()` function (02-02) should be added to `shipping_tracker/gmail/__init__.py` after implementation

---
*Phase: 02-gmail*
*Completed: 2026-05-31*
