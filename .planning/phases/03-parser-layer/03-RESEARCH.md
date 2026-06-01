# Phase 3: Parser Layer - Research

**Researched:** 2026-06-01
**Domain:** Python pluggable email parser pattern, regex extraction, AliExpress shipping email structure
**Confidence:** MEDIUM — core Python patterns are HIGH; AliExpress email label strings and sender domains are MEDIUM (cross-referenced multiple sources but not personally verified against a live inbox)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** `AliExpressParser.can_parse()` matches on sender domain. Each parser declares its own AliExpress sender domain(s) as a parser-owned constant. This constant is also the source for Phase 2's Gmail `from:()` query. Adding a new seller is a single self-contained parser file with no central sender-list edit. Rejected: body-marker-only matching and sender+body-marker matching.
- **D-02:** Extraction is label-anchored with a constrained shape-pattern fallback. Primary path: locate a known label ("Tracking number:", "Logistics No.", "Tracking No.", and any AliExpress variants the researcher confirms) and capture the adjacent token. Fallback: a constrained shape pattern when no recognized label is present.
- **D-03:** First match wins for v1 when an email contains more than one candidate tracking number. `extract()` keeps its single-`TrackingInfo` return contract. Extra candidates that are seen but not processed are logged (message_id only, PII-safe).
- **D-04:** Change `TrackingInfo.carrier` from a required `str` to `str | None` (default `None`). The parser populates it only when the email clearly names a courier; otherwise `None`. TrackingMore auto-detects the courier, so carrier is a best-effort hint that must never block registration. Rejected: empty-string sentinel and dropping carrier entirely.
- **D-05:** When a parser claims an email (sender matches) but no tracking number can be extracted — routine for pre-shipment "order confirmed" emails — this is treated as an expected, non-fatal outcome. Log at debug level (message_id only), skip the email, and continue. Debug (not warning) avoids warning-spam on every routine order-confirmation email. Distinct from PARSE-03's "no parser matched at all" skip.

### Claude's Discretion

- **Mechanism for the no-tracking skip (D-05):** `extract()` returning `None` vs. raising `ValueError` caught by the dispatch loop — planner's choice, as long as the run always continues and logging stays at debug with message_id only. Current `base.py` docstring says `extract()` raises `ValueError` on match-but-fail; the planner may revise this contract.
- **Integration of per-parser sender list with Phase 2 (D-01):** how parser-owned sender domains feed Phase 2's existing `GMAIL_SENDER_LIST` env path — may touch Phase 2 code. Planner to decide the cleanest wiring.
- **Parser registry location:** `main.py` list vs. a dedicated registry module — planner's choice.
- **Exact label strings and fallback shape pattern:** researcher to verify against real AliExpress shipping-email formats (synthetic fixtures must mirror the real structure without real data).

### Deferred Ideas (OUT OF SCOPE)

- **Multi-parcel-per-email splitting:** registering every tracking number when one email lists several parcels (would change `extract()` to return `list[TrackingInfo]` and ripple into Phase 4/5). Deferred from v1 per D-03.
- Carried from Phase 2: auto-discovering shipping senders; marking emails read / applying Gmail labels.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PARSE-01 | `BaseParser` abstract base class defined with `can_parse(email) -> bool` and `extract(email) -> TrackingInfo` interface | Already scaffolded in Phase 1 at `shipping_tracker/parsers/base.py`. D-04 requires editing `carrier` to `str \| None = None`. Interface is already ABC-compliant and mypy-strict. |
| PARSE-02 | `AliExpressParser` implements `BaseParser` and correctly extracts the tracking number from AliExpress shipping notification emails; carrier is best-effort metadata only | Requires new file `shipping_tracker/parsers/aliexpress.py`. Label-anchored regex with shape-pattern fallback researched below. Sender domain constant researched below. |
| PARSE-03 | Parsers registered in a list; first match wins; unknown emails logged and skipped without error | Requires dispatch loop in `main.py` (or a registry module). Pattern is a simple `for parser in PARSERS` loop. No-match logging at info/warning with count only. |
</phase_requirements>

---

## Summary

Phase 3 is narrowly scoped: edit one dataclass field, create one parser implementation file, add a dispatch loop to the pipeline, and cover everything with synthetic-fixture tests. The Python patterns involved — ABC, dataclasses, `re` module, a list-based registry — are all stdlib and already in use elsewhere in the project. No new packages are required.

The two genuine research questions are (1) the real AliExpress email label strings and sender domains, and (2) a constrained fallback shape pattern that reliably distinguishes a tracking number from an order reference. Both are resolved in the sections below with confidence levels noted per claim.

The primary recommendation for the no-tracking skip (D-05 discretion item) is `extract()` returning `Optional[TrackingInfo]` rather than raising `ValueError`, because it makes the happy and no-tracking paths type-safe and forces the dispatch loop to handle both cases explicitly at call sites without exception machinery.

