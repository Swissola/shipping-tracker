# Phase 1: Scaffold - Context

**Gathered:** 2026-05-31
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish the complete Python project structure, toolchain, and CI baseline that all subsequent phases build on. Deliverable: a repo where `python -m shipping_tracker` runs, `ruff`, `mypy --strict`, and `pytest` all pass, pre-commit hooks fire on commit, and GitHub Actions CI runs the full check suite on every push.

</domain>

<decisions>
## Implementation Decisions

### Entry Point

- **D-01:** `python -m shipping_tracker` runs the full pipeline directly — zero arguments, no flags, cron-friendly. Everything configured via `.env`.
- **D-02:** Entry point lives in two places: `shipping_tracker/__main__.py` (enables `python -m shipping_tracker`) AND a `console_scripts` entry in `pyproject.toml` (exposes `shipping-tracker` as an installed command for the cron line).
- **D-03:** Entry function is **synchronous**. Architecture must not block a future move to async — no deep coupling to sync-specific patterns, no `time.sleep` loops, clean separation between I/O and logic.

### HTTP Client

- **D-04:** Use `httpx` with `httpx.Client` (sync). Async-capable if the architecture evolves, but no `AsyncClient` complexity until needed.

### Logging

- **D-05:** Use `structlog`. Output is compact JSON — **no whitespace, no indentation** — optimised for both machine parsing and LLM consumption.
- **D-06:** Rotate log file at 10MB, keep 3 rotations. Default path: `logs/shipping-tracker.log`.
- **D-07:** Default log level: `WARNING`. INFO and DEBUG are available but not the cron default.

### Type Checking

- **D-08:** mypy runs with `--strict` from day 1. All functions must be fully typed. `# type: ignore` comments are tracked and cleaned up. Expect a small number of explicit `cast()` calls around Gmail API responses (patchy stubs).

### Dependencies

- **D-09:** Split `pyproject.toml` into runtime `[project.dependencies]` and `[project.optional-dependencies]` dev group. `pip install -e '.[dev]'` installs everything; production install on the Pi skips dev tools.

### CI

- **D-10:** GitHub Actions on `ubuntu-latest`. Python version matrix: **3.11, 3.12, 3.13**. Triggers on every push and pull request. Jobs: ruff check, ruff format --check, mypy --strict, pytest.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Context
- `.planning/PROJECT.md` — project goals, privacy constraints (non-negotiable), and key decisions
- `.planning/REQUIREMENTS.md` — SETUP-01 through SETUP-07 define exactly what this phase must deliver
- `.planning/ROADMAP.md` — Phase 1 success criteria (the observable outcomes that define "done")

### Privacy & Security
- `.planning/PROJECT.md §Privacy & Security Constraints` — non-negotiable rules: no PII in source, tests, logs, or history; `.env`, SQLite DB, and token cache never committed; test fixtures use synthetic data only

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield project. All modules are new.

### Established Patterns
- None established yet. This phase sets the patterns all subsequent phases follow.

### Integration Points
- `shipping_tracker/__main__.py` → calls `main()` in `shipping_tracker/main.py`
- `shipping_tracker/main.py` → orchestrates the pipeline (Gmail → parsers → dedup → 17track). Stubbed in Phase 1; wired in Phase 5.
- `pyproject.toml` → declares all runtime and dev dependencies upfront so subsequent phases can add imports without config changes

</code_context>

<specifics>
## Specific Ideas

- Compact JSON log output (no whitespace) is an explicit requirement — configure structlog's JSON renderer with `sort_keys=True` and no separators beyond `,` and `:`.
- The `logs/` directory should be in `.gitignore`.
- `shipping-tracker` (kebab-case) as the console_scripts command name, matching the repo name.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 1-Scaffold*
*Context gathered: 2026-05-31*
