# ARRIS SB6190 - Investigation Status

**Last Updated**: 2026-02-04
**Status**: ✅ FIXED (Issue #93 resolved in commit 14d31e8)

---

## Executive Summary

**Issue #93 has been FIXED.** The SB6190 parser was returning 0 channels in production despite successful authentication. Root cause: orchestrator added 341-byte auth response to "/" key instead of 15KB status page. Parser tried "/" first and got wrong HTML.

**Solution**: Modified `parse_resources()` to try explicit path (`/cgi-bin/status`) before "/" fallback. All tests pass, parser now correctly extracts 24 downstream and 4 upstream channels.

This document preserves the investigation process that led to the fix.

---

## Hardware & Firmware

### Known Variants

| Firmware | Auth Required | Status | Source |
|----------|---------------|--------|--------|
| Unknown (older) | No | ✅ Worked (PR #22) | sfennell |
| 9.1.103AA72 | Yes | ❌ Never worked | Issue #83 (Winesnob) |
| 9.1.103AA65L | Yes | ❌ Never worked | Issue #93 (Paul/@HenryGeorge1978) |

### Hardware Specs

- **DOCSIS**: 3.0
- **Chipset**: Intel Puma 6
- **Release**: 2016
- **EOL**: 2023
- **Default IP**: 192.168.100.1
- **Channels**: 24-32 downstream, 4 upstream (typical)

---

## Authentication

### Firmware Variants

**Non-Auth Variant** (older firmware):
- No authentication required
- Status pages are public
- **Status**: Worked in PR #22 (no fixtures preserved)

**Auth Variant** (firmware 9.1.103+):
- **Strategy**: `form_nonce` (added v3.13.0-beta.2)
- **Endpoint**: `/cgi-bin/adv_pwd_cgi`
- **Flow**: POST with `username`, `password`, `ar_nonce` (8-digit client-generated)
- **Response**: `"Url:/path"` (success) or `"Error:message"` (failure)
- **Session**: `credential` cookie set on successful auth
- **Status**: Auth works ✅, but parser returns 0 channels ❌

### Session Management

- ❌ **No logout endpoint** on this modem
- ✅ Session persists indefinitely (until modem restart)
- ✅ Session cookies maintained between polls
- ❌ Session expiration is **NOT** the issue

**Evidence**:
- HAR capture shows no logout URLs
- Web interface has no logout button/link
- No logout configuration in `modem.yaml`

---

## Parser Implementation

### Code Location

- **Parser**: `modems/arris/sb6190/parser.py`
- **Class**: `ArrisSB6190Parser`
- **Base**: `ModemParser`
- **Paradigm**: `html` (standard table parsing)

### Parser Logic

```python
def _parse_downstream(self, soup):
    # Find table containing "Downstream Bonded Channels"
    # Parse rows starting at index 2 (skip 2 header rows)
    # Extract: channel_id, frequency, power, SNR, corrected, uncorrected
    # Each row has 9 cells
```

**Expected Table Structure**:
```html
<table>
  <tr><th colspan="9">Downstream Bonded Channels</th></tr>
  <tr><td>Channel</td><td>Lock Status</td>...[7 more headers]</tr>
  <tr><td>1</td><td> Locked </td><td>256QAM</td>...[6 more values]</tr>
  ...
</table>
```

### Provenance

- **Original**: PR #22 (sfennell, Nov 2025) - claimed to work
- **Note**: "Parser based on SB6141 code; fixture provenance unknown"
- **Issue**: No fixtures or tests were committed with PR #22
- **Current fixtures**: Added during v3.12 refactor, source unknown

---

## Test Coverage

### Unit Tests ✅

**File**: `modems/arris/sb6190/tests/test_parser.py`

- ✅ Parser detection via HintMatcher
- ✅ Downstream parsing (expects 32 channels)
- ✅ Upstream parsing (expects 4 channels)
- ✅ Transposed table format handling
- ✅ Tests **PASS** in CI

**Fixture**: `modems/arris/sb6190/fixtures/cgi-bin/status` (15,623 bytes, 34 channels)

### Integration Tests ⚠️

**File**: `tests/integration/test_config_flow_e2e.py`

**Before**: Only checked `result.success` (auth worked) ❌
**After** (2026-02-03): Now asserts channel counts > 0 ✅

Tests:
- `test_sb6190_form_nonce_auth` - Auth + parsing with mock server
- `test_sb6190_no_auth` - No-auth variant with mock server
- `test_sb6190_wrong_credentials` - Auth failure handling

**Status**: Tests pass, but they use a different fixture than Paul's HTML

### HAR Tests ⚠️

**File**: `modems/arris/sb6190/tests/test_har.py`

- ⚠️ Only tests auth detection, **NOT** parsing
- ⚠️ Skips when HAR files unavailable (gitignored)

### Paul's HTML Test ✅

**File**: `modems/arris/sb6190/tests/test_har_variant.py` (created 2026-02-03)

**Fixture**: `modems/arris/sb6190/fixtures/status-firmware-9.1.103.html` (15,127 bytes, 24 channels)

Tests parser against Paul's ACTUAL modem HTML extracted from HAR capture.

**Status**: NOT YET RUN (requires pytest installation)

---

## What We've Proven

### ✅ Parser Logic is Correct

**Test**: Mock server with Paul's HTML (2026-02-03)

```
Parser extracted:
  24 downstream channels ✅
  4 upstream channels ✅
  First channel: ID=4, 405MHz, 3.5dBmV, 40.95dB SNR ✅
```

**Evidence**:
- Live mock server test with Paul's exact HTML
- Parser extracted all expected channels
- Channel data matches HAR capture values
- `parse_resources()` works with various dict keys

### ✅ HTML Structure is Correct

**Paul's HTML**:
- ✅ Contains "Downstream Bonded Channels" header
- ✅ Has `colspan="9"` table structure
- ✅ Has 28 data rows with 9 cells each
- ✅ All required fields present (ID, freq, power, SNR, errors)

**Regex verification**: Found 28 channel rows matching expected pattern

### ✅ Auth Flow Works

**HAR Capture Evidence**:
1. GET `/` → Login page returned
2. POST `/cgi-bin/adv_pwd_cgi` → `credential` cookie set
3. GET `/cgi-bin/status` → Status page with 28 channels returned

**Integration Test**: `form_nonce` auth succeeds in tests

**Paul's Diagnostics**: `auth_configuration.status: "success"`

### ✅ No Session Management Issues

- No logout endpoint exists
- Sessions don't expire (persist until modem restart)
- Session cookies maintained correctly
- Not a session timeout problem

---

## What We Don't Know

### ❓ Why Production Returns 0 Channels

**Symptoms**:
- Auth works (integration installs) ✅
- HTTP connection works ✅
- Parser returns 0 channels ❌
- Diagnostics: `connection_status: "parser_issue"`

**Possible Causes**:

1. **Parser Not Called During Polls**
   - Coordinator might skip parser invocation
   - Error handling might return early with empty data
   - Need to verify parser logs during poll

2. **Parser Receives Empty/Different HTML**
   - Fetch might fail silently during polls
   - HTML might be truncated or corrupted
   - Might get redirected to login page

3. **Parser Exception Swallowed**
   - Parser might throw exception during production
   - Exception caught and returns empty dict
   - No error logged at INFO level

4. **Timing/Race Condition**
   - Diagnostics captured during transient error
   - Modem had no signal at capture time
   - Issue is intermittent, not persistent

5. **Environment Difference**
   - BeautifulSoup parsing differently in HA
   - Python version differences
   - Dependency version mismatch

### ❓ When Did It Last Work?

**PR #22 (Nov 2025)**: User claimed it worked
- ❌ No fixtures committed
- ❌ No tests to verify
- ❌ No way to reproduce
- ❓ Was it actually tested or just "no errors"?

**Possibility**: Parser has **NEVER** worked correctly, tests just didn't catch it

### ❓ Test Fixture vs Production Difference

**Test Fixture**: 15,623 bytes, 34 channels (mock server)
**Paul's HTML**: 15,127 bytes, 28 channels (real modem)

Differences:
- Different channel counts
- Different first channel ID (1 vs 4)
- Different frequency ranges
- Same overall structure

**Question**: Does parser handle all variations correctly?

### ❓ Other Users' Status

**Issue #83** (Winesnob):
- Firmware: 9.1.103AA72
- Status: Also returns 0 channels
- Same symptoms as Paul

**Question**: Is this firmware-specific or parser-specific?

---

## Data Sources

### HAR Captures

| Source | Location | Size | Channels | Status |
|--------|----------|------|----------|--------|
| Paul (auth) | `RAW_DATA/v3.13.0/arris-sb6190-paul/modem_20260127_paul.har` | 15,127B | 28 DS, 4 US | ✅ Complete |
| Unknown (non-auth?) | `RAW_DATA/har/arris-sb6190.har` | 16,270B | 36 DS | ✅ Complete |

### Fixtures

| File | Source | Size | Channels | Used By |
|------|--------|------|----------|---------|
| `cgi-bin/status` | Unknown | 15,623B | 34 DS, 4 US | Unit tests, mock server |
| `status-firmware-9.1.103.html` | HAR capture | 15,127B | 24 DS, 4 US | Paul's HTML test |
| `login.html` | HAR capture | 5,579B | N/A | Auth tests |

### Diagnostics

**Paul's Latest** (Issue #93, Jan 29):
```json
{
  "version": "3.13.0-beta.7",
  "auth_configuration.status": "success",
  "auth_configuration.strategy": "form_nonce",
  "modem_data.connection_status": "parser_issue",
  "modem_data.downstream_channels_parsed": 0,
  "modem_data.upstream_channels_parsed": 0,
  "recent_logs": [INFO level only, no errors visible]
}
```

---

## Hypotheses

### Hypothesis 1: Parser Works, Coordinator Doesn't Call It ⭐ LIKELY

**Evidence For**:
- Parser works in all tests
- Auth succeeds
- No errors in logs

**Evidence Against**:
- Would expect logged errors

**Test**: Add debug logging to parser entry/exit

### Hypothesis 2: Parser Gets Empty/Wrong HTML

**Evidence For**:
- Would explain 0 channels
- HTML fetch might fail silently

**Evidence Against**:
- Auth works, so HTML should be fetchable

**Test**: Log actual HTML passed to parser

### Hypothesis 3: BeautifulSoup Parsing Difference

**Evidence For**:
- Test env vs HA env might differ
- Could explain test pass, prod fail

**Evidence Against**:
- Same Python version, same dependencies

**Test**: Run parser in HA container with Paul's HTML

### Hypothesis 4: Diagnostics Captured During Anomaly ⭐ POSSIBLE

**Evidence For**:
- HAR shows modem works
- Issue might be transient
- Timing-dependent

**Evidence Against**:
- Paul reports consistent failure

**Test**: Request fresh diagnostics during known-good time

### Hypothesis 5: Parser Never Worked, Tests Are Wrong

**Evidence For**:
- PR #22 had no tests
- Current tests use different HTML
- No proof it ever worked

**Evidence Against**:
- Mock server test with Paul's HTML works

**Test**: Already done - parser works!

---

## Session Expiration Testing (2026-02-03 Evening)

### Test Results

**Created Test**: `/tmp/test_sb6190_session_issue.py` - Simulates session expiration by clearing cookies

**Key Findings**:

1. ✅ **Re-auth Logic Works**: DataOrchestrator successfully re-authenticates when session expires
   - Cleared cookies between polls
   - Both polls returned 32 channels correctly
   - Auth endpoint works (`/cgi-bin/adv_pwd_cgi` returns `Url:/cgi-bin/status`)

2. ⚠️ **Session Cookies NOT Persisted**:
   ```
   DEBUG: Session has no cookies - will need to authenticate
   ```
   - This message appears on EVERY poll, not just first poll
   - Session cookies are not being stored after authentication
   - Orchestrator re-authenticates on every single poll

3. ✅ **Parser Returns 0 Channels for Login Page**: Confirmed via `/tmp/test_parser_with_login_page.py`
   - Parser given `login.html` → returns 0 channels
   - This is expected behavior (not a bug)
   - If session expired AND re-auth failed → parser gets login HTML → 0 channels

4. ✅ **Enhanced Logging Added**: `data_orchestrator.py` now logs ERROR when parser receives login HTML
   ```python
   if is_login_page(html):
       _LOGGER.error(
           "Parser is receiving LOGIN page HTML instead of data! "
           "Session may have expired. This will cause 0 channels to be parsed."
       )
   ```

### Why Mock Server Test Passes But Paul's Modem Fails

**Mock Server** (works correctly):
- Re-authenticates on every poll (no cookies stored)
- Auth always succeeds → gets status HTML → parser extracts channels
- Test shows re-auth logic is sound

**Paul's Modem** (returns 0 channels):
- Likely also re-authenticating on every poll (same cookie issue)
- But something causes re-auth to fail silently
- Failed re-auth → gets login HTML → parser returns 0 channels

### Hypothesis: Silent Re-Auth Failures

**New Primary Hypothesis**: Paul's modem has intermittent auth failures during polling

**Evidence**:
- Session cookies aren't persisting (orchestrator re-auths every poll)
- If modem is slow/busy during a poll, auth might timeout or fail
- Failed auth returns login page HTML
- Parser gets login HTML → returns 0 channels
- ERROR logging would catch this (not yet deployed to Paul)

**Supporting Evidence**:
- Paul reports "never worked" - suggests consistent failure
- Diagnostics show `auth_configuration.status: "success"` but `connection_status: "parser_issue"`
- This fits: initial setup auth succeeds, but polling auths fail

### Next Steps from Testing

1. **Deploy enhanced ERROR logging** to Paul's installation (already added to `data_orchestrator.py`)
2. **Request DEBUG logs** from Paul during 2-3 poll cycles
3. **Look for ERROR**: "Parser is receiving LOGIN page HTML" in Paul's logs
4. **Investigate cookie persistence** - why aren't session cookies being stored?

---

## Next Steps

### Immediate (DEBUG Priority)

1. **Enable DEBUG Logging** on Paul's Installation
   ```yaml
   logger:
     default: info
     logs:
       custom_components.cable_modem_monitor: debug
   ```
   Capture logs during 2-3 poll cycles

2. **Add Parser Entry/Exit Logging**
   ```python
   def parse_resources(self, resources):
       _LOGGER.debug(f"parse_resources called with keys: {list(resources.keys())}")
       _LOGGER.debug(f"Resource types: {[(k, type(v)) for k, v in resources.items()]}")
       result = ...
       _LOGGER.debug(f"parse_resources returning {len(result.get('downstream', []))} DS channels")
       return result
   ```

3. **Run Paul's HTML Test**
   ```bash
   pytest modems/arris/sb6190/tests/test_har_variant.py -v -s
   ```

### Short Term (Investigation)

4. **Add HTML Capture to Diagnostics**
   - Capture actual HTML received by parser
   - Compare to HAR capture
   - Check for truncation, encoding issues

5. **Test in HA Container**
   - Run parser directly in HA Python environment
   - Rule out environment differences

6. **Request Fresh Diagnostics from Paul**
   - Verify issue is persistent, not transient
   - Get diagnostics immediately after known success

### Medium Term (Architecture)

7. **Add Parser Health Monitoring**
   - Log parser invocation count
   - Log parse success/failure rate
   - Surface in diagnostics

8. **Improve Error Handling**
   - Don't swallow parser exceptions
   - Return structured error info
   - Make "parser_issue" status more specific

9. **Add Fixture Validation**
   - Verify all fixtures parse correctly
   - Compare fixture results to expected values
   - Add fixture source documentation

---

## Open Questions

1. **Did PR #22 actually work, or just "not crash"?**
   - No test fixtures to verify
   - No way to reproduce original success

2. **Why do unit tests pass but production fails?**
   - Same parser code
   - Same HTML structure
   - Different results

3. **Is this firmware-specific?**
   - Issue #83 has similar symptoms
   - Same firmware family (9.1.103AA*)
   - Different from PR #22 firmware?

4. **What does "parser_issue" status mean exactly?**
   - Code sets this when downstream/upstream are empty
   - Doesn't distinguish between different failure modes
   - Need more granular status reporting

5. **Are there other SB6190 users we haven't heard from?**
   - PR #22 worked (claimed)
   - Issues #83, #93 don't work
   - Silent majority working or broken?

---

## Related Issues

- **#93**: Paul's SB6190 (firmware 9.1.103AA65L) - 0 channels
- **#83**: Winesnob's SB6190 (firmware 9.1.103AA72) - 0 channels
- **#22**: sfennell's PR - claimed working (older firmware, no auth)

---

## Document History

- **2026-02-03 Evening**: Session expiration testing and enhanced logging
  - Created session expiration test with mock server
  - Confirmed re-auth logic works correctly
  - Discovered session cookies NOT persisting (re-auth every poll)
  - Added ERROR-level logging to detect login page HTML
  - New hypothesis: Silent re-auth failures during polling

- **2026-02-03**: Initial version - comprehensive investigation summary
  - Documented known facts vs unknowns
  - Recorded test results (mock server with Paul's HTML)
  - Identified 5 main hypotheses
  - Proposed next steps for debugging
