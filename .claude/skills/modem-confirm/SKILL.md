---
name: modem-confirm
description: Process a contributor's diagnostics download into a modem.verified.json, flip the catalog status to confirmed, and draft the commit message and issue reply. Covers Steps 13–16 of the modem intake workflow.
---

# Modem Confirm

Read `packages/cable_modem_monitor_catalog_tools/docs/MODEM_INTAKE_WORKFLOW.md`
Steps 13 through 16 in full before doing anything else. Execute each step
in order. Do not skip ahead.

Key requirements that are easy to miss:

- Strip exactly the keys listed in Step 13 — no more, no fewer.
- Channel arrays use compact rendering: one JSON object per line, no
  internal line breaks. All other objects use standard 2-space indent.
- Status flips to `confirmed`, not `verified` or any other value.
- **Run catalog tests (Step 15a) before committing.** This is ordinary
  verification, not a promotion gate:
  `test_modem_golden_spec_conformance` covers every modem regardless of
  status, so flipping to `confirmed` activates nothing new. A failure
  means this session's edits broke something. Fix it before proceeding.
- Commit message follows the exact shape in Step 15, including the
  hardware summary line and `Related to #<issue>` (never `Fixes` or
  `Closes`).
- Show the user the files to stage; do not run `git add`.
