# Phase 5: Pipeline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-01
**Phase:** 5-Pipeline
**Areas discussed:** Quota/rate-limit run behavior, Transient error & timeout policy, Testing vs the free 50/month quota, API-key validation & startup failure, Short-circuit signal mechanism, Response logging detail & levels, courier_code hint handling

---

## Quota / rate-limit run behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Short-circuit creates for the run | On first quota/429, stop further create calls this run; one WARNING summary; unregistered numbers auto-retry next cron (DEDUP-05) | ✓ |
| Keep trying every number | Attempt a create for every number regardless; each fails independently. Burns N pointless calls + N error lines once quota gone | |
| Distinguish 429 from quota-exhausted | Treat transient 429 differently from monthly-quota-exhausted; more precise, more parsing logic | |

**User's choice:** Short-circuit creates for the run
**Notes:** Maps to D-01. The signal mechanism (how "stop" reaches main()'s loop) was promoted to its own area below.

---

## Transient error & timeout policy

| Option | Description | Selected |
|--------|-------------|----------|
| No in-run retry; defer to next cron | Treat as normal failure; DEDUP-05 retries next run. Simplest | |
| One quick in-run retry | Retry the single failed call once after a short pause (~2s), then defer. Catches one-off blips | ✓ |
| Bounded retry with backoff | 2–3 retries with exponential backoff. Most resilient, most code, risks long-running cron | |

**User's choice:** One quick in-run retry → D-02
**Follow-up (Timeout):**

| Option | Description | Selected |
|--------|-------------|----------|
| 10s connect+read | 10s per attempt; ~22s worst case with one retry then defer | ✓ |
| 30s | More tolerant; ~60s+ worst case | |
| 5s | Fail fast; may abandon a slow-but-alive response | |

**User's choice:** 10s connect+read → D-03
**Notes:** Clean split captured — 429/quota is NOT transient: it short-circuits (D-01), never retried. Only network/5xx get the one retry.

---

## Testing vs the free 50/month quota

| Option | Description | Selected |
|--------|-------------|----------|
| Mocked/recorded only — zero live calls | Inject fake HTTP transport with synthetic responses for every path; never touches real API/quota; CI-safe | ✓ |
| Mocked + opt-in manual live smoke | Mocked suite plus env-gated live smoke (1 real registration each run); needs real key | |
| Mocked + recorded real fixtures | Mocked suite with fixtures captured once from a real (sanitized) call; one-time quota cost | |

**User's choice:** Mocked/recorded only — zero live calls → D-04
**Notes:** Requires the registrar to expose an injectable HTTP transport seam. Researcher must document real TrackingMore response shapes so synthetic fixtures are accurate. Live smoke noted as deferred.

---

## API-key validation & startup failure

| Option | Description | Selected |
|--------|-------------|----------|
| Fail-fast at startup, exit 1 | Validate key right after load_dotenv(), before Gmail/DB; missing → PII-safe error + exit 1 | ✓ |
| Lazy — fail when first create is needed | Run Gmail/parse/dedupe; only abort at first registration. No-new-trackings run "succeeds" with no key | |
| Fail-fast, but exit 0 + warn | Check at startup, WARNING + exit 0. Cron-quiet but contradicts "refuses to start" | |

**User's choice:** Fail-fast at startup, exit 1 → D-05

---

## Short-circuit signal mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Typed QuotaExceeded exception | Registrar raises QuotaExceededError; register_and_persist propagates; main()'s loop catches & breaks. Keeps bool Protocol intact | ✓ |
| Catch at register_and_persist, return signal | Helper returns an enum (persisted/not/quota-stop); main() branches. Exception-free but widens Phase 4 helper return contract | |
| Mutable flag / callback | Registrar sets a quota_reached flag main() checks each iteration. Shared mutable state — least clean | |

**User's choice:** Typed QuotaExceeded exception → D-06
**Notes:** Phase 4 D-08 explicitly left "return-value vs typed exception" to the planner; this is the deciding input. CRITICAL wiring: the `except QuotaExceededError: break` must precede the loop's broad `except Exception` (main.py:135) or it gets swallowed.

---

## Response logging detail & levels

| Option | Description | Selected |
|--------|-------------|----------|
| Quiet-by-default, tiered | created→INFO, already-exists→INFO/DEBUG, transient error→ERROR, quota→one WARNING. Healthy runs near-silent | ✓ |
| Verbose — log every response | Every outcome incl. raw status at INFO + counts summary. More observability, noisier | |
| Minimal — errors only | Only failures (ERROR) + quota (WARNING); successes silent. Leanest, hard to confirm a healthy run | |

**User's choice:** Quiet-by-default, tiered → D-07
**Notes:** All PII-safe (LOG-02). Sets the pattern Phase 6 formalizes for cron-silence (LOG-03).

---

## courier_code hint handling

| Option | Description | Selected |
|--------|-------------|----------|
| Omit field when None | tracking_number always; courier_code only when carrier non-None; omit key otherwise. Auto-detect preserved, future-proof | ✓ |
| Always send, null when absent | Always include courier_code=null when absent. Uniform but relies on API tolerating null | |
| Drop courier_code entirely for now | Don't wire courier_code at all since AliExpress yields None. Re-opens payload later | |

**User's choice:** Omit field when None → D-08
**Notes:** AliExpressParser returns carrier=None today, so the field is omitted in practice now, but the param is wired through (the seam already carries it) for future parsers.

---

## Claude's Discretion

- HTTP library choice (httpx vs requests) — httpx fits the stack and the injectable-transport testing.
- Exact already-exists detection (TRACK-03) — the precise TrackingMore v4 response field/code — research from live API docs.
- Exact `QuotaExceededError` module home / base class — semantics locked (D-06).
- Injectable-transport shape (constructor-injected client, base-URL override, or callable).
- Whether to expand the `TRACKINGMORE_API_KEY` comment in `.env.example` (var already exists).
- Retry pause exactness (~2s) and connect/read split within the 10s budget.

## Deferred Ideas

- Proactive monthly-quota counting (Phase 5 is reactive only).
- Opt-in live smoke test (zero-live-calls policy chosen instead; possible manual one-off).
- Bounded exponential-backoff retry (rejected for D-02; cron re-run recovers anyway).
- `provider` column / second provider (PROV-01, v2 — carried from Phase 4).
- `.env.example` TrackingMore comment expansion (minor).
