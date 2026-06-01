# Phase 3: Parser Layer - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-01
**Phase:** 3-Parser Layer
**Areas discussed:** Parser matching (can_parse), Tracking-number extraction, Multi-number handling, Carrier field shape, Match-but-no-tracking handling

---

## Parser matching — how a parser claims an email

| Option | Description | Selected |
|--------|-------------|----------|
| Sender domain, per-parser | Each parser declares its own AliExpress sender domain(s); `can_parse()` matches on the bare sender. Same list feeds the Gmail query (resolves Phase 2 D-02). New seller = one self-contained file. | ✓ |
| Sender domain + body marker | Match sender AND require an AliExpress-specific body phrase. More robust to shared/spoofed domains, more brittle to template wording. | |
| Body markers only | Ignore sender; match purely on body content. Most flexible but fragile and locale-dependent. | |

**User's choice:** Sender domain, declared per-parser.
**Notes:** Directly resolves the open Phase 2 D-02 thread — the per-parser sender list is the single source for both `can_parse()` and the Gmail `from:()` query. Integration with Phase 2's `GMAIL_SENDER_LIST` left to the planner.

---

## Tracking-number extraction

| Option | Description | Selected |
|--------|-------------|----------|
| Label-anchored, pattern fallback | Find a known label ("Tracking number:", "Logistics No.", "Tracking No.") and capture the adjacent token; fall back to a constrained shape pattern if no label. | ✓ |
| Label-anchored only | Extract only when a known label is present; otherwise treat as no-tracking. Safest vs false positives, misses unlabeled numbers. | |
| Shape pattern only | Match the number's format directly without labels. Robust to label/locale changes, higher risk of grabbing order refs. | |

**User's choice:** Label-anchored with a constrained shape-pattern fallback.
**Notes:** Researcher to confirm the real AliExpress label set and the fallback pattern.

---

## Multi-number handling

| Option | Description | Selected |
|--------|-------------|----------|
| First match wins, defer rest | Extract the first number; keep `extract() -> TrackingInfo`; log extra candidates seen-but-skipped; defer multi-parcel splitting. | ✓ |
| Return all (list contract) | Change `extract()` to return `list[TrackingInfo]`; ripples into Phase 4/5. | |
| You decide (research first) | Let researcher check real AliExpress formats and pick. | |

**User's choice:** First match wins for v1.
**Notes:** Multi-parcel-per-email splitting recorded as a deferred idea.

---

## Carrier field shape

| Option | Description | Selected |
|--------|-------------|----------|
| Optional[str], default None | `TrackingInfo.carrier` becomes `str | None`; set only when confidently found; downstream optional hint. Edits Phase 1 dataclass. | ✓ |
| Keep required str, '' when unknown | Leave type as `str`, empty string for unknown. No dataclass change, conflates unknown/empty. | |
| Drop carrier from parser | Parser returns only the tracking number; carrier left to TrackingMore. Throws away a real hint. | |

**User's choice:** `carrier: str | None = None`.
**Notes:** Direct consequence of the 17track→TrackingMore replan (carrier auto-detected, best-effort). Deliberate edit to `shipping_tracker/parsers/base.py`.

---

## Match-but-no-tracking handling

| Option | Description | Selected |
|--------|-------------|----------|
| Quiet skip, debug-level, continue | Treat no-tracking as expected (pre-shipment emails are routine); debug log (message_id only), skip, continue run. | ✓ |
| Skip with WARNING, continue | Same skip but at WARNING level; noisier — every order-confirmation email warns. | |
| You decide the mechanism | Lock behavior (non-fatal, message_id-only logging); planner picks return-None vs raise-ValueError and exact level. | |

**User's choice:** Quiet skip at debug level, run continues.
**Notes:** Because `can_parse` matches by sender alone, routine "order confirmed" emails are claimed then skipped — debug level avoids warning-spam. Mechanism (return `None` vs raise `ValueError`) left to the planner.

---

## Claude's Discretion

- Mechanism for the no-tracking skip (`extract()` returns `None` vs raises `ValueError`) and exact log level details — planner.
- Wiring of the per-parser sender list into Phase 2's `GMAIL_SENDER_LIST` — planner (may touch Phase 2 code).
- Parser registry location (`main.py` list vs dedicated registry module) — planner.
- Exact label strings and fallback shape pattern — researcher (verify against real AliExpress formats).

## Deferred Ideas

- Multi-parcel-per-email splitting (`extract()` → `list[TrackingInfo]`) — future phase.
- Carried from Phase 2 (still out of scope): auto-discovering shipping senders; marking emails read / applying Gmail labels.
