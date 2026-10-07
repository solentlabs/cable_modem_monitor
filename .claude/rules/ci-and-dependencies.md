---
paths:
  - ".github/workflows/**"
  - "Makefile"
  - "**/pyproject.toml"
  - "requirements*.txt"
---

# CI, validate-ci and dependency floors

Loads when a workflow, the Makefile or a dependency file is touched. The
push gate itself is CLAUDE.md § Before a push.

## `validate-ci` green does not guarantee CI green

It mirrors what CI runs, not where CI runs it. Per-job settings in
`.github/workflows/` (`lfs:`, path filters, fresh-clone state) are
invisible locally, where the repo is complete and LFS content always
present. When a change alters what a script *reads*, check the
checkout step of the job that runs it.

## Adding a new CI job: local-mirror rule

Whenever you add a new job or step to `.github/workflows/tests.yml`,
add a corresponding Makefile target and wire it into `make validate-ci`
as a dependency. Every CI check must have a local-mirror command. The
two together are a single change, not a CI change with a "follow up"
Makefile change. Drift between CI and local is what hides regressions
until tag time (see alpha.17 retrospective).

If the job name is listed as a required status check in the
`require-status-checks` repository ruleset, update the ruleset at the
same time. The ruleset is a plain string match; it has no awareness of
the workflow files. Rename drift silently breaks every subsequent PR
(shows "Expected — Waiting for status to be reported" on required
checks). Update via
`gh api repos/solentlabs/cable_modem_monitor/rulesets/10547747 --method PUT --input <payload>`.

Exceptions: external GitHub Actions that can't be reasonably reproduced
locally (e.g., `home-assistant/actions/hassfest@master`, which requires
HA core source and Docker). Document the exception in the Makefile
comment so future-you knows why `validate-ci` doesn't cover it.

## Owned-deps check

`validate-ci` ends with `scripts/check_owned_deps.py`, which reports only
packages declared in our requirements files and pyproject.toml, not the
transitive HA or test-harness tree. When it shows drift, propose a
separate deps-update commit before pushing.

## HA compatibility gate

`validate-ci` runs `scripts/check_ha_compat.py` (mirrored by the
`ha-compat-check` CI job), which validates that every floor declared in
Core and Catalog's `pyproject.toml` is satisfiable under HA's
`package_constraints.txt`. This is a hard gate: exit non-zero blocks the
push. Never bump a floor in a published package's pyproject.toml above
what HA constrains without first verifying compatibility (the beta.4
incident: `requests>=2.34.2` and `pyyaml>=6.0.3` both exceeded HA's
pins).

## Optional pre-push hook: opt-in, suggest at the right moment

`make install-hooks` installs an opt-in `.git/hooks/pre-push` that runs
`make validate-ci` automatically before every push (chained after
`git lfs pre-push`). It is not committed-by-default: CI is the
authoritative gate, and forcing the hook on every developer would create
install-state inconsistency without adding any enforcement CI doesn't
already provide.

**When to suggest it:** after a developer hits a CI failure that
`make validate-ci` would have caught locally (coverage drop, lint miss,
missing local-mirror), suggest `make install-hooks` *once*. Do not
repeat the suggestion if they decline, and do not suggest it on fresh
clones or on every validate-ci run; that becomes noise.
