"""Gmail query builder — constructs server-side Gmail search query strings."""

from __future__ import annotations


def build_query(senders: list[str], window_days: int) -> str:
    """Build a Gmail search query string for unread shipping emails.

    Args:
        senders: List of sender addresses or domains, e.g. ["@aliexpress.com"]
        window_days: How many days back to look (e.g. 30 -> newer_than:30d)

    Returns:
        Query string like: is:unread from:(sender1 OR sender2) newer_than:30d
        If senders is empty, returns an unread-only query without a from clause.

    Note: Gmail OR syntax requires no spaces around OR when inside parentheses.
    """
    if senders:
        from_clause = " OR ".join(senders)
        return f"is:unread from:({from_clause}) newer_than:{window_days}d"
    return f"is:unread newer_than:{window_days}d"
