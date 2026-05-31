---
phase: 1
slug: scaffold
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-31
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — created in Wave 0 |
| **Quick run command** | `ruff check . && mypy shipping_tracker/ --strict && pytest` |
| **Full suite command** | `pytest -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `ruff check . && mypy shipping_tracker/ --strict && pytest`
- **After every plan wave:** Run `pytest -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-pyproject | 01 | 1 | SETUP-01 | — | N/A | smoke | `python -c "import shipping_tracker"` | ❌ W0 | ⬜ pending |
| 1-entrypoint | 01 | 1 | SETUP-01 | — | N/A | smoke | `python -m shipping_tracker` | ❌ W0 | ⬜ pending |
| 1-ruff | 01 | 1 | SETUP-02 | — | N/A | toolchain | `ruff check . && ruff format --check .` | ❌ W0 | ⬜ pending |
| 1-mypy | 01 | 1 | SETUP-03 | — | N/A | toolchain | `mypy shipping_tracker/ --strict` | ❌ W0 | ⬜ pending |
| 1-pytest | 01 | 1 | SETUP-04 | — | N/A | unit | `pytest` | ❌ W0 | ⬜ pending |
| 1-precommit | 01 | 1 | SETUP-05 | — | N/A | manual | `pre-commit run --all-files` | ❌ W0 | ⬜ pending |
| 1-ci | 01 | 1 | SETUP-06 | — | N/A | toolchain | CI validates on push | ❌ W0 | ⬜ pending |
| 1-gitignore | 01 | 1 | SETUP-07 | T-info-disc | `.env` never committed | manual | `git check-ignore .env` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/__init__.py` — makes tests directory a package
- [ ] `tests/conftest.py` — shared fixtures
- [ ] `tests/fixtures/` — directory for synthetic test data files
- [ ] `tests/test_smoke.py` — covers SETUP-01, SETUP-04 (importability, entry point)
- [ ] `pip install -e '.[dev]'` — framework install

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| pre-commit hooks fire on commit | SETUP-05 | Requires a git commit; not automatable in pytest | Run `pre-commit run --all-files` and verify ruff + mypy hooks pass |
| `.env` not tracked by git | SETUP-07 | Requires filesystem state beyond pytest scope | Run `git check-ignore .env` — must output `.env` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
