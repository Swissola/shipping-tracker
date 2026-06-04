---
phase: 01-scaffold
audit_date: 2026-05-31
asvs_level: 1
threats_total: 9
threats_closed: 9
threats_open: 0
status: secured
---

# SECURITY.md — Phase 01 (scaffold) Threat Verification

**Phase:** 01-scaffold (plans 01-01 and 01-02)
**Audit date:** 2026-05-31
**ASVS Level:** 1
**Threats Closed:** 9/9
**Threats Open:** 0/9

---

## Threat Verification

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-01-01 | Information Disclosure | mitigate | CLOSED | `.gitignore` lines 2-4: `.env`, `token.json`, `credentials.json` excluded. `git check-ignore .env` → `.env`. `git check-ignore token.json credentials.json` → both confirmed. `*.db`, `*.sqlite3`, `logs/` also excluded (lines 7-10). |
| T-01-02 | Information Disclosure | mitigate | CLOSED | `logging_config.py:49`: only `root_logger.addHandler(handler)` where `handler` is `RotatingFileHandler`. No `StreamHandler` instantiated or added anywhere in file. Comment at line 51: `# NO StreamHandler — cron silence (D-07, LOG-03)`. Docstring at line 17 states no StreamHandler. |
| T-01-03 | Information Disclosure | mitigate | CLOSED | `tests/conftest.py:3-5`: mandatory privacy docstring present. `conftest.py:16`: `FAKE1234567890`. `conftest.py:17`: `FAKECARRIER`. `test_smoke.py:35`: `FAKE123`, `FAKECARRIER`. No real tracking numbers, email addresses, or order IDs in any test file — grep across `tests/` confirmed. |
| T-01-04 | Information Disclosure | mitigate | CLOSED | `.env.example:5`: `TRACKINGMORE_API_KEY=your_api_key_here` — placeholder only. Post-rename from `SEVENTEEN_TRACK_API_KEY` confirmed: git history shows both forms carried placeholder value only (`your_api_key_here`). Full history scan of `+`-prefixed diff lines found no real key material in any tracked file. |
| T-01-SC | Tampering | accept | CLOSED | Accepted risk recorded below. Packages verified at plan time via slopcheck 0.6.1 against PyPI on 2026-05-31 (RESEARCH.md §Package Legitimacy Audit). All packages returned `[OK]`, none `[ASSUMED]` or `[SUS]`. |
| T-02-01 | Information Disclosure | mitigate | CLOSED | `tests/conftest.py:1-6`: privacy docstring present with explicit prohibition on real data. All fixture data FAKE-prefixed (`FAKE1234567890`, `FAKECARRIER`). `tests/fixtures/` directory tracked via `.gitkeep` only — no fixture data files present. `test_smoke.py` uses `FAKE123` / `FAKECARRIER` exclusively. |
| T-02-02 | Information Disclosure | mitigate | CLOSED | `.github/workflows/ci.yml`: no `secrets.*` context, no `env:` block with credentials, no hardcoded tokens. Phase 1 CI uses only `pip install -e '.[dev]'` and open tool invocations. No credentials required or referenced. |
| T-02-03 | Tampering | mitigate | CLOSED | `.pre-commit-config.yaml:3`: `rev: v0.15.15` (ruff-pre-commit). `.pre-commit-config.yaml:10`: `rev: v2.1.0` (mirrors-mypy). `additional_dependencies` block at line 14 lists `httpx`, `structlog`, `python-dotenv` — all pinned package names for isolated mypy venv. Hook order: `ruff-check` (line 4) before `ruff-format` (line 6), correct. |
| T-02-SC | Tampering | accept | CLOSED | Accepted risk recorded below. pre-commit isolated virtualenv installs from pinned revs (v0.15.15 / v2.1.0) plus pinned `additional_dependencies`. All packages cleared in Plan 01 Package Legitimacy Audit (RESEARCH.md). |

---

## Accepted Risks

### T-01-SC — pip supply chain (runtime dependencies)

