# Phase 2: Gmail - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-31
**Phase:** 2-gmail
**Areas discussed:** Sender matching, Inbox handling + permission, Scan scope, Headless first-run auth

---

## Sender matching strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Sender list → Gmail query | Configurable sender domains/addresses matched server-side via Gmail search (is:unread from:(...)) | ✓ |
| Manual Gmail label | User applies a label; tool reads only that label — precise but manual per email | |
| Subject/body keyword heuristics | Match on phrases like "your order has shipped" — fragile, locale-dependent | |

**User's choice:** Sender list → Gmail query
**Notes:** Transparent and extensible for Phase 2 sellers; no manual work per email. Physical location of the list (config value vs. parser-derived) left to the planner.

---

## Inbox handling + permission (OAuth scope)

| Option | Description | Selected |
|--------|-------------|----------|
| Read-only, dedup via DB | gmail.readonly scope; never modify inbox; "processed" tracked in SQLite (Phase 4) | ✓ |
| Apply a "Tracked" label | gmail.modify; visible Gmail marker, grants write access | |
| Mark as read | gmail.modify; consumes unread state as processed signal | |

**User's choice:** Read-only, dedup via DB
**Notes:** Least-privilege / most privacy-respecting, fits the non-negotiable privacy constraint. Phase 2 is stateless re "seen"; returns matching unread emails each run, DB dedup prevents reprocessing.

---

## Scan scope

| Option | Description | Selected |
|--------|-------------|----------|
| Configurable window, default 30 days | Unread + sender-matched, Inbox, lookback window set in .env | ✓ |
| All unread matching, no time limit | Simplest, but large/old backlog could be slow and register stale parcels | |
| Recent window, all mail (read + unread) | Broader, but with read-only + DB dedup would re-examine handled mail | |

**User's choice:** Configurable window, default 30 days
**Notes:** Bounds first-run query; window adjustable via .env without code changes.

---

## Headless first-run auth

| Option | Description | Selected |
|--------|-------------|----------|
| Auth on laptop, copy token to Pi | Browser OAuth flow once on laptop, copy token.json to Pi | ✓ |
| Console / out-of-band flow on the Pi | Pi prints URL, user pastes code back — no file copy, clunkier | |
| Local-server flow on the Pi (SSH tunnel) | Tunnel callback port over SSH — more setup | |

**User's choice:** Auth on laptop, copy token to Pi
**Notes:** Standard headless Google pattern; Pi never needs a browser. README (Phase 6) documents the steps.

## Claude's Discretion

- Exact Gmail query string + pagination
- Sender list as standalone config vs. parser-declared sender domains
- Gmail client structure/typing for mypy --strict
- Shape of the returned raw email object (must carry message_id, sender, raw body)

## Deferred Ideas

- Marking emails read / applying a Gmail label (rejected — needs gmail.modify write scope)
- Auto-discovering shipping senders (out of scope; v1 uses an explicit configured list)
