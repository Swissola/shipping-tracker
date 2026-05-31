<!-- GSD:project-start source:PROJECT.md -->
## Project

**shipping-tracker**

A Python automation tool that monitors Gmail for shipping notification emails, extracts tracking numbers and carrier information, and registers them with the 17track API. Designed to run unattended on a Raspberry Pi 5 as a scheduled cron job. Intended for open-source release once stable.

**Core Value:** An email arrives → a tracking number is registered with 17track, without any human intervention, without duplicates, and without ever exposing personal data.

### Constraints

- **Privacy**: No PII in source, tests, logs, or history — project will be public; non-negotiable
- **Credentials**: All secrets via `.env` only; `.env`, SQLite DB, and OAuth token cache excluded from git
- **Tech stack**: Python 3.11+, Gmail API, SQLite stdlib, httpx/requests, structlog, ruff, mypy, pytest, pre-commit, GitHub Actions — defined in brief, not open for reconsideration
- **Test data**: Synthetic fixtures only — no real tracking numbers, email addresses, or order references
- **Architecture**: Pluggable parser pattern must be in place from Phase 1 — monolithic AliExpress-specific code would block Phase 2
<!-- GSD:project-end -->

<!-- GSD:stack-start source:STACK.md -->
## Technology Stack

Technology stack not yet documented. Will populate after codebase mapping or first phase.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
