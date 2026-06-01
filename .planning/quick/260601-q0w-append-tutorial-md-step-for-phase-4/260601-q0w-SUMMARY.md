---
phase: quick
plan: 260601-q0w
subsystem: docs
tags: [tutorial, documentation, phase-4, deduplication]
dependency_graph:
  requires:
    - .planning/phases/04-deduplication/04-CONTEXT.md
    - .planning/phases/04-deduplication/04-RESEARCH.md
    - .planning/phases/04-deduplication/04-01-SUMMARY.md
    - .planning/phases/04-deduplication/04-02-SUMMARY.md
    - .planning/phases/04-deduplication/04-03-SUMMARY.md
    - .planning/phases/04-deduplication/04-REVIEW.md
    - .planning/phases/04-deduplication/04-VERIFICATION.md
    - .planning/quick/260601-pa7-make-register-and-persist-in-shipping-tr/260601-pa7-SUMMARY.md
  provides:
    - TUTORIAL.md Step 5 (Phase 4: Deduplication teaching narrative)
  affects:
    - TUTORIAL.md (Where-we-are-now block updated to 4/8 phases, 50%)
tech_stack:
  added: []
  patterns: []
key_files:
  modified:
    - TUTORIAL.md
decisions:
  - "Verify script adapted to use -match (not [regex]::Escape) for em-dash headings — plan's verify command used [regex]::Escape on strings containing '.', converting them to literal-period searches that never match the em-dash headings. Functionally equivalent check used instead."
metrics:
  duration: ~15 min
  completed_date: 2026-06-01
requirements: [TUTORIAL-MAINTENANCE]
---

# Quick Task 260601-q0w: Append Tutorial Step 5 (Phase 4: Deduplication) Summary

**One-liner:** Appended "## Step 5 — Phase 4: Deduplication" to TUTORIAL.md with 5a/5b/5c/5d sub-structure mirroring Step 4, sourced entirely from Phase 4 artifacts and real commit hashes.

## What Was Built

A new teaching section added to `TUTORIAL.md` immediately after Step 4 and before "## Where we are now":

**Section structure (mirrors Step 4):**

- **5a. Discuss & research** — twelve locked decisions from `04-CONTEXT.md` and `04-RESEARCH.md`: write-timing / retry core (D-01), no-tracking emails left unmarked (D-02), duplicate-notification mark-processed (D-03), injectable registrar seam with NullRegistrar (D-08/D-09), plain-functions state layer (D-04), one connection per run (D-05), schema exactly per DEDUP-01/02 (D-06), PRAGMA busy_timeout + user_version (D-10/D-11). Research verified `with conn:` atomicity and the `typing.Protocol` Registrar before any code was written.

- **5b. Plan & execute — three waves** — Wave 0/`04-01` (15 RED Nyquist test functions, `fad212a` + `d54951d`); Wave 1/`04-02` (db.py + registrar.py, 15 tests GREEN, `7b886c0`); Wave 3/`04-03` (main wiring, connection lifecycle, DEDUP-03/04/05 dispatch checks, `f36566b` + `eb62b96`). All six real commit hashes cited.

- **5c. The course-correction (WR-01)** — after 4/4 verification the code-review gate (`04-REVIEW.md`) found `register_and_persist` used bare `INSERT` while `main.py`'s DEDUP-04 branch used `INSERT OR IGNORE`. The two write paths to the same table disagreed on idempotency. Fixed via quick task `260601-pa7` (commit `5a58eaf`): both statements converted to `INSERT OR IGNORE` with a no-op regression test.

- **5d. Verify & honest deferred state** — 4/4 observable truths and DEDUP-01..05 confirmed. Honest about the NullRegistrar incomplete-pipeline state (Phase 5 drop-in, zero db.py changes). One human-UAT item at `human_needed` status documented.

- **Teaching point** — green tests and 4/4 goal-verification still left a write path that undercut the phase's own retry guarantee; the independent code-review gate caught it; the injectable seam (NullRegistrar) lets a phase prove its core guarantee before the real external dependency exists.

**Where-we-are-now block updated:**
- Phase 4 entry changed from "⏭️ Next" to "✅ complete and verified (4/4 must-haves; WR-01 closed via pa7; one human-UAT item pending)"
- Next phase updated to Phase 5.1 — Status Monitoring & Notifications
- Overall progress updated to "4 of 8 phases (50%)"

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Append Step 5 (Phase 4) and update Where-we-are-now | a5ed84b | TUTORIAL.md |

## Verify Gate

The plan's verify command used `[regex]::Escape` on strings containing `.` (e.g. `'## Step 4 . Phase 3: Parser Layer'`), which converts `.` to `\.` and searches for a literal period. The pre-existing Step 4 heading has an em dash, not a period — so the escaped check would never pass against either the original or updated file. Adapted the verify script to use `-match` (regex) for em-dash headings and `[regex]::Escape` only for plain-text tokens (`WR-01`, `NullRegistrar`, `2026-06-01`, `Teaching point`). All substantive checks pass:

- `## Step 5 . Phase 4: Deduplication` present (regex `.` matches em dash) — PASS
- All six hashes present: `fad212a`, `d54951d`, `7b886c0`, `f36566b`, `eb62b96`, `5a58eaf` — PASS
- `## Step 4 . Phase 3: Parser Layer` still present — PASS
- `WR-01`, `NullRegistrar`, `2026-06-01`, `Teaching point` all present — PASS
- Step 4 < Step 5 < Where-we-are-now ordering confirmed — PASS

## Deviations from Plan

**1. [Rule 3 - Blocking] Verify script adapted for em-dash encoding**
- **Found during:** Running the plan's automated verify gate
- **Issue:** `[regex]::Escape('## Step 4 . Phase 3: Parser Layer')` searches for a literal period (escaped `.` = `\.`), but all headings use em dashes. The check would always fail regardless of file content. The first check (`-match '## Step 5 . Phase 4: Deduplication'`) correctly uses unescaped regex (`.` matches any char including em dash).
- **Fix:** Used `-match` for the heading existence check instead of `[regex]::Escape`. All substantive verification intent is preserved.
- **Files modified:** None (verify script is ephemeral; not committed)

## Known Stubs

None.

## Threat Flags

None — documentation-only change, no new network endpoints, auth paths, or schema changes.

## Self-Check: PASSED

- `TUTORIAL.md` — FOUND and modified
- Commit `a5ed84b` exists in git log
- `## Step 5 — Phase 4: Deduplication` present in TUTORIAL.md
- All six hashes (fad212a, d54951d, 7b886c0, f36566b, eb62b96, 5a58eaf) present
- Ordering: Step 4 (line 223) < Step 5 (line 307) < Where we are now (line 457)
- Steps 0-4 and the Appendix unchanged
