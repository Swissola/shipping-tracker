# Phase 1: Scaffold - Research

**Researched:** 2026-05-31
**Domain:** Python project toolchain — packaging, linting, type checking, logging, CI
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** `python -m shipping_tracker` runs the full pipeline directly — zero arguments, no flags, cron-friendly. Everything configured via `.env`.
- **D-02:** Entry point lives in two places: `shipping_tracker/__main__.py` (enables `python -m shipping_tracker`) AND a `console_scripts` entry in `pyproject.toml` (exposes `shipping-tracker` as an installed command for the cron line).
- **D-03:** Entry function is synchronous. Architecture must not block a future move to async — no deep coupling to sync-specific patterns, no `time.sleep` loops, clean separation between I/O and logic.
- **D-04:** Use `httpx` with `httpx.Client` (sync). Async-capable if the architecture evolves, but no `AsyncClient` complexity until needed.
- **D-05:** Use `structlog`. Output is compact JSON — no whitespace, no indentation — optimised for both machine parsing and LLM consumption.
- **D-06:** Rotate log file at 10MB, keep 3 rotations. Default path: `logs/shipping-tracker.log`.
- **D-07:** Default log level: `WARNING`. INFO and DEBUG are available but not the cron default.
- **D-08:** mypy runs with `--strict` from day 1. All functions must be fully typed. `# type: ignore` comments are tracked. Expect a small number of explicit `cast()` calls around Gmail API responses.
- **D-09:** Split `pyproject.toml` into runtime `[project.dependencies]` and `[project.optional-dependencies]` dev group. `pip install -e '.[dev]'` installs everything.
- **D-10:** GitHub Actions on `ubuntu-latest`. Python version matrix: 3.11, 3.12, 3.13. Triggers on every push and pull request. Jobs: ruff check, ruff format --check, mypy --strict, pytest.

### Claude's Discretion

None specified — all key choices are locked above.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SETUP-01 | Python package scaffolded under `shipping_tracker/` with `pyproject.toml` as the packaging manifest | pyproject.toml PEP 621 standard; setuptools build backend pattern documented |
| SETUP-02 | `ruff` configured for lint and format (replaces pylint/black/isort) | Ruff official docs; `[tool.ruff]` and `[tool.ruff.lint]` sections in pyproject.toml |
| SETUP-03 | `mypy` configured for static type checking | mypy docs; `[tool.mypy]` with `strict = true` |
| SETUP-04 | `pytest` configured with a `tests/fixtures/` directory for synthetic test data | pytest docs; `[tool.pytest.ini_options]` with `testpaths` |
| SETUP-05 | `pre-commit` hooks configured to run ruff and mypy before every commit | ruff-pre-commit and mirrors-mypy repos; `.pre-commit-config.yaml` pattern documented |
| SETUP-06 | GitHub Actions CI workflow runs ruff, mypy, and pytest on every push and pull request | GitHub Actions docs; Python matrix workflow pattern documented |
| SETUP-07 | `.env.example` committed with placeholder values; `.env`, SQLite DB, and OAuth token cache in `.gitignore` | Standard practice; gitignore entries listed in findings |
</phase_requirements>

---

## Summary

Phase 1 scaffolds the complete Python project baseline: package layout, pyproject.toml manifest, ruff lint/format, mypy strict, pytest, pre-commit hooks, and GitHub Actions CI. Every tool in the stack has a well-established integration pattern via pyproject.toml. No novel decisions are needed — the toolchain is mature and the configuration is straightforward.

The one non-trivial configuration concern is structlog. The correct pattern for compact JSON output to a rotating file (with stdout suppressed for cron silence) uses `structlog.stdlib.ProcessorFormatter` integrated with `logging.handlers.RotatingFileHandler`. The `JSONRenderer()` produces whitespace-free JSON by default. Setting the root logger to WARNING and attaching only a file handler — no StreamHandler — achieves cron silence.

The architecture constraint from CLAUDE.md (pluggable `BaseParser` from Phase 1) means the scaffold must include `shipping_tracker/parsers/base.py` with the abstract `BaseParser` class even though no parsers are implemented yet. This is structural scaffolding only — the class body can be a stub — but it must be present and fully typed to satisfy mypy strict.

