"""AliExpressParser — sender-domain matching and tracking-number extraction."""

from __future__ import annotations

import logging
import re

from shipping_tracker.parsers.base import BaseParser, TrackingInfo

logger = logging.getLogger(__name__)

# Parser-owned sender domains — single source of truth for can_parse() AND
# the Gmail from:() query (D-01). Add new domains here; no other file changes needed.
ALIEXPRESS_SENDER_DOMAINS: tuple[str, ...] = (
    "@mail.aliexpress.com",
    "@aliexpress.com",
)

# Module-level compiled regexes — compiled once at import time, never inside extract().
# ReDoS-safe: all quantifiers are bounded; no nested unbounded quantifiers.

# Primary path (D-02): label-anchored extraction.
# Matches known AliExpress label prefixes followed by an alphanumeric token.
_LABEL_RE = re.compile(
    r"""
    (?:
        Tracking \s+ (?:number|No\.?)
      | Logistics \s+ (?:No\.? | tracking \s+ number)
      | Waybill   \s+ (?:number|No\.?)
      | Parcel    \s+ (?:number|No\.?)
    )
    \s* [:\s] \s*
    ([A-Z0-9]{8,35})
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Fallback path (D-02): shape-pattern matching.
# Every alternative requires at least one mandatory letter component so that
# purely-numeric order references (Pitfall 2 / T-03-05) cannot false-match.
_SHAPE_RE = re.compile(
    r"""
    \b
    (?:
        LP [A-Z0-9]{10,16}              # Cainiao LP prefix
      | [A-Z]{2} \d{8,10} [A-Z]{2}     # Universal postal: 2L+8-10D+2L
      | YT \d{14,18}                    # Yun Te domestic
      | [A-Z]{2} \d{9,13} [A-Z]{2}     # Broader postal: 2L+9-13D+2L
      | [A-Z]{2,} \d{3,} [A-Z]{2,} [A-Z0-9]*  # Mixed: letters-digits-letters
    )
    \b
    """,
    re.VERBOSE,
)


class AliExpressParser(BaseParser):
    """Parser for AliExpress shipping notification emails."""

    def can_parse(self, email_body: str, sender: str) -> bool:
        """Return True if the sender matches a declared AliExpress domain (D-01)."""
        return any(domain in sender for domain in ALIEXPRESS_SENDER_DOMAINS)

    def extract(self, email_body: str) -> TrackingInfo | None:
        """Extract tracking number from an AliExpress email body.

        Stage 1 (primary): label-anchored search using known AliExpress label strings.
        Stage 2 (fallback): shape-pattern search requiring mandatory letter component.
        Returns None for pre-shipment bodies with no tracking number (D-05).
        Carrier is not extracted in v1 — left as None (D-04).
        """
        # Stage 1: label-anchored (primary path, D-02)
        m = _LABEL_RE.search(email_body)
        if m:
            return TrackingInfo(tracking_number=m.group(1))

        # Stage 2: shape-pattern fallback (D-02)
        m2 = _SHAPE_RE.search(email_body)
        if m2:
            return TrackingInfo(tracking_number=m2.group(0))

        # No tracking number found — expected for pre-shipment emails (D-05)
        return None
