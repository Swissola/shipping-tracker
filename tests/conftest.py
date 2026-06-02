"""Shared pytest fixtures for shipping-tracker tests.

PRIVACY: All fixtures use synthetic data. No real tracking numbers,
email addresses, order IDs, or personal names may appear in this file
or in tests/fixtures/. See CLAUDE.md privacy constraints.
"""

import sqlite3
from collections.abc import Generator

import pytest
import respx

from shipping_tracker.db import init_db


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
