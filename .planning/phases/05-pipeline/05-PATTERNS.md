# Phase 5: Pipeline - Pattern Map

**Mapped:** 2026-06-02
**Files analyzed:** 5 (2 new, 3 modified)
**Analogs found:** 5 / 5

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `shipping_tracker/registrar.py` (modify) | service / adapter | request-response | `shipping_tracker/registrar.py` (NullRegistrar) | exact — same module, adding `TrackingMoreRegistrar` and `QuotaExceededError` |
| `shipping_tracker/main.py` (modify) | orchestrator | request-response | `shipping_tracker/main.py` (existing dispatch loop) | exact — same file, three surgical additions |
| `shipping_tracker/db.py` (modify) | service | CRUD | `shipping_tracker/db.py` (existing `register_and_persist`) | exact — same file, one targeted change to pass `carrier` |
| `tests/test_registrar.py` (new) | test | request-response | `tests/test_db.py` | role-match — same test conventions, inline callable pattern |
| `tests/conftest.py` (modify) | config / fixture | — | `tests/conftest.py` (existing `db_conn` fixture) | exact — same file, adding `mock_router` + response builders |
| `pyproject.toml` (modify) | config | — | `pyproject.toml` (existing `[project.optional-dependencies] dev`) | exact — append one entry to `dev` list |

---

## Pattern Assignments

### `shipping_tracker/registrar.py` (modify — add `QuotaExceededError` and `TrackingMoreRegistrar`)

**Analog:** `shipping_tracker/registrar.py` (the existing module)

**Existing module structure** (lines 1-42 — full file):
```python
"""Registrar Protocol and NullRegistrar placeholder.

PRIVACY (LOG-02): implementations MUST NOT embed tracking_number, carrier, or
any email content in exception messages. The dispatch loop logs only message_id
and type(exc).__name__ — a careless implementation that includes PII in its
exception string would defeat that guarantee.
"""

from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class Registrar(Protocol):
    def __call__(self, tracking_number: str, carrier: str | None) -> bool: ...


class NullRegistrar:
    def __call__(self, tracking_number: str, carrier: str | None) -> bool:
        logger.debug("registrar.deferred")  # no tracking_number — LOG-02
        return False
```

**Import additions needed** — new imports to append to the existing block:
```python
import time
import httpx
```

**QuotaExceededError pattern** — new exception class, placed immediately after the module-level `logger` assignment, before `Registrar`:
```python
class QuotaExceededError(Exception):
    """Raised by TrackingMoreRegistrar on quota-exhausted (4021) or rate-limit (429).

    LOG-02: the message MUST NOT contain tracking_number, carrier, or API key.
    Caught specifically in main()'s dispatch loop BEFORE the broad except Exception (D-06).
    """
```

**TrackingMoreRegistrar core pattern** — new class after `NullRegistrar`:
```python
_BASE_URL = "https://api.trackingmore.com"

class TrackingMoreRegistrar:
    """Implements Registrar Protocol against TrackingMore v4 API.

    LOG-02: never embed tracking_number, carrier, or API key in exception messages.
    D-04: accepts an injected httpx.Client so tests feed fakes (zero live calls).
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
            payload["courier_code"] = carrier  # D-08: omit key entirely when None
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
                    time.sleep(self._retry_pause)  # D-02: one ~2s retry
                    continue
                return False  # second attempt failed — defer to next cron run
        return False  # unreachable; mypy requires it

    def _handle(self, resp: httpx.Response) -> bool:
        if resp.status_code == 429:
            raise QuotaExceededError("rate-limit")  # D-06; no PII in message
        try:
            body = resp.json()
        except Exception:
            body = {}  # non-JSON body (CDN/proxy error) — treat as transient 5xx
        meta_code = body.get("meta", {}).get("code")
        if meta_code in (200, 201):
            logger.info("registrar.created")  # D-07: INFO; no tracking_number
            return True
        if meta_code in (4016, 4101):  # 4101: defensive SDK-era code
            logger.info("registrar.already_exists")  # TRACK-03: duplicate = success
            return True
        if meta_code in (4021, 4190) or resp.status_code == 402:
            raise QuotaExceededError("quota-exhausted")  # D-06; no PII
        if resp.status_code >= 500:
            raise httpx.HTTPStatusError(
                "server-error",  # LOG-02: no f-string with tracking_number
                request=resp.request,
                response=resp,
            )
        logger.error("registrar.error code=%s", meta_code)  # D-07: ERROR, no PII
        return False  # other 4xx: log + don't persist + continue
```

**Logging pattern** — mirrors NullRegistrar's existing convention:
- Use `logger = logging.getLogger(__name__)` (already in module, line 14)
- Log event-name strings only (`"registrar.created"`, `"registrar.already_exists"`, `"registrar.error"`)
- Never include `tracking_number`, `carrier`, or `api_key` in any log call — LOG-02

