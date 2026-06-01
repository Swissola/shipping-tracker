# Building shipping-tracker with GSD — A Step-by-Step Walkthrough

> This document is a teaching narrative. It reconstructs, in order, how this project
> was built using the **GSD** (Get Sh\*t Done) planning workflow, so the process can be
> explained to someone who wasn't in the room. Every step below maps to real artifacts
> in `.planning/` and real commits in git history — nothing here is invented for the story.
>
> Dates are absolute (the work happened on **2026-05-31**). Commit hashes are real and
> can be checked with `git show <hash>`.

---

## What you're looking at

**shipping-tracker** is a Python tool that watches Gmail for shipping-notification emails,
pulls out the tracking number, registers it with a tracking API, and pushes a phone
notification when the parcel moves — all unattended on a Raspberry Pi 5.

But this tutorial isn't really about the parcel tracker. It's about *how it was built*:
one disciplined loop, repeated per phase, leaving a paper trail at every step.

---

## The GSD loop (read this once, then it repeats)

Every phase of this project went through the same four-beat cycle. Once you understand
the loop, the rest of the document is just the loop running again with different content.

| Beat | GSD command | What happens | Artifact left behind |
|------|-------------|--------------|----------------------|
| **1. Discuss** | `/gsd-discuss-phase` | Adaptive Q&A to surface every decision *before* writing code. Options are laid out with trade-offs; the human chooses. | `NN-CONTEXT.md`, `NN-DISCUSSION-LOG.md` |
| **2. Plan** | `/gsd-plan-phase` | Research the unknowns, then break the phase into atomic, independently-committable tasks with explicit success criteria. | `NN-RESEARCH.md`, `NN-PATTERNS.md`, `NN-NN-PLAN.md` |
| **3. Execute** | `/gsd-execute-phase` | Build it. Each task is its own atomic commit. Deviations from the plan are logged, not hidden. | `NN-NN-SUMMARY.md`, real commits |
| **4. Verify** | `/gsd-verify-work` + `/gsd-secure-phase` | Prove the phase goal was actually met (not just that tasks "completed"), and confirm the threat model is closed. | `NN-VERIFICATION.md`, `NN-VALIDATION.md`, `NN-SECURITY.md` |

The key idea: **decisions are made before code, written down, and verified after.**
If you ever wonder "why is it built this way?", the answer is in a `CONTEXT` or
`DISCUSSION-LOG` file, not in a developer's memory.

---

## Step 0 — Project genesis

Before any phase, the project itself had to be defined.

We started from a human-written brief, [`PROJECT-BRIEF.md`](PROJECT-BRIEF.md). That brief
described the original idea: monitor Gmail, extract tracking numbers, register them with
**17track**, run on a Pi via cron, and — critically — **never leak personal data** because
the repo will be open-sourced.

GSD turned that brief into three living documents under `.planning/`:

- **`PROJECT.md`** — the vision, scope, and a running **Key Decisions** table.
- **`REQUIREMENTS.md`** — numbered, checkable requirements (`SETUP-01`, `GMAIL-02`, `TRACK-01`, …).
- **`ROADMAP.md`** — the phase breakdown, in dependency order:

  > scaffold → Gmail → parsers → dedup → pipeline → status monitoring → hardening

The brief is now marked **SUPERSEDED** at the top — it's kept only as the historical
record. The source of truth moved into `.planning/`. (Remember this; it matters in Step 2.)

> **Teaching point:** GSD separates the *original idea* (the brief) from the *living plan*
> (`.planning/`). The brief is allowed to be wrong later — and it was.

---

## Step 1 — Phase 1: Scaffold ("walking skeleton")

**Goal:** a runnable, installable, fully-linted Python package with the pluggable parser
architecture already in place — *before* a single feature is written.

### 1a. Discuss

We ran the discussion beat and made a string of explicit choices, all recorded in
[`01-DISCUSSION-LOG.md`](.planning/phases/01-scaffold/01-DISCUSSION-LOG.md). A few that
shaped everything after:

