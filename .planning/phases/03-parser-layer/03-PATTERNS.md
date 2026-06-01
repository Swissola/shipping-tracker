# Phase 3: Parser Layer - Pattern Map

**Mapped:** 2026-06-01
**Files analyzed:** 6 (3 new, 3 modified)
**Analogs found:** 6 / 6

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `shipping_tracker/parsers/base.py` | model | transform | self (existing file — field edit only) | exact |
| `shipping_tracker/parsers/aliexpress.py` | service | transform | `shipping_tracker/parsers/base.py` (ABC contract) + `shipping_tracker/gmail/client.py` (logging pattern) | role-match |
| `shipping_tracker/main.py` | controller | request-response | self (existing file — dispatch loop added) | exact |
| `tests/fixtures/fake_aliexpress_email.py` | utility | — | `tests/fixtures/fake_gmail_message.py` | exact |
| `tests/test_aliexpress_parser.py` | test | — | `tests/test_smoke.py` | exact |
| `tests/test_smoke.py` | test | — | self (existing file — one assertion updated) | exact |

---

## Pattern Assignments

### `shipping_tracker/parsers/base.py` (model — field edit only)

**Analog:** self (current file at `shipping_tracker/parsers/base.py`)

**Current file, lines 1–49** — read in full above. The only change is D-04: `carrier: str` becomes `carrier: str | None = None` and the `extract()` return type changes from `TrackingInfo` to `TrackingInfo | None`.

**Existing import pattern** (lines 1–4):
```python
"""BaseParser abstract interface — all email parsers inherit from this class."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
```

**Add `from __future__ import annotations`** as the first import (matches `client.py` line 3) for forward-reference compatibility:
```python
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
```

**D-04 dataclass edit** — change lines 7–13 from:
```python
@dataclass
class TrackingInfo:
    """Structured tracking data extracted from a shipping email."""

    tracking_number: str
    carrier: str
```
to:
```python
@dataclass
class TrackingInfo:
    """Structured tracking data extracted from a shipping email."""

    tracking_number: str
    carrier: str | None = None
```

**D-05 abstract method signature edit** — change line 37 from:
```python
    def extract(self, email_body: str) -> TrackingInfo:
```
to:
```python
    def extract(self, email_body: str) -> TrackingInfo | None:
```
Update the docstring: remove the `Raises: ValueError` clause; add `Returns None if the email matches but contains no tracking number (e.g., pre-shipment order confirmation).`

---

### `shipping_tracker/parsers/aliexpress.py` (service, transform — NEW)

**Analog:** `shipping_tracker/parsers/base.py` (ABC contract to implement) + `shipping_tracker/gmail/client.py` (logging pattern to copy)

**Imports pattern** — model on `client.py` lines 1–23 (module docstring, `from __future__`, stdlib first, then project):
```python
"""AliExpressParser — sender-domain matching and tracking-number extraction."""

from __future__ import annotations

import logging
import re

from shipping_tracker.parsers.base import BaseParser, TrackingInfo
```

**Logger instantiation pattern** — copy `client.py` line 22 exactly:
```python
logger = logging.getLogger(__name__)
```

**Sender-domain constant** — parser-owned per D-01; typed as `tuple[str, ...]` for mypy `--strict`:
```python
# Parser-owned sender domains — single source of truth for can_parse() AND
# the Gmail from:() query (D-01). Add new domains here; no other file changes needed.
ALIEXPRESS_SENDER_DOMAINS: tuple[str, ...] = (
    "@mail.aliexpress.com",
    "@aliexpress.com",
)
```

**Module-level compiled regex constants** — compile once at import time, never inside `extract()`:
```python
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

_SHAPE_RE = re.compile(
    r"""
    \b
    (?:
        LP \d{10,16}
      | [A-Z]{2} \d{8,10} [A-Z]{2}
      | YT \d{14,18}
      | [A-Z]{2} \d{9,13} [A-Z]{2}
    )
    \b
    """,
    re.VERBOSE,
)
```

**ABC implementation** — `can_parse` and `extract` typed to satisfy mypy `--strict`:
```python
class AliExpressParser(BaseParser):
    """Parser for AliExpress shipping notification emails."""

    def can_parse(self, email_body: str, sender: str) -> bool:
        return any(domain in sender for domain in ALIEXPRESS_SENDER_DOMAINS)

    def extract(self, email_body: str) -> TrackingInfo | None:
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
```

