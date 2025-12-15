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

## 📡 Help Us Add Your Modem

**Don't see your modem supported?** You can help us add it by capturing data from your modem's web interface.

> **📖 See the [Modem Request Guide](./docs/MODEM_REQUEST.md)** for complete instructions on capturing data, reviewing for PII, and submitting your request.

**Quick summary:**
1. Capture your modem's web pages (two methods available)
2. **Review the capture for your WiFi credentials** - automated sanitization isn't perfect
3. [Open a modem request issue](https://github.com/solentlabs/cable_modem_monitor/issues/new?template=modem_request.yml)

Your captured data becomes a test fixture that lets us develop and verify the parser without physical access to your modem.

---

## Development Workflow

You can develop using either a **local Python environment** (fastest) or a **VS Code Dev Container** (guaranteed consistency).

> **📖 See [Getting Started Guide](./docs/setup/GETTING_STARTED.md)** for comprehensive setup instructions, decision tree, and troubleshooting.

### Docker Development (Recommended)

Docker provides an isolated, consistent development environment with Home Assistant pre-installed.

#### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop) installed and running
- [VS Code](https://code.visualstudio.com/) (optional, for Dev Container support)

#### Quick Start

```bash
# Clone the repository
git clone https://github.com/solentlabs/cable_modem_monitor.git
cd cable_modem_monitor

# Start Home Assistant with the integration
make docker-start
# Or: ./scripts/dev/docker-dev.sh start

# View logs
make docker-logs

# Access Home Assistant at http://localhost:8123
```

#### VS Code Dev Container (Optional)

For the best development experience, use VS Code with Dev Containers:

**1. Install the Dev Containers extension** (choose any method):

- **From VS Code**: Open Extensions (`Ctrl+Shift+X`), search "Dev Containers", click Install
- **Quick Install**: Press `Ctrl+P`, paste: `ext install ms-vscode-remote.remote-containers`
- **Command Line**: `code --install-extension ms-vscode-remote.remote-containers`
- **From Marketplace**: Visit https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers

**2. Verify installation**: You should see a "Remote Explorer" icon in the sidebar and "Dev Containers:" commands when pressing `F1`

**3. Open the project** in VS Code and reopen in container:
- Open the project: `code /path/to/cable_modem_monitor`
- Press `F1` → "Dev Containers: Reopen in Container"
- Wait for the container to build (2-3 minutes first time)

See [Getting Started Guide](./docs/setup/GETTING_STARTED.md) or [VS Code Dev Container Guide](./docs/setup/DEVCONTAINER.md) for detailed instructions and troubleshooting.

#### Docker Commands

```bash
# Using Make (recommended)
make docker-start      # Start the environment
make docker-stop       # Stop the environment
make docker-restart    # Restart after code changes
make docker-logs       # View logs
make docker-status     # Check status
make docker-shell      # Open a shell in the container
make docker-clean      # Remove all data

# Or use the script directly
./scripts/dev/docker-dev.sh [command]
```

#### Docker Development Workflow

1. **Start the environment**: `make docker-start`
2. **Make code changes** in your editor
3. **Restart to load changes**: `make docker-restart`
4. **Test in Home Assistant**: http://localhost:8123
5. **Run tests**: Open a shell with `make docker-shell`, then run `pytest`

### Local Development (Advanced)

For developers who prefer working directly with Python without Docker:

#### 1. Set Up Your Environment

First, clone the repository and install the development dependencies. This will give you all the tools you need for testing, linting, and code formatting.

```bash
git clone https://github.com/solentlabs/cable_modem_monitor.git
cd cable_modem_monitor

# Option 1: Use the automated setup script (recommended)
./scripts/setup.sh

# Option 2: Manual installation
pip install -r requirements-dev.txt  # Comprehensive dev dependencies (includes types, linters, pre-commit)
pre-commit install  # Install git hooks for automatic code formatting
```

**Having environment issues?** See [Getting Started Guide](./docs/setup/GETTING_STARTED.md) for:
- Comprehensive troubleshooting
- Environment comparison and decision tree
- Platform-specific notes
- Switching between environments

**Testing fresh developer experience?** Run `python scripts/dev/fresh_start.py` to reset VS Code state.

### 2. Write Your Code

Make your code changes or additions on a new branch.

### 3. Format and Lint

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

**Manual commands:**
```bash
# Auto-format your code with Black
black custom_components/cable_modem_monitor/

# Check for linting issues with Ruff
ruff check custom_components/cable_modem_monitor/

# Auto-fix linting issues
ruff check --fix custom_components/cable_modem_monitor/

# Type checking with mypy
mypy custom_components/cable_modem_monitor/

# Or use the comprehensive lint script
bash scripts/dev/lint.sh
# On Windows PowerShell:
# .\scripts\dev\lint.ps1
```

**Automated Quality Checks:**

The repository includes a **pre-push hook** that automatically runs quality checks before pushing to GitHub. This prevents CI failures by catching issues locally.

```bash
# The pre-push hook runs automatically and checks:
# - Code formatting (Black)
# - Linting (Ruff)

# To skip the hook in emergencies (not recommended):
git push --no-verify
```

**Pre-commit hooks (alternative method):**
```bash
# Install pre-commit hooks (runs automatically on commit)
pip install pre-commit
pre-commit install

# Run manually on all files
pre-commit run --all-files

# Note: May have permission issues in WSL environments
```

### 4. Run Tests

Make sure all tests pass before submitting your changes.

```bash
pytest tests/ -v
```

### 5. Deploy for Manual Testing (Optional)

You can deploy your changes to a real Home Assistant instance for manual testing.

```bash
# Interactive mode - guides you through deployment options
./scripts/deploy_updates.sh

# Or specify directly:
./scripts/deploy_updates.sh --local ~/homeassistant/config
./scripts/deploy_updates.sh --ssh root@192.168.1.100
./scripts/deploy_updates.sh --docker homeassistant --restart
```

See [Testing on HA](./docs/setup/TESTING_ON_HA.md) for detailed instructions and troubleshooting.

## Adding Support for New Modem Models

> **📖 See [Parser Guide](docs/reference/PARSER_GUIDE.md)** for complete instructions.

**Quick overview:**
1. Capture HTML from your modem's status pages
2. Create parser in `parsers/<manufacturer>/<model>.py` (extend `ModemParser`)
3. Add test fixtures with `metadata.yaml` (see [Fixture Format](docs/reference/FIXTURE_FORMAT.md))
4. Write tests - the plugin system auto-discovers your parser

**Example parsers:** `arris/sb6141.py` (simple), `motorola/mb7621.py` (form auth), `technicolor/xb7.py` (complex)

## Code Style

- Follow [PEP 8](https://pep8.org/) style guidelines
- Use type hints where appropriate
- Add docstrings to functions and classes
- Keep functions focused and small
- Use async/await for I/O operations

### Linting

The project uses multiple linting tools for code quality:

**Ruff** (Primary linter - fast and comprehensive):
```bash
# Check for issues
ruff check custom_components/cable_modem_monitor/

# Auto-fix issues
ruff check --fix custom_components/cable_modem_monitor/
```

**mypy** (Type checking):
```bash
mypy custom_components/cable_modem_monitor/ --config-file=mypy.ini
```

**Black** (Code formatting):
```bash
# Format code
black custom_components/cable_modem_monitor/

# Check formatting (CI mode)
black --check custom_components/cable_modem_monitor/
```

**Comprehensive linting:**
```bash
# Run all checks at once
make check

# Or use the lint script
bash scripts/dev/lint.sh
```

See `docs/SECURITY_LINTING.md` for security-specific linting tools (Bandit, Semgrep).
See `docs/reference/LINTING.md` for comprehensive linting documentation.

## Testing Guide

> **📖 See [Testing Guide](./docs/reference/TESTING.md)** for comprehensive testing documentation including:
> - Running tests locally
> - Test suite overview
> - CI/CD pipeline details
> - Troubleshooting common issues

**Quick commands:**
```bash
# Run all tests
pytest tests/ -v

# Quick test during development
./scripts/dev/quick_test.sh

# Full test suite with linting
./scripts/dev/run_tests_local.sh
```

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

```
Add support for Arris TG1682G modem

- Added HTML parser for Arris status page format
- Created test fixtures from real modem output
- Updated documentation with supported models
- All existing tests still pass
```

## Release Process

Maintainers will handle releases following semantic versioning:

- **Major (1.0.0)**: Breaking changes
- **Minor (0.1.0)**: New features, backward compatible
- **Patch (0.0.1)**: Bug fixes, backward compatible

### Automated Release Script

The project includes an automated release script that handles all version bumping and release creation:

```bash
# Create a new release (will prompt for push confirmation)
python scripts/release.py 3.5.1

# Test locally without pushing
python scripts/release.py 3.5.1 --no-push

# Skip git hooks if needed
python scripts/release.py 3.5.1 --skip-verify

# Skip changelog update (not recommended)
python scripts/release.py 3.5.1 --skip-changelog
```

**What the script does:**
1. Validates version format (must be X.Y.Z)
2. Checks that git working directory is clean
3. Updates version in:
   - `custom_components/cable_modem_monitor/manifest.json`
   - `custom_components/cable_modem_monitor/const.py`
   - `tests/components/test_version_and_startup.py`
4. Moves `[Unreleased]` section in `CHANGELOG.md` to new version with today's date
5. Creates a git commit with all version changes
6. Creates an annotated git tag (v3.5.1)
7. Pushes commit and tag to remote
8. Creates a GitHub release with notes from CHANGELOG.md

**VS Code Task:**
You can also run the release script from VS Code:
1. Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
2. Type "Tasks: Run Task"
3. Select "🚀 Create Release"
4. Enter the version when prompted

### Manual Release Process (Legacy)

If you need to create a release manually:

Each release includes:
- Version bump in `manifest.json` and `const.py`
- Version update in `tests/components/test_version_and_startup.py`
- Updated `CHANGELOG.md`
- Git tag
- GitHub Release with notes

**Important:** Always update the version test when bumping versions to prevent test failures

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
