***REMOVED*** Arris SB6190 Modem Fixtures


<!-- AUTO-GENERATED FROM metadata.yaml - DO NOT EDIT BELOW -->
***REMOVED******REMOVED*** Quick Facts

| Spec | Value |
|------|-------|
| **DOCSIS** | 3.0 |
| **Released** | 2016 |
| **Status** | EOL 2023 |
| **ISPs** | Comcast, Cox, Spectrum, TWC |
| **Parser** | ✅ Verified |

<!-- END AUTO-GENERATED -->

***REMOVED******REMOVED*** Verification Status

⚠️ **UNVERIFIED** - No confirmed user reports

***REMOVED******REMOVED*** Modem Information

| Property | Value |
|----------|-------|
| **Model** | SB6190 |
| **Manufacturer** | Arris (Motorola SURFboard) |
| **DOCSIS Version** | 3.0 |
| **Release Year** | 2014 |
| **EOL Year** | 2023 |
| **ISPs** | Comcast, Cox, Spectrum, TWC |
| **Channels** | Up to 32 downstream / 8 upstream |
| **Parser Status** | Unverified |
| **Captured By** | @sfennell |
| **Capture Date** | November 2025 |

***REMOVED******REMOVED*** Implementation History

**Added by:** sfennell (@contributor@example.org)
**Date:** November 7, 2025
**Commit:** a6d09ad "Added support for Arris SB6190"
**Release:** v3.0.0

**Commit Message:**
> "Added support for Arris SB6190, similar to the SB6140, however URL and page layout are a little different. Parser and Test based off SB6140."

**Note:** Parser was developed based on SB6141 code (author likely meant SB6141, not SB6140), but no user has confirmed it works with a real SB6190 modem.

***REMOVED******REMOVED*** Verification Needed

⚠️ **This parser has NOT been verified against a real modem!**

**To verify this parser, we need:**
1. A user with an Arris SB6190 modem
2. HTML capture from their modem's status page
3. Confirmation that all entities display correctly
4. Test against the captured HTML to validate parser accuracy

**If you have an SB6190:**
- Please test this integration and report results!
- Open a GitHub issue or comment on the HA community forum
- Provide HTML diagnostics using the "Capture HTML" button
- Help us move this to "VERIFIED" status!

***REMOVED******REMOVED*** Available Fixtures

***REMOVED******REMOVED******REMOVED*** arris_sb6190.html
- **Source:** Unknown - likely synthetic or from online examples
- **Size:** 15.8 KB
- **Content:** Status page HTML
- **Captured:** Unknown date/source
- **Authentication:** Unknown

**⚠️ Provenance Unknown:**
- Not confirmed to be from a real SB6190 modem
- May be based on documentation or other sources
- Parser may not work correctly with real hardware

***REMOVED******REMOVED*** Parser Implementation

**File:** `custom_components/cable_modem_monitor/parsers/arris/sb6190.py`

**Class:** `ArrisSB6190Parser`

**URL Patterns:**
```python
url_patterns = [
    {"path": "/cmSignal.asp", "auth_method": "none"},  ***REMOVED*** Note: .asp not .html
]
```

**Detection Logic:**
- Checks for "SB6190" in page content
- Priority: 110 (model-specific)

**Parsing Method:**
- Similar to SB6141 but adapted for .asp page format
- HTML table scraping with BeautifulSoup
- No authentication (assumed)

***REMOVED******REMOVED*** Test Coverage

**File:** `tests/parsers/arris/test_sb6190.py`

**Tests:** 5 tests, all passing against fixture
- ✅ Parser detection
- ✅ Downstream channel parsing
- ✅ Upstream channel parsing
- ✅ System info parsing
- ✅ Transposed table parsing

**⚠️ Important:** Tests pass against the fixture, but fixture may not represent real modem output!

***REMOVED******REMOVED*** Known Issues

1. **No User Confirmation**
   - No reports of successful usage
   - May not work with real hardware
   - URL path may be incorrect (.asp vs .html)

2. **Fixture Provenance Unknown**
   - Source of test fixture unclear
   - May not match real modem output
   - Could lead to parsing failures

3. **Authentication Unclear**
   - Assumes no authentication required
   - Real modem may require Basic Auth or other method

***REMOVED******REMOVED*** How to Help

**If you own an Arris SB6190:**

1. **Install the integration** (it should detect your modem as SB6190)
2. **Check if entities work** - Do you see channel data?
3. **Capture diagnostics:**
   - Press "Capture HTML" button
   - Download diagnostics within 5 minutes
   - Post to GitHub issue or HA community forum
4. **Report results:**
   - GitHub Issue: https://github.com/solentlabs/cable_modem_monitor/issues
   - HA Forum: https://community.home-assistant.io/t/cable-modem-monitor-track-your-internet-signal-quality-in-home-assistant

***REMOVED******REMOVED*** Related Documentation

- Commit a6d09ad: Initial SB6190 support
- Release v3.0.0: SB6190 included in release notes
- No community forum mentions found
- No GitHub issues for SB6190 found

***REMOVED******REMOVED*** Comparison to SB6141

**Similarities:**
- Both Arris/Motorola SURFboard modems
- Both DOCSIS 3.0
- Similar HTML table structure
- No authentication (assumed)

**Differences:**
- SB6190: `/cmSignal.asp` (ASP)
- SB6141: `/cmSignal.html` (HTML)
- SB6190: More channels (32 DS / 8 US)
- SB6141: Fewer channels (8 DS / 4 US)

***REMOVED******REMOVED*** Recommendation

⚠️ **Until verified by a real user, consider this parser experimental.**

**For UI marking:** This modem should be marked with an asterisk (*) or "Unverified" tag in the modem selection dropdown to indicate it hasn't been tested with real hardware.

**For maintainers:** When a user confirms this works (or doesn't work), update this README with their findings and move the status to either VERIFIED or BROKEN.
