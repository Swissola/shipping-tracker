# Phase 5: Pipeline - Context

**Gathered:** 2026-06-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Integrate the real TrackingMore API and complete the end-to-end run. Build a
`TrackingMoreRegistrar` that calls `POST https://api.trackingmore.com/v4/trackings/create`,
drop it into the Phase 4 registrar seam (replace `NullRegistrar` at
`shipping_tracker/main.py:73`), validate `TRACKINGMORE_API_KEY`, and map
TrackingMore's responses onto the success/duplicate/failure semantics already
locked by Phase 4 — so Gmail fetch → parse → deduplicate → register runs for real.

Covers TRACK-01 (create via `/v4/trackings/create`), TRACK-02 (key from
`TRACKINGMORE_API_KEY` env only), TRACK-03 (already-exists handled as success),
TRACK-04 (responses logged; rate-limit/quota/network errors don't crash),
TRACK-05 (courier auto-detected; carrier passed only as optional `courier_code` hint).

**In scope:** the `TrackingMoreRegistrar` (real HTTP client behind the locked
`Registrar` Protocol), API-key startup validation, request-payload construction
(tracking_number always; courier_code conditionally), response → success/
already-exists/quota/transient-error mapping, the run short-circuit on quota,
one in-run retry on transient failure, PII-safe tiered logging of outcomes,
wiring the real registrar into `main()`, and full mocked-transport test coverage.

**Out of scope:** status polling and populating `last_status` / `last_status_at`
(Phase 5.1), push notifications (Phase 5.1), structured JSON logging formalization
and cron-silence hardening (Phase 6 — Phase 5 just follows the PII-safe pattern),
a second tracking provider / `provider` column (PROV-01, v2), proactive
monthly-quota counting (deferred — reactive handling only).

</domain>

<decisions>
## Implementation Decisions

### Quota & rate-limit run behavior (TRACK-04)
- **D-01:** On the **first** quota-exhausted or rate-limit (HTTP 429) response,
  **short-circuit** further create calls for the rest of the run — every remaining
  create would fail identically. Emit **one** WARNING summary line. Unregistered
  numbers stay unwritten and auto-retry next cron via the Phase 4 DEDUP-05 path.
  Rejected: keep-trying-every-number (burns N pointless API calls + N error lines
  once quota is gone).
- **D-06 (signal mechanism):** The registrar signals quota exhaustion by **raising
  a dedicated typed exception** (e.g. `QuotaExceededError`). `register_and_persist`
  propagates it; `main()`'s dispatch loop catches it **specifically and breaks**.
  The normal path keeps the clean `bool` return; ordinary failures still return
  `False`/raise generic exceptions. This adds an exception type **alongside** the
  Phase 4 `Registrar` Protocol without widening its `bool` contract (Phase 4 D-08
  explicitly left "return-value vs typed exception" to the planner).
  **CRITICAL wiring note:** the `except QuotaExceededError: ... break` clause MUST
  sit **before** the loop's existing broad `except Exception` (WR-04, `main.py:135`),
  or the broad catch will swallow it and the loop will continue instead of stopping.

### Transient error & timeout policy (TRACK-04)
- **D-02:** On a **transient** single-call failure — network timeout, connection
  reset, or a 5xx from TrackingMore — perform **one quick in-run retry** after a
  short fixed pause (~2s), then give up: log PII-safely, don't persist, continue.
  The DEDUP-05 retry re-attempts unwritten numbers next cron. A quota/429 is **NOT**
  a transient error — it short-circuits (D-01) and is **never** retried. Rejected:
  no-retry-at-all (misses one-off blips) and bounded-exponential-backoff (risks a
  long-running cron job when the next run would recover anyway).
- **D-03:** **10s** per-request HTTP timeout (connect + read). Generous for a slow
  home connection / cold API, short enough that a hung socket never stalls the cron
  job. With the one retry, a dead endpoint costs ~22s then defers. Rejected: 30s
  (slower to fail) and 5s (may abandon a slow-but-alive response).

### Testing strategy (synthetic-only, quota-safe)
- **D-04:** **All automated tests use a mocked/injectable HTTP transport** returning
  synthetic responses for every path (success, already-exists, 429/quota, 5xx,
  timeout). **Zero live calls** — no test ever hits the real API or consumes the
  50/month free quota; CI needs no secret. Consistent with Phase 4's
  injectable-registrar testing and the project's synthetic-fixture rule. This
  REQUIRES the registrar to accept an **injectable HTTP transport / client seam**
  (constructor-injected) so tests feed fakes. Rejected: opt-in live smoke test and
  record-real-fixtures-once (both touch the real API / quota).

### API-key validation (TRACK-02 / success-criterion 1)
- **D-05:** **Fail-fast at startup.** Validate `TRACKINGMORE_API_KEY` in `main()`
  immediately after `load_dotenv()` — **before** the Gmail fetch and DB open. If
  missing/empty, log **one PII-safe error** (never the key value) and **return
  exit code 1**. "Refuses to start" literally; cron sees a clear non-zero exit; no
  wasted Gmail/DB work. Rejected: lazy (a no-new-trackings run would "succeed" with
  no key) and exit-0-warn (contradicts "refuses to start"; could silently mask a
  misconfigured Pi).

### Outcome logging (PII-safe, sets the Phase 6 pattern)
- **D-07:** **Quiet-by-default, tiered.** All lines PII-safe (LOG-02): only
  `message_id` + structural fields, never tracking_number / carrier / sender / body.
  - `created` → **INFO** (one line, message_id)
  - `already-exists` (TRACK-03) → **INFO/DEBUG**, treated as success
  - transient error → **ERROR** (message_id + exception *type*, per existing WR-04)
  - quota short-circuit → **one WARNING** summary (D-01)
  Healthy runs stay near-silent (aligns with the LOG-03 cron-silence goal Phase 6
  formalizes); only real problems surface at WARNING+. Rejected: verbose
  (log-every-response — noisier, more to trim in Phase 6) and minimal
  (errors-only — can't confirm a healthy registration from logs).

### courier_code hint (TRACK-05)
- **D-08:** Build the create payload with `tracking_number` always present; include
  `courier_code` **only when carrier is non-None/non-empty** — **omit the key
  entirely otherwise**. Lets TrackingMore auto-detect (the locked behavior), avoids
  sending an explicit `null` some APIs reject, and is future-proof for parsers that
  do supply a carrier. `AliExpressParser` returns `carrier=None` today, so in
  practice the field is omitted now — but the seam already carries the param, so it
  is wired through, not dropped. Registration never depends on it. Rejected:
  always-send-null and drop-courier_code-entirely-for-now.

### Claude's Discretion (planner / researcher)
- **HTTP library** — httpx vs requests (brief allows either). Planner's call; httpx
  fits the stated stack and supports clean timeout + injectable-transport testing.
- **Exact already-exists detection (TRACK-03)** — the precise TrackingMore v4
  response field/code that means "tracking already exists" (vs created vs quota vs
  rate-limit) is **research** (read the live API docs) — see canonical refs. The
  *policy* (already-exists = success → persist) is locked; the *detection* is not.
- **Exact `QuotaExceededError` type/placement** — module home (registrar.py likely)
  and whether it subclasses a project base exception. Semantics locked by D-06.
- **Injectable-transport shape** (D-04) — constructor-injected `httpx.Client`,
  base-URL override, or a callable transport — planner's choice as long as tests
  inject fakes with no live calls.
- **TrackingMore `.env` notes** — whether to expand the existing
  `TRACKINGMORE_API_KEY` comment in `.env.example` (the var already exists).
- **Retry pause exactness** (~2s) and whether the create request uses a separate
  connect/read split within the 10s budget.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & scope
- `.planning/REQUIREMENTS.md` §Tracking Provider Integration (TrackingMore) —
  TRACK-01..05 acceptance criteria (create endpoint, key from env only,
  already-exists graceful, rate-limit/quota handled, carrier auto-detected/optional)
- `.planning/ROADMAP.md` §Phase 5: Pipeline — goal + the five success criteria
  (note criterion 2 names the exact endpoint `POST .../v4/trackings/create` and
  "written only after a confirmed success response")
- `.planning/PROJECT.md` §Key Decisions — "Tracking provider: TrackingMore"
  (50 new trackings/month free, quota on creation only, courier auto-detected,
  duplicate handled gracefully); "Carrier is auto-detected, not required"; "Write
  `registered_tracking` only on API success"

### External API (RESEARCH REQUIRED — not yet in repo)
- **TrackingMore v4 API docs — `POST /v4/trackings/create`.** Researcher MUST pull
  the live request schema (auth header for `TRACKINGMORE_API_KEY`, body fields incl.
  `tracking_number` / `courier_code`) AND the response shapes so D-04's synthetic
  fixtures are accurate: the success code, the **already-exists** code (TRACK-03),
  and the **quota-exhausted / rate-limit (429)** codes (D-01/D-06). These exact
  codes are the crux of the response→outcome mapping and are NOT yet documented in
  this repo.

### Carry-forward decisions (upstream phases) — the locked seam Phase 5 fills
- `.planning/phases/04-deduplication/04-CONTEXT.md` §Implementation Decisions —
  D-08 (register-then-persist orchestration behind the injectable registrar; the
  contract semantics: success incl. already-exists → persist; any failure → don't
  persist, log, continue; "return-value vs typed exception" left to planner = D-06
  here), D-01/D-05 (atomic two-row write only on success; one connection per run),
  D-03 (DEDUP-04 already-registered email gets marked processed)
- `.planning/phases/03-parser-layer/03-CONTEXT.md` §Implementation Decisions —
  D-04 (`TrackingInfo.carrier` optional, `AliExpressParser` returns `None` — basis
  for D-08 here)

### Privacy (non-negotiable)
- `./CLAUDE.md` §Constraints — no PII in source / tests / logs / history; synthetic
  fixtures only. Registrar logs and exception messages carry only `message_id` +
  structural fields; the API key value is never logged (D-05); tests use `FAKE`-
  prefixed synthetic tracking numbers and a mocked transport (D-04).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `shipping_tracker/registrar.py` — the locked `Registrar` Protocol
  (`__call__(tracking_number: str, carrier: str | None) -> bool`) and the
  `NullRegistrar` placeholder. Phase 5 adds `TrackingMoreRegistrar` implementing
  this Protocol and (likely) defines `QuotaExceededError` here. The module docstring
  already states implementations MUST NOT embed tracking_number/carrier/email
  content in exception messages (LOG-02) — D-06's exception must honor that.
- `shipping_tracker/main.py` — `main()` orchestrator. Phase 5 touchpoints:
  (a) add the D-05 API-key check right after `load_dotenv()`/`configure_logging()`,
  before the DB open; (b) replace `registrar: Registrar = NullRegistrar()`
  (`main.py:73`) with the real `TrackingMoreRegistrar`; (c) add `except
  QuotaExceededError: <warn summary>; break` to the dispatch loop **before** the
  broad `except Exception` at `main.py:135` (D-06). `register_and_persist` is called
  at `main.py:129` — it already returns `bool` and persists atomically.
- `shipping_tracker/db.py` — `register_and_persist(conn, message_id,
  tracking_number, registrar)` is the orchestration; it must let
  `QuotaExceededError` propagate (not swallow it) so `main()` can break.
- `shipping_tracker/parsers/base.py` — `TrackingInfo(tracking_number, carrier)`;
  `carrier` feeds the optional `courier_code` hint (D-08).
- `shipping_tracker/logging_config.py` — JSON logging (default WARNING; debug/info
  available). Tiered outcome logging (D-07) uses these levels.
- `tests/conftest.py` + `tests/fixtures/` — synthetic-fixture pattern (`FAKE` prefix,
  privacy docstring) and the in-memory `sqlite3` connection fixture from Phase 4.
  Phase 5 tests add a mocked HTTP transport + synthetic TrackingMore responses (D-04).
- `.env.example` — `TRACKINGMORE_API_KEY=your_api_key_here` already present (D-05
  reads this var; key absent = exit 1).

### Established Patterns
- **The injectable registrar seam is the whole point of Phase 4's design** — Phase 5
  is a near-drop-in replacement of `NullRegistrar`; dedup logic in `db.py`/`main.py`
  does not change except for the D-06 quota break and the D-05 startup check.
- mypy `--strict` from day 1 — `TrackingMoreRegistrar`, the transport seam, and
  `QuotaExceededError` fully typed.
- PII-safe logging (LOG-02) and the WR-04 per-email try/except (log `message_id` +
  `type(exc).__name__`, never the body/traceback) — the registrar's error path and
  exception messages follow this exactly.
- `.env`-driven config via `python-dotenv` (`load_dotenv()` already first in
  `main()`).

### Integration Points
- Input: `TrackingInfo` results + `RawEmail.message_id` from the existing dispatch
  loop; `is_tracking_registered` / DEDUP-04 already gate the call.
- Seam filled: `TrackingMoreRegistrar` into the Phase 4 registrar callable.
- Downstream: Phase 5.1 writes `last_status` / `last_status_at` into the
  `registered_tracking` rows this phase creates; Phase 6 formalizes JSON logging
  and cron-silence around the D-07 pattern.

</code_context>

<specifics>
## Specific Ideas

- Response→outcome mapping is the heart of the registrar: created → persist (True);
  already-exists → persist (True, TRACK-03); quota/429 → raise `QuotaExceededError`
  (short-circuit, D-01/D-06); transient (timeout/5xx) → one ~2s retry then
  return False/raise generic (D-02); other 4xx → log + don't persist + continue.
- Tests MUST cover, via the mocked transport over an in-memory DB: success→both
  rows written; already-exists→both rows written + treated as success; quota→
  `QuotaExceededError`→loop breaks→remaining numbers unwritten (retry-next-run
  proof); transient→one retry then unwritten (DEDUP-05 retry proof); missing key→
  `main()` returns 1 before any Gmail/DB work.
- 10s timeout, one ~2s in-run retry on transient only, never on quota/429.
- API key absent → exit 1, logged PII-safely (no key value), before Gmail/DB.

</specifics>

<deferred>
## Deferred Ideas

- **Proactive monthly-quota counting** — tracking how many of the 50/month
  registrations have been used and stopping before hitting the limit. Phase 5 is
  **reactive only** (handle the quota-error response, D-01). Revisit only if the
  reactive short-circuit proves insufficient in practice.
- **Opt-in live smoke test** — a manually-run, env-gated test that registers one
  real tracking number to prove the wire end-to-end. Rejected for Phase 5 (D-04:
  zero live calls, protect quota); could be a one-off manual verification a human
  runs outside the test suite if ever desired.
- **Bounded exponential-backoff retry** — considered for D-02 and rejected (cron
  re-run recovers anyway); revisit only if transient failures prove frequent within
  a single run.
- **`provider` column / second tracking provider (PROV-01)** — v2-deferred
  (carried from Phase 4); TrackingMore covers the cross-border couriers AliExpress
  uses.
- **`.env.example` expansion** for a richer TrackingMore comment — minor; planner's
  discretion since the var already exists.

</deferred>

---

*Phase: 5-Pipeline*
*Context gathered: 2026-06-01*
