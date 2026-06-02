"""Tests for shipping_tracker.registrar — TRACK-01..05 acceptance criteria.

All test data is synthetic — FAKE-prefixed tracking numbers, message IDs, and
API keys. No real tracking numbers, email addresses, or order references.
See CLAUDE.md privacy constraints.

WAVE 0 (Nyquist): this suite is authored BEFORE the source it tests. The imports
of QuotaExceededError and TrackingMoreRegistrar from shipping_tracker.registrar
fail RED until Plan 02 (Wave 2) lands them — that is the intended, required state.

Every HTTP interaction is intercepted by respx (D-04): zero live calls, no
free-tier quota consumed, CI needs no secret.
"""

import sqlite3

import httpx
import pytest
import respx

from shipping_tracker.db import (
    is_email_processed,
    is_tracking_registered,
    register_and_persist,
)
from shipping_tracker.registrar import (
    QuotaExceededError,
    TrackingMoreRegistrar,
)
from tests.fixtures.fake_db import (
    FAKE_MESSAGE_ID_1,
    FAKE_MESSAGE_ID_2,
    FAKE_TRACKING_NUMBER_1,
    FAKE_TRACKING_NUMBER_2,
)

_CREATE_URL = "https://api.trackingmore.com/v4/trackings/create"
_FAKE_API_KEY = "FAKE_KEY"


# ---------------------------------------------------------------------------
# Helpers — synthetic registrar wiring (all transports mocked, D-04)
# ---------------------------------------------------------------------------


def _make_registrar(router: respx.MockRouter) -> TrackingMoreRegistrar:
    """Build a TrackingMoreRegistrar backed by a respx mock transport.

    retry_pause=0 and retry_jitter=0 keep transient/timeout retry tests fast and
    deterministic (no real sleep, no random pause) now that jitter is on by
    default (WR-05). The injected client (D-04) guarantees no live calls.
    """
    # respx 0.23 MockRouter is not itself an httpx transport; wrap its handler in
    # httpx.MockTransport so the injected client (D-04) routes through the mock
    # (zero live calls). route.called / route.calls remain fully functional.
    client = httpx.Client(transport=httpx.MockTransport(router.handler))
    return TrackingMoreRegistrar(
        api_key=_FAKE_API_KEY, client=client, retry_pause=0, retry_jitter=0
    )


def _success_route(router: respx.MockRouter) -> None:
    router.post(_CREATE_URL).mock(
        return_value=httpx.Response(
            200, json={"meta": {"code": 200, "message": "Success"}, "data": {}}
        )
    )


# ---------------------------------------------------------------------------
# TRACK-01: POST /v4/trackings/create — correct URL and headers
# ---------------------------------------------------------------------------


def test_create_sends_correct_request(mock_router: respx.MockRouter) -> None:
    """TRACK-01: POST goes to the create endpoint with the Tracking-Api-Key header."""
    route = mock_router.post(_CREATE_URL).mock(
        return_value=httpx.Response(
            200, json={"meta": {"code": 200, "message": "Success"}, "data": {}}
        )
    )
    registrar = _make_registrar(mock_router)

    registrar(FAKE_TRACKING_NUMBER_1, None)

    assert route.called, "registrar must POST to the create endpoint"
    request = route.calls.last.request
    assert str(request.url) == _CREATE_URL
    assert request.headers["Tracking-Api-Key"] == _FAKE_API_KEY


def test_success_creates_tracking(
    mock_router: respx.MockRouter, db_conn: sqlite3.Connection
) -> None:
    """TRACK-01: a 200/meta.code 200 response writes BOTH DB rows; returns True."""
    _success_route(mock_router)
    registrar = _make_registrar(mock_router)

    result = register_and_persist(
        db_conn, FAKE_MESSAGE_ID_1, FAKE_TRACKING_NUMBER_1, registrar
    )

    assert result is True
    assert is_email_processed(db_conn, FAKE_MESSAGE_ID_1) is True
    assert is_tracking_registered(db_conn, FAKE_TRACKING_NUMBER_1) is True


# ---------------------------------------------------------------------------
# TRACK-02: API key handling (env-sourced, fail-fast, never hardcoded)
# ---------------------------------------------------------------------------


