# Contributing to Cable Modem Monitor

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Ways to Contribute

- 🐛 Report bugs via [GitHub Issues](https://github.com/solentlabs/cable_modem_monitor/issues)
- 💡 Suggest features or improvements
- 📝 Improve documentation
- 🧪 Add support for additional modem models
- 🔧 Submit bug fixes or enhancements
- 🌍 Help translate the integration (see [Translations](#translations) below)

---

## Adding Modem Support

There are two paths, depending on what you can do:

- **HA user requesting support for your modem** — see
  [docs/MODEM_REQUEST.md](./docs/MODEM_REQUEST.md). Capture a HAR,
  screen it for PII, file a request.
- **Have AI access and want to help expand the catalog** — see
  [AI-Assisted Catalog Contribution](#ai-assisted-catalog-contribution)
  below. Analyze captures, propose catalog entries, triage incoming
  requests.

Either path is valuable. The catalog includes modems the maintainer
can't physically test — community contribution is how it grows.

---

## Development Environment

See the [Getting Started Guide](./docs/setup/GETTING_STARTED.md) for
environment setup. Come back here once you can run `make validate`.

### Format, Lint, Test

Day-to-day, the workflow runs through VS Code tasks
(`Ctrl+Shift+P` → `Tasks: Run Task`):

- **🎨 Format Code** — auto-format on demand
- **🧪 Test: All** — full test suite (Core, Catalog, HA)
- **⚡ Test: Quick** — fast feedback during development

Linting runs continuously in the **PROBLEMS** tab via the Ruff, mypy,
and Pyright extensions — keep it at zero.

For terminal use, `make format` / `make check` / `make test` cover the
same ground. Pre-commit hooks check formatting, linting, type-check,
and PII at commit time. See [Submitting Changes](#submitting-changes)
below for the pre-push gate.

### Test on Local HA

VS Code tasks bring up a local Home Assistant container with the
integration bind-mounted:

- **🚀 HA: Start** — start HA at <http://localhost:8123>
- **🚀 HA: Start (Debug)** — same, with `custom_components.cable_modem_monitor`
  at DEBUG log level
- **📋 HA: View Logs** — tail the HA log
- **⏹️ HA: Stop** — shut down the container

To test a PR, `gh pr checkout NNN` then run **🚀 HA: Start**.

If you need to test the real HACS install or update path instead of the
bind-mounted dev workflow, use the separate guide at
[docs/setup/TESTING_VIA_HACS.md](./docs/setup/TESTING_VIA_HACS.md). Keep that
workflow on a dedicated HACS testing branch rather than on the normal
feature branch, especially when you need a simple way to test Python
package changes on a non-dev system through commit-pinned manifest
requirements.

## Project Architecture

The codebase is split into three layers:

| Package | Path | Responsibility |
|---------|------|----------------|
| **Core** | `packages/cable_modem_monitor_core/` | Auth, HTTP loading, parsing, orchestration, test harness. Platform-agnostic — no HA imports. |
| **Catalog** | `packages/cable_modem_monitor_catalog/` | Modem configs (`modem.yaml`), parsers (`parser.yaml` / `parser.py`), HAR fixtures and golden files. |
| **HA Adapter** | `custom_components/cable_modem_monitor/` | Config flow, sensors, services, coordinators. Thin wrapper that imports from Core and Catalog. |

Core and Catalog are published to PyPI as standalone packages. The HA
adapter declares them as dependencies in `manifest.json`.

**Specs** (authoritative design docs):

- Core: [`packages/cable_modem_monitor_core/docs/`](packages/cable_modem_monitor_core/docs/) — architecture, auth, parsing, orchestration, onboarding
- HA: [`custom_components/cable_modem_monitor/docs/`](custom_components/cable_modem_monitor/docs/) — config flow, entities, adapter wiring

**Tests:**

- Core + Catalog: `pytest` in each package's `tests/` directory (not from repo root)
- HA integration: `pytest` at repo root (`tests/`)

## AI-Assisted Catalog Contribution

The maintainer doesn't have access to most of the modems in the
catalog. Catalog growth depends on contributors who have the hardware
and on AI tools that lower the bar to analyzing captures and proposing
entries. This section is for that audience.

If you have AI access (Claude, ChatGPT, or similar with file
attachment support), you can do significantly more than file a request:

- **Audit your own HAR** for completeness before submitting (prompt
  in the next section).
- **Run the intake pipeline** on a HAR — yours or one attached to a
  stalled issue — and open a PR with the resulting catalog entry. See
  [MODEM_INTAKE_WORKFLOW.md](packages/cable_modem_monitor_catalog_tools/docs/MODEM_INTAKE_WORKFLOW.md).
- **Comment on stalled issues** with HAR audit results so other
  contributors can pick them up.
- **Analyze logs** from bug reports to identify patterns.

### Auditing a HAR for completeness

The most common reason a HAR is unusable is that it was recorded
against an already-logged-in browser session — the auth flow is
missing. Attach the `.sanitized.har` to your AI assistant and run this
prompt:

````text
You are auditing a HAR capture from a cable modem's web interface.
The capture will be used to build a parser, so it needs to contain
the full HTTP conversation including any login flow.

Please inspect the attached HAR and answer these questions in order.
Output a fenced markdown block I can paste into a GitHub issue.

1. Total number of entries (requests) in the HAR.
2. Is there evidence of authentication in the capture? Look for any
   of: a POST request whose URL contains "login", "auth", "session",
   "hnap", or "admin"; a POST carrying form-encoded credentials in
   the body; or any request carrying an `Authorization` header
   (which is how HTTP Basic Auth modems present credentials). List
   what you find (URL + method + which signal). Note: HNAP-style
   modems POST to `/HNAP1/` for normal operations too, so listing
   all of them is fine — presence is what matters.
3. Does the FIRST request to the modem carry a Cookie header? On
   its own this is a hint, not proof — but combined with the
   *absence* of any authentication evidence in question 2, it
   strongly suggests the capture was recorded against an already
   logged-in session.
4. How many distinct data-bearing responses are present? Count
   responses whose Content-Type starts with "text/html",
   "application/json", "application/xml", or "text/xml". List the
   paths.
5. Do any responses look truncated or empty (response body size
   under 200 bytes)? List them — small responses are sometimes
   legitimate (status pings, redirects), so this is an FYI, not a
   failure on its own.
6. Overall verdict: PASS / RECAPTURE NEEDED / UNCERTAIN, with a
   one-sentence reason.

Format the output exactly like this:

```
## HAR audit

- Entries: <N>
- Authentication evidence: <list or "none found">
- First-request cookie: <yes/no>
- Data-bearing responses: <count> — <paths>
- Small responses (FYI): <list or "none">
- Verdict: <PASS | RECAPTURE NEEDED | UNCERTAIN> — <reason>
```
````

**PASS** → continue to the intake pipeline. **RECAPTURE NEEDED** →
recapture using an incognito/private browsing window so the modem
forces a fresh login. **UNCERTAIN** → submit anyway with the audit
output included.

A capture with no authentication evidence *and* a Cookie header on the
first request is almost certainly post-auth and won't produce a working
parser.

### The intake pipeline

The `cable_modem_monitor_catalog_tools` package contains the intake
pipeline — a deterministic toolchain that validates HAR captures,
detects auth strategy, classifies response formats, generates
`modem.yaml` and `parser.yaml`, and produces golden files.

- [Intake Pipeline overview](packages/cable_modem_monitor_catalog_tools/docs/INTAKE_PIPELINE.md)
- [Modem Intake Workflow](packages/cable_modem_monitor_catalog_tools/docs/MODEM_INTAKE_WORKFLOW.md)
- [Onboarding Spec](packages/cable_modem_monitor_catalog_tools/docs/ONBOARDING_SPEC.md)

The catalog tools package is never installed by Home Assistant — it's
a developer accelerator for catalog growth, open to contributors with
hardware. The pipeline mechanics are plain Python; the judgment work
(format detection on ambiguous HTML, metadata enrichment, test failure
diagnosis) realistically benefits from AI assistance — that's what
this section's audience brings to the table.

Modem configurations live in the catalog package
(`packages/cable_modem_monitor_catalog/`). Each modem has a
`modem.yaml`, `parser.yaml`, and `test_data/` directory with a HAR
capture and golden file.

## Code Style

- Follow [PEP 8](https://pep8.org/) style guidelines
- Use type hints where appropriate
- Add docstrings to functions and classes
- Keep functions focused and small
- Use async/await for I/O operations

## Submitting Changes

Standard fork → branch → PR flow.

**Inner loop**: `make test` (or VS Code's **🧪 Test: All** task) for
quick iteration. Runs the package and integration test suites — same
pytest CI runs, but it's a *subset* of the full CI gate.

**Pre-push gate**: `make validate-ci`. This is the canonical local
mirror of the CI Tests workflow — lint, format, type-check, tests,
intake regression, PII check, and catalog README freshness. If
`make validate-ci` is green, CI will be green. Pre-push hooks run a
subset, so failures still surface, but `make validate-ci` is the
definitive local check.

`scripts/release.py` runs `make validate-ci` automatically as part of
every version bump, so a release can never silently land on top of
regressions that accumulated since the last bump.

PRs that touch a modem (parser, catalog entry) should follow the
[AI-Assisted Catalog Contribution](#ai-assisted-catalog-contribution)
flow above. Reference issues with `Related to #X` or `Addresses #X` —
never `Fixes #X` (see [Issue Closing Policy](#issue-closing-policy)).
Update CHANGELOG.md when relevant.

### Issue Closing Policy

**No issue is ever auto-closed.** Don't use `Fixes #X`, `Closes #X`,
or `Resolves #X` in PR bodies or commit messages — GitHub auto-closes
from any commit message in a merge, including buried references. Use
`Related to #X` or `Addresses #X` instead.

Closing requires either an artifact proving the fix worked, or a
deliberate manual close by the maintainer (when the reporter has left
the conversation — not automatic).

- **Bug or defect** — artifact is the reporter confirming the fix on
  their hardware.
- **Modem support request** — closing requires:
  - **From the user:** sanitized HAR capture (`modem.har`) and
    verified diagnostics (`modem.verified.json`)
  - **Derived from the HAR:** `modem.yaml`, `parser.yaml`, optionally
    `parser.py`, and `modem.expected.json`
  - **Gate:** all of the above pass the regression test suite before
    the branch merges

### Commit Message Format

Use clear, descriptive commit messages:

```text
Add support for Arris TG1682G modem

- Added HTML parser for Arris status page format
- Created test fixtures from real modem output
- Updated documentation with supported models
- All existing tests still pass
```

## Issue Labels

State labels (`needs-triage`, `in-development`, `needs-testing`,
`needs-data`, `backlog`) are mutually exclusive — exactly one
applies. Same for `release:vX.Y` labels. Everything else stacks.

- `needs-triage` — auto-applied; replaced with a real state on first read
- `in-development` — code being written or in an unreleased branch
- `needs-testing` — released and installable; user can verify now
- `needs-data` — waiting on user for HAR / diagnostics / clarification
- `backlog` — acknowledged, not actively prioritized

`needs-testing` is not applied until the code is released. A parser on
an unreleased branch is `in-development` even when complete. Apply
`release:vX.Y` when the work is committed to that release (branch cut,
or merged); all `release:vX.Y` descriptions read "Tagged for vX.Y."

When a user confirms a modem parser works on real hardware, the modem
is promoted per the
[promotion procedure in MODEM_DIRECTORY_SPEC.md](packages/cable_modem_monitor_core/docs/MODEM_DIRECTORY_SPEC.md#promotion-procedure).

## Release Process

Maintainers handle releases following semantic versioning. See
[Release Process](docs/reference/RELEASING.md) for the full workflow
including the `release.py` script and step-by-step instructions.

## Code of Conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Attribution

When adding a parser informed by external code or research, document
the source in the parser docstring and add an entry to
[docs/ATTRIBUTION.md](docs/ATTRIBUTION.md). For how to phrase external
influence honestly — especially when AI tools were involved — see
[Attribution Standards](docs/ATTRIBUTION.md#attribution-standards).

Data contributors, testers, and external references are credited in
ATTRIBUTION.md.

---

## Questions?

- 🐛 Report issues via [GitHub Issues](https://github.com/solentlabs/cable_modem_monitor/issues)
- 📧 Contact maintainers via GitHub

## Resources

- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [HACS Documentation](https://hacs.xyz/)
- [Python asyncio](https://docs.python.org/3/library/asyncio.html)
- [pytest Documentation](https://docs.pytest.org/)

---

## Translations

> **📖 See [Translation Guide](docs/TRANSLATION_GUIDE.md)** for complete instructions.

**12 languages supported:** English, German, Dutch, French, Chinese, Italian, Spanish, Polish, Swedish, Russian, Portuguese (Brazil), Ukrainian

**To add a language:** Copy `translations/en.json` → `translations/XX.json`, translate values (not keys), submit PR.

Thank you for contributing to Cable Modem Monitor!
