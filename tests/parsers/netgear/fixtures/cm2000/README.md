***REMOVED*** Netgear CM2000 (Nighthawk) Test Fixtures

***REMOVED******REMOVED*** Modem Information

| Property | Value |
|----------|-------|
| **Model** | CM2000 (Nighthawk) |
| **Manufacturer** | Netgear |
| **Type** | Cable Modem (standalone, no router) |
| **DOCSIS Version** | 3.1 |
| **Channel Bonding** | 32x8 (DOCSIS 3.0) + OFDM (DOCSIS 3.1) |
| **Max Speed** | 2.5 Gbps downstream |
| **Firmware Tested** | V8.01.02 |
| **Hardware Version** | 1.01 |

***REMOVED******REMOVED*** Links

- [Netgear CM2000 Product Page](https://www.netgear.com/home/wifi/modems/cm2000/)
- [Netgear CM2000 Support](https://www.netgear.com/support/product/cm2000)
- [Related Issue: ***REMOVED***38](https://github.com/kwschulz/cable_modem_monitor/issues/38)

***REMOVED******REMOVED*** Authentication

- **Method**: Form-based POST to `/goform/Login`
- **Username Field**: `loginName` (value: "admin")
- **Password Field**: `loginPassword`
- **Default URL**: `http://192.168.100.1/`

***REMOVED******REMOVED*** Fixture Files

| File | Status | Description |
|------|--------|-------------|
| index.htm | ✓ Available | Login page (unauthenticated) |
| DocsisStatus.htm | ✓ Available | DOCSIS channel data (authenticated) |

***REMOVED******REMOVED*** Data Available

Unlike the CM600, the CM2000 **does provide** uptime and system time!

***REMOVED******REMOVED******REMOVED*** InitTagValue() - System Status
| Index | Field | Example Value |
|-------|-------|---------------|
| 0 | Acquire DS Frequency | `579000000` |
| 1 | Acquire DS Status | `Locked` |
| 2 | Connectivity State | `OK` |
| 3 | Connectivity Comment | `Operational` |
| 4 | Boot State | `OK` |
| 5 | Boot State Comment | `Operational` |
| 8 | Security Status | `Enabled` |
| 9 | Security Type | `BPI+` |
| **10** | **Current System Time** | `Tue Nov 25 12:48:02 2025` |
| **14** | **System Up Time** | `7 days 00:00:01` |
| 15 | OFDM DS Channel Count | `3` |
| 16 | OFDM US Channel Count | `1` |

***REMOVED******REMOVED******REMOVED*** InitDsTableTagValue() - 32 Downstream Channels (DOCSIS 3.0)

| Field | Example |
|-------|---------|
| Channel Count | 32 |
| Per Channel | ch\|lock\|mod\|id\|freq\|power\|snr\|corrected\|uncorrected |

**Sample Data:**
| Ch | Lock | Mod | ID | Frequency | Power | SNR | Corr | Uncorr |
|----|------|-----|----:|----------:|------:|----:|-----:|-------:|
| 1 | Locked | QAM256 | 17 | 579 MHz | 7.8 dBmV | 41.4 dB | 80 | 418 |
| 2 | Locked | QAM256 | 14 | 561 MHz | 7.8 dBmV | 41.4 dB | 75 | 429 |
| ... | ... | ... | ... | ... | ... | ... | ... | ... |
| 31 | Locked | QAM256 | 45 | 741 MHz | 9.2 dBmV | 41.2 dB | 80 | 423 |

***REMOVED******REMOVED******REMOVED*** InitUsTableTagValue() - 8 Upstream Channels (DOCSIS 3.0)

| Field | Example |
|-------|---------|
| Channel Count | 8 (4 locked) |
| Per Channel | ch\|lock\|type\|id\|sym_rate\|freq\|power |

**Sample Data:**
| Ch | Lock | Type | ID | Symbol Rate | Frequency | Power |
|----|------|------|----:|------------:|----------:|------:|
| 1 | Locked | ATDMA | 2 | 5120 Ksym/s | 22.8 MHz | 38.0 dBmV |
| 2 | Locked | ATDMA | 3 | 5120 Ksym/s | 29.2 MHz | 38.0 dBmV |
| 3 | Locked | ATDMA | 1 | 5120 Ksym/s | 16.3 MHz | 38.0 dBmV |
| 4 | Locked | ATDMA | 4 | 5120 Ksym/s | 35.6 MHz | 37.8 dBmV |

***REMOVED******REMOVED******REMOVED*** InitOfdmDsTableTagValue() - OFDM Downstream (DOCSIS 3.1)

| Field | Example |
|-------|---------|
| Channel Count | 2 (1 locked) |
| Per Channel | ch\|lock\|subcarriers\|id\|freq\|power\|snr\|active\|corrected\|uncorrected\|unerrored |

**Sample Data:**
| Ch | Lock | Subcarriers | ID | Frequency | Power | SNR |
|----|------|-------------|----:|----------:|------:|----:|
| 1 | Locked | 0,1,2,3 | 33 | 762 MHz | 9.88 dBmV | 40.9 dB |

***REMOVED******REMOVED******REMOVED*** InitOfdmUsTableTagValue() - OFDM Upstream (DOCSIS 3.1)

| Field | Example |
|-------|---------|
| Channel Count | 2 (0 locked in this capture) |

***REMOVED******REMOVED*** Contributor Information

- **Original Issue**: [***REMOVED***38 - Netgear CM2000 Support Request](https://github.com/kwschulz/cable_modem_monitor/issues/38)
- **Contributor**: @m4dh4tt3r-88
- **Fixtures Captured**: November 2025
- **Parser Status**: ✓ Verified

***REMOVED******REMOVED*** Comparison with CM600

| Feature | CM600 | CM2000 |
|---------|-------|--------|
| DOCSIS | 3.0 | 3.1 |
| DS Channels | 24 | 32 + OFDM |
| US Channels | 8 | 8 + OFDM |
| System Uptime | ✗ Not available | ✓ Available |
| System Time | ✗ Not available | ✓ Available |
| Authentication | HTTP Basic | Form POST |
