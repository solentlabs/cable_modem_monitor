# Test Fixture Requirements

> **Submitting data for a new modem?** See [MODEM_REQUEST.md](MODEM_REQUEST.md) first - it covers capture methods, PII review, and the submission process.

This guide explains the technical requirements for test fixtures used in parser development.

## Fixture Directory Structure

```
tests/parsers/<manufacturer>/fixtures/<model>/
├── metadata.yaml           # Required: modem metadata
├── <model>_status.html     # Required: main status page
├── <model>_info.html       # Optional: system info page
├── <model>_logs.html       # Optional: event logs page
└── ...                     # Any other relevant pages
```

## metadata.yaml Template

Every fixture directory **must** include a `metadata.yaml` file:

```yaml
# Modem metadata - verified against official sources
# This file is read by scripts/generate_fixture_index.py

release_date: 2020          # Year modem was released (YYYY or YYYY-MM)
end_of_life: null           # Year discontinued, or null if still sold
docsis_version: "3.1"       # DOCSIS version: "3.0", "3.1", "4.0"
isps:                       # Known compatible ISPs
  - Comcast
  - Spectrum
  - Cox
source: https://example.com/datasheet.pdf  # URL to official specs
```

### Finding Release Date

- Check the modem's FCC filing date: https://www.fcc.gov/oet/ea/fccid
- Search for product announcements or datasheets
- Copyright dates in the modem's web interface can provide hints

### DOCSIS Version

| Version | Max Downstream | Max Upstream | Typical Release Era |
|---------|---------------|--------------|---------------------|
| 3.0     | ~340 Mbps     | ~120 Mbps    | 2008-2016          |
| 3.1     | ~1 Gbps       | ~200 Mbps    | 2016-2020          |
| 4.0     | ~10 Gbps      | ~6 Gbps      | 2020+              |

## PII Scrubbing Checklist

**Before committing fixtures, you MUST remove all personally identifiable information:**

### Must Remove/Anonymize

| Data Type | Example | Replace With |
|-----------|---------|--------------|
| MAC Address | `A4:B5:C6:D7:E8:F9` | `00:00:00:00:00:00` |
| Serial Number | `MJ1234567890` | `XXXXXXXXXXXX` |
| Public IP | `73.45.123.89` | `0.0.0.0` |
| Account ID | `8401234567` | `0000000000` |
| Subscriber ID | `SUB-12345` | `SUB-XXXXX` |

### Safe to Keep

These values are useful for testing and do not identify you:

- ✅ Frequencies (MHz)
- ✅ Power levels (dBmV)
- ✅ SNR values (dB)
- ✅ Channel IDs
- ✅ Modulation types (QAM256, OFDM)
- ✅ Error counts (corrected/uncorrectable)
- ✅ System uptime
- ✅ Firmware version
- ✅ Model name
- ✅ Private IPs (192.168.x.x, 10.x.x.x)

### Quick Scrub Commands

```bash
# Find potential MAC addresses
grep -oE '([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}' fixture.html

# Find potential serial numbers (varies by manufacturer)
grep -oiE 'serial[^<]*' fixture.html

# Find public IPs (not 192.168.x.x or 10.x.x.x)
grep -oE '\b([0-9]{1,3}\.){3}[0-9]{1,3}\b' fixture.html | grep -v '^192\.168\.' | grep -v '^10\.'
```

## Capture All Available Pages

Modems often have multiple pages with useful data. Capture all that are relevant:

### Common Pages to Capture

| Page Type | Common URLs | Data Available |
|-----------|-------------|----------------|
| Status | `/status.html`, `/cmconnectionstatus.html` | Channels, power, SNR |
| System Info | `/info.html`, `/cmswinfo.html`, `/vers_cgi` | Firmware, uptime, model |
| Event Logs | `/eventlog.html`, `/cmeventlog.html` | Error history |
| Network | `/network.html`, `/cmnetworkstatus.html` | IP config, DHCP |

### Why Capture Everything?

1. **Future enhancements** - We may add support for event logs, network status, etc.
2. **Better testing** - More data = more comprehensive test coverage
3. **Parser improvements** - Additional pages help understand the modem's interface

## Using the HAR Capture Script (Recommended)

The easiest way to capture fixtures properly:

```bash
# Install dependencies
pip install playwright && playwright install chromium

# Run the capture script
python scripts/capture_modem.py
```

The script automatically:
- Records all pages you visit
- Prompts for metadata
- Sanitizes PII
- Creates proper directory structure

## Manual Capture Checklist

If capturing manually (View Page Source → Save):

- [ ] Created fixture directory: `tests/parsers/<mfr>/fixtures/<model>/`
- [ ] Saved all relevant HTML pages
- [ ] Created `metadata.yaml` with all fields
- [ ] Scrubbed MAC addresses
- [ ] Scrubbed serial numbers
- [ ] Scrubbed public IPs
- [ ] Scrubbed account/subscriber IDs
- [ ] Verified no other PII remains

## Example: Complete Fixture

```
tests/parsers/arris/fixtures/sb6141/
├── metadata.yaml
├── sb6141_status.html      # Downstream/upstream channels
└── sb6141_info.html        # System information
```

**metadata.yaml:**
```yaml
release_date: 2011
end_of_life: 2019
docsis_version: "3.0"
isps:
  - Comcast
  - Cox
  - Spectrum
source: https://content.abt.com/documents/48624/SB6141-US-EN.pdf
```

## Questions?

- Open a [GitHub Discussion](https://github.com/solentlabs/cable_modem_monitor/discussions)
- Check existing fixtures for examples
- Ask in your PR if unsure about any requirements
