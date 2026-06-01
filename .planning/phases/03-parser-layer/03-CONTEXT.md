# Phase 3: Parser Layer - Context

**Gathered:** 2026-06-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Turn a `RawEmail` (sender + plain-text body, produced by Phase 2) into a `TrackingInfo`
for AliExpress shipping notification emails, dispatched through the pluggable `BaseParser`
architecture so that adding a future seller is a drop-in operation. Covers PARSE-01
(BaseParser interface — already satisfied by the Phase 1 scaffold), PARSE-02 (AliExpressParser
extracts the tracking number; carrier best-effort), and PARSE-03 (first-match-wins parser
registry; unmatched emails logged and skipped without error).

In scope: `AliExpressParser` (`can_parse` + `extract`), the tracking-number extraction logic,
the parser registry / dispatch loop, making `TrackingInfo.carrier` optional, synthetic-fixture
test coverage.
Out of scope: dedup/state (Phase 4), TrackingMore registration (Phase 5), status
monitoring/notifications (Phase 5.1), any seller other than AliExpress.

</domain>

<decisions>
## Implementation Decisions

### Parser matching — how a parser claims an email (PARSE-03)
- **D-01:** `AliExpressParser.can_parse()` matches on **sender domain**, with each parser
  declaring its own AliExpress sender domain(s) as a parser-owned constant. This resolves the
  open Phase 2 thread (02-CONTEXT D-02): the *same* per-parser sender list is the source for
  both `can_parse()` matching and the Gmail query's `from:()` clause. Net effect — adding a new
  seller is a single self-contained parser file, with no central sender-list edit. Rejected:
  body-marker-only matching (fragile, locale-dependent) and sender+body-marker (unnecessary
  brittleness for v1's single trusted sender).

### Tracking-number extraction (PARSE-02)
- **D-02:** Extraction is **label-anchored with a constrained shape-pattern fallback**.
  Primary path: locate a known label ("Tracking number:", "Logistics No.", "Tracking No.",
  and any AliExpress variants the researcher confirms) and capture the adjacent token.
  Fallback: a constrained shape pattern when no recognized label is present. This disambiguates
  the tracking number from order references while staying resilient to label wording changes.
- **D-03:** **First match wins** for v1 when an email contains more than one candidate
  tracking number. `extract()` keeps its single-`TrackingInfo` return contract. Extra
  candidates that are seen but not processed are logged (message_id only, PII-safe).
  Multi-parcel-per-email splitting is explicitly deferred (see Deferred Ideas).

### Carrier field — best-effort, driven by the TrackingMore replan (PARSE-02 / TRACK-05)
- **D-04:** Change `TrackingInfo.carrier` from a required `str` to **`str | None` (default
  `None`)**. The parser populates it only when the email clearly names a courier; otherwise
  `None`. This is a deliberate edit to the Phase 1 `shipping_tracker/parsers/base.py` dataclass.
  Rationale: TrackingMore auto-detects the courier from the tracking number, so carrier is a
  best-effort hint that must never block registration. Rejected: empty-string sentinel
  (conflates "unknown" with "empty") and dropping carrier entirely (throws away a real hint
  when the email does state the courier).

### Match-but-no-tracking handling (PARSE-03 boundary)
- **D-05:** When a parser claims an email (sender matches) but no tracking number can be
  extracted — which happens **routinely** for pre-shipment AliExpress emails ("order
  confirmed") because matching is sender-based — this is treated as an **expected, non-fatal**
  outcome. Log at **debug** level (message_id only), skip the email, and continue the run; one
  unparseable email never crashes the run. Debug (not warning) is chosen specifically to avoid
  warning-spam on every routine order-confirmation email. Note this is distinct from PARSE-03's
  "no parser matched at all" skip. Phase 4 dedup tolerates re-seeing these unshipped emails on
  later runs until a real shipping email arrives.

### Claude's Discretion (planner / researcher)
- **Mechanism for the no-tracking skip** (D-05): `extract()` returning `None` vs. raising
  `ValueError` caught by the dispatch loop — planner's choice, as long as the run always
  continues and logging stays at debug with message_id only. (Note: current `base.py` docstring
  says `extract()` raises `ValueError` on match-but-fail; the planner may revise this contract.)
- **Integration of the per-parser sender list with Phase 2** (D-01): how the parser-owned
  sender domains feed Phase 2's existing `GMAIL_SENDER_LIST` env path — may touch Phase 2 code.
  Planner to decide the cleanest wiring.
- **Parser registry location** — `main.py` list vs. a dedicated registry module — planner.
- **Exact label strings and the fallback shape pattern** — researcher to verify against real
  AliExpress shipping-email formats (synthetic fixtures must mirror the real structure without
  real data).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & scope
- `.planning/REQUIREMENTS.md` §Parser Layer — PARSE-01 / PARSE-02 / PARSE-03 acceptance criteria
- `.planning/ROADMAP.md` §Phase 3: Parser Layer — goal + success criteria
- `.planning/PROJECT.md` §Key Decisions — carrier-auto-detected / carrier-optional decision
  (TrackingMore replan, locked 2026-05-31)

### Carry-forward decisions
- `.planning/phases/02-gmail/02-CONTEXT.md` §Implementation Decisions — D-02 (sender-list vs
  parser-derived; resolved here as D-01) and the `RawEmail` shape Phase 3 consumes

### Privacy (non-negotiable)
- `./CLAUDE.md` §Constraints — no PII in source/tests/logs/history; synthetic fixtures only
  (tracking numbers count as sensitive — `FAKE`-prefixed test data only)
- `.planning/phases/01-scaffold/01-SECURITY.md` — established secret/PII-handling boundaries

No external (third-party) specs — AliExpress email formats are a research concern and belong
in RESEARCH.md, not here.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `shipping_tracker/parsers/base.py` — `BaseParser` ABC (`can_parse(email_body, sender)`,
  `extract(email_body) -> TrackingInfo`) and the `TrackingInfo` dataclass already exist from
  Phase 1. PARSE-01 is essentially already satisfied; D-04 edits the `carrier` field here.
- `shipping_tracker/gmail/client.py` — `RawEmail(message_id, sender, body)` is the parser's
  input. `body` is the decoded plain-text used by `extract()`; `sender` is the bare address
  used by `can_parse()`.
- `shipping_tracker/main.py` — pipeline orchestrator; the parser registry + dispatch loop wire
  in here, between the Phase 2 Gmail fetch and the (future) Phase 4 dedup step.
- `tests/conftest.py` + `tests/fixtures/` — synthetic-fixture pattern (`FAKE…` prefix, privacy
  docstring) to extend with a synthetic AliExpress shipping-email body fixture.

### Established Patterns
- mypy `--strict` from first commit — `AliExpressParser` and the revised `TrackingInfo` must be
  fully typed (`carrier: str | None`).
- PII-safe logging (LOG-02): parser log calls use `%`-style stdlib formatting and carry only
  `message_id` / counts — never sender, body, or the tracking number itself.
- `FAKE`-prefixed synthetic test data only; no real tracking numbers, addresses, or order refs.

### Integration Points
- Input: `list[RawEmail]` from `fetch_unread_shipping_emails()` (Phase 2).
- Output: `TrackingInfo` per shipped email, consumed by Phase 4 (dedup) then Phase 5
  (TrackingMore registration). `message_id` stays the Phase 4 dedup key.
- D-01 couples the parser's declared sender domains back to Phase 2's Gmail query input.

</code_context>

<specifics>
## Specific Ideas

- Known label candidates to anchor extraction on: "Tracking number:", "Logistics No.",
  "Tracking No." (researcher to confirm the real AliExpress set and add variants).
- A parser file should be self-contained: its sender domain(s), `can_parse`, and `extract`
  all live together, so a new seller is one new file appended to the registry.
- Carrier is a hint, never a gate — `None` is a first-class, expected value.

</specifics>

<deferred>
## Deferred Ideas

- **Multi-parcel-per-email splitting** — registering every tracking number when one email lists
  several parcels (would change `extract()` to return `list[TrackingInfo]` and ripple into
  Phase 4/5). Deferred from v1 per D-03; revisit if real AliExpress emails commonly bundle
  multiple parcels. Belongs in its own phase/discussion.
- (Carried from Phase 2, still out of scope: auto-discovering shipping senders; marking emails
  read / applying Gmail labels.)

</deferred>

---

*Phase: 3-Parser Layer*
*Context gathered: 2026-06-01*
