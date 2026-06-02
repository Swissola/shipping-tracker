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


# --- CR-01: over-length tracking numbers must not be silently truncated ------


def test_extract_overlength_token_not_truncated() -> None:
    """CR-01: a >35-char label token yields no truncated TrackingInfo.

    The 35-char capture cap used to silently truncate an over-length token,
    registering a corrupted number. It must now either match the full token or
    not match at all — never a partial value.
    """
    parser = AliExpressParser()
    # 38-char synthetic token (all FAKE-prefixed, no real carrier number).
    over_length = "FAKELP" + "0" * 32  # 38 chars
    body = f"Tracking number: {over_length} ships soon"
    result = parser.extract(body)
    if result is not None:
        # If anything matched, it must be the full token, never a truncation.
        assert result.tracking_number == over_length.upper()
        assert len(result.tracking_number) != 35
    # Critically: the first-35-char truncation must NOT appear.
    truncated = over_length[:35]
    assert result is None or result.tracking_number != truncated


# --- WR-01: shape fallback must not false-match ordinary contiguous tokens ---


@pytest.mark.parametrize("token", ["HTTP200OK", "ISO9001CERT", "ABC123XYZ"])
def test_extract_shape_rejects_ordinary_tokens(token: str) -> None:
    """WR-01: SKU / cert / protocol tokens are not extracted as tracking numbers."""
    parser = AliExpressParser()
    body = f"Reference {token} in our catalogue footer."
    assert parser.extract(body) is None


def test_extract_shape_rejects_numeric_order_ref() -> None:
    """WR-01/Pitfall 2: a purely-numeric order reference is rejected."""
    parser = AliExpressParser()
    assert parser.extract("Order reference: 500FAKE123456789") is None


def test_extract_shape_still_matches_real_shape() -> None:
    """WR-01: a genuine AliExpress-shaped token still extracts via shape fallback."""
    parser = AliExpressParser()
    result = parser.extract(FAKE_ALIEXPRESS_NOLABEL_BODY)
    assert result is not None
    assert result.tracking_number == "FAKEYT00000FAKE0001"


# --- WR-02: captured tracking numbers are normalised to upper-case -----------


def test_extract_normalises_lowercase_to_upper() -> None:
    """WR-02: a lowercase label token is stored upper-cased (dedup safety)."""
    parser = AliExpressParser()
    body = "Tracking number: fakelp00fake00001 is on its way"
    result = parser.extract(body)
    assert result is not None
    assert result.tracking_number == "FAKELP00FAKE00001"


# --- CR-02: sender domains aggregate across all registered parsers -----------


def test_get_all_sender_domains_aggregates_across_parsers() -> None:
    """CR-02/D-01: appending a parser surfaces its domain in the Gmail query."""
    from shipping_tracker import main as main_mod

    class SecondParser(BaseParser):
        sender_domains = ("@fakesecond.example.com",)

        def can_parse(self, email_body: str, sender: str) -> bool:
            return any(d in sender for d in self.sender_domains)

        def extract(self, email_body: str) -> TrackingInfo | None:
            return None

    original = list(main_mod.PARSERS)
    try:
        main_mod.PARSERS.append(SecondParser())
        domains = main_mod._get_all_sender_domains()
        # The AliExpress domains are still present...
        for d in ALIEXPRESS_SENDER_DOMAINS:
            assert d in domains
        # ...and the newly appended parser's domain now appears too.
        assert "@fakesecond.example.com" in domains
        # De-duplicated, stable order.
        assert len(domains) == len(set(domains))
    finally:
        main_mod.PARSERS[:] = original


# --- WR-04: one raising parser must not crash the whole dispatch batch -------


