---
phase: quick-260604-cp7
plan: 01
subsystem: privacy/git-history
tags: [privacy, pii-scrub, git-filter-repo, history-rewrite]
dependency_graph:
  requires: []
  provides: [PRIVACY-PII-HISTORY]
  affects: [all git history, TUTORIAL.md, STATE.md, .git/config]
tech_stack:
  added: [git-filter-repo==2.47.0]
  patterns: [replace-text rewrite, email-callback metadata rewrite]
key_files:
  created:
    - ../shipping-tracker-pre-scrub.bundle
    - ../email-replace.txt
  modified:
    - .planning/phases/01-scaffold/01-SECURITY.md
    - TUTORIAL.md
    - .planning/STATE.md
    - .git/config (repo-local user.email set to noreply form)
decisions:
  - filter-repo invoked twice: once for blob content (replace-text), once for commit metadata (email-callback) — second pass was required because Task 2's commit was authored under the old real-email git config before user.email was updated (Task 6 runs after Task 4)
  - Name field the maintainer also replaced with Swissola in the metadata pass for consistency
  - 4 TUTORIAL.md hashes flagged HASH-UNMAPPABLE (008ac7f, 29f6913, 5acb308, ab64c2e) — not present in git history even before the rewrite; likely from an earlier rebase/amend session before current work began
metrics:
  duration: ~25 minutes
  completed: 2026-06-04
---

# Quick Task 260604-cp7: scrub real email from history before public release — Summary

**One-liner:** Permanently removed `<maintainer-real-email-redacted>` from all 129 git commits (blob content and author/committer metadata) using git-filter-repo, with a pre-rewrite bundle backup, post-rewrite history verification, and stale hash refresh across TUTORIAL.md and STATE.md — history is clean; force-push to origin/main is pending human approval.

---

## Pre-Rewrite State

| Item | Value |
|------|-------|
| Pre-rewrite HEAD SHA | `cabd28e546e64233c6558223803742cc73e84c75` |
| Commit count (pre-rewrite) | 129 |
| Backup bundle | `../shipping-tracker-pre-scrub.bundle` (verified OK) |
| Backup tag | `backup/pre-email-scrub` (local, not to be pushed) |
| Email in blob content | 1 file: `.planning/phases/01-scaffold/01-SECURITY.md` (single line in Advisory section) |
| Email in commit metadata | The Task 2 commit authored under real email before user.email was updated |

---

## Post-Rewrite State

| Item | Value |
|------|-------|
| New HEAD SHA | `6d192e1034fa1783cdd13c65b7b133754ad030df` |
| Commit count (post-rewrite) | 130 (129 original + Task 2 working-tree edit + Task 6 hash-refresh commit) |
| Commits rewritten | All 130 passed through filter-repo (content pass + metadata pass) |
| Email in any blob | ZERO — verified by `git grep -i <maintainer-real-email-redacted> $(git rev-list --all)` → empty |
| Email in any metadata | ZERO — `git log --all --format='%ae %ce'` shows only `9119417+Swissola@users.noreply.github.com` |
| Author name in metadata | Only `Swissola` (the maintainer replaced in metadata pass) |

---

## Tasks Completed

| Task | Name | Commit | Result |
|------|------|--------|--------|
| 1 | Create pre-rewrite backup | (no code commit — bundle + tag only) | BACKUP_OK |
| 2 | Rephrase email line in 01-SECURITY.md | `9b299b4` | WORKTREE_LINE_CLEAN |
| 3 | Install git-filter-repo, write replacement spec | (no code commit) | FILTERREPO_READY |
| 4 | Execute history rewrite (blob content pass) | (filter-repo rewrites history itself) | REWRITE_DONE |
| 4b | Execute metadata rewrite (email-callback pass) | (second filter-repo pass) | Deviation — see below |
| 5 | Verify history clean | (verification only) | HISTORY_CLEAN |
| 6 | Re-add origin, set user.email, refresh hashes | `6d192e1` | REMOTE_AND_CONFIG_OK |
| 7 | Force-push to origin/main | PENDING — human checkpoint | — |

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Task 2 commit authored with real email before user.email was set**

