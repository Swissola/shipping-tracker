# Requirements: shipping-tracker

**Defined:** 2026-05-31
**Core Value:** An email arrives → a tracking number is registered with TrackingMore, and you are notified on your phone when the parcel's status changes — without human intervention, without duplicates, and without ever exposing personal data.

## v1 Requirements

### Project Setup

- [x] **SETUP-01**: Python package scaffolded under `shipping_tracker/` with `pyproject.toml` as the packaging manifest
- [x] **SETUP-02**: `ruff` configured for lint and format (replaces pylint/black/isort)
- [x] **SETUP-03**: `mypy` configured for static type checking
- [x] **SETUP-04**: `pytest` configured with a `tests/fixtures/` directory for synthetic test data
- [x] **SETUP-05**: `pre-commit` hooks configured to run ruff and mypy before every commit
- [x] **SETUP-06**: GitHub Actions CI workflow runs ruff, mypy, and pytest on every push and pull request
- [x] **SETUP-07**: `.env.example` committed with placeholder values; `.env`, SQLite DB, and OAuth token cache in `.gitignore`

### Gmail Integration

- [x] **GMAIL-01**: Tool authenticates to Gmail via OAuth2 (`google-api-python-client`, `google-auth-oauthlib`)
- [x] **GMAIL-02**: Tool polls for unread emails matching known shipping sender patterns
- [x] **GMAIL-03**: OAuth token cache (e.g. `token.json`) persists across runs so no browser interaction is needed after initial setup

### Parser Layer

- [x] **PARSE-01**: `BaseParser` abstract base class defined with `can_parse(email) -> bool` and `extract(email) -> TrackingInfo` interface
- [x] **PARSE-02**: `AliExpressParser` implements `BaseParser` and correctly extracts the tracking number from AliExpress shipping notification emails; carrier is best-effort metadata only (TrackingMore auto-detects the courier, so a missing carrier never blocks registration)
- [ ] **PARSE-03**: Parsers are registered in a list; first match wins; unknown emails are logged and skipped without error

### Deduplication

- [ ] **DEDUP-01**: SQLite database initialised with `processed_emails(message_id PRIMARY KEY, processed_at)` table
- [ ] **DEDUP-02**: SQLite database initialised with `registered_tracking(tracking_number PRIMARY KEY, registered_at, source_email_id, last_status, last_status_at)` table (`last_status`/`last_status_at` are nullable; populated by Phase 5.1 monitoring)
- [ ] **DEDUP-03**: Tool checks `processed_emails` first — skips the entire email if already seen
- [ ] **DEDUP-04**: Tool checks `registered_tracking` before calling the API — skips registration if tracking number already registered
- [ ] **DEDUP-05**: `registered_tracking` is only written on confirmed TrackingMore API success — failed calls are not recorded and will retry next run

### Tracking Provider Integration (TrackingMore)

- [ ] **TRACK-01**: Tool registers tracking numbers via the TrackingMore Create Trackings API (`POST https://api.trackingmore.com/v4/trackings/create`)
- [ ] **TRACK-02**: API key is read exclusively from the `TRACKINGMORE_API_KEY` environment variable; never hardcoded
- [ ] **TRACK-03**: A duplicate / already-exists response from TrackingMore is handled gracefully (not treated as an error)
- [ ] **TRACK-04**: All API responses are logged; rate-limit and monthly-quota errors (free tier: 50 new trackings/month) are handled without crashing
- [ ] **TRACK-05**: The courier is auto-detected by TrackingMore; if the parser supplied a carrier it is passed only as an optional `courier_code` hint, and registration never requires it

### Status Monitoring

- [ ] **MONITOR-01**: On each run, the tool fetches the current status of all non-terminal (in-flight) tracked parcels from TrackingMore in a single bulk call — never one call per parcel, and never for parcels already in a delivered/terminal state. Status retrieval consumes no monthly registration quota (only new-tracking creation does)
- [ ] **MONITOR-02**: Each parcel's last-known status is persisted in SQLite (`registered_tracking.last_status`); a fetched status that differs from the stored value is detected as a change and updates the stored value. Polling never exceeds TrackingMore's carrier refresh cadence (~every 4–6 hours)

### Notifications