def test_dispatch_isolates_raising_parser() -> None:
    """WR-04/D-05: a parser raising on one email does not abort the batch."""
    from shipping_tracker import main as main_mod

    class ExplodingParser(BaseParser):
        sender_domains = ("@fakeboom.example.com",)

        def can_parse(self, email_body: str, sender: str) -> bool:
            return any(d in sender for d in self.sender_domains)

        def extract(self, email_body: str) -> TrackingInfo | None:
            raise ValueError("synthetic parser failure")

    emails = [
        RawEmail(
            message_id="FAKEMSGID_BAD",
            sender="orders@fakeboom.example.com",
            body="boom",
        ),
        RawEmail(
            message_id="FAKEMSGID_GOOD",
            sender="shipping@mail.aliexpress.com",
            body=FAKE_ALIEXPRESS_SHIPPED_BODY,
        ),
    ]

    original = list(main_mod.PARSERS)
    try:
        # Prepend the exploding parser so the bad email is claimed by it.
        main_mod.PARSERS.insert(0, ExplodingParser())

        # Re-run the dispatch logic the way main() does, asserting no raise.
        tracking_results: list[TrackingInfo] = []
        for email in emails:
            try:
                for parser in main_mod.PARSERS:
                    if parser.can_parse(email.body, email.sender):
                        result = parser.extract(email.body)
                        if result is not None:
                            tracking_results.append(result)
                        break
            except Exception:
                continue

        # The good email was still processed despite the bad one raising.
        assert len(tracking_results) == 1
        assert tracking_results[0].tracking_number == "FAKELP00FAKE00001"
    finally:
        main_mod.PARSERS[:] = original


def test_main_dispatch_loop_logs_pii_safely_on_error(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WR-04/LOG-02: the real main() dispatch never leaks PII when a parser raises.

    Drives the actual ``main()`` (not a re-implemented loop) with a parser whose
    exception message *itself* embeds the email body and tracking number — the
    exact leak vector ``logger.exception`` would render via the log config's
    ``format_exc_info`` processor. Asserts the error record carries only the
    message_id and the exception *type*, attaches no traceback (``exc_info`` is
    None), and that no PII appears in any record.
    """
    from shipping_tracker import main as main_mod

    class ExplodingParser(BaseParser):
        sender_domains = ("@fakeboom.example.com",)

        def can_parse(self, email_body: str, sender: str) -> bool:
            return True

        def extract(self, email_body: str) -> TrackingInfo | None:
            # PII deliberately placed in the exception message — a careless
            # third-party parser could do this; the dispatch loop must not
            # surface it (no exc_info, message_id + type only).
            raise ValueError(f"parse failed on {email_body}")

    email = RawEmail(
        message_id="FAKEMSGID_PII",
        sender="orders@fakeboom.example.com",
        body="SECRETBODY FAKELP00FAKE00001",
    )

    # No-op logging setup so caplog captures cleanly and no log file is written.
    # Use in-memory SQLite so no side-effect DB file is created during the test.
    # Phase 5 D-05: a (synthetic) TRACKINGMORE_API_KEY must be present or main()
    # fail-fasts with exit 1 before ever reaching the dispatch loop under test.
    monkeypatch.setenv("TRACKINGMORE_API_KEY", "FAKE_KEY")
    monkeypatch.setenv("DATABASE_PATH", ":memory:")
    monkeypatch.setattr(main_mod, "configure_logging", lambda: None)
    monkeypatch.setattr(
        main_mod, "fetch_unread_shipping_emails", lambda senders, window: [email]
    )

    original = list(main_mod.PARSERS)
    try:
        main_mod.PARSERS[:] = [ExplodingParser()]
        with caplog.at_level("DEBUG"):
            assert main_mod.main() == 0  # one bad email never aborts the run

        # Phase 4: log key renamed from parser.dispatch.error to pipeline.error (WR-04)
        error_records = [
            r for r in caplog.records if "pipeline.error" in r.getMessage()
        ]
        assert error_records, "expected a dispatch-error log record"
        for record in caplog.records:
            rendered = record.getMessage()
            assert "SECRETBODY" not in rendered
            assert "FAKELP00FAKE00001" not in rendered
            assert record.exc_info is None  # no traceback attached → nothing to render
        err = error_records[0]
        assert "FAKEMSGID_PII" in err.getMessage()
        assert "ValueError" in err.getMessage()  # exception type is safe to log
    finally:
        main_mod.PARSERS[:] = original