**PII-safe logging rule** — when logging inside the parser, follow `client.py` line 238 exactly: log only `message_id`. Never log `email_body`, `sender`, `result.tracking_number`, or `result.carrier`. The `message_id` is not available inside `extract()` — the dispatch loop in `main.py` owns the logging for the no-tracking and no-match cases.

---

### `shipping_tracker/main.py` (controller, request-response — MODIFY)

**Analog:** self (existing `shipping_tracker/main.py`)

**Additional import** — add after existing imports (current line 8):
```python
from shipping_tracker.parsers.base import BaseParser, TrackingInfo
from shipping_tracker.parsers.aliexpress import AliExpressParser, ALIEXPRESS_SENDER_DOMAINS
```

**PARSERS registry** — module-level list, instantiated once (not inside the loop):
```python
PARSERS: list[BaseParser] = [
    AliExpressParser(),
]
```

**`_get_all_sender_domains()` helper** — replaces the `os.getenv("GMAIL_SENDER_LIST")` read; derives the sender list from parser constants (D-01):
```python
def _get_all_sender_domains() -> list[str]:
    """Return all sender domains declared by registered parsers (D-01).

    This is the single source of truth for the Gmail from:() query.
    Adding a new parser automatically extends the fetch scope.
    """
    return list(ALIEXPRESS_SENDER_DOMAINS)
```

**Updated `senders` derivation in `main()`** — replace current lines 28–30:
```python
# Before (current):
senders = [
    s.strip() for s in os.getenv("GMAIL_SENDER_LIST", "").split(",") if s.strip()
]

# After (Phase 3):
senders = _get_all_sender_domains()
```

**Dispatch loop** — insert after the `fetch_unread_shipping_emails` call (after current line 34), before the final `return 0`. Follow the `%`-style logging pattern from `client.py` lines 155–158 and 238:
```python
tracking_results: list[TrackingInfo] = []
for email in emails:
    matched = False
    for parser in PARSERS:
        if parser.can_parse(email.body, email.sender):
            matched = True
            result = parser.extract(email.body)
            if result is None:
                # Expected for pre-shipment "order confirmed" emails (D-05)
                logger.debug("parser.no_tracking id=%s", email.message_id)
            else:
                tracking_results.append(result)
            break  # first match wins (D-03)
    if not matched:
        logger.info("parser.no_match id=%s", email.message_id)

logger.warning("parser.dispatch.complete total=%d parsed=%d", len(emails), len(tracking_results))
```

Note: `logger.warning` is used for the summary line to match the existing `gmail.fetch.complete` log at line 39 (same level, same pattern — count-only, no PII).

---

### `tests/fixtures/fake_aliexpress_email.py` (utility — NEW)

**Analog:** `tests/fixtures/fake_gmail_message.py` (lines 1–29)

**Module docstring pattern** — copy the privacy docstring format from `fake_gmail_message.py` lines 1–5:
```python
"""Synthetic AliExpress email body fixtures for parser tests.

PRIVACY: All values are synthetic. No real tracking numbers, email addresses,
sender domains, or order references. See CLAUDE.md privacy constraints.
Tracking numbers use FAKE prefix; sender uses @fakealixmail.example.com domain.
"""
```

**FAKE-prefix convention** — all constants named `FAKE_*`, all data values prefixed with `FAKE` or using `.example.com` / `.example` domains. Copy the convention from `fake_gmail_message.py` lines 7–9:
```python
FAKE_GMAIL_MESSAGE: dict[str, object] = {
    "id": "FAKEMESSAGEID001",
    ...
    {"name": "From", "value": "shipping@fakestore.example.com"},
```

**Required fixture variants** (cover all test cases in RESEARCH.md Validation Architecture):

