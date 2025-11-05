***REMOVED*** Test Fixture Status & Issue HTML Samples

**Date:** November 5, 2025
**Purpose:** Track HTML samples from users and test fixture coverage

---

***REMOVED******REMOVED*** Summary

| Issue | Modem Model | HTML Samples Provided | Fixtures in Repo | Status | Action Needed |
|-------|-------------|----------------------|------------------|--------|---------------|
| ***REMOVED***1 | TC-4400 | ✅ Yes (3 files) | ✅ Yes (3 files) | ⚠️ Parser Issue | Fix parser logic |
| ***REMOVED***2 | XB7 | ✅ Yes (1 file) | ✅ Yes (1 file) | ⚠️ Incomplete | Add system info fields |
| ***REMOVED***3 | Netgear CM600 | ❌ No | ❌ No | 🆕 New Parser Needed | Request HTML samples |
| ***REMOVED***4 | MB8611 | ✅ Yes (5 files) | ❌ No | 🚧 HNAP/SOAP Needed | Add fixtures, Phase 2 |
| ***REMOVED***5 | XB7 (timeout) | N/A | N/A | 📝 Logging Issue | Fix exception handling |

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
**Status:** Authentication working, parsing working, but missing system info fields
**Root Cause:** Parser incomplete - missing uptime, software version, primary channel

***REMOVED******REMOVED******REMOVED*** HTML Sample Provided ✅

**File:** Provided in issue comments (used to build XB7 parser)
**Location in tests:** `tests/parsers/technicolor/xb7/fixtures/technicolor_xb7_network_setup.html`

***REMOVED******REMOVED******REMOVED*** Available Fields in HTML (Not Yet Parsed)

**System Info:**
- ✅ System Uptime: "21 days 15h: 20m: 33s" (Line 512-514)
- ✅ Software Version: "Prod_23.2_231009 & Prod_23.2_231009" (Line 836-837, Download Version)
- ✅ BOOT Version: Also available (Line 830-831)
- ✅ Last Boot Time: Can calculate from uptime

**Channel Info:**
- ✅ Primary Channel: "*Channel ID 10 is the Primary channel" (Line 884)

***REMOVED******REMOVED******REMOVED*** Test Fixtures Status ✅

**Location:** `tests/parsers/technicolor/xb7/fixtures/`

```
✅ technicolor_xb7_network_setup.html (complete, ready for enhancement)
```

***REMOVED******REMOVED******REMOVED*** Action Items

✅ **READY TO IMPLEMENT** - See Phase 0 roadmap

- [ ] Parse System Uptime from HTML (Line 512-514)
- [ ] Parse Download Version as software_version (Line 836-837)
- [ ] Calculate last_boot_time from uptime
- [ ] Parse Primary Channel ID (Line 884)
- [ ] Add 4 new tests to test suite
- [ ] Update Issue ***REMOVED***2 when complete

---

***REMOVED******REMOVED*** Issue ***REMOVED***3: Netgear CM600 - Login Doesn't Work

**User:** (no username shown)
**Status:** New parser needed
**Root Cause:** Netgear CM600 not supported

***REMOVED******REMOVED******REMOVED*** HTML Samples Provided ❌

**No HTML samples provided yet**

***REMOVED******REMOVED******REMOVED*** Action Items

- [ ] **REQUEST HTML SAMPLES FROM USER**
  - Login page (if auth required)
  - Connection/status page with downstream/upstream channels
  - System info page
  - Any other relevant pages

- [ ] Create test fixture directory: `tests/parsers/netgear/cm600/fixtures/`
- [ ] Implement parser (Phase 1 or later)
- [ ] Add to supported modems list

***REMOVED******REMOVED******REMOVED*** Template Message for User

```markdown
@<username> To help add support for your Netgear CM600, could you please provide HTML samples?

**What we need:**
1. Right-click on the modem's web interface pages and "View Page Source"
2. Save the HTML for these pages:
   - Login page (if auth is required)
   - Connection/Status page (with downstream/upstream channel data)
   - System information page
   - Any other pages showing modem metrics

**How to share:**
- Save each page as a `.txt` or `.html` file
- Attach to this issue

**Privacy:** Please redact any sensitive info like:
- MAC addresses
- Serial numbers
- IP addresses
- Usernames/passwords

Thank you!
```

---

