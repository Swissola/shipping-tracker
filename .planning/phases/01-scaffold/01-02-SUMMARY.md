---
phase: 01-scaffold
plan: 02
subsystem: infra
tags: [pre-commit, github-actions, pytest, ruff, mypy, ci, test-infrastructure]

# Dependency graph
requires:
  - 01-01 (shipping_tracker package, pyproject.toml, toolchain baseline)
provides:
  - pre-commit hooks: ruff-check + ruff-format + mypy --strict fire on every commit
  - GitHub Actions CI: lint job (py3.11) + test matrix (py3.11/3.12/3.13) on push/pull_request
  - pytest test suite: 6 smoke tests, all passing, tests/fixtures/ tracked in git
  - Synthetic fixture pattern enforced with mandatory privacy docstring in conftest.py
affects: [phase-2, phase-3, phase-4, phase-5]

# Tech tracking
tech-stack:
  added:
    - pre-commit hooks via ruff-pre-commit v0.15.15 and mirrors-mypy v2.1.0
    - GitHub Actions CI workflow (ubuntu-latest, Python 3.11/3.12/3.13 matrix)
  patterns:
    - pre-commit hook order: ruff-check (--fix) before ruff-format (required with --fix)
    - mypy additional_dependencies in pre-commit hook (httpx, structlog, python-dotenv) — Pitfall 2
    - Synthetic test data: FAKE prefix for tracking numbers, FAKECARRIER for carrier names
    - Privacy docstring guardrail in conftest.py — mandatory for all future contributors

key-files:
  created:
    - .pre-commit-config.yaml
    - .github/workflows/ci.yml
    - tests/__init__.py
    - tests/conftest.py
    - tests/fixtures/.gitkeep
    - tests/test_smoke.py
  modified: []

key-decisions:
  - "pre-commit additional_dependencies mandatory for mypy hook — without httpx/structlog/python-dotenv, pre-commit isolated venv cannot resolve imports (Pitfall 2)"
  - "Hook order: ruff-check before ruff-format required when --fix is used"
  - "CI lint job runs single Python version (3.11) for speed; test matrix spans 3.11/3.12/3.13 per D-10"
  - "Privacy docstring in conftest.py is mandatory guardrail — enforces synthetic-data-only rule for future contributors"

requirements-completed: [SETUP-04, SETUP-05, SETUP-06]

# Metrics
duration: ~9min
completed: 2026-05-31
---

# Phase 01 Plan 02: Toolchain Enforcement and Test Infrastructure Summary

**Pre-commit hooks (ruff + mypy) and GitHub Actions CI matrix added; pytest suite with 6 smoke tests using synthetic fixtures passing green**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-05-31T13:45:03Z
- **Completed:** 2026-05-31
- **Tasks:** 2 of 2
- **Files created:** 6

## Accomplishments

- Pre-commit enforcement: `python -m pre_commit run --all-files` exits 0; ruff-check, ruff-format, and mypy --strict hooks all pass
- GitHub Actions CI workflow committed: lint job (py3.11) + test matrix (py3.11/3.12/3.13), triggers on push and pull_request
- Pytest suite: 6 smoke tests collected and passed — importability, BaseParser ABC, TrackingInfo dataclass, entry point exits 0, entry point produces no stdout (cron silence D-07)
- tests/fixtures/.gitkeep tracked in git — directory ready for Phase 2–5 synthetic test data
- Privacy constraint satisfied: all test data uses FAKE prefix; mandatory privacy docstring in conftest.py

## Task Commits

Each task was committed atomically:

1. **Task 1: Pre-commit config and GitHub Actions CI workflow** - `5acb308` (chore)
2. **Task 2: Test infrastructure — conftest, fixtures directory, and smoke tests** - `ab64c2e` (feat)

## Files Created/Modified