**Primary recommendation:** Implement `AliExpressParser` as a self-contained module under `shipping_tracker/parsers/aliexpress.py` with sender domain constant, label-anchored regex, constrained fallback, and `extract()` returning `TrackingInfo | None`. Wire the dispatch loop directly in `main.py` as a module-level list — a separate registry module is warranted only when there are multiple parsers.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Parser interface contract (PARSE-01) | Parser layer (Python module) | — | BaseParser ABC is already at `shipping_tracker/parsers/base.py`; stays there |
| Sender-domain matching (`can_parse`) | Parser layer (AliExpressParser) | Pipeline/main.py dispatch loop | The parser owns its sender constants; main.py iterates the registry |
| Tracking-number extraction (`extract`) | Parser layer (AliExpressParser) | — | All regex logic lives in the parser, not the pipeline |
| Parser registry and dispatch | Pipeline (`main.py`) | — | Registry is a module-level list; dispatch loop is a for-loop in `main()` |
| No-match / no-tracking skip logic | Pipeline (`main.py`) | — | The dispatch loop observes None / empty registry result and logs at debug |
| `TrackingInfo` dataclass (D-04 edit) | Parser layer (`base.py`) | Consumed by Phase 4 and 5 | Single source of truth for the output shape |
| Synthetic test fixtures | `tests/fixtures/` | `tests/conftest.py` | Established pattern from Phase 2; extend with AliExpress email body fixtures |

---

## Standard Stack

### Core (no new packages needed)

Phase 3 requires zero new runtime dependencies. All tools are stdlib or already installed.

| Library | Version | Purpose | Source |
|---------|---------|---------|--------|
| `re` | stdlib | Regex-based label search and shape-pattern fallback | [VERIFIED: Python 3.11 stdlib] |
| `abc` | stdlib | `BaseParser` ABC already inherits from it | [VERIFIED: Python 3.11 stdlib] |
| `dataclasses` | stdlib | `TrackingInfo` dataclass already uses it | [VERIFIED: Python 3.11 stdlib] |
| `pytest` | >=9.0 (installed) | Test coverage for PARSE-01/02/03 | [VERIFIED: pyproject.toml] |
| `mypy` | >=2.1 (installed) | `--strict` type-checking; `carrier: str \| None = None` must pass | [VERIFIED: pyproject.toml] |

### Supporting (already installed, relevant to integration)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `logging` | stdlib | PII-safe debug logs in parser and dispatch | Every log call; never log body, sender, or tracking number |
| `python-dotenv` | >=1.2 | `GMAIL_SENDER_LIST` env var feeds from parser constants | In `main.py` on startup |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `re` with label-anchored pattern | `pyparsing`, `parsimonious` | Heavy dependency for a structurally simple extraction; `re` is sufficient and already available |
| `re` stdlib | `regex` (PyPI) | More Unicode features; unnecessary for ASCII tracking-number labels |
| List-based registry in `main.py` | Plugin framework (`pluggy`) | Plugin framework adds complexity with no benefit for v1 single-parser use |

**Installation:** No new packages to install. This phase is pure stdlib + existing dev dependencies.

---

## Package Legitimacy Audit

> No new packages are introduced in Phase 3. The phase relies entirely on Python stdlib (`re`, `abc`, `dataclasses`) and existing project dependencies. This section is intentionally empty.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
list[RawEmail]  (from Phase 2 Gmail fetch)
      |
      v
  [ Dispatch loop in main() ]
      |
      |-- for each RawEmail:
      |       |
      |       v
      |   PARSERS list (module-level, defined in main.py)
      |       |
      |       |-- AliExpressParser.can_parse(email.body, email.sender)
      |       |       |
      |       |       YES --> AliExpressParser.extract(email.body)
      |       |                   |
      |       |                   |-- Returns TrackingInfo  --> yield/collect for Phase 4
      |       |                   |
      |       |                   \-- Returns None (no tracking found)
      |       |                           --> log debug (message_id only), skip
      |       |
      |       \-- NO PARSER MATCHED
      |               --> log info (message_id only, count), skip
      |
      v
  list[TrackingInfo]  (consumed by Phase 4 dedup)
```

### Recommended Project Structure

```
shipping_tracker/
├── parsers/
│   ├── __init__.py          # re-export BaseParser, TrackingInfo, AliExpressParser
│   ├── base.py              # BaseParser ABC + TrackingInfo dataclass (D-04 edit)
│   └── aliexpress.py        # AliExpressParser (new file)
├── gmail/
│   └── ...                  # unchanged
├── main.py                  # add PARSERS list + dispatch loop
└── ...
tests/
├── conftest.py              # extend with AliExpress body fixtures
├── fixtures/
│   ├── fake_aliexpress_email.py   # new: synthetic AliExpress email body variants
│   └── ...
└── test_aliexpress_parser.py      # new: PARSE-01/02/03 coverage
```

### Pattern 1: Dataclass with Optional Field (D-04)

**What:** Change `carrier` from required `str` to `str | None` with a default of `None`.
**When to use:** Any field that is legitimately absent; `None` is a first-class value, not a sentinel.
**mypy --strict compatibility:** The pattern `field: str | None = None` is valid and fully supported by mypy ≥ 2.x under `--strict`. Using `dataclasses.field(default=None)` is also valid but unnecessary when the default is a simple scalar.

```python
# Source: Python 3.11 stdlib dataclasses + mypy --strict verified pattern [VERIFIED: Python 3.11 stdlib]
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class TrackingInfo:
    """Structured tracking data extracted from a shipping email."""
    tracking_number: str
    carrier: str | None = None
```

Note: the `from __future__ import annotations` import (already present in some project files) makes `str | None` syntax work on Python 3.9 and earlier, but is not strictly required on 3.11+. Include it for consistency with the rest of the codebase.

### Pattern 2: Parser ABC with Sender-Domain Constant

**What:** Each parser owns its sender domains as a module-level constant. `can_parse()` checks the sender against those domains. The same constant feeds Phase 2's query builder.
**When to use:** Every parser implementation file.

```python
# Source: established project pattern in base.py + D-01 decision [VERIFIED: codebase]
from __future__ import annotations
from shipping_tracker.parsers.base import BaseParser, TrackingInfo