```python
# Fixture 1: label-anchored body — "Tracking number:" label (happy path, PARSE-02)
FAKE_ALIEXPRESS_SHIPPED_BODY = """\
Dear Customer,

Your order has been shipped.

Tracking number: FAKELP00FAKE00001
Carrier: FAKECARRIER

You can track your parcel at: https://faketrack.example.com

Thank you for shopping.
"""

# Fixture 2: "Logistics No." label variant
FAKE_ALIEXPRESS_LOGISTICS_BODY = """\
Hi,

Order dispatched.
Logistics No.: FAKEMM1234FAKE56CN
"""

# Fixture 3: "Tracking No." label variant
FAKE_ALIEXPRESS_TRACKING_NO_BODY = """\
Shipment notification

Tracking No. FAKEXX5678FAKE90CN
"""

# Fixture 4: pre-shipment — no tracking number (D-05 expected case)
FAKE_ALIEXPRESS_PRESHIPMENT_BODY = """\
Thank you for your order!

Your order is being processed. You will receive a shipping
notification once it has been dispatched.

Order reference: 500FAKE123456789
"""

# Fixture 5: shape-pattern fallback — no recognisable label, tracking number present
FAKE_ALIEXPRESS_NOLABEL_BODY = """\
Shipment update:
FAKEYT00000FAKE0001 is on its way to you.
"""

# Synthetic sender addresses (for can_parse tests) — no real domains
FAKE_ALIEXPRESS_SENDER = "shipping@fakemailaliexpress.example.com"
FAKE_OTHER_SENDER = "noreply@fakeotherstore.example.com"
```

Note: the `FAKE_ALIEXPRESS_SENDER` uses `.example.com` (RFC 2606 reserved, never routes) and does not contain `@mail.aliexpress.com` or `@aliexpress.com` — the `can_parse` tests must use strings that actually match the domain constant. Construct test inputs that contain the constant substring: e.g. `"shipping@mail.aliexpress.com"` only in test code, never as a fixture value here. The fixture provides the unmatched sender for the negative test.

---

### `tests/test_aliexpress_parser.py` (test — NEW)

**Analog:** `tests/test_smoke.py` (lines 1–52)

**Module docstring and imports pattern** — copy from `test_smoke.py` lines 1–11:
```python
"""Tests for AliExpressParser and the Phase 3 dispatch loop.

Verifies PARSE-01 / PARSE-02 / PARSE-03 acceptance criteria.
All test data is synthetic — no real tracking numbers or personal data.
"""

import pytest

from shipping_tracker.parsers.base import BaseParser, TrackingInfo
from shipping_tracker.parsers.aliexpress import AliExpressParser, ALIEXPRESS_SENDER_DOMAINS
from shipping_tracker.gmail.client import RawEmail
from tests.fixtures.fake_aliexpress_email import (
    FAKE_ALIEXPRESS_SHIPPED_BODY,
    FAKE_ALIEXPRESS_LOGISTICS_BODY,
    FAKE_ALIEXPRESS_TRACKING_NO_BODY,
    FAKE_ALIEXPRESS_PRESHIPMENT_BODY,
    FAKE_ALIEXPRESS_NOLABEL_BODY,
    FAKE_ALIEXPRESS_SENDER,
    FAKE_OTHER_SENDER,
)
```

**Test function style** — copy from `test_smoke.py` lines 27–37: plain functions (no class), `-> None` return type, docstring states the single invariant, one `assert` per test where possible:
```python
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


def test_extract_carrier_none() -> None:
    """extract() sets carrier=None when no courier is named (D-04)."""
    parser = AliExpressParser()
    result = parser.extract(FAKE_ALIEXPRESS_SHIPPED_BODY)
    assert result is not None
    assert result.carrier is None


def test_extract_returns_none_preshipment() -> None:
    """extract() returns None for a pre-shipment body with no tracking number (D-05)."""
    parser = AliExpressParser()
    assert parser.extract(FAKE_ALIEXPRESS_PRESHIPMENT_BODY) is None
```

**PII log check pattern** — use `caplog` fixture (pytest stdlib) to assert no sensitive fields are logged:
```python
def test_extract_does_not_log_pii(caplog: pytest.LogCaptureFixture) -> None:
    """Parser logs do not contain body, sender, or tracking number text."""
    parser = AliExpressParser()
    with caplog.at_level("DEBUG"):
        parser.extract(FAKE_ALIEXPRESS_SHIPPED_BODY)
    for record in caplog.records:
        assert "FAKELP00FAKE00001" not in record.message
        assert "Tracking number" not in record.message
```

**Dispatch integration tests** — use `RawEmail` directly (no mocking needed; `RawEmail` is a dataclass):
```python
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
```

---

### `tests/test_smoke.py` (test — MODIFY)

**Analog:** self (existing `tests/test_smoke.py`)

**One assertion to update** — `test_tracking_info_dataclass` (lines 33–37) currently passes `carrier="FAKECARRIER"` positionally. After D-04 the field has a default; the existing test still passes (positional construction works on dataclasses), but add one new assertion for the default:

