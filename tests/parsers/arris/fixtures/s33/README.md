# Arris/CommScope S33 Modem Fixtures


<!-- AUTO-GENERATED FROM metadata.yaml - DO NOT EDIT BELOW -->
## Quick Facts

| Spec | Value |
|------|-------|
| **DOCSIS** | 3.1 |
| **Released** | 2020 |
| **Status** | Current |
| **ISPs** | Comcast, Cox, Spectrum |

<!-- END AUTO-GENERATED -->

## Modem Information

| Property | Value |
|----------|-------|
| **Model** | S33 |
| **Manufacturer** | Arris/CommScope |
| **DOCSIS Version** | 3.1 |
| **Release Year** | 2019 |
| **ISPs** | Comcast, Xfinity, Cox, Spectrum |
| **Firmware** | TB01.03.001.10_012022_212.S3 |
| **Related Issue** | [#32](https://github.com/kwschulz/cable_modem_monitor/issues/32) |
| **Captured By** | @gmogoody |
| **Capture Date** | November 2025 |

## Known URLs

- **Base URL:** `http://192.168.100.1` (also works with HTTPS)
- **Login Page:** `/Login.html` (✓ captured)
- **Status Page:** `/Cmconnectionstatus.html` (⚠️ not captured - requires authentication)

## Authentication

**Type:** HNAP/SOAP (SOAP-based authentication)

**Evidence:**
- Login.html references `./js/SOAP/SOAPAction.js?V=M2`
- JavaScript-based authentication flow
- Similar to Motorola MB8611 HNAP protocol

**Credentials:**
- Default username: `admin`
- Password: User-configured
- Authentication method: HTTP Basic Auth attempted, but likely needs HNAP/SOAP session

**Challenges:**
- HNAP authentication has proven unreliable across multiple modems (see issues #4, #6)
- SSL certificate verification issues with self-signed certificates common
- Status page not accessible without proper HNAP authentication

## Directory Structure

```
s33/
├── Login.html              # Core - authentication page
├── cmconnectionstatus.html # Core - channel data
├── README.md
└── extended/
    └── connectionstatus.js # JS file (reference only)
```

## Core Fixtures

### Login.html
- **Source:** Diagnostics capture from fallback parser
- **Status Code:** 200 OK
- **Size:** 6,825 bytes
- **Content:** Full login page with ARRIS branding
- **Captured:** 2025-11-24 (via diagnostics download)
- **Authentication:** None required (public page)

**Key Content:**
- ARRIS logo and branding
- Username/password form
- "Device Status" button (shows firmware, connection status without login)
- References to SURFboard Central mobile app
- SOAP/HNAP JavaScript includes

### commscope_s33.html ✅ CAPTURED
- **Source:** User @gmogoody via issue #32
- **Size:** 7.5 KB
- **Content:** Connection status page template (HTML structure only)
- **Captured:** 2025-11-24

**Structure:**
- Startup Procedure table with span IDs for dynamic population
- Empty `CustomerConnDownstreamChannel` table (populated by JavaScript)
- Empty `CustomerConnUpstreamChannel` table (populated by JavaScript)
- System uptime span: `CustomerConnSystemUpTime`
- Breadcrumb shows this is `cmconnectionstatus.html`

**Important:** This is just the HTML template - actual channel data is loaded dynamically via HNAP JavaScript.

### commscope_s33-2.html ✅ CAPTURED (JavaScript)
- **Source:** User @gmogoody via issue #32
- **Size:** 11 KB
- **Content:** JavaScript code (`connectionstatus.js`) that populates the page
- **Captured:** 2025-11-24

**Critical Discovery:** This reveals the complete HNAP protocol and data format!

## HNAP Protocol Analysis

**Major Discovery:** The S33 uses **identical HNAP protocol and data format to the Motorola MB8611!**

### HNAP Actions Used

The JavaScript makes two batched HNAP calls to `/HNAP1/`:

**Call 1 - Startup & Connection Info:**
- `GetCustomerStatusStartupSequence` (vs MB8611's `GetMotoStatusStartupSequence`)
- `GetCustomerStatusConnectionInfo` (vs MB8611's `GetMotoStatusConnectionInfo`)

**Call 2 - Channel Data:**
- `GetCustomerStatusDownstreamChannelInfo` (vs MB8611's `GetMotoStatusDownstreamChannelInfo`)
- `GetCustomerStatusUpstreamChannelInfo` (vs MB8611's `GetMotoStatusUpstreamChannelInfo`)

**Pattern:** S33 uses `GetCustomer...` prefix, MB8611 uses `GetMoto...` prefix, but otherwise identical!

### Channel Data Format

**Downstream Channels:** (same as MB8611)
```
Format: ChannelSelect^LockStatus^ChannelType^ChannelID^Frequency^PowerLevel^SNRLevel^CorrectedCodewords^UnerroredsCodewords
Delimiter: ^ (caret) between fields, |+| between channels
Indices:
  [0] = Channel Select (unused in display)
  [1] = Lock Status
  [2] = Modulation (Channel Type)
  [3] = Channel ID
  [4] = Frequency (Hz)
  [5] = Power (dBmV)
  [6] = SNR (dB)
  [7] = Corrected Codewords
  [8] = Uncorrected Codewords
```

**Upstream Channels:** (same as MB8611)
```
Format: ChannelSelect^LockStatus^ChannelType^ChannelID^SymbolRate/Width^Frequency^PowerLevel
Delimiter: ^ (caret) between fields, |+| between channels
Indices:
  [0] = Channel Select (unused)
  [1] = Lock Status
  [2] = Channel Type (US Channel Type)
  [3] = Channel ID
  [4] = Symbol Rate/Width
  [5] = Frequency (Hz)
  [6] = Power (dBmV)
```

### Authentication Flow

JavaScript checks for session key:
```javascript
if (sessionStorage.getItem('PrivateKey') === null){
    window.location.replace('../Login.html');
}
```

This confirms HNAP session-based authentication is required.

## Parser Implementation Status

**Current Status:** ⏸️ **ON HOLD - Pending HNAP Authentication Improvements**

**Decision:** Rather than implement another potentially unreliable HNAP parser, we're waiting to:
1. Get hands-on access to an HNAP device for proper testing
2. Shake out authentication issues systematically
3. Refactor/abstract HNAP authentication logic for better reuse
4. Build a solid framework before adding more HNAP modems

**All fixtures captured and documented - ready for implementation when HNAP is solid!**

### Option 1: HNAP-Based Parser (Reuse MB8611 Code)

**Pros:**
- ✅ Data format is identical to MB8611
- ✅ Can reuse most MB8611 HNAP parser code
- ✅ Just change action names: `GetCustomer...` instead of `GetMoto...`
- ✅ Complete understanding of protocol from JavaScript

**Cons:**
- ⚠️ HNAP authentication has been unreliable (issues #4, #6)
- ⚠️ SSL certificate issues common
- ⚠️ Session management complexity
- ⚠️ Harder for users to troubleshoot

### Option 2: Request Static HTML with Data

**Pros:**
- ✅ More reliable than HNAP
- ✅ Simpler to implement and maintain
- ✅ Easier for users to capture (Save Page As)
- ✅ No authentication issues

**Cons:**
- ⚠️ Requires user to manually save HTML after page loads
- ⚠️ User must wait for JavaScript to populate data
- ⚠️ Extra step for user

### Recommendation

Given the HNAP challenges documented in issues #4 and #6:
1. **First, request user to save the populated HTML page** (after JavaScript runs)
2. If that doesn't work, implement HNAP parser using MB8611 as template
3. Document both approaches in parser

## Future HNAP Refactoring Notes

**When tackling HNAP authentication properly, consider:**

### 1. Abstract Common HNAP Logic
Current MB8611 parser has hardcoded action names. Could abstract:
```python
class HNAPParserBase(ModemParser):
    """Base class for HNAP-based parsers."""

    # Subclasses override these
    action_prefix = "GetMoto"  # or "GetCustomer" for S33

    def get_downstream_action(self):
        return f"{self.action_prefix}StatusDownstreamChannelInfo"

    def get_upstream_action(self):
        return f"{self.action_prefix}StatusUpstreamChannelInfo"
```

### 2. Reusable Channel Data Parser
Both MB8611 and S33 use identical caret-delimited format:
- Extract parsing logic into shared utility
- `parse_hnap_channels(data, delimiter="^", separator="|+|")`
- Reduces duplication, easier to test

### 3. HNAP Authentication Strategy Improvements
Current challenges (issues #4, #6):
- SSL certificate verification
- Session management/timeouts
- Error handling and retry logic
- User-friendly diagnostics when auth fails

Consider:
- Better session persistence
- Automatic retry on auth failure
- Clear user guidance when things go wrong
- Option to bypass SSL verification (with warning)

### 4. Testing Framework
With fixtures for MB8611 and S33:
- Create mock HNAP server for testing
- Test authentication flows without real hardware
- Validate different firmware versions
- Test error conditions (timeouts, bad auth, etc.)

### 5. When Ready to Implement S33

**Simple approach (after HNAP is solid):**
```python
class ArrisS33Parser(HNAPParserBase):
    name = "Arris S33"
    manufacturer = "Arris"
    models = ["S33", "CommScope S33"]
    action_prefix = "GetCustomer"  # Only difference from MB8611!

    url_patterns = [
        {"path": "/HNAP1/", "auth_method": "hnap", "auth_required": True},
        {"path": "/cmconnectionstatus.html", "auth_method": "hnap", "auth_required": True},
    ]
```

**Next Steps When Ready:**
1. Get hands-on HNAP device for testing
2. Refactor MB8611 parser to use base class
3. Test authentication thoroughly
4. Implement S33 as subclass (minimal code)
5. Test with real S33 user (@gmogoody)
6. Document patterns for future HNAP modems

## Related Issues

- **Issue #32:** Arris/CommScope S33 support request (active)
- **Issue #4:** MB8611 HNAP authentication challenges (SSL certs, SOAP complexity)
- **Issue #6:** MB8611 SSL certificate verification failures (self-signed certs)

## Notes

- The S33 appears to share authentication patterns with Motorola MB8611 (HNAP/SOAP)
- However, HNAP has proven problematic in practice - prefer HTML samples if available
- User has already provided HTML samples via issue #32 attachments
- Fallback parser successfully captured Login.html using Basic Auth over HTTPS
- The modem accepts both HTTP and HTTPS connections

## Diagnostics Metadata

**Capture Details:**
- Captured: 2025-11-24 20:31:43 UTC
- Trigger: Manual capture via "Capture HTML" button
- Integration Version: 3.5.1
- Parser Used: Unknown Modem (Fallback Mode)
- Working URL: `https://192.168.100.1/`
- Health Status: ICMP blocked (firewall), HTTP latency 9.6ms

**What Was Captured:**
- Login.html (200 OK)
- All standard endpoints returned 404 (index, status, connection variations)
- No channel data captured (authentication barrier)

**What's Missing:**
- Cmconnectionstatus.html (primary status page)
- Any authenticated pages with channel data
- HNAP/SOAP responses (if applicable)
