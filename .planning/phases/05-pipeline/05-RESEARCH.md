# Phase 5: Pipeline - Research

**Researched:** 2026-06-01
**Domain:** TrackingMore v4 REST API, httpx sync client, injectable-transport testing, Python exception design
**Confidence:** HIGH (API contract verified against official status-code page; auth header confirmed via official Go SDK source; httpx/respx verified on PyPI)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** On the first quota-exhausted or rate-limit (HTTP 429) response, short-circuit further create calls for the rest of the run — every remaining create would fail identically. Emit one WARNING summary line. Unregistered numbers stay unwritten and auto-retry next cron via the Phase 4 DEDUP-05 path.
- **D-02:** On a transient single-call failure (network timeout, connection reset, or a 5xx from TrackingMore) perform one quick in-run retry after a short fixed pause (~2s), then give up: log PII-safely, don't persist, continue. A quota/429 is NOT a transient error — it short-circuits (D-01) and is never retried.
- **D-03:** 10s per-request HTTP timeout (connect + read). With the one retry, a dead endpoint costs ~22s then defers.
- **D-04:** All automated tests use a mocked/injectable HTTP transport returning synthetic responses for every path (success, already-exists, 429/quota, 5xx, timeout). Zero live calls — no test ever hits the real API or consumes the 50/month free quota; CI needs no secret. The registrar MUST accept an injectable HTTP transport/client seam (constructor-injected) so tests feed fakes.
- **D-05:** Fail-fast at startup. Validate TRACKINGMORE_API_KEY in main() immediately after load_dotenv() — before the Gmail fetch and DB open. If missing/empty, log one PII-safe error (never the key value) and return exit code 1.
- **D-06 (signal mechanism):** The registrar signals quota exhaustion by raising a dedicated typed exception (e.g. QuotaExceededError). register_and_persist propagates it; main()'s dispatch loop catches it specifically and breaks. The except QuotaExceededError: ... break clause MUST sit before the loop's existing broad except Exception (WR-04, main.py:135), or the broad catch will swallow it and the loop will continue instead of stopping.
- **D-07:** Quiet-by-default, tiered, PII-safe logging. created → INFO; already-exists (TRACK-03) → INFO/DEBUG, treated as success; transient error → ERROR (message_id + exception type); quota short-circuit → one WARNING summary (D-01).
- **D-08:** Build the create payload with tracking_number always present; include courier_code only when carrier is non-None/non-empty — omit the key entirely otherwise.

### Claude's Discretion

- HTTP library — httpx vs requests. Planner's call; httpx fits the stated stack and supports clean timeout + injectable-transport testing.
- Exact already-exists detection (TRACK-03) — the precise TrackingMore v4 response field/code is research (see below; now resolved).
- Exact QuotaExceededError type/placement — module home (registrar.py likely) and whether it subclasses a project base exception.
- Injectable-transport shape (D-04) — constructor-injected httpx.Client, base-URL override, or a callable transport — planner's choice.
- TrackingMore .env notes — whether to expand the existing TRACKINGMORE_API_KEY comment in .env.example.
- Retry pause exactness (~2s) and whether the create request uses a separate connect/read split within the 10s budget.

### Deferred Ideas (OUT OF SCOPE)

