---
phase: 03-parser-layer
fixed_at: 2026-06-01T00:00:00Z
review_path: .planning/phases/03-parser-layer/03-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 3: Code Review Fix Report

**Fixed at:** 2026-06-01T00:00:00Z
**Source review:** .planning/phases/03-parser-layer/03-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (CR-01, CR-02, WR-01, WR-02, WR-03, WR-04)
- Fixed: 6
- Skipped: 0

Info findings (IN-01, IN-02, IN-03) were out of scope. IN-01 (vacuous PII
test) and IN-02 (overstated docstring) were nonetheless resolved as a
side-effect of the WR-04 / CR-02 fixes — see notes below. IN-03 (fixture
comment drift) was left untouched.

All commits were made on an isolated git worktree and fast-forwarded onto the
branch. After every fix the full gate was re-run: `pytest -q` (42 passed),
`mypy shipping_tracker` (strict, clean), and `ruff check shipping_tracker
tests` (clean).

## Fixed Issues

### CR-01: Over-length tracking numbers are silently truncated to 35 chars

**Files modified:** `shipping_tracker/parsers/aliexpress.py`, `tests/test_aliexpress_parser.py`
**Commit:** 3ecad06
**Applied fix:** Added a trailing boundary assertion `(?![A-Z0-9])` after the
`([A-Z0-9]{8,35})` capture group in `_LABEL_RE`. An over-length token
(>35 alnum chars) now fails the assertion at every backtrack length, so the
label stage no longer truncates — it returns no match and falls through to the
shape stage / `None` instead of registering a corrupted partial number.
Regression test `test_extract_overlength_token_not_truncated` proves a 38-char
synthetic (FAKE-prefixed) token never yields the first-35-char truncation.

### CR-02: `_get_all_sender_domains()` ignores `PARSERS`, breaking the D-01 drop-in contract

**Files modified:** `shipping_tracker/parsers/base.py`, `shipping_tracker/main.py`, `shipping_tracker/parsers/aliexpress.py`, `tests/test_aliexpress_parser.py`
**Commits:** e839166 (base.py + main.py + test); the `sender_domains`
class attribute on `AliExpressParser` landed in 3ecad06 (whole-file staging —
see Notes)
**Applied fix:** Declared `sender_domains: tuple[str, ...] = ()` on the
`BaseParser` ABC; `AliExpressParser` exposes `ALIEXPRESS_SENDER_DOMAINS`
through it. Rewrote `main._get_all_sender_domains()` to iterate `PARSERS` and
union each parser's declared domains (de-duplicated, first-seen order
preserved for a stable Gmail query). Dropped the now-unused
`ALIEXPRESS_SENDER_DOMAINS` import from `main.py`. This restores Success
Criterion 3 (a new parser is a single self-contained file with no `main.py`
edit) and incidentally makes the IN-02 docstring claim accurate. Test
`test_get_all_sender_domains_aggregates_across_parsers` asserts that appending
a second parser surfaces its domain in the aggregated list while preserving
the AliExpress domains and de-duplication.

### WR-01: Shape-fallback last alternative false-matches ordinary contiguous tokens

**Files modified:** `shipping_tracker/parsers/aliexpress.py`, `tests/test_aliexpress_parser.py`
**Commit:** 3ecad06
**Applied fix:** Replaced the open-ended
`[A-Z]{2,} \d{3,} [A-Z]{2,} [A-Z0-9]*` alternative in `_SHAPE_RE` with a
length-gated variant: a leading `(?=[A-Z0-9]{16,35}\b)` look-ahead plus
"at-least-one-letter" and "at-least-one-digit" assertions before the same
mixed shape. Short ordinary tokens (`HTTP200OK`, `ISO9001CERT`, `ABC123XYZ`)
no longer match, while the real AliExpress-shaped fixture
`FAKEYT00000FAKE0001` still extracts and purely-numeric order refs
(`500FAKE123456789`) still reject. Negative tests added via
`test_extract_shape_rejects_ordinary_tokens`,
`test_extract_shape_rejects_numeric_order_ref`, and a positive guard
`test_extract_shape_still_matches_real_shape`.

### WR-02: `IGNORECASE` captures lowercase tracking numbers (Phase 4 dedup hazard)

**Files modified:** `shipping_tracker/parsers/aliexpress.py`, `tests/test_aliexpress_parser.py`
**Commit:** 3ecad06
**Applied fix:** Normalised captured tracking numbers to canonical upper-case
at both extraction stages (`m.group(1).upper()` and `m2.group(0).upper()`).
Label matching stays case-insensitive; only the stored value is canonicalised,
so the same physical number arriving in different casings dedupes to one key
in Phase 4. Test `test_extract_normalises_lowercase_to_upper` asserts a
lowercase label body yields the upper-cased number.

### WR-03: Routine success-path summaries logged at WARNING level (cron noise)

**Files modified:** `shipping_tracker/main.py`
**Commit:** e839166
**Applied fix:** Demoted `parser.dispatch.complete` from `logger.warning` to
`logger.info`, and removed the duplicate `gmail.fetch.complete` WARNING
emission in `main.py` (the Gmail client at `gmail/client.py:240` already logs
that event at INFO — single source of truth restored). LOG-02 compliance
preserved (counts only, no PII).

### WR-04: A parser raising in `extract()`/`can_parse()` crashes the whole run

**Files modified:** `shipping_tracker/main.py`, `tests/test_aliexpress_parser.py`
**Commit:** e839166
**Applied fix:** Wrapped each email's per-email dispatch in `main()` in a
`try/except Exception` that logs `parser.dispatch.error id=%s` (message_id
only — LOG-02), then `continue`s so one malformed email cannot abort the
batch (D-05 robustness intent). Tests `test_dispatch_isolates_raising_parser`
(a raising parser does not prevent the remaining good email from producing a
result) and `test_main_dispatch_loop_logs_pii_safely_on_error` (the new error
log carries the message_id but never the body or tracking text) were added —
the latter strengthens the previously vacuous IN-01 PII assertion now that the
dispatch loop emits a real log record.

## Notes on commit grouping

`gsd-sdk query commit --files` stages whole files (it runs `git add <file>`),
so findings that share a source file cannot be split into separate commits.
Consequently:

- All `aliexpress.py` changes (CR-01, WR-01, WR-02, and the CR-02
  `sender_domains` class attribute) landed together in **3ecad06**. The
  attribute is inert without the `base.py` / `main.py` aggregation, so this
  grouping kept that commit green.
- All `main.py` changes (CR-02 aggregation, WR-03, WR-04) plus the `base.py`
  ABC attribute and the remaining tests landed together in **e839166**.

Every commit was verified green independently (pytest + mypy --strict + ruff)
before the next was made.

---

_Fixed: 2026-06-01T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
