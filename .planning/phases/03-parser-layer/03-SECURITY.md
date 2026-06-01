---
phase: 03-parser-layer
audited: 2026-06-01
asvs_level: 1
auditor: gsd-security-auditor
verdict: SECURED
threats_total: 11
threats_closed: 11
threats_open: 0
---

# Phase 03 — Parser Layer Security Audit

**Phase:** 3 — parser-layer
**Audit date:** 2026-06-01
**Auditor:** gsd-security-auditor (claude-sonnet-4-6)
**ASVS Level:** 1
**block_on:** high (OPEN_THREATS block shipment)

---

## Summary

**Threats closed:** 11 / 11
**Threats open:** 0 / 11
**Unregistered flags:** 0

All declared mitigations are present in the shipped implementation.
Phase 3 may ship.

---

## Threat Verification

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-03-01 | Information Disclosure | mitigate | CLOSED | See detail below |
| T-03-02 | Information Disclosure | mitigate | CLOSED | See detail below |
| T-03-03 | Denial of Service | mitigate | CLOSED | See detail below |
| T-03-04 | Denial of Service (ReDoS) | mitigate | CLOSED | See detail below |
| T-03-05 | Spoofing | mitigate | CLOSED | See detail below |
| T-03-06 | Information Disclosure | mitigate | CLOSED | See detail below |
| T-03-07 | Denial of Service | mitigate | CLOSED | See detail below |
| T-03-08 | Denial of Service | mitigate | CLOSED | See detail below |
| T-03-09 | Information Disclosure | mitigate | CLOSED | See detail below |
| T-03-10 | Tampering | mitigate | CLOSED | See detail below |
| T-03-SC | Tampering | accept | CLOSED | See accepted risks log |

---

## Per-Threat Evidence

### T-03-01 — Information Disclosure: test fixtures (CLOSED)

**Mitigation declared:** All fixture values FAKE-prefixed / `.example.com`;
PRIVACY docstring; no real `aliexpress.com` domains in fixtures.

**Verification:**

- `tests/fixtures/fake_aliexpress_email.py:3` — PRIVACY docstring present:
  `PRIVACY: All values are synthetic. No real tracking numbers, email addresses,`
- `tests/fixtures/fake_aliexpress_email.py:9,23,31,38,48,54,55` — all exported
  constants are FAKE-prefixed (`FAKE_ALIEXPRESS_SHIPPED_BODY`, etc.)
- `tests/fixtures/fake_aliexpress_email.py:54` — sender constant value is
  `shipping@fakemailaliexpress.example.com` (.example.com, not aliexpress.com)
- `tests/fixtures/fake_aliexpress_email.py:55` — second sender
  `noreply@fakeotherstore.example.com` (.example.com)
- Grep for `aliexpress.com` in the fixture file returns zero matches — no real
  AliExpress domain appears as a fixture value.

**Note on IN-03 (out of scope for this audit):** The module docstring on line 5
says "sender uses @fakealixmail.example.com domain" but the actual constant at
line 54 is `@fakemailaliexpress.example.com`. This is comment/code drift only;
both values are synthetic `.example.com` domains. It is not a T-03-01 privacy
violation and does not affect threat disposition.

---

### T-03-02 — Information Disclosure: PII-safe logging test (CLOSED)

**Mitigation declared:** `test_extract_does_not_log_pii` asserts no body /
tracking number text appears in any log record (LOG-02).

**Verification:**

- `tests/test_aliexpress_parser.py:72–80` — `test_extract_does_not_log_pii`
  exists, uses `caplog.at_level("DEBUG")`, and asserts both
  `"FAKELP00FAKE00001" not in record.message` and
  `"Tracking number" not in record.message` for every record.
- `tests/test_aliexpress_parser.py:310–355` — `test_main_dispatch_loop_logs_pii_safely_on_error`
  (added by WR-04 fix) strengthens LOG-02 coverage by exercising the dispatch
  loop's real error-log path and asserting that `SECRETBODY` and
  `FAKELP00FAKE00001` are absent from every record while `FAKEMSGID_PII` is
  present. This addresses the previously vacuous IN-01 concern.

---

### T-03-03 — Denial of Service: extract() return contract (CLOSED)

**Mitigation declared:** `extract()` returns `TrackingInfo | None` (no
exception flow on pre-shipment) so a no-tracking email cannot crash the run.

**Verification:**

- `shipping_tracker/parsers/base.py:46` — abstract signature is
  `def extract(self, email_body: str) -> TrackingInfo | None:`
- `shipping_tracker/parsers/base.py:55` — docstring states "or None if the
  email matches but contains no tracking number (e.g., pre-shipment order
  confirmation emails — expected routine case per D-05)"
