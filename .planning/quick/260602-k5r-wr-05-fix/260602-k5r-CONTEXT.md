# WR-05 fix — decision context

## Gray area resolved (AskUserQuestion, 2026-06-02)

**Question:** WR-05's review offers several valid fixes (bound the per-run retry
budget, add jitter, or merely document the cumulative sleep). Which scope?

**Decision: Budget + jitter (most complete).**
- Add a per-run total-retry-budget cap. The `TrackingMoreRegistrar` instance is
  created once per run and reused for every email, so it can hold a budget counter
  that bounds total retries across the whole batch — N transient failures can no
  longer accumulate N×pause of serial sleep and collide with the cron cadence.
- Add random jitter (`random.uniform(0, retry_jitter)`) to each retry pause,
  matching the Gmail client's `_execute_with_backoff`, to avoid synchronized
  retries against a recovering API.

**Rationale:** Addresses BOTH sub-concerns in the finding (unbounded cumulative
wall-clock AND synchronized retries), not just one. Slightly more code + per-run
state, accepted by the user.

## Constraints carried in
- Preserve existing per-call semantics: still at most ONE retry per `__call__`
  (the `attempt == 0` guard), so TRACK-04/D-02 tests (`route.call_count == 2`)
  stay green.
- LOG-02: no PII in any new log/exception strings.
- Keep the injected-client (D-04) test seam; new knobs are keyword-only with
  safe defaults so existing call sites are unaffected.
