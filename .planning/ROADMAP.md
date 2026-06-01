# Roadmap: shipping-tracker

## Overview

The tool is built in the natural order of dependencies: scaffold the project, connect to Gmail, parse emails, deduplicate with SQLite, wire the TrackingMore API into a complete registration pipeline, add status monitoring with push notifications, then harden for production deployment. Each phase delivers a runnable vertical slice that proves the layer works before the next layer builds on it.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Scaffold** - Project toolchain and package structure ready for development *(Planned — 2 plans)*
- [x] **Phase 2: Gmail** - Tool authenticates to Gmail and retrieves unread shipping emails
 (completed 2026-05-31)
- [x] **Phase 3: Parser Layer** - AliExpress emails parsed via pluggable BaseParser architecture (completed 2026-06-01)
- [ ] **Phase 4: Deduplication** - SQLite state layer enforces idempotency across all runs
- [ ] **Phase 5: Pipeline** - TrackingMore registration wired end-to-end; tool runs completely
- [ ] **Phase 5.1: Status Monitoring & Notifications** *(INSERTED)* - poll for status changes, push phone notifications
- [ ] **Phase 6: Production** - Logging, deployment, and documentation make the tool cron-ready

## Phase Details

### Phase 1: Scaffold
**Goal**: The project has a complete, working toolchain so every subsequent phase starts from a clean, enforced baseline.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: SETUP-01, SETUP-02, SETUP-03, SETUP-04, SETUP-05, SETUP-06, SETUP-07
**Success Criteria** (what must be TRUE):
  1. `python -m shipping_tracker` runs (even if it just prints a placeholder) from the repo root
  2. `ruff check .` and `ruff format --check .` pass with zero violations on the initial codebase
  3. `mypy shipping_tracker/` passes with zero type errors on the initial codebase
  4. `pytest` discovers and runs the test suite (zero tests is acceptable; zero failures is required)
  5. A `git commit` triggers pre-commit hooks (ruff + mypy) and the GitHub Actions workflow runs ruff, mypy, and pytest on push
**Plans**: 2 plans

Plans:

**Wave 1**
- [x] 01-01-PLAN.md — Package foundation: pyproject.toml, .gitignore, .env.example, shipping_tracker package with entry point, pipeline stub, logging config, and BaseParser ABC

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 01-02-PLAN.md — Toolchain enforcement: pre-commit hooks, GitHub Actions CI, pytest infrastructure with smoke tests

**Cross-cutting constraints:**
- Privacy: `.env`, `*.db`, `token.json` must be in `.gitignore` before any secret is written (01-01)
- mypy `--strict` enforced from first commit — all source files must be fully typed
- All test fixtures use synthetic data only (no real tracking numbers, emails, or order refs)

### Phase 2: Gmail
**Goal**: The tool authenticates to Gmail via OAuth2 and retrieves unread emails matching shipping sender patterns, producing a list of raw email objects for downstream processing.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: GMAIL-01, GMAIL-02, GMAIL-03
**Success Criteria** (what must be TRUE):
  1. Running the tool after initial OAuth consent produces a persisted token file; subsequent runs use the token without opening a browser
  2. The tool queries Gmail and returns the set of unread messages matching at least one configured sender pattern
  3. The Gmail fetch is covered by tests using a synthetic fixture (no real email data in repo)
**Plans**: 2 plans

Plans:

**Wave 1**
- [x] 02-01-PLAN.md — Gmail foundation: install Google stack + stubs, add Gmail .env vars, create gmail package (auth/query/RawEmail contracts) + synthetic fixture and auth/query tests (GMAIL-01, GMAIL-03, GMAIL-02 query)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 02-02-PLAN.md — Fetch loop: implement fetch_unread_shipping_emails() (paginate, MIME/base64url decode, RawEmail list), wire into main(), client + LOG-02 PII-safety tests (GMAIL-02)

### Phase 3: Parser Layer
**Goal**: AliExpress shipping notification emails are parsed to extract tracking number and carrier via a pluggable BaseParser architecture that makes adding future parsers a drop-in operation.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: PARSE-01, PARSE-02, PARSE-03
**Success Criteria** (what must be TRUE):
  1. A synthetic AliExpress fixture email passed through `AliExpressParser` returns a correct `TrackingInfo` with tracking number and carrier
  2. An email that matches no parser is logged and skipped without raising an exception
  3. `BaseParser` enforces the `can_parse` / `extract` interface so a third-party parser can be registered by appending to the parser list with no other changes
**Plans**: 3 plans

Plans:

**Wave 1**
- [x] 03-01-PLAN.md — Contract + Wave 0 scaffold: D-04/D-05 edit to base.py (TrackingInfo optional carrier, extract -> TrackingInfo | None), synthetic FAKE AliExpress fixtures, 13 failing parser tests + smoke carrier-default assertion (PARSE-01)

**Wave 2** *(blocked on Wave 1)*
- [x] 03-02-PLAN.md — AliExpressParser: sender-domain can_parse (D-01) + label-anchored/shape-fallback extract (D-02), carrier None (D-04), pre-shipment returns None (D-05), PII-safe (PARSE-02)

**Wave 3** *(blocked on Wave 2)*
- [x] 03-03-PLAN.md — Dispatch wiring: PARSERS registry + first-match-wins loop, parser-derived Gmail sender list (D-01), no-match/pre-shipment logged and skipped without raising (PARSE-03)

