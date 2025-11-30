***REMOVED*** Motorola MB8611 Test Fixtures

***REMOVED******REMOVED*** Modem Information

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

***REMOVED******REMOVED*** Directory Structure

```
mb8611/
├── Login.html               ***REMOVED*** Core - authentication
├── MotoHome.html            ***REMOVED*** Core - dashboard/detection
├── MotoStatusConnection.html ***REMOVED*** Core - channel data tables
├── MotoStatusSoftware.html  ***REMOVED*** Core - hardware/software versions
├── MotoStatusSecurity.html  ***REMOVED*** Core - restart functionality
├── hnap_full_status.json    ***REMOVED*** Core - HNAP API response
├── README.md
└── extended/
    └── MotoStatusLog.html      ***REMOVED*** Event logs
```

***REMOVED******REMOVED*** Core Fixtures

***REMOVED******REMOVED******REMOVED*** HNAP API Response

- **hnap_full_status.json** - Complete `GetMultipleHNAPs` response with channel data
  - 33 downstream channels (including OFDM PLC)
  - 4 upstream channels
  - Format: Caret-delimited (`ID^Status^Mod^ChID^Freq^Power^SNR^Corr^Uncorr^`)

***REMOVED******REMOVED******REMOVED*** HTML Pages

| File | Purpose |
|------|---------|
| `Login.html` | Authentication page, HNAP JS init |
| `MotoHome.html` | Main dashboard |
| `MotoStatusConnection.html` | Channel data tables |
| `MotoStatusSoftware.html` | Hardware/software versions |
| `MotoStatusSecurity.html` | Restart functionality |

***REMOVED******REMOVED*** Extended Fixtures (`extended/`)

| File | Purpose |
|------|---------|
| `MotoStatusLog.html` | Event logs |

***REMOVED******REMOVED*** Authentication

Uses HNAP challenge-response authentication (HMAC-MD5).
- Default credentials: `admin` / `motorola`
- Implementation credit: @BowlesCR (Chris Bowles)

***REMOVED******REMOVED*** References

- Issue ***REMOVED***4: Original fixture capture by @dlindnegm
- Issue ***REMOVED***6: HNAP authentication implementation
- Prior art: xNinjaKittyx/mb8600 repository
