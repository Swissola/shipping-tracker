---
phase: 01-scaffold
created: 2026-05-31
walking_skeleton: true
status: planned
---

# Walking Skeleton — shipping-tracker

> The thinnest possible end-to-end working slice. All subsequent phases build on
> these decisions without renegotiating them.

---

## What the Skeleton Delivers

After Phase 1 executes:

- `python -m shipping_tracker` runs to completion (exits 0) from the repo root
- `ruff check . && ruff format --check .` pass with zero violations
- `mypy shipping_tracker/ --strict` passes with zero type errors
- `pytest` discovers and runs the test suite, zero failures
- A `git commit` triggers pre-commit hooks (ruff + mypy)
- GitHub Actions runs ruff, mypy, and pytest on every push/PR
- `.env` and secrets are excluded from git; `.env.example` is committed

The pipeline stages downstream of the entry point are stubs. The architecture is
wired but empty — ready for Phase 2 to fill in Gmail, Phase 3 parsers, etc.

---

## Architectural Decisions (locked for all phases)

### Language & Runtime

| Decision | Value | Rationale |
|----------|-------|-----------|
| Language | Python 3.11+ | Deployment target is Raspberry Pi OS Bookworm / Python 3.11 |
| Entry point style | `python -m shipping_tracker` (zero args) | Cron-friendly; everything configured via `.env` |
| Concurrency model | Synchronous (D-03) | Simpler; async upgrade path preserved — no sync-specific coupling |

### Package Layout

```
shipping-tracker/
├── pyproject.toml                  # Single manifest: metadata, deps, all tool config
├── .env.example                    # Placeholder vars — committed to git
├── .gitignore                      # Excludes .env, *.db, token.json, logs/
├── .pre-commit-config.yaml         # ruff + mypy hooks
├── .github/
│   └── workflows/
│       └── ci.yml                  # ruff + mypy + pytest matrix (3.11/3.12/3.13)
├── shipping_tracker/
│   ├── __init__.py                 # Package marker
│   ├── __main__.py                 # python -m runner (3 lines: import, call, exit)
│   ├── main.py                     # main() — pipeline orchestrator (stub in Phase 1)
│   ├── logging_config.py           # configure_logging() — structlog + RotatingFileHandler
│   └── parsers/
│       ├── __init__.py
│       └── base.py                 # BaseParser ABC + TrackingInfo dataclass
└── tests/
    ├── __init__.py
    ├── conftest.py                 # Shared fixtures (synthetic data only)
    ├── fixtures/                   # Synthetic test data files
    └── test_smoke.py               # Smoke tests: import, entry point, toolchain
```

### Framework & Library Choices

| Layer | Choice | Version | Why Locked |
|-------|--------|---------|------------|
| HTTP client | `httpx` | >=0.28 | D-04: sync now, async upgrade path |
| Structured logging | `structlog` | >=25.5 | D-05: compact JSON, no whitespace |
| Env loading | `python-dotenv` | >=1.2 | Secrets never hardcoded |
| Lint + format | `ruff` | >=0.15 | Replaces pylint + black + isort |
| Type checking | `mypy` | >=2.1 | D-08: --strict from day 1 |
| Test runner | `pytest` | >=9.0 | Standard; CI matrix |
| Hook manager | `pre-commit` | >=4.6 | Hooks committed to repo |

### Entry Point Contract

```
__main__.py  →  shipping_tracker.main.main()  →  return int
```

- `__main__.py`: three executable lines only — no logic, invisible to pytest
- `main()`: returns `int` (0 = success); called by `sys.exit()` in `__main__.py`
- `[project.scripts]` console entry: `shipping-tracker = "shipping_tracker.main:main"` (not `__main__`)

### Logging Contract (all phases)

| Property | Value |
|----------|-------|
| Library | `structlog` via `ProcessorFormatter` |
| Output format | Compact JSON — no whitespace, no indentation (D-05) |
| Handler | `RotatingFileHandler` only — NO `StreamHandler` (cron silence, D-07) |
| Rotation | 10 MB per file, 3 rotations kept (D-06) |
| Default path | `logs/shipping-tracker.log` (relative; Phase 6 adds env-var override) |
| Default level | `WARNING` (D-07) |
| PII policy | Log processors MUST NOT emit email addresses, tracking numbers, or order data |

### BaseParser Contract (all phases)

```python
class BaseParser(ABC):
    def can_parse(self, email_body: str, sender: str) -> bool: ...
    def extract(self, email_body: str) -> TrackingInfo: ...

@dataclass
class TrackingInfo:
    tracking_number: str
    carrier: str
```

Phase 3 implements `AliExpressParser`. Future sellers are drop-in: implement
`BaseParser`, append to the parser list in `main.py` — no core changes required.

### Dependency Split

- Runtime (`pip install -e .`): `httpx`, `structlog`, `python-dotenv`
- Dev (`pip install -e '.[dev]'`): + `ruff`, `mypy`, `pytest`, `pre-commit`

### CI Matrix (GitHub Actions)

| Job | Python versions | Triggers |
|-----|----------------|----------|
| lint (ruff + mypy) | 3.11 only | push, pull_request |
| test (pytest) | 3.11, 3.12, 3.13 | push, pull_request |

### Privacy Invariants (non-negotiable, all phases)

- `.env`, `token.json`, `credentials.json`, `*.db`, `*.sqlite3`, `logs/` are in `.gitignore` and MUST never appear in git history
- All test fixtures use synthetic data: tracking numbers prefixed `FAKE`, carrier name `FAKECARRIER`, no real email addresses
- Log output never contains email addresses, personal names, order references, or raw email bodies

---

## Phase-by-Phase Build Plan

| Phase | Adds to Skeleton |
|-------|-----------------|
| 1 — Scaffold | This skeleton: entry point runs, toolchain green |
| 2 — Gmail | Gmail OAuth2 fetch; stub pipeline stages replaced with real Gmail fetch |
| 3 — Parser Layer | `AliExpressParser` implements `BaseParser`; dispatch loop in `main.py` |
| 4 — Deduplication | SQLite state layer; `processed_emails` and `registered_tracking` tables |
| 5 — Pipeline | 17track API integration; full end-to-end pipeline wired |
| 6 — Production | Structured logging hardened; cron entry point; README |

---

*Walking Skeleton created: 2026-05-31*
*Source: Phase 1 context (D-01 through D-10) and RESEARCH.md verified patterns*