- Proactive monthly-quota counting (reactive handling only in Phase 5)
- Opt-in live smoke test
- Bounded exponential-backoff retry
- provider column / second tracking provider (PROV-01, v2)
- .env.example expansion (planner's discretion)

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TRACK-01 | Register via POST https://api.trackingmore.com/v4/trackings/create | API contract fully documented in Standard Stack and Code Examples sections |
| TRACK-02 | API key exclusively from TRACKINGMORE_API_KEY env var; never hardcoded | D-05 startup validation pattern documented; httpx header construction shown |
| TRACK-03 | Duplicate/already-exists response handled gracefully (not an error) | meta.code 4016 identified as the already-exists signal; mapped to persist=True |
| TRACK-04 | All API responses logged; rate-limit and quota errors handled without crashing | 429 (rate-limit) and 4021 (quota) signals identified; QuotaExceededError pattern documented |
| TRACK-05 | Courier auto-detected by TrackingMore; parser carrier passed as optional courier_code hint only | CRITICAL FINDING: courier_code is REQUIRED by TrackingMore v4 per official docs; auto-detect requires calling /v4/couriers/detect first — see Open Questions |

</phase_requirements>

---

## Summary

Phase 5 wires the real TrackingMore v4 HTTP client into the registrar seam Phase 4 left ready. The `TrackingMoreRegistrar` class replaces `NullRegistrar` — it accepts an injected `httpx.Client` for testability, calls `POST https://api.trackingmore.com/v4/trackings/create`, maps the four response outcomes onto the locked persistence semantics (created / already-exists / quota-stop / transient-retry), and raises `QuotaExceededError` so `main()`'s dispatch loop can `break` cleanly.

The most consequential research finding is a **partial conflict** with the CONTEXT.md assumption about `courier_code`: the official TrackingMore v4 `Create Trackings` help article states `courier_code` is **REQUIRED** for `/v4/trackings/create`. Auto-detection of the carrier from the tracking number is a separate `/v4/couriers/detect` call, not an implicit behavior of the create endpoint. PROJECT.md says "courier auto-detected" — this is true but requires a detect-then-create two-step, not a simple create-without-courier. The planner must resolve this (see Open Questions Q-1) before committing to the D-08 "omit courier_code when None" behavior.

The TrackingMore v4 response codes are confirmed. The auth header is `Tracking-Api-Key`. `httpx` is already a declared dependency (`httpx>=0.28`); `respx` is the idiomatic mock companion and a clean new dev dependency. Both packages pass slopcheck and are long-standing legitimate PyPI packages.

**Primary recommendation:** Use `httpx.Client` (already in `pyproject.toml`), add `respx>=0.23` as a dev dependency, implement `TrackingMoreRegistrar` with constructor-injected `client: httpx.Client`, and resolve the `courier_code` required/optional question before implementation begins.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| API key validation | App startup (main.py) | — | Fail-fast before any I/O; single point of truth |
| HTTP call to TrackingMore | registrar.py (TrackingMoreRegistrar) | — | Isolates all API protocol knowledge; injectable seam |
| Response → outcome mapping | registrar.py | — | Four outcomes are API-contract logic, not pipeline logic |
| QuotaExceededError signal | registrar.py (raises) | main.py (catches and breaks) | Typed exception crosses the registrar→dispatch boundary |
| Transient retry | registrar.py | — | One retry is a per-call transport concern; caller sees bool |
| DB persistence | db.py (register_and_persist) | — | Unchanged from Phase 4; QuotaExceededError propagates through |
| Dispatch loop short-circuit | main.py | — | Breaks the for-email loop when QuotaExceededError raised |
| Tiered PII-safe logging | registrar.py (INFO/ERROR) + main.py (WARNING on quota) | — | D-07 specifies tiers; PII constraint from CLAUDE.md |

---

## Standard Stack

### Core (already in pyproject.toml)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | >=0.28 (0.28.1 installed) | Sync HTTP client for TrackingMore calls | Already declared; supports injectable transport; clean timeout API; encode/httpx on GitHub |

### New Dev Dependency

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| respx | >=0.23 (0.23.1 latest) | Mock/intercept httpx calls in tests | D-04 zero-live-call requirement; idiomatic httpx companion |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| respx | pytest-httpx (0.36.2) | pytest-httpx is fixture-based (pytest-only); respx works with plain callables and supports constructor-injected transport pattern more naturally — prefer respx |
| httpx | requests + responses | requests also in the CLAUDE.md brief; httpx already installed and has native MockTransport; no reason to add requests |

**Installation (dev only):**
```bash
pip install respx>=0.23
```
Add to `pyproject.toml [project.optional-dependencies] dev`.

**Version verification (performed during research):**
- `httpx 0.28.1` — verified installed; [VERIFIED: PyPI registry]
- `respx 0.23.1` — latest on PyPI; author Jonas Lundberg; source github.com/lundberg/respx; [VERIFIED: PyPI registry]

---

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| httpx | PyPI | ~5 yrs | Very high (encode/httpx) | github.com/encode/httpx | OK | Approved |
| respx | PyPI | ~5 yrs | ~325k/wk | github.com/lundberg/respx | OK | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

slopcheck ran successfully (`python3 -m slopcheck install httpx respx`) — both packages returned `[OK]`. The subprocess error on Windows after the scan is a pip-invocation artifact unrelated to the package scan result.

---

## TrackingMore v4 API Contract

### Authentication

**Header:** `Tracking-Api-Key: <your_api_key>` [VERIFIED: official Go SDK source `req.Header.Set("Tracking-Api-Key", "YOUR API KEY")` at github.com/trackingmore100/tracking-sdk-go]

All requests must include:
```
Tracking-Api-Key: <value of TRACKINGMORE_API_KEY>
Content-Type: application/json
```

### POST /v4/trackings/create — Request Body

**Endpoint:** `POST https://api.trackingmore.com/v4/trackings/create`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `tracking_number` | string | YES | The parcel tracking number |
| `courier_code` | string | YES (per docs) | Carrier slug (e.g. `"aliexpress"`, `"yanwen"`). See Open Question Q-1 re: whether omitting triggers auto-detect or an error |

[CITED: support.trackingmore.com/en/article/trackingmore-create-api-122cydg — "Headers, tracking_number, and courier_code are REQUIRED"]

**Example minimal request body:**
```json
{"tracking_number": "FAKE1234567890", "courier_code": "aliexpress"}
```

**Example when carrier is None (D-08 behavior — UNDER QUESTION):**
```json
{"tracking_number": "FAKE1234567890"}
```
Whether the above is accepted (auto-detect) or returns error 4015/4013 is the open question. Research found conflicting signals — see Q-1.

### POST /v4/trackings/create — Response Outcomes

All responses return HTTP status code AND a `meta` envelope. v4 returns both (v3/v2 returned meta only). [CITED: support.trackingmore.com/en/article/differences-among-3-versions-of-trackingmore-api-1ip0fmh]

**Response envelope shape:**
```json
{
  "meta": {
    "code": <int>,
    "message": "<string>"
  },
  "data": { ... }
}
```

### Complete Response → Outcome Mapping Table

| HTTP Status | meta.code | Meaning | Persist? | Action |
|-------------|-----------|---------|----------|--------|
| 200 or 201 | 200 | Created successfully | YES | Log INFO "registrar.created"; return True |
| 400 | **4016** | Tracking already exists (duplicate) | YES | Log INFO/DEBUG "registrar.already_exists"; return True (TRACK-03) |
| 400 | 4001 | Invalid API key | NO | Raise generic exception; log ERROR (type only) |
| 400 | 4002 | API key deleted | NO | Raise generic exception; log ERROR (type only) |
| 400 | 4013 | tracking_number missing | NO | Raise generic exception; log ERROR |
| 400 | 4014 | Invalid tracking_number value | NO | Return False; log ERROR (no PII in message) |
| 400 | 4015 | Invalid courier_code value | NO | Return False; log ERROR |
| 400 | **4021** | Monthly quota exhausted ("Remaining quota is deficient, or the 7-day free trial has expired") | NO | Raise **QuotaExceededError**; D-01 short-circuit |
| 402 | — | Payment Required (balance) | NO | Raise QuotaExceededError (treat same as 4021) |
| **429** | — | Rate-limit: too many requests/second | NO | Raise **QuotaExceededError**; D-01 short-circuit (no retry) |
| 500, 503 | — | TrackingMore server error | NO | Transient: one ~2s retry, then return False; log ERROR type only |
| httpx.TimeoutException | — | Connect/read timeout (>10s) | NO | Transient: one ~2s retry, then return False; log ERROR type only |
| httpx.ConnectError | — | Connection reset/refused | NO | Transient: one ~2s retry, then return False; log ERROR type only |

[CITED: trackingmore.com/api-status_code.html — confirmed 4016=already-exists, 4021=quota, 429=rate-limit]

**Note on meta.code 4101 / 4190:** These codes appear in the official .NET and Go SDK README response tables but are NOT present on the official status-code page. The official status-code page (trackingmore.com/api-status_code.html) is the authoritative source for v4 — it lists 4016 and 4021. The SDK README tables may document v3 codes. Planner should use 4016 and 4021 as the primary detection targets but also handle 4101 and 4190 defensively (treat them identically to 4016 and 4021 respectively) since the SDK READMEs show these in response tables for the v4 SDK. [ASSUMED: that 4016/4021 are the v4 canonical codes — the official docs page confirms them]

**429 Retry-After header:** Documentation does NOT mention a `Retry-After` header for 429 responses. The guidance is to wait 120 seconds. Since 429 is a quota/rate-limit that triggers D-01 short-circuit (no retry), the absence of `Retry-After` is irrelevant to implementation. [CITED: support.trackingmore.com/en/article/why-do-i-get-429-response-code-error-in-your-api-2405za]

**Rate limit for /v4/trackings/create:** 3 requests/second. [CITED: support.trackingmore.com/en/article/trackingmore-api-request-rate-limit-c0ye70]

---

## Architecture Patterns

### System Architecture Diagram

```
main() startup
  └─ load_dotenv()
  └─ TRACKINGMORE_API_KEY check ──── missing → log ERROR, exit 1 (D-05)
  └─ open DB
  └─ init_db()
  └─ TrackingMoreRegistrar(client=httpx.Client(timeout=10)) ← injected at main()
       |
       ↓ for each email in fetch_unread_shipping_emails():
           ├─ DEDUP-03: is_email_processed? → skip
           ├─ parser dispatch → TrackingInfo(tracking_number, carrier)
           ├─ DEDUP-04: is_tracking_registered? → mark processed, skip
           └─ register_and_persist(conn, msg_id, tracking_number, registrar)
                └─ registrar(tracking_number, carrier)  ← TrackingMoreRegistrar.__call__
                     └─ POST /v4/trackings/create
                          ├─ 200/201 meta.code 200 → return True
                          ├─ 4016 (already-exists) → return True      [TRACK-03]
                          ├─ 4021 / 429 → raise QuotaExceededError    [D-06]
                          ├─ 5xx / timeout → retry once after ~2s     [D-02]
                          │       └─ still fails → return False
                          └─ other 4xx → return False
                ├─ True → write both DB rows atomically (Phase 4 unchanged)
                └─ QuotaExceededError propagates →
                     caught in main() BEFORE broad except Exception  [D-06 CRITICAL]
                     └─ log WARNING summary, break loop
```

### Recommended Project Structure (additions only)

```
shipping_tracker/
├── registrar.py          # Add: TrackingMoreRegistrar, QuotaExceededError
└── main.py               # Add: API-key check after load_dotenv(); swap NullRegistrar→TrackingMoreRegistrar;
                          #      add except QuotaExceededError BEFORE broad except Exception

tests/
├── test_registrar.py     # New: all TrackingMoreRegistrar tests (mocked transport)
└── conftest.py           # Add: respx router fixture / synthetic TrackingMore response fixtures
```

### Pattern 1: Constructor-Injected httpx.Client (D-04)

```python
# Source: https://www.python-httpx.org/advanced/transports/
import httpx
import time
from shipping_tracker.registrar import Registrar, QuotaExceededError

_BASE_URL = "https://api.trackingmore.com"

class TrackingMoreRegistrar:
    """Implements Registrar Protocol against TrackingMore v4 API.

    LOG-02: never embed tracking_number, carrier, or API key in exception messages.
    """

    def __init__(
        self,
        api_key: str,
        client: httpx.Client | None = None,
        *,
        retry_pause: float = 2.0,
    ) -> None:
        self._api_key = api_key
        self._client = client or httpx.Client(timeout=10.0)
        self._retry_pause = retry_pause

    def __call__(self, tracking_number: str, carrier: str | None) -> bool:
        payload: dict[str, str] = {"tracking_number": tracking_number}
        if carrier:
            payload["courier_code"] = carrier
        for attempt in range(2):
            try:
                resp = self._client.post(
                    f"{_BASE_URL}/v4/trackings/create",
                    json=payload,
                    headers={"Tracking-Api-Key": self._api_key},
                )
                return self._handle(resp)
            except (httpx.TimeoutException, httpx.ConnectError):
                if attempt == 0:
                    time.sleep(self._retry_pause)
                    continue
                return False  # second attempt failed — defer to next run
        return False  # unreachable but mypy needs it

    def _handle(self, resp: httpx.Response) -> bool:
        if resp.status_code == 429:
            raise QuotaExceededError("rate-limit")  # no PII in message
        meta_code = resp.json().get("meta", {}).get("code")
        if meta_code in (200, 201):
            return True
        if meta_code in (4016, 4101):  # 4101 defensive: some SDK docs show it
            return True  # TRACK-03: already-exists is success
        if meta_code in (4021, 4190, 402):  # 4190 defensive; 402 payment required
            raise QuotaExceededError("quota-exhausted")  # no PII in message
        if resp.status_code >= 500:
            raise httpx.HTTPStatusError(
                "server-error",  # no PII — not f"server error for {tracking_number}"
                request=resp.request,
                response=resp,
            )
        return False  # other 4xx: log at call site, don't persist
```

**Testing seam (D-04):**
```python
# Source: https://lundberg.github.io/respx/guide/
import httpx
import respx

def make_success_response() -> httpx.Response:
    return httpx.Response(200, json={"meta": {"code": 200, "message": "Success"}, "data": {}})

def make_already_exists_response() -> httpx.Response:
    return httpx.Response(400, json={"meta": {"code": 4016, "message": "Tracking already exists."}, "data": {}})

def make_quota_response() -> httpx.Response:
    return httpx.Response(400, json={"meta": {"code": 4021, "message": "Remaining quota is deficient."}, "data": {}})

def make_429_response() -> httpx.Response:
    return httpx.Response(429, json={"meta": {"code": 429, "message": "Too Many Requests"}, "data": {}})

# Inject fake transport into registrar under test
router = respx.MockRouter()
mock_client = httpx.Client(transport=router)
registrar = TrackingMoreRegistrar(api_key="FAKE_KEY", client=mock_client)
```

### Pattern 2: QuotaExceededError in registrar.py

```python
class QuotaExceededError(Exception):
    """Raised by TrackingMoreRegistrar on quota-exhausted or rate-limit (429).

    LOG-02: the message MUST NOT contain tracking_number, carrier, or API key.
    Caught specifically in main()'s dispatch loop BEFORE the broad except Exception.
    """
```

`QuotaExceededError` lives in `registrar.py` alongside the Protocol and `NullRegistrar`. It does NOT widen the `Registrar` Protocol's `bool` return (Phase 4 D-08) — it is a signalling exception alongside the protocol.

### Pattern 3: Dispatch Loop Wiring (main.py) — CRITICAL ORDER

```python
# CRITICAL: QuotaExceededError MUST be caught BEFORE the broad except Exception (WR-04)
# Current broad except is at main.py:135; new clause goes at main.py:~130

try:
    persisted = register_and_persist(
        conn, email.message_id, result.tracking_number, registrar
    )
    ...
except QuotaExceededError:
    logger.warning("registrar.quota_exceeded")  # one warning, no PII (D-07)
    break   # short-circuit: remaining numbers unwritten, retry next cron
except Exception as exc:
    # WR-04: existing broad catch — MUST remain AFTER QuotaExceededError
    logger.error(
        "pipeline.error id=%s type=%s",
        email.message_id,
        type(exc).__name__,
    )
    continue
```

### Anti-Patterns to Avoid

- **PII in exception messages:** `raise ValueError(f"unknown response for {tracking_number}")` — LOG-02 violation. Use only structural/type info: `raise QuotaExceededError("quota-exhausted")`.
- **Logging the API key:** `logger.debug("key=%s", self._api_key)` — never log any part of the key.
- **Retrying on 429/quota:** 429 and 4021 are short-circuit signals, not transient failures. Any retry call would fail identically and waste quota.
- **Catching QuotaExceededError inside register_and_persist:** db.py must re-raise it unchanged so main()'s loop can break. The existing `except Exception: raise` in db.py already does this correctly.
- **Placing except QuotaExceededError after except Exception in main.py:** Python evaluates except clauses in order — broad catch will swallow QuotaExceededError if placed first. The new clause MUST come first.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP client with timeout | Custom socket/urllib | `httpx.Client(timeout=10.0)` | Handles connect + read timeout correctly in one param |
| Request mocking in tests | Custom fake transport class | `respx.MockRouter` + `httpx.Client(transport=router)` | Exact URL matching, side effects (exceptions), response construction |
| JSON serialization of request | Manual string building | `client.post(..., json=payload)` | httpx handles Content-Type header + json.dumps atomically |
| Response envelope parsing | Custom envelope class | `resp.json()["meta"]["code"]` | Flat access; no framework overhead for this simple envelope |

**Key insight:** The registrar is a thin adapter — its only job is translating TrackingMore's HTTP protocol into `bool` / `QuotaExceededError`. Any logic beyond that (retries, logging, DB writes) belongs in its respective layer.

---

## Common Pitfalls

### Pitfall 1: QuotaExceededError Swallowed by Broad Catch

**What goes wrong:** `QuotaExceededError` is raised by `TrackingMoreRegistrar`, propagates through `register_and_persist` (which re-raises all exceptions), then hits `main.py`'s loop — but the broad `except Exception` at line 135 catches it first and the loop `continue`s instead of `break`ing.
**Why it happens:** Python evaluates except clauses in declaration order. If `except Exception` appears before `except QuotaExceededError`, the broad clause wins.
**How to avoid:** Place `except QuotaExceededError: ... break` immediately before the `except Exception: ... continue` clause. This is D-06's CRITICAL wiring note in CONTEXT.md.
**Warning signs:** Test for "quota short-circuit → remaining numbers unwritten" (see Validation Architecture) — if this test fails, the ordering is wrong.

### Pitfall 2: Transient vs Quota Retry Confusion

**What goes wrong:** Code retries on 429/4021 (quota) thinking it is a transient blip. Each retry consumes a quota slot or gets another 429.
**Why it happens:** 429 looks like "try again later" but for this free-tier use case it means "stop for this run entirely."
**How to avoid:** Branch on exception type BEFORE attempting retry. `QuotaExceededError` → raise immediately; `httpx.TimeoutException` / `httpx.ConnectError` / 5xx → one retry.

### Pitfall 3: Tracking Number in Exception Message (LOG-02)

**What goes wrong:** A formatted exception message like `f"Failed to register {tracking_number}"` is raised and caught by WR-04's `type(exc).__name__` log — but if any other logger elsewhere logs `str(exc)`, the tracking number leaks.
**Why it happens:** Habit of including context in exception strings for debugging.
**How to avoid:** All exceptions from `TrackingMoreRegistrar` must have structural-only messages: `"rate-limit"`, `"quota-exhausted"`, `"server-error"`. The `registrar.py` module docstring already mandates this (LOG-02).

### Pitfall 4: httpx.Client Not Closed

**What goes wrong:** `httpx.Client()` created without a context manager leaks connections.
**Why it happens:** `httpx.Client` holds a connection pool; not closing it leaves sockets open.
**How to avoid:** In production, `main()` owns the client lifetime — create once, pass to `TrackingMoreRegistrar`, close in the `finally` block. Alternatively use `with httpx.Client() as client:` if the client's scope is narrow. In tests, `respx.MockRouter` handles cleanup.

### Pitfall 5: courier_code Required (TRACK-05 Risk)

**What goes wrong:** `TrackingMoreRegistrar` omits `courier_code` from the request body (D-08 behavior when `carrier=None`), and TrackingMore returns error 4015 (invalid carrier) or 4013 (missing required parameter).
**Why it happens:** CONTEXT.md says "courier auto-detected" but the official Create API docs say `courier_code` is required. AUTO-DETECT is a separate `/v4/couriers/detect` endpoint, not a create-without-courier behavior.
**How to avoid:** Resolve Open Question Q-1 before implementation. If omitting is rejected, a pre-create detect call must be added, or parsers must supply a carrier.

### Pitfall 6: meta.code Absent From Response

**What goes wrong:** `resp.json()["meta"]["code"]` raises `KeyError` on an unexpected response format (e.g. CDN error pages, proxy interception).
**Why it happens:** TrackingMore may return non-JSON 5xx errors under high load or cloudflare interception.
**How to avoid:** Use `.get()` chains: `resp.json().get("meta", {}).get("code")`. Fall through to HTTP status code check if meta absent. Wrap the entire `_handle` method in a try/except for `json.JSONDecodeError` → treat as transient 5xx.

---

## Code Examples

### Verified Pattern: respx with injected transport (no global patching)

```python
# Source: https://lundberg.github.io/respx/guide/
import httpx
import respx
import pytest

@pytest.fixture
def mock_router() -> respx.MockRouter:
    """Injectable respx router for TrackingMoreRegistrar tests."""
    router = respx.MockRouter()
    return router

def test_success_creates_tracking(
    mock_router: respx.MockRouter,
    db_conn: sqlite3.Connection,
) -> None:
    """TRACK-01: successful create returns True; both DB rows written."""
    mock_router.post("https://api.trackingmore.com/v4/trackings/create").mock(
        return_value=httpx.Response(
            200, json={"meta": {"code": 200, "message": "Success"}, "data": {}}
        )
    )
    client = httpx.Client(transport=mock_router)
    registrar = TrackingMoreRegistrar(api_key="FAKE_KEY", client=client)

    result = register_and_persist(db_conn, "FAKE_MSG_001", "FAKE_TN_001", registrar)
    assert result is True
```

### Verified Pattern: Timeout as side_effect

```python
# Source: https://lundberg.github.io/respx/guide/
mock_router.post("...").mock(side_effect=httpx.TimeoutException("timeout"))
```

### Verified Pattern: httpx.Client timeout

```python
# Source: https://www.python-httpx.org/advanced/transports/
client = httpx.Client(timeout=10.0)  # applies to both connect and read
```

### Verified Pattern: response envelope access

```python
# Defensive access to handle non-standard responses (Pitfall 6)
try:
    body = resp.json()
except Exception:
    body = {}
meta_code = body.get("meta", {}).get("code")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| v3 meta-code-only responses | v4 returns both HTTP status AND meta.code | TrackingMore v4 launch | Can branch on either; HTTP status sufficient for 429; meta.code needed for 4016/4021 |
| requests + responses mock | httpx + respx mock | httpx became preferred in 2022+ | Native MockTransport; cleaner timeout API; already in this project |
| Detect API consumed quota (v2/v3) | v4 detect is free | v4 | Two-step detect+create has zero quota cost for the detect call |

**Deprecated / outdated:**
- SDK-documented codes 4101 / 4190: appear in older SDK READMEs, likely v3 codes. The v4 official status-code page lists 4016 / 4021. Handle both defensively.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | meta.code 4016 is the v4 duplicate/already-exists code (official status-code page) | Response Mapping Table | If wrong (uses 4101), already-exists would raise generic exception instead of returning True — TRACK-03 failure |
| A2 | meta.code 4021 is the v4 quota-exhausted code | Response Mapping Table | If wrong (uses 4190), quota exhaustion would fall through to generic 4xx → return False instead of QuotaExceededError — no run short-circuit |
| A3 | courier_code is required for /v4/trackings/create — omitting it returns an error rather than triggering auto-detect | Open Question Q-1 | If omitting IS accepted (auto-detect), D-08 works as locked. If NOT accepted, every AliExpress tracking (carrier=None) will fail to register. HIGH RISK. |
| A4 | 429 has no Retry-After header in TrackingMore responses | Response Mapping Table | If Retry-After exists and is short (e.g. 1s), a smarter policy could retry — but D-01 says no retry on 429 regardless, so this assumption is safe for Phase 5 |
| A5 | respx >=0.23 is compatible with httpx >=0.28 | Standard Stack | respx requires httpx>=0.25; 0.28 satisfies that — confirmed by PyPI metadata |

---

## Open Questions (RESOLVED)

### Q-1: Is courier_code truly required, or does omitting it trigger auto-detect? (RESOLVED)

**What we know:** The official Create API help article states `courier_code` is required. The Detect API (free, separate endpoint `/v4/couriers/detect`) returns suggested carrier codes from a tracking number. The CONTEXT.md D-08 decision says "omit the key entirely" when carrier is None — implying the API accepts a create without it.

**What's unclear:** Whether the v4 create endpoint actually accepts a request body without `courier_code` and performs internal auto-detection, or whether it returns error 4013/4015.

**Risk:** AliExpressParser returns `carrier=None` today. If courier_code is truly required and omitting it returns an error, ALL Phase 5 registrations would fail.

**Recommendation:** Before implementation begins, the planner must decide between two strategies:

1. **Two-step (detect + create):** Call `GET https://api.trackingmore.com/v4/couriers/detect?tracking_number=<X>` first (free, no quota cost), take the first suggested courier_code, then POST to create. Adds one HTTP call per new tracking but guarantees courier_code is populated.

2. **Attempt create-without-courier, observe response:** Implement D-08 as planned (omit when None), and handle the 4013/4015 error case gracefully (return False, log). If the free-tier test account confirms create-without-courier works, the question is resolved. If not, switch to strategy 1.

**Suggestion:** Start with strategy 2 (D-08 as locked); include a test that verifies the 4013 error case returns False gracefully. Add an open note that if live testing shows 100% registration failure with carrier=None, switch to strategy 1 (detect endpoint research is out of scope for Phase 5 but the endpoint is documented as free).

**RESOLUTION (2026-06-02, planner decision — strategy 2):** D-08 is a **locked CONTEXT.md decision** and is honored exactly as written: the create payload omits `courier_code` entirely when `carrier` is None/empty (Plan 02 Task 1, `if carrier: payload["courier_code"] = carrier`). The HIGH-RISK uncertainty in A3 (a courier-required rejection from the live API) does **not** require a new dedicated code path or a new test beyond `test_no_courier_code_when_carrier_none`: a courier-required rejection arrives as either 4013, 4015, or another non-4016/non-4021 4xx, and **all** of these already land on the existing "other 4xx → log ERROR (no PII), return False" branch in `_handle` (Plan 02 Task 1). That return-False path means the number is simply not persisted and auto-retries next cron via DEDUP-05 — a graceful, PII-safe deferral, not a crash. We therefore consciously accept strategy 2 with no extra implementation: D-08 as locked, courier-required rejections handled by the generic other-4xx → return False fallthrough. If a live smoke test (a deferred, out-of-scope idea) later shows 100% registration failure for `carrier=None`, the documented fallback is to add the free `/v4/couriers/detect` pre-call (strategy 1) in a follow-up phase — no Phase 5 plan change is needed now. This consciously trades a possible one-run deferral for staying inside the locked D-08 contract and the existing error-handling surface.

### Q-2: Response body when meta.code is absent (CDN / proxy errors) (RESOLVED)

**What we know:** TrackingMore returns a JSON envelope with meta.code for all documented cases. A CDN error page (Cloudflare 503, nginx 502) may return HTML or non-JSON.

**Recommendation:** Wrap `resp.json()` in `try/except` and treat JSON parse failure as a transient 5xx.

**RESOLUTION (2026-06-02):** Already mitigated — Plan 02 Task 1 bakes in the Pitfall 6 defensive parse (`try: body = resp.json() except Exception: body = {}`), so an absent or non-JSON body yields `meta_code = body.get("meta", {}).get("code") == None`. With `meta_code` None, `_handle` falls through to the HTTP status checks: a 5xx CDN/proxy error hits the `status_code >= 500` transient-retry branch (D-02 one retry then return False), and any other non-JSON 4xx lands on the other-4xx → return False fallthrough. No KeyError, no crash, no PII. No additional code or test beyond the defensive parse already specified in Plan 02 Task 1 is required.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | Entire project | ✓ | 3.14 (dev machine), 3.11+ on Pi target | — |
| httpx | HTTP calls to TrackingMore | ✓ | 0.28.1 installed | — |
| respx (dev) | D-04 mocked tests | ✓ (via pip install) | 0.23.1 | pytest-httpx 0.36.2 |
| TRACKINGMORE_API_KEY | D-05 startup validation | ✗ (not in env) | — | Fail-fast exit 1 per D-05; CI tests use mocked transport (no key needed) |

**Missing dependencies with no fallback:** TRACKINGMORE_API_KEY is not available in the dev/CI environment — by design. All tests must use mocked transport (D-04). Live validation requires a real key set in `.env` for manual smoke testing only.

**Missing dependencies with fallback:** None blocking.

---

## Validation Architecture

> nyquist_validation = true in config.json

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0+ |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_registrar.py -x -q` |
| Full suite command | `pytest -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TRACK-01 | POST /v4/trackings/create called with correct URL + headers | unit | `pytest tests/test_registrar.py::test_create_sends_correct_request -x` | No — Wave 0 |
| TRACK-01 | Successful 200 response → both DB rows written | integration | `pytest tests/test_registrar.py::test_success_creates_tracking -x` | No — Wave 0 |
| TRACK-02 | Tracking-Api-Key header populated from env var | unit | `pytest tests/test_registrar.py::test_api_key_in_header -x` | No — Wave 0 |
| TRACK-02 | Missing/empty TRACKINGMORE_API_KEY → main() returns 1, no Gmail/DB work | integration | `pytest tests/test_registrar.py::test_missing_api_key_exits_1 -x` | No — Wave 0 |
| TRACK-03 | 4016 already-exists → True returned + both rows written | unit | `pytest tests/test_registrar.py::test_already_exists_treated_as_success -x` | No — Wave 0 |
| TRACK-04 | 429 rate-limit → QuotaExceededError raised | unit | `pytest tests/test_registrar.py::test_rate_limit_raises_quota_error -x` | No — Wave 0 |
| TRACK-04 | 4021 quota → QuotaExceededError raised | unit | `pytest tests/test_registrar.py::test_quota_exhausted_raises_quota_error -x` | No — Wave 0 |
| TRACK-04 | QuotaExceededError → dispatch loop breaks; remaining numbers unwritten | integration | `pytest tests/test_registrar.py::test_quota_error_breaks_dispatch_loop -x` | No — Wave 0 |
| TRACK-04 | 5xx transient → one retry, then return False; number not in DB | unit | `pytest tests/test_registrar.py::test_5xx_retries_once_then_defers -x` | No — Wave 0 |
| TRACK-04 | TimeoutException → one retry, then return False; number not in DB | unit | `pytest tests/test_registrar.py::test_timeout_retries_once_then_defers -x` | No — Wave 0 |
| TRACK-05 | carrier=None → courier_code omitted from request body | unit | `pytest tests/test_registrar.py::test_no_courier_code_when_carrier_none -x` | No — Wave 0 |
| TRACK-05 | carrier="aliexpress" → courier_code present in request body | unit | `pytest tests/test_registrar.py::test_courier_code_included_when_carrier_set -x` | No — Wave 0 |

**Additional tests (implementation quality):**
- LOG-02 regression: tracking_number never appears in any log output from registrar
- D-05: API key value never logged (even on error)
- D-06: QuotaExceededError caught before broad except Exception (ordering test)
- Idempotency: QuotaExceededError leaves no DB rows (register_and_persist re-raises)

### Sampling Rate

- **Per task commit:** `pytest tests/test_registrar.py -x -q`
- **Per wave merge:** `pytest -x -q`
- **Phase gate:** `pytest -x -q && mypy --strict shipping_tracker/ && ruff check .` all green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_registrar.py` — new file; covers all TRACK-0x requirements above
- [ ] `tests/conftest.py` — add: `mock_router` fixture (respx.MockRouter), synthetic TrackingMore response builders
- [ ] `respx>=0.23` in `pyproject.toml [project.optional-dependencies] dev`
- [ ] `shipping_tracker/registrar.py` — add `QuotaExceededError` and `TrackingMoreRegistrar`

---

## Security Domain

> security_enforcement = true, asvs_level = 1

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | YES (API key) | TRACKINGMORE_API_KEY from env only; key never logged; D-05 validates presence |
| V3 Session Management | No | Stateless HTTP request/response; no session |
| V4 Access Control | Partial | API key scoped to this account; no user-level ACL concerns |
| V5 Input Validation | YES | tracking_number and courier_code values come from parser output; already validated upstream by parser |
| V6 Cryptography | No | No crypto; HTTPS for all TrackingMore calls (TLS handled by httpx/system CA) |

### Known Threat Patterns for this Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API key exposure in logs | Information Disclosure | D-05/D-07: never log key value; LOG-02 enforced in module docstring |
| API key in exception messages | Information Disclosure | Exception messages must be structural only (registrar.py LOG-02 docstring) |
| Tracking number in logs | Information Disclosure | LOG-02: all registrar log lines use message_id, never tracking_number |
| SSRF via malicious tracking_number | Tampering | Not applicable — URL is hardcoded (`_BASE_URL`), not constructed from user input |
| Dependency confusion (httpx/respx) | Supply Chain | Both packages slopcheck [OK]; pinned to >=known-good versions; source repos confirmed |

---

## Sources

### Primary (HIGH confidence)

- `trackingmore.com/api-status_code.html` — canonical meta.code reference; confirmed 4016=duplicate, 4021=quota, 429=rate-limit; confirmed v4 response codes differ from SDK README codes
- `github.com/trackingmore100/tracking-sdk-go` — confirmed `Tracking-Api-Key` header name via `req.Header.Set("Tracking-Api-Key", ...)` source
- `support.trackingmore.com/en/article/trackingmore-create-api-122cydg` — confirmed courier_code is REQUIRED per official help article
- `support.trackingmore.com/en/article/trackingmore-api-request-rate-limit-c0ye70` — confirmed 3 req/s limit, 429 wait 120s
- `lundberg.github.io/respx/guide/` — respx injectable transport pattern (constructor-injection, side_effect for TimeoutException)
- `python-httpx.org/advanced/transports/` — httpx MockTransport and timeout configuration
- PyPI registry — httpx 0.28.1, respx 0.23.1 version and metadata verified

### Secondary (MEDIUM confidence)

- `github.com/TrackingMore-API/trackingmore-sdk-python` — confirmed `courier_code` field name (not `courier`) and SDK-level response code table (4101/4190 — may be v3 codes)
- `github.com/TrackingMore-API/trackingmore-sdk-net` — confirmed 4101=duplicate, 4190=quota (defensive handling needed)
- `support.trackingmore.com/en/article/differences-among-3-versions-of-trackingmore-api-1ip0fmh` — v4 returns both HTTP + meta code; detect API is free in v4

### Tertiary (LOW confidence / ASSUMED)

- Claim that omitting `courier_code` triggers auto-detect behavior at create time: NOT confirmed by official docs — open question Q-1 [ASSUMED]
- Exact JSON shape of a successful 200 response `data` object (content of `data` field beyond `{}`) [ASSUMED]

---

## Metadata

**Confidence breakdown:**
- Standard stack (httpx, respx): HIGH — verified on PyPI, slopcheck OK, in-project already
- API auth header: HIGH — confirmed in official Go SDK source
- API response codes (4016, 4021, 429): HIGH — confirmed on official status-code page
- courier_code required/optional: LOW — conflicting signals; ASSUMED required per official help text
- Architecture patterns: HIGH — derived directly from locked decisions in CONTEXT.md

**Research date:** 2026-06-01
**Valid until:** 2026-07-01 (30 days; TrackingMore v4 API is stable; response codes unlikely to change)