- [ ] **NOTIFY-01**: When a tracked parcel's status changes (e.g. in transit → out for delivery → delivered), the tool sends a push notification via a channel configured in `.env` (e.g. ntfy / Pushover / Telegram — final channel chosen at Phase 5.1 planning)
- [ ] **NOTIFY-02**: Notification payloads contain no PII — no email addresses, personal names, order references, or raw email bodies
- [ ] **NOTIFY-03**: A notification or status-fetch failure is logged and never crashes the run

### Logging

- [ ] **LOG-01**: Structured JSON logging to file using `structlog` or stdlib logging with JSON formatter
- [ ] **LOG-02**: Log output never contains email addresses, personal names, order references, or raw email bodies
- [ ] **LOG-03**: Tool runs silently (no stdout output during normal cron operation)

### Deployment

- [ ] **DEPLOY-01**: Tool runs as a standalone script / entry point callable by cron on Raspberry Pi 5 (Raspberry Pi OS Bookworm, Python 3.11+)
- [ ] **DEPLOY-02**: `README.md` documents setup steps: OAuth consent, initial token generation, cron configuration, `.env` variables (including `TRACKINGMORE_API_KEY` and the notification channel)

## v2 Requirements

### Additional Parsers (Phase 2)

- **PARSE2-01**: `AmazonUKParser` implements `BaseParser` for Amazon UK shipping notification emails
- **PARSE2-02**: `EbayParser` implements `BaseParser` for eBay shipping notification emails
- **PARSE2-03**: `EtsyParser` implements `BaseParser` for Etsy shipping notification emails
- **PARSE2-04**: Additional seller parsers can be added by implementing `BaseParser` and registering in the parser list — no changes to core pipeline required

### Additional Tracking Providers (Phase 3)

- **PROV-01**: Evaluate whether TrackingMore covers all carriers encountered in practice; add a supplementary provider (e.g. Ship24) only if genuine gaps are found

## Out of Scope

| Feature | Reason |
|---------|--------|
| Native phone app / home-screen widget | Push notifications on status change (NOTIFY-01) cover the "know on my phone" need; a consumer app/widget would require manual entry or a separate account that API-registered parcels do not feed |
| Notifications for events other than status change | v1 notifies on carrier status transitions only; richer alerting (ETAs, exceptions digests) is a later concern |
| Web UI or dashboard | This is a CLI/cron tool; UI adds complexity without serving the goal |
| LLM-based email parsing | Adds cost and external dependency; structured email formats are sufficient |
| Non-Gmail email providers | Gmail API is the chosen source; IMAP/other providers not planned |
| Any seller other than AliExpress in v1 | Architecture supports it via pluggable parsers; Phase 2 adds them |

## Traceability

Updated during roadmap creation and the TrackingMore provider replan (2026-05-31).

| Requirement | Phase | Status |
|-------------|-------|--------|
| SETUP-01 | Phase 1 | Complete |
| SETUP-02 | Phase 1 | Complete |
| SETUP-03 | Phase 1 | Complete |
| SETUP-04 | Phase 1 | Complete |
| SETUP-05 | Phase 1 | Complete |
| SETUP-06 | Phase 1 | Complete |
| SETUP-07 | Phase 1 | Complete |
| GMAIL-01 | Phase 2 | Complete |
| GMAIL-02 | Phase 2 | Complete |
| GMAIL-03 | Phase 2 | Complete |
| PARSE-01 | Phase 3 | Complete |
| PARSE-02 | Phase 3 | Complete |
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
| TRACK-05 | Phase 5 | Pending |
| MONITOR-01 | Phase 5.1 | Pending |
| MONITOR-02 | Phase 5.1 | Pending |
| NOTIFY-01 | Phase 5.1 | Pending |
| NOTIFY-02 | Phase 5.1 | Pending |
| NOTIFY-03 | Phase 5.1 | Pending |
| LOG-01 | Phase 6 | Pending |
| LOG-02 | Phase 6 | Pending |
| LOG-03 | Phase 6 | Pending |
| DEPLOY-01 | Phase 6 | Pending |
| DEPLOY-02 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 33 total
- Mapped to phases: 33
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-31*
*Last updated: 2026-05-31 after TrackingMore provider replan (status monitoring + notifications added)*
