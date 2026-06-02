"""Shared pytest fixtures for shipping-tracker tests.

PRIVACY: All fixtures use synthetic data. No real tracking numbers,
email addresses, order IDs, or personal names may appear in this file
or in tests/fixtures/. See CLAUDE.md privacy constraints.
"""

import sqlite3
from collections.abc import Generator

import httpx
import pytest
import respx

from shipping_tracker.db import init_db


@pytest.fixture
def synthetic_email_body() -> str:
    """A synthetic AliExpress-style email body with fake tracking data."""
    return (
        "Your order has shipped!\n"
        "Tracking number: FAKE1234567890\n"
        "Carrier: FAKECARRIER\n"
    )


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


@pytest.fixture
def mock_router() -> respx.MockRouter:
    """Injectable respx MockRouter for TrackingMoreRegistrar tests (D-04).

    PRIVACY: zero live calls — all HTTP is intercepted by respx.
    Wire into a client via httpx.Client(transport=httpx.MockTransport(
    mock_router.handler)) (respx 0.23 MockRouter is not itself a transport) so
    no request ever escapes to the real TrackingMore API or consumes quota.
    """
    return respx.MockRouter()


# ---------------------------------------------------------------------------
# Synthetic TrackingMore v4 response builders (D-04)
#
# Module-level helpers (NOT fixtures) returning httpx.Response objects with the
# exact meta.code integers from 05-RESEARCH.md's Response -> Outcome Mapping
# Table. All bodies are synthetic — no real tracking numbers, emails, or order
# references appear here. See CLAUDE.md privacy constraints.
# ---------------------------------------------------------------------------


def make_success_response() -> httpx.Response:
    """Synthetic 200/success response from TrackingMore v4 (meta.code 200)."""
    return httpx.Response(
        200, json={"meta": {"code": 200, "message": "Success"}, "data": {}}
    )


def make_already_exists_response() -> httpx.Response:
    """Synthetic already-exists response (HTTP 400, meta.code 4016) — TRACK-03."""
    return httpx.Response(
        400,
        json={
            "meta": {"code": 4016, "message": "Tracking already exists."},
            "data": {},
        },
    )


def make_quota_response() -> httpx.Response:
    """Synthetic quota-exhausted response (HTTP 400, meta.code 4021) — D-01/D-06."""
    return httpx.Response(
        400,
        json={
            "meta": {"code": 4021, "message": "Remaining quota is deficient."},
            "data": {},
        },
    )


def make_rate_limit_response() -> httpx.Response:
    """Synthetic rate-limit response (HTTP 429, meta.code 429) — D-01/D-06."""
    return httpx.Response(
        429, json={"meta": {"code": 429, "message": "Too Many Requests"}, "data": {}}
    )


def make_5xx_response() -> httpx.Response:
    """Synthetic server-error response (HTTP 500, meta.code 500) — D-02 transient."""
    return httpx.Response(
        500,
        json={"meta": {"code": 500, "message": "Internal Server Error"}, "data": {}},
    )
