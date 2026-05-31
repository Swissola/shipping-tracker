"""Gmail sub-package — OAuth2 auth, query construction, and message fetch."""

from shipping_tracker.gmail.client import (
    RawEmail,
    build_service,
    fetch_unread_shipping_emails,
)

__all__ = [
    "RawEmail",
    "build_service",
    "fetch_unread_shipping_emails",
]
