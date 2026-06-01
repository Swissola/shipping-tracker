"""Shared pytest fixtures for shipping-tracker tests.

PRIVACY: All fixtures use synthetic data. No real tracking numbers,
email addresses, order IDs, or personal names may appear in this file
or in tests/fixtures/. See CLAUDE.md privacy constraints.
"""

import sqlite3
from collections.abc import Generator

import pytest
from shipping_tracker.db import init_db  # type: ignore[import-not-found]


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
