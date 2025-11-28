***REMOVED*** Arris SB6141 Modem Fixtures

***REMOVED******REMOVED*** Verification Status

✅ **VERIFIED** - Confirmed working by real user

***REMOVED******REMOVED*** Modem Information

| Property | Value |
|----------|-------|
| **Model** | SB6141 |
| **Manufacturer** | Arris (originally Motorola SURFboard) |
| **DOCSIS Version** | 3.0 |
| **Release Year** | 2011 |
| **EOL Year** | 2019 |
| **ISPs** | Comcast, Cox, TWC |
| **Channels** | 8 downstream / 4 upstream |
| **Parser Status** | Verified |
| **Captured By** | @captain-coredump |
| **Capture Date** | October 2025 |

***REMOVED******REMOVED*** User Verification

**Verified by:** @captain-coredump (vreihen)
**Date:** October 2025 (v2.0.0)
**Source:** [Home Assistant Community Forum](https://community.home-assistant.io/t/cable-modem-monitor-track-your-internet-signal-quality-in-home-assistant)

**User Report:**
> "I'm confirming that the ARRIS SB6141 is still working in v2.0.0"

**Working Features:**
- ✅ All 57-58 entities displaying correctly
- ✅ Channel frequencies
- ✅ Signal-to-noise ratios (SNR)
- ✅ Power levels
- ✅ Error statistics (corrected/uncorrected codewords)

**Known Limitations:**
- ⚠️ Software version not available (not exposed by modem web interface)
- ⚠️ System uptime not available (not exposed by modem web interface)

***REMOVED******REMOVED*** Available Fixtures

***REMOVED******REMOVED******REMOVED*** signal.html
- **Source:** HTML samples provided by @captain-coredump
- **Size:** 4.9 KB
- **Content:** Signal status page (`/cmSignal.html`)
- **Captured:** October 2025
- **Authentication:** None required (public page)

**Structure:**
- Transposed HTML table format (rows are channels, columns are metrics)
- Downstream channels: Channel ID, Frequency, SNR, Power, Corrected, Uncorrected
- Upstream channels: Channel ID, Frequency, Power

***REMOVED******REMOVED*** Parser Implementation

**File:** `custom_components/cable_modem_monitor/parsers/arris/sb6141.py`

**Class:** `ArrisSB6141Parser`

**URL Patterns:**
```python
url_patterns = [
    {"path": "/cmSignal.html", "auth_method": "none"},
]
```

**Detection Logic:**
- Checks for "SB6141" in page title or content
- Explicitly excludes SB6190 to prevent false positives
- Priority: 110 (model-specific)

**Parsing Method:**
- Transposed table parsing (rows are channels, not headers)
- HTML table scraping with BeautifulSoup
- No authentication required

***REMOVED******REMOVED*** Test Coverage

**File:** `tests/parsers/arris/test_sb6141.py`

**Tests:** 5 tests, all passing
- ✅ Parser detection
- ✅ Downstream channel parsing (8 channels)
- ✅ Upstream channel parsing (4 channels)
- ✅ System info parsing
- ✅ Transposed table parsing

***REMOVED******REMOVED*** Attribution

- **HTML Samples:** @captain-coredump (vreihen)
- **Parser Development:** Cable Modem Monitor project
- **Verification:** Community testing on Home Assistant forum
- **Documentation:** Commit cd49916 "Update documentation: ARRIS SB6141 confirmed working"

***REMOVED******REMOVED*** Related Documentation

- Commit cd49916: Added to confirmed working status
- ATTRIBUTION.md: Hardware testing contributors
- Home Assistant Community Forum: User confirmation thread

***REMOVED******REMOVED*** Notes

- This is one of the older DOCSIS 3.0 modems still in use
- No authentication required for status page
- Simple HTML table format makes parsing reliable
- User confirmation provides confidence in parser accuracy
- Good example of community-contributed modem support
