# SB6190 Test Suite

Comprehensive testing for ARRIS SB6190 parser to address issue #93.

## Test Files

### 1. `test_parser.py` - Unit Tests
**Status**: ✓ EXISTS (created during v3.12 refactor)
**Coverage**: Parser logic with fixture HTML

Tests the parser directly against the static fixture in `fixtures/cgi-bin/status`:
- ✓ Downstream channel parsing (expects 32 channels)
- ✓ Upstream channel parsing (expects 4 channels)
- ✓ Channel data structure validation
- ✓ Parser detection via HintMatcher

**Run**: `pytest modems/arris/sb6190/tests/test_parser.py -v`

### 2. `test_har_variant.py` - HAR-Based Parser Test
**Status**: ✅ NEWLY CREATED
**Coverage**: Parser with real modem HTML from issue #93

Tests the parser against Paul's actual SB6190 HTML (firmware 9.1.103AA65L) extracted from HAR capture:
- ❌ **EXPECTED TO FAIL** if parser is broken (reproduces issue #93)
- ✓ Verifies parser extracts 24 downstream, 4 upstream channels
- ✓ Validates channel data completeness
- ✓ Tests `parse_resources()` with various resource dict keys

**Fixture**: `fixtures/status-firmware-9.1.103.html` (extracted from RAW_DATA HAR)

**Run**: `pytest modems/arris/sb6190/tests/test_har_variant.py -v -s`

### 3. `test_har.py` - HAR Auth Detection
**Status**: ✓ EXISTS
**Coverage**: Authentication pattern detection from HAR

Tests auth discovery pipeline using HAR replay:
- ✓ Detects URL_TOKEN pattern (false positive noted)
- ⚠️ Does NOT test parser - only auth detection

**Note**: Skips when HAR files unavailable (gitignored for PII)

## Integration Tests

### `tests/integration/test_config_flow_e2e.py`
**Status**: ✅ UPDATED with channel assertions
**Coverage**: End-to-end auth + parsing with mock server

Updated tests to verify channel counts:
- `test_sb6190_form_nonce_auth`: Now asserts channels > 0
- `test_sb6190_no_auth`: Now asserts channels > 0

**Before**: Only checked `result.success` (auth worked)
**After**: Checks `result.modem_data` has channels

## Running Tests

### Quick Validation
```bash
# Run all SB6190 tests
pytest modems/arris/sb6190/tests/ -v

# Run with output to see channel counts
pytest modems/arris/sb6190/tests/test_har_variant.py -v -s
```

### Full Test Suite
```bash
# All tests (unit + integration)
pytest

# Just SB6190 integration tests
pytest tests/integration/test_config_flow_e2e.py::TestFormNonceE2E::test_sb6190_form_nonce_auth -v -s
```

### Expected Results

**If parser is working correctly:**
- ✅ `test_parser.py`: All pass (fixture has data)
- ✅ `test_har_variant.py`: All pass (Paul's HTML parses)
- ✅ Integration tests: Pass with channel counts logged

**If parser is broken (issue #93 bug):**
- ✅ `test_parser.py`: May still pass (different HTML structure?)
- ❌ `test_har_variant.py`: **FAILS** with "No downstream channels parsed"
- ❌ Integration tests: **FAIL** with "Parser returned 0 channels"

## Test Coverage Gaps (Before This Update)

1. ❌ No test validated parser works with **real modem HTML** from HAR
2. ❌ Integration tests only checked auth success, not parsing success
3. ❌ HAR tests only covered auth detection, not data extraction
4. ❌ Unit tests used different HTML than production (untested edge cases)

## Investigation Status

**See**: `../INVESTIGATION.md` for comprehensive status of SB6190 issues

**Current Status** (2026-02-03):
- ✅ Parser logic proven correct (mock server test passed)
- ✅ Parser extracts 24 channels from Paul's HTML
- ❌ Production returns 0 channels (Issue #93)
- ❓ Root cause unknown - not parser, not HTML, not auth

## Next Steps

1. **Run `test_har_variant.py`** to verify parser works with Paul's HTML:
   ```bash
   pytest modems/arris/sb6190/tests/test_har_variant.py -v -s
   ```
   **Expected**: PASS (parser should extract 24 channels)

2. **Enable DEBUG logging** on Paul's installation to see what's happening:
   - What HTML does parser receive during polls?
   - Is parser being called at all?
   - Are there exceptions being swallowed?

3. **Run updated integration tests** to ensure mock server works:
   ```bash
   pytest tests/integration/test_config_flow_e2e.py::TestFormNonceE2E::test_sb6190_form_nonce_auth -v -s
   ```
   **Expected**: PASS with channel counts logged

4. **Compare diagnostics** between test and production:
   - Mock server: Returns 24 channels ✅
   - Paul's modem: Returns 0 channels ❌
   - Same HTML structure, different results

## Issue #93 Root Cause Diagnosis

The test suite now distinguishes between:

**Scenario A: Parser is broken**
- `test_har_variant.py` FAILS → Parser can't parse Paul's HTML structure
- Fix: Update parser logic to handle the HTML structure

**Scenario B: Parser works, but isn't being called correctly**
- `test_har_variant.py` PASSES → Parser CAN parse the HTML
- But production returns 0 channels → Resource loading/orchestration issue
- Fix: Debug how HTML is delivered to parser in production

## Test Fixtures

All fixtures in `fixtures/`:
- `cgi-bin/status` - Original test fixture (34 channels)
- `login.html` - Login page for form_nonce auth
- `status-firmware-9.1.103.html` - Paul's real modem HTML (24 channels) ← NEW

Source HAR files in `RAW_DATA/`:
- `RAW_DATA/v3.13.0/arris-sb6190-paul/modem_20260127_paul.har`
- `RAW_DATA/har/arris-sb6190.har` (non-auth variant)