- No `Raises: ValueError` clause present in the docstring (removed per D-05).

---

### T-03-04 — Denial of Service (ReDoS): `_LABEL_RE` / `_SHAPE_RE` (CLOSED)

**Mitigation declared:** Bounded quantifiers only, no nested unbounded
quantifiers, regexes compiled at module level.

**Verification:**

- `shipping_tracker/parsers/aliexpress.py:24` — `_LABEL_RE = re.compile(...)` at
  module level (not inside `extract()`).
- `shipping_tracker/parsers/aliexpress.py:44` — `_SHAPE_RE = re.compile(...)` at
  module level.
- Quantifiers in `_LABEL_RE`: `{8,35}` — bounded upper limit.
- Quantifiers in `_SHAPE_RE`: `{10,16}`, `{8,10}`, `{14,18}`, `{9,13}`,
  `{2,}` (bounded minimum, used inside a look-ahead with a total-length gate
  `{16,35}`), `{3,}` (same look-ahead gated). No nested unbounded quantifiers;
  no `.*` or `.+` inside a group that is itself repeated.
- CR-01 fix (`aliexpress.py:34`) added `(?![A-Z0-9])` trailing boundary to
  `_LABEL_RE` — this is a zero-width negative look-ahead, not a quantifier, and
  does not introduce ReDoS risk.
- WR-01 fix (`aliexpress.py:56–58`) added a length-gated look-ahead
  `(?=[A-Z0-9]{16,35}\b)` with two positive look-aheads as guards; all
  quantifiers remain bounded.

---

### T-03-05 — Spoofing: `_SHAPE_RE` fallback rejects purely-numeric refs (CLOSED)

**Mitigation declared:** Every fallback alternative requires a mandatory letter
component so a purely-numeric order reference cannot be mis-extracted.

**Verification:**

- `shipping_tracker/parsers/aliexpress.py:42–43` — comment: "Every alternative
  requires at least one mandatory letter component so that purely-numeric order
  references (Pitfall 2 / T-03-05) cannot false-match."
- `shipping_tracker/parsers/aliexpress.py:48–59` — examining each alternative:
  - `LP [A-Z0-9]{10,16}` — mandatory `LP` letter prefix.
  - `[A-Z]{2} \d{8,10} [A-Z]{2}` — mandatory letter prefix and suffix.
  - `YT \d{14,18}` — mandatory `YT` letter prefix.
  - `[A-Z]{2} \d{9,13} [A-Z]{2}` — mandatory letter prefix and suffix.
  - Fifth alternative (WR-01 fix): `(?=[A-Z0-9]*[A-Z])` look-ahead at line 57
    asserts at least one letter must be present.
- `tests/test_aliexpress_parser.py:199–202` — `test_extract_shape_rejects_numeric_order_ref`
  asserts `parser.extract("Order reference: 500FAKE123456789") is None`.

**Note on WR-01 interaction:** The WR-01 fix tightened the fifth alternative
with a 16-char minimum length gate, which only strengthens the T-03-05
mitigation — short purely-numeric sequences fail both the letter requirement and
the length gate.

---

### T-03-06 — Information Disclosure: aliexpress.py logging (CLOSED)

**Mitigation declared:** `extract()` / parser emits no log calls referencing
body/sender/tracking_number (LOG-02).

**Verification:**

- Grep for `logger.(debug|info|warning|error|exception)` in
  `shipping_tracker/parsers/aliexpress.py` returns zero matches. The `logger`
  object is declared at line 10 but is never called anywhere in the file.
- `extract()` at lines 79–102 contains no logging statements of any kind.

---

### T-03-07 — Denial of Service: extract() on no-tracking body (CLOSED)

**Mitigation declared:** Returns `None` rather than raising (D-05).

**Verification:**

- `shipping_tracker/parsers/aliexpress.py:102` — `return None` is the final
  statement of `extract()`, reached when neither `_LABEL_RE` nor `_SHAPE_RE`
  matches.
- `shipping_tracker/parsers/aliexpress.py:84` — docstring: "Returns None for
  pre-shipment bodies with no tracking number (D-05)."
- `tests/test_aliexpress_parser.py:58–61` — `test_extract_returns_none_preshipment`
  asserts `parser.extract(FAKE_ALIEXPRESS_PRESHIPMENT_BODY) is None`.

---

### T-03-08 — Denial of Service: main() dispatch loop (CLOSED)

**Mitigation declared:** A no-tracking or no-match email is logged and skipped,
never raised — one bad email cannot crash the run.

**Verification:**

- `shipping_tracker/main.py:75–92` — per-email `try/except Exception` block
  wraps the entire match/extract logic for each email (WR-04 fix). On any
  exception, `logger.exception("parser.dispatch.error id=%s", email.message_id)`
  is called and `continue` skips to the next email.
