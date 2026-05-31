# Requirements: shipping-tracker

**Defined:** 2026-05-31
**Core Value:** An email arrives → a tracking number is registered with 17track, without human intervention, without duplicates, and without ever exposing personal data.

## v1 Requirements

### Project Setup

- [ ] **SETUP-01**: Python package scaffolded under `shipping_tracker/` with `pyproject.toml` as the packaging manifest
- [ ] **SETUP-02**: `ruff` configured for lint and format (replaces pylint/black/isort)
- [ ] **SETUP-03**: `mypy` configured for static type checking
- [ ] **SETUP-04**: `pytest` configured with a `tests/fixtures/` directory for synthetic test data
- [ ] **SETUP-05**: `pre-commit` hooks configured to run ruff and mypy before every commit
- [ ] **SETUP-06**: GitHub Actions CI workflow runs ruff, mypy, and pytest on every push and pull request
- [ ] **SETUP-07**: `.env.example` committed with placeholder values; `.env`, SQLite DB, and OAuth token cache in `.gitignore`

### Gmail Integration

- [ ] **GMAIL-01**: Tool authenticates to Gmail via OAuth2 (`google-api-python-client`, `google-auth-oauthlib`)
- [ ] **GMAIL-02**: Tool polls for unread emails matching known shipping sender patterns
- [ ] **GMAIL-03**: OAuth token cache (e.g. `token.json`) persists across runs so no browser interaction is needed after initial setup

### Parser Layer

- [ ] **PARSE-01**: `BaseParser` abstract base class defined with `can_parse(email) -> bool` and `extract(email) -> TrackingInfo` interface
- [ ] **PARSE-02**: `AliExpressParser` implements `BaseParser` and correctly extracts tracking number and carrier from AliExpress shipping notification emails
- [ ] **PARSE-03**: Parsers are registered in a list; first match wins; unknown emails are logged and skipped without error

### Deduplication

- [ ] **DEDUP-01**: SQLite database initialised with `processed_emails(message_id PRIMARY KEY, processed_at)` table
- [ ] **DEDUP-02**: SQLite database initialised with `registered_tracking(tracking_number PRIMARY KEY, registered_at, source_email_id)` table
- [ ] **DEDUP-03**: Tool checks `processed_emails` first — skips the entire email if already seen
- [ ] **DEDUP-04**: Tool checks `registered_tracking` before calling the API — skips if tracking number already registered
- [ ] **DEDUP-05**: `registered_tracking` is only written on confirmed 17track API success — failed calls are not recorded and will retry next run

### 17track Integration

- [ ] **TRACK-01**: Tool registers tracking numbers via the 17track v2 API (`POST https://api.17track.net/track/v2/register`)
- [ ] **TRACK-02**: API key is read exclusively from environment variable; never hardcoded
- [ ] **TRACK-03**: Duplicate registration response from 17track is handled gracefully (not treated as an error)
- [ ] **TRACK-04**: All API responses are logged; rate limit errors are handled without crashing

### Logging

- [ ] **LOG-01**: Structured JSON logging to file using `structlog` or stdlib logging with JSON formatter
- [ ] **LOG-02**: Log output never contains email addresses, personal names, order references, or raw email bodies
- [ ] **LOG-03**: Tool runs silently (no stdout output during normal cron operation)

### Deployment

- [ ] **DEPLOY-01**: Tool runs as a standalone script / entry point callable by cron on Raspberry Pi 5 (Raspberry Pi OS Bookworm, Python 3.11+)
- [ ] **DEPLOY-02**: `README.md` documents setup steps: OAuth consent, initial token generation, cron configuration, `.env` variables

## v2 Requirements

### Additional Parsers (Phase 2)

- **PARSE2-01**: `AmazonUKParser` implements `BaseParser` for Amazon UK shipping notification emails
- **PARSE2-02**: `EbayParser` implements `BaseParser` for eBay shipping notification emails
- **PARSE2-03**: `EtsyParser` implements `BaseParser` for Etsy shipping notification emails
- **PARSE2-04**: Additional seller parsers can be added by implementing `BaseParser` and registering in the parser list — no changes to core pipeline required

### Additional Tracking Providers (Phase 3)

- **PROV-01**: Evaluate whether 17track covers all carriers encountered in practice; add supplementary providers only if genuine gaps are found

## Out of Scope

| Feature | Reason |
|---------|--------|
| Polling 17track for status updates | Phase 1 is registration only; status polling is a separate concern |
| Notifications/alerts when parcels move | Out of scope for this tool; would require push infrastructure |
| Web UI or dashboard | This is a CLI/cron tool; UI adds complexity without serving the goal |
| LLM-based email parsing | Adds cost and external dependency; structured email formats are sufficient |
| Non-Gmail email providers | Gmail API is the chosen source; IMAP/other providers not planned |
| Any seller other than AliExpress in v1 | Architecture supports it via pluggable parsers; Phase 2 adds them |

## Traceability

Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SETUP-01 | Phase 1 | Pending |
| SETUP-02 | Phase 1 | Pending |
| SETUP-03 | Phase 1 | Pending |
| SETUP-04 | Phase 1 | Pending |
| SETUP-05 | Phase 1 | Pending |
| SETUP-06 | Phase 1 | Pending |
| SETUP-07 | Phase 1 | Pending |
| GMAIL-01 | Phase 2 | Pending |
| GMAIL-02 | Phase 2 | Pending |
| GMAIL-03 | Phase 2 | Pending |
| PARSE-01 | Phase 3 | Pending |
| PARSE-02 | Phase 3 | Pending |
| PARSE-03 | Phase 3 | Pending |
| DEDUP-01 | Phase 4 | Pending |
| DEDUP-02 | Phase 4 | Pending |
| DEDUP-03 | Phase 4 | Pending |
| DEDUP-04 | Phase 4 | Pending |
| DEDUP-05 | Phase 4 | Pending |
| TRACK-01 | Phase 5 | Pending |
| TRACK-02 | Phase 5 | Pending |
| TRACK-03 | Phase 5 | Pending |
| TRACK-04 | Phase 5 | Pending |
| LOG-01 | Phase 6 | Pending |
| LOG-02 | Phase 6 | Pending |
| LOG-03 | Phase 6 | Pending |
| DEPLOY-01 | Phase 6 | Pending |
| DEPLOY-02 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 27 total
- Mapped to phases: 27
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-31*
*Last updated: 2026-05-31 after roadmap creation*
