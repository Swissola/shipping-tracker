# Quick Task 260604-cp7: scrub real email from history before public release - Context

**Gathered:** 2026-06-04
**Status:** Ready for planning

<domain>
## Task Boundary

Remove the maintainer's real personal email (`<maintainer-real-email-redacted>`) from the
git repository's tracked content **and full history**, so the repo can be made public
with no PII whatsoever, then propagate the clean history to the already-pushed private
GitHub remote.

</domain>

<decisions>
## Implementation Decisions

### Audit scope (established before planning)
- The real email appears in **file content** in exactly one place: a single line in
  `.planning/phases/01-scaffold/01-SECURITY.md` (the line reads
  ``Every commit's author trailer is `Swissola <<maintainer-real-email-redacted>>`...``).
- That line is present in **~20 commits** since it was introduced at `44a7564`
  (`docs(phase-01): add security threat verification`).
- Commit **author/committer metadata is already clean** — every commit is authored as
  `Swissola <9119417+Swissola@users.noreply.github.com>` (GitHub noreply form). No
  metadata rewrite of names/emails is required; only file CONTENT must be scrubbed.
- Test fixtures, `.env` handling, and `.gitignore` are already PII-clean (synthetic
  `.example.com` / `FAKE`-prefixed values). Do NOT touch them.
- Local `git config user.email` currently resolves to the real email even though commits
  used noreply — set repo-local config to the noreply form to prevent future leaks.

### Rewrite approach — LOCKED
- Use **targeted history rewrite** (`git filter-repo --replace-text`) to replace the real
  email string with the noreply form (`9119417+Swissola@users.noreply.github.com`)
  across all of history. **Preserve all 128 commits** and the GSD teaching trail — do NOT
  squash.
- `git-filter-repo` is **NOT installed** locally. Install it (`pip install git-filter-repo`)
  or, if that is unavailable, fall back to `git filter-branch` / `git replace`-free
  equivalent. filter-repo is strongly preferred.
- Accept that commit hashes from `44a7564` onward will change. `TUTORIAL.md` and various
  `SUMMARY`/`STATE` files reference real commit hashes that will go stale — include a
  follow-up task to refresh those hash references after the rewrite (best-effort; flag any
  that can't be auto-mapped).

### Remote handling — LOCKED
- After the local rewrite, **force-push** to overwrite `origin/main`
  (`https://github.com/Swissola/shipping-tracker`, currently private).
- The user accepts that GitHub keeps the old commits reachable by SHA until garbage
  collection; acceptable for a private solo repo with no forks.

### Safety — REQUIRED
- Before ANY history rewrite, create a recoverable backup (e.g. `git bundle create
  ../shipping-tracker-pre-scrub.bundle --all` and/or a `backup/pre-email-scrub` branch /
  tag). The rewrite is irreversible without it.
- After the rewrite, **verify** the email is absent from ALL history:
  `git grep -i "<maintainer-real-email-redacted>" $(git rev-list --all)` must return nothing,
  and `git log --all --format='%ae %ce' | sort -u` must show only the noreply address.

### Claude's Discretion
- Exact filter-repo invocation, replacement-spec file format, remote re-add mechanics
  (filter-repo drops `origin` after rewriting), and how TUTORIAL.md hash refs are refreshed.
- Whether the working-tree `01-SECURITY.md` line is rephrased (recommended: rewrite the
  sentence so it no longer quotes the address verbatim — describe it as "the GitHub noreply
  address" instead) vs. left to the replace-text substitution alone.

</decisions>

<specifics>
## Specific Ideas

- Replacement target: `<maintainer-real-email-redacted>` ⇒ `9119417+Swissola@users.noreply.github.com`
  (the form already used in commit metadata, so content and metadata become consistent).
- filter-repo `--replace-text` expects a file of `literal:OLD==>NEW` rules.

</specifics>

<canonical_refs>
## Canonical References

- `CLAUDE.md` → Constraints: "Privacy: No PII in source, tests, logs, or history — project
  will be public; non-negotiable."
- `.planning/phases/01-scaffold/01-SECURITY.md` → the file containing the leak (and the
  advisory that originally recommended the noreply author email).
- `TUTORIAL.md` → teaching walkthrough with real commit hashes that the rewrite will
  invalidate.

</canonical_refs>
