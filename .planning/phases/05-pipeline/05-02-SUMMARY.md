---
phase: 05-pipeline
plan: 02
subsystem: TrackingMore pipeline (Nyquist Wave 2 — GREEN implementation)
tags: [trackingmore, registrar, httpx, pipeline, green, mvp-slice]
requires:
  - "Plan 05-01 RED contract (tests/test_registrar.py — 15 tests) + temporary mypy override"
  - "Phase 4 registrar seam (Registrar Protocol, register_and_persist, dispatch loop)"
  - "httpx>=0.28 (in-tree), respx>=0.23 (dev, installed Wave 1)"
provides:
  - "shipping_tracker.registrar.TrackingMoreRegistrar (injectable httpx.Client, D-04)"
  - "shipping_tracker.registrar.QuotaExceededError (structural-message signal, D-06)"
  - "db.register_and_persist carrier passthrough (D-08)"
  - "main() D-05 key fail-fast + named http_client lifecycle + QuotaExceededError catch-before-broad"
affects:
  - "Closes TRACK-01..05; completes the Phase 5 end-to-end fetch->parse->dedupe->register slice"
  - "Removes the temporary tests.test_registrar mypy override (full-tree --strict restored)"
tech-stack:
  added: []
  patterns:
    - "Constructor-injected httpx.Client adapter (D-04 zero-live-call seam)"
    - "Typed signalling exception across registrar->dispatch boundary (QuotaExceededError)"
    - "Defensive response-envelope parse (try resp.json() except -> {})"
    - "Fail-fast env validation before any I/O (D-05)"
    - "Caller-owned httpx.Client lifetime, closed in finally (Pitfall 4)"
key-files:
  created:
    - ".planning/phases/05-pipeline/05-02-SUMMARY.md"
  modified:
    - "shipping_tracker/registrar.py"
    - "shipping_tracker/db.py"
    - "shipping_tracker/main.py"
    - "pyproject.toml"
    - "tests/test_registrar.py"
    - "tests/conftest.py"
    - "tests/test_aliexpress_parser.py"
    - "tests/test_gmail_client.py"
decisions:
  - "5xx transient retry catch lives in __call__ (not _handle): _handle raises httpx.HTTPStatusError, __call__ catches it to drive the single ~2s retry, so test_5xx_retries_once_then_defers sees call_count==2 (D-02)."
  - "Q-1 RESOLUTION honored without extra code: courier-required rejections fall through to the generic other-4xx -> return False branch (D-08 locked, DEDUP-05 defer)."
  - "respx 0.23 MockRouter is not an httpx transport; wrapped router.handler in httpx.MockTransport at the single test helper to make the Wave 0 contract runnable."
metrics:
  duration_min: 4
  tasks: 2
  files: 8
  completed: 2026-06-02
---

# Phase 5 Plan 02: TrackingMore Pipeline GREEN Implementation Summary

Turned the Plan 01 RED suite GREEN by implementing the real TrackingMore v4 slice: added `TrackingMoreRegistrar` (injectable `httpx.Client`, D-04) and `QuotaExceededError` to `registrar.py`, threaded `carrier` through `db.register_and_persist`, and made the three surgical `main.py` edits — D-05 API-key fail-fast, `NullRegistrar`→`TrackingMoreRegistrar` swap against a named `http_client` closed in `finally`, and the `except QuotaExceededError: ... break` clause placed before the broad `except Exception` (D-06). All 15 contract tests pass, the full 73-test suite is GREEN, mypy `--strict` is clean across the whole tree (temporary Wave 0 override removed), and ruff check/format are clean.

## What Was Built

