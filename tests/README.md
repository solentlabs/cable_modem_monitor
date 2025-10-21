***REMOVED*** Cable Modem Monitor - Test Suite

Automated tests for the Cable Modem Monitor integration, using real HTML fixtures from Motorola MB series modems.

***REMOVED******REMOVED*** Running Tests

***REMOVED******REMOVED******REMOVED*** Setup

```bash
***REMOVED*** Install test dependencies
pip install -r tests/requirements.txt
```

***REMOVED******REMOVED******REMOVED*** Run All Tests

```bash
***REMOVED*** From project root
pytest tests/ -v

***REMOVED*** Run with coverage
pytest tests/ -v --cov=custom_components/cable_modem_monitor --cov-report=html
```

***REMOVED******REMOVED******REMOVED*** Run Specific Tests

```bash
***REMOVED*** Test only scraper functionality
pytest tests/test_modem_scraper.py -v

***REMOVED*** Test a specific function
pytest tests/test_modem_scraper.py::TestModemScraper::test_parse_software_version -v
```

***REMOVED******REMOVED*** Test Structure

***REMOVED******REMOVED******REMOVED*** Fixtures

The `tests/fixtures/` directory contains real HTML responses from modems:

- `moto_connection.html` - MotoConnection.asp page (channel data, uptime)
- `moto_home.html` - MotoHome.asp page (software version, channel counts)

**Adding New Modem Models:**

To add support for a new modem model:

1. Capture HTML from your modem:
   ```bash
   curl -u username:password http://MODEM_IP/status.html > tests/fixtures/brand_model_status.html
   ```

2. Create corresponding tests in `test_modem_scraper.py`

3. Update the scraper to handle the new HTML structure

4. Run tests to ensure both old and new modems work

***REMOVED******REMOVED******REMOVED*** Test Categories

1. **TestModemScraper** - Unit tests for individual parsing functions
   - `test_parse_downstream_channels` - Validates downstream channel parsing
   - `test_parse_upstream_channels` - Validates upstream channel parsing
   - `test_parse_software_version` - Validates version extraction
   - `test_parse_system_uptime` - Validates uptime extraction
   - `test_parse_channel_counts` - Validates channel count parsing

2. **TestRealWorldScenarios** - Integration tests with real data
   - `test_motorola_mb_series_full_parse` - End-to-end parsing workflow
   - `test_power_levels_in_range` - Validates signal levels are reasonable
   - `test_frequencies_in_valid_range` - Validates DOCSIS 3.0 frequency ranges

***REMOVED******REMOVED*** Regression Testing

Before releasing new versions:

```bash
***REMOVED*** Run full test suite
pytest tests/ -v

***REMOVED*** Verify all assertions pass
***REMOVED*** Pay special attention to:
***REMOVED*** - Channel counts match expected values
***REMOVED*** - Software version is correctly extracted
***REMOVED*** - Uptime format is preserved
***REMOVED*** - Power/SNR values are in valid ranges
```

***REMOVED******REMOVED*** Continuous Integration

These tests can be integrated into CI/CD pipelines:

```yaml
***REMOVED*** Example GitHub Actions workflow
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - run: pip install -r tests/requirements.txt
      - run: pytest tests/ -v
```

***REMOVED******REMOVED*** Expected Test Results

When all tests pass, you should see:

```
tests/test_modem_scraper.py::TestModemScraper::test_parse_downstream_channels PASSED
tests/test_modem_scraper.py::TestModemScraper::test_parse_upstream_channels PASSED
tests/test_modem_scraper.py::TestModemScraper::test_parse_software_version PASSED
tests/test_modem_scraper.py::TestModemScraper::test_parse_system_uptime PASSED
tests/test_modem_scraper.py::TestModemScraper::test_parse_channel_counts PASSED
tests/test_modem_scraper.py::TestRealWorldScenarios::test_motorola_mb_series_full_parse PASSED
tests/test_modem_scraper.py::TestRealWorldScenarios::test_power_levels_in_range PASSED
tests/test_modem_scraper.py::TestRealWorldScenarios::test_frequencies_in_valid_range PASSED

========== 8 passed in 0.15s ==========
```

***REMOVED******REMOVED*** Adding Tests for New Features

When adding new sensors or features:

1. Add a test fixture if needed (new HTML page)
2. Write a test that validates the parsing
3. Write a test that validates the data ranges/format
4. Ensure existing tests still pass (regression test)

Example:

```python
def test_parse_new_sensor(self, scraper, html_fixture):
    """Test parsing new sensor data."""
    soup = BeautifulSoup(html_fixture, 'html.parser')
    result = scraper._parse_new_sensor(soup)

    assert result != "Unknown", "Should find new sensor value"
    assert isinstance(result, expected_type), "Should return correct type"
```