# Parser-owned sender domains — also the source for GMAIL_SENDER_LIST (D-01)
ALIEXPRESS_SENDER_DOMAINS: tuple[str, ...] = (
    "@mail.aliexpress.com",
    "@aliexpress.com",
)

class AliExpressParser(BaseParser):
    def can_parse(self, email_body: str, sender: str) -> bool:
        return any(domain in sender for domain in ALIEXPRESS_SENDER_DOMAINS)

    def extract(self, email_body: str) -> TrackingInfo | None:
        ...
```

### Pattern 3: Label-Anchored Extraction with Shape-Pattern Fallback (D-02)

**What:** Two-stage regex approach. Stage 1 looks for a known label immediately before the tracking token. Stage 2 (fallback) matches the constrained shape directly.
**When to use:** In `AliExpressParser.extract()`.

```python
# Source: D-02 decision + AliExpress tracking format research [ASSUMED for label strings; VERIFIED shape for UPU S10 format]
import re

# Stage 1: label-anchored patterns (case-insensitive to handle formatting variants)
_LABEL_PATTERN = re.compile(
    r"""
    (?:
        Tracking\s+(?:number|No\.?)  # "Tracking number:", "Tracking No.", "Tracking No"
      | Logistics\s+(?:No\.?|tracking\s+number)  # "Logistics No.", "Logistics tracking number"
      | Waybill\s+(?:number|No\.?)   # "Waybill number:", "Waybill No."
      | Parcel\s+(?:number|No\.?)    # "Parcel number:", "Parcel No."
    )
    \s*[:\s]\s*
    ([A-Z0-9]{8,35})                 # capture: constrained shape token
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Stage 2: fallback shape pattern (only when no label found)
# Matches the main AliExpress/cross-border tracking number families:
#   UPU S10:    2 uppercase + 8 digits + check digit + 2 uppercase  (13 chars, e.g. RV123456789CN)
#   LP prefix:  LP + 10-16 digits                                    (e.g. LP00123456789012)
#   YT prefix:  YT + 14-18 digits                                    (e.g. YT12345678901234)
#   ZA...HK/CN: ZA + 9 digits + 2 uppercase country code            (e.g. ZA123456789HK)
# Explicitly does NOT match purely numeric sequences (avoids order-number collisions)
_SHAPE_FALLBACK = re.compile(
    r"""
    \b
    (?:
        LP\d{10,16}          # Cainiao LP internal codes
      | [A-Z]{2}\d{8,10}[A-Z]{2}  # UPU S10 international postal (e.g. RV123456789CN)
      | YT\d{14,18}          # YunTu/YunExpress
      | [A-Z]{2}\d{9,13}[A-Z]{2}  # Wider catch for country-code-suffixed formats
    )
    \b
    """,
    re.VERBOSE,
)
```

### Pattern 4: Dispatch Loop in main.py

**What:** A module-level list of parser instances. The loop tries each parser in order; first `can_parse()` match wins.
**When to use:** Between the Gmail fetch and the (future) Phase 4 dedup call.

```python
# Source: PARSE-03 requirement + D-01/D-05 decisions [VERIFIED: codebase pattern]
from shipping_tracker.parsers.aliexpress import AliExpressParser, ALIEXPRESS_SENDER_DOMAINS

PARSERS: list[BaseParser] = [
    AliExpressParser(),
]

def _get_all_sender_domains() -> list[str]:
    """Derive GMAIL_SENDER_LIST from parser-owned domain constants (D-01)."""
    return list(ALIEXPRESS_SENDER_DOMAINS)
    # Phase 2 sellers: extend this list from each parser's constant

# In main():
tracking_results: list[TrackingInfo] = []
for email in emails:
    matched = False
    for parser in PARSERS:
        if parser.can_parse(email.body, email.sender):
            matched = True
            result = parser.extract(email.body)
            if result is None:
                logger.debug("parser.no_tracking id=%s", email.message_id)
            else:
                tracking_results.append(result)
            break  # first match wins (D-03)
    if not matched:
        logger.info("parser.no_match id=%s", email.message_id)
```

### Anti-Patterns to Avoid

- **Logging the tracking number:** The tracking number is not technically PII under GDPR, but CLAUDE.md says no real tracking numbers in source or logs. Log `message_id` only for traceability. [VERIFIED: CLAUDE.md]
- **Logging `email.sender` or `email.body`:** Violates LOG-02. Established pattern from Phase 2.
- **Using bare `.+` in the fallback shape pattern:** Matches order reference numbers (15-17 digit numeric strings). Always anchor the fallback to alphanumeric patterns with mandatory letter components.
- **Raising `ValueError` from `extract()` for pre-shipment emails:** D-05 is explicit that the run must not crash on routine "order confirmed" emails. Returning `None` is cleaner than exception flow for an expected, frequent outcome.
- **Storing `GMAIL_SENDER_LIST` separately from parser constants:** D-01 locks that the parser is the single source of truth for its sender domains. A separate config list creates a maintenance divergence risk.
- **Instantiating parsers inside the loop:** Parser instances are stateless; instantiate once at module level and reuse.
- **Using `Optional[str]` vs `str | None`:** The project targets Python 3.11+, and the codebase already uses `str | None` style (see `client.py`). Use `str | None` for consistency. [VERIFIED: codebase]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Regex compilation | Re-compile pattern on every `extract()` call | Module-level `re.compile()` constant | Compiled patterns are cached; re-compiling per call wastes CPU on every email |
| Plugin discovery | `importlib` metaclass auto-discovery | Simple list in `main.py` | Metaclass registries are complex; a list is explicit, readable, and sufficient for v1 |
| Email mime parsing | Custom base64/MIME decoder | Already done in Phase 2 `client.py` | `RawEmail.body` is already decoded plain-text; parsers receive a clean string |
| Carrier inference | Map tracking prefixes to carrier names | Pass `None`; let TrackingMore auto-detect | TrackingMore's auto-detection covers 1,500+ carriers (PROJECT.md); home-grown mapping would be incomplete and stale |

**Key insight:** The parser layer is deliberately thin. The heavy lifting (MIME decoding, authentication, dedup, API calls) lives in other layers. `AliExpressParser` should be ≤ 60 lines including docstrings.

---

## AliExpress Email Specifics (D-02 Research)

### Sender Domains

The following domains are confirmed as legitimate AliExpress communication domains based on multiple cross-referenced secondary sources. The user should verify against their actual inbox before the phase is complete.

| Domain | Confidence | Notes |
|--------|------------|-------|
| `@mail.aliexpress.com` | MEDIUM | Most frequently cited as the primary transactional sender [ASSUMED — not personally verified against live inbox] |
| `@aliexpress.com` | MEDIUM | Used for some notification types; catch-all for subdomains not yet seen [ASSUMED] |
| `@notice.aliexpress.com` | LOW | Cited in one source; may be used for order status notifications [ASSUMED] |

**Recommendation for D-01 constant:** Start with `("@mail.aliexpress.com", "@aliexpress.com")`. These two cover the vast majority of AliExpress emails per community sources. The `any(domain in sender for domain in DOMAINS)` pattern handles all subdomain variants (e.g., `shipping@mail.aliexpress.com` matches `@mail.aliexpress.com`).

**User action recommended:** Before closing Phase 3, the user should check one real AliExpress shipping email header and confirm the From domain. If it differs, update the constant — this is a one-line change confined to `aliexpress.py`.

### Email Label Strings (D-02 primary path)

Labels appear immediately before the tracking number token in the email body. Research found the following candidates:

| Label String | Confidence | Source |
|--------------|------------|--------|
| `Tracking number:` | MEDIUM | Cited by multiple tracking aggregator sites as standard AliExpress label [ASSUMED] |
| `Tracking No.` | MEDIUM | Cited alongside "Tracking number" as a variant [ASSUMED] |
| `Logistics No.` | MEDIUM | Cited by one source as a logistics-specific label variant [ASSUMED] |
| `Logistics tracking number` | LOW | Cited by one source; may appear in some notification variants [ASSUMED] |
| `Waybill number` | LOW | Cited by one source as an alternative label [ASSUMED] |
| `Parcel number` | LOW | Possible variant; lower confidence [ASSUMED] |

**Recommendation:** Compile all labels into one case-insensitive regex (Pattern 3 above). The label-anchored path will succeed for any known label; the shape-pattern fallback catches any unlabelled token.

### Tracking Number Shapes (D-02 fallback pattern)

AliExpress uses multiple couriers. The tracking number shapes used across their network:

| Format Family | Shape | Example (FAKE) | Confidence |
|---------------|-------|---------------|------------|
| Cainiao LP codes | `LP` + 10-16 digits | `LP00FAKE123456` | MEDIUM [CITED: parceldetect.com] |
| UPU S10 international | 2 uppercase letters + 8-9 digits + 2 uppercase letters (13 chars) | `RVFAKE6789CN` | HIGH [CITED: parceldetect.com, China Post UPU standard] |
| Cainiao/ePacket LZ/LX | `LZ` or `LX` + 7 digits + `CN` | `LZFAKE123CN` | MEDIUM [CITED: parceldetect.com] |
| Yanwen/YunTu YT prefix | `YT` + 14-18 digits | `YTFAKE12345678` | MEDIUM [CITED: web search results] |
| Yanwen ZA…HK/CN | `ZA` + 9 digits + 2 uppercase | `ZAFAKE567HK` | MEDIUM [CITED: web search results] |
| China Post EMS | `EE`/`EM`/`EA` + 8 digits + `CN` | `EMFAKE456CN` | MEDIUM [CITED: parceldetect.com] |
| China Post Registered | `R` + second letter + 8 digits + `CN` | `RVFAKE789CN` | MEDIUM [CITED: parceldetect.com] |

**Key disambiguation fact:** AliExpress **order numbers** are purely numeric (15-17 digits, e.g., `502370139095420`). [CITED: ship24.com, parcelsapp.com] The shape fallback pattern MUST require at least one letter component to exclude order numbers. A purely numeric sequence of 10+ digits is almost certainly an order reference, not a tracking number.

**Recommended fallback regex (see Pattern 3 above):** The `_SHAPE_FALLBACK` pattern handles all major families and explicitly excludes purely-numeric strings via the mandatory letter anchors in each alternative.

---

## Common Pitfalls

### Pitfall 1: Logging the Tracking Number
**What goes wrong:** Developer logs `result.tracking_number` for debugging, which passes LOG-02 tests but violates CLAUDE.md's "no real tracking numbers in logs" rule.
**Why it happens:** Tracking numbers look like harmless codes, not PII. But CLAUDE.md is explicit: tracking numbers count as sensitive data.
**How to avoid:** Log only `message_id` in parser and dispatch code. Follow the Phase 2 `client.py` pattern exactly.
**Warning signs:** Any `logger.*` call that references `body`, `sender`, `tracking_number`, or `carrier`.

### Pitfall 2: Fallback Pattern Matching Order Reference Numbers
**What goes wrong:** The shape fallback fires on a purely numeric order reference (e.g., `86087307282773`) and returns it as a tracking number. TrackingMore registration then fails on an invalid number.
**Why it happens:** Numeric-only strings don't look different from some domestic tracking formats at first glance.
**How to avoid:** The fallback pattern must require at least one mandatory letter component (prefix or suffix). Never match a purely numeric sequence without a letter anchor.
**Warning signs:** Shape fallback matching a 15-17 digit all-numeric string.

### Pitfall 3: Carrier Field Breaking mypy --strict
**What goes wrong:** `carrier: str | None = None` triggers a mypy error if the field ordering is wrong (fields with defaults must come after fields without defaults in a dataclass).
**Why it happens:** `TrackingInfo` currently has `tracking_number: str` (no default) first and `carrier: str` (no default) second. Adding `= None` to `carrier` while keeping it after `tracking_number` is fine — field ordering is already correct. The only concern is if a third field is added without a default after `carrier`.
**How to avoid:** Keep `carrier: str | None = None` as the last field in the dataclass. Add the `from __future__ import annotations` import for forward-reference compatibility.
**Warning signs:** `mypy` error "non-default argument follows default argument" — fix by ordering required fields before optional fields.

### Pitfall 4: test_tracking_info_dataclass Smoke Test Breaks
**What goes wrong:** The existing smoke test `test_tracking_info_dataclass` instantiates `TrackingInfo(tracking_number="FAKE123", carrier="FAKECARRIER")` with carrier as a positional argument. After D-04, `carrier` becomes keyword-with-default. Positional construction still works (dataclass preserves order), but the test is a good regression check that it does.
**Why it happens:** Making a field optional doesn't break positional construction, but it's worth verifying.
**How to avoid:** Keep the existing smoke test as-is (it still passes), and add a new test that constructs `TrackingInfo(tracking_number="FAKENUMBER")` with `carrier` omitted to prove the default works.
**Warning signs:** `TypeError: __init__() missing 1 required positional argument: 'carrier'` — this would mean D-04 was not applied.

### Pitfall 5: Sender-Domain Wiring Back to Phase 2 GMAIL_SENDER_LIST
**What goes wrong:** The parser constant declares `@mail.aliexpress.com` but `GMAIL_SENDER_LIST` in `.env` still has a different or empty value, so Gmail fetches zero emails.
**Why it happens:** D-01 says the parser constant is the source of truth, but Phase 2's `main.py` reads `GMAIL_SENDER_LIST` from the environment. These two are not yet wired together.
**How to avoid:** In Phase 3, update `main.py` to derive the sender list from parser constants (see Pattern 4's `_get_all_sender_domains()` helper) rather than reading from the environment. The `.env.example` should still document `GMAIL_SENDER_LIST` as optional/deprecated override, but the default should come from the parsers.
**Warning signs:** `gmail.fetch.complete count=0` on every run despite matching emails in the inbox.

### Pitfall 6: Pre-Shipment Emails Causing ValueError Noise
**What goes wrong:** If `extract()` raises `ValueError` (current `base.py` docstring contract), and the dispatch loop doesn't catch it, a routine pre-shipment "order confirmed" email crashes the run.
**Why it happens:** The current `base.py` docstring says `extract()` raises `ValueError` on match-but-fail. D-05 says that outcome is expected and non-fatal.
**How to avoid:** Change `extract()` return type to `TrackingInfo | None`. Return `None` for the no-tracking case. The dispatch loop checks for `None` and logs at debug. No exception machinery needed.
**Warning signs:** `ValueError` in the run log; run exits with non-zero status on pre-shipment emails.

---

## Code Examples

### Synthetic Fixture Shape (Privacy-Safe)

```python
# Source: established FAKE-prefix pattern from tests/conftest.py [VERIFIED: codebase]
# tests/fixtures/fake_aliexpress_email.py

"""Synthetic AliExpress email body fixtures for parser tests.

PRIVACY: All values are synthetic. No real tracking numbers, email addresses,
sender domains, or order references. See CLAUDE.md privacy constraints.
Tracking numbers use FAKE prefix; sender uses @fakealixmail.example.com domain.
"""

# Fixture 1: standard label-anchored body (happy path)
FAKE_ALIEXPRESS_SHIPPED_BODY = """\
Dear Customer,

Your order has been shipped.

Tracking number: FAKELP00FAKE0001
Carrier: FAKECARRIER

You can track your package at: https://faketrack.example.com

Thank you for shopping with us.
"""

# Fixture 2: "Logistics No." label variant
FAKE_ALIEXPRESS_LOGISTICS_BODY = """\
Hi,

Order dispatched.
Logistics No.: FAKEXX1234FAKE56CN
"""

# Fixture 3: pre-shipment / no tracking number (D-05 expected case)
FAKE_ALIEXPRESS_PRESHIPMENT_BODY = """\
Thank you for your order!

Your order is being processed. You will receive a shipping
notification once it has been dispatched.

Order reference: 500FAKE123456789
"""

# Fixture 4: fallback shape — no recognisable label, tracking number present in body
FAKE_ALIEXPRESS_NOLABEL_BODY = """\
Shipment update:
FAKEYT00000FAKE0001 is on its way.
"""
```

### D-04: TrackingInfo With Optional Carrier

```python
# Source: Python 3.11 dataclasses stdlib [VERIFIED: codebase + stdlib]
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class TrackingInfo:
    """Structured tracking data extracted from a shipping email."""
    tracking_number: str
    carrier: str | None = None
```

### AliExpressParser Structure Sketch

```python
# Source: D-01/D-02/D-05 decisions + Pattern 1-3 above [ASSUMED for label strings]
from __future__ import annotations
import logging
import re
from shipping_tracker.parsers.base import BaseParser, TrackingInfo

logger = logging.getLogger(__name__)

ALIEXPRESS_SENDER_DOMAINS: tuple[str, ...] = (
    "@mail.aliexpress.com",
    "@aliexpress.com",
)

_LABEL_RE = re.compile(
    r"""(?:Tracking\s+(?:number|No\.?)|Logistics\s+(?:No\.?|tracking\s+number)
         |Waybill\s+(?:number|No\.?)|Parcel\s+(?:number|No\.?))
        \s*[:\s]\s*([A-Z0-9]{8,35})""",
    re.IGNORECASE | re.VERBOSE,
)

_SHAPE_RE = re.compile(
    r"""\b(?:LP\d{10,16}|[A-Z]{2}\d{8,10}[A-Z]{2}|YT\d{14,18}
           |[A-Z]{2}\d{9,13}[A-Z]{2})\b""",
    re.VERBOSE,
)

class AliExpressParser(BaseParser):
    def can_parse(self, email_body: str, sender: str) -> bool:
        return any(d in sender for d in ALIEXPRESS_SENDER_DOMAINS)

    def extract(self, email_body: str) -> TrackingInfo | None:
        # Stage 1: label-anchored
        m = _LABEL_RE.search(email_body)
        if m:
            return TrackingInfo(tracking_number=m.group(1))

        # Stage 2: shape fallback
        m2 = _SHAPE_RE.search(email_body)
        if m2:
            return TrackingInfo(tracking_number=m2.group(0))

        return None  # pre-shipment / no tracking number (D-05)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `TrackingInfo.carrier: str` (required) | `TrackingInfo.carrier: str \| None = None` | Phase 3 (D-04) | Removes the need to guess the carrier; TrackingMore auto-detects |
| `extract()` raises `ValueError` on no-tracking (base.py docstring) | `extract()` returns `None` on no-tracking | Phase 3 (D-05 recommendation) | Pre-shipment emails handled without exception flow |
| `GMAIL_SENDER_LIST` hardcoded in `.env` | Derived from parser `ALIEXPRESS_SENDER_DOMAINS` constants | Phase 3 (D-01) | Adding a new parser automatically extends the Gmail query |

**Deprecated/outdated:**
- `TrackingInfo(carrier="")` empty-string sentinel: explicitly rejected by D-04. Use `None`.
- Body-marker-only matching in `can_parse()`: explicitly rejected by D-01. Use sender domain.

---

## Discretion Recommendations

The following are recommendations for the three "Claude's Discretion" items from CONTEXT.md:

### 1. Mechanism for No-Tracking Skip (D-05)

**Recommendation: `extract()` returns `TrackingInfo | None`.**

Rationale:
- Pre-shipment emails arrive on every order before the item ships. For a user who orders frequently, this is the majority of AliExpress emails. Raising `ValueError` for the common case and catching it every loop iteration is semantically wrong — exceptions should not be used for expected control flow.
- `TrackingInfo | None` is self-documenting: the type signature at the call site makes both outcomes explicit. A caller cannot accidentally ignore the `None` case when mypy `--strict` is active.
- The current `base.py` docstring contract (`raises ValueError`) was written at scaffold time before D-05 was locked. Updating the docstring and return type is a legitimate change at Phase 3.
- **Cost:** The `base.py` `extract()` signature changes from `-> TrackingInfo` to `-> TrackingInfo | None`. The dispatch loop checks `if result is not None`.

### 2. Parser-Owned Sender Domains Wiring Back to Phase 2 (D-01)

**Recommendation: Replace the `GMAIL_SENDER_LIST` env read in `main.py` with a function that collects domains from all registered parsers.**

Rationale:
- D-01 explicitly says the parser constant is the source of truth. An env variable that can drift out of sync with the parser is a latent bug.
- `main.py` already imports `AliExpressParser`; importing `ALIEXPRESS_SENDER_DOMAINS` alongside it costs nothing.
- The `.env.example` comment can document that the sender list is now parser-derived, keeping the contract visible to users setting up the tool.
- The `GMAIL_SENDER_LIST` env var could be kept as an *override* (non-empty env value wins over parser-derived) so power users can add ad-hoc senders without creating a parser. This is optional.

### 3. Parser Registry Location

**Recommendation: Define `PARSERS` as a module-level list in `main.py` for Phase 3 (single parser).**

Rationale:
- A separate `registry.py` module is the right pattern when there are 3+ parsers with shared registration logic. For one parser, it is premature abstraction.
- `main.py` is the pipeline orchestrator; the registry list is part of the pipeline configuration. Collocating them makes the dependency explicit.
- When Phase 2 sellers arrive, refactoring to a `registry.py` is a one-file extraction with no logic changes.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >=9.0 (installed) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_aliexpress_parser.py -x -q` |
| Full suite command | `pytest -q` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PARSE-01 | `BaseParser` ABC enforces `can_parse`/`extract` contract | unit (smoke) | `pytest tests/test_smoke.py::test_base_parser_is_abstract -x` | Yes (existing) |
| PARSE-01 | `TrackingInfo` with optional carrier constructs correctly | unit | `pytest tests/test_smoke.py::test_tracking_info_dataclass -x` | Needs update (D-04) |
| PARSE-01 | `TrackingInfo(tracking_number=...)` works with carrier omitted | unit | `pytest tests/test_aliexpress_parser.py::test_tracking_info_carrier_optional -x` | No — Wave 0 gap |
| PARSE-02 | `AliExpressParser.can_parse()` returns True for known sender domains | unit | `pytest tests/test_aliexpress_parser.py::test_can_parse_known_domains -x` | No — Wave 0 gap |
| PARSE-02 | `AliExpressParser.can_parse()` returns False for non-AliExpress sender | unit | `pytest tests/test_aliexpress_parser.py::test_can_parse_rejects_other_senders -x` | No — Wave 0 gap |
| PARSE-02 | `extract()` returns `TrackingInfo` with correct number for label-anchored body | unit | `pytest tests/test_aliexpress_parser.py::test_extract_label_anchored -x` | No — Wave 0 gap |
| PARSE-02 | `extract()` returns `TrackingInfo` via fallback shape when no label present | unit | `pytest tests/test_aliexpress_parser.py::test_extract_shape_fallback -x` | No — Wave 0 gap |
| PARSE-02 | `extract()` returns `None` for pre-shipment body (no tracking number) | unit | `pytest tests/test_aliexpress_parser.py::test_extract_returns_none_preshipment -x` | No — Wave 0 gap |
| PARSE-02 | Carrier is `None` when email does not name a courier | unit | `pytest tests/test_aliexpress_parser.py::test_extract_carrier_none -x` | No — Wave 0 gap |
| PARSE-02 | LOG-02: parser does not log body, sender, or tracking number | unit | `pytest tests/test_aliexpress_parser.py::test_extract_does_not_log_pii -x` | No — Wave 0 gap |
| PARSE-03 | Dispatch loop: matched email with tracking yields `TrackingInfo` | integration | `pytest tests/test_aliexpress_parser.py::test_dispatch_matched_email -x` | No — Wave 0 gap |
| PARSE-03 | Dispatch loop: no-match email logs info and does not raise | integration | `pytest tests/test_aliexpress_parser.py::test_dispatch_no_match_skips -x` | No — Wave 0 gap |
| PARSE-03 | Dispatch loop: pre-shipment email logs debug and does not raise | integration | `pytest tests/test_aliexpress_parser.py::test_dispatch_preshipment_skips -x` | No — Wave 0 gap |
| PARSE-03 | Adding a second fake parser to the list makes it discoverable | unit | `pytest tests/test_aliexpress_parser.py::test_registry_drop_in -x` | No — Wave 0 gap |

### Sampling Rate

- **Per task commit:** `pytest tests/test_aliexpress_parser.py tests/test_smoke.py -x -q`
- **Per wave merge:** `pytest -q`
- **Phase gate:** Full suite green (`pytest -q`, zero failures) before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/fixtures/fake_aliexpress_email.py` — synthetic body variants for all test cases
- [ ] `tests/test_aliexpress_parser.py` — all 13 new test functions listed above
- [ ] Update `tests/test_smoke.py::test_tracking_info_dataclass` to also test the `carrier=None` default after D-04

*(Existing test infrastructure is fully adequate — no framework install needed)*

---

## Security Domain

*`security_enforcement` is enabled (not set to false in config.json).*

### Applicable ASVS Categories (ASVS Level 1)

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Phase 3 has no auth; Gmail auth is Phase 2 |
| V3 Session Management | No | Stateless parsing; no sessions |
| V4 Access Control | No | No user-facing endpoints |
| V5 Input Validation | Yes | Regex input validation on email body strings |
| V6 Cryptography | No | No crypto operations in this phase |
| V7 Error Handling and Logging | Yes | PII-safe logging (LOG-02); no sensitive data in errors |

### Known Threat Patterns for Email Parsing

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| ReDoS (catastrophic regex backtracking) | DoS | Use possessive quantifiers or atomic groups; avoid nested quantifiers on unbounded input. The constrained shape patterns use fixed-width alternatives `{8,35}` and explicit prefixes — safe against ReDoS on typical email bodies. |
| Crafted email body that extracts a malicious tracking number | Tampering | Tracking number captured by regex is passed to TrackingMore in Phase 5 as opaque data. TrackingMore validates format server-side. No SQL or shell interpolation in Phase 3. |
| Order reference number extracted as tracking number | Spoofing | Shape fallback requires mandatory letter components; purely numeric strings (order references) are excluded from the pattern. |
| Sensitive data exposure via logs | Information Disclosure | Parser logs only `message_id`. `TrackingInfo` fields are never logged. Established LOG-02 pattern from Phase 2. |

**ReDoS assessment:** The `_LABEL_RE` and `_SHAPE_RE` patterns use bounded quantifiers (`{8,35}`, `{10,16}`, etc.) and fixed letter-prefix anchors. There are no nested quantifiers or overlapping alternatives on unbounded character classes. Risk: LOW.

---

## Environment Availability

Phase 3 is pure Python stdlib + existing installed packages. No new external tools, services, or CLI utilities are required.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | All | Yes | 3.14.0 (exceeds requirement) | — |
| `re` module | Regex extraction | Yes | stdlib | — |
| `abc` module | BaseParser ABC | Yes | stdlib | — |
| `dataclasses` module | TrackingInfo | Yes | stdlib | — |
| `pytest` | Test suite | Yes | >=9.0 (pyproject.toml) | — |
| `mypy` | Type checking | Yes | >=2.1 (pyproject.toml) | — |

**Missing dependencies with no fallback:** None.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | AliExpress shipping notification emails are sent from `@mail.aliexpress.com` and/or `@aliexpress.com` subdomains | AliExpress Email Specifics — Sender Domains | `can_parse()` returns False for all AliExpress emails; zero tracking numbers extracted. Mitigated by: user verifies inbox before closing phase. |
| A2 | "Tracking number:", "Tracking No.", "Logistics No.", "Logistics tracking number", "Waybill number" are the primary label strings in AliExpress email bodies | AliExpress Email Specifics — Email Label Strings | Label-anchored path never fires; shape-pattern fallback takes over. Fallback is designed to handle this. Risk is LOW-MEDIUM. |
| A3 | AliExpress order numbers are purely numeric (15-17 digits) and thus excluded by the mandatory-letter-component shape pattern | AliExpress Email Specifics — Tracking Number Shapes | If an order reference shares a shape with a tracking number, false positives result. Multiple sources confirm order numbers are numeric-only; risk LOW. |
| A4 | The `notice.aliexpress.com` domain is used by some AliExpress notification emails | AliExpress Email Specifics — Sender Domains | If this domain is used and not in the constant, some emails are silently skipped. Mitigated by: `@aliexpress.com` suffix match catches all `*.aliexpress.com` domains. |
| A5 | `extract()` returning `TrackingInfo \| None` (rather than raising `ValueError`) is compatible with mypy `--strict` for the revised `BaseParser.extract()` abstract method signature | D-02 / Pattern 2 | mypy error in `base.py` or `aliexpress.py`. Low risk — `Optional` return types are standard mypy practice. |

---

## Open Questions

1. **Real AliExpress sender domain confirmation**
   - What we know: Multiple secondary sources cite `@mail.aliexpress.com` as the standard transactional domain.
   - What's unclear: Whether `@notice.aliexpress.com` or other subdomains are used for shipping specifically vs. marketing.
   - Recommendation: User checks one real "your order has shipped" email before closing Phase 3 and updates the constant if needed. One-line change.

2. **"Carrier" extraction — is it worth attempting?**
   - What we know: TrackingMore auto-detects carriers; D-04 makes `carrier` optional. The email may or may not name the courier.
   - What's unclear: How frequently AliExpress shipping emails include a carrier name (e.g., "China Post", "Cainiao") in a labelled field.
   - Recommendation: For v1, attempt carrier extraction with a simple label pattern (e.g., `Carrier:\s*(\w+[\w\s]*)`) capped at 40 characters. If not found, return `None`. Do not invest heavily in carrier name normalisation — that belongs in a separate mapping step if needed.

3. **Multiple tracking numbers in one email (D-03 scope)**
   - What we know: D-03 explicitly defers multi-parcel handling. First match wins.
   - What's unclear: How common multi-parcel emails are in practice for AliExpress standard shipping.
   - Recommendation: Implement first-match per D-03. Log at info if additional candidates are found (message_id + count only, no tracking numbers). This ensures the deferred case is observable in logs.

---

## Sources

### Primary (HIGH confidence)
- Python 3.11 stdlib — `re`, `abc`, `dataclasses` modules — verified by running `python -c "import re, abc, dataclasses"` on the target environment
- `C:\Projects\shipping-tracker\shipping_tracker\parsers\base.py` — existing BaseParser ABC and TrackingInfo dataclass
- `C:\Projects\shipping-tracker\shipping_tracker\gmail\client.py` — RawEmail shape, PII-safe logging pattern
- `C:\Projects\shipping-tracker\shipping_tracker\main.py` — pipeline orchestrator, existing GMAIL_SENDER_LIST pattern
- `C:\Projects\shipping-tracker\pyproject.toml` — confirmed installed packages and mypy config
- `C:\Projects\shipping-tracker\.planning\phases\03-parser-layer\03-CONTEXT.md` — all locked decisions

### Secondary (MEDIUM confidence)
- [parceldetect.com — AliExpress Standard Shipping Tracking Number Format](https://parceldetect.com/faq/aliexpress-standard-shipping-tracking-number-format) — LP, CN, UPU S10 format details
- [parceldetect.com — China Post Tracking Number Formats](https://parceldetect.com/faq/china-post-tracking-number-format) — R/E/L/C prefix families, UPU S10 regex
- Web search results — AliExpress order number format (numeric-only, 15-17 digits)
- Web search results — `@mail.aliexpress.com` as primary AliExpress transactional sender domain

### Tertiary (LOW confidence — flagged as ASSUMED in text)
- Web search results — Label string variants ("Waybill number", "Parcel number", "Logistics tracking number")
- Web search results — `@notice.aliexpress.com` subdomain usage

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — stdlib only; no new packages; all verified in pyproject.toml
- Architecture patterns: HIGH — ABC/dataclass patterns are established Python idioms; dispatch loop follows existing Phase 2 style
- AliExpress email specifics (label strings, sender domains): MEDIUM — cross-referenced secondary sources; not verified against live inbox; user confirmation recommended before closing phase
- Fallback shape pattern: MEDIUM — tracking number format families confirmed by authoritative-adjacent sources; order-number disambiguation logic is sound
- Pitfalls: HIGH — derived from codebase inspection, mypy behaviour, and D-04/D-05 decision implications

**Research date:** 2026-06-01
**Valid until:** 2026-07-01 (AliExpress email format stable; Python stdlib does not change; re-verify sender domain if AliExpress updates their email infrastructure)
