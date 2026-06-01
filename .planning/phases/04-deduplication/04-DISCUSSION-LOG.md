# Phase 4: Deduplication - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-01
**Phase:** 4-Deduplication
**Areas discussed:** Processed-email write timing, State-layer API & connection, DB location & config, Registration seam, Concurrency/locking, Already-registered handling, Schema versioning

---

## Processed-email write timing — core retry model

| Option | Description | Selected |
|--------|-------------|----------|
| Only on durable success | Write `processed_emails` + `registered_tracking` together in one transaction, only after confirmed success; failure writes neither row → retries. | ✓ |
| Decouple, tracking-level only | Never short-circuit tracking-bearing emails via `processed_emails`; rely solely on `registered_tracking` (DEDUP-04). | |

**User's choice:** Only on durable success
**Notes:** Satisfies DEDUP-05 by construction. → CONTEXT D-01.

## Processed-email write timing — no-tracking / no-match emails

| Option | Description | Selected |
|--------|-------------|----------|
| Leave unmarked | Don't write no-tracking/no-match emails; cheaply re-parsed each run until they age out. Honors Phase 3 D-05; keeps emails open to re-evaluation if a parser improves. | ✓ |
| Mark processed on sight | Write every dispatched email immediately. Risk: an improved parser never re-reads an email already marked seen. | |

**User's choice:** Leave unmarked
**Notes:** `processed_emails` = "a tracking number from this email is registered"; `registered_tracking` is the number-level backstop. → CONTEXT D-02.

---

## State-layer API shape

| Option | Description | Selected |
|--------|-------------|----------|
| Module of functions | `db.py` with `init_db(conn)`, `is_email_processed`, `is_tracking_registered`, register helper; connection passed in. Idiomatic stdlib sqlite3, trivially testable. | ✓ |
| Database/StateStore class | Class wrapping the connection; only wins if a future deploy swaps the storage backend behind one interface. | |

**User's choice:** Module of functions
**Notes:** User asked whether functions vs class better supports parser/provider extensibility. Conclusion: it doesn't — parser extensibility lives in the PARSERS registry (Phase 3) and provider extensibility in a Phase 5 provider seam + a schema `provider` column, both orthogonal to the state-layer API style. → CONTEXT D-04.

## State-layer — provider column (folded in from the above)

| Option | Description | Selected |
|--------|-------------|----------|
| Defer to v2 | Build exactly the DEDUP-02 schema; add `provider` via one-line ALTER TABLE when PROV-01 lands. | ✓ |
| Pre-add provider column now | Add `provider` (default 'trackingmore') now; deviates from locked DEDUP-02 schema. | |

**User's choice:** Defer to v2
**Notes:** → CONTEXT D-06, and Deferred Ideas.

## State-layer — connection lifecycle

| Option | Description | Selected |
|--------|-------------|----------|
| One connection per run | `main()` opens one connection, `init_db` once, threads it through, closes in `finally`. Matches single-process sync cron model. | ✓ |
| Open/close per operation | Each helper opens its own connection; redundant churn, awkward cross-helper transaction. | |

**User's choice:** One connection per run
**Notes:** → CONTEXT D-05.

---

## DB location & configuration

| Option | Description | Selected |
|--------|-------------|----------|
| .env with sensible default | `DATABASE_PATH` from `.env`, default `data/shipping-tracker.db`; parent dir created at startup; add to `.env.example`. | ✓ |
| Fixed default only | Hardcode the path, no env var; Pi can't relocate the DB without editing source. | |

**User's choice:** .env with sensible default
**Notes:** → CONTEXT D-07.

## DB default path / directory

| Option | Description | Selected |
|--------|-------------|----------|
| data/shipping-tracker.db | Dedicated gitignored `data/` dir at repo root, parallel to `logs/`. | ✓ |
| shipping-tracker.db at repo root | Mixes runtime state with project files. | |
| Inside the package dir | Risks landing in site-packages when pip-installed on the Pi. | |

**User's choice:** data/shipping-tracker.db
**Notes:** `*.db` already gitignored. → CONTEXT D-07.

