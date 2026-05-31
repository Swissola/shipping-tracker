# Phase 1: Scaffold - Pattern Map

**Mapped:** 2026-05-31
**Files analyzed:** 13 new files (greenfield — zero existing source code)
**Analogs found:** 0 / 13 (no codebase to search)

> **Greenfield note:** This project has no existing source code. No analog search was possible.
> All patterns below are drawn directly from RESEARCH.md, which verified them against official
> upstream documentation (pyproject.toml PEP 621, structlog docs, mypy docs, ruff docs, GitHub
> Actions docs). These patterns ARE the canonical patterns for the chosen stack — the planner
> should treat them as first-class references, equivalent to codebase analogs.

---

## File Classification

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `pyproject.toml` | config | — | None (greenfield) | no analog |
| `.gitignore` | config | — | None (greenfield) | no analog |
| `.env.example` | config | — | None (greenfield) | no analog |
| `.pre-commit-config.yaml` | config | — | None (greenfield) | no analog |
| `.github/workflows/ci.yml` | config | — | None (greenfield) | no analog |
| `shipping_tracker/__init__.py` | package | — | None (greenfield) | no analog |
| `shipping_tracker/__main__.py` | entry-point | request-response | None (greenfield) | no analog |
| `shipping_tracker/main.py` | orchestrator | request-response | None (greenfield) | no analog |
| `shipping_tracker/logging_config.py` | utility | — | None (greenfield) | no analog |
| `shipping_tracker/parsers/__init__.py` | package | — | None (greenfield) | no analog |
| `shipping_tracker/parsers/base.py` | model/interface | — | None (greenfield) | no analog |
| `tests/__init__.py` | package | — | None (greenfield) | no analog |
| `tests/conftest.py` | test | — | None (greenfield) | no analog |

---

## Pattern Assignments

### `pyproject.toml` (config)

**Pattern source:** RESEARCH.md §Pattern 2 + §Code Examples (verified against packaging.python.org)

**Key concerns:**
- D-09: runtime deps in `[project.dependencies]`, dev tools in `[project.optional-dependencies]` dev group
- D-10: Python version target `py311` for ruff, `3.11` for mypy
- Pitfall 5: `[project.scripts]` must point at `shipping_tracker.main:main`, NOT at `__main__:main`
- Pitfall 6: mypy 2.x is the baseline — do not use 1.x patterns

**Full structure to copy:**

```toml
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
shipping-tracker = "shipping_tracker.main:main"

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

[[tool.mypy.overrides]]
module = ["google.*", "googleapiclient.*"]
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]

[tool.setuptools.packages.find]
where = ["."]
include = ["shipping_tracker*"]
```

**Notes for planner:**
- The `[tool.mypy.overrides]` block for `google.*` anticipates Phase 2. Include it now so Phase 2 mypy does not regress.
- `[project.scripts]` uses `shipping_tracker.main:main` (the real pipeline function), not `shipping_tracker.__main__:main`. See Pitfall 5 — `__main__.py` is the `python -m` runner; the installed console script calls `main()` directly.

---

### `.gitignore` (config)

**Pattern source:** RESEARCH.md §Code Examples (verified against SETUP-07 requirement)

**Privacy-critical entries — must all be present before first non-trivial commit:**

```gitignore
# Secrets and credentials (SETUP-07 — NON-NEGOTIABLE, project will be public)
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

**Notes for planner:** This file must be the first file committed in Wave 0. The privacy constraint (CLAUDE.md) is non-negotiable — `.env`, `token.json`, and SQLite DB must never appear in git history.

---

### `.env.example` (config)

**Pattern source:** RESEARCH.md §Architecture Patterns (SETUP-07 requirement)

**Structure — placeholder values only, no real secrets:**

```bash
# shipping-tracker environment variables
# Copy this file to .env and fill in real values
# NEVER commit .env to git

SEVENTEEN_TRACK_API_KEY=your_api_key_here
LOG_LEVEL=WARNING
LOG_PATH=logs/shipping-tracker.log
```

**Notes for planner:** Values are placeholders only. Phase 5 will document the full set of required env vars; Phase 1 can include only the log-level vars since no API keys are used yet. Add a comment block explaining the `.env` → `.env.example` relationship.

---

### `.pre-commit-config.yaml` (config)

**Pattern source:** RESEARCH.md §Pattern 5 (verified against ruff-pre-commit and mirrors-mypy READMEs)

**Full file to copy:**

```yaml
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

**Notes for planner:**
- `ruff-check` MUST come before `ruff-format` when `--fix` is used (RESEARCH.md verified note).
- `additional_dependencies` in the mypy hook is mandatory — without it, pre-commit's isolated virtualenv cannot resolve imports and mypy silently fails (Pitfall 2).
- Pin `rev` to exact versions matching pyproject.toml dev dependencies.

---

### `.github/workflows/ci.yml` (config)

**Pattern source:** RESEARCH.md §Pattern 6 (verified against GitHub Actions docs)

