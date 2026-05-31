---
phase: 01-scaffold
plan: 01
subsystem: infra
tags: [python, setuptools, ruff, mypy, structlog, pytest, pyproject]

# Dependency graph
requires: []
provides:
  - Installable shipping_tracker Python package (pip install -e .[dev])
  - python -m shipping_tracker entry point runs and exits 0
  - Pluggable BaseParser ABC + TrackingInfo dataclass in shipping_tracker.parsers.base
  - structlog + RotatingFileHandler logging config (no stdout, cron-silent)
  - Toolchain baseline: ruff check/format and mypy --strict all green
  - Privacy enforcement: .env, token.json, *.db, logs/ excluded from git
affects: [02-scaffold, phase-2, phase-3, phase-4, phase-5]

# Tech tracking
tech-stack:
  added:
    - setuptools>=77 (build backend)
    - httpx>=0.28 (HTTP client — runtime)
    - structlog>=25.5 (structured JSON logging — runtime)
    - python-dotenv>=1.2 (env loading — runtime)
    - ruff>=0.15 (linting + formatting — dev)
    - mypy>=2.1 (type checking strict — dev)
    - pytest>=9.0 (test runner — dev)
    - pre-commit>=4.6 (git hooks — dev)
  patterns:
    - Pluggable ABC parser pattern (BaseParser/TrackingInfo) — non-negotiable from Phase 1
    - structlog stdlib integration via ProcessorFormatter (not structlog.get_logger() in modules)
    - load_dotenv() first, configure_logging() second ordering in main()
    - No StreamHandler on root logger (cron silence by design)
    - logging.getLogger(__name__) in modules; structlog intercepts via ProcessorFormatter

key-files:
  created:
    - pyproject.toml
    - .gitignore
    - .env.example
    - shipping_tracker/__init__.py
    - shipping_tracker/__main__.py
    - shipping_tracker/main.py
    - shipping_tracker/logging_config.py
    - shipping_tracker/parsers/__init__.py
    - shipping_tracker/parsers/base.py
  modified: []

key-decisions:
  - "Entry point split: __main__.py for python -m; pyproject.toml scripts for installed command — both call main() in main.py"
  - "No StreamHandler on root logger — cron must be silent on stdout (D-07 / LOG-03)"
  - "BaseParser ABC mandated in Phase 1 — retrofitting before Phase 3 parsers would require core refactor"
  - "load_dotenv() before configure_logging() — prevents logging.basicConfig() racing env reads"
  - "mypy --strict from day 1 — all functions fully typed including return annotations"

patterns-established:
  - "Parser pattern: Subclass BaseParser, implement can_parse() and extract(), return TrackingInfo"
  - "Logger acquisition: import logging; logger = logging.getLogger(__name__) — structlog intercepts"
  - "Test data: FAKE prefix for tracking numbers (e.g. FAKE1234567890), FAKECARRIER for carrier names"

requirements-completed: [SETUP-01, SETUP-02, SETUP-03, SETUP-07]

# Metrics
duration: 25min
completed: 2026-05-31
---

# Phase 01 Plan 01: Walking Skeleton Summary

**Python package scaffold with structlog/RotatingFileHandler logging, pluggable BaseParser ABC, and green ruff+mypy --strict toolchain baseline**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-31T13:34:21Z
- **Completed:** 2026-05-31
- **Tasks:** 2 of 2
- **Files created:** 9

## Accomplishments

- Installable shipping_tracker package: pip install -e ".[dev]" resolves all runtime and dev dependencies
- Walking skeleton runs: python -m shipping_tracker exits 0 with no stdout (cron-silent)
- Pluggable parser architecture in place: BaseParser ABC and TrackingInfo dataclass ready for Phase 3 AliExpressParser
- Toolchain green from day 1: ruff check, ruff format --check, mypy --strict all pass on initial codebase
- Privacy enforced: .env, token.json, credentials.json, *.db, logs/ all excluded from git via .gitignore

## Task Commits

Each task was committed atomically:

1. **Task 1: Project manifest, .gitignore, and .env.example** - `008ac7f` (chore) — previously committed
2. **Task 2: Python package files** - `29f6913` (feat)

**Plan metadata:** _(docs commit follows)_

## Files Created/Modified

- `pyproject.toml` — PEP 621 manifest with ruff, mypy, pytest config and runtime/dev dependency split
- `.gitignore` — Privacy enforcement: .env, token.json, credentials.json, *.db, logs/ excluded
- `.env.example` — Placeholder env vars committed to git (SEVENTEEN_TRACK_API_KEY, LOG_LEVEL, LOG_PATH)
- `shipping_tracker/__init__.py` — Package marker with module docstring
- `shipping_tracker/__main__.py` — Minimal python -m entry point: sys.exit(main())
- `shipping_tracker/main.py` — Pipeline orchestrator stub: load_dotenv() → configure_logging() → return 0
- `shipping_tracker/logging_config.py` — structlog + RotatingFileHandler (10 MB / 3 rotations), no StreamHandler
- `shipping_tracker/parsers/__init__.py` — Parsers sub-package marker
- `shipping_tracker/parsers/base.py` — BaseParser ABC + TrackingInfo dataclass (architecture constraint)

## Decisions Made

- **Entry point split:** __main__.py handles python -m; pyproject.toml scripts entry calls main() directly. Both routes converge at the same main() function in main.py.
- **No StreamHandler:** Root logger has RotatingFileHandler only — cron job must produce zero stdout output (D-07 / LOG-03).
- **BaseParser in Phase 1:** The pluggable parser ABC is non-negotiable from the start. Deferring it would require a core refactor before Phase 3 parsers could be added.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Shortened comment to fix ruff E501 line-too-long**
- **Found during:** Task 2 verification (ruff check .)
- **Issue:** Line 35 of logging_config.py was 91 chars (limit 88) due to inline comment "compact JSON — no whitespace by default"
- **Fix:** Shortened comment to "compact JSON, no whitespace"
- **Files modified:** shipping_tracker/logging_config.py
- **Verification:** ruff check . passes with zero violations after fix
- **Committed in:** 29f6913 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - trivial comment length)
**Impact on plan:** No scope creep. Fix was cosmetic to satisfy the configured line-length of 88.

## Issues Encountered

- ruff format reformatted 4 files (added blank line after module docstrings, consistent spacing). Applied formatting before committing — all files now match canonical ruff output.

## User Setup Required

None — no external service configuration required for this plan. Phase 5 will require a real SEVENTEEN_TRACK_API_KEY in .env.

## Next Phase Readiness

- Walking skeleton complete — Phase 01 Plan 02 (CI, pre-commit, tests/__init__.py, tests/conftest.py) can begin immediately
- All toolchain checks green; subsequent plans start from a clean baseline
- BaseParser ABC in place — Phase 3 AliExpressParser is a drop-in addition with no core changes required
- No blockers

---
*Phase: 01-scaffold*
*Completed: 2026-05-31*
