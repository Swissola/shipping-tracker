---
phase: 04-deduplication
reviewed: 2026-06-01T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - shipping_tracker/db.py
  - shipping_tracker/main.py
  - shipping_tracker/registrar.py
  - tests/conftest.py
  - tests/fixtures/fake_db.py
  - tests/test_db.py
findings:
  critical: 0
  warning: 4
  info: 4
  total: 8
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-06-01T00:00:00Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Reviewed the Phase 4 deduplication layer: the SQLite state functions (`db.py`),
the connection-lifecycle + dispatch wiring (`main.py`), the registrar seam
(`registrar.py`), and the test suite. The privacy constraint is well honoured —
all SQL is parameterized (no injection surface), logging sites consistently emit
only `message_id` and exception *type* (never `tracking_number`, body, or
sender), `.gitignore` excludes `.env`, `*.db`, `data/`, and `token.json`, and
fixtures use only `FAKE`-prefixed synthetic data. There is a LOG-02 regression
guard test. No Critical issues were found.

The defects that remain are robustness and consistency concerns, not security
holes. The most important: `register_and_persist` performs a bare, non-idempotent
`INSERT` for both rows, which is inconsistent with the `INSERT OR IGNORE` used in
the DEDUP-04 branch and makes the function itself non-reentrant — it relies
entirely on the caller having checked dedup first. There is also a real
crash-window in the retry guarantee (API success → process dies before DB
commit) that is *safe only because* the Registrar Protocol promises idempotency
for already-exists responses; that coupling is currently undocumented at the
`register_and_persist` call site.

## Warnings

### WR-01: `register_and_persist` uses non-idempotent `INSERT`, inconsistent with the DEDUP-04 path

**File:** `shipping_tracker/db.py:90-97`
**Issue:** Both writes use a bare `INSERT`:
```python
conn.execute("INSERT INTO processed_emails VALUES (?, ?)", (message_id, now))
conn.execute("INSERT INTO registered_tracking VALUES (?, ?, ?, NULL, NULL)",
             (tracking_number, now, message_id))
```
Either `message_id` or `tracking_number` already existing raises
`sqlite3.IntegrityError` (PRIMARY KEY violation). The function does not itself
re-check `is_tracking_registered` / `is_email_processed`; it trusts the caller to
have guarded. That is fragile: any future caller (or a retry where a partial
prior state exists) that calls `register_and_persist` for an already-registered
number raises mid-transaction. Worse, the *other* write site for the same table
in `main.py:122-125` deliberately uses `INSERT OR IGNORE` — so the two paths that
write `processed_emails` disagree on idempotency. The retry-proof guarantee this
phase is built around is weakened by a write that is itself not retry-safe.
**Fix:** Make the persist idempotent and consistent with the DEDUP-04 branch:
```python
with conn:
    conn.execute(
        "INSERT OR IGNORE INTO processed_emails VALUES (?, ?)",
        (message_id, now),
    )
    conn.execute(
        "INSERT OR IGNORE INTO registered_tracking VALUES (?, ?, ?, NULL, NULL)",
        (tracking_number, now, message_id),
    )
```
If a hard failure on duplicate is actually desired, document that contract
explicitly and add a test for the IntegrityError path.

### WR-02: Crash window between registrar success and DB commit relies on undocumented idempotency coupling

**File:** `shipping_tracker/db.py:82-98`
**Issue:** The registrar (an external API side-effect) is invoked at line 83,
*before* the `with conn:` transaction at line 89. On the target hardware (a Pi
running unattended), a power loss or kill between a successful registration and
the commit leaves the parcel registered with TrackingMore but no row in
`registered_tracking`. On the next run `is_tracking_registered` returns False and
the registrar is called *again*. This is only safe because the `Registrar`
Protocol docstring (`registrar.py:23`) promises `True` for "TRACK-03
already-exists responses". That cross-module invariant is the linchpin of the
retry guarantee, yet `register_and_persist`'s docstring (which is where a future
maintainer swapping in `TrackingMoreRegistrar` will look) does not state that the
registrar MUST be idempotent. A non-idempotent registrar silently breaks the
"no duplicates" core value.
**Fix:** Add an explicit contract note to the `register_and_persist` docstring,
e.g. *"The registrar MUST be idempotent: a crash between registration and the DB
commit causes a re-registration on the next run, so a repeat call for an
already-registered number MUST return True, not error or double-register
(TRACK-03)."* No code change required; this is a documented invariant the Phase 5
implementer must honour.

### WR-03: `os.makedirs(... or "data")` fallback creates the wrong directory for a bare filename