---

### `shipping_tracker/main.py` (modify — three surgical additions)

**Analog:** `shipping_tracker/main.py` (the existing file)

**Addition 1 — import** (after existing `from shipping_tracker.registrar import NullRegistrar, Registrar` at line 22):
```python
from shipping_tracker.registrar import NullRegistrar, QuotaExceededError, Registrar, TrackingMoreRegistrar
```

**Addition 2 — D-05 API-key fail-fast** (lines 64-65, immediately after `configure_logging()`, before the DB open at line 67):
```python
    load_dotenv()
    configure_logging()

    # D-05: fail-fast before any I/O if TRACKINGMORE_API_KEY missing or empty
    api_key = os.getenv("TRACKINGMORE_API_KEY", "").strip()
    if not api_key:
        logger.error("config.missing_api_key")  # LOG-02: never log the key value
        return 1

    db_path = os.getenv("DATABASE_PATH", "data/shipping-tracker.db")
    # ... rest of existing setup
```

**Addition 3 — swap NullRegistrar and add QuotaExceededError catch** (lines 73 and 129-146):

Line 73 replacement:
```python
        # Phase 5: real registrar — injected client for testability (D-04)
        registrar: Registrar = TrackingMoreRegistrar(
            api_key=api_key,
            client=httpx.Client(timeout=10.0),
        )
```

Dispatch loop exception ordering — CRITICAL (D-06): `QuotaExceededError` MUST be caught BEFORE the broad `except Exception` at line 135. The new clause replaces the existing try/except block:
```python
            try:
                # ... existing DEDUP-03, parse, DEDUP-04 logic unchanged ...

                persisted = register_and_persist(
                    conn, email.message_id, result.tracking_number, registrar
                )
                if persisted:
                    tracking_results.append(result)

            except QuotaExceededError:
                # D-06: MUST be before broad except Exception (WR-04) or it's swallowed
                # D-01/D-07: one WARNING summary, no PII
                logger.warning("registrar.quota_exceeded")
                break  # short-circuit: remaining numbers retry via DEDUP-05 next cron

            except Exception as exc:
                # WR-04: existing handler — kept AFTER QuotaExceededError
                logger.error(
                    "pipeline.error id=%s type=%s",
                    email.message_id,
                    type(exc).__name__,
                )
                continue
```

**httpx import** — add to the existing stdlib import block (after `sqlite3`):
```python
import httpx
```

**Lifetime management** — `httpx.Client` created in `main()` must be closed. Wrap with try/finally or context manager around the outer `try` block:
```python
    http_client = httpx.Client(timeout=10.0)
    registrar: Registrar = TrackingMoreRegistrar(api_key=api_key, client=http_client)
    try:
        # ... existing init_db, fetch, dispatch loop
    finally:
        conn.close()
        http_client.close()
```

---

### `shipping_tracker/db.py` (modify — pass `carrier` through `register_and_persist`)

**Analog:** `shipping_tracker/db.py`, function `register_and_persist` (lines 67-103)

**Existing call site** (line 88 — the only change needed):
```python
        success = registrar(tracking_number, None)  # carrier deferred to Phase 5
```

**Updated call site** — `register_and_persist` gains a `carrier` parameter and passes it through:
```python
def register_and_persist(
    conn: sqlite3.Connection,
    message_id: str,
    tracking_number: str,
    registrar: Registrar,
    carrier: str | None = None,  # Phase 5: fed from TrackingInfo.carrier (D-08)
) -> bool:
    ...
        success = registrar(tracking_number, carrier)  # no longer hardcoded None
```

The `except Exception: raise` at line 89-90 already propagates `QuotaExceededError` unchanged — no modification needed there.

---

### `tests/test_registrar.py` (new file)

**Analog:** `tests/test_db.py` — same project test conventions throughout

**File header pattern** (from `tests/test_db.py`, lines 1-24):
```python
"""Tests for shipping_tracker.registrar — TRACK-01..05 acceptance criteria.

All test data is synthetic — FAKE-prefixed tracking numbers, message IDs, and API keys.
No real tracking numbers, email addresses, or order references.
"""

import sqlite3

import httpx
import pytest
import respx

from shipping_tracker.db import register_and_persist
from shipping_tracker.registrar import QuotaExceededError, TrackingMoreRegistrar
from tests.fixtures.fake_db import FAKE_MESSAGE_ID_1, FAKE_TRACKING_NUMBER_1
```

