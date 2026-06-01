"""Parser sub-package — pluggable email parser implementations."""

from shipping_tracker.parsers.aliexpress import (
    ALIEXPRESS_SENDER_DOMAINS,
    AliExpressParser,
)
from shipping_tracker.parsers.base import BaseParser, TrackingInfo

__all__ = [
    "AliExpressParser",
    "ALIEXPRESS_SENDER_DOMAINS",
    "BaseParser",
    "TrackingInfo",
]