- **Entry point:** zero-argument, no flags — just runs the pipeline (cron-friendly). Both
  `python -m shipping_tracker` *and* an installed `shipping-tracker` command.
- **HTTP client:** `httpx` (sync for now, but the architecture must not block going async later).
- **Logging:** `structlog` with **compact JSON** and a **rotating file** (10 MB, keep 3) —
  and *no* stdout handler, because a cron job must be silent.
- **Type checking:** `mypy --strict` from day one. The human asked for the full consequences
  first, accepted that Google's patchy type stubs would force a few `cast()`/`type: ignore`
  calls, and chose strict anyway.
- **CI:** GitHub Actions on `ubuntu-latest`, testing a **3.11 / 3.12 / 3.13** matrix
  (anticipating open-source contributors).

> **Teaching point:** notice there's a table for every decision with the options that were
> *rejected*. That's deliberate — the discussion log is an audit trail of alternatives, so
> later "why didn't we just…?" questions already have answers.

### 1b. Plan

Phase 1 was split into **two plans**:

- **Plan 01 — Walking skeleton:** the package, entry points, logging config, and the
  `BaseParser` ABC + `TrackingInfo` dataclass.
- **Plan 02 — Toolchain enforcement:** pre-commit hooks, the GitHub Actions CI workflow,
  and the pytest smoke-test suite.

### 1c. Execute

Each task became an atomic commit:

- Plan 01 → `008ac7f` (manifest/gitignore/env) and `29f6913` (package files).
- Plan 02 → `5acb308` (pre-commit + CI) and `ab64c2e` (tests).

By the end, the skeleton ran (`python -m shipping_tracker` exits 0, prints nothing),
`ruff` + `mypy --strict` were green, and 6 smoke tests passed.

Two important constraints were baked in here and enforced forever after:

1. **Pluggable parsers from day one.** The brief *required* this — a monolithic
   AliExpress-only parser would have blocked later sellers. So `BaseParser` exists before
   any parser does.
2. **Privacy guardrails.** `.env`, `token.json`, `credentials.json`, `*.db`, and `logs/`
   are git-ignored. Test fixtures must use `FAKE`-prefixed synthetic data, and
   `tests/conftest.py` carries a mandatory privacy docstring so future contributors can't
   miss the rule.