**Primary recommendation:** Use `pyproject.toml` as the single source of truth for all tool configuration. Install with `pip install -e '.[dev]'`. Keep `__main__.py` minimal (three lines: import, call, exit). All logic lives in `main.py`.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| CLI entry point (`python -m`, cron) | Package (`__main__.py`) | `main.py` (`main()` fn) | `__main__.py` is the runner; business logic stays in `main.py` |
| Configuration loading (`.env`) | `main.py` or dedicated `config.py` | — | Read once at startup before any I/O |
| Logging initialisation | `logging_config.py` (or inline in `main.py`) | stdlib `logging` + structlog | Set up once, before first log call |
| Parser interface (`BaseParser`) | `shipping_tracker/parsers/base.py` | — | Pluggable contract; all parsers inherit from here |
| Static type checking | mypy (CI + pre-commit) | — | Enforced toolchain layer, not runtime |
| Linting / formatting | ruff (CI + pre-commit) | — | Enforced toolchain layer, not runtime |
| Test execution | pytest (CI) | pre-commit (optional) | Pytest is the standard runner |
| Dependency management | pyproject.toml | pip | Single manifest; no requirements.txt needed |

---

## Standard Stack

### Core (Runtime)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `httpx` | 0.28.1 [VERIFIED: PyPI] | Sync (and async-capable) HTTP client | Locked decision D-04; modern replacement for requests, async upgrade path |
| `structlog` | 25.5.0 [VERIFIED: PyPI] | Structured JSON logging | Locked decision D-05; de-facto standard for structured Python logging |
| `python-dotenv` | 1.2.2 [VERIFIED: PyPI] | Load `.env` into `os.environ` at startup | Industry standard; secrets never hardcoded |

### Dev/Toolchain

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `ruff` | 0.15.15 [VERIFIED: PyPI] | Lint + format (replaces pylint, black, isort) | All development; replaces three tools |
| `mypy` | 2.1.0 [VERIFIED: PyPI] | Static type checking | All development; strict from day 1 |
| `pytest` | 9.0.3 [VERIFIED: PyPI] | Test runner | All testing |
| `pre-commit` | 4.6.0 [VERIFIED: PyPI] | Git hook manager | Runs ruff + mypy on every commit |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `python-dotenv` | Read `os.environ` directly | dotenv is needed for local dev (`.env` file); prod Pi can use real env vars |
| `setuptools` build backend | `hatchling`, `flit` | Locked stack — setuptools is universally understood and needs no extra install |

**Installation (development):**
```bash
pip install -e '.[dev]'
```

**Installation (production Pi — runtime only):**
```bash
pip install -e .
```

---

## Package Legitimacy Audit

All packages verified via slopcheck 0.6.1 and PyPI registry check on 2026-05-31.

| Package | Registry | slopcheck | Disposition |
|---------|----------|-----------|-------------|
| `httpx` | PyPI | [OK] | Approved |
| `structlog` | PyPI | [OK] | Approved |
| `python-dotenv` | PyPI | [OK] | Approved |
| `ruff` | PyPI | [OK] | Approved |
| `mypy` | PyPI | [OK] | Approved |
| `pytest` | PyPI | [OK] | Approved |
| `pre-commit` | PyPI | [OK] | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
[cron / shell]
      |
      v
python -m shipping_tracker        <-- __main__.py (3 lines)
      |
      v
shipping_tracker.main.main()      <-- synchronous entry fn
      |
      +-- load_dotenv()            <-- reads .env into os.environ
      |
      +-- configure_logging()      <-- structlog + RotatingFileHandler
      |
      v
[Gmail fetch]  -->  [parser dispatch]  -->  [dedup check]  -->  [17track API]
      ^                   ^                     ^                    ^
   Phase 2             Phase 3              Phase 4              Phase 5

