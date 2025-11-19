***REMOVED*** Test Fixture Status & Issue HTML Samples

**Date:** November 18, 2025 (Updated for v3.3.0)
**Purpose:** Track HTML samples from users and test fixture coverage

---

***REMOVED******REMOVED*** Summary

| Issue | Modem Model | HTML Samples Provided | Fixtures in Repo | Status | Action Needed |
|-------|-------------|----------------------|------------------|--------|---------------|
| ***REMOVED***1 | TC-4400 | ✅ Yes (3 files) | ✅ Yes (3 files) | ⚠️ **OPEN** - Entities Unavailable | Debug with user |
| ***REMOVED***2 | XB7 | ✅ Yes (1 file) | ✅ Yes (1 file) | ✅ **RESOLVED** (v2.6.0) | Awaiting user confirmation |
| ***REMOVED***3 | Netgear CM600 | ✅ Yes (7 files) | ✅ Yes (7 files) | 🧪 **IMPLEMENTED** (v3.3.0) | Awaiting user testing |
| ***REMOVED***4 | MB8611 | ✅ Yes (6 files + HNAP JSON) | ✅ Yes (HNAP fixtures) | ⚠️ **OPEN** - Parser Mismatch | User needs HNAP parser |
| ***REMOVED***5 | XB7 (timeout) | N/A | N/A | ✅ **RESOLVED** (v2.6.0) | Awaiting user confirmation |

---

***REMOVED******REMOVED*** Issue ***REMOVED***1: TC-4400 Login Not Possible

**User:** Mar1usW3
**Status:** Login works but entities unavailable
**Root Cause:** Parser expects `cmconnectionstatus.html` but user's modem may be serving different content

***REMOVED******REMOVED******REMOVED*** HTML Samples Provided ✅

1. **cmswinfo.html** - System info page
   - Software version: 70.12.42-190604
   - Hardware version: TC4400 Rev:3.6.0
   - Uptime: "17 days 00h:38m:36s"
   - Board temperature: -99.0°C (invalid reading)

2. **cmconnectionstatus.html** - Connection status page
   - 32 downstream channels (30 SC-QAM + 2 OFDM)
   - 5 upstream channels (4 SC-QAM + 1 OFDMA)
   - Complete signal data

3. **statsifc.html** - LAN statistics
   - eth0/eth1 stats (bytes, packets, errors, drops)
   - Could be used for extra_attributes in future

***REMOVED******REMOVED******REMOVED*** Test Fixtures Status ✅

**Location:** `tests/parsers/technicolor/tc4400/fixtures/`

```
✅ technicolor_tc4400_cmswinfo.html (matches user sample)
✅ technicolor_tc4400_cmconnectionstatus.html (matches user sample)
✅ technicolor_tc4400_statsifc.html (matches user sample)
```

***REMOVED******REMOVED******REMOVED*** Action Items

- [ ] Debug why parser isn't reading the HTML correctly (entities unavailable)
- [ ] Verify parser can handle both `cmswinfo.html` and `cmconnectionstatus.html`
- [ ] Check if user's HTML differs from test fixture
- [ ] Request debug logs from user showing parse failure
- [ ] Consider: LAN statistics as extra_attributes (future enhancement)

---

***REMOVED******REMOVED*** Issue ***REMOVED***2: XB7 Support

**User:** esand
**Status:** ✅ **RESOLVED in v2.6.0**
**Resolution:** All requested system info fields have been implemented

***REMOVED******REMOVED******REMOVED*** HTML Sample Provided ✅

**File:** Provided in issue comments (used to build XB7 parser)
**Location in tests:** `tests/parsers/technicolor/xb7/fixtures/technicolor_xb7_network_setup.html`

***REMOVED******REMOVED******REMOVED*** Implementation Status ✅

**Completed in v2.6.0 (2025-11-06):**
- ✅ `sensor.cable_modem_system_uptime` - Human-readable uptime
- ✅ `sensor.cable_modem_last_boot_time` - Calculated timestamp
- ✅ `sensor.cable_modem_software_version` - Firmware/software version
- ✅ Primary downstream channel detection

***REMOVED******REMOVED******REMOVED*** Test Fixtures Status ✅

**Location:** `tests/parsers/technicolor/xb7/fixtures/`

```
✅ technicolor_xb7_network_setup.html (complete, all fields parsed)
```

***REMOVED******REMOVED******REMOVED*** Next Steps

- [ ] **User confirmation needed** - Verify sensors appear and are accurate
- [ ] Close issue once user confirms success

---

***REMOVED******REMOVED*** Issue ***REMOVED***3: Netgear CM600 - Login Doesn't Work

**User:** (no username shown)
**Status:** 🧪 **IMPLEMENTED in v3.3.0 - Awaiting User Testing**
**Implementation:** Full JavaScript-based parser with comprehensive test coverage

***REMOVED******REMOVED******REMOVED*** HTML Samples Provided ✅

**Complete set of 7 files captured from real modem:**