> **Teaching point:** the deviations weren't hidden. The summaries record small auto-fixes
> (e.g. shortening a comment to satisfy ruff's 88-char limit) under a "Deviations from Plan"
> heading. GSD treats "what changed and why" as part of the deliverable.

---

## Step 2 — The course correction: dropping 17track for TrackingMore ⚠️

**This is the moment you asked me to make sure I captured.**

After the Phase 1 scaffold was already built, we hit a problem that the original brief had
gotten wrong. The brief assumed the tracking provider would be **17track** — its
`.env.example` even shipped a `SEVENTEEN_TRACK_API_KEY` placeholder, and Phase 5 was
written around 17track's v2 `/register` endpoint.

The issue: **17track has no free recurring API tier.** It only offers a one-time, 100-query
test quota — useless for a tool meant to run unattended on a Pi indefinitely.

So we stopped and **replanned the provider** (decisions locked **2026-05-31**). The switch
was to **TrackingMore**, and it rippled through several documents:

- **Provider swapped:** TrackingMore offers **50 new trackings/month free**, covers the
  cross-border couriers AliExpress actually uses (1,500+ carriers), and fits the existing
  `httpx` + SQLite stack with no new infrastructure. Quota is charged **only on creation** —
  status re-checks are free.
- **`.env` variable renamed:** `SEVENTEEN_TRACK_API_KEY` → `TRACKINGMORE_API_KEY`. The
  security audit (`01-SECURITY.md`, threat **T-01-04**) then confirmed that *both* forms had
  only ever carried the placeholder value `your_api_key_here` — a full git-history scan found
  no real key material had ever been committed.
- **Carrier became optional:** TrackingMore auto-detects the courier from the tracking
  number. That *relaxed* the future parser contract — a parser only has to extract the
  number; `TrackingInfo.carrier` is now best-effort metadata that never blocks registration.
  (New requirement **TRACK-05** captured this.)
- **Status updates via polling, not webhooks:** the Pi sits behind home NAT and can't receive
  inbound webhooks, so the cron run re-fetches status for in-flight parcels and diffs against
  SQLite.
- **A new phase was inserted:** **Phase 5.1 — Status Monitoring & Notifications**, scoping
  the polling + phone-push behavior that the provider replan made possible.

Where to see it in the repo:
- `PROJECT.md` → **Key Decisions** table, three rows locked 2026-05-31 ("Tracking provider:
  TrackingMore (replaces unstated 17track assumption)", carrier auto-detection, polling-not-webhooks).
- `STATE.md` → *Roadmap Evolution*: "Phase 5 edited: provider swap 17track→TrackingMore…"
  and "Phase 05.1 inserted…".
- `PROJECT-BRIEF.md` → the SUPERSEDED banner explaining the change.

> **Teaching point — this is the whole reason GSD's structure pays off.** The wrong
> assumption lived in the *brief* and in *one phase's plan + one env variable* — not smeared
> across thousands of lines of code. Because decisions were written down in one place, the
> correction was a bounded, auditable edit (swap the provider, rename one secret, relax one
> future contract, add one phase) instead of a painful refactor. The scaffold from Step 1
> didn't have to change at all — the parser abstraction it established actually got *easier*
> to satisfy.

---

## Step 3 — Phase 2: Gmail

**Goal:** authenticate to Gmail and fetch unread shipping emails — safely, with zero PII in
logs — proven by tests, without needing real credentials in CI.

### 3a. Plan 01 — Foundation + contracts

- Installed the locked Google stack (`google-api-python-client`, `google-auth-oauthlib`,
  `google-auth`) plus dev type stubs.
- Created the `shipping_tracker/gmail/` package with typed contracts: `load_credentials()`
  (a two-path OAuth flow — silent refresh on the Pi, browser flow on a laptop),
  `build_query()`, a `RawEmail` frozen dataclass, and `build_service()`.
- **Security decision:** the OAuth scope is a hard-coded module constant —
  `gmail.readonly` — and is **never** read from `.env`. The tool can read mail and nothing
  else, by construction. (Threat **T-02-scope**.)
- 8 mypy-strict tests, all synthetic. Commits `236ccd4`, `173a33e`, `2132dc1`.

### 3b. Plan 02 — The fetch loop (built test-first)

This plan was done **TDD-style** — failing tests first (RED), then the implementation (GREEN):

- `fetch_unread_shipping_emails()` paginates `messages.list` via `nextPageToken`, fetches
  each message, walks the MIME tree for the plain-text body, and base64url-decodes it
  (with padding normalisation to avoid `binascii` errors).
- **PII safety proven, not assumed:** a test (`test_fetch_does_not_log_pii`) captures the
  logs and asserts there's no `@` and no body content in them. Log calls only ever carry a
  message ID or a count. (Threat **T-02-logpii**.)
- Rate-limit resilience: `_execute_with_backoff()` retries on HTTP 429/403 with jittered
  exponential backoff. (Threat **T-02-quota**.)
- Commits `541ca77` (RED), `04bf93f` (GREEN), `faa852a` (wire into `main()`).

A nice example of an honest deviation: wiring the real fetch into `main()` meant the tool now
exits **1** (not 0) when `credentials.json` is missing — which broke a Phase 1 smoke test
that expected exit 0. Rather than paper over it, the summary records the fix: `main()` now
catches `FileNotFoundError` and returns 1 *with no stdout* (preserving the cron-silence
invariant), and the obsolete smoke test was removed while the no-stdout test was kept.

### 3c. Verify

Phase 2 was verified: **9/9 automated checks green**, the threat model **6/6 closed**, with
2 items that can only be tested with real OAuth credentials deferred to the Phase 6 README.
See [`02-VERIFICATION.md`](.planning/phases/02-gmail/02-VERIFICATION.md).

---

## Step 4 — Phase 3: Parser Layer

**Goal:** turn an AliExpress shipping email into a `TrackingInfo` (tracking number +
best-effort carrier) through a *pluggable* `BaseParser`, so adding a future seller is a
drop-in — one new file, no edits to the core pipeline.

### 4a. Discuss & research

`/gsd-discuss-phase 3` locked five decisions ([`03-CONTEXT.md`](.planning/phases/03-parser-layer/03-CONTEXT.md),
2026-06-01): a parser matches on **sender domain** and owns that domain list itself (D-01);
extraction is **label-anchored with a constrained shape-pattern fallback** (D-02); first
match wins (D-03); `carrier` becomes `str | None` — a direct consequence of the Step 2
TrackingMore replan, since the provider auto-detects the courier (D-04); and a "matched but
no tracking number" email (the routine pre-shipment *"order confirmed"*) is an **expected,
non-fatal** skip, not an error (D-05).

Research (`8d4ddf1`) confirmed the real AliExpress sender domains and label strings without
ever committing real data, and made two recommendations the planner adopted: `extract()`
should **return `None`** rather than raise on a no-tracking email (exceptions are the wrong
tool for an expected case), and the parser registry should just be a `PARSERS` list in
`main.py` for v1.

### 4b. Plan & execute — three waves

Planning produced 3 plans across 3 strictly-sequential waves (the plan-checker passed all
dimensions before a line of code was written):

- **Wave 1 — `03-01` (RED scaffold):** the `carrier: str | None` edit (D-04) and the new
  `extract() -> TrackingInfo | None` contract (D-05) in `base.py`, plus synthetic
  `FAKE`-prefixed fixtures and a deliberately-failing test suite. Tests exist *before* the
  implementation. Commits `0b45f07`, `5f9212c`, `a04571a`.
- **Wave 2 — `03-02` (the parser):** `AliExpressParser` with a module-level sender-domain
  constant, a label regex, and a **ReDoS-safe** shape fallback (every alternative requires a
  letter component, so a purely-numeric order reference can't be mis-read as a tracking
  number). Unit tests go green. Commits `6eaa8d0`, `66037f5`.
- **Wave 3 — `03-03` (dispatch):** the `PARSERS` registry and the first-match-wins loop wired
  into `main()`, completing the `RawEmail → TrackingInfo` path. Integration tests go green.
  Commits `ea9492f`, `5f16bec`.

### 4c. The course-correction: the code review caught what the tests missed ⚠️

This is the instructive moment of Phase 3 (the Step-2 equivalent of the 17track→TrackingMore
switch). After execution, **every one of the 32 tests was green** and the phase looked done.
The automated `/gsd-code-review` gate (`e41ad67`) still found two real bugs:

- **CR-01 — silent truncation.** The tracking-number capture `([A-Z0-9]{8,35})` had no
  trailing boundary, so a token longer than 35 characters was captured as its *first 35
  chars* — a wrong number, registered as if correct. A direct hit on the tool's core value.
- **CR-02 — the drop-in contract was quietly broken.** `_get_all_sender_domains()` returned
  the AliExpress constant directly instead of aggregating across `PARSERS`. So a second
  parser would extend `can_parse` matching but **not** the Gmail fetch query — its emails
  would never be fetched. That contradicts Success Criterion 3 ("register by appending to the
  parser list with *no other changes*"). The `test_registry_drop_in` test missed it because
  it only exercised `can_parse`, never the query-building path.

The fixer repaired both: CR-01 gained a `(?![A-Z0-9])` boundary (an over-length token now
fails cleanly rather than truncating), and CR-02 added a `sender_domains` field to the
`BaseParser` ABC with `main()` aggregating over `PARSERS` — restoring the true single-file
drop-in. Commits `3ecad06`, `e839166`.

### 4d. Verify, secure & a follow-up

Goal-backward verification ([`03-VERIFICATION.md`](.planning/phases/03-parser-layer/03-VERIFICATION.md),
`c5eaf4d`) confirmed **9/9 must-haves** and all three success criteria *true against the code*
— including the now-repaired drop-in, re-tested with a real second parser. `/gsd-secure-phase`
closed **11/11 threats** (`31a6c3d`), and specifically re-checked that the review fixes
preserved their mitigations (CR-02 actually *strengthened* the sender-list single-source-of-truth).

One honest follow-up: a human read of the fixes surfaced a *forward-looking* PII risk — the
dispatch error handler used `logger.exception`, which renders the traceback and the
exception's own message; a careless third-party parser raising `ValueError(f"bad body: {body}")`
would leak that into the JSON log. Hardened to log the `message_id` and exception **type**
only, with a contract note on `BaseParser.extract` (`1c5b347`).

**Teaching point — green tests are not a proof of correctness; they prove what you thought to
test.** All 32 tests passed *and* the phase passed goal-verification, yet the independent
code-review reader still found a bug that broke a success criterion — because the test
asserted the mechanism it expected (`can_parse`) rather than the contract it cared about (a
new parser needs *zero* other edits). Both bugs the review caught — truncation and the
drop-in gap — produced fully green suites. That's exactly why GSD runs code review as a
separate gate after execution: treat its findings as first-class even when everything passes.

---

## Step 5 — Phase 4: Deduplication

**Goal:** build the SQLite state layer that makes the whole pipeline idempotent — an email is
never re-processed, a tracking number is never re-registered, and a *failed* registration is
retried automatically on the next run. Two tables (`processed_emails` and `registered_tracking`)
whose schemas are locked by DEDUP-01 and DEDUP-02. The phase also introduces an injectable
**registrar seam** with a `NullRegistrar` placeholder, so the DEDUP-05 retry guarantee is
provable *before* the real TrackingMore client exists.

### 5a. Discuss & research

`/gsd-discuss-phase 4` produced twelve locked decisions, all recorded in
[`04-CONTEXT.md`](.planning/phases/04-deduplication/04-CONTEXT.md) and verified by
stdlib-only probes before a line of code was written
([`04-RESEARCH.md`](.planning/phases/04-deduplication/04-RESEARCH.md), 2026-06-01).

The central architectural question was **write timing**: when exactly do rows land in
`processed_emails` and `registered_tracking`? The answer (D-01) is strict — both rows are
written together in a single `with conn:` transaction, **only on confirmed registrar success**.
A failure (exception or a `False` return from the registrar) writes neither row, logs
PII-safely, and continues. The email is therefore *unseen* on the next cron run and the
tracking number retries automatically. This satisfies DEDUP-05 by construction.

Three finer decisions flow from D-01:

- **D-02:** emails with no tracking number or no parser match are left **unmarked** in
  `processed_emails`. Their body is immutable and re-parseable cheaply every run (local
  regex, no API call) until they age out of the Gmail lookback window. This keeps them open
  to re-evaluation if a parser is later improved.
- **D-03:** when a fresh email arrives whose tracking number is *already* in
  `registered_tracking` (a duplicate-notification email arriving under a new `message_id`),
  the API call is skipped **and** the new `message_id` is written to `processed_emails` via
  `INSERT OR IGNORE` — eliminating re-parse churn for notification duplicates.
- **D-08/D-09 (the seam):** Phase 4 owns the register-then-persist orchestration behind an
  **injectable registrar callable**. The `NullRegistrar` placeholder always returns `False`
  and logs a single `registrar.deferred` line at debug — no WARNING noise on live Phase 4
  runs. Phase 5 drops the real `TrackingMoreRegistrar` into the same seam with **zero
  changes** to `db.py` or the dispatch loop.

Other decisions locked: the state layer as a **module of plain functions** in `db.py` (no
class, connection passed in explicitly — D-04); one connection per run, opened in `main()`
and closed in `finally` (D-05); schema built exactly to DEDUP-01/02 with no speculative
`provider` column (D-06, deferred to a v2 `ALTER TABLE`); and `PRAGMA busy_timeout = 5000`
plus `PRAGMA user_version = 1` set on connect/creation (D-10/D-11).

Research verified the `with conn:` atomic two-row write, the `typing.Protocol` Registrar
contract, and ran a retry-proof probe in-process before any code was written.

### 5b. Plan & execute — three waves

Planning produced 3 plans across 3 strictly-sequential waves:

- **Wave 0 — `04-01` (RED scaffold):** 15 failing DEDUP test functions in `tests/test_db.py`,
  `FAKE`-prefixed fixture constants in `tests/fixtures/fake_db.py`, and an in-memory
  `db_conn` fixture in `tests/conftest.py` — all authored *before* the source modules exist.
  Pre-commit mypy required `# type: ignore[import-not-found]` on the not-yet-written
  `shipping_tracker.db` imports (standard Nyquist Wave 0 pattern). The 15 tests covered
  DEDUP-01 through DEDUP-05 including the `test_retry_proof` integration test. Commits
  `fad212a`, `d54951d`.

- **Wave 1 — `04-02` (the state layer):** `shipping_tracker/db.py` (`init_db`,
  `is_email_processed`, `is_tracking_registered`, `register_and_persist`) plus
  `shipping_tracker/registrar.py` (the `Registrar` `typing.Protocol` and `NullRegistrar`).
  The atomic `with conn:` two-row write turned all 15 RED tests GREEN; 57/57 full-suite
  passing. Wave 0's `# type: ignore[import-not-found]` comments were removed as a
  pre-commit-caught `[unused-ignore]` deviation. Commit `7b886c0`.

- **Wave 3 — `04-03` (main wiring):** the SQLite connection lifecycle (`sqlite3.connect` →
  `init_db` → `finally: conn.close()`) in `main()`, `NullRegistrar` seam injection, and the
  DEDUP-03 (before parse) / DEDUP-04 (`INSERT OR IGNORE` mark-processed in D-03 branch) /
  DEDUP-05 (`register_and_persist`) checks wired into the dispatch loop. `DATABASE_PATH`
  added to `.env.example`, `data/` added to `.gitignore`. Commits `f36566b`, `eb62b96`.

### 5c. The course-correction: `INSERT OR IGNORE` and the self-undercut retry guarantee ⚠️

This is the instructive moment of Phase 4 — the code-review equivalent of the Step 3
CR-01/CR-02 bugs that green tests did not catch.

After execution, all 15 DEDUP tests were green (58/58 full suite), and goal-backward
verification scored 4/4 — all observable truths confirmed against the code, including the
`test_retry_proof` integration test. The automated `/gsd-code-review` gate
([`04-REVIEW.md`](.planning/phases/04-deduplication/04-REVIEW.md)) still flagged **WR-01**:
`register_and_persist` in `db.py` wrote both rows with a bare, non-idempotent `INSERT`,
while the DEDUP-04 mark-processed branch in `main.py` used `INSERT OR IGNORE`. The two write
paths to the same table **disagreed on idempotency**.

The consequence: `register_and_persist` — the function at the very heart of the phase's retry
guarantee — was itself not retry-safe. A future caller, or a crash-window re-registration
where the registrar had already succeeded but the DB commit had not landed, would hit an
already-present row and raise `sqlite3.IntegrityError` mid-transaction. The verifier assessed
it as a WARNING rather than a blocking defect (the upstream `is_tracking_registered` guard in
`main()` prevented the bad call in the normal dispatch path, so SC4 held *as wired*), but
recorded it for a mandatory follow-up.

It was fixed via quick task `260601-pa7`: both `INSERT` statements in `register_and_persist`
became `INSERT OR IGNORE`, and a `test_register_and_persist_idempotent` regression test was
added to prove a repeat call is a silent no-op returning `True`. Commit `5a58eaf`. The two
write paths now agree; the function is self-defending regardless of caller.

### 5d. Verify & the honest deferred state

Goal-backward verification ([`04-VERIFICATION.md`](.planning/phases/04-deduplication/04-VERIFICATION.md),
2026-06-01) confirmed 4/4 observable truths and all five DEDUP requirements
(DEDUP-01 through DEDUP-05) true against the code:

- SC1 (table creation): `CREATE TABLE IF NOT EXISTS` in `init_db`; `test_init_db_*` GREEN.
- SC2 (email dedup): `is_email_processed` guard before any parse work; `test_dispatch_skips_processed_email` GREEN.
- SC3 (tracking dedup): `is_tracking_registered` guard + `INSERT OR IGNORE` mark-processed; `test_dispatch_skips_registered_tracking` and `test_dup_notification_marks_email_processed` GREEN.
- SC4 (retry guarantee): `with conn:` atomic two-row write + registrar-first ordering; `test_retry_proof` (fail-run leaves zero rows; success-run writes both) GREEN.

The verification is honest about the incomplete-pipeline state. A real Phase 4 cron run
creates both tables and exercises the DEDUP-03/DEDUP-04 skip paths, but `NullRegistrar`
always returns `False` — so `registered_tracking` stays empty. This is intentional (D-09):
Phase 5 drops the real `TrackingMoreRegistrar` into the same seam with **zero changes** to
`db.py` or the dispatch loop. The `parsed=0` count in the dispatch-complete log is an honest
signal of a correctly-wired-but-incomplete pipeline, not a bug.

One item remains at `human_needed` status: a live cron run against a real Gmail OAuth token
and a populated `.env`, which in-process pytest cannot exercise. That live-run check confirms
the `data/` directory creation, the file-backed `init_db` idempotency, and the NullRegistrar
"no rows but no errors" end state on a real Pi.

**Teaching point — green tests and a passing goal-verification still left a write path that
quietly undercut the phase's own retry guarantee.** `register_and_persist` relied entirely on
callers having run the upstream dedup guard first, but the code review's independent read of
the implementation found that the two paths writing the same table disagreed on idempotency —
a latent `IntegrityError` waiting for any future caller or crash-window re-entry. The
injectable seam (`NullRegistrar`) is the other lesson: it let Phase 4 *prove* its core
guarantee end-to-end in a fully-automated test suite before the real TrackingMore client
existed — an honest "incomplete but verified" state beats a half-wired loop every time.

---

## Where we are now

- ✅ **Phase 1 — Scaffold:** complete and verified.
- ✅ **Phase 2 — Gmail:** complete and verified (9/9 automated, threats 6/6 closed).
- ✅ **Phase 3 — Parser Layer:** complete and verified (9/9 must-haves, threats 11/11 closed)
  — with a code-review catch (CR-02) that repaired the drop-in contract before it shipped.
- ✅ **Phase 4 — Deduplication:** complete and verified (4/4 must-haves; code-review finding
  WR-01 closed via quick task `260601-pa7`; one live-run UAT item pending human verification).
- ⏭️ **Next: Phase 5.1 — Status Monitoring & Notifications.** Start with
  `/gsd-discuss-phase 5.1`. Phase 4 left a `NullRegistrar` seam and two tables ready;
  Phase 5.1 drops in the real `TrackingMoreRegistrar`, polls for status changes, and pushes
  phone notifications.

Overall milestone progress: **4 of 8 phases (50%)**.

---

## Appendix — How to read the artifacts yourself

For any phase `NN`, look under `.planning/phases/NN-*/`:

| File | What it tells you |
|------|-------------------|
| `NN-CONTEXT.md` | The decisions that were made (the *answers*). |
| `NN-DISCUSSION-LOG.md` | The options considered, including the rejected ones. |
| `NN-RESEARCH.md` | What was investigated before planning (APIs, pitfalls, versions). |
| `NN-PATTERNS.md` | Reusable code patterns established in the phase. |
| `NN-NN-PLAN.md` | The task breakdown with success criteria. |
| `NN-NN-SUMMARY.md` | What actually got built, the commits, and **deviations from plan**. |
| `NN-VERIFICATION.md` | Proof the phase *goal* was met, not just that tasks finished. |
| `NN-SECURITY.md` | The threat model and whether each threat is closed. |

Project-wide state lives in `.planning/PROJECT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, and
`STATE.md`. When in doubt about *why*, start with `PROJECT.md`'s Key Decisions table.