(Phase 1: all downstream stages are stubs that log "not implemented")
```

### Recommended Project Structure

```
shipping-tracker/
├── pyproject.toml           # single manifest for metadata, deps, tool config
├── .env.example             # placeholder vars — committed to git
├── .gitignore               # excludes .env, *.db, token.json, logs/
├── .pre-commit-config.yaml  # ruff + mypy hooks
├── .github/
│   └── workflows/
│       └── ci.yml           # ruff + mypy + pytest matrix
├── shipping_tracker/
│   ├── __init__.py
│   ├── __main__.py          # python -m entry: calls main(); sys.exit()
│   ├── main.py              # main() function — pipeline orchestration stub
│   ├── logging_config.py    # configure_logging() — structlog + RotatingFileHandler
│   └── parsers/
│       ├── __init__.py
│       └── base.py          # BaseParser ABC (required by architecture constraint)
└── tests/
    ├── __init__.py
    ├── conftest.py          # shared fixtures
    └── fixtures/            # synthetic test data (JSON, txt — no real PII)
```

### Pattern 1: Minimal `__main__.py`

**What:** Three-line runner that enables both `python -m shipping_tracker` and cron invocation.
**When to use:** Always — keep this file minimal; all logic lives in `main.py`.

```python
# Source: packaging.python.org/en/latest/guides/writing-pyproject-toml/
import sys
from shipping_tracker.main import main

sys.exit(main())
```

`main()` returns `int` (0 = success, non-zero = error). mypy strict will enforce the return type.

### Pattern 2: pyproject.toml structure

**What:** Single manifest covering packaging metadata, runtime deps, dev deps, and all tool config.
**When to use:** This is the only config file needed — no `setup.py`, no `requirements.txt`.

```toml
# Source: packaging.python.org/en/latest/guides/writing-pyproject-toml/
[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"

[project]
name = "shipping-tracker"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.28",
    "structlog>=25.5",
    "python-dotenv>=1.2",
]

[project.optional-dependencies]
dev = [
    "ruff>=0.15",
    "mypy>=2.1",
    "pytest>=9.0",
    "pre-commit>=4.6",
]

[project.scripts]
shipping-tracker = "shipping_tracker.__main__:main"

# --- Tool configuration below ---

[tool.ruff]
target-version = "py311"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "W", "UP"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.mypy]
strict = true
python_version = "3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]

[tool.setuptools.packages.find]
where = ["."]
include = ["shipping_tracker*"]
```

### Pattern 3: structlog compact JSON to rotating file

**What:** structlog integrated with stdlib `logging.handlers.RotatingFileHandler`. Compact JSON output, WARNING default, no stdout.
**When to use:** In `configure_logging()`, called once at program startup before any log call.

```python
# Source: structlog.org/en/stable/standard-library.html
import logging
import logging.handlers
import structlog

def configure_logging(log_path: str = "logs/shipping-tracker.log") -> None:
    shared_processors: list[structlog.types.Processor] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),  # compact JSON, no whitespace
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.handlers.RotatingFileHandler(
        filename=log_path,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=3,
    )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.WARNING)  # D-07: WARNING default, no stdout

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
```

Key detail: no `StreamHandler` is added — this is what achieves cron silence (D-07, LOG-03).

### Pattern 4: BaseParser ABC (architecture constraint)

**What:** Abstract base class that enforces the pluggable parser contract from Phase 1.
**When to use:** Phase 1 creates the stub; Phase 3 implements the first concrete parser.

```python
# Source: CLAUDE.md architecture constraint + REQUIREMENTS.md PARSE-01
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class TrackingInfo:
    tracking_number: str
    carrier: str

class BaseParser(ABC):
    @abstractmethod
    def can_parse(self, email_body: str, sender: str) -> bool:
        """Return True if this parser handles the given email."""
        ...

    @abstractmethod
    def extract(self, email_body: str) -> TrackingInfo:
        """Extract tracking info from a matching email."""
        ...
```

`TrackingInfo` must be a typed dataclass or NamedTuple — mypy strict requires concrete return types.

### Pattern 5: .pre-commit-config.yaml

```yaml
# Source: github.com/astral-sh/ruff-pre-commit, github.com/pre-commit/mirrors-mypy
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.15
    hooks:
      - id: ruff-check
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v2.1.0
    hooks:
      - id: mypy
        args: [--strict]
        additional_dependencies:
          - httpx
          - structlog
          - python-dotenv
