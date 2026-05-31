# Roadmap: shipping-tracker

## Overview

Six phases build the tool in the natural order of dependencies: scaffold the project, connect to Gmail, parse emails, deduplicate with SQLite, wire the 17track API into a complete pipeline, then harden for production deployment. Each phase delivers a runnable vertical slice that proves the layer works before the next layer builds on it.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Scaffold** - Project toolchain and package structure ready for development
- [ ] **Phase 2: Gmail** - Tool authenticates to Gmail and retrieves unread shipping emails
- [ ] **Phase 3: Parser Layer** - AliExpress emails parsed via pluggable BaseParser architecture
- [ ] **Phase 4: Deduplication** - SQLite state layer enforces idempotency across all runs
- [ ] **Phase 5: Pipeline** - 17track registration wired end-to-end; tool runs completely
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
**Plans**: TBD

### Phase 2: Gmail
**Goal**: The tool authenticates to Gmail via OAuth2 and retrieves unread emails matching shipping sender patterns, producing a list of raw email objects for downstream processing.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: GMAIL-01, GMAIL-02, GMAIL-03
**Success Criteria** (what must be TRUE):
  1. Running the tool after initial OAuth consent produces a persisted token file; subsequent runs use the token without opening a browser
  2. The tool queries Gmail and returns the set of unread messages matching at least one configured sender pattern
  3. The Gmail fetch is covered by tests using a synthetic fixture (no real email data in repo)
**Plans**: TBD

### Phase 3: Parser Layer
**Goal**: AliExpress shipping notification emails are parsed to extract tracking number and carrier via a pluggable BaseParser architecture that makes adding future parsers a drop-in operation.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: PARSE-01, PARSE-02, PARSE-03
**Success Criteria** (what must be TRUE):
  1. A synthetic AliExpress fixture email passed through `AliExpressParser` returns a correct `TrackingInfo` with tracking number and carrier
  2. An email that matches no parser is logged and skipped without raising an exception
  3. `BaseParser` enforces the `can_parse` / `extract` interface so a third-party parser can be registered by appending to the parser list with no other changes
**Plans**: TBD

### Phase 4: Deduplication
**Goal**: SQLite provides the stateful core of the idempotency guarantee — processed emails and registered tracking numbers are never acted on twice, and failed API calls are retried next run automatically.
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: DEDUP-01, DEDUP-02, DEDUP-03, DEDUP-04, DEDUP-05
**Success Criteria** (what must be TRUE):
  1. On first run, both `processed_emails` and `registered_tracking` tables are created if they do not exist
  2. An email whose `message_id` is already in `processed_emails` is skipped entirely without re-parsing or re-querying the API
  3. A tracking number already in `registered_tracking` is skipped without calling the 17track API
  4. A simulated API failure leaves `registered_tracking` unwritten, so the same tracking number is attempted again on the next run
**Plans**: TBD

### Phase 5: Pipeline
**Goal**: The 17track API is integrated and every layer is wired together — Gmail fetch → parse → deduplicate → register — so the tool can complete a real end-to-end run.
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: TRACK-01, TRACK-02, TRACK-03, TRACK-04
**Success Criteria** (what must be TRUE):
  1. The tool reads `SEVENTEEN_TRACK_API_KEY` exclusively from `.env` and refuses to start if it is absent
  2. A parsed tracking number not in the database is successfully registered via `POST /track/v2/register` and written to `registered_tracking` only after a confirmed success response
  3. A duplicate-registration response from 17track (already registered) is logged and treated as success — no error is raised
  4. A rate-limit or network error from 17track is logged and the run continues without crashing; the tracking number is not written to the database
**Plans**: TBD

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
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Scaffold | 0/TBD | Not started | - |
| 2. Gmail | 0/TBD | Not started | - |
| 3. Parser Layer | 0/TBD | Not started | - |
| 4. Deduplication | 0/TBD | Not started | - |
| 5. Pipeline | 0/TBD | Not started | - |
| 6. Production | 0/TBD | Not started | - |