- `shipping_tracker/main.py:83` — pre-shipment path: `logger.debug("parser.no_tracking id=%s", email.message_id)` and falls through (no raise).
- `shipping_tracker/main.py:88` — no-match path: `logger.info("parser.no_match id=%s", email.message_id)` and falls through (no raise).
- `tests/test_aliexpress_parser.py:259–307` — `test_dispatch_isolates_raising_parser`
  proves a raising parser does not abort the batch; the subsequent good email
  still produces a `TrackingInfo`.

---

### T-03-09 — Information Disclosure: main() dispatch log calls (CLOSED)

**Mitigation declared:** All dispatch log calls carry only message_id / counts
(`%`-style); body/sender/tracking_number never logged.

**Verification — every log call in main.py examined:**

| Line | Call | Fields logged |
|------|------|---------------|
| 63 | `logger.error("gmail.credentials.missing path=%s", exc.filename)` | file path only (no email content) |
| 83 | `logger.debug("parser.no_tracking id=%s", email.message_id)` | message_id only |
| 88 | `logger.info("parser.no_match id=%s", email.message_id)` | message_id only |
| 91 | `logger.exception("parser.dispatch.error id=%s", email.message_id)` | message_id only |
| 96–100 | `logger.info("parser.dispatch.complete total=%d parsed=%d", ...)` | counts only |

No log call in `main.py` passes `email.body`, `email.sender`, any
`tracking_number`, or `carrier` as an argument. All calls use `%`-style
formatting (not f-strings).

---

### T-03-10 — Tampering: `_get_all_sender_domains()` single source of truth (CLOSED)

**Mitigation declared:** Sender list derived from parser-owned constants (single
source of truth), no env/parser divergence.

**Verification (CR-02 fix applied):**

- `shipping_tracker/parsers/base.py:30` — `BaseParser` declares
  `sender_domains: tuple[str, ...] = ()`.
- `shipping_tracker/parsers/aliexpress.py:73` — `AliExpressParser` overrides it:
  `sender_domains = ALIEXPRESS_SENDER_DOMAINS`.
- `shipping_tracker/main.py:34–38` — `_get_all_sender_domains()` iterates
  `PARSERS` and extends from each `parser.sender_domains`, with deduplication.
  The old `os.getenv("GMAIL_SENDER_LIST")` call is absent from the entire file.
- `shipping_tracker/main.py:57` — `senders = _get_all_sender_domains()` is the
  only source for the Gmail `senders` argument.
- `tests/test_aliexpress_parser.py:228–253` —
  `test_get_all_sender_domains_aggregates_across_parsers` proves appending a
  `SecondParser` with `sender_domains = ("@fakesecond.example.com",)` causes
  that domain to appear in the aggregated list alongside the AliExpress domains.

---

## Accepted Risks Log

| Threat ID | Category | Accepted risk | Rationale |
|-----------|----------|---------------|-----------|
| T-03-SC | Tampering (package installs) | No packages installed in Phase 3 (stdlib-only additions). No supply-chain install task to gate. | Accepted at plan time across all three PLAN.md files (03-01, 03-02, 03-03). The RESEARCH.md Package Legitimacy Audit section for Phase 3 is intentionally empty — confirmed by zero `pip install` calls in any Phase 3 execution artifact. |

---

## Unregistered Flags

None. The SUMMARY.md `## Threat Flags` sections for all three plans report no
new network endpoints, auth paths, or schema changes. All threat flags map to
existing threat IDs in the register.

---

## Review Fixes Verified

The following post-execution code-review fixes (03-REVIEW-FIX.md) touched
security-relevant code and were re-verified above:

| Fix ID | Relevant Threats | Verification outcome |
|--------|-----------------|----------------------|
| CR-01 (trailing boundary `(?![A-Z0-9])` in `_LABEL_RE`) | T-03-04, T-03-05 | CLOSED — boundary present at `aliexpress.py:34`; `_LABEL_RE` still uses only bounded quantifiers |
| CR-02 (`sender_domains` field + PARSERS-iterating `_get_all_sender_domains()`) | T-03-10 | CLOSED — field at `base.py:30`, override at `aliexpress.py:73`, loop at `main.py:34–38` |
| WR-01 (tightened `_SHAPE_RE` fifth alternative with length gate) | T-03-04, T-03-05 | CLOSED — look-ahead gate at `aliexpress.py:56`; letter assertion at `aliexpress.py:57`; all quantifiers bounded |
| WR-04 (per-email `try/except` in dispatch loop) | T-03-08, T-03-09 | CLOSED — exception block at `main.py:89–92`; only `email.message_id` passed to the error log |
