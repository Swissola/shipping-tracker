# Phase 2: Gmail - Context

**Gathered:** 2026-05-31
**Status:** Ready for planning

<domain>
## Phase Boundary

Authenticate to Gmail via OAuth2 and retrieve unread emails that match shipping-sender
patterns, producing a list of raw email objects for the parser layer (Phase 3) to consume.
Covers requirements GMAIL-01 (OAuth2 auth), GMAIL-02 (poll unread matching sender patterns),
GMAIL-03 (token cache persists across runs).

In scope: OAuth2 flow + token persistence, Gmail query/fetch of matching unread emails,
returning raw email objects, synthetic-fixture test coverage.
Out of scope: parsing email contents (Phase 3), dedup/state (Phase 4), provider registration
(Phase 5), status monitoring/notifications (Phase 5.1).

</domain>

<decisions>
## Implementation Decisions

### Sender matching (GMAIL-02)
- **D-01:** Recognize shipping emails by a **configurable sender list** (domains/addresses) compiled into a **server-side Gmail search query** — e.g. `is:unread from:(sender1 OR sender2) newer_than:30d`. Chosen over manual labels (defeats automation) and subject/body keyword heuristics (fragile, locale-dependent).
- **D-02:** The sender list is configuration, not hardcoded. For v1 it covers AliExpress sender domain(s). Where the list physically lives (a dedicated config value vs. derived from registered parsers) is a planner decision — see Claude's Discretion.

### Inbox handling + OAuth scope (GMAIL-01)
- **D-03:** Request the **read-only** Gmail scope (`https://www.googleapis.com/auth/gmail.readonly`). The tool MUST NEVER modify the mailbox — no mark-as-read, no labelling, no deletion. This is the least-privilege / most privacy-respecting choice and aligns with the non-negotiable privacy constraint.
- **D-04:** Because the tool does not mark emails read or labelled, "already processed" is NOT tracked in Gmail. It is tracked in SQLite (Phase 4, `processed_emails` by `message_id`). Phase 2 therefore returns matching unread emails on every run; downstream dedup prevents reprocessing. Phase 2 itself is stateless with respect to "seen" status.

### Scan scope (GMAIL-02)
- **D-05:** Each scan covers **unread, sender-matched emails in the Inbox within a configurable lookback window, default 30 days** (`newer_than:30d` style). The window is set via `.env` so it can be widened/narrowed without code changes. Read state = unread only (per GMAIL-02). Bounds the first-run query so a large/old mailbox is not scanned wholesale.

### First-run authentication (GMAIL-03)
- **D-06:** The one-time interactive OAuth consent is performed **on the user's laptop** (local browser flow); the resulting `token.json` is **copied to the Pi**. The Pi never needs a browser. After the token exists, runs are non-interactive and the cached token auto-refreshes. The README (Phase 6) will document the laptop-auth → copy-token → cron steps.
- **D-07:** `credentials.json` (OAuth client secrets) and `token.json` (token cache) are both secrets — already excluded from git via the Phase 1 `.gitignore`. Confirm both remain ignored; neither may appear in source, tests, logs, or history.

### Claude's Discretion
- Exact Gmail query string construction and pagination handling (researcher/planner).
- Whether the sender list is a standalone config value or each `BaseParser` declares its own sender domains (the parser's `can_parse(email_body, sender)` already takes a sender). The parser-derived approach is architecturally cleaner for Phase 3+ and worth the planner's consideration; a simple config list is acceptable for v1 AliExpress-only.
- Library choice details within the locked stack (`google-api-python-client`, `google-auth-oauthlib`) and how the Gmail service client is structured/typed for mypy --strict.
- Shape of the returned "raw email object" (dict vs. small typed dataclass) — should carry at minimum `message_id`, `sender`, and the raw body needed by Phase 3.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & scope
- `.planning/REQUIREMENTS.md` §Gmail Integration — GMAIL-01/02/03 acceptance criteria
- `.planning/ROADMAP.md` §Phase 2: Gmail — goal + success criteria
- `.planning/PROJECT.md` §Key Decisions / §Constraints — Gmail-via-OAuth2 decision, privacy constraint, tech stack lock

### Privacy (non-negotiable)
- `./CLAUDE.md` §Constraints — no PII in source/tests/logs/history; synthetic fixtures only
- `.planning/phases/01-scaffold/01-SECURITY.md` — established secret-handling boundaries (`.env`, `token.json`, `credentials.json` git-ignored)

No external (third-party) specs — Google Gmail API docs are the implementation reference and belong in RESEARCH.md, not here.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `shipping_tracker/main.py` — pipeline orchestrator stub; the Gmail fetch is the first real step wired in here (after `load_dotenv()` / `configure_logging()`), without changing `main() -> int`.
- `shipping_tracker/logging_config.py` — structlog file logging already configured; Gmail fetch logging must stay PII-free (no email addresses/subjects/bodies in logs, per LOG-02).
- `shipping_tracker/parsers/base.py` — `BaseParser.can_parse(email_body, sender)` already takes `sender`; relevant to the sender-list-vs-parser-derived decision (D-02).
- `.gitignore` — already excludes `.env`, `token.json`, `credentials.json` (Phase 1 / T-01-01).
- `tests/conftest.py` — synthetic-fixture pattern (`FAKE…`) and privacy docstring to extend for Gmail fixtures.

### Established Patterns
- mypy `--strict` from first commit — the Gmail client and any email object must be fully typed (Google libs have a mypy override block already in `pyproject.toml`).
- Config via `.env` only (python-dotenv); new vars (sender list, lookback window) follow that pattern and get placeholders in `.env.example`.

### Integration Points
- Output (raw email objects) feeds Phase 3 parser dispatch.
- `message_id` on each email object is the key Phase 4 uses for `processed_emails` dedup — Phase 2 must surface it.

</code_context>

<specifics>
## Specific Ideas

- Gmail query shape the user endorsed: `is:unread from:(<senders>) newer_than:<window>`, Inbox only.
- Read-only posture is a hard preference, not a default — the tool must be incapable of altering the mailbox.
- Lookback window default 30 days, `.env`-configurable.

</specifics>

<deferred>
## Deferred Ideas

- **Marking emails read / applying a "Tracked" Gmail label** — deliberately rejected for v1 (would require `gmail.modify` write scope). If ever wanted, it is a scope/permission change and belongs in its own discussion, not Phase 2.
- **Auto-discovering shipping senders** (e.g. learning new sender domains automatically) — out of scope; v1 uses an explicit configured list.

None of the above are in Phase 2 scope; recorded so they are not lost.

</deferred>

---

*Phase: 2-Gmail*
*Context gathered: 2026-05-31*
