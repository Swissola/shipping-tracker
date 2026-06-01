---
phase: 4
slug: deduplication
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-01
---

# Phase 4 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Register origin: **authored at plan time** (all three 04-NN-PLAN.md files carried a
`<threat_model>` block). This pass **verified each mitigation against the
implementation** — it did not retroactively scan for new threats.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| test fixtures → public git repo | Synthetic test data is committed; must contain no real PII | Tracking numbers, message ids (synthetic/FAKE only) |
| tracking_number / message_id → SQL | Values flow into SQLite queries; must be parameterized, never string-formatted | Operational identifiers |
| db.py / registrar.py → log file | Operational data (tracking numbers) must never reach logs (LOG-02) | Tracking numbers (must NOT cross) |
| injected registrar callable → register_and_persist | An injected callable may raise; its exception message could carry PII if careless | Exception payloads |
| DATABASE_PATH (.env) → filesystem | An operator-set path determines where the SQLite file is written | Filesystem path |
| per-email exception → log file | A raising parser/registrar must not leak email content into logs (WR-04 / LOG-02) | Exception type only (no body) |
| SQLite DB file → other local Pi users | The DB holds real tracking numbers + opaque Gmail ids | At-rest operational data |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-04-01 | Information disclosure | tests/fixtures + tests/test_db.py in public repo | mitigate | FAKE-prefixed synthetic values + privacy docstring; no real ids/emails — `tests/fixtures/fake_db.py:9-15`, docstring `:1-7` | closed |
| T-04-02 | Information disclosure | LOG-02 caplog assertion (`test_null_registrar_defers`) | mitigate | Test asserts `FAKE_TRACKING_NUMBER_1 not in record.message` over every caplog record — `tests/test_db.py:375-376` | closed |
| T-04-03 | Tampering | SQL in tests | accept (low) | Parameterized `?` placeholders throughout; in-memory connection; no untrusted input | closed |
| T-04-04 | Tampering (SQLi) | All db.py queries (tracking_number / message_id) | mitigate | Every query uses `?` placeholders; zero f-string SQL — `db.py:52-54, 60-63, 95-102` | closed |
| T-04-05 | Information disclosure | db.py / registrar.py logging | mitigate | db.py has zero logger calls in its bodies; `registrar.py:40` logs `"registrar.deferred"` with no arguments | closed |
| T-04-06 | Information disclosure | registrar exception message reaching a log | mitigate | `db.py:89-90` bare `raise` (no wrap/log); `main.py:141-145` logs `type(exc).__name__` only; no `logger.exception` | closed |
| T-04-07 | Denial of service | DB lock under brief cron overlap | accept (low) | `PRAGMA busy_timeout = 5000` — `db.py:25` | closed |
| T-04-08 | Tampering (SQLi) | D-03 `INSERT OR IGNORE` in main() loop | mitigate | Parameterized `(?, ?)` for message_id + timestamp — `main.py:123-124` | closed |
| T-04-09 | Information disclosure | WR-04 per-email error log in main() | mitigate | Logs `id=%s type=%s` with `type(exc).__name__` only; no `logger.exception`/body — `main.py:141-145` | closed |
| T-04-10 | Tampering / EoP | DATABASE_PATH directory traversal / write location | accept (low) | Operator-set in own `.env`, not attacker input; `os.path.dirname(...) or "data"` guard — `main.py:68`; documented `.env.example:20-24` | closed |
| T-04-11 | Information disclosure | SQLite file readable by other Pi users | accept (low) | `*.db` + `data/` gitignored — `.gitignore:7,15`; POSIX umask governs single-user Pi perms (out of scope to harden for v1) | closed |
| T-04-12 | Denial of service | Cron overlap causing "database is locked" | accept (low) | `PRAGMA busy_timeout=5000` (`db.py:25`) + idempotent `INSERT OR IGNORE` (`main.py:123`, `db.py:95,99`) | closed |
| T-04-SC | Tampering (supply chain) | package installs | n/a | Zero new dependencies — stdlib `sqlite3`/`datetime`/`typing` + existing `python-dotenv`; pyproject.toml unchanged from Phase 3 | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party) · n/a*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-04-01 | T-04-03 | Test SQL is parameterized by convention; in-memory only with no untrusted input — residual risk negligible | Phase 4 plan (mitigate→accept-low) | 2026-06-01 |
| AR-04-02 | T-04-07 / T-04-12 | Single-writer cron tool; `busy_timeout=5000` waits rather than raising "database is locked". WAL rejected as overkill (D-10) | Phase 4 plan | 2026-06-01 |
| AR-04-03 | T-04-10 | `DATABASE_PATH` is operator-set in their own `.env`, never attacker-supplied; no traversal-from-untrusted-source path exists on a single-user Pi | Phase 4 plan | 2026-06-01 |
| AR-04-04 | T-04-11 | DB file lives under the operator's own data dir and is gitignored (never reaches the public repo); local file perms governed by POSIX umask on a single-user Pi — hardening further is out of scope for v1 | Phase 4 plan | 2026-06-01 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-01 | 13 | 13 | 0 | gsd-security-auditor (verify-mitigations mode, ASVS L1) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-01
