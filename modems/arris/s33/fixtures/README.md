# Arris/CommScope S33 Modem Fixtures


<!-- AUTO-GENERATED FROM metadata.yaml - DO NOT EDIT BELOW -->
## Quick Facts

| Spec | Value |
|------|-------|
| **DOCSIS** | 3.1 |
| **Released** | 2020 |
| **Status** | Current |
| **ISPs** | Comcast, Cox, Spectrum |
| **Parser** | ⏳ Pending |

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
| **Related Issue** | [#32](https://github.com/solentlabs/cable_modem_monitor/issues/32) |
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

## Parser Implementation

**Status:** ✅ **VERIFIED** (December 2025)

The S33 parser uses JSON-based HNAP authentication, sharing the same protocol as the Motorola MB8611 but with `GetCustomer*` action prefixes instead of `GetMoto*`.

**Key implementation details:**
- Uses `HNAPJsonRequestBuilder` for JSON-based HNAP calls
- Batched requests via `GetMultipleHNAPs` for efficiency
- Channel data format: caret-delimited (`^`) fields, pipe-separated (`|+|`) channels
- Supports modem restart via `SetArrisConfigurationInfo` with `Action="reboot"`
- Note: S33 blocks ICMP ping - integration uses HTTP-only health checks

**Capabilities:**
- ✅ Downstream channels (SC-QAM + OFDM)
- ✅ Upstream channels (ATDMA + OFDMA)
- ✅ Software version
- ✅ Modem restart
- ❌ System uptime (not available - S33 only exposes current clock time)

## Related Issues

- **Issue #32:** Arris/CommScope S33 support request (closed, verified)

## Notes

- Uses HNAP/SOAP authentication similar to Motorola MB8611
- Supports both HTTP and HTTPS connections (self-signed certs)
- Default credentials: `admin` / user-configured password
- Verified by @gmogoody on Comcast network
