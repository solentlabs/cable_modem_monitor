***REMOVED*** Contributing to Cable Modem Monitor

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

***REMOVED******REMOVED*** Ways to Contribute

- 🐛 Report bugs via [GitHub Issues](https://github.com/kwschulz/cable_modem_monitor/issues)
- 💡 Suggest features or improvements
- 📝 Improve documentation
- 🧪 Add support for additional modem models
- 🔧 Submit bug fixes or enhancements

***REMOVED******REMOVED*** Development Workflow

***REMOVED******REMOVED******REMOVED*** 1. Set Up Your Environment

First, clone the repository and install the development dependencies. This will give you all the tools you need for testing, linting, and code formatting.

```bash
git clone https://github.com/kwschulz/cable_modem_monitor.git
cd cable_modem_monitor
pip install -r tests/requirements.txt
```

***REMOVED******REMOVED******REMOVED*** 2. Write Your Code

Make your code changes or additions on a new branch.

***REMOVED******REMOVED******REMOVED*** 3. Format and Lint

Before committing, ensure your code is well-formatted and passes all quality checks.

```bash
***REMOVED*** Auto-format your code with Black
black custom_components/cable_modem_monitor/ tests/

***REMOVED*** Check for linting issues with Ruff
ruff check custom_components/cable_modem_monitor/ tests/
```

***REMOVED******REMOVED******REMOVED*** 4. Run Tests

Make sure all tests pass before submitting your changes.

```bash
pytest tests/ -v
```

***REMOVED******REMOVED******REMOVED*** 5. Deploy for Manual Testing (Optional)

You can deploy your changes to a local Home Assistant instance for manual testing using the provided script.

```bash
***REMOVED*** Edit scripts/deploy_updates.sh with your settings first
./scripts/deploy_updates.sh
```

***REMOVED******REMOVED*** Adding Support for New Modem Models

Thanks to our modular parser architecture, adding support for a new modem is simple! The integration uses a **plugin system** that automatically discovers and registers parsers.

***REMOVED******REMOVED******REMOVED*** Quick Start Guide

1. **Capture HTML from your modem**
   ```bash
   ***REMOVED*** Save the status page HTML for testing
   curl -u username:password http://MODEM_IP/status_page.html > tests/fixtures/brand_model.html
   ```

2. **Create a new parser file** in `custom_components/cable_modem_monitor/parsers/`

   Use `parsers/parser_template.py` as a starting point, or copy an existing parser:

   ```python
   ***REMOVED*** custom_components/cable_modem_monitor/parsers/my_modem.py
   from bs4 import BeautifulSoup
   from .base_parser import ModemParser
   from ..utils import extract_number, extract_float

   class MyModemParser(ModemParser):
       """Parser for My Modem Model."""

       ***REMOVED*** Metadata - define your modem info
       name = "My Modem Brand Model"
       manufacturer = "My Modem Brand"
       models = ["Model123", "Model456"]

       ***REMOVED*** URL patterns your modem uses
       ***REMOVED*** The scraper will try these URLs automatically
       url_patterns = [
           {"path": "/status.html", "auth_method": "basic"},  ***REMOVED*** or "form" or "none"
           {"path": "/connection.asp", "auth_method": "basic"},  ***REMOVED*** fallback URL
       ]

       @classmethod
       def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
           """Detect if this parser can handle the modem's HTML."""
           ***REMOVED*** Check for unique identifiers in the HTML
           return "My Modem" in soup.title.string if soup.title else False

       def login(self, session, base_url, username, password):
           """Handle authentication (if required)."""
           if not username or not password:
               return True  ***REMOVED*** No auth needed

           ***REMOVED*** For basic auth:
           session.auth = (username, password)
           return True

           ***REMOVED*** For form auth, see motorola_mb.py for example

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
           ***REMOVED*** Your parsing logic here
           ***REMOVED*** Return list of dicts with: channel_id, frequency, power, snr, corrected, uncorrected
           return channels

       def _parse_upstream(self, soup):
           """Parse upstream channel data."""
           channels = []
           ***REMOVED*** Your parsing logic here
           ***REMOVED*** Return list of dicts with: channel_id, frequency, power
           return channels

       def _parse_system_info(self, soup):
           """Parse system information."""
           return {
               "software_version": "...",
               "system_uptime": "...",
               ***REMOVED*** etc.
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
       ***REMOVED*** etc.
   ```

4. **Test your parser**
   ```bash
   ***REMOVED*** Run your specific tests
   pytest tests/test_parser_my_modem.py -v

   ***REMOVED*** Make sure all tests still pass
   pytest tests/ -v
   ```

5. **That's it!** The parser will be automatically:
   - Discovered by the integration
   - Added to the modem selection dropdown
   - Tried during auto-detection
   - Cached after successful connection

***REMOVED******REMOVED******REMOVED*** Parser Architecture Benefits

- **✅ Zero core changes needed** - Just add your parser file
- **✅ Auto-discovery** - Plugin system finds your parser automatically
- **✅ URL patterns in parser** - No hardcoded URLs in the scraper
- **✅ User control** - Users can manually select your parser if auto-detection fails
- **✅ Performance caching** - Parser choice is cached after first success

***REMOVED******REMOVED******REMOVED*** Authentication Methods

Your parser's `url_patterns` can specify:
- `"auth_method": "none"` - No authentication (e.g., ARRIS SB6141)
- `"auth_method": "basic"` - HTTP Basic Auth (e.g., Technicolor TC4400)
- `"auth_method": "form"` - Form-based login (e.g., Motorola MB series)

***REMOVED******REMOVED******REMOVED*** Example Parsers

Look at these existing parsers for examples:
- **Simple (no auth)**: `parsers/arris_sb6141.py`
- **Basic auth**: `parsers/technicolor_tc4400.py`
- **Form auth**: `parsers/motorola_mb.py`
- **Complex**: `parsers/technicolor_xb7.py`

***REMOVED******REMOVED******REMOVED*** Submitting Your Parser

When you submit a pull request, include:
- ✅ Parser file in `parsers/` directory
- ✅ Test fixture HTML in `tests/fixtures/` (sanitize personal info!)
- ✅ Test file in `tests/` directory
- ✅ Update to docs listing the new supported modem
- ✅ All tests passing: `pytest tests/ -v`

***REMOVED******REMOVED*** Code Style

- Follow [PEP 8](https://pep8.org/) style guidelines
- Use type hints where appropriate
- Add docstrings to functions and classes
- Keep functions focused and small
- Use async/await for I/O operations

***REMOVED******REMOVED******REMOVED*** Linting
```bash
ruff check custom_components/cable_modem_monitor/
```

***REMOVED******REMOVED*** Testing Guide

This guide explains how to run tests locally before pushing to GitHub, preventing CI failures and speeding up development.

***REMOVED******REMOVED******REMOVED*** Automated Testing Status

[![Tests](https://github.com/kwschulz/cable_modem_monitor/actions/workflows/tests.yml/badge.svg)](https://github.com/kwschulz/cable_modem_monitor/actions/workflows/tests.yml)

---

***REMOVED******REMOVED******REMOVED*** Prerequisites

Before running tests locally, ensure you have:

```bash
***REMOVED*** Check Python version (3.11+ required)
python3 --version

***REMOVED*** Install required system packages (Ubuntu/Debian/WSL)
sudo apt update
sudo apt install python3-pip python3-venv

***REMOVED*** Verify installation
python3 -m pip --version
python3 -m venv --help
```

**Note:** If you're using Windows with WSL, make sure these packages are installed in your WSL distribution.

---

***REMOVED******REMOVED******REMOVED*** Quick Start - Local Testing

***REMOVED******REMOVED******REMOVED******REMOVED*** First-Time Setup

Run the full test suite (creates virtual environment automatically):

```bash
./run_tests_local.sh
```

This will:
- Create a Python virtual environment (`venv/`)
- Install all test dependencies
- Run code quality checks (ruff)
- Run all tests with pytest
- Generate coverage report

**Time:** ~2-3 minutes (first run), ~30 seconds (subsequent runs)

***REMOVED******REMOVED******REMOVED******REMOVED*** Quick Testing During Development

After initial setup, use the quick test script:

```bash
./quick_test.sh
```

This runs tests with minimal output for rapid feedback during development.

**Time:** ~5-10 seconds

---

***REMOVED******REMOVED******REMOVED*** Why Test Locally?

**Benefits:**
- ⚡ Catch errors before CI runs (faster feedback)
- 💰 Save GitHub Actions minutes
- 🎯 Prevent "fix CI" commits
- 📈 Maintain code quality
- 🚀 Faster development cycle

**Recommended Workflow:**
1. Make code changes
2. Run `./quick_test.sh` frequently during development
3. Run `./run_tests_local.sh` before committing
4. Push to GitHub only when local tests pass

---

***REMOVED******REMOVED******REMOVED*** Test Suite Overview

***REMOVED******REMOVED******REMOVED******REMOVED*** Unit Tests
Located in `tests/test_modem_scraper.py`

**Coverage:**
- ✅ Downstream channel parsing (24 channels)
- ✅ Upstream channel parsing (5 channels)
- ✅ Software version extraction
- ✅ System uptime parsing
- ✅ Channel count validation
- ✅ Total error calculation

***REMOVED******REMOVED******REMOVED******REMOVED*** Integration Tests
Real-world scenario testing with actual modem HTML fixtures

**Tests:**
- ✅ Full parse workflow (Motorola MB series)
- ✅ Power level validation (-20 to +20 dBmV downstream, 20-60 dBmV upstream)
- ✅ SNR validation (0-60 dB)
- ✅ Frequency validation (DOCSIS 3.0 ranges)

***REMOVED******REMOVED******REMOVED******REMOVED*** Test Fixtures
Real HTML responses from modems in `tests/fixtures/`:
- `moto_connection.html` - Channel data and uptime
- `moto_home.html` - Software version and channel counts

***REMOVED******REMOVED******REMOVED*** CI/CD Pipeline

***REMOVED******REMOVED******REMOVED******REMOVED*** Automated Workflows

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

***REMOVED******REMOVED******REMOVED*** Manual Testing (Alternative)

If you prefer manual control over the test environment:

***REMOVED******REMOVED******REMOVED******REMOVED*** 1. Set Up Virtual Environment (Once)

```bash
***REMOVED*** Create virtual environment
python3 -m venv venv

***REMOVED*** Activate it
source venv/bin/activate  ***REMOVED*** Linux/Mac/WSL
***REMOVED*** OR
venv\Scripts\activate  ***REMOVED*** Windows CMD
***REMOVED*** OR
venv\Scripts\Activate.ps1  ***REMOVED*** Windows PowerShell
```

***REMOVED******REMOVED******REMOVED******REMOVED*** 2. Install Dependencies (Once)

```bash
pip install --upgrade pip
pip install -r tests/requirements.txt
```

***REMOVED******REMOVED******REMOVED******REMOVED*** 3. Run Tests

```bash
***REMOVED*** Run all tests
pytest tests/ -v

***REMOVED*** Run specific test file
pytest tests/test_config_flow.py -v

***REMOVED*** Run specific test
pytest tests/test_config_flow.py::TestConfigFlow::test_scan_interval_minimum_valid -v

***REMOVED*** Run with coverage
pytest tests/ --cov=custom_components/cable_modem_monitor --cov-report=term

***REMOVED*** Generate HTML coverage report
pytest tests/ --cov=custom_components/cable_modem_monitor --cov-report=html
***REMOVED*** Open htmlcov/index.html in browser
```

***REMOVED******REMOVED******REMOVED******REMOVED*** 4. Run Code Quality Checks

```bash
***REMOVED*** Check code quality
ruff check custom_components/cable_modem_monitor/

***REMOVED*** Auto-fix issues
ruff check --fix custom_components/cable_modem_monitor/
```

***REMOVED******REMOVED******REMOVED******REMOVED*** 5. Deactivate Virtual Environment (When Done)

```bash
deactivate
```

***REMOVED******REMOVED******REMOVED*** Test Results

***REMOVED******REMOVED******REMOVED******REMOVED*** Current Status
**Total Tests:** 53 tests across 3 test files
- ✅ `test_modem_scraper.py` - Modem parsing logic (8 tests)
- ✅ `test_config_flow.py` - Configuration validation (25 tests)
- ✅ `test_coordinator.py` - Data update coordinator (20 tests)

***REMOVED******REMOVED******REMOVED******REMOVED*** Coverage Goals
- **Current:** ~50%
- **Target:** 60-70% (realistic for community projects)
- **Critical paths:** Config flow, coordinator, scraper core functions

***REMOVED******REMOVED******REMOVED*** Adding New Tests

***REMOVED******REMOVED******REMOVED******REMOVED*** For New Features
1. Add HTML fixture if parsing new data
2. Write unit test for parsing function
3. Write integration test for complete workflow
4. Validate data ranges and types

***REMOVED******REMOVED******REMOVED******REMOVED*** Example
```python
def test_new_feature(self, scraper, html_fixture):
    """Test new feature parsing."""
    soup = BeautifulSoup(html_fixture, 'html.parser')
    result = scraper._parse_new_feature(soup)

    assert result is not None, "Should parse feature"
    assert isinstance(result, expected_type)
    assert result in valid_range
```

***REMOVED******REMOVED******REMOVED*** Regression Testing

Before each release:
1. Run full test suite locally
2. Verify all tests pass
3. Check coverage hasn't decreased
4. Test with live modem if possible
5. Review GitHub Actions results

***REMOVED******REMOVED******REMOVED*** Troubleshooting

***REMOVED******REMOVED******REMOVED******REMOVED*** "ModuleNotFoundError" when running tests

**Solution:** Install test dependencies
```bash
source venv/bin/activate
pip install -r tests/requirements.txt
```

***REMOVED******REMOVED******REMOVED******REMOVED*** Virtual environment not activating

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

***REMOVED******REMOVED******REMOVED******REMOVED*** Tests pass locally but fail in CI

**Possible causes:**
1. **Missing dependency** - Check `tests/requirements.txt` includes all imports
2. **Python version difference** - CI tests on 3.11 and 3.12
3. **File path issues** - Use relative imports in tests
4. **Environment-specific code** - Mock external dependencies properly

***REMOVED******REMOVED******REMOVED******REMOVED*** Permission denied on test scripts

**Solution:** Make scripts executable
```bash
chmod +x run_tests_local.sh quick_test.sh
```

---

***REMOVED******REMOVED******REMOVED*** Continuous Improvement

***REMOVED******REMOVED******REMOVED******REMOVED*** Planned Enhancements
- [x] Add tests for config_flow.py
- [x] Add tests for coordinator.py
- [ ] Add tests for sensor.py
- [ ] Add tests for button.py
- [ ] Integration tests with Home Assistant test framework
- [ ] Mock HTTP requests for network isolation
- [ ] Performance benchmarks

***REMOVED******REMOVED******REMOVED******REMOVED*** Contributing Tests
When adding support for new modem models:
1. Capture HTML from modem status pages
2. Add to `tests/fixtures/`
3. Create test cases for new HTML structure
4. Ensure backward compatibility with existing tests

***REMOVED******REMOVED******REMOVED*** Resources

- [pytest Documentation](https://docs.pytest.org/)
- [Home Assistant Testing](https://developers.home-assistant.io/docs/development_testing)
- [Coverage.py](https://coverage.readthedocs.io/)

***REMOVED******REMOVED******REMOVED*** Support

If tests fail:
1. Check GitHub Actions logs for details
2. Run tests locally to reproduce
3. Review test output and tracebacks
4. Open issue with test failure details

***REMOVED******REMOVED*** Submitting Changes

***REMOVED******REMOVED******REMOVED*** Pull Request Process

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

***REMOVED******REMOVED******REMOVED*** Pull Request Guidelines

- **Clear description**: Explain what changes you made and why
- **Link issues**: Reference any related GitHub issues
- **Test results**: Include test output showing all tests pass
- **Screenshots**: For UI changes, include before/after screenshots
- **Documentation**: Update README, CHANGELOG, or other docs as needed

***REMOVED******REMOVED******REMOVED*** Commit Message Format

Use clear, descriptive commit messages:

```
Add support for Arris TG1682G modem

- Added HTML parser for Arris status page format
- Created test fixtures from real modem output
- Updated documentation with supported models
- All existing tests still pass
```

***REMOVED******REMOVED*** Release Process

Maintainers will handle releases following semantic versioning:

- **Major (1.0.0)**: Breaking changes
- **Minor (0.1.0)**: New features, backward compatible
- **Patch (0.0.1)**: Bug fixes, backward compatible

Each release includes:
- Version bump in `manifest.json`
- Updated `CHANGELOG.md`
- Git tag
- GitHub Release with notes

***REMOVED******REMOVED*** Code of Conduct

***REMOVED******REMOVED******REMOVED*** Our Standards

- Be respectful and inclusive
- Welcome newcomers and help them learn
- Focus on what is best for the community
- Show empathy towards others

***REMOVED******REMOVED******REMOVED*** Unacceptable Behavior

- Harassment, discrimination, or offensive comments
- Trolling or insulting comments
- Publishing others' private information
- Unprofessional conduct

***REMOVED******REMOVED*** Questions?

- 💬 Open a [GitHub Discussion](https://github.com/kwschulz/cable_modem_monitor/discussions)
- 🐛 Report issues via [GitHub Issues](https://github.com/kwschulz/cable_modem_monitor/issues)
- 📧 Contact maintainers via GitHub

***REMOVED******REMOVED*** Resources

- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [HACS Documentation](https://hacs.xyz/)
- [Python asyncio](https://docs.python.org/3/library/asyncio.html)
- [pytest Documentation](https://docs.pytest.org/)

Thank you for contributing to Cable Modem Monitor! 🎉
