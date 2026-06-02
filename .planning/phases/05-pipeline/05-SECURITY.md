---
phase: 05
slug: pipeline
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-02
---

# Phase 05 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| env (`.env`) → process | `TRACKINGMORE_API_KEY` enters the process; must never leave via logs or exceptions | API key (secret) |
| shipping_tracker → TrackingMore API (HTTPS) | Outbound request carrying the API key in the `Tracking-Api-Key` header; response is untrusted input parsed in `_handle` | API key (out), untrusted JSON (in) |
| parser output → registrar | `tracking_number` / `carrier` cross into the request body (validated upstream by the parser) | PII (tracking number) |
| test process → PyPI (pip install) | Untrusted package install crosses here during dev-dependency setup | third-party code |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-05-01 | Information Disclosure | Test fixtures / response builders | mitigate | Builder bodies use synthetic data only (no real tracking/email); LOG-02 regression `test_tracking_number_never_logged` asserts no PII in logs (`tests/conftest.py`, `tests/test_registrar.py:332-355`) | closed |
| T-05-02 | Information Disclosure | API key in tests | mitigate | Tests use `_FAKE_API_KEY = "FAKE_KEY"`; `test_api_key_never_logged` asserts the key value never reaches log output (`tests/test_registrar.py:38,363-392`) | closed |
| T-05-03 | Information Disclosure | API key in logs/exceptions | mitigate | Key read from env only (D-05, `main.py:74`); `config.missing_api_key` logs no value (`main.py:76`); no `logger.`/`raise` site in `registrar.py` or `main.py` interpolates the key | closed |
| T-05-04 | Information Disclosure | tracking_number / carrier in logs | mitigate | All registrar log/raise sites structural only; WR-04 broad except logs `message_id` + `type(exc).__name__` only (`main.py:172-176`); `tracking_number` never inside a logger/raise arg | closed |
| T-05-05 | Tampering | Malformed / non-JSON TrackingMore response | mitigate | Defensive `try resp.json() except → {}` (`registrar.py:114-117`); unknown `meta_code` falls through to status checks → transient retry or `return False` (no persist, no crash) | closed |
| T-05-06 | Denial of Service | Hung socket stalls cron job | mitigate | 10s `httpx` timeout (D-03) + single ~2s retry caps a dead endpoint then defers (D-02); named `http_client` closed in `finally` (`main.py:188`, Pitfall 4) | closed |
| T-05-07 | Tampering | SSRF via tracking_number | accept | URL is the hardcoded constant `_BASE_URL = "https://api.trackingmore.com"` (`registrar.py:58,92`), never constructed from input — no SSRF surface | closed |
| T-05-SC | Tampering | httpx / respx supply chain | accept | Both audited `OK` in `05-RESEARCH.md` Package Legitimacy Audit (slopcheck clean, ~5yr age); pinned in `pyproject.toml` (`httpx>=0.28`, `respx>=0.23`) | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-05-01 | T-05-07 | No SSRF surface: the request URL is a hardcoded module constant (`_BASE_URL`), never built from `tracking_number`, `carrier`, or any other input. Confirmed in code against the `05-RESEARCH.md` Security Domain rationale. | gsd-security-auditor (verified 2026-06-02) | 2026-06-02 |
| AR-05-02 | T-05-SC | `httpx` and `respx` both pass the `05-RESEARCH.md` Package Legitimacy Audit (source repos confirmed, ~5yr age, slopcheck clean); versions pinned in `pyproject.toml`. No `[ASSUMED]`/`[SUS]` packages introduced. | gsd-security-auditor (verified 2026-06-02) | 2026-06-02 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-02 | 8 | 8 | 0 | gsd-security-auditor (verify mitigations; register authored at plan time) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-02
