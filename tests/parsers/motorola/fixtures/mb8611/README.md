# Motorola MB8611 Test Fixtures


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
| **Model** | MB8611 |
| **Manufacturer** | Motorola |
| **DOCSIS Version** | 3.1 |
| **Release Year** | 2020 |
| **ISPs** | Comcast, Xfinity, Cox, Spectrum |
| **Channels** | 32 DS / 8 US + 2 OFDM |
| **Protocol** | HNAP (HTTPS with self-signed certificate) |
| **Firmware Tested** | 8611-19.2.18 |
| **Captured By** | @dlindnegm |
| **Capture Date** | October 2025 |

## Directory Structure

```
mb8611/
├── Login.html               # Core - authentication
├── MotoHome.html            # Core - dashboard/detection
├── MotoStatusConnection.html # Core - channel data tables
├── MotoStatusSoftware.html  # Core - hardware/software versions
├── MotoStatusSecurity.html  # Core - restart functionality
├── hnap_full_status.json    # Core - HNAP API response
├── README.md
└── extended/
    └── MotoStatusLog.html      # Event logs
```

## Core Fixtures

### HNAP API Response

- **hnap_full_status.json** - Complete `GetMultipleHNAPs` response with channel data
  - 33 downstream channels (including OFDM PLC)
  - 4 upstream channels
  - Format: Caret-delimited (`ID^Status^Mod^ChID^Freq^Power^SNR^Corr^Uncorr^`)

### HTML Pages

| File | Purpose |
|------|---------|
| `Login.html` | Authentication page, HNAP JS init |
| `MotoHome.html` | Main dashboard |
| `MotoStatusConnection.html` | Channel data tables |
| `MotoStatusSoftware.html` | Hardware/software versions |
| `MotoStatusSecurity.html` | Restart functionality |

## Extended Fixtures (`extended/`)

| File | Purpose |
|------|---------|
| `MotoStatusLog.html` | Event logs |

## Authentication

Uses HNAP challenge-response authentication (HMAC-MD5).
- Default credentials: `admin` / `motorola`
- Implementation credit: @BowlesCR (Chris Bowles)

## References

- Issue #4: Original fixture capture by @dlindnegm
- Issue #6: HNAP authentication implementation
- Prior art: xNinjaKittyx/mb8600 repository