**Inline fake callable pattern** (from `tests/test_db.py`, lines 30-44) — used for dispatch-loop integration tests:
```python
def _make_registrar(router: respx.MockRouter) -> TrackingMoreRegistrar:
    """Build a TrackingMoreRegistrar backed by a respx mock transport."""
    client = httpx.Client(transport=router)
    return TrackingMoreRegistrar(api_key="FAKE_KEY", client=client)
```

**Unit test structure** (from `tests/test_db.py`, lines 51-99 — section + function naming pattern):
```python
# ---------------------------------------------------------------------------
# TRACK-01: POST /v4/trackings/create — correct URL and headers
# ---------------------------------------------------------------------------

def test_create_sends_correct_request(mock_router: respx.MockRouter) -> None:
    """TRACK-01: correct endpoint URL and Tracking-Api-Key header are sent."""
    ...

# ---------------------------------------------------------------------------
# TRACK-03: already-exists (4016) treated as success
# ---------------------------------------------------------------------------

def test_already_exists_treated_as_success(mock_router: respx.MockRouter, db_conn: sqlite3.Connection) -> None:
    """TRACK-03: meta.code 4016 returns True; both DB rows written."""
    ...
```

**respx mock construction pattern** (from RESEARCH.md Code Examples):
```python
def test_success_creates_tracking(
    mock_router: respx.MockRouter,
    db_conn: sqlite3.Connection,
) -> None:
    """TRACK-01: successful 200 response → both DB rows written."""
    mock_router.post("https://api.trackingmore.com/v4/trackings/create").mock(
        return_value=httpx.Response(
            200, json={"meta": {"code": 200, "message": "Success"}, "data": {}}
        )
    )
    registrar = _make_registrar(mock_router)
    result = register_and_persist(db_conn, FAKE_MESSAGE_ID_1, FAKE_TRACKING_NUMBER_1, registrar)
    assert result is True
```

**Timeout side_effect pattern** (from RESEARCH.md Code Examples):
```python
mock_router.post("https://api.trackingmore.com/v4/trackings/create").mock(
    side_effect=httpx.TimeoutException("timeout")
)
```

**LOG-02 regression pattern** (from `tests/test_db.py`, lines 368-376):
```python
def test_log02_no_tracking_number_in_logs(
    mock_router: respx.MockRouter,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """LOG-02: tracking_number must not appear in any log record from registrar."""
    ...
    for record in caplog.records:
        assert FAKE_TRACKING_NUMBER_1 not in record.message
```

**Fixtures used:** `db_conn` (existing, from `conftest.py`), `mock_router` (new, added to `conftest.py`).

---

### `tests/conftest.py` (modify — add `mock_router` fixture and response builders)

**Analog:** `tests/conftest.py` (the existing file, lines 1-36)

**Existing fixture structure to mirror** (lines 16-36):
```python
@pytest.fixture
def db_conn() -> Generator[sqlite3.Connection, None, None]:
    """In-memory sqlite3.Connection with schema already initialised via init_db.

    PRIVACY: never use real tracking numbers or message IDs in tests.
    All test data must use FAKE-prefixed synthetic values.
    """
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    yield conn
    conn.close()
```

**New fixture to add** — same docstring privacy note convention, same import style:
```python
import httpx
import respx

@pytest.fixture
def mock_router() -> respx.MockRouter:
    """Injectable respx MockRouter for TrackingMoreRegistrar tests.

    PRIVACY: zero live calls — all HTTP is intercepted by respx.
    Pass to httpx.Client(transport=mock_router) in each test.
    """
    return respx.MockRouter()
```

**New response builder helpers** — module-level functions (not fixtures), mirrors the inline callable pattern in `test_db.py`:
```python
def make_success_response() -> httpx.Response:
    """Synthetic 200/success response from TrackingMore v4."""
    return httpx.Response(200, json={"meta": {"code": 200, "message": "Success"}, "data": {}})

def make_already_exists_response() -> httpx.Response:
    """Synthetic 4016/already-exists response (TRACK-03)."""
    return httpx.Response(400, json={"meta": {"code": 4016, "message": "Tracking already exists."}, "data": {}})

def make_quota_response() -> httpx.Response:
    """Synthetic 4021/quota-exhausted response (D-01/D-06)."""
    return httpx.Response(400, json={"meta": {"code": 4021, "message": "Remaining quota is deficient."}, "data": {}})

def make_rate_limit_response() -> httpx.Response:
    """Synthetic 429/rate-limit response (D-01/D-06)."""
    return httpx.Response(429, json={"meta": {"code": 429, "message": "Too Many Requests"}, "data": {}})

def make_5xx_response() -> httpx.Response:
    """Synthetic 500/server-error response (D-02 transient)."""
    return httpx.Response(500, json={"meta": {"code": 500, "message": "Internal Server Error"}, "data": {}})
```

