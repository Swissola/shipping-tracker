"""Unit tests for shipping_tracker.gmail.query.

Covers GMAIL-02 query string construction for single/multiple senders and window sizes.
All test data is synthetic — no real sender addresses.
"""

from shipping_tracker.gmail.query import build_query


def test_build_query_single_sender() -> None:
    """build_query produces correct q string for a single sender."""
    q = build_query(["@aliexpress.com"], 30)
    assert q == "is:unread from:(@aliexpress.com) newer_than:30d"


def test_build_query_multiple_senders() -> None:
    """build_query joins multiple senders with OR and includes correct window."""
    q = build_query(["@aliexpress.com", "ship@fakestore.example.com"], 14)
    assert "OR" in q
    assert "newer_than:14d" in q
    assert "from:(" in q


def test_build_query_multiple_senders_exact() -> None:
    """build_query produces the exact expected string for two senders."""
    q = build_query(["@aliexpress.com", "ship@fakestore.example.com"], 14)
    expected = (
        "is:unread from:(@aliexpress.com OR ship@fakestore.example.com) newer_than:14d"
    )
    assert q == expected


def test_build_query_empty_senders_returns_unread_query() -> None:
    """build_query with empty senders returns valid unread query without from clause."""
    q = build_query([], 30)
    assert "newer_than:30d" in q
    assert "from:()" not in q
    assert "is:unread" in q


def test_build_query_window_days_in_result() -> None:
    """build_query respects the window_days parameter."""
    q = build_query(["@fakestore.example.com"], 7)
    assert "newer_than:7d" in q