def test_api_key_in_header(mock_router: respx.MockRouter) -> None:
    """TRACK-02: the Tracking-Api-Key header carries the injected key value."""
    route = mock_router.post(_CREATE_URL).mock(
        return_value=httpx.Response(
            200, json={"meta": {"code": 200, "message": "Success"}, "data": {}}
        )
    )
    registrar = _make_registrar(mock_router)

    registrar(FAKE_TRACKING_NUMBER_1, None)

    assert route.calls.last.request.headers["Tracking-Api-Key"] == _FAKE_API_KEY


def test_missing_api_key_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    """TRACK-02 / D-05: empty TRACKINGMORE_API_KEY → main() returns 1, no fetch/DB.

    The Gmail fetch is monkeypatched to raise if invoked, proving the fail-fast
    check short-circuits before any I/O.
    """
    import shipping_tracker.main as main_mod

    monkeypatch.setenv("TRACKINGMORE_API_KEY", "")

    def _explode(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("fetch must not run when API key is missing")

    monkeypatch.setattr(main_mod, "fetch_unread_shipping_emails", _explode)

    assert main_mod.main() == 1


# ---------------------------------------------------------------------------
# TRACK-03: already-exists (4016) treated as success
# ---------------------------------------------------------------------------


def test_already_exists_treated_as_success(
    mock_router: respx.MockRouter, db_conn: sqlite3.Connection
) -> None:
    """TRACK-03: meta.code 4016 returns True and writes both DB rows."""
    mock_router.post(_CREATE_URL).mock(
        return_value=httpx.Response(
            400,
            json={
                "meta": {"code": 4016, "message": "Tracking already exists."},
                "data": {},
            },
        )
    )
    registrar = _make_registrar(mock_router)

    result = register_and_persist(
        db_conn, FAKE_MESSAGE_ID_1, FAKE_TRACKING_NUMBER_1, registrar
    )

    assert result is True
    assert is_email_processed(db_conn, FAKE_MESSAGE_ID_1) is True
    assert is_tracking_registered(db_conn, FAKE_TRACKING_NUMBER_1) is True


# ---------------------------------------------------------------------------
# TRACK-04: rate-limit, quota, transient/timeout handling
# ---------------------------------------------------------------------------


def test_rate_limit_raises_quota_error(mock_router: respx.MockRouter) -> None:
    """TRACK-04: HTTP 429 → QuotaExceededError (D-06; no retry, short-circuit)."""
    mock_router.post(_CREATE_URL).mock(
        return_value=httpx.Response(
            429,
            json={"meta": {"code": 429, "message": "Too Many Requests"}, "data": {}},
        )
    )
    registrar = _make_registrar(mock_router)

    with pytest.raises(QuotaExceededError):
        registrar(FAKE_TRACKING_NUMBER_1, None)


def test_quota_exhausted_raises_quota_error(mock_router: respx.MockRouter) -> None:
    """TRACK-04: meta.code 4021 → QuotaExceededError (D-01 short-circuit)."""
    mock_router.post(_CREATE_URL).mock(
        return_value=httpx.Response(
            400,
            json={
                "meta": {"code": 4021, "message": "Remaining quota is deficient."},
                "data": {},
            },
        )
    )
    registrar = _make_registrar(mock_router)

    with pytest.raises(QuotaExceededError):
        registrar(FAKE_TRACKING_NUMBER_1, None)


def test_quota_error_breaks_dispatch_loop(
    mock_router: respx.MockRouter, db_conn: sqlite3.Connection
) -> None:
    """TRACK-04 / D-06: a QuotaExceededError breaks the loop; the SECOND number
    is never written (retry-next-run proof, DEDUP-05 path).

    The first create raises QuotaExceededError; register_and_persist re-raises it
    (db.py propagates), so the dispatch loop's break leaves the second tracking
    number out of registered_tracking.
    """
    mock_router.post(_CREATE_URL).mock(
        return_value=httpx.Response(
            400,
            json={
                "meta": {"code": 4021, "message": "Remaining quota is deficient."},
                "data": {},
            },
        )
    )
    registrar = _make_registrar(mock_router)

    pending = [
        (FAKE_MESSAGE_ID_1, FAKE_TRACKING_NUMBER_1),
        (FAKE_MESSAGE_ID_2, FAKE_TRACKING_NUMBER_2),
    ]
    # Mirror main()'s dispatch loop: QuotaExceededError breaks before the
    # second number is processed.
    for message_id, tracking_number in pending:
        try:
            register_and_persist(db_conn, message_id, tracking_number, registrar)
        except QuotaExceededError:
            break

    # First number short-circuited (no row), second never attempted.
    assert is_tracking_registered(db_conn, FAKE_TRACKING_NUMBER_1) is False
    assert is_tracking_registered(db_conn, FAKE_TRACKING_NUMBER_2) is False


def test_5xx_retries_once_then_defers(
    mock_router: respx.MockRouter, db_conn: sqlite3.Connection
) -> None:
    """TRACK-04 / D-02: two 500s → one retry, then return False; number not in DB."""
    route = mock_router.post(_CREATE_URL).mock(
        return_value=httpx.Response(
            500,
            json={
                "meta": {"code": 500, "message": "Internal Server Error"},
                "data": {},
            },
        )
    )
    registrar = _make_registrar(mock_router)

    result = register_and_persist(
        db_conn, FAKE_MESSAGE_ID_1, FAKE_TRACKING_NUMBER_1, registrar
    )

    assert result is False
    assert route.call_count == 2, "5xx must trigger exactly one retry (two attempts)"
    assert is_tracking_registered(db_conn, FAKE_TRACKING_NUMBER_1) is False


def test_timeout_retries_once_then_defers(
    mock_router: respx.MockRouter, db_conn: sqlite3.Connection
) -> None:
    """TRACK-04 / D-02: a timeout on both attempts → return False; one retry."""
    route = mock_router.post(_CREATE_URL).mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    registrar = _make_registrar(mock_router)

    result = register_and_persist(
        db_conn, FAKE_MESSAGE_ID_1, FAKE_TRACKING_NUMBER_1, registrar
    )

    assert result is False
    assert route.call_count == 2, "timeout must trigger exactly one retry"
    assert is_tracking_registered(db_conn, FAKE_TRACKING_NUMBER_1) is False


# ---------------------------------------------------------------------------
# WR-05: per-run retry budget bound + jittered retry pause
# ---------------------------------------------------------------------------


def test_retry_budget_bounds_cumulative_retries(mock_router: respx.MockRouter) -> None:
    """WR-05: the per-run retry budget caps total retries across the batch.

    With max_total_retries=1 the first retry-eligible call spends the only budget
    unit (2 requests: original + retry); the second call finds the budget exhausted
    and defers immediately (1 request, no retry). Total = 3, not 4.
    """
    route = mock_router.post(_CREATE_URL).mock(
        return_value=httpx.Response(
            500,
            json={"meta": {"code": 500, "message": "Server Error"}, "data": {}},
        )
    )
    client = httpx.Client(transport=httpx.MockTransport(mock_router.handler))
    registrar = TrackingMoreRegistrar(
        api_key=_FAKE_API_KEY,
        client=client,
        retry_pause=0,
        retry_jitter=0,
        max_total_retries=1,
    )

    first = registrar(FAKE_TRACKING_NUMBER_1, None)
    second = registrar(FAKE_TRACKING_NUMBER_2, None)

    assert first is False
    assert second is False
    assert route.call_count == 3, (
        "budget of 1 → first call retries (2 reqs), second defers (1 req) = 3"
    )


def test_retry_pause_includes_jitter(
    mock_router: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WR-05: each retry pause is retry_pause + random.uniform(0, retry_jitter)."""
    slept: list[float] = []
    monkeypatch.setattr("shipping_tracker.registrar.time.sleep", slept.append)
    monkeypatch.setattr(
        "shipping_tracker.registrar.random.uniform", lambda _lo, _hi: 0.5
    )

    mock_router.post(_CREATE_URL).mock(
        return_value=httpx.Response(
            500,
            json={"meta": {"code": 500, "message": "Server Error"}, "data": {}},
        )
    )
    client = httpx.Client(transport=httpx.MockTransport(mock_router.handler))
    registrar = TrackingMoreRegistrar(
        api_key=_FAKE_API_KEY, client=client, retry_pause=2.0, retry_jitter=1.0
    )

    assert registrar(FAKE_TRACKING_NUMBER_1, None) is False
    assert slept == [2.5], "one retry should pause for retry_pause + jitter (2.0 + 0.5)"


# ---------------------------------------------------------------------------
# TRACK-05: courier_code payload behavior (D-08)
# ---------------------------------------------------------------------------


def test_no_courier_code_when_carrier_none(mock_router: respx.MockRouter) -> None:
    """TRACK-05 / D-08: carrier=None omits courier_code from the request body."""
    import json

    route = mock_router.post(_CREATE_URL).mock(
        return_value=httpx.Response(
            200, json={"meta": {"code": 200, "message": "Success"}, "data": {}}
        )
    )
    registrar = _make_registrar(mock_router)

    registrar(FAKE_TRACKING_NUMBER_1, None)

    body = json.loads(route.calls.last.request.content)
    assert "tracking_number" in body
    assert "courier_code" not in body


def test_courier_code_included_when_carrier_set(mock_router: respx.MockRouter) -> None:
    """TRACK-05 / D-08: a non-empty carrier adds courier_code to the request body."""
    import json

    route = mock_router.post(_CREATE_URL).mock(
        return_value=httpx.Response(
            200, json={"meta": {"code": 200, "message": "Success"}, "data": {}}
        )
    )
    registrar = _make_registrar(mock_router)

    registrar(FAKE_TRACKING_NUMBER_1, "aliexpress")

    body = json.loads(route.calls.last.request.content)
    assert body["courier_code"] == "aliexpress"


# ---------------------------------------------------------------------------
# LOG-02: tracking_number never logged
# ---------------------------------------------------------------------------


def test_tracking_number_never_logged(
    mock_router: respx.MockRouter, caplog: pytest.LogCaptureFixture
) -> None:
    """LOG-02: tracking_number appears in no log record across success + error paths."""
    success = mock_router.post(_CREATE_URL).mock(
        return_value=httpx.Response(
            200, json={"meta": {"code": 200, "message": "Success"}, "data": {}}
        )
    )
    registrar = _make_registrar(mock_router)

    with caplog.at_level("DEBUG"):
        registrar(FAKE_TRACKING_NUMBER_1, None)

        # Drive an error path too (other 4xx → return False, logged).
        success.mock(
            return_value=httpx.Response(
                400, json={"meta": {"code": 4014, "message": "Invalid."}, "data": {}}
            )
        )
        registrar(FAKE_TRACKING_NUMBER_1, None)

    for record in caplog.records:
        assert FAKE_TRACKING_NUMBER_1 not in record.getMessage()


# ---------------------------------------------------------------------------
# D-05: API key value never logged
# ---------------------------------------------------------------------------


def test_api_key_never_logged(
    mock_router: respx.MockRouter,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """D-05: the API key value never reaches any log record (missing-key + error)."""
    import shipping_tracker.main as main_mod

    # Missing-key fail-fast path: must log an error WITHOUT the key value.
    monkeypatch.setenv("TRACKINGMORE_API_KEY", "")
    monkeypatch.setattr(
        main_mod,
        "fetch_unread_shipping_emails",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("fetch must not run")),
    )
    with caplog.at_level("DEBUG"):
        assert main_mod.main() == 1

    # Error path on the registrar with the FAKE key set.
    mock_router.post(_CREATE_URL).mock(
        return_value=httpx.Response(
            400, json={"meta": {"code": 4014, "message": "Invalid."}, "data": {}}
        )
    )
    registrar = _make_registrar(mock_router)
    with caplog.at_level("DEBUG"):
        registrar(FAKE_TRACKING_NUMBER_1, None)

    for record in caplog.records:
        assert _FAKE_API_KEY not in record.getMessage()


# ---------------------------------------------------------------------------
# D-06: QuotaExceededError ordering — propagates rather than being swallowed
# ---------------------------------------------------------------------------


def test_quota_error_ordering(
    mock_router: respx.MockRouter, db_conn: sqlite3.Connection
) -> None:
    """D-06: QuotaExceededError propagates through register_and_persist (db.py
    re-raises) so main()'s loop can catch it before the broad except and break.

    Also asserts it is not a subclass that the broad ``except Exception`` would
    need to special-case incorrectly: it IS an Exception (so the broad clause
    *would* catch it if ordered first — proving the ordering requirement), and
    register_and_persist does not swallow it.
    """
    assert issubclass(QuotaExceededError, Exception)

    mock_router.post(_CREATE_URL).mock(
        return_value=httpx.Response(
            400,
            json={
                "meta": {"code": 4021, "message": "Remaining quota is deficient."},
                "data": {},
            },
        )
    )
    registrar = _make_registrar(mock_router)

    with pytest.raises(QuotaExceededError):
        register_and_persist(
            db_conn, FAKE_MESSAGE_ID_1, FAKE_TRACKING_NUMBER_1, registrar
        )

    # Re-raise (not swallow) means no rows were written.
    assert is_email_processed(db_conn, FAKE_MESSAGE_ID_1) is False
    assert is_tracking_registered(db_conn, FAKE_TRACKING_NUMBER_1) is False
