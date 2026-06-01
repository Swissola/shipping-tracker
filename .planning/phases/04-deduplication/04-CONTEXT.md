# Phase 4: Deduplication - Context

**Gathered:** 2026-06-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the SQLite state layer that makes the whole pipeline idempotent: an email
is never re-processed, a tracking number is never re-registered, and a *failed*
registration is retried automatically on the next run. Two tables —
`processed_emails` and `registered_tracking` — whose column shapes are locked by
DEDUP-01 / DEDUP-02. Covers DEDUP-01 (create `processed_emails`), DEDUP-02
(create `registered_tracking`), DEDUP-03 (skip already-seen emails), DEDUP-04
(skip already-registered tracking numbers), DEDUP-05 (persist only on confirmed
registration success).

In scope: the `db`/state module (table creation + dedup checks + the
register-then-persist write), the connection lifecycle in `main()`, the
injectable **registrar seam** plus a `NullRegistrar` placeholder, wiring the
dedup checks into the existing `main.py` dispatch loop, and synthetic-fixture
test coverage proving every DEDUP criterion (including a simulated registration
failure → retry).

Out of scope: the real TrackingMore client and the `/trackings/create` call
(Phase 5 — drops a real registrar into the seam), status polling and the
`last_status` / `last_status_at` columns being *populated* (Phase 5.1; the
columns are *created* here as nullable per DEDUP-02), notifications (Phase 5.1),
a second tracking provider (PROV-01, v2).

</domain>

<decisions>
## Implementation Decisions

### Write timing — the idempotency / retry core (DEDUP-03 / DEDUP-04 / DEDUP-05)
- **D-01:** `processed_emails[message_id]` and `registered_tracking[tracking_number]`
  are written **together in a single transaction, only on confirmed registration
  success.** A failure (exception or negative registrar result) writes **neither**
  row, logs PII-safely, and continues — so the email is unseen next run and the
  number retries automatically. This satisfies DEDUP-05 by construction.