**Packages:** httpx, structlog, python-dotenv, ruff, mypy, pytest, pre-commit

**Rationale:** All packages verified via slopcheck 0.6.1 and direct PyPI inspection on 2026-05-31. All returned `[OK]` with no `[ASSUMED]` or `[SUS]` findings. All packages are widely used, well-maintained, and have established release histories. No pinned hashes are used; version range specifiers are used instead (`>=`). The residual risk of a future compromised release entering the dependency graph is accepted for Phase 1 given the non-production nature of the scaffold phase. Hash-pinning via `pip-compile --generate-hashes` is recommended before production deployment.

**Accepted by:** Plan author (2026-05-31, RESEARCH.md §Package Legitimacy Audit)

---

### T-02-SC — pip supply chain (pre-commit hook isolation)

**Packages:** ruff-pre-commit v0.15.15, mirrors-mypy v2.1.0 and their additional_dependencies (httpx, structlog, python-dotenv)

**Rationale:** pre-commit hooks run in isolated virtualenvs pinned to exact git revs (`v0.15.15`, `v2.1.0`). The mypy hook's `additional_dependencies` are also pinned by package name. All packages cleared in Plan 01 legitimacy audit. The pre-commit isolated venv model limits blast radius: a compromised hook package cannot directly modify the running system beyond the pre-commit virtualenv scope. Residual risk of a future rev compromise is accepted; updating pinned revs triggers explicit review.

**Accepted by:** Plan author (2026-05-31, RESEARCH.md §Package Legitimacy Audit)

---

## Advisory — Developer Identity in Git History (not a Phase 01 threat-register item)

Every commit's author trailer uses the GitHub noreply address (`9119417+Swissola@users.noreply.github.com`). This is standard git metadata (it lives in commit author/committer headers, **not** in any file content), so it is **not** a Phase 01 threat-model finding and does not block this phase.

However, given the project's non-negotiable constraint — *"no PII in source, tests, logs, or history — project will be public"* — a personal email address embedded in every commit of a repo that will be **published** is worth a conscious decision before the first public push. Options if the user wants it scrubbed:
- Configure a GitHub `noreply` author email (`git config user.email "<id>+username@users.noreply.github.com"`) going forward, and
- Rewrite existing history (e.g. `git filter-repo --mailmap`) **before** the repo is ever made public — history rewrites are cheap now (single contributor, pre-release) and painful later.

Disposition: **deferred to the user** — flagged here so it is not silently carried into the public release.

---

## Unregistered Threat Flags

The `01-02-SUMMARY.md §Threat Flags` section states: "No new threat surface introduced beyond what was covered in the plan's threat model." All three items listed in that section map directly to T-02-02, T-02-01, and T-02-03 respectively. No unregistered flags.

---

## Verification Commands Run

```
git check-ignore .env                     → .env (CLOSED T-01-01)
git check-ignore token.json credentials.json → both confirmed (CLOSED T-01-01)
git check-ignore *.db *.sqlite3 logs/     → all three confirmed (CLOSED T-01-01)
grep addHandler logging_config.py         → line 49 only: RotatingFileHandler (CLOSED T-01-02)
grep StreamHandler logging_config.py      → docstring + comment only, no addHandler (CLOSED T-01-02)
grep FAKE tests/**                        → FAKE1234567890, FAKECARRIER, FAKE123 only (CLOSED T-01-03, T-02-01)
grep PRIVACY tests/conftest.py            → privacy docstring confirmed at lines 3-5 (CLOSED T-01-03, T-02-01)
cat .env.example                          → TRACKINGMORE_API_KEY=your_api_key_here (CLOSED T-01-04)
git log -p -- .env.example | grep "^+"   → only placeholder values in all commits (CLOSED T-01-04)
grep secrets .github/workflows/ci.yml     → no output (CLOSED T-02-02)
grep "v0.15.15\|v2.1.0" .pre-commit-config.yaml → lines 3, 10 (CLOSED T-02-03)
grep additional_dependencies .pre-commit-config.yaml → line 14 (CLOSED T-02-03)
```