```python
def test_tracking_info_dataclass() -> None:
    """TrackingInfo stores tracking_number and carrier as a dataclass."""
    ti = TrackingInfo(tracking_number="FAKE123", carrier="FAKECARRIER")
    assert ti.tracking_number == "FAKE123"
    assert ti.carrier == "FAKECARRIER"


def test_tracking_info_carrier_optional() -> None:
    """TrackingInfo.carrier defaults to None after D-04."""
    ti = TrackingInfo(tracking_number="FAKENUMBER")
    assert ti.carrier is None
```

The new function `test_tracking_info_carrier_optional` is added immediately after `test_tracking_info_dataclass`. No other changes to `test_smoke.py`.

---

## Shared Patterns

### PII-Safe Logging
**Source:** `shipping_tracker/gmail/client.py` lines 22, 155–158, 238
**Apply to:** `shipping_tracker/parsers/aliexpress.py`, `shipping_tracker/main.py` (dispatch loop)

```python
# Logger instantiation — always module-level, always __name__
logger = logging.getLogger(__name__)

# Log format: %-style, event.name key=value pairs, message_id only
logger.debug("parser.no_tracking id=%s", email.message_id)
logger.info("parser.no_match id=%s", email.message_id)
logger.warning("gmail.fetch.complete count=%d", len(results))

# NEVER log: email.body, email.sender, result.tracking_number, result.carrier
```

### `from __future__ import annotations`
**Source:** `shipping_tracker/gmail/client.py` line 3
**Apply to:** `shipping_tracker/parsers/base.py` (add), `shipping_tracker/parsers/aliexpress.py` (add)

```python
from __future__ import annotations
```

### FAKE-Prefix Synthetic Fixture Convention
**Source:** `tests/fixtures/fake_gmail_message.py` lines 1–9, `tests/conftest.py` lines 1–6
**Apply to:** `tests/fixtures/fake_aliexpress_email.py`, all new test assertions

Rules extracted from existing fixtures:
- Module docstring must contain the PRIVACY notice
- All constant names start with `FAKE_`
- All data string values use `FAKE`-prefixed tokens for IDs and numbers
- Domain names use `.example.com` (RFC 2606 reserved)
- No real tracking numbers, email addresses, or order references

### mypy `--strict` Typing
**Source:** `shipping_tracker/parsers/base.py` lines 23–24, `shipping_tracker/gmail/client.py` lines 26–36
**Apply to:** `shipping_tracker/parsers/aliexpress.py`, `shipping_tracker/parsers/base.py` (edit), `shipping_tracker/main.py` (additions)

```python
# Explicit return types on every function
def can_parse(self, email_body: str, sender: str) -> bool: ...
def extract(self, email_body: str) -> TrackingInfo | None: ...
def _get_all_sender_domains() -> list[str]: ...

# Typed module-level constants
ALIEXPRESS_SENDER_DOMAINS: tuple[str, ...] = (...)
PARSERS: list[BaseParser] = [...]
tracking_results: list[TrackingInfo] = []

# Use str | None, not Optional[str] (Python 3.11+ codebase style per RESEARCH.md)
carrier: str | None = None
```

### Dataclass Pattern
**Source:** `shipping_tracker/gmail/client.py` lines 25–39 (`RawEmail`), `shipping_tracker/parsers/base.py` lines 7–13 (`TrackingInfo`)
**Apply to:** `shipping_tracker/parsers/base.py` (D-04 edit)

```python
# Plain @dataclass for mutable output types (TrackingInfo)
@dataclass
class TrackingInfo:
    required_field: str
    optional_field: str | None = None  # required fields always first

# @dataclass(frozen=True) for immutable input types (RawEmail)
@dataclass(frozen=True)
class RawEmail:
    ...
```

---

## No Analog Found

All six files have a close codebase analog. No files require fallback to RESEARCH.md patterns exclusively.

---

## Metadata

**Analog search scope:** `shipping_tracker/` (all modules), `tests/` (all test and fixture files)
**Files read:** `base.py`, `main.py`, `client.py`, `conftest.py`, `fake_gmail_message.py`, `fixtures/__init__.py`, `test_smoke.py`, `logging_config.py`, `parsers/__init__.py`
**Pattern extraction date:** 2026-06-01