1. **index.html** - Main page (914 lines)
2. **DocsisStatus.asp** - Primary data source (816 lines) - Contains `InitDsTableTagValue()` and `InitUsTableTagValue()` JavaScript functions
3. **DashBoard.asp** - Dashboard page (1392 lines)
4. **DocsisOffline.asp** - Offline status page (117 lines)
5. **EventLog.asp** - Event log (291 lines)
6. **RouterStatus.asp** - Router status (2056 lines)
7. **SetPassword.asp** - Password settings (522 lines)

***REMOVED******REMOVED******REMOVED*** Test Fixtures Status ✅

**Location:** `tests/parsers/netgear/fixtures/cm600/`

```
✅ index.html - Main interface page
✅ DocsisStatus.asp - Primary parsing source (JavaScript channel data)
✅ DashBoard.asp - Dashboard with modem info
✅ DocsisOffline.asp - Offline handling
✅ EventLog.asp - Event log page
✅ RouterStatus.asp - Router interface data
✅ SetPassword.asp - Configuration page
```

***REMOVED******REMOVED******REMOVED*** Implementation Status ✅

**Completed in v3.3.0:**
- ✅ Parser created at `custom_components/cable_modem_monitor/parsers/netgear/cm600.py` (384 lines)
- ✅ JavaScript variable extraction from `DocsisStatus.asp`
- ✅ Regex-based parsing of `InitDsTableTagValue()` and `InitUsTableTagValue()` functions
- ✅ Comprehensive test coverage - 5 tests (all passing)
- ✅ Handles downstream and upstream channels
- ✅ System info extraction

***REMOVED******REMOVED******REMOVED*** Next Steps

- [ ] **User testing required** - User needs to upgrade to v3.3.0 and test
- [ ] **Await feedback** - Verify parser works on user's actual modem/firmware
- [ ] **Only close after user confirmation** - Follow issue management policy
- [ ] If successful, move CM600 to "Confirmed Working" in compatibility guide

---

***REMOVED******REMOVED*** Issue ***REMOVED***4: All Entities Unavailable (MB8611)

**User:** dlindnegm
**Status:** ⚠️ **OPEN - Parser Mismatch Detected**
**Root Cause:** User selected "Static" parser but modem uses HNAP protocol

***REMOVED******REMOVED******REMOVED*** HTML Samples Provided ✅ (6 files)

**HTML Pages (5 files from original issue):**

1. **Login.html** - HNAP login page
2. **MotoHome.html** - Main dashboard
3. **MotoStatusConnection.html** - Connection status (26K, channel tables)
4. **MotoStatusSoftware.html** - Software/settings page
5. **MotoStatusLog.html** - Event log

**HNAP API Data (added Nov 5, 2025):**

6. **hnap_full_status.json** ✅ - Complete HNAP `GetMultipleHNAPs` response
   - 33 downstream channels (including OFDM PLC)
   - 4 upstream channels
   - System uptime: "47 days 21h:15m:38s"
   - Format: Caret-delimited channel data (`ID^Status^Mod^ChID^Freq^Power^SNR^Corr^Uncorr^`)

***REMOVED******REMOVED******REMOVED*** Test Fixtures Status ✅

**Location:** `tests/parsers/motorola/fixtures/mb8611_hnap/` and `mb8611_static/`

```
✅ Login.html
✅ MotoHome.html
✅ MotoStatusConnection.html
✅ MotoStatusSoftware.html
✅ MotoStatusLog.html
✅ hnap_full_status.json - Complete HNAP SOAP API response
```

***REMOVED******REMOVED******REMOVED*** Diagnostics Analysis (Nov 13, 2025)

**Problem identified from diagnostics dump:**
```json
"parser_name": "Motorola MB8611 (Static)",  // ❌ Wrong parser selected
"working_url": "https://192.168.100.1/HNAP1/",  // ✅ Modem uses HNAP!
"connection_status": "parser_issue",
"downstream_channel_count": 0,  // ❌ 0 channels parsed
```

**Root cause:** Static parser expects HTML tables at `/MotoStatusConnection.html`, but modem only serves data via HNAP SOAP API at `/HNAP1/`. Parser tried to parse Login.html as if it contained channel tables.

***REMOVED******REMOVED******REMOVED*** Action Items

- [x] Parsers implemented (both HNAP and Static) in v3.1.0
- [x] HNAP JSON fixtures added to test suite
- [x] Diagnostics capability added in v3.2.0
- [x] SSL certificate fixes applied in v3.1.0
- [ ] **User needs to switch to HNAP parser** - Email instructions sent
- [ ] **User reconfigures and tests with HNAP parser**
- [ ] **If still failing, capture HNAP diagnostics** using HTML Capture button
- [ ] Troubleshoot based on HNAP response data

---

***REMOVED******REMOVED*** Issue ***REMOVED***5: Login Timeouts Not Handled

**User:** esand (XB7 owner)
**Status:** ✅ **RESOLVED in v2.6.0**
**Resolution:** Improved exception handling with proper log levels

***REMOVED******REMOVED******REMOVED*** HTML Samples Needed ❌

N/A - This is an exception handling issue, not a parsing issue

***REMOVED******REMOVED******REMOVED*** Implementation Status ✅

