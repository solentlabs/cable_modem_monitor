# Technicolor XB7 (CGM4331COM) Test Fixtures


<!-- AUTO-GENERATED FROM metadata.yaml - DO NOT EDIT BELOW -->
## Quick Facts

| Spec | Value |
|------|-------|
| **DOCSIS** | 3.1 |
| **Released** | 2020 |
| **Status** | Current |
| **ISPs** | Comcast |
| **Parser** | ⏳ Pending |

<!-- END AUTO-GENERATED -->

## Modem Information

| Property | Value |
|----------|-------|
| **Model** | XB7 / CGM4331COM |
| **Manufacturer** | Technicolor |
| **Type** | Cable Modem + Router (Gateway) |
| **DOCSIS Version** | 3.1 |
| **Release Year** | 2021 |
| **ISPs** | Rogers, Comcast, Xfinity |
| **Parser Status** | Verified |
| **Captured By** | @kwschulz |
| **Capture Date** | Development |

## Links

- [Rogers XB7 Information](https://www.rogers.com/)
- [Comcast XB7 Information](https://www.xfinity.com/)

## Authentication

- **Method**: Form-based POST to `/check.jst`
- **Username Field**: `username`
- **Password Field**: `password`
- **Success Redirect**: `/at_a_glance.jst`
- **Default IP**: `10.0.0.1`

## Fixture Files

| File | Description | Key Data |
|------|-------------|----------|
| `network_setup.jst` | Network setup/status page | DS/US channels, system info, error codewords |

## Data Available

### network_setup.jst - Channel and System Data

This page uses a transposed table format where:
- Rows = Metrics (Channel ID, Lock Status, Frequency, SNR, Power, Modulation)
- Columns = Channels
- Each cell contains `<div class="netWidth">value</div>`

**System Information:**
| Field | Example |
|-------|---------|
| Serial Number | (redacted) |
| CM MAC / Hardware Address | (redacted) |
| Acquire Downstream | Status |
| Upstream Ranging | Status |
| System Uptime | 21 days 15h: 20m: 33s |
| Download Version | Software version |

**Downstream Channels (DOCSIS 3.0):**
| Field | Description |
|-------|-------------|
| Channel ID | DOCSIS channel identifier |
| Lock Status | Locked/Unlocked |
| Frequency | MHz |
| SNR | Signal-to-Noise Ratio (dB) |
| Power Level | dBmV |
| Modulation | QAM256, etc. |

**Upstream Channels:**
| Field | Description |
|-------|-------------|
| Channel ID | DOCSIS channel identifier |
| Lock Status | Locked/Unlocked |
| Frequency | MHz |
| Power Level | dBmV |
| Symbol Rate | Ksym/sec |
| Channel Type | TDMA, ATDMA, OFDMA |

**Error Codewords (CM Error Codewords table):**
| Field | Description |
|-------|-------------|
| Channel ID | Matches downstream channel |
| Correctable Codewords | FEC corrected errors |
| Uncorrectable Codewords | FEC uncorrectable errors |

## Parser Capabilities

| Capability | Supported |
|------------|-----------|
| Downstream Channels | Yes |
| Upstream Channels | Yes |
| System Uptime | Yes |
| Last Boot Time | Yes (calculated) |
| Software Version | Yes |
| Hardware Version | No |
| Restart | No |

## Contributor Information

- **Parser Status**: Unverified (needs user confirmation)
- **ISP Variations**: May vary between Rogers and Comcast deployments

## Notes for Parser Development

1. **Table format**: Transposed - rows are metrics, columns are channels
2. **Cell values**: Wrapped in `<div class="netWidth">` elements
3. **Row labels**: Use `<th class="row-label">` elements
4. **Error table**: Separate "CM Error Codewords" table for corrected/uncorrected
5. **Uptime format**: "X days Xh: Xm: Xs" (note spaces around colons)
6. **Primary channel**: Note at bottom indicates primary channel ID
7. **Detection**: Look for `network_setup.jst` URL or "Channel Bonding Value" + netWidth divs
8. **Localization**: Page includes Italian translations (Rogers/Italian market?)