***REMOVED******REMOVED*** Issue ***REMOVED***4: All Entities Unavailable (MB8611)

**User:** dlindnegm
**Status:** HNAP/SOAP protocol needed (Phase 2 work)
**Root Cause:** MB8611 uses HNAP (Home Network Administration Protocol), not HTML scraping

***REMOVED******REMOVED******REMOVED*** HTML Samples Provided ✅ (5 files)

**Attached to Issue ***REMOVED***4:**

1. **Login Page.txt** - HNAP login page
2. **Landing Page.txt** - Main dashboard after login
3. **Advanced Page.txt** - Advanced settings
4. **Connection Page.txt** - Connection status (may contain HNAP endpoints)
5. **Event Log Page.txt** - System event log

**Note:** These are actual HTML page sources, but MB8611 likely uses HNAP SOAP API calls underneath.

***REMOVED******REMOVED******REMOVED*** Test Fixtures Status ❌

**Location:** DOES NOT EXIST YET

**Needs creation:** `tests/parsers/motorola/mb8611/fixtures/`

```
❌ login_page.html (need to add from Issue ***REMOVED***4)
❌ landing_page.html (need to add from Issue ***REMOVED***4)
❌ connection_page.html (need to add from Issue ***REMOVED***4)
❌ HNAP SOAP response samples (NEED TO REQUEST)
```

***REMOVED******REMOVED******REMOVED*** Action Items

- [ ] **Download HTML samples from Issue ***REMOVED***4 attachments**
  - [Login Page.txt](https://github.com/user-attachments/files/23267508/Login.Page.txt)
  - [Landing Page.txt](https://github.com/user-attachments/files/23267507/Landing.Page.txt)
  - [Advanced Page.txt](https://github.com/user-attachments/files/23267505/Advanced.Page.txt)
  - [Connection Page.txt](https://github.com/user-attachments/files/23267509/Connection.Page.txt)
  - [Event Log Page.txt](https://github.com/user-attachments/files/23267506/Event.Log.Page.txt)

- [ ] **REQUEST HNAP SOAP RESPONSE SAMPLES**
  - User needs to capture HNAP API calls using browser dev tools
  - Network tab → Filter XHR → Capture POST requests to `/HNAP1/`
  - Save request/response XML for:
    - GetMotoStatusStartupSequence
    - GetMotoStatusConnectionInfo
    - GetMotoStatusDownstreamChannelInfo
    - GetMotoStatusUpstreamChannelInfo

- [ ] Create fixtures directory structure
- [ ] Implement MB8611 parser (Phase 2)
- [ ] Test with user's modem

***REMOVED******REMOVED******REMOVED*** Template Message for User (HNAP Samples)

```markdown
@dlindnegm Thank you for the HTML samples! However, the MB8611 uses HNAP (a SOAP-based API) which means we need to capture the actual API requests to parse the data.

**How to capture HNAP requests:**

1. Open your modem's web interface (`http://192.168.100.1`)
2. Open browser Developer Tools (F12)
3. Go to the **Network** tab
4. Filter by **XHR** or **Fetch**
5. Navigate to the Connection/Status page
6. Look for POST requests to `/HNAP1/`
7. Click on each request and copy:
   - **Request payload** (XML)
   - **Response** (XML)

**HNAP actions we need:**
- GetMotoStatusStartupSequence
- GetMotoStatusConnectionInfo
- GetMotoStatusDownstreamChannelInfo
- GetMotoStatusUpstreamChannelInfo
- Login (if there's a login SOAP action)

Please attach these as text files. Thank you!
```

---

***REMOVED******REMOVED*** Issue ***REMOVED***5: Login Timeouts Not Handled

**User:** esand (XB7 owner)
**Status:** Logging issue, not parser issue
**Root Cause:** Timeout exceptions logging full stack traces instead of graceful debug messages

***REMOVED******REMOVED******REMOVED*** HTML Samples Needed ❌

N/A - This is an exception handling issue, not a parsing issue

***REMOVED******REMOVED******REMOVED*** Action Items

✅ **READY TO IMPLEMENT** - See Phase 0 roadmap

- [ ] Improve exception handling in XB7 `login()` method
- [ ] Specific catch blocks for timeout exceptions
- [ ] Log timeouts at debug level, not error level
- [ ] Apply pattern to other parsers
- [ ] Add timeout test cases

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