**Completed in v2.6.0 (2025-11-06):**
- ✅ Timeout errors logged at DEBUG level (reduces log noise during reboots)
- ✅ Connection errors logged at WARNING level
- ✅ Authentication errors logged at ERROR level
- ✅ Helps distinguish between network issues, modem reboots, and auth problems

***REMOVED******REMOVED******REMOVED*** Next Steps

- [ ] **User confirmation needed** - Verify timeout logs no longer show stack traces
- [ ] Close issue once user confirms success

---

***REMOVED******REMOVED*** Test Fixture Organization

***REMOVED******REMOVED******REMOVED*** Current Structure ✅

**Clean, non-redundant hierarchy:**

```
tests/
├── components/           ***REMOVED*** Component tests
│   ├── test_config_flow.py
│   ├── test_coordinator.py
│   └── ...
├── lib/                 ***REMOVED*** Library/utility tests
│   └── test_utils.py
└── parsers/             ***REMOVED*** Parser tests (grouped)
    ├── arris/
    │   ├── test_sb6141.py
    │   └── fixtures/
    │       └── sb6141/
    │           └── signal.html
    │
    ├── motorola/
    │   ├── test_generic.py
    │   ├── test_mb7621.py
    │   └── fixtures/
    │       ├── generic/
    │       │   ├── MotoConnection.asp
    │       │   └── MotoHome.asp
    │       ├── mb7621/
    │       │   ├── Login.html
    │       │   ├── MotoConnection.asp
    │       │   ├── MotoHome.asp
    │       │   ├── MotoSecurity.asp
    │       │   ├── MotoSnmpLog.asp
    │       │   └── MotoSwInfo.asp
    │       └── mb8611/
    │           ├── mb8611_login_page.txt (need actual page name)
    │           ├── mb8611_landing_page.txt (need actual page name)
    │           ├── mb8611_connection_page.txt (need actual page name)
    │           ├── mb8611_advanced_page.txt (need actual page name)
    │           ├── mb8611_event_log_page.txt (need actual page name)
    │           └── README.md
    │
    └── technicolor/
        ├── test_tc4400.py
        ├── test_xb7.py
        └── fixtures/
            ├── tc4400/
            │   ├── cmswinfo.html
            │   ├── cmconnectionstatus.html
            │   └── statsifc.html
            └── xb7/
                └── network_setup.jst
```

**Structure Principles:**
- ✅ No redundant naming (manufacturer/model in path already)
- ✅ Files named after actual page URLs
- ✅ Tests at manufacturer level
- ✅ Fixtures grouped by model
- ✅ Generic parsers checked last (via code logic)

***REMOVED******REMOVED******REMOVED*** Missing Fixtures ❌

```
tests/parsers/
├── motorola/
│   └── fixtures/
│       └── mb8611/
│           ├── ⚠️ Have HTML, need actual page names from user
│           ├── ❌ HNAP SOAP XML samples (request sent)
│           └── README.md ✅ Documents what's needed
│
└── netgear/  ❌ NEEDS TO BE CREATED
    ├── test_cm600.py (when samples received)
    └── fixtures/
        └── cm600/
            └── (pending HTML samples - request sent)
```

---

***REMOVED******REMOVED*** Recommendations

***REMOVED******REMOVED******REMOVED*** Immediate Actions (Phase 0)

1. **Issue ***REMOVED***2 (XB7):** Implement system info enhancements - HTML already available ✅
2. **Issue ***REMOVED***5 (XB7):** Fix timeout logging - no HTML needed ✅
3. **Issue ***REMOVED***4 (MB8611):** Download existing HTML samples and request HNAP samples
4. **Issue ***REMOVED***3 (CM600):** Request HTML samples from user

***REMOVED******REMOVED******REMOVED*** Phase 1+ Actions

1. **Issue ***REMOVED***1 (TC4400):** Debug parser logic (fixtures already exist)
2. **Issue ***REMOVED***4 (MB8611):** Implement HNAP/SOAP support (Phase 2)
3. **Issue ***REMOVED***3 (CM600):** Implement new parser (after receiving samples)

***REMOVED******REMOVED******REMOVED*** Best Practices for Future Issues

When users report unsupported modems, immediately request:

1. **HTML Samples:**
   - Login page source
   - Connection/status page source
   - System info page source
   - All other relevant pages

2. **Network Inspection (for SOAP/API modems):**
   - Browser DevTools → Network tab
   - Capture XHR/Fetch requests
   - Save request/response bodies

3. **Privacy:**
   - Remind users to redact sensitive info
   - MAC addresses, serial numbers, IPs, credentials

4. **Test Fixture Format:**
   - Save as `.html` or `.txt`
   - Include page URL in filename or comment
   - Attach to GitHub issue

---

***REMOVED******REMOVED*** Next Steps

- [ ] Download MB8611 HTML samples from Issue ***REMOVED***4
- [ ] Create `tests/parsers/motorola/mb8611/fixtures/` directory
- [ ] Request HNAP SOAP samples from MB8611 user
- [ ] Request HTML samples from CM600 user (Issue ***REMOVED***3)
- [ ] Update this document as new fixtures are added
