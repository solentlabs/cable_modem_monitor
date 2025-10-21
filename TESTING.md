***REMOVED*** Testing Documentation

***REMOVED******REMOVED*** Automated Testing Status

[![Tests](https://github.com/kwschulz/cable_modem_monitor/actions/workflows/tests.yml/badge.svg)](https://github.com/kwschulz/cable_modem_monitor/actions/workflows/tests.yml)

The Cable Modem Monitor integration has comprehensive automated testing via GitHub Actions.

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

***REMOVED******REMOVED*** Running Tests Locally

***REMOVED******REMOVED******REMOVED*** Quick Start
```bash
***REMOVED*** Install dependencies
pip install -r tests/requirements.txt

***REMOVED*** Run all tests
pytest tests/ -v

***REMOVED*** Run with coverage
pytest tests/ --cov=custom_components/cable_modem_monitor --cov-report=html

***REMOVED*** View coverage report
open htmlcov/index.html
```

***REMOVED******REMOVED******REMOVED*** Individual Test Suites
```bash
***REMOVED*** Unit tests only
pytest tests/test_modem_scraper.py::TestModemScraper -v

***REMOVED*** Integration tests only
pytest tests/test_modem_scraper.py::TestRealWorldScenarios -v

***REMOVED*** Specific test
pytest tests/test_modem_scraper.py::TestModemScraper::test_parse_downstream_channels -v
```

***REMOVED******REMOVED*** Test Results

***REMOVED******REMOVED******REMOVED*** Current Status
All 8 tests passing:
- ✅ `test_parse_downstream_channels`
- ✅ `test_parse_upstream_channels`
- ✅ `test_parse_software_version`
- ✅ `test_parse_system_uptime`
- ✅ `test_parse_channel_counts`
- ✅ `test_total_errors_calculation`
- ✅ `test_motorola_mb_series_full_parse`
- ✅ `test_power_levels_in_range`
- ✅ `test_frequencies_in_valid_range`

***REMOVED******REMOVED******REMOVED*** Coverage Goals
- Current: Check CI for latest coverage %
- Target: >80% code coverage
- Critical paths: 100% coverage

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

***REMOVED******REMOVED*** Continuous Improvement

***REMOVED******REMOVED******REMOVED*** Planned Enhancements
- [ ] Add tests for config_flow.py
- [ ] Add tests for sensor.py
- [ ] Add tests for button.py
- [ ] Integration tests with Home Assistant test framework
- [ ] Mock HTTP requests for network isolation
- [ ] Performance benchmarks
- [ ] Load testing with multiple modems

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
