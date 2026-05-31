# shipping-tracker — Project Brief

> ⚠️ **SUPERSEDED — historical brief.** This is the original project brief as first
> conceived. The direction has since changed: the tracking provider is **TrackingMore**
> (not 17track — 17track has no free recurring API tier), and the tool now also does
> **status monitoring + phone push notifications** (Phase 5.1). The 17track references
> below are retained only as the original record.
>
> **Living source of truth:** `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`,
> `.planning/ROADMAP.md`. See `PROJECT.md` §Key Decisions for the provider rationale.
> _Banner added 2026-05-31._

## Overview

A Python automation tool that monitors email for shipping notifications, extracts tracking numbers, and registers them with the 17track API. Designed to run unattended on a Raspberry Pi 5 as a cron job.

This project will be open-sourced. **No PII, credentials, or personal data may appear in source code, tests, logs, comments, or commit history at any point.**

---

## Goals

- Automatically detect shipping notification emails as they arrive in Gmail
- Extract carrier and tracking number from email content
- Register tracking numbers with 17track via their v2 API
- Deduplicate: never register the same tracking number twice, never re-process the same email
- Run silently on a schedule with structured logging

---

## Phased Delivery

### Phase 1 — AliExpress + 17track (current scope)

- Parse AliExpress shipping notification emails from Gmail
- Extract tracking number and carrier where possible
- Register with 17track v2 API (`/register` endpoint)
- SQLite for deduplication state (tracking numbers + processed email IDs)
- Cron deployment on Raspberry Pi 5

### Phase 2 — Additional sellers

- Extend to other sellers: Amazon UK, eBay, Etsy, and others
- Email parser must be **modular from Phase 1** — pluggable per-seller parsers, not a monolithic AliExpress-specific implementation
- Each seller gets its own parser module implementing a common interface

### Phase 3 — Evaluate additional shipping APIs

- Assess whether 17track covers all carriers encountered in practice
- Add supplementary providers only if genuine gaps emerge
- 17track covers ~2,500 carriers; this phase may not be needed

---

## Architecture

### Email Source

- **Gmail API** via OAuth2
- Poll for unread emails matching known shipping sender patterns
- Track processed Gmail message IDs in SQLite to prevent reprocessing

### Parser Layer

- Abstract base class: `BaseParser` with `can_parse(email) -> bool` and `extract(email) -> TrackingInfo`
- Phase 1 implementation: `AliExpressParser`
- Parsers registered in a list; first match wins
- Unknown emails: log and skip (no LLM fallback in Phase 1)

### Deduplication

- SQLite database (local, not committed)
- Two tables:
  - `processed_emails(message_id PRIMARY KEY, processed_at)`
  - `registered_tracking(tracking_number PRIMARY KEY, registered_at, source_email_id)`
- Check `processed_emails` first — skip entire email if already seen
- Check `registered_tracking` before API call — skip if tracking number already registered
- Only write to `registered_tracking` on confirmed 17track API success (failed calls retry next run)

### 17track Integration

- API v2: `https://api.17track.net/track/v2/register`
- API key via environment variable
- Handle duplicate registration response gracefully (not an error)
- Respect rate limits; log all API responses

### Deployment

- Target: Raspberry Pi 5 (Raspberry Pi OS Bookworm, Python 3.11+)
- Scheduled via cron
- Structured JSON logging to file (no stdout emission of PII)
- Logs must not contain: email addresses, personal names, order references, or raw email bodies

---

## Tech Stack

- **Language**: Python 3.11+
- **Email**: Gmail API (`google-api-python-client`, `google-auth-oauthlib`)
- **Database**: SQLite via `sqlite3` (stdlib)
- **HTTP**: `httpx` or `requests`
- **Config**: `python-dotenv` — all secrets in `.env`, never in source
- **Logging**: `structlog` or stdlib `logging` with JSON formatter
- **Testing**: `pytest` with synthetic/anonymised fixtures only
- **Linting/Formatting**: `ruff` (lint + format, replaces pylint/black/isort)
- **Type checking**: `mypy`
- **Pre-commit hooks**: `pre-commit` running ruff and mypy before every commit
- **CI**: GitHub Actions — runs ruff, mypy, and pytest on every push and pull request
- **Packaging**: `pyproject.toml`

---

## Privacy & Security Constraints

These are non-negotiable and apply to every phase:

- All credentials (Gmail OAuth, 17track API key) via `.env` only
- `.env` is in `.gitignore` — never committed
- `.env.example` committed with placeholder values only
- SQLite DB file in `.gitignore` — never committed
- OAuth token cache files (e.g. `token.json`) in `.gitignore`
- Test fixtures use **synthetic data only** — fake tracking numbers, fake email addresses, no real order data
- Log output must never contain email addresses, personal names, or order details
- Tracking numbers in logs: avoid unless necessary for debugging; if included, mark as sensitive
- No hardcoded strings that could identify a real person or order

---

## Repository

- **Name**: `shipping-tracker`
- **Initial visibility**: Private
- **Intended**: Open-source (public) once stable
- **Structure**:

```text
shipping-tracker/
├── shipping_tracker/
│   ├── __init__.py
│   ├── gmail_client.py
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── aliexpress.py
│   ├── tracker.py          # 17track API client
│   ├── database.py         # SQLite dedup layer
│   └── main.py             # Entry point
├── tests/
│   └── fixtures/           # Synthetic test data only
├── .env.example
├── .gitignore
├── pyproject.toml
└── README.md
```

---

## Out of Scope (Phase 1)

- Polling 17track for status updates
- Notifications/alerts when parcels move
- Web UI or dashboard
- LLM-based email parsing
- Non-Gmail email providers
- Any seller other than AliExpress
