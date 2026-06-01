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
    (?![A-Z0-9])          # CR-01: trailing boundary — an over-length token
                          # (>35 alnum chars) fails this assertion instead of
                          # being silently truncated to its first 35 chars.
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
      # Mixed letters-digits-letters (WR-01): length-gated to 16-35 alnum
      # chars with at least one letter AND one digit, so ordinary short
      # contiguous tokens (HTTP200OK, ISO9001CERT, ABC123XYZ) no longer
      # false-match while real long AliExpress/Cainiao-shaped tokens still do.
      | (?=[A-Z0-9]{16,35}\b)          # length gate
        (?=[A-Z0-9]*[A-Z])            # at least one letter
        (?=[A-Z0-9]*\d)               # at least one digit
        [A-Z]{2,} \d{3,} [A-Z]{2,} [A-Z0-9]*
    )
    \b
    """,
    re.VERBOSE,
)


class AliExpressParser(BaseParser):
    """Parser for AliExpress shipping notification emails."""

    # CR-02: expose this parser's sender domains through the BaseParser
    # contract so main._get_all_sender_domains() can aggregate across parsers
    # (D-01 drop-in: a new parser is a single self-contained file).
    sender_domains = ALIEXPRESS_SENDER_DOMAINS

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
            # WR-02: label matching is case-insensitive, but the captured
            # tracking number is normalised to upper-case so the same physical
            # number arriving in different casings dedupes to one key in Phase 4.
            return TrackingInfo(tracking_number=m.group(1).upper())

        # Stage 2: shape-pattern fallback (D-02)
        m2 = _SHAPE_RE.search(email_body)
        if m2:
            # WR-02: canonicalise to upper-case (see Stage 1).
            return TrackingInfo(tracking_number=m2.group(0).upper())

        # No tracking number found — expected for pre-shipment emails (D-05)
        return None
