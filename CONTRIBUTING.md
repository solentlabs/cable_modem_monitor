# Contributing to Cable Modem Monitor

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Ways to Contribute

- 🐛 Report bugs via [GitHub Issues](https://github.com/kwschulz/cable_modem_monitor/issues)
- 💡 Suggest features or improvements
- 📝 Improve documentation
- 🧪 Add support for additional modem models
- 🔧 Submit bug fixes or enhancements

## Development Workflow

You can develop using either a **local Python environment** (fastest) or a **VS Code Dev Container** (guaranteed consistency).

> **📖 See [Getting Started Guide](./docs/GETTING_STARTED.md)** for comprehensive setup instructions, decision tree, and troubleshooting.

### Docker Development (Recommended)

Docker provides an isolated, consistent development environment with Home Assistant pre-installed.

#### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop) installed and running
- [VS Code](https://code.visualstudio.com/) (optional, for Dev Container support)

#### Quick Start

```bash
# Clone the repository
git clone https://github.com/kwschulz/cable_modem_monitor.git
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

See [Getting Started Guide](./docs/GETTING_STARTED.md) or [VS Code Dev Container Guide](./docs/VSCODE_DEVCONTAINER_GUIDE.md) for detailed instructions and troubleshooting.

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
git clone https://github.com/kwschulz/cable_modem_monitor.git
cd cable_modem_monitor

# Option 1: Use the automated setup script (recommended)
./scripts/setup.sh

# Option 2: Manual installation
pip install -r requirements-dev.txt  # Comprehensive dev dependencies (includes types, linters, pre-commit)
pre-commit install  # Install git hooks for automatic code formatting
```

**Having environment issues?** See [Getting Started Guide](./docs/GETTING_STARTED.md) for:
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

You can deploy your changes to a local Home Assistant instance for manual testing using the provided script.

```bash
# Edit scripts/deploy_updates.sh with your settings first
./scripts/deploy_updates.sh
```

## Adding Support for New Modem Models

Thanks to our modular parser architecture, adding support for a new modem is simple! The integration uses a **plugin system** that automatically discovers and registers parsers.

### Quick Start Guide

1. **Capture HTML from your modem**
   ```bash
   # Save the status page HTML for testing
   curl -u username:password http://MODEM_IP/status_page.html > tests/fixtures/brand_model.html
   ```

2. **Create a new parser file** in `custom_components/cable_modem_monitor/parsers/`

   Use `parsers/parser_template.py` as a starting point, or copy an existing parser:

   ```python
   # custom_components/cable_modem_monitor/parsers/my_modem.py
   from bs4 import BeautifulSoup
   from .base_parser import ModemParser
   from ..utils import extract_number, extract_float

   class MyModemParser(ModemParser):
       """Parser for My Modem Model."""

       # Metadata - define your modem info
       name = "My Modem Brand Model"
       manufacturer = "My Modem Brand"
       models = ["Model123", "Model456"]

       # URL patterns your modem uses
       # The scraper will try these URLs automatically
       url_patterns = [
           {"path": "/status.html", "auth_method": "basic"},  # or "form" or "none"
           {"path": "/connection.asp", "auth_method": "basic"},  # fallback URL
       ]

       @classmethod
       def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
           """Detect if this parser can handle the modem's HTML."""
           # Check for unique identifiers in the HTML
           return "My Modem" in soup.title.string if soup.title else False

       def login(self, session, base_url, username, password):
           """Handle authentication (if required)."""
           if not username or not password:
               return True  # No auth needed

           # For basic auth:
           session.auth = (username, password)
           return True

           # For form auth, see motorola_mb.py for example

       def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
           """Parse all data from the modem."""
           downstream = self._parse_downstream(soup)
           upstream = self._parse_upstream(soup)
           system_info = self._parse_system_info(soup)

           return {
               "downstream": downstream,
               "upstream": upstream,
               "system_info": system_info,
           }

       def _parse_downstream(self, soup):
           """Parse downstream channel data."""
           channels = []
           # Your parsing logic here
           # Return list of dicts with: channel_id, frequency, power, snr, corrected, uncorrected
           return channels

       def _parse_upstream(self, soup):
           """Parse upstream channel data."""
           channels = []
           # Your parsing logic here
           # Return list of dicts with: channel_id, frequency, power
           return channels

       def _parse_system_info(self, soup):
           """Parse system information."""
           return {
               "software_version": "...",
               "system_uptime": "...",
               # etc.
           }
   ```

3. **Create tests** in `tests/test_parser_my_modem.py`

   ```python
   import pytest
   from bs4 import BeautifulSoup
   from custom_components.cable_modem_monitor.parsers.my_modem import MyModemParser

   @pytest.fixture
   def sample_html():
       """Load the test fixture."""
       with open("tests/fixtures/my_modem.html") as f:
           return f.read()

   def test_parser_detection(sample_html):
       """Test that the parser correctly identifies the modem."""
       soup = BeautifulSoup(sample_html, "html.parser")
       assert MyModemParser.can_parse(soup, "http://192.168.0.1/status.html", sample_html)

   def test_parsing_downstream(sample_html):
       """Test downstream channel parsing."""
       soup = BeautifulSoup(sample_html, "html.parser")
       parser = MyModemParser()
       data = parser.parse(soup)

       assert len(data["downstream"]) > 0
       assert "channel_id" in data["downstream"][0]
       assert "frequency" in data["downstream"][0]
       # etc.
   ```

4. **Test your parser**
   ```bash
   # Run your specific tests
   pytest tests/test_parser_my_modem.py -v

   # Make sure all tests still pass
   pytest tests/ -v
   ```

5. **That's it!** The parser will be automatically:
   - Discovered by the integration
   - Added to the modem selection dropdown
   - Tried during auto-detection
   - Cached after successful connection

### Parser Architecture Benefits

- **✅ Zero core changes needed** - Just add your parser file
- **✅ Auto-discovery** - Plugin system finds your parser automatically
- **✅ URL patterns in parser** - No hardcoded URLs in the scraper
- **✅ User control** - Users can manually select your parser if auto-detection fails
- **✅ Performance caching** - Parser choice is cached after first success

### Authentication Methods

Your parser's `url_patterns` can specify:
- `"auth_method": "none"` - No authentication (e.g., ARRIS SB6141)
- `"auth_method": "basic"` - HTTP Basic Auth (e.g., Technicolor TC4400)
- `"auth_method": "form"` - Form-based login (e.g., Motorola MB series)

### Example Parsers

Look at these existing parsers for examples:
- **Simple (no auth)**: `parsers/arris_sb6141.py`
- **Basic auth**: `parsers/technicolor_tc4400.py`
- **Form auth**: `parsers/motorola_mb.py`
- **Complex**: `parsers/technicolor_xb7.py`

### Submitting Your Parser

When you submit a pull request, include:
- ✅ Parser file in `parsers/` directory
- ✅ Test fixture HTML in `tests/fixtures/` (sanitize personal info!)
- ✅ Test file in `tests/` directory
- ✅ Update to docs listing the new supported modem
- ✅ All tests passing: `pytest tests/ -v`

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
See `docs/LINTING.md` for comprehensive linting documentation.

## Testing Guide

This guide explains how to run tests locally before pushing to GitHub, preventing CI failures and speeding up development.

### Automated Testing Status

[![Tests](https://github.com/kwschulz/cable_modem_monitor/actions/workflows/tests.yml/badge.svg)](https://github.com/kwschulz/cable_modem_monitor/actions/workflows/tests.yml)

---

### Prerequisites

Before running tests locally, ensure you have:

```bash
# Check Python version (3.11+ required)
python3 --version

# Install required system packages (Ubuntu/Debian/WSL)
sudo apt update
sudo apt install python3-pip python3-venv

# Verify installation
python3 -m pip --version
python3 -m venv --help
```

**Note:** If you're using Windows with WSL, make sure these packages are installed in your WSL distribution.

---

### Quick Start - Local Testing

#### First-Time Setup

Run the full test suite (creates virtual environment automatically):

```bash
./scripts/dev/run_tests_local.sh
```

This will:
- Create a Python virtual environment (`.venv/`)
- Install all test dependencies
- Run code quality checks (ruff)
- Run all tests with pytest
- Generate coverage report

**Time:** ~2-3 minutes (first run), ~30 seconds (subsequent runs)

#### Quick Testing During Development

After initial setup, use the quick test script:

```bash
./scripts/dev/quick_test.sh
```

This runs tests with minimal output for rapid feedback during development.

**Time:** ~5-10 seconds

---

### Why Test Locally?

**Benefits:**
- ⚡ Catch errors before CI runs (faster feedback)
- 💰 Save GitHub Actions minutes
- 🎯 Prevent "fix CI" commits
- 📈 Maintain code quality
- 🚀 Faster development cycle

**Recommended Workflow:**
1. Make code changes
2. Run `./scripts/dev/quick_test.sh` frequently during development
3. Run `./scripts/dev/run_tests_local.sh` before committing
4. Push to GitHub only when local tests pass

---

### Test Suite Overview

#### Unit Tests
Located in `tests/test_modem_scraper.py`

**Coverage:**
- ✅ Downstream channel parsing (24 channels)
- ✅ Upstream channel parsing (5 channels)
- ✅ Software version extraction
- ✅ System uptime parsing
- ✅ Channel count validation
- ✅ Total error calculation

#### Integration Tests
Real-world scenario testing with actual modem HTML fixtures

**Tests:**
- ✅ Full parse workflow (Motorola MB series)
- ✅ Power level validation (-20 to +20 dBmV downstream, 20-60 dBmV upstream)
- ✅ SNR validation (0-60 dB)
- ✅ Frequency validation (DOCSIS 3.0 ranges)

#### Test Fixtures
Real HTML responses from modems in `tests/fixtures/`:
- `moto_connection.html` - Channel data and uptime
- `moto_home.html` - Software version and channel counts

### CI/CD Pipeline

#### Automated Workflows

**On Every Push/PR:**
1. **Tests Job**
   - Matrix testing: Python 3.11 & 3.12
   - Runs full pytest suite
   - Generates coverage report
   - Uploads to Codecov

2. **Lint Job**
   - Code quality checks with ruff
   - Enforces Python best practices
   - Validates code style

3. **Validate Job**
   - HACS validation
   - Ensures integration meets HACS requirements

### Manual Testing (Alternative)

If you prefer manual control over the test environment:

#### 1. Set Up Virtual Environment (Once)

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # Linux/Mac/WSL
# OR
venv\Scripts\activate  # Windows CMD
# OR
venv\Scripts\Activate.ps1  # Windows PowerShell
```

#### 2. Install Dependencies (Once)

```bash
pip install --upgrade pip
pip install -r tests/requirements.txt
```

#### 3. Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_config_flow.py -v

# Run specific test
pytest tests/test_config_flow.py::TestConfigFlow::test_scan_interval_minimum_valid -v

# Run with coverage
pytest tests/ --cov=custom_components/cable_modem_monitor --cov-report=term

# Generate HTML coverage report
pytest tests/ --cov=custom_components/cable_modem_monitor --cov-report=html
# Open htmlcov/index.html in browser
```

#### 4. Run Code Quality Checks

```bash
# Check code quality
ruff check custom_components/cable_modem_monitor/

# Auto-fix issues
ruff check --fix custom_components/cable_modem_monitor/
```

#### 5. Deactivate Virtual Environment (When Done)

```bash
deactivate
```

### Test Results

#### Current Status
**Total Tests:** 443 tests across 26 test files
- ✅ **Components (162 tests):** diagnostics, sensors, buttons, config flow, coordinator, modem scraper
- ✅ **Parsers (146 tests):** All 10 modem parsers with comprehensive coverage
- ✅ **Core Modules (115 tests):** signal_analyzer, health_monitor, hnap_builder, authentication, discovery, crawler
- ✅ **Utils (20 tests):** entity cleanup, HTML helpers

#### Coverage Goals
- **Current:** ~70% (test-to-code ratio)
- **Required:** 60%+ (enforced in CI/CD)
- **Status:** ✅ Target achieved and maintained
- **Critical paths:** All user-facing functionality, parsers, and core infrastructure fully tested

### Adding New Tests

#### For New Features
1. Add HTML fixture if parsing new data
2. Write unit test for parsing function
3. Write integration test for complete workflow
4. Validate data ranges and types

#### Example
```python
def test_new_feature(self, scraper, html_fixture):
    """Test new feature parsing."""
    soup = BeautifulSoup(html_fixture, 'html.parser')
    result = scraper._parse_new_feature(soup)

    assert result is not None, "Should parse feature"
    assert isinstance(result, expected_type)
    assert result in valid_range
```

### Regression Testing

Before each release:
1. Run full test suite locally
2. Verify all tests pass
3. Check coverage hasn't decreased
4. Test with live modem if possible
5. Review GitHub Actions results

### Troubleshooting

#### "ModuleNotFoundError" when running tests

**Solution:** Install test dependencies
```bash
source venv/bin/activate
pip install -r tests/requirements.txt
```

#### Virtual environment not activating

**Linux/Mac/WSL:**
```bash
source venv/bin/activate
```

**Windows (PowerShell):**
```powershell
venv\Scripts\Activate.ps1
```

**Windows (CMD):**
```cmd
venv\Scripts\activate.bat
```

#### Tests pass locally but fail in CI

**Possible causes:**
1. **Missing dependency** - Check `tests/requirements.txt` includes all imports
2. **Python version difference** - CI tests on 3.11 and 3.12
3. **File path issues** - Use relative imports in tests
4. **Environment-specific code** - Mock external dependencies properly

#### Permission denied on test scripts

**Solution:** Make scripts executable
```bash
chmod +x scripts/dev/run_tests_local.sh scripts/dev/quick_test.sh
```

---

### Continuous Improvement

#### Planned Enhancements
- [x] Add tests for config_flow.py
- [x] Add tests for coordinator.py
- [ ] Add tests for sensor.py
- [ ] Add tests for button.py
- [ ] Integration tests with Home Assistant test framework
- [ ] Mock HTTP requests for network isolation
- [ ] Performance benchmarks

#### Contributing Tests
When adding support for new modem models:
1. Capture HTML from modem status pages
2. Add to `tests/fixtures/`
3. Create test cases for new HTML structure
4. Ensure backward compatibility with existing tests

### Resources

- [pytest Documentation](https://docs.pytest.org/)
- [Home Assistant Testing](https://developers.home-assistant.io/docs/development_testing)
- [Coverage.py](https://coverage.readthedocs.io/)

### Support

If tests fail:
1. Check GitHub Actions logs for details
2. Run tests locally to reproduce
3. Review test output and tracebacks
4. Open issue with test failure details

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

Each release includes:
- Version bump in `manifest.json` and `const.py`
- Updated `CHANGELOG.md`
- Git tag
- GitHub Release with notes

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

- 💬 Open a [GitHub Discussion](https://github.com/kwschulz/cable_modem_monitor/discussions)
- 🐛 Report issues via [GitHub Issues](https://github.com/kwschulz/cable_modem_monitor/issues)
- 📧 Contact maintainers via GitHub

## Resources

- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [HACS Documentation](https://hacs.xyz/)
- [Python asyncio](https://docs.python.org/3/library/asyncio.html)
- [pytest Documentation](https://docs.pytest.org/)

Thank you for contributing to Cable Modem Monitor! 🎉