```

Important: `ruff-check` must come before `ruff-format` when using `--fix`. [VERIFIED: ruff-pre-commit README]

The `additional_dependencies` in the mypy hook installs typed packages into pre-commit's isolated virtualenv so mypy can resolve imports. [VERIFIED: mirrors-mypy README]

### Pattern 6: GitHub Actions CI workflow

```yaml
# Source: docs.github.com/en/actions/tutorials/build-and-test-code/python
name: CI

on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e '.[dev]'
      - run: ruff check .
      - run: ruff format --check .
      - run: mypy shipping_tracker/ --strict

  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e '.[dev]'
      - run: pytest
```

D-10 specifies ruff, mypy, and pytest all in CI. Pattern above separates lint (single Python version, fast) from test matrix (three versions). Both trigger on push and pull_request.

### Anti-Patterns to Avoid

- **Putting logic in `__main__.py`:** The file must stay minimal. Import `main`, call it, exit. Any logic here is invisible to `pytest` and untestable.
- **Adding a StreamHandler to the root logger:** This breaks cron silence. The only handler should be `RotatingFileHandler`.
- **Using `JSONRenderer(sort_keys=True, separators=(',', ':'))` manually:** The default `JSONRenderer()` already produces compact output. Verify this on the structlog version being used — do not add separator args unless compact output is confirmed absent.
- **Skipping `BaseParser` in Phase 1:** The architecture constraint is non-negotiable (CLAUDE.md). A monolithic entry in `main.py` would require a refactor before Phase 3 parsers can be added.
- **Committing `.env` or `token.json`:** The privacy constraint is non-negotiable. These must be in `.gitignore` before the first non-trivial commit.
- **Pinning exact versions in `pyproject.toml` runtime deps:** Use minimum version bounds (`>=`) not exact pins (`==`). Pins in a library block downstream consumers from resolving conflicts.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON log formatting | Custom `logging.Formatter` subclass | `structlog.stdlib.ProcessorFormatter` + `JSONRenderer()` | structlog handles ISO timestamps, exc_info, log level, stack rendering correctly |
| Log file rotation | Custom file handler or cron rotation | `logging.handlers.RotatingFileHandler` | stdlib — zero deps, battle-tested, handles mid-write rotation correctly |
| Import sorting | Manual organisation | `ruff --select I` | ruff implements isort rules; hand-sorting diverges on every merge |
| `.env` file loading | `open(".env"); for line in f` | `python-dotenv` | Handles quoting, comments, multiline values, `override` semantics |
| Abstract interface enforcement | Runtime duck-typing check | `abc.ABC` + `@abstractmethod` | mypy strict cannot verify duck-typing; ABC makes missing-method errors compile-time |
| Pre-commit hook wiring | Custom git hooks in `.git/hooks/` | `pre-commit` framework | `.git/hooks/` is not committed; pre-commit config is |

**Key insight:** The Python stdlib covers log rotation; structlog covers formatting; ruff covers import sorting. These are not problems that need solving — they are already solved.

---

## Common Pitfalls

### Pitfall 1: mypy strict fails on Gmail API responses (Phase 2 concern, but scaffold must anticipate)
**What goes wrong:** `google-api-python-client` returns `Any` for nearly everything. Under `--strict`, assigning `Any` to a typed variable generates errors.
**Why it happens:** The Gmail API client has incomplete type stubs. `--strict` includes `--warn-return-any` and `--disallow-any-generics`.
**How to avoid:** Use `cast()` from `typing` to narrow `Any` to a concrete type at the boundary. Document each cast with a comment. The `google-api-python-client-stubs` [VERIFIED: PyPI, 1.37.0] package provides partial stubs — add it to dev dependencies in Phase 2.
**Warning signs:** mypy reports `error: Returning Any from function declared to return "..."` — this means a cast is needed at that boundary.

### Pitfall 2: pre-commit mypy hook misses import errors
**What goes wrong:** pre-commit runs mypy in an isolated virtualenv. Without `additional_dependencies`, mypy cannot find `httpx`, `structlog`, etc. and either fails with import errors or silently skips modules.
**Why it happens:** pre-commit's virtualenv does not inherit the project's virtualenv.
**How to avoid:** List every typed runtime dependency in the `mypy` hook's `additional_dependencies`. [VERIFIED: mirrors-mypy README]
**Warning signs:** mypy passes in pre-commit but fails when run directly with `mypy shipping_tracker/ --strict`.

### Pitfall 3: structlog outputs to stdout unexpectedly
**What goes wrong:** An accidental `logging.basicConfig()` call (e.g., from an imported library) adds a StreamHandler to the root logger, causing log lines to appear on stdout during cron runs.
**Why it happens:** `basicConfig()` is a common default; many libraries call it at import time if no handlers are configured.
**How to avoid:** Call `configure_logging()` as the first action in `main()`, before importing any third-party library that might call `basicConfig()`. Alternatively, set `logging.root.handlers = []` before configuring. Ensure only `RotatingFileHandler` is attached.
**Warning signs:** Cron emails with unexpected output, or stdout not empty when running the tool manually.

### Pitfall 4: `logs/` directory missing at runtime
**What goes wrong:** `RotatingFileHandler` raises `FileNotFoundError` if `logs/` does not exist.
**Why it happens:** The directory is in `.gitignore` and won't be created by git checkout.
**How to avoid:** `configure_logging()` must `os.makedirs("logs", exist_ok=True)` before creating the handler.
**Warning signs:** `FileNotFoundError: [Errno 2] No such file or directory: 'logs/shipping-tracker.log'` on first run.

### Pitfall 5: `console_scripts` entry calls `__main__` instead of `main()`
**What goes wrong:** `[project.scripts] shipping-tracker = "shipping_tracker.__main__:main"` fails if `__main__.py` contains `sys.exit(main())` at module level instead of inside a `main()` function.
**Why it happens:** `console_scripts` calls the named function — it does not execute the module. The function must be importable.
**How to avoid:** Either (a) define a `main()` function in `__main__.py` that wraps `sys.exit(pipeline_main())`, or (b) point the console script at `shipping_tracker.main:main` directly and keep `__main__.py` as the `python -m` runner. Option (b) is cleaner.
**Warning signs:** `AttributeError: module 'shipping_tracker.__main__' has no attribute 'main'` when running `shipping-tracker` as an installed command.

### Pitfall 6: mypy 2.x breaking changes vs 1.x
**What goes wrong:** mypy 2.0 changed several defaults. Code passing under mypy 1.x may fail under 2.x.
**Why it happens:** Breaking defaults were introduced in the 2.0 release. Current version is 2.1.0.
**How to avoid:** This is a greenfield project starting on 2.1.0 — no migration concern. But do not reference tutorials or examples targeting mypy 1.x; the strict flag behaviour may differ.
**Warning signs:** Errors referencing `--no-strict-optional` or patterns that "used to work" in older mypy.

---

## Code Examples

### Verified: pyproject.toml `[tool.mypy]` section
```toml
# Source: mypy.readthedocs.io/en/stable/config_file.html
[tool.mypy]
strict = true
python_version = "3.11"

