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
same ground. `./scripts/dev/commit.sh "message"` runs format → check →
commit in one step. Pre-commit hooks check formatting, linting,
type-check, and PII; pre-push hooks run the full lint and test suite
(1–2 minutes).

### Test on Local HA

VS Code tasks bring up a local Home Assistant container with the
integration bind-mounted:

- **🚀 HA: Start** — start HA at http://localhost:8123
- **🚀 HA: Start (Debug)** — same, with `custom_components.cable_modem_monitor`
  at DEBUG log level
- **📋 HA: View Logs** — tail the HA log
- **⏹️ HA: Stop** — shut down the container

To test a PR, `gh pr checkout NNN` then run **🚀 HA: Start**.

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

- Audit your own HAR capture for completeness before submitting
- Walk an incoming HAR through the intake pipeline and propose a
  catalog entry
- Triage user-submitted HARs and give feedback on quality
- Analyze logs from bug reports to identify patterns

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

The catalog tools package is maintainer-only and never installed by
Home Assistant — it's a developer accelerator for catalog growth.

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

Standard fork → branch → PR flow. Before pushing: `make check` and
`make test` (or VS Code's **🧪 Test: All** task) — pre-push hooks will
run them anyway, but catching failures locally is faster.

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

- 💬 Open a [GitHub Discussion](https://github.com/solentlabs/cable_modem_monitor/discussions)
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