**New import additions** (append to existing `conftest.py` import block):
```python
import httpx
import respx
```

---

### `pyproject.toml` (modify — add `respx` to dev dependencies)

**Analog:** `pyproject.toml`, `[project.optional-dependencies] dev` section (lines 19-25)

**Existing pattern** (lines 18-25):
```toml
[project.optional-dependencies]
dev = [
    "ruff>=0.15",
    "mypy>=2.1",
    "pytest>=9.0",
    "pre-commit>=4.6",
    "google-api-python-client-stubs>=1.37",
]
```

**Modified section** — append one entry, maintain alphabetical-ish order:
```toml
[project.optional-dependencies]
dev = [
    "ruff>=0.15",
    "mypy>=2.1",
    "pytest>=9.0",
    "pre-commit>=4.6",
    "respx>=0.23",
    "google-api-python-client-stubs>=1.37",
]
```

---

## Shared Patterns

### LOG-02: PII-safe logging — apply to all registrar log calls and exception messages

**Source:** `shipping_tracker/registrar.py` module docstring (lines 1-7) + `shipping_tracker/main.py` lines 135-146

```python
# CORRECT — structural key only, no PII:
logger.debug("registrar.deferred")
logger.info("registrar.created")
logger.error("registrar.error code=%s", meta_code)
logger.warning("registrar.quota_exceeded")

# CORRECT — exception message is structural, no PII:
raise QuotaExceededError("rate-limit")
raise QuotaExceededError("quota-exhausted")

# WRONG — LOG-02 violation:
logger.info("registered tracking_number=%s", tracking_number)
raise QuotaExceededError(f"quota exhausted for {tracking_number}")
```

**Apply to:** `TrackingMoreRegistrar._handle()`, `TrackingMoreRegistrar.__call__()`, `QuotaExceededError` instantiation sites.

### WR-04: Per-email broad exception handler — do not disturb, only insert BEFORE it

**Source:** `shipping_tracker/main.py` lines 135-146

```python
            except Exception as exc:
                # WR-04: PII-safe — log message_id + exception TYPE only (LOG-02).
                # NOT logger.exception — the traceback and exception message could
                # embed email content if a parser/registrar raised e.g.
                # ValueError(f"bad body: {body}"). type(exc).__name__ is structural,
                # never PII.
                logger.error(
                    "pipeline.error id=%s type=%s",
                    email.message_id,
                    type(exc).__name__,
                )
                continue
```

**Apply to:** The `except QuotaExceededError` clause MUST be placed immediately before this block in `main.py`. Python evaluates except clauses in order — if this broad catch appears first, it swallows `QuotaExceededError` and the loop never breaks.

### `from __future__ import annotations` — all new Python modules

**Source:** `shipping_tracker/registrar.py` line 9, `shipping_tracker/main.py` line 3, `shipping_tracker/db.py` line 3

```python
from __future__ import annotations
```

**Apply to:** No new modules are created in this phase, but confirm the existing `registrar.py` already has this (it does, line 9).

### Synthetic fixture naming convention — all test data

**Source:** `tests/fixtures/fake_db.py` lines 8-15, `tests/conftest.py` docstring lines 3-5

```python
# Message IDs — FAKEMSGID prefix
FAKE_MESSAGE_ID_1 = "FAKEMSGID001"

# Tracking numbers — FAKETRACK prefix, no real carrier format
FAKE_TRACKING_NUMBER_1 = "FAKETRACK001CN"

# API keys in tests — FAKE_KEY (never a real key shape)
api_key = "FAKE_KEY"
```

**Apply to:** All new synthetic values in `tests/test_registrar.py` and `tests/conftest.py`. Reuse `FAKE_MESSAGE_ID_1` and `FAKE_TRACKING_NUMBER_1` from `tests/fixtures/fake_db.py` rather than defining duplicates.

### Section-header comment style in test files

**Source:** `tests/test_db.py` lines 28-29, 48-50, 103-104 (repeated pattern)

```python
# ---------------------------------------------------------------------------
# DEDUP-05: register_and_persist
# ---------------------------------------------------------------------------
```

**Apply to:** All requirement-boundary sections in `tests/test_registrar.py` (`TRACK-01`, `TRACK-02`, `TRACK-03`, `TRACK-04`, `TRACK-05`, `D-05`, `D-06`, `LOG-02`).

---

## No Analog Found

All files have close analogs in the codebase. No fallback to RESEARCH.md patterns required — the RESEARCH.md architecture patterns were used only to validate what the planner already provided.

---

## Metadata

**Analog search scope:** `C:\Projects\shipping-tracker\shipping_tracker\`, `C:\Projects\shipping-tracker\tests\`
**Files scanned:** 10 source files read in full
**Pattern extraction date:** 2026-06-02