[[tool.mypy.overrides]]
module = ["google.*", "googleapiclient.*"]
ignore_missing_imports = true
```

The `overrides` block suppresses import errors for the Gmail client until proper stubs are added in Phase 2.

### Verified: pytest fixture pattern for synthetic data
```python
# Source: docs.pytest.org/en/stable/reference/fixtures.html
# tests/conftest.py
import pytest

@pytest.fixture
def synthetic_email_body() -> str:
    """A synthetic AliExpress-style email body with fake tracking data."""
    return (
        "Your order has shipped!\n"
        "Tracking number: FAKE1234567890\n"
        "Carrier: FAKECARRIER\n"
    )
```

All fixtures must use synthetic data. No real tracking numbers, email addresses, or order IDs.

### Verified: .gitignore entries required by SETUP-07
```gitignore
# Secrets and credentials (SETUP-07)
.env
token.json
credentials.json

# Database
*.db
*.sqlite3

# Logs directory
logs/

# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
.venv/
venv/
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `setup.py` + `setup.cfg` | `pyproject.toml` (PEP 621) | PEP 621 accepted 2020, standard by 2022 | Single config file; no `setup.py` needed |
| `pylint` + `black` + `isort` (3 tools) | `ruff` (1 tool) | ruff stable 2023; dominant by 2024 | Faster, simpler config, fewer CI steps |
| `requirements.txt` | `pyproject.toml [project.optional-dependencies]` | PEP 517/518/621 | Packaging and dep management unified |
| `mypy` 1.x permissive defaults | `mypy` 2.x stricter defaults | mypy 2.0 released 2025 | Code valid in 1.x may error in 2.x |
| `requests` | `httpx` (sync + async) | `httpx` stable ~2021 | Same sync API; async upgrade is drop-in |

