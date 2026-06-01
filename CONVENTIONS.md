# Conventions

Project conventions. This file is the source of truth for the `## Conventions` block in
`CLAUDE.md` (synced via the `GSD:conventions` markers).

## Tutorial maintenance (TUTORIAL.md)

This project is documented as a GSD teaching walkthrough. `TUTORIAL.md` (repo root) must
stay current with the phases.

- **Trigger:** after a phase passes its verify beat (`/gsd-verify-work`) and before advancing
  to the next phase, append a new `## Step N — Phase X` section to `TUTORIAL.md`.
- **Source from artifacts, not memory:** draw the narrative from that phase's
  `NN-CONTEXT.md`, `NN-DISCUSSION-LOG.md`, `NN-NN-SUMMARY.md`, and `NN-VERIFICATION.md`.
- **Match the established format:** discuss → plan → execute → verify narrative, real commit
  hashes, absolute dates, and a closing **Teaching point**.
- **Call out course-corrections explicitly** — replans, dropped assumptions, and logged
  deviations are the most instructive moments (see Step 2, the 17track→TrackingMore switch).
- Commit the update with the phase's docs (`commit_docs` is on).