**File:** `shipping_tracker/main.py:67-69`
**Issue:**
```python
db_path = os.getenv("DATABASE_PATH", "data/shipping-tracker.db")
os.makedirs(os.path.dirname(db_path) or "data", exist_ok=True)
conn = sqlite3.connect(db_path)
```
If `DATABASE_PATH` is set to a bare filename (e.g. `shipping.db`),
`os.path.dirname` returns `""`, so the `or "data"` fallback creates a `data/`
directory that the connection then ignores — the DB is opened in the cwd. The
directory the user actually needs is never created in that branch; the fallback
only happens to be correct for the *default* value. If `DATABASE_PATH=:memory:`,
a stray `data/` directory is created on every run. The fallback masks rather than
handles the no-directory case.
**Fix:** Only create a directory when the path actually has one:
```python
db_dir = os.path.dirname(db_path)
if db_dir:
    os.makedirs(db_dir, exist_ok=True)
conn = sqlite3.connect(db_path)
```

### WR-04: DEDUP-04 / D-03 mark-processed logic is duplicated in main.py and re-implemented in tests instead of shared

**File:** `shipping_tracker/main.py:117-126`; `tests/test_db.py:228-238`
**Issue:** The "tracking already registered → mark email processed via
`INSERT OR IGNORE`" sequence lives inline in `main.py` and is then *re-typed* in
`test_dup_notification_marks_email_processed` (test lines 228-238) and the skip
decisions in `test_dispatch_skips_processed_email` / `_skips_registered_tracking`
are likewise hand-simulated `if/else` blocks rather than exercising real code.
This means: (1) the DEDUP-04 branch in `main()` has no test that runs the actual
production code path — the tests reconstruct the logic, so a regression in
`main.py`'s branch (e.g. dropping the `INSERT OR IGNORE`) would not be caught;
and (2) the mark-processed step is unguarded by the per-email `try/except`'s
transaction semantics — it opens its own `with conn:`. Extract the branch into a
small testable helper in `db.py` (e.g. `mark_email_processed(conn, message_id)`)
and have both `main.py` and the test call it.
**Fix:** Add to `db.py`:
```python
def mark_email_processed(conn: sqlite3.Connection, message_id: str) -> None:
    """Idempotently record message_id as processed (D-03 dedup-skip path)."""
    now = datetime.datetime.now(datetime.UTC).isoformat()
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO processed_emails VALUES (?, ?)",
            (message_id, now),
        )
```
Call it from `main.py:121-125` and assert against it directly in the test.

## Info

### IN-01: `import datetime` in main.py is needed only by the inline DEDUP-04 block

**File:** `shipping_tracker/main.py:5`, `120`
**Issue:** `datetime` is imported solely for the `now = ...isoformat()` call at
line 120. If WR-04 is applied (moving that block into `db.py`), this import
becomes unused. Flagging so it is removed alongside the refactor rather than left
dangling (ruff F401 would catch it, but worth noting now).
**Fix:** Remove `import datetime` from `main.py` once the mark-processed logic
moves to `db.py`.

### IN-02: `tracking_results` accumulates full `TrackingInfo` objects but only its length is used

**File:** `shipping_tracker/main.py:88`, `133`, `150-154`
**Issue:** `tracking_results: list[TrackingInfo]` holds every parsed result, yet
the only consumer is `len(tracking_results)` in the end-of-run log. Holding the
objects is harmless for now but is dead state — and `TrackingInfo` carries
`tracking_number`, so keeping the list around lengthens the lifetime of PII-
adjacent data in memory for no functional reason in Phase 4.
**Fix:** Replace the list with a counter (`parsed_count += 1`) unless Phase 5
genuinely needs the collected results; if so, leave a comment naming that future
consumer.

### IN-03: `is_email_processed` / `is_tracking_registered` docstrings cite criteria IDs but not the None-vs-bool contract

**File:** `shipping_tracker/db.py:49-55`, `58-64`
**Issue:** Both helpers do `return row is not None`, which is correct, but the
`SELECT 1` could be misread by a maintainer as returning a truthy row. Minor
clarity only — the explicit `is not None` is the right pattern. No bug.
**Fix:** Optional: rename the projected column intent in a comment, or leave as
is. No action required for correctness.

### IN-04: Test helpers `fail_registrar` / `success_registrar` / `raising_registrar` ignore their parameters

**File:** `tests/test_db.py:31-43`
**Issue:** The three fake registrars take `tracking_number` and `carrier` but use
neither. This is fine for fakes, but ruff (ARG001) may flag unused arguments
depending on config. The synthetic exception message in `raising_registrar`
("synthetic API failure") correctly contains no PII — good.
**Fix:** Optional: prefix unused params with `_` (`_tracking_number`, `_carrier`)
or add a `# noqa: ARG001` if the linter complains. No correctness impact.

---

_Reviewed: 2026-06-01T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
