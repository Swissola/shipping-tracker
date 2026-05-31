# shipping-tracker

## What This Is

A Python automation tool that monitors Gmail for shipping notification emails, extracts tracking numbers and carrier information, and registers them with the 17track API. Designed to run unattended on a Raspberry Pi 5 as a scheduled cron job. Intended for open-source release once stable.

## Core Value

An email arrives → a tracking number is registered with 17track, without any human intervention, without duplicates, and without ever exposing personal data.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Poll Gmail via OAuth2 for unread emails matching known shipping sender patterns
- [ ] Parse AliExpress shipping notification emails to extract tracking number and carrier
- [ ] Register extracted tracking numbers with the 17track v2 API (`/register` endpoint)
- [ ] Deduplicate: skip any email already in `processed_emails` table; skip any tracking number already in `registered_tracking` table
- [ ] Write to `registered_tracking` only on confirmed API success (failed calls retry next run)
- [ ] SQLite database with `processed_emails` and `registered_tracking` tables
- [ ] Structured JSON logging to file — no PII in log output
- [ ] Run as a cron job on Raspberry Pi 5 (Raspberry Pi OS Bookworm, Python 3.11+)
- [ ] Pluggable parser architecture (`BaseParser` with `can_parse` / `extract`) so Phase 2 sellers are drop-in additions
- [ ] Full project toolchain: ruff, mypy, pytest, pre-commit hooks, GitHub Actions CI
- [ ] Synthetic-only test fixtures — no real email addresses, tracking numbers, or order data

### Out of Scope

- Polling 17track for status updates — Phase 1 is registration only
- Notifications/alerts when parcels move — future phase
- Web UI or dashboard — out of scope entirely for this tool
- LLM-based email parsing — adds complexity and cost; regex/heuristic parsing is sufficient
- Non-Gmail email providers — Gmail API is the chosen source
- Any seller other than AliExpress in Phase 1 — architecture supports it; Phase 2 adds the parsers
- Additional shipping API providers — Phase 3 evaluation; 17track covers ~2,500 carriers

## Context

- Deployment target: Raspberry Pi 5 running Raspberry Pi OS Bookworm with Python 3.11+
- Privacy is a first-class constraint: this project will be open-sourced, so no PII, credentials, or personal data may appear anywhere in source code, tests, logs, comments, or commit history
- Gmail OAuth2 flow: initial auth requires a browser; thereafter the token cache handles refresh unattended
- 17track v2 API handles duplicate registration gracefully — not an error condition
- Parsers are registered in a list; first match wins; unknown emails are logged and skipped

## Constraints

- **Privacy**: No PII in source, tests, logs, or history — project will be public; non-negotiable
- **Credentials**: All secrets via `.env` only; `.env`, SQLite DB, and OAuth token cache excluded from git
- **Tech stack**: Python 3.11+, Gmail API, SQLite stdlib, httpx/requests, structlog, ruff, mypy, pytest, pre-commit, GitHub Actions — defined in brief, not open for reconsideration
- **Test data**: Synthetic fixtures only — no real tracking numbers, email addresses, or order references
- **Architecture**: Pluggable parser pattern must be in place from Phase 1 — monolithic AliExpress-specific code would block Phase 2

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Gmail API via OAuth2 | Direct access to Gmail; works headlessly after initial auth | — Pending |
| SQLite for deduplication state | Zero-dependency, local, sufficient for single-instance cron job | — Pending |
| Pluggable `BaseParser` from Phase 1 | Phase 2 adds sellers; retrofitting the architecture later would be costly | — Pending |
| Write `registered_tracking` only on API success | Ensures failed registrations are retried next run without double-processing | — Pending |
| No LLM fallback in Phase 1 | Adds cost and complexity; structured email formats make regex sufficient | — Pending |
| ruff replaces pylint/black/isort | Single tool for lint + format + import sorting; faster, simpler config | — Pending |
| Structured JSON logging | Machine-readable, easy to grep; compatible with log aggregation if needed later | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-31 after initialization*