- **D-02:** **No-tracking and no-parser-matched emails are left UNMARKED** in
  `processed_emails`. Their body is immutable, so they are cheaply re-parsed
  (local regex, no API) every run until they age out of the Gmail unread/lookback
  window. This honors Phase 3 D-05 ("tolerate re-seeing unshipped emails until a
  real shipping email arrives") and keeps such emails open to re-evaluation if a
  parser is later improved. Rejected: mark-every-dispatched-email-on-sight (would
  let DEDUP-03 skip a tracking email *before* the registration check, breaking the
  DEDUP-05 retry; and would permanently blind an improved parser to an email it
  previously couldn't read).
- **D-03:** In the **DEDUP-04 branch** — a fresh email whose tracking number is
  *already* in `registered_tracking` (e.g. a duplicate notification arriving under
  a new `message_id`) — the API call is skipped **and** this email's `message_id`
  is written to `processed_emails` (mark it done). This eliminates re-parse churn
  for duplicate-notification emails.
- **Consolidated rule (D-01 + D-03):** `processed_emails[message_id]` is written
  whenever this email's tracking number ends up **durably present** in
  `registered_tracking` — whether registered by this run (success, incl. the
  TRACK-03 already-exists case in Phase 5) or already present from a prior run.
  It is **not** written when the email has no tracking number, or when
  registration fails. `processed_emails` therefore means "a tracking number from
  this email is durably registered"; `registered_tracking` is the
  number-level backstop and the source of the DEDUP-04 skip.

### State-layer shape (architecture)
- **D-04:** Expose the state layer as a **module of plain functions** (e.g.
  `shipping_tracker/db.py`): `init_db(conn)`, `is_email_processed(conn, message_id)`,
  `is_tracking_registered(conn, tracking_number)`, and a register-then-persist
  helper. Connection is **passed in explicitly** (idiomatic stdlib `sqlite3`,
  trivially testable with an in-memory connection). Rejected: a `Database`/`StateStore`
  class — only justified if a future deploy swaps the storage backend behind one
  interface (SQLite → Postgres), which is speculative for a single-file cron tool.
- **D-05:** **One connection per run.** `main()` opens a single `sqlite3` connection
  at startup (after `load_dotenv()` / `configure_logging()`), calls `init_db(conn)`
  once, threads the connection through the dispatch loop (and into the registrar
  orchestration), and closes it in a `finally`. Matches the synchronous,
  single-process cron model (Scaffold D-03).
- **D-06:** **Build the schema exactly per DEDUP-01 / DEDUP-02** — no `provider`
  column. PROV-01 (a second provider) is v2-deferred; it adds the column later via
  a one-line `ALTER TABLE` migration. Parser/provider extensibility lives in the
  `PARSERS` registry (Phase 3) and a Phase 5 provider seam — *not* in the
  state-layer API shape, so deferring costs nothing now.

### Database location & configuration
- **D-07:** Read the DB path from **`DATABASE_PATH` in `.env`**; default to
  **`data/shipping-tracker.db`** when unset (a dedicated gitignored `data/` dir at
  repo root, parallel to the existing `logs/` from Scaffold D-06). The parent
  directory is created at startup if missing. Add `DATABASE_PATH` to `.env.example`.
  `*.db` is already in `.gitignore`, so the file is never committed regardless of
  path. Rationale: lets the Pi deploy relocate the DB (e.g. external storage,
  absolute `/home/<user>` path) with no code change; works out-of-the-box for dev.

### Registration seam (makes DEDUP-05 provable in Phase 4)
- **D-08:** Phase 4 **owns the register-then-persist orchestration** behind an
  **injectable registrar callable**. The orchestration: call the registrar; on
  success → write both rows in one transaction (D-01); on failure/exception →
  write neither, log PII-safely (message_id + exception *type* only, per the
  existing WR-04 pattern in `main.py`), and continue. Phase 5 drops the real
  TrackingMore client into this seam with **zero changes** to the dedup logic.
  Tests inject fake success / failure registrars to prove DEDUP-05 and the retry
  path end-to-end — satisfying success-criterion 4 without TrackingMore.
- **D-09:** Ship a **`NullRegistrar`** placeholder for live Phase 4 runs: it
  returns a "deferred / not registered" result logged at **debug** (message_id
  only). A real Phase 4 cron run thus creates the tables (criterion 1), skips
  already-seen emails (criterion 2), finds tracking numbers, and persists nothing
  yet — an honest incomplete-pipeline state with no WARNING-level noise. Rejected:
  raising `NotImplementedError` (an error line per tracking email every run could
  trip alerting); leaving the orchestration unwired from `main()` (ships a
  half-wired loop — the runnable-vertical-slice principle prefers the loop fully
  wired with a null implementation).

### Concurrency, versioning, and key identity
- **D-10:** Set **`PRAGMA busy_timeout = 5000`** (ms) on connect; keep the default
  rollback journal (no WAL `-wal`/`-shm` side-files to manage on the Pi). A brief
  cron overlap (slow run during a Gmail/network stall) then waits rather than
  instantly raising "database is locked". WAL was considered and rejected as more
  than this single-writer workload needs.
- **D-11:** Set **`PRAGMA user_version = 1`** at table creation. Zero cost now;
  gives the eventual PROV-01 migration a clean integer to branch on
  (`if user_version < 2: ALTER TABLE ...`) and avoids special-casing unversioned
  (`user_version = 0`) legacy DBs later.
- **D-12 (settled by fact, not a choice):** The dedup key is the **opaque Gmail API
  message `id`** already carried by `RawEmail.message_id` (`msg["id"]` in
  `gmail/client.py`) — stable across the email's lifetime and **not** the RFC822
  `Message-ID` header, so it carries no PII. `registered_tracking.source_email_id`
  stores this same id.

### Claude's Discretion (planner / researcher)
- **Exact registrar contract signature** (D-08): return-value vs typed exception,
  and how Phase 5's TRACK-03 "duplicate / already-exists" maps to the seam. The
  *semantics* are locked — success **incl. already-exists** → persist; any failure
  → don't persist, log, continue — but the precise callable signature / protocol
  is the planner's choice (design it so Phase 5 can express "already-exists =
  success" cleanly).
- **Module name & helper boundaries** (D-04): `db.py` vs `state.py`, and exactly
  which functions exist / how the register-then-persist helper is factored.
- **Transaction mechanism** (D-01): explicit `BEGIN`/`COMMIT`, `with conn:`
  context-manager transaction, or `conn.commit()` discipline — planner's call, as
  long as the two-row write is atomic and rolls back together on failure.
- **Where the dedup checks sit in `main.py`** — the order of `is_email_processed`
  (DEDUP-03, before parse) and `is_tracking_registered` (DEDUP-04, after parse,
  before registrar) inside the existing dispatch loop.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & scope
- `.planning/REQUIREMENTS.md` §Deduplication — DEDUP-01..05 acceptance criteria
  (the locked table schemas: `processed_emails(message_id PRIMARY KEY, processed_at)`
  and `registered_tracking(tracking_number PRIMARY KEY, registered_at,
  source_email_id, last_status, last_status_at)` — `last_status*` nullable, populated
  in Phase 5.1)
- `.planning/ROADMAP.md` §Phase 4: Deduplication — goal + the four success criteria
- `.planning/PROJECT.md` §Key Decisions — "Write `registered_tracking` only on API
  success"; "SQLite for deduplication state"

### Carry-forward decisions (upstream phases)
- `.planning/phases/03-parser-layer/03-CONTEXT.md` §Implementation Decisions —
  D-03 (dispatch loop collects `list[TrackingInfo]`; single TrackingInfo per email;
  `message_id` is the dedup key) and D-05 (pre-shipment match-but-no-tracking is
  routine; "tolerate re-seeing unshipped emails" — basis for D-02 here)
- `.planning/phases/01-scaffold/01-CONTEXT.md` §Implementation Decisions —
  D-01 (zero-arg cron, all config via `.env`), D-03 (synchronous entry; don't
  block a future async move), D-06 (`logs/` dir + 10MB rotation — `data/` mirrors it)

### Privacy (non-negotiable)
- `./CLAUDE.md` §Constraints — no PII in source / tests / logs / history; synthetic
  fixtures only. The SQLite DB holds real tracking numbers + opaque Gmail ids but is
  gitignored (`*.db`) and never logged; tests use `FAKE`-prefixed synthetic data only.
- `shipping_tracker/main.py` (WR-04 block, lines ~74-100) — the established PII-safe
  per-item error pattern (log `message_id` + `type(exc).__name__`, never the
  traceback/body); the registrar orchestration's failure path follows it.

No external (third-party) specs — TrackingMore API specifics belong to Phase 5.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `shipping_tracker/main.py` — the `main()` orchestrator and the per-email dispatch
  loop (collects `tracking_results: list[TrackingInfo]`). Phase 4 opens the DB
  connection here, calls `init_db` once, and inserts the DEDUP-03 / DEDUP-04 checks
  + registrar orchestration into this loop. The WR-04 try/except per email is the
  PII-safe error template to reuse.
- `shipping_tracker/parsers/base.py` — `TrackingInfo(tracking_number, carrier)` is
  the object handed to the registrar; `tracking_number` is the `registered_tracking`
  PK.
- `shipping_tracker/gmail/client.py` — `RawEmail.message_id` (opaque Gmail `id`) is
  the `processed_emails` PK and `registered_tracking.source_email_id`. `RawEmail`
  already documents "Do not log sender or body".
- `shipping_tracker/logging_config.py` — structlog/stdlib JSON logging (compact,
  default WARNING; debug available) — the `NullRegistrar` logs its "deferred" line
  at debug here.
- `tests/conftest.py` + `tests/fixtures/` — synthetic-fixture pattern (`FAKE`
  prefix, privacy docstring). Phase 4 tests use an in-memory `sqlite3` connection
  and `FAKE`-prefixed tracking numbers / message ids.

### Established Patterns
- mypy `--strict` from day 1 — all new db/registrar code fully typed.
- PII-safe logging (LOG-02): db/registrar logs carry only `message_id` + counts +
  exception *type* — never tracking number, sender, or body.
- `.env`-driven config via `python-dotenv` (`load_dotenv()` already called first in
  `main()`); `DATABASE_PATH` joins `GMAIL_LOOKBACK_DAYS` as a configured value.
- `data/` mirrors the existing `logs/` convention for gitignored runtime state.

### Integration Points
- Input: the `TrackingInfo` results produced by the Phase 3 dispatch loop, plus the
  `RawEmail.message_id` for each email.
- Output / seam: the **injectable registrar** — Phase 5 supplies the real
  TrackingMore client; Phase 5.1 writes `last_status` / `last_status_at` into the
  `registered_tracking` rows created here.
- Connection lifecycle owned by `main()` (open → `init_db` → thread through → close
  in `finally`).

</code_context>

<specifics>
## Specific Ideas

- `data/shipping-tracker.db` as the default DB path (dir mirrors `logs/`); override
  via `DATABASE_PATH` in `.env`; add the var to `.env.example`.
- `NullRegistrar` is the Phase 4 placeholder; the seam is designed so Phase 5's real
  registrar is a literal drop-in replacement.
- Tests must include a **simulated registration failure → unwritten row → retry next
  run** flow (success-criterion 4), driven by a fake failing registrar over an
  in-memory DB — not just a DB-helper unit assertion.
- `PRAGMA busy_timeout = 5000` and `PRAGMA user_version = 1` set on connect/creation.

</specifics>

<deferred>
## Deferred Ideas

- **`provider` column on `registered_tracking`** — forward-compat for PROV-01 (a
  second tracking provider, e.g. Ship24). Explicitly v2-deferred; added later via a
  one-line `ALTER TABLE` gated on `PRAGMA user_version` (D-06 / D-11). Building it
  now would deviate from the locked DEDUP-02 schema.
- **WAL journal mode** — considered for concurrency (D-10) and rejected as more than
  a single-writer cron tool needs; revisit only if real lock contention appears.
- **`StateStore` class / swappable storage backend** — considered for D-04 and
  rejected (YAGNI for single-file SQLite); revisit only if a non-Pi deploy needs a
  different backend.
- (Carried from Phase 3, still out of scope: multi-parcel-per-email splitting —
  would make `extract()` return `list[TrackingInfo]` and ripple into Phase 4/5.)

</deferred>

---

*Phase: 4-Deduplication*
*Context gathered: 2026-06-01*
