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

## Help Us Add Your Modem

**Don't see your modem supported?** You can help us add it by capturing a HAR file from your modem's web interface.

> **See the [Modem Request Guide](./docs/MODEM_REQUEST.md)** for complete instructions on capturing data, reviewing for PII, and submitting your request.

**Quick summary:**

1. Capture your modem's login and status pages with [har-capture](https://github.com/solentlabs/har-capture)
2. **Review the capture for your WiFi credentials** - automated sanitization isn't perfect
3. [Open a modem request issue](https://github.com/solentlabs/cable_modem_monitor/issues/new?template=modem_request.yml)

Your HAR capture becomes the test fixture that lets us develop and verify the parser without physical access to your modem.

---

## Development Environment

This project uses **Git LFS** for large test fixtures (HAR captures).
Install it before cloning — see the
[Getting Started Guide](./docs/setup/GETTING_STARTED.md) for details.

See the **[Getting Started Guide](./docs/setup/GETTING_STARTED.md)** for
complete environment setup. It covers Local Python, Dev Container, and
WSL2 paths in a single document. Come back here once you can run
`make validate`.

> **Windows users:** WSL2 is required. The Getting Started Guide covers this.

### Write Your Code

Make your code changes or additions on a new branch.

### Format and Lint

Before committing, ensure your code is well-formatted and passes all quality checks.

**Recommended Workflow:**

```bash
# Option 1: Smart commit helper (formats, checks, and commits)
./scripts/dev/commit.sh "your commit message"

# Option 2: Manual workflow
make format        # Auto-format code
make quick-check   # Fast checks (lint + format)
make check         # Full checks (lint + format + type-check)
git add -A
git commit -m "your message"
```

**Quick commands (using Make):**

```bash
# Run all code quality checks
make check         # Full checks (recommended before push)

# Quick checks (faster, skips type-check)
make quick-check

# Auto-fix linting issues
make lint-fix

# Format code
make format

# Run comprehensive linting (includes security)
make lint-all
```

### What Runs Automatically

`setup.sh` installs all hooks. Here's what they do:

**On commit** (pre-commit):

- Code formatting (Black) and linting (Ruff) with auto-fix
- Type checking (mypy, pyright) on Core/Catalog packages
- File checks: trailing whitespace, YAML/JSON validation, large files
- Custom: commit email privacy, changelog reminder, PII in test fixtures

**On commit message** (commit-msg):

- Conventional commit format validation

**On push** (pre-push):

- Full project lint (`ruff check .`)
- Full test suite (`pytest`)
- This takes 1-2 minutes — it's intentional, not stuck

If a hook fails, read the error output — it usually explains what to fix.
Run `make format` to auto-fix most formatting issues.

```bash
# Run all hooks manually on all files
pre-commit run --all-files
```

### Run Tests

```bash
make test    # Runs all three test suites (HA, Core, Catalog)
```

For a specific package:

```bash
pytest tests/ -v                                                      # HA only
cd packages/cable_modem_monitor_core && pytest tests/ -v && cd ../..  # Core only
```

### Test on Local HA (Optional)

You can test your changes on a local Home Assistant instance via Docker:

```bash
# Start HA with integration bind-mounted
make docker-start

# Open http://localhost:8123 and add the integration
# After code changes, restart to pick them up:
make docker-restart
```

**Testing a PR:**

```bash
gh pr checkout XX
make docker-start
```

**Debug logging** — add this to your HA `configuration.yaml` to see
detailed integration logs:

```yaml
logger:
  default: warning
  logs:
    custom_components.cable_modem_monitor: debug
```

Then check Settings → System → Logs after restarting.

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

## Adding Support for New Modem Models

**For users:** Submit a HAR capture via the [Modem Request Guide](docs/MODEM_REQUEST.md). This is the primary onboarding path.

**For developers:** New modems are onboarded through the MCP intake pipeline. The pipeline validates HAR captures, detects auth strategy, generates modem/parser configs, and produces golden files. See [Intake Pipeline](packages/cable_modem_monitor_catalog/docs/INTAKE_PIPELINE.md) for an overview, or [ONBOARDING_SPEC.md](packages/cable_modem_monitor_core/docs/ONBOARDING_SPEC.md) for the full specification.

Modem configurations live in the catalog package (`packages/cable_modem_monitor_catalog/`). Each modem has a `modem.yaml`, `parser.yaml`, and `test_data/` directory with a HAR capture and golden file.

## Code Style

- Follow [PEP 8](https://pep8.org/) style guidelines
- Use type hints where appropriate
- Add docstrings to functions and classes
- Keep functions focused and small
- Use async/await for I/O operations

### Linting

Run `make check` for all code quality checks, or `make quick-check` for
a faster pass. See [Linting Guide](docs/reference/LINTING.md) for
individual tool commands and configuration.

## Testing Guide

`make test` runs all three test suites (HA integration, Core, Catalog).
See [Run Tests](#run-tests) above for per-package commands.

## Submitting Changes

### Pull Request Process

1. **Fork the repository** and create a feature branch

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following code style guidelines

3. **Add/update tests** for your changes

4. **Run the test suite**

   ```bash
   pytest tests/ -v
   cd packages/cable_modem_monitor_core && pytest tests/ -v && cd ../..
   ```

5. **Update documentation** if needed (README.md, CHANGELOG.md)

6. **Commit your changes** with clear commit messages

   ```bash
   git commit -m "Add support for Arris TG1682G modem"
   ```

7. **Push to your fork** and create a pull request

   ```bash
   git push origin feature/your-feature-name
   ```

### Pull Request Guidelines

- **Clear description**: Explain what changes you made and why
- **Link issues**: Reference any related GitHub issues (see Issue Closing Policy below)
- **Test results**: Include test output showing all tests pass
- **Screenshots**: For UI changes, include before/after screenshots
- **Documentation**: Update README, CHANGELOG, or other docs as needed

### Issue Closing Policy

**Important**: Developers should NEVER auto-close user-reported issues via PR keywords like "Fixes #123" or "Closes #456".

**Auto-close is ONLY appropriate for:**

- ✅ Developer-only improvements (code refactoring, test improvements)
- ✅ Quality of life enhancements for developers
- ✅ Documentation-only updates
- ✅ CI/CD pipeline improvements
- ✅ Development tooling updates

**User validation REQUIRED for:**

- ❌ Bug fixes affecting user experience
- ❌ New modem support or parser changes
- ❌ Authentication or connection handling
- ❌ Any feature that changes integration behavior
- ❌ Performance or reliability improvements

**How to link issues without auto-closing:**

```markdown
# ❌ DO NOT use these keywords (they auto-close):
Fixes #123
Closes #456
Resolves #789

# ✅ USE these phrases instead:
Addresses #123
Related to #456
Implements changes for #789
See #123 (awaiting user validation)
```

**Why this matters:**

- Users need to test and validate fixes in their environment
- What works in tests may not work with all modem firmware versions
- User feedback helps catch edge cases and regressions
- Maintainers manually close issues after user confirmation

**After the PR is merged:**

1. Comment on the issue linking to the release
2. Request user testing and validation
3. Wait for user confirmation
4. Maintainer manually closes the issue after validation

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

### Our Standards

- Be respectful and inclusive
- Welcome newcomers and help them learn
- Focus on what is best for the community
- Show empathy towards others

### Unacceptable Behavior

- Harassment, discrimination, or offensive comments
- Trolling or insulting comments
- Publishing others' private information
- Unprofessional conduct

## Attribution Policy

We believe in giving credit where credit is due. This section outlines how we acknowledge contributions.

### Data Contributors

Users who provide modem captures for new parser development are acknowledged in:

| Location | What's Credited |
| ---------- | ----------------- |
| Fixture README | Name, modem model, capture date |
| Parser `verification_source` | Issue link after user confirms working |
| Release notes | When parser ships |

### External Code & Inspiration

When we reference external implementations to understand modem protocols or authentication:

1. **Document the source** in the parser docstring:

   ```python
   """
   Motorola MB8611 parser for Cable Modem Monitor.

   Auth implementation informed by:
   - BowlesCR/MB8600_Login: https://github.com/BowlesCR/MB8600_Login

   See ATTRIBUTION.md for full credits.
   """
   ```

2. **Add to ATTRIBUTION.md** with:
   - Project name and author
   - Repository URL
   - What we learned from it
   - License acknowledgment

3. **We learn from, not copy** - External references inform our approach, but we implement in our own architecture with proper attribution.

### AI-Assisted Development

When using AI tools during development, additional care is needed for attribution:

1. **Review all attributions before committing** - AI may add plausible-sounding citations that weren't actually referenced during development.

2. **Verify you can answer "how did we use this?"** - If you can't explain the specific influence, use softer framing instead of claiming direct learning.

3. **Data contributors are verifiable** - Issue numbers, forum posts, and HAR captures can be traced. External code references added by AI may not be.

#### Honest Framing Levels

| Framing | Use When | Example |
| --------- | ---------- | --------- |
| "Based on" / "Informed by" | You directly studied their code or docs | BowlesCR's HMAC-MD5 auth flow |
| "Field definitions from" | You verified specific details came from them | Tatsh's StatusSoftwareSfVer fields |
| "Related prior art" | Similar work exists, can't verify direct influence | Projects doing similar modem monitoring |

#### When In Doubt

- **Don't remove existing attribution** - Removing credit looks worse than over-crediting
- **Soften the language** - Change "Based on" to "Related prior art"
- **Document the uncertainty** - Note in your tracker that influence couldn't be verified

### Testers & Validators

Users who test pre-release parsers and confirm functionality:

| Contribution | Acknowledgment |
| -------------- | ---------------- |
| Confirms parser works | Parser marked "Verified", issue closed with thanks |
| Reports bugs during testing | Credited in fix commit |
| Provides additional captures | Added to fixture README |

### Our Commitment

- ✅ Credit external research and code references
- ✅ Acknowledge all data contributors
- ✅ Thank testers who validate our work
- ✅ Respect open source licenses
- ✅ Reach out to original authors when heavily referencing their work

### If We Missed You

If we've used your work without proper attribution or forgot to credit your contribution:

1. We apologize - it was unintentional
2. Please [open an issue](https://github.com/solentlabs/cable_modem_monitor/issues) or contact us
3. We'll add proper attribution immediately

See [ATTRIBUTION.md](./docs/ATTRIBUTION.md) for the full list of credits.

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
