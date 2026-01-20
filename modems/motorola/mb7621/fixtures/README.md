# Motorola MB7621 Test Fixtures


<!-- AUTO-GENERATED FROM metadata.yaml - DO NOT EDIT BELOW -->
## Quick Facts

| Spec | Value |
|------|-------|
| **DOCSIS** | 3.0 |
| **Released** | 2017 |
| **Status** | Current |
| **ISPs** | Comcast, Cox, Spectrum, TWC, CableOne, RCN |
| **Parser** | ✅ Verified |

<!-- END AUTO-GENERATED -->

## Modem Information

| Property | Value |
|----------|-------|
| **Model** | MB7621 |
| **Manufacturer** | Motorola |
| **Type** | Cable Modem (standalone, no router) |
| **DOCSIS Version** | 3.0 |
| **Release Year** | 2015 |
| **ISPs** | Comcast, Cox, Spectrum, TWC |
| **Channel Bonding** | 24x8 (24 downstream, 8 upstream) |
| **Max Speed** | 1 Gbps downstream |
| **Firmware Tested** | 7621-5.7.1.5 |
| **Hardware Version** | V1.0 |
| **Parser Status** | Verified |
| **Captured By** | @kwschulz |
| **Capture Date** | Development |

## Links

- [Motorola MB7621 Product Page](https://www.motorola.com/us/mb7621)
- [Motorola MB7621 Support](https://motorolanetwork.com/mb7621.html)

## Authentication

- **Method**: Form-based POST to `/goform/login`
- **Username Field**: `loginUsername`
- **Password Field**: `loginPassword`
- **Default IP**: `192.168.100.1`

## Directory Structure

```
mb7621/
├── Login.html          # Core - authentication
├── MotoHome.asp        # Core - dashboard/detection
├── MotoConnection.asp  # Core - channel data
├── MotoSwInfo.asp      # Core - software info
├── MotoSecurity.asp    # Core - restart functionality (used by tests)
├── README.md
└── extended/
    └── MotoSnmpLog.asp   # Event logs
```

## Core Fixtures

| File | Description | Key Data |
|------|-------------|----------|
| `Login.html` | Login page | Authentication form |
| `MotoHome.asp` | Home/Dashboard | Basic status overview |
| `MotoConnection.asp` | DOCSIS channel data | DS/US channels, frequencies, power, SNR |
| `MotoSwInfo.asp` | Software information | Hardware/firmware version, serial number |
| `MotoSecurity.asp` | Security/restart page | Restart functionality |

## Extended Fixtures (`extended/`)

| File | Description |
|------|-------------|
| `MotoSnmpLog.asp` | Event logs |

## Data Available

### MotoSwInfo.asp - Software Information

| Field | Example Value |
|-------|---------------|
| Cable Specification Version | DOCSIS 3.0 |
| Hardware Version | V1.0 |
| Software Version | 7621-5.7.1.5 |
| Cable Modem MAC Address | (redacted) |
| Cable Modem Serial Number | 2480-MB7621-30-5076 |
| CM Certificate | Installed |

### MotoConnection.asp - Channel Data

| Data Type | Details |
|-----------|---------|
| Downstream Channels | Up to 24 channels |
| Upstream Channels | Up to 8 channels |
| System Up Time | Available |

**Downstream Channel Fields:**
- Channel ID
- Lock Status
- Frequency (MHz)
- SNR (dB)
- Power Level (dBmV)
- Modulation
- Corrected/Uncorrected codewords

**Upstream Channel Fields:**
- Channel ID
- Lock Status
- Frequency (MHz)
- Power Level (dBmV)
- Channel Type
- Symbol Rate

## Contributor Information

- **Original Contributor**: kwschulz (maintainer)
- **Fixtures Captured**: Development testing
- **Parser Status**: Verified

## Notes for Parser Development

1. **Primary data source**: `MotoConnection.asp` contains all channel data
2. **System info**: `MotoSwInfo.asp` has hardware/firmware versions
3. **Restart endpoint**: POST to `/goform/Restart`
4. **Authentication**: Form-based with plain and Base64 password encoding attempts
