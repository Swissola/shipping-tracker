---
quick_id: 260601-kp7
slug: add-claude-md-guardrail-routing-conversa
status: complete
created: 2026-06-01
completed: 2026-06-01
---

# Quick Task 260601-kp7 — Summary

## What was done

1. **CLAUDE.md governance guardrail.** Extended §GSD Workflow Enforcement with two extra entry
   points (`/gsd-plan-phase N --gaps`, `/gsd-capture`) and a new `### Routing conversational
   requests` subsection. It draws the line between *conversation* (free — questions, analysis,
   triage) and *file changes* (route through GSD), classifies changes three ways
   (code/behaviour/schema/config → offer a command first; docs/tracking → quick preferred,
   direct acceptable if named; trivial user-driven one-liner → proceed atomically), tightens
   "explicit bypass" to mean a deliberate opt-out *after* the route was offered, and forbids
   letting a finished command's tail become a string of untracked edits.

2. **WR-04 tracking record (retroactive).** The WR-04 PII-logging hardening was already applied
   and committed during the Phase 3 follow-up triage, outside a GSD wrapper — which is the exact
   behaviour the new guardrail targets. This task retroactively brings it under tracking.

## WR-04 change being recorded

- **Commit:** `1c5b347` — `fix(03): harden dispatch error logging against PII leak (WR-04 follow-up)`
- **Files:** `shipping_tracker/main.py`, `shipping_tracker/parsers/base.py`, `tests/test_aliexpress_parser.py`
- **What it did:** replaced `logger.exception` in the dispatch error handler with
  `logger.error("parser.dispatch.error id=%s type=%s", message_id, type(exc).__name__)` so a
  third-party parser raising with PII in its exception message/traceback cannot leak it into the
  JSON log (which renders `exc_info` via `format_exc_info`). Added a LOG-02 contract note to
  `BaseParser.extract` and rewrote the error-path test to drive the real `main()` with PII in the
  exception, asserting `record.exc_info is None` and no PII in any record.
- **Gates at commit time:** 42 tests pass, mypy --strict clean, ruff clean.

## Deviation from the standard quick flow

Execution was done **inline by the orchestrator** rather than via spawned planner + executor
subagents. Rationale: the substantive change is a single, fully-specified governance doc edit
(no code), so the quick workflow's "shortest path / you know exactly what to do" default was
honoured by skipping the subagent round-trips while still producing the full artifact trail
(PLAN.md, this SUMMARY.md, STATE.md row, atomic commit).

Note: the CLAUDE.md edit lands inside the `GSD:workflow-start/end` managed markers, so a future
`/gsd-config` regeneration of that block could overwrite it — re-apply from this task if so.

## Self-Check: PASSED

- `CLAUDE.md` contains `### Routing conversational requests` and references `/gsd-capture` + `/gsd-plan-phase N --gaps`. ✓
- WR-04 commit `1c5b347` recorded above and in the STATE Quick Tasks table. ✓
- No source/test files modified by this task. ✓