**Deprecated/outdated:**
- `setup.py`: Do not create. `pyproject.toml` is the standard.
- `requirements.txt` for a package: Use `[project.dependencies]` and `[project.optional-dependencies]`.
- `black` + `isort` separately: Replaced entirely by `ruff`.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `console_scripts` entry should point to `shipping_tracker.main:main` (not `__main__:main`) for cleaner separation | Architecture Patterns, Pitfall 5 | Minor — either works; if `__main__` is used, a wrapper function is needed |
| A2 | `google-api-python-client-stubs` (PyPI 1.37.0) provides useful partial stubs for Phase 2 | Common Pitfalls | If stubs are absent or unusable, more `cast()` calls will be needed; plan for this in Phase 2 |

---

## Open Questions

1. **`logs/` directory location — relative vs absolute path**
   - What we know: D-06 specifies `logs/shipping-tracker.log` as the default path
   - What's unclear: Whether the path should be relative to the repo root or to the user's home directory for the deployed Pi
   - Recommendation: Use relative path for Phase 1 (suitable for development). Phase 6 (Production) can add an env-var override for the Pi deployment path.

2. **`python-dotenv` — load at module level vs in `main()`**
   - What we know: `load_dotenv()` should be called before any env var is read
   - What's unclear: Whether to call it in `__main__.py` or in `main()`
   - Recommendation: Call `load_dotenv()` as the first line in `main()`. This makes the function testable (tests can set env vars before calling `main()`) and keeps `__main__.py` minimal.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | All | [ASSUMED] — dev machine runs 3.14 based on pip output | 3.14 (dev); 3.11 target | — |
| git | pre-commit hooks | [ASSUMED] — git repo exists | Unknown | — |
| GitHub Actions | SETUP-06 | ✓ (cloud service) | — | — |
| pip | Package install | ✓ — confirmed via pip calls | — | — |

**Missing dependencies with no fallback:** None identified for Phase 1 (pure toolchain work).

**Note:** Raspberry Pi 5 with Python 3.11 is the deployment target (Phase 6). Phase 1 installs and runs on the developer's machine.

---

## Validation Architecture

Framework: pytest 9.0.3

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — created in Wave 0 |
| Quick run command | `pytest` |
| Full suite command | `pytest -v` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SETUP-01 | `shipping_tracker` is importable as a package | smoke | `python -c "import shipping_tracker"` | Wave 0 |
| SETUP-01 | `python -m shipping_tracker` exits 0 | smoke | `python -m shipping_tracker` | Wave 0 |
| SETUP-02 | `ruff check .` passes | toolchain | `ruff check .` | Wave 0 |
| SETUP-02 | `ruff format --check .` passes | toolchain | `ruff format --check .` | Wave 0 |
| SETUP-03 | `mypy shipping_tracker/ --strict` passes | toolchain | `mypy shipping_tracker/ --strict` | Wave 0 |
| SETUP-04 | `pytest` discovers test suite, zero failures | unit | `pytest` | Wave 0 |
| SETUP-05 | pre-commit hooks fire on commit | manual | `pre-commit run --all-files` | Wave 0 |
| SETUP-06 | GitHub Actions workflow file exists and is valid YAML | toolchain | CI validates on push | Wave 0 |
| SETUP-07 | `.env` is not tracked by git | manual | `git check-ignore .env` | Wave 0 |