**Full file to copy:**

```yaml
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

**Notes for planner:**
- D-10: lint job runs a single Python version (3.11, fast); test job uses matrix 3.11/3.12/3.13.
- Both jobs trigger on `push` and `pull_request`.
- `mypy` runs in the lint job only (not the test matrix) — type checking is not Python-version-sensitive here.

---

### `shipping_tracker/__init__.py` (package marker)

**Pattern source:** Standard Python packaging

**Content:** Empty file (or a version string if desired).

```python
"""shipping-tracker: Gmail → 17track automation."""
```

**Notes for planner:** Minimal. Do not put imports here — circular import risk as the package grows.

---

### `shipping_tracker/__main__.py` (entry-point, request-response)

**Pattern source:** RESEARCH.md §Pattern 1 (verified against packaging.python.org)

**Critical constraint:** This file must stay minimal. Logic here is invisible to pytest (Pitfall in RESEARCH.md §Anti-Patterns).

```python
"""Entry point for `python -m shipping_tracker`."""
import sys

from shipping_tracker.main import main

sys.exit(main())
```

**Notes for planner:**
- Three lines of executable content (import sys, import main, sys.exit call).
- `main()` must return `int` — mypy strict enforces the return type annotation.
- Do NOT define a `main()` function here — the `[project.scripts]` entry in pyproject.toml points at `shipping_tracker.main:main`, not this file.
- Module-level `sys.exit()` is intentional — it converts the int return code from `main()` into a process exit code.

---

### `shipping_tracker/main.py` (orchestrator, request-response)

**Pattern source:** RESEARCH.md §Architecture Patterns (pipeline diagram) + D-01, D-03

**Phase 1 stub pattern — fully typed, passes mypy strict:**

```python
"""Pipeline orchestrator — stub for Phase 1."""
import logging

from dotenv import load_dotenv

from shipping_tracker.logging_config import configure_logging

logger = logging.getLogger(__name__)


def main() -> int:
    """Run the shipping-tracker pipeline.

    Returns:
        0 on success, non-zero on unrecoverable error.
    """
    load_dotenv()
    configure_logging()

    logger.warning("shipping_tracker started — pipeline stub, no work performed")
    return 0
```

**Notes for planner:**
- `load_dotenv()` is the FIRST call in `main()` — before any env var reads or library imports that might call `logging.basicConfig()` (Pitfall 3).
- `configure_logging()` is the SECOND call — sets up the file handler before any log statement.
- Return type is `int` (required by `sys.exit()` in `__main__.py` and by mypy strict).
- Phase 1 body is a stub — the real pipeline stages (Gmail fetch, parse, dedup, register) are wired in Phases 2–5.
- D-03: no `time.sleep`, no sync-specific coupling. The function signature and call chain must remain async-compatible in shape.

---

### `shipping_tracker/logging_config.py` (utility)

**Pattern source:** RESEARCH.md §Pattern 3 (verified against structlog.org standard-library docs)

**Full pattern to copy — this is the most complex file in the scaffold:**

```python
"""Logging configuration — structlog + RotatingFileHandler, compact JSON, no stdout."""
import logging
import logging.handlers
import os

import structlog


def configure_logging(
    log_path: str = "logs/shipping-tracker.log",
    log_level: int = logging.WARNING,
) -> None:
    """Configure structlog with a rotating file handler.

    Produces compact JSON (no whitespace). No StreamHandler is added — the tool
    runs silently on stdout for cron compatibility (LOG-03).

    Args:
        log_path: Path to the log file. Parent directory is created if absent.
        log_level: Root logger level. Default WARNING per D-07.
    """
    os.makedirs(os.path.dirname(log_path) or "logs", exist_ok=True)

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
            structlog.processors.JSONRenderer(),  # compact JSON — no whitespace by default
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.handlers.RotatingFileHandler(
        filename=log_path,
        maxBytes=10 * 1024 * 1024,  # 10 MB per D-06
        backupCount=3,              # keep 3 rotations per D-06
    )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)
    # NO StreamHandler — cron silence (D-07, LOG-03)

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
```

**Notes for planner:**
- `os.makedirs(..., exist_ok=True)` is mandatory — `logs/` is in `.gitignore` and won't exist on fresh checkout (Pitfall 4).
- `os.path.dirname(log_path) or "logs"` handles the edge case where `log_path` has no directory component.
- Do NOT add a `StreamHandler` — this is the mechanism for cron silence (LOG-03).
- `JSONRenderer()` default output is already compact (no whitespace). Do not add `separators` arg unless testing confirms otherwise (RESEARCH.md §Anti-Patterns).
- The `log_level` parameter makes the function testable — tests can pass `logging.DEBUG` without touching the default.

---

### `shipping_tracker/parsers/__init__.py` (package marker)

**Content:** Empty file.

```python
"""Parser sub-package — pluggable email parser implementations."""
```

---

### `shipping_tracker/parsers/base.py` (model/interface)

**Pattern source:** RESEARCH.md §Pattern 4 (architecture constraint from CLAUDE.md — non-negotiable)

**Full pattern to copy:**

```python
"""BaseParser abstract interface — all email parsers inherit from this class."""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TrackingInfo:
    """Structured tracking data extracted from a shipping email."""

    tracking_number: str
    carrier: str


