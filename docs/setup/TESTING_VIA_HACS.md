# Testing via HACS

Use this guide when you need to test the real Home Assistant install
path through HACS instead of the local bind-mounted dev workflow.

The primary reason this workflow exists is that manually testing Python
package changes on a non-dev Home Assistant system is complicated. This
is a simple way to do it with a small number of controlled changes.

## When to use this workflow

Use a HACS-backed test instance when you need to verify one or more of
these:

- you need a simple way to test Core and Catalog package changes on a
  non-dev system
- the manifest requirement refs point at the exact package code you want
  Home Assistant to pull in
- HACS can see and install the branch correctly
- update and restart behavior matches a real HACS install
- manual regression testing should happen without the dev bind-mount path

Do not use this workflow for normal code-test iteration. It is slower,
more stateful, and easier to misconfigure than the standard dev
container flow.

## Core rules

- Use a separate Home Assistant test instance
- Keep HACS-only changes on a dedicated testing branch
- Never merge HACS-only manifest or `hacs.json` changes into the normal
  feature branch
- After testing, move only the real product commits back to the normal
  branch

The HACS test branch exists to make the install path testable. It is not
the source of truth for the feature itself.

## Recommended branch layout

Use two branches:

- normal feature branch, for example `fix-entity-cleanup-hardening`
- HACS testing branch, for example `hacs-test/fix-entity-cleanup-hardening`

The feature branch contains only the real code, test, and documentation
changes. The HACS testing branch layers temporary install-specific
changes on top.

## Prepare a separate Home Assistant instance

Use a dedicated HA instance for testing via HACS. Do not reuse your main
dev container state if you want reliable install and update results.

The goal is to test the same sequence a user would take:

1. Add the repository in HACS
2. Select the HACS testing branch
3. Install or update the integration through HACS
4. Restart Home Assistant
5. Verify setup, reload, and feature behavior

If you need to repeat the test from scratch, reset the test instance so
old install state does not hide packaging problems.

## Prepare the HACS testing branch

On the HACS testing branch, update the install surface so HACS pulls the
exact package code under test.

### `manifest.json`

To make this workflow test package changes, the manifest requirements
must point at the exact HACS test branch commit you want Home Assistant
to use. That is the key change that brings in the matching Core and
Catalog package code.

Example pattern:

```json
"requirements": [
  "solentlabs-cable-modem-monitor-core @ git+https://github.com/<owner>/cable_modem_monitor.git@<commit>#subdirectory=packages/cable_modem_monitor_core",
  "solentlabs-cable-modem-monitor-catalog @ git+https://github.com/<owner>/cable_modem_monitor.git@<commit>#subdirectory=packages/cable_modem_monitor_catalog"
],
"version": "3.14.0-beta.906"
```

In this example:

- both package requirements point at the same repo commit
- that commit is the HACS test branch commit you want Home Assistant to
  pull in for package testing
- the manifest version is bumped so HACS sees a new installable build

Rules:

- point both package requirements at the same commit
- use the exact branch HEAD commit you are testing
- bump the manifest version so HACS sees a new installable version

These changes are temporary and belong only on the HACS testing branch.

### `hacs.json`

Set the repository metadata to match branch-based testing rather than
release-zip installation.

In the current testing flow, that means using branch installation rather
than a release zip.

Example shape:

```json
{
  "name": "Cable Modem Monitor",
  "render_readme": true,
  "homeassistant": "2024.12.0",
  "hacs": "2.0.0",
  "zip_release": false,
  "hide_default_branch": true
}
```

Only make the minimum HACS metadata changes needed for the test.

## Install through HACS

In the HA test instance:

1. Add the repository as a custom repository in HACS
2. Select the HACS testing branch
3. Install the integration
4. Restart Home Assistant
5. Confirm the integration loads and dependencies resolve cleanly

If the branch is already installed, use HACS to update to the new branch
version, then restart again and verify the upgrade path.

## What to verify

At minimum, check:

- Home Assistant is running with the expected Core and Catalog package
  commit
- HACS sees the expected version
- install completes without dependency resolution errors
- Home Assistant starts cleanly after install or update
- the integration loads and config entries behave correctly
- the specific feature or fix under test behaves correctly in the HA UI

For lifecycle or migration work, also verify:

- restart behavior after install
- reload behavior after options changes
- migrated-entry behavior if the change is upgrade-sensitive

## After testing

Once HACS-based testing is complete:

1. Keep the HACS testing branch for traceability if needed
2. Move only the real product commits back to the normal feature branch
3. Leave HACS-only manifest and `hacs.json` commits behind

If a small real code fix was discovered during testing via HACS, replay
that code fix directly onto the normal feature branch instead of
carrying the temporary install commit history with it.

## Common mistakes

- Testing on the normal feature branch instead of a dedicated HACS branch
- Updating only one requirement ref instead of both package refs together
- Forgetting that the package test depends on commit-pinned requirement
  refs in `manifest.json`
- Forgetting to bump the manifest version after changing the requirement
  commit
- Treating HACS-only commits as product commits and moving them back to
  the main feature branch
- Reusing stale HA test state and assuming install/update behavior is
  clean

## Related docs

- [Getting Started](GETTING_STARTED.md)
- [Project documentation index](../README.md)
- [Contributing guide](../../CONTRIBUTING.md)