### Task 1 — TrackingMoreRegistrar + QuotaExceededError (commit 9fb626f)
- Added `QuotaExceededError(Exception)` with a structural-only docstring (LOG-02); imported `time` and `httpx`; added module-level `_BASE_URL = "https://api.trackingmore.com"`.
- Added `TrackingMoreRegistrar` implementing the `Registrar` Protocol: constructor `(api_key, client=None, *, retry_pause=2.0)`; `__call__` builds `payload: dict[str, str]` with `tracking_number` always present and `courier_code` only when `carrier` is truthy (D-08); POSTs `/v4/trackings/create` with the `Tracking-Api-Key` header (TRACK-02); single ~2s retry on `TimeoutException`/`ConnectError` then `False` (D-02).
- `_handle` maps all six outcomes: 429 → `QuotaExceededError("rate-limit")`; defensive `try resp.json() except → {}` (Pitfall 6/Q-2); meta 200/201 → INFO `registrar.created`, `True`; 4016/4101 → INFO `registrar.already_exists`, `True` (TRACK-03); 4021/4190 or HTTP 402 → `QuotaExceededError("quota-exhausted")` (D-01/D-06); status ≥500 → raise `httpx.HTTPStatusError("server-error", ...)` (caught by `__call__`'s retry path, D-02); any other 4xx → ERROR `registrar.error code=%s` (meta_code only), `False`.
- `NullRegistrar` and the `Registrar` Protocol are unchanged and still present.

### Task 2 — db carrier passthrough + main() wiring + override removal (commit eb1acae)
- `db.register_and_persist` gained `carrier: str | None = None` and now calls `registrar(tracking_number, carrier)` (was hardcoded `None`); the `except Exception: raise` is untouched so `QuotaExceededError` still propagates.
- `main.py`: D-05 fail-fast — `api_key = os.getenv("TRACKINGMORE_API_KEY", "").strip()`; if falsy, `logger.error("config.missing_api_key")` (no key value) and `return 1`, before `sqlite3.connect` and before `fetch_unread_shipping_emails`.
- `main.py`: named `http_client = httpx.Client(timeout=10.0)` constructed once, injected as `TrackingMoreRegistrar(api_key=api_key, client=http_client)`, and closed in `finally` after `conn.close()` (Pitfall 4).
- `main.py`: `except QuotaExceededError:` (WARNING `registrar.quota_exceeded` + `break`) placed immediately before the broad `except Exception` (D-06 critical ordering); `register_and_persist(..., carrier=result.carrier)` (D-08). Import widened to pull `TrackingMoreRegistrar`/`QuotaExceededError`; unused `NullRegistrar` import dropped.
- Removed the temporary `[[tool.mypy.overrides]] module = ["tests.test_registrar"]` block from `pyproject.toml` (dependency carry-forward) — full-tree `mypy --strict` now passes without it (26 files).

## Verification Results

- `python -m pytest tests/test_registrar.py -q` → 15 passed (all TRACK-01..05 + LOG-02/D-05/D-06 contract tests GREEN).
- `python -m pytest -x -q` → 73 passed (no regression in Phase 1-4 tests).
- `python -m mypy --strict shipping_tracker/` → Success, 13 source files. `python -m mypy --strict shipping_tracker/ tests/` → Success, 26 source files (override removal confirmed).
- `python -m ruff check .` → All checks passed. `python -m ruff format --check .` → 26 files already formatted.
- Source assertions: `except QuotaExceededError` (line 158) precedes `except Exception` (line 166); key check + `return 1` (line 74) precede `sqlite3.connect` (81) and `fetch_unread_shipping_emails` (98); named `http_client` (85) injected as `client=http_client` (91) and `http_client.close()` (188) in finally; `carrier=result.carrier` (153) passed through; `v4/trackings/create` and `Tracking-Api-Key` present in registrar.py.
- Pre-commit hooks (ruff check, ruff format, mypy strict) passed on both task commits.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Wave 0 test transport wiring incompatible with respx 0.23.1**
- **Found during:** Task 1 (running the contract tests).
- **Issue:** The Plan 01 `_make_registrar` helper did `httpx.Client(transport=router)`, but in respx 0.23.1 `MockRouter` is not an `httpx.BaseTransport` (`AttributeError: 'MockRouter' object has no attribute 'handle_request'`). Every test errored before exercising any source.
- **Fix:** Wrapped the router in `httpx.Client(transport=httpx.MockTransport(router.handler))` at the single test helper, and corrected the `mock_router` fixture docstring in `conftest.py` to match. `route.called` / `route.calls` remain fully functional; zero live calls preserved (D-04).
- **Files modified:** `tests/test_registrar.py`, `tests/conftest.py`
- **Commit:** 9fb626f

**2. [Rule 1 - Bug] Two Phase-4 main() tests broke on the new D-05 gate**
- **Found during:** Task 2 (full-suite run).
- **Issue:** `test_main_dispatch_loop_logs_pii_safely_on_error` and `test_main_calls_fetch_and_returns_zero` drive the real `main()` and assert exit 0, but neither set `TRACKINGMORE_API_KEY`. The new D-05 fail-fast (this plan's intended behavior) correctly returns 1 before the code each test exercises.
- **Fix:** Set a synthetic `monkeypatch.setenv("TRACKINGMORE_API_KEY", "FAKE_KEY")` (and in-memory `DATABASE_PATH` where missing) so each test reaches the behavior it actually asserts, past the new gate. PII-safe (FAKE key, consistent with existing synthetic conventions).
- **Files modified:** `tests/test_aliexpress_parser.py`, `tests/test_gmail_client.py`
- **Commit:** eb1acae

### Implementation note (within plan intent, not a deviation)
- The PATTERNS.md pseudocode raised `httpx.HTTPStatusError` for 5xx inside `_handle` but did not show where the D-02 retry catch lived. The retry catch is placed in `__call__` (it owns the `for attempt in range(2)` loop and `retry_pause`), so a 5xx triggers exactly one retry then `return False` — satisfying `test_5xx_retries_once_then_defers` (`call_count == 2`). This matches the locked D-02 semantics exactly.

## Authentication Gates

None. All registrar tests use a mocked transport (D-04); no real `TRACKINGMORE_API_KEY` was required. The D-05 fail-fast is exercised with a synthetic empty/FAKE key only.

## Known Stubs

None. This plan replaced the `NullRegistrar` placeholder with the real `TrackingMoreRegistrar`. No empty/placeholder data sources remain in the pipeline path.

## Threat Flags

None. All surface in this plan (the single hardcoded `_BASE_URL` outbound endpoint, the API-key env boundary, parser→request body) is already enumerated in the plan's `<threat_model>` (T-05-03..07). Mitigations applied as specified: key never logged (T-05-03), structural-only logs/exceptions (T-05-04), defensive JSON parse (T-05-05), 10s timeout + single retry + finally-close (T-05-06).

## Self-Check: PASSED

- `shipping_tracker/registrar.py`, `shipping_tracker/db.py`, `shipping_tracker/main.py`, `pyproject.toml`, `tests/test_registrar.py`, `tests/conftest.py`, `tests/test_aliexpress_parser.py`, `tests/test_gmail_client.py`, `.planning/phases/05-pipeline/05-02-SUMMARY.md` — all present on disk.
- Commits 9fb626f and eb1acae present in git history.
