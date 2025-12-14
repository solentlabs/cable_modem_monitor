***REMOVED*** ARRIS CM820B Modem Fixtures

<!-- AUTO-GENERATED FROM metadata.yaml - DO NOT EDIT BELOW -->
***REMOVED******REMOVED*** Quick Facts

| Spec | Value |
|------|-------|
| **DOCSIS** | 3.0 |
| **Released** | 2011 |
| **Status** | Current |
| **ISPs** | Volya |
| **Parser** | ✅ Verified |

<!-- END AUTO-GENERATED -->

***REMOVED******REMOVED*** Verification Status

✅ **VERIFIED** - Confirmed working by real user

***REMOVED******REMOVED*** Modem Information

| Property | Value |
|----------|-------|
| **Model** | CM820B |
| **Manufacturer** | ARRIS |
| **DOCSIS Version** | EuroDOCSIS 3.0 |
| **Release Year** | 2011 |
| **Chipset** | Intel Puma 5 |
| **Channels** | 8 downstream / 4 upstream |
| **Authentication** | None required |
| **Parser Status** | Verified |
| **Contributed By** | @dimkalinux |
| **Contribution Date** | December 2025 |

***REMOVED******REMOVED*** User Verification

**Verified by:** @dimkalinux
**Date:** December 2025 (v3.10.0)
**Source:** [GitHub PR ***REMOVED***57](https://github.com/solentlabs/cable_modem_monitor/pull/57)

**Working Features:**
- 8 downstream channels with power, SNR, frequency, modulation
- 4 upstream channels with power, frequency, symbol rate
- System uptime parsing
- FEC error statistics (corrected/uncorrected codewords)

**Known Limitations:**
- Software version parsing returns "Unknown" (field present but not parsed)
- URLs require `/cgi-bin/` prefix (handled by parser)

***REMOVED******REMOVED*** Available Fixtures

***REMOVED******REMOVED******REMOVED*** cm820b_info.html
- **Source:** `/cgi-bin/vers_cgi`
- **Content:** Hardware/firmware information page
- **Contains:** Model, vendor, hardware revision, serial number, firmware version

***REMOVED******REMOVED******REMOVED*** cm820b_status.html
- **Source:** `/cgi-bin/status_cgi`
- **Content:** RF parameters and status page
- **Contains:** Downstream/upstream channel data, system uptime, interface status

***REMOVED******REMOVED*** Parser Implementation

**File:** `custom_components/cable_modem_monitor/parsers/arris/cm820b.py`

**Class:** `ArrisCM820BParser`

**URL Patterns:**
```python
url_patterns = [
    {"path": "/cgi-bin/vers_cgi", "auth_method": "none"},
    {"path": "/cgi-bin/status_cgi", "auth_method": "none"},
]
```

**Detection Logic:**
- Checks for "CM820B" in page content
- Detects "EuroDOCSIS" or "Touchstone" identifiers
- Priority: 110 (model-specific)

***REMOVED******REMOVED*** Test Coverage

**File:** `tests/parsers/arris/test_cm820b.py`

**Tests:** 8 tests, all passing
- Parser detection
- Downstream channel parsing (8 channels)
- Upstream channel parsing (4 channels)
- System info parsing
- Uptime parsing

***REMOVED******REMOVED*** Notes

- This is a EuroDOCSIS 3.0 variant used primarily in European markets
- Uses Intel Puma 5 chipset (predecessor to problematic Puma 6)
- No authentication required for status pages
- First modem verified from Ukraine (Volya ISP)
- Simple HTML table format with CGI-based URLs

***REMOVED******REMOVED*** Attribution

- **Parser & Fixtures:** @dimkalinux
- **Verification:** Real-world testing on Volya ISP (Ukraine)
- **Documentation:** Cable Modem Monitor project