class BaseParser(ABC):
    """Abstract base class for email shipping parsers.

    Implement `can_parse` and `extract` to register a new parser.
    Phase 3 adds AliExpressParser; further parsers are drop-in additions
    to the parser registry in main.py with no core changes required.
    """

    @abstractmethod
    def can_parse(self, email_body: str, sender: str) -> bool:
        """Return True if this parser handles the given email.

        Args:
            email_body: Plain-text body of the email.
            sender: From address of the email.

        Returns:
            True if this parser should handle the email.
        """
        ...

    @abstractmethod
    def extract(self, email_body: str) -> TrackingInfo:
        """Extract tracking info from a matching email.

        Args:
            email_body: Plain-text body of the email.

        Returns:
            TrackingInfo with tracking_number and carrier populated.

        Raises:
            ValueError: If the email matches but extraction fails.
        """
        ...
```

**Notes for planner:**
- `@dataclass` on `TrackingInfo` is required — mypy strict cannot verify dict/tuple return types.
- Both methods must have complete type annotations — mypy strict enforces this.
- The stub is architecture scaffolding only — no implementation logic in Phase 1.
- CLAUDE.md makes this non-negotiable: skipping `BaseParser` in Phase 1 would require a refactor before Phase 3 parsers can be added.

---

### `tests/__init__.py` (package marker)

**Content:** Empty file. Makes `tests/` a package so pytest import resolution works consistently.

---

### `tests/conftest.py` (test)

**Pattern source:** RESEARCH.md §Code Examples (verified against pytest docs)

**Phase 1 pattern — minimal, synthetic data only:**

```python
"""Shared pytest fixtures for shipping-tracker tests.

PRIVACY: All fixtures use synthetic data. No real tracking numbers,
email addresses, order IDs, or personal names may appear in this file
or in tests/fixtures/. See CLAUDE.md privacy constraints.
"""
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

**Notes for planner:**
- The privacy docstring comment is mandatory — it serves as a guardrail for future contributors.
- Additional fixtures are added in Phases 2–5 as each layer is implemented.
- `tests/fixtures/` directory should be created with a `.gitkeep` or a placeholder synthetic data file.

---

## Shared Patterns

### Privacy Guard (applies to ALL files)

**Source:** CLAUDE.md §Privacy + RESEARCH.md §Security Domain
**Apply to:** Every file in the repository

```
RULE: No PII in source, tests, logs, or git history.
- No real email addresses, tracking numbers, order IDs, or personal names anywhere in source
- Test fixtures use synthetic data only (e.g. "FAKE1234567890", "FAKECARRIER")
- .env excluded from git via .gitignore — must be committed before any secret is written
- Log processors must never emit raw email content
```

### mypy Strict Typing (applies to all Python files)

**Source:** RESEARCH.md §D-08 + Pitfall 6
**Apply to:** All `.py` files under `shipping_tracker/`

```python
# Every function must have full type annotations
# Return types are mandatory (mypy strict enforces --warn-no-return)
# Use cast() at API response boundaries, not # type: ignore
from typing import cast
```

### structlog Logger Acquisition (applies to all Python modules that log)

**Source:** RESEARCH.md §Pattern 3
**Apply to:** All modules that emit log statements

```python
import logging

logger = logging.getLogger(__name__)
# Use stdlib logger — structlog intercepts it via ProcessorFormatter
# Do NOT call structlog.get_logger() in individual modules
```

### Synthetic Test Data (applies to all test files)

**Source:** RESEARCH.md §Code Examples + CLAUDE.md constraints
**Apply to:** `tests/conftest.py` and all test files

```python
# All test data must be synthetic
# Tracking numbers: "FAKE" prefix (e.g. FAKE1234567890)
# Carriers: "FAKECARRIER" or similar clearly-synthetic names
# Email addresses: never use real addresses
```

---

## No Analog Found

All 13 files have no analog in the codebase (greenfield project). The patterns above are the canonical starting patterns, sourced from official upstream documentation as verified in RESEARCH.md.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| All 13 files | various | various | Greenfield project — no existing source code |

The RESEARCH.md patterns are HIGH confidence (verified against official docs). Planner should use them directly.

---

## Metadata

**Analog search scope:** Entire repository (`C:\Projects\shipping-tracker`)
**Files scanned:** 2 source files (CLAUDE.md, PROJECT-BRIEF.md) — both are documentation, not source code
**Pattern extraction date:** 2026-05-31
**Pattern source confidence:** HIGH — all patterns verified against official upstream docs in RESEARCH.md