---

## Registration seam for DEDUP-05

| Option | Description | Selected |
|--------|-------------|----------|
| Build injectable registrar seam | Phase 4 owns register-then-persist orchestration behind an injected registrar; tests inject fake success/failure; Phase 5 drops in the real client unchanged. | ✓ |
| DB-layer only, defer wiring | Unit-test db helpers in isolation; move orchestration + failure handling to Phase 5. | |

**User's choice:** Build injectable registrar seam
**Notes:** Matches the phase goal ("stateful core of the idempotency guarantee"). → CONTEXT D-08.

## Registration seam — placeholder behavior in a live Phase 4 run

| Option | Description | Selected |
|--------|-------------|----------|
| No-op 'deferred', logged at debug | `NullRegistrar` returns "not registered/deferred", logged at debug (message_id only). Live run creates tables, dedups, persists nothing yet — honest, no warnings. | ✓ |
| Raise NotImplementedError | Caught per-email and logged; noisy error line per tracking email every run until Phase 5. | |
| Orchestration built but not wired into main() | main() wires only table creation + dedup checks; orchestration unit-tested but uncalled until Phase 5. | |

**User's choice:** No-op 'deferred', logged at debug
**Notes:** Keeps Phase 4 a runnable vertical slice. → CONTEXT D-09.

---

## Concurrency / locking posture

| Option | Description | Selected |
|--------|-------------|----------|
| busy_timeout, keep default journal | `PRAGMA busy_timeout = 5000`; default rollback journal (no WAL side-files on the Pi). | ✓ |
| busy_timeout + WAL mode | Adds `-wal`/`-shm` files; marginal benefit for single-writer cron. | |
| Defaults, assume no overlap | Keep sqlite3 defaults; a slow run could collide with the next and raise "database is locked". | |

**User's choice:** busy_timeout, keep default journal
**Notes:** → CONTEXT D-10.

## Already-registered email handling (DEDUP-04 branch)

| Option | Description | Selected |
|--------|-------------|----------|
| Mark it processed | A fresh email whose number is already registered → skip API and write its `message_id` to `processed_emails`. Eliminates re-parse churn for duplicate notifications. | ✓ |
| Leave for re-parse | Don't write it; re-parsed each run, hits DEDUP-04 skip, ages out. | |

**User's choice:** Mark it processed
**Notes:** Refines the model into the consolidated rule — `processed_emails` written whenever the number is durably present (this run or prior). → CONTEXT D-03.

## Schema versioning

| Option | Description | Selected |
|--------|-------------|----------|
| Set user_version = 1 now | `init_db` sets `PRAGMA user_version = 1`; gives PROV-01 migration a clean integer to branch on. | ✓ |
| Add versioning when first migration lands | First migration must then special-case unversioned (`user_version = 0`) legacy DBs. | |

**User's choice:** Set user_version = 1 now
**Notes:** → CONTEXT D-11.

---

## Claude's Discretion

- Exact registrar contract signature (return-value vs typed exception; how TRACK-03 "already-exists" maps) — semantics locked, signature is planner's choice.
- Module name & helper boundaries (`db.py` vs `state.py`; how register-then-persist is factored).
- Transaction mechanism (explicit BEGIN/COMMIT vs `with conn:` vs commit discipline) — must be atomic + roll back together.
- Placement of the DEDUP-03 (pre-parse) and DEDUP-04 (post-parse) checks within the existing `main.py` dispatch loop.
- Dedup-key identity settled by fact (D-12): opaque Gmail API message `id`, not the RFC822 header — no PII.

## Deferred Ideas

- `provider` column on `registered_tracking` (PROV-01, v2) — add via one-line ALTER TABLE gated on `user_version`.
- WAL journal mode — revisit only if real lock contention appears.
- `StateStore` class / swappable storage backend — revisit only if a non-Pi deploy needs a different backend.
- (From Phase 3) multi-parcel-per-email splitting — would change `extract()` to return `list[TrackingInfo]`.