### Phase 4: Deduplication
**Goal**: SQLite provides the stateful core of the idempotency guarantee — processed emails and registered tracking numbers are never acted on twice, and failed API calls are retried next run automatically.
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: DEDUP-01, DEDUP-02, DEDUP-03, DEDUP-04, DEDUP-05
**Success Criteria** (what must be TRUE):
  1. On first run, both `processed_emails` and `registered_tracking` tables are created if they do not exist
  2. An email whose `message_id` is already in `processed_emails` is skipped entirely without re-parsing or re-querying the API
  3. A tracking number already in `registered_tracking` is skipped without calling the TrackingMore API
  4. A simulated API failure leaves `registered_tracking` unwritten, so the same tracking number is attempted again on the next run
**Plans**: 3 plans

Plans:

**Wave 1** *(Nyquist test scaffold — authored before source)*
- [x] 04-01-PLAN.md — Wave 0 test scaffold: FAKE fixture data, in-memory db_conn fixture, and the 15 DEDUP-01..05/D-03/D-09 test functions (incl. the retry proof) failing RED until source lands

**Wave 2** *(blocked on Wave 1)*
- [ ] 04-02-PLAN.md — State layer source: registrar.py (Registrar Protocol + NullRegistrar seam, D-08/D-09) and db.py (init_db schema/PRAGMAs, dedup predicates, atomic register_and_persist — DEDUP-01..05, D-01)

**Wave 3** *(blocked on Wave 2)*
- [ ] 04-03-PLAN.md — Dispatch wiring (MVP slice): connection lifecycle in main() (D-05), DEDUP-03/04/05 checks + NullRegistrar seam + D-03 INSERT OR IGNORE branch, DATABASE_PATH in .env.example (D-07)

### Phase 5: Pipeline
**Goal**: The TrackingMore API is integrated and every layer is wired together — Gmail fetch → parse → deduplicate → register — so the tool can complete a real end-to-end run.
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: TRACK-01, TRACK-02, TRACK-03, TRACK-04, TRACK-05
**Success Criteria** (what must be TRUE):
  1. The tool reads `TRACKINGMORE_API_KEY` exclusively from `.env` and refuses to start if it is absent
  2. A parsed tracking number not in the database is successfully registered via TrackingMore's Create Trackings API (`POST https://api.trackingmore.com/v4/trackings/create`) and written to `registered_tracking` only after a confirmed success response
  3. A duplicate / already-exists response from TrackingMore is logged and treated as success — no error is raised
  4. A rate-limit, quota, or network error from TrackingMore is logged and the run continues without crashing; the tracking number is not written to the database
  5. The courier is auto-detected by TrackingMore; the parser's carrier value is passed only as an optional `courier_code` hint and is never required for registration
**Plans**: TBD

### Phase 05.1: Status Monitoring and Notifications (INSERTED)
**Goal**: The tool monitors in-flight parcels by polling TrackingMore for status changes and sends a push notification when a parcel moves — giving phone-side awareness ("out for delivery", "delivered") without any consumer app or home-screen widget, and without consuming the monthly registration quota.
**Mode:** mvp
**Depends on**: Phase 5
**Requirements**: MONITOR-01, MONITOR-02, NOTIFY-01, NOTIFY-02, NOTIFY-03
**Success Criteria** (what must be TRUE):
  1. On each run, the tool fetches current status for all non-terminal (in-flight) tracked parcels in a single bulk TrackingMore call — never one call per parcel, and never for parcels already in a delivered/terminal state
  2. Each parcel's last-known status is persisted in SQLite; a status that differs from the stored value is detected as a change and updates the stored value
  3. When a parcel's status changes, the tool sends a push notification via a channel configured in `.env` (e.g. ntfy/Pushover/Telegram), and the notification body contains no PII (no email addresses, personal names, order references, or raw email bodies)
  4. A notification or status-fetch failure is logged and never crashes the run
  5. Status polling consumes no monthly registration quota (only new-tracking creation does) and does not poll faster than TrackingMore's carrier refresh cadence (~every 4–6 hours)
**Plans**: TBD

Plans:
- [ ] TBD (run /gsd-plan-phase 05.1 to break down)

### Phase 6: Production
**Goal**: The tool is production-ready: structured JSON logging keeps PII out of log files, the entry point runs cleanly as a cron job on Raspberry Pi OS Bookworm, and the README lets a new user go from zero to running in one sitting.
**Mode:** mvp
**Depends on**: Phase 5
**Requirements**: LOG-01, LOG-02, LOG-03, DEPLOY-01, DEPLOY-02
**Success Criteria** (what must be TRUE):
  1. Log output is valid JSON and contains no email addresses, personal names, order references, or raw email bodies — verified by inspecting a test run
  2. The tool produces no stdout output during a normal run (cron-silent)
  3. `python -m shipping_tracker` (or the installed entry point) runs to completion on Raspberry Pi OS Bookworm with Python 3.11+ using only dependencies in `pyproject.toml`
  4. A developer following only the README can complete OAuth consent, set `.env`, configure cron, and verify the tool runs — without needing to read the source code
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 5.1 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Scaffold | 2/2 | Complete   | 2026-05-31 |
| 2. Gmail | 2/2 | Complete   | 2026-05-31 |
| 3. Parser Layer | 3/3 | Complete    | 2026-06-01 |
| 4. Deduplication | 1/3 | In Progress|  |
| 5. Pipeline | 0/TBD | Not started | - |
| 5.1 Status Monitoring & Notifications | 0/TBD | Not started | - |
| 6. Production | 0/TBD | Not started | - |