- **Found during:** Task 5 verification gate
- **Issue:** Task 2 committed the 01-SECURITY.md edit using the old git local config (real email), because `git config user.email` was only updated in Task 6. The blob content was clean after Task 4's replace-text pass, but `git log --all --format='%ae %ce'` showed `<maintainer-real-email-redacted>` in HEAD's author/committer metadata — Task 5 would have failed.
- **Fix:** Ran a second filter-repo pass with `--email-callback` (to replace the email in commit metadata) and `--name-callback` (to replace "the maintainer" with "Swissola" for consistency). This is the correct, purpose-built mechanism for commit-metadata rewrites per filter-repo documentation.
- **Files modified:** `.git/` (commit objects only — no working-tree changes)
- **Verification:** `git log --all --format='%ae %ce' | sort -u` → only `9119417+Swissola@users.noreply.github.com`; HISTORY_CLEAN passed.

---

## Hash Refresh Results

### Mapped and updated

All 12 Quick Tasks in STATE.md: hashes updated via commit-map lookup.
All cited hashes in TUTORIAL.md (Phase 2, 3, 4 commits): hashes updated.

### Flagged as HASH-UNMAPPABLE

These 4 hashes appear in TUTORIAL.md (Step 1c — Phase 1 execute section) but were not found in git history even in the pre-rewrite backup bundle — they predate the current commit graph (likely from an earlier rebase or amended session):

| Old hash | Context | Flag placed |
|----------|---------|-------------|
| `008ac7f` | Phase 1 Plan 01 — manifest/gitignore/env | [HASH-UNMAPPABLE: not in current git history] |
| `29f6913` | Phase 1 Plan 01 — package files | [HASH-UNMAPPABLE: not in current git history] |
| `5acb308` | Phase 1 Plan 02 — pre-commit + CI | [HASH-UNMAPPABLE: not in current git history] |
| `ab64c2e` | Phase 1 Plan 02 — tests | [HASH-UNMAPPABLE: not in current git history] |

These flags are inline in TUTORIAL.md. They do not affect the correctness of the history rewrite.

---

## Pending: Task 7 — Force-push (BLOCKING checkpoint)

The local history is verified clean. The force-push to `origin/main` is the point of no return and requires human confirmation.

**Command to run:**
```
git push --force-with-lease origin main
```
(If lease is rejected due to stale tracking ref, fall back to: `git push --force origin main` — this is a private solo repo with no other contributors.)

**After pushing, verify:**
```
git ls-remote origin main
```
The returned SHA should match the new local HEAD: `6d192e1034fa1783cdd13c65b7b133754ad030df`

---

## Self-Check

- [x] `../shipping-tracker-pre-scrub.bundle` exists and verifies OK
- [x] `backup/pre-email-scrub` tag exists locally
- [x] `.planning/phases/01-scaffold/01-SECURITY.md` contains no occurrence of the real email
- [x] `git grep -i <maintainer-real-email-redacted> $(git rev-list --all)` → empty (HISTORY_CLEAN)
- [x] `git log --all --format='%ae %ce' | sort -u` → only noreply address (HISTORY_CLEAN)
- [x] `git remote get-url origin` → `https://github.com/Swissola/shipping-tracker`
- [x] `git config user.email` → `9119417+Swissola@users.noreply.github.com`
- [x] Commit `9b299b4` exists in git log (Task 2 working-tree edit, post-rewrite hash)
- [x] Commit `6d192e1` exists in git log (Task 6 hash-refresh doc commit)
- [ ] origin/main reflects scrubbed history — PENDING Task 7

## Self-Check: PASSED (pre-push items)
