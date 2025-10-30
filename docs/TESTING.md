***REMOVED*** Testing Guide

This guide explains how to run tests locally before pushing to GitHub, preventing CI failures and speeding up development.

***REMOVED******REMOVED*** Automated Testing Status

[![Tests](https://github.com/kwschulz/cable_modem_monitor/actions/workflows/tests.yml/badge.svg)](https://github.com/kwschulz/cable_modem_monitor/actions/workflows/tests.yml)

---

***REMOVED******REMOVED*** Prerequisites

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

***REMOVED******REMOVED*** Quick Start - Local Testing

***REMOVED******REMOVED******REMOVED*** First-Time Setup

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

***REMOVED******REMOVED******REMOVED*** Quick Testing During Development

After initial setup, use the quick test script:

```bash
./quick_test.sh
```

This runs tests with minimal output for rapid feedback during development.

**Time:** ~5-10 seconds

---

***REMOVED******REMOVED*** Why Test Locally?

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

***REMOVED******REMOVED*** Test Suite Overview

***REMOVED******REMOVED******REMOVED*** Unit Tests
Located in `tests/test_modem_scraper.py`

**Coverage:**
- ✅ Downstream channel parsing (24 channels)
- ✅ Upstream channel parsing (5 channels)
- ✅ Software version extraction
- ✅ System uptime parsing
- ✅ Channel count validation
- ✅ Total error calculation

***REMOVED******REMOVED******REMOVED*** Integration Tests
Real-world scenario testing with actual modem HTML fixtures

**Tests:**
- ✅ Full parse workflow (Motorola MB series)
- ✅ Power level validation (-20 to +20 dBmV downstream, 20-60 dBmV upstream)
- ✅ SNR validation (0-60 dB)
- ✅ Frequency validation (DOCSIS 3.0 ranges)

***REMOVED******REMOVED******REMOVED*** Test Fixtures
Real HTML responses from modems in `tests/fixtures/`:
- `moto_connection.html` - Channel data and uptime
- `moto_home.html` - Software version and channel counts

***REMOVED******REMOVED*** CI/CD Pipeline

***REMOVED******REMOVED******REMOVED*** Automated Workflows

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

***REMOVED******REMOVED*** Manual Testing (Alternative)

If you prefer manual control over the test environment:

***REMOVED******REMOVED******REMOVED*** 1. Set Up Virtual Environment (Once)

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

***REMOVED******REMOVED******REMOVED*** 2. Install Dependencies (Once)

```bash
pip install --upgrade pip
pip install -r tests/requirements.txt
```

***REMOVED******REMOVED******REMOVED*** 3. Run Tests

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

***REMOVED******REMOVED******REMOVED*** 4. Run Code Quality Checks

```bash
***REMOVED*** Check code quality
ruff check custom_components/cable_modem_monitor/

***REMOVED*** Auto-fix issues
ruff check --fix custom_components/cable_modem_monitor/
```

***REMOVED******REMOVED******REMOVED*** 5. Deactivate Virtual Environment (When Done)

```bash
deactivate
```

***REMOVED******REMOVED*** Test Results

***REMOVED******REMOVED******REMOVED*** Current Status
**Total Tests:** 53 tests across 3 test files
- ✅ `test_modem_scraper.py` - Modem parsing logic (8 tests)
- ✅ `test_config_flow.py` - Configuration validation (25 tests)
- ✅ `test_coordinator.py` - Data update coordinator (20 tests)

***REMOVED******REMOVED******REMOVED*** Coverage Goals
- **Current:** ~50%
- **Target:** 60-70% (realistic for community projects)
- **Critical paths:** Config flow, coordinator, scraper core functions

***REMOVED******REMOVED*** Adding New Tests

***REMOVED******REMOVED******REMOVED*** For New Features
1. Add HTML fixture if parsing new data
2. Write unit test for parsing function
3. Write integration test for complete workflow
4. Validate data ranges and types

***REMOVED******REMOVED******REMOVED*** Example
```python
def test_new_feature(self, scraper, html_fixture):
    """Test new feature parsing."""
    soup = BeautifulSoup(html_fixture, 'html.parser')
    result = scraper._parse_new_feature(soup)

    assert result is not None, "Should parse feature"
    assert isinstance(result, expected_type)
    assert result in valid_range
```

***REMOVED******REMOVED*** Regression Testing

Before each release:
1. Run full test suite locally
2. Verify all tests pass
3. Check coverage hasn't decreased
4. Test with live modem if possible
5. Review GitHub Actions results

***REMOVED******REMOVED*** Troubleshooting

***REMOVED******REMOVED******REMOVED*** "ModuleNotFoundError" when running tests

**Solution:** Install test dependencies
```bash
source venv/bin/activate
pip install -r tests/requirements.txt
```

***REMOVED******REMOVED******REMOVED*** Virtual environment not activating

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

***REMOVED******REMOVED******REMOVED*** Tests pass locally but fail in CI

**Possible causes:**
1. **Missing dependency** - Check `tests/requirements.txt` includes all imports
2. **Python version difference** - CI tests on 3.11 and 3.12
3. **File path issues** - Use relative imports in tests
4. **Environment-specific code** - Mock external dependencies properly

***REMOVED******REMOVED******REMOVED*** Permission denied on test scripts

**Solution:** Make scripts executable
```bash
chmod +x run_tests_local.sh quick_test.sh
```

---

***REMOVED******REMOVED*** Continuous Improvement

***REMOVED******REMOVED******REMOVED*** Planned Enhancements
- [x] Add tests for config_flow.py
- [x] Add tests for coordinator.py
- [ ] Add tests for sensor.py
- [ ] Add tests for button.py
- [ ] Integration tests with Home Assistant test framework
- [ ] Mock HTTP requests for network isolation
- [ ] Performance benchmarks

***REMOVED******REMOVED******REMOVED*** Contributing Tests
When adding support for new modem models:
1. Capture HTML from modem status pages
2. Add to `tests/fixtures/`
3. Create test cases for new HTML structure
4. Ensure backward compatibility with existing tests

***REMOVED******REMOVED*** Resources

- [pytest Documentation](https://docs.pytest.org/)
- [Home Assistant Testing](https://developers.home-assistant.io/docs/development_testing)
- [Coverage.py](https://coverage.readthedocs.io/)

***REMOVED******REMOVED*** Support

If tests fail:
1. Check GitHub Actions logs for details
2. Run tests locally to reproduce
3. Review test output and tracebacks
4. Open issue with test failure details