- `.pre-commit-config.yaml` — ruff-check (--fix) + ruff-format + mypy (--strict) hooks; pinned revs v0.15.15 / v2.1.0; mypy additional_dependencies: httpx, structlog, python-dotenv
- `.github/workflows/ci.yml` — lint job (py3.11) + test matrix (3.11/3.12/3.13); triggers on push and pull_request; installs via `pip install -e '.[dev]'`
- `tests/__init__.py` — empty package marker for consistent pytest import resolution
- `tests/conftest.py` — synthetic_email_body fixture with mandatory privacy docstring guardrail; contains FAKE1234567890 and FAKECARRIER
- `tests/fixtures/.gitkeep` — tracks fixtures/ directory in git; ready for Phase 2–5 synthetic data files
- `tests/test_smoke.py` — 6 smoke tests: test_package_importable, test_parsers_subpackage_importable, test_base_parser_is_abstract, test_tracking_info_dataclass, test_entry_point_exits_zero, test_entry_point_no_stdout

## Decisions Made

- **mypy additional_dependencies are mandatory in the pre-commit hook**: httpx, structlog, and python-dotenv must be listed under `additional_dependencies` in the mirrors-mypy hook. Without them, the pre-commit isolated virtualenv cannot resolve these imports and mypy silently fails on the package (Pitfall 2 from RESEARCH.md).
- **Hook order: ruff-check before ruff-format**: When `ruff-check --fix` is used, it must run before ruff-format so formatting is applied after auto-fixes are written. Reversing the order causes ruff-format to format before --fix modifies the file, leaving post-fix formatting inconsistent.
- **Privacy docstring is a mandatory guardrail**: The privacy comment in conftest.py is intentional documentation for future contributors — it surfaces the constraint directly in the test file where violations would occur.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Applied ruff format to test files before commit**
- **Found during:** Task 2 verification (ruff format --check .)
- **Issue:** conftest.py and test_smoke.py needed blank lines inserted after module docstrings per ruff's formatting rules
- **Fix:** Ran `python -m ruff format .` — 2 files reformatted; all 9 files clean afterward
- **Files modified:** tests/conftest.py, tests/test_smoke.py
- **Verification:** `python -m ruff format --check .` exits 0 after fix; `pytest -v` still shows 6 passed
- **Committed in:** ab64c2e (Task 2 commit includes formatted files)

## Full Phase 1 Gate Results

All Phase 1 success criteria satisfied:

```
ruff check .          → All checks passed (zero violations)
ruff format --check . → 9 files already formatted (zero violations)
mypy shipping_tracker/ --strict → Success: no issues found in 6 source files
pytest -v             → 6 passed in 2.05s
python -m shipping_tracker → exits 0, empty stdout
pre-commit run --all-files → ruff check Passed, ruff format Passed, mypy Passed
git check-ignore .env → .env (privacy-critical file excluded from git)
```

## Known Stubs

None — no stub patterns in files created by this plan. Test files contain only smoke tests against the Plan 01 skeleton.

## Threat Flags

No new threat surface introduced beyond what was covered in the plan's threat model:
- CI workflow contains no embedded secrets (T-02-02: accepted)
- Test files use FAKE-prefixed synthetic data only (T-02-01: mitigated)
- Pre-commit hooks pinned to exact revs (T-02-03: mitigated)

## Self-Check: PASSED

Files verified present:
- .pre-commit-config.yaml: FOUND
- .github/workflows/ci.yml: FOUND
- tests/__init__.py: FOUND
- tests/conftest.py: FOUND
- tests/fixtures/.gitkeep: FOUND
- tests/test_smoke.py: FOUND

Commits verified in git log:
- 5acb308: FOUND (chore(01-02): add pre-commit config and GitHub Actions CI workflow)
- ab64c2e: FOUND (feat(01-02): add test infrastructure — conftest, fixtures dir, and smoke tests)

tests/fixtures/.gitkeep tracked: git ls-files tests/fixtures/.gitkeep → confirmed

---
*Phase: 01-scaffold*
*Completed: 2026-05-31*
