---
phase: 03-parser-layer
reviewed: 2026-06-01T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - shipping_tracker/main.py
  - shipping_tracker/parsers/__init__.py
  - shipping_tracker/parsers/aliexpress.py
  - shipping_tracker/parsers/base.py
  - tests/fixtures/fake_aliexpress_email.py
  - tests/test_aliexpress_parser.py
  - tests/test_smoke.py
findings:
  critical: 2
  warning: 4
  info: 3
  total: 9
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-06-01T00:00:00Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Phase 3 wires the pluggable parser layer: `BaseParser`/`TrackingInfo` interface,
`AliExpressParser` with label-anchored + shape-fallback extraction, and a
first-match-wins dispatch loop in `main()`. The privacy posture is good — no PII
in fixtures or source, log calls carry only `message_id`/counts with %-style
formatting, and `RawEmail.__repr__` is PII-safe. The extraction regexes are
ReDoS-safe (all quantifiers bounded; timing tests on 50k adversarial inputs
return in ~1ms).

However, two correctness defects affect the core value proposition ("register
the *correct* tracking number, fetch *all* parser senders"):

1. The `_LABEL_RE` length cap silently **truncates** over-length tracking
   numbers, producing a wrong number that would be registered with TrackingMore.
2. `_get_all_sender_domains()` does not actually derive from `PARSERS` — it
   hardcodes the AliExpress constant, breaking the stated D-01 "drop-in parser"
   contract; a second parser's emails would never be fetched.

Additional warnings cover the broad shape-fallback alternative (false-matches
ordinary contiguous tokens like `HTTP200OK`), `IGNORECASE` capturing lowercase
tracking numbers (dedup hazard for Phase 4), and routine success logged at
WARNING level (cron-noise / monitoring false alarms). A vacuous PII test rounds
out the info items.

## Critical Issues

### CR-01: Over-length tracking numbers are silently truncated to 35 chars

**File:** `shipping_tracker/parsers/aliexpress.py:33`
**Issue:** The capture group `([A-Z0-9]{8,35})` is bounded to 35 chars but is
**not** anchored by a trailing word boundary. When a real tracking number
exceeds 35 characters, the regex greedily captures the first 35 and stops
mid-token, returning a corrupted number rather than rejecting or capturing the
full token. Confirmed empirically:

```
input:    "Tracking number: LP123456789012345678901234567890123456"  (38-char token)
captured: "LP123456789012345678901234567890123"                       (35 chars — wrong)
```

This corrupted value would be registered with the TrackingMore API as a distinct
(invalid) tracking number, defeating the core value of the tool and creating a
phantom parcel that never resolves. Some carriers (e.g. certain UPU S10 +
suffix, freight references) do exceed 35 chars.

**Fix:** Require a word boundary after the token so an over-length token fails to
match the cap (then falls through to the shape stage / `None`) instead of being
truncated; and/or widen and validate the bound explicitly:
```python
# Option A: anchor the token so a too-long token does not partially match
([A-Z0-9]{8,35})(?![A-Z0-9])
# Option B: widen the upper bound to the real-world max and length-validate
#           the captured value before returning TrackingInfo.
```
Add a fixture with a >35-char token asserting either full capture or `None`
(never a truncated value).

### CR-02: `_get_all_sender_domains()` ignores `PARSERS`, breaking the D-01 drop-in contract

**File:** `shipping_tracker/main.py:26-32`
**Issue:** The docstring states this is "the single source of truth for the
Gmail `from:()` query" and that "adding a new parser automatically extends the
fetch scope (D-01)." The implementation returns `list(ALIEXPRESS_SENDER_DOMAINS)`
— a hardcoded import of one parser's constant. It does **not** iterate `PARSERS`.

Consequence: when a second parser is appended to `PARSERS` (the documented
extension mechanism, D-01), its sender domains are **not** added to the Gmail
query. Its emails are never fetched, so its `can_parse`/`extract` never run —
silently. The fetch scope and the dispatch registry drift apart, which is
exactly the failure mode T-03-10 claims to mitigate. `test_registry_drop_in`
does not catch this because it tests `can_parse` against a hand-built `RawEmail`,
not the query-building path.

`BaseParser` also exposes no domain accessor, so there is currently no generic
way to aggregate domains across parsers — the abstraction is incomplete.

**Fix:** Give `BaseParser` a domain declaration and aggregate it:
```python
# base.py
class BaseParser(ABC):
    sender_domains: tuple[str, ...] = ()

# aliexpress.py
class AliExpressParser(BaseParser):
    sender_domains = ALIEXPRESS_SENDER_DOMAINS

# main.py
def _get_all_sender_domains() -> list[str]:
    domains: list[str] = []
    for parser in PARSERS:
        domains.extend(parser.sender_domains)
    return domains
```
Add a test: appending a second parser with a new domain makes that domain appear
in `_get_all_sender_domains()`.

## Warnings

### WR-01: Shape-fallback last alternative false-matches ordinary contiguous tokens

**File:** `shipping_tracker/parsers/aliexpress.py:49`
**Issue:** The catch-all alternative `[A-Z]{2,} \d{3,} [A-Z]{2,} [A-Z0-9]*`
matches any contiguous letters-digits-letters token with ≥3 digits. Plausible
non-tracking strings in real email bodies match and would be registered as
tracking numbers:
```
"ISO9001CERT" -> ISO9001CERT
"HTTP200OK"   -> HTTP200OK
"ABC123XYZ"   -> ABC123XYZ
```
Product SKUs, certification codes, and footer text routinely take this shape.
A false tracking number registered with TrackingMore is a silent data-quality
defect. (The purely-numeric order-ref case from Pitfall 2 is correctly
rejected — verified `500FAKE123456789` → no match — but the mixed case is not.)

**Fix:** Tighten the fallback to known AliExpress/Cainiao carrier shapes only
(LP/YT/UPU-S10 prefixes already enumerated above it), and drop the open-ended
`[A-Z]{2,} \d{3,} [A-Z]{2,} [A-Z0-9]*` alternative — or gate it behind a
shipping-context keyword. Add negative fixtures (`HTTP200OK`, `ISO9001CERT`)
asserting `extract()` returns `None`.

### WR-02: `IGNORECASE` captures lowercase tracking numbers → Phase 4 dedup hazard

**File:** `shipping_tracker/parsers/aliexpress.py:33,35`
**Issue:** `re.IGNORECASE` applies to the capture class `[A-Z0-9]`, so a
lowercase body token is captured verbatim:
```
"Tracking number: lp00fake00001" -> captured "lp00fake00001"
```
Tracking numbers are conventionally uppercase. Capturing case-as-written means
the same physical number arriving in two casings dedupes as two distinct numbers
in the Phase 4 dedup key, producing duplicate registrations/notifications — one
of the explicit non-goals ("without duplicates").

**Fix:** Normalise the captured value before constructing `TrackingInfo`:
```python
return TrackingInfo(tracking_number=m.group(1).upper())
```
(apply to both the label and shape stages). Add a test asserting a lowercase
body yields an uppercased tracking number.

### WR-03: Routine success-path summaries logged at WARNING level (cron noise)

**File:** `shipping_tracker/main.py:59,77-81`
**Issue:** `gmail.fetch.complete` and `parser.dispatch.complete` are normal
end-of-run summaries but are emitted at `logger.warning`. For an unattended cron
job, every successful run will surface a WARNING, defeating log-level-based
alerting (operators filtering for WARNING+ get false alarms on healthy runs).
`gmail.client.py:240` already logs the identical `gmail.fetch.complete` event at
INFO, so line 59 is both a duplicate and a level inconsistency.

**Fix:** Use `logger.info` for both summaries, and remove the duplicate
`gmail.fetch.complete` at `main.py:59` (the client already logs it):
```python
logger.info("parser.dispatch.complete total=%d parsed=%d",
            len(emails), len(tracking_results))
```

### WR-04: A parser raising in `extract()`/`can_parse()` crashes the whole run

**File:** `shipping_tracker/main.py:62-75`
**Issue:** The dispatch loop has no per-email error isolation. If any parser's
`can_parse` or `extract` raises (e.g. a future parser, or a malformed body
hitting an edge case), the exception propagates out of `main()` and aborts the
entire batch — every remaining email in the fetch is dropped for that cron run.
For an unattended tool the "no-raise guarantee" the project context calls out is
not currently provided at the dispatch level.

**Fix:** Wrap per-email dispatch in a try/except that logs `message_id` + error
type (no body/sender — LOG-02) and continues:
```python
for email in emails:
    try:
        ... # existing match/extract logic
    except Exception:
        logger.exception("parser.dispatch.error id=%s", email.message_id)
        continue
```

## Info

### IN-01: PII-safe-logging test is vacuous

**File:** `tests/test_aliexpress_parser.py:72-80`
**Issue:** `extract()` contains no logging calls, so `caplog.records` is empty
and the assertion loop body never executes — the test passes unconditionally and
would keep passing even if `extract()` were later changed to log the body.
Additionally `"Tracking number"` is a label string, not PII. The test gives
false confidence about LOG-02 enforcement.

**Fix:** Assert the absence of records explicitly
(`assert caplog.records == []`), or, when a future logging line is added, assert
the tracking number / body substrings are absent from emitted records — and test
the dispatch-loop log path (which *does* log) rather than `extract()` alone.

### IN-02: D-01 docstring overstates behavior

**File:** `shipping_tracker/main.py:27-32`
**Issue:** Independent of the CR-02 fix, the docstring claim "Adding a new parser
automatically extends the fetch scope" is currently false for the shipped code.
Documentation that describes intended-but-unimplemented behavior misleads future
maintainers.

**Fix:** Once CR-02 is implemented the docstring becomes accurate; until then it
should not assert auto-extension.

### IN-03: Fixture comment cites a non-matching sender domain shape

**File:** `tests/fixtures/fake_aliexpress_email.py:6,54`
**Issue:** The header comment says "sender uses @fakealixmail.example.com domain"
but the actual constant is `shipping@fakemailaliexpress.example.com` — the
documented domain does not match the value, a minor doc/code drift. (No PII
concern; both are synthetic `.example.com` domains, which is correct.)

**Fix:** Align the comment with the actual `FAKE_ALIEXPRESS_SENDER` value.

---

_Reviewed: 2026-06-01T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
