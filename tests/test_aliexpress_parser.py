"""Tests for AliExpressParser and the Phase 3 dispatch loop.

Verifies PARSE-01 / PARSE-02 / PARSE-03 acceptance criteria.
All test data is synthetic — no real tracking numbers or personal data.
"""

import pytest

from shipping_tracker.gmail.client import RawEmail
from shipping_tracker.parsers.aliexpress import (
    ALIEXPRESS_SENDER_DOMAINS,
    AliExpressParser,
)
from shipping_tracker.parsers.base import BaseParser, TrackingInfo
from tests.fixtures.fake_aliexpress_email import (
    FAKE_ALIEXPRESS_NOLABEL_BODY,
    FAKE_ALIEXPRESS_PRESHIPMENT_BODY,
    FAKE_ALIEXPRESS_SHIPPED_BODY,
    FAKE_OTHER_SENDER,
)


def test_tracking_info_carrier_optional() -> None:
    """TrackingInfo.carrier defaults to None after D-04."""
    ti = TrackingInfo(tracking_number="FAKENUMBER")
    assert ti.carrier is None


def test_can_parse_known_domains() -> None:
    """can_parse() returns True for each declared AliExpress sender domain."""
    parser = AliExpressParser()
    for domain in ALIEXPRESS_SENDER_DOMAINS:
        assert parser.can_parse("", f"shipping{domain}")


def test_can_parse_rejects_other_senders() -> None:
    """can_parse() returns False for a non-AliExpress sender."""
    parser = AliExpressParser()
    assert parser.can_parse("", FAKE_OTHER_SENDER) is False


def test_extract_label_anchored() -> None:
    """extract() returns TrackingInfo for a label-anchored body."""
    parser = AliExpressParser()
    result = parser.extract(FAKE_ALIEXPRESS_SHIPPED_BODY)
    assert result is not None
    assert result.tracking_number == "FAKELP00FAKE00001"


def test_extract_shape_fallback() -> None:
    """extract() returns TrackingInfo via shape-pattern fallback (no label present)."""
    parser = AliExpressParser()
    result = parser.extract(FAKE_ALIEXPRESS_NOLABEL_BODY)
    assert result is not None
    assert result.tracking_number == "FAKEYT00000FAKE0001"


def test_extract_returns_none_preshipment() -> None:
    """extract() returns None for a pre-shipment body with no tracking number (D-05)."""
    parser = AliExpressParser()
    assert parser.extract(FAKE_ALIEXPRESS_PRESHIPMENT_BODY) is None


def test_extract_carrier_none() -> None:
    """extract() sets carrier=None when no courier is named (D-04)."""
    parser = AliExpressParser()
    result = parser.extract(FAKE_ALIEXPRESS_SHIPPED_BODY)
    assert result is not None
    assert result.carrier is None


def test_extract_does_not_log_pii(caplog: pytest.LogCaptureFixture) -> None:
    """Parser logs do not contain body, sender, or tracking number text."""
    parser = AliExpressParser()
    with caplog.at_level("DEBUG"):
        parser.extract(FAKE_ALIEXPRESS_SHIPPED_BODY)
    for record in caplog.records:
        assert "FAKELP00FAKE00001" not in record.message
        assert "Tracking number" not in record.message


def test_dispatch_matched_email() -> None:
    """Dispatch loop yields TrackingInfo for a matched, shipped email."""
    from shipping_tracker.main import PARSERS

    email = RawEmail(
        message_id="FAKEMSGID001",
        sender="shipping@mail.aliexpress.com",
        body=FAKE_ALIEXPRESS_SHIPPED_BODY,
    )
    results = []
    for parser in PARSERS:
        if parser.can_parse(email.body, email.sender):
            result = parser.extract(email.body)
            if result is not None:
                results.append(result)
            break
    assert len(results) == 1
    assert results[0].tracking_number == "FAKELP00FAKE00001"


def test_dispatch_no_match_skips() -> None:
    """Dispatch loop skips emails that no parser claims."""
    from shipping_tracker.main import PARSERS

    email = RawEmail(
        message_id="FAKEMSGID002",
        sender=FAKE_OTHER_SENDER,
        body=FAKE_ALIEXPRESS_SHIPPED_BODY,
    )
    matched = False
    for parser in PARSERS:
        if parser.can_parse(email.body, email.sender):
            matched = True
            break
    assert matched is False


def test_dispatch_preshipment_skips() -> None:
    """Dispatch loop yields no TrackingInfo for a matched pre-shipment email (D-05)."""
    from shipping_tracker.main import PARSERS

    email = RawEmail(
        message_id="FAKEMSGID003",
        sender="shipping@mail.aliexpress.com",
        body=FAKE_ALIEXPRESS_PRESHIPMENT_BODY,
    )
    results = []
    for parser in PARSERS:
        if parser.can_parse(email.body, email.sender):
            result = parser.extract(email.body)
            if result is not None:
                results.append(result)
            break
    assert len(results) == 0


def test_registry_drop_in() -> None:
    """A second parser appended to PARSERS is discoverable via can_parse."""
    from shipping_tracker.main import PARSERS

    class FakeParser(BaseParser):
        def can_parse(self, email_body: str, sender: str) -> bool:
            return "@fakestore.example.com" in sender

        def extract(self, email_body: str) -> TrackingInfo | None:
            return TrackingInfo(tracking_number="FAKEREGISTRY001")

    extended = list(PARSERS) + [FakeParser()]
    email = RawEmail(
        message_id="FAKEMSGID004",
        sender="orders@fakestore.example.com",
        body="",
    )
    matched_parser = None
    for parser in extended:
        if parser.can_parse(email.body, email.sender):
            matched_parser = parser
            break
    assert matched_parser is not None
    assert isinstance(matched_parser, FakeParser)