### Sampling Rate

- **Per task commit:** `ruff check . && mypy shipping_tracker/ --strict && pytest`
- **Per wave merge:** Full suite: `pytest -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/__init__.py` — makes tests directory a package
- [ ] `tests/conftest.py` — shared fixtures
- [ ] `tests/fixtures/` — directory for synthetic test data files
- [ ] `tests/test_smoke.py` — covers SETUP-01, SETUP-04 (importability, entry point)
- [ ] Framework install: `pip install -e '.[dev]'`

---

## Security Domain

`security_enforcement` is enabled (absent = enabled). ASVS level 1.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Phase 2 (Gmail OAuth); not in scaffold |
| V3 Session Management | No | Cron tool, no sessions |
| V4 Access Control | No | Single-user local tool |
| V5 Input Validation | Partial | `.env` values read at startup — validate required keys are present and non-empty before use |
| V6 Cryptography | No | No crypto in scaffold; OAuth handled by google-auth library in Phase 2 |
| V7 Error Handling & Logging | Yes | structlog; no PII in logs (LOG-02, privacy constraint) |

### Known Threat Patterns for Python CLI Tools

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Secrets in source or git history | Information Disclosure | `.env` in `.gitignore`; `.env.example` with placeholders only |
| PII in log output | Information Disclosure | structlog processors must strip/exclude email addresses and tracking numbers |
| Hardcoded credentials | Information Disclosure | All secrets via `os.environ` / `python-dotenv`; never string literals |
| Secrets in test fixtures | Information Disclosure | Synthetic data only; enforced by CLAUDE.md |

**Phase 1 security posture:** The scaffold itself has no credentials or PII. The risk is in the *plumbing* — `.gitignore` must be correct before any secret is ever written, and log configuration must strip PII from the first log call. Both are Phase 1 deliverables.

---

## Sources

### Primary (HIGH confidence)
- [Ruff configuration docs](https://docs.astral.sh/ruff/configuration/) — `[tool.ruff]` and `[tool.ruff.lint]` configuration verified
- [structlog standard-library integration docs](https://www.structlog.org/en/stable/standard-library.html) — ProcessorFormatter, RotatingFileHandler pattern verified
- [mypy config file docs](https://mypy.readthedocs.io/en/stable/config_file.html) — `strict = true`, `overrides`, `ignore_missing_imports` verified
- [Python Packaging Guide — writing pyproject.toml](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/) — PEP 621 `[project]`, `[project.optional-dependencies]`, `[project.scripts]` verified
- [GitHub Actions — building Python](https://docs.github.com/en/actions/tutorials/build-and-test-code/python) — matrix strategy, ubuntu-latest, setup-python action verified
- [ruff-pre-commit README](https://github.com/astral-sh/ruff-pre-commit) — `ruff-check` and `ruff-format` hook IDs, rev `v0.15.15` verified
- [mirrors-mypy `.version`](https://github.com/pre-commit/mirrors-mypy/blob/main/.version) — rev `v2.1.0` verified
- [PyPI registry](https://pypi.org) — all package versions verified via `pip index versions`

### Secondary (MEDIUM confidence)
- [pytest configuration docs](https://docs.pytest.org/en/stable/reference/customize.html) — `testpaths`, `pythonpath` in `[tool.pytest.ini_options]`
- [google-api-python-client-stubs PyPI](https://pypi.org/project/google-api-python-client-stubs/) — stubs exist at 1.37.0; utility for Phase 2 confirmed

### Tertiary (LOW confidence)
- None — all claims backed by primary or secondary sources.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified on PyPI via `pip index versions`; all passed slopcheck
- Architecture: HIGH — patterns from official packaging docs and structlog docs
- Pitfalls: HIGH — verified against official docs (mypy, structlog, pre-commit); one pitfall (Pitfall 1) is MEDIUM because it concerns Phase 2 behaviour anticipated from Phase 1

**Research date:** 2026-05-31
**Valid until:** 2026-08-31 (stable ecosystem; ruff/mypy release frequently but config patterns are stable)
