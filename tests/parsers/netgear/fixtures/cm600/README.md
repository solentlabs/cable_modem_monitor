***REMOVED*** Netgear CM600 Test Fixtures


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

***REMOVED******REMOVED*** Modem Information

| Property | Value |
|----------|-------|
| **Model** | CM600 (CM600-100NAS) |
| **Manufacturer** | Netgear |
| **Type** | Cable Modem (standalone, no router) |
| **DOCSIS Version** | 3.0 |
| **Channel Bonding** | 24x8 (24 downstream, 8 upstream) |
| **Max Speed** | 960 Mbps downstream |
| **Release Year** | 2016 |
| **EOL Year** | 2023 |
| **ISPs** | Comcast, Cox, Spectrum, TWC |
| **Firmware Tested** | V1.01.22 |
| **Hardware Version** | 1.01B |
| **Parser Status** | Verified |
| **Captured By** | @chairstacker |
| **Capture Date** | November 2025 |

***REMOVED******REMOVED*** Links

- [Netgear CM600 Product Page](https://www.netgear.com/home/wifi/modems/cm600/)
- [Netgear CM600 Support (EOL)](https://www.netgear.com/support/product/cm600)
- [CM600 Data Sheet (PDF)](https://www.downloads.netgear.com/files/GDC/datasheet/en/CM600.pdf)
- [Quick Start Guide (PDF)](https://www.downloads.netgear.com/files/GDC/CM600/CM600_All_MSOs_QSG_EN.pdf)
- [Related Issue: ***REMOVED***3](https://github.com/solentlabs/cable_modem_monitor/issues/3)

***REMOVED******REMOVED*** Authentication

- **Method**: HTTP Basic Authentication
- **Default Username**: `admin`
- **Default Password**: `password`
- **Default IP**: `192.168.100.1`

***REMOVED******REMOVED*** Directory Structure

```
cm600/
├── DocsisStatus.asp      ***REMOVED*** Core - channel data
├── RouterStatus.asp      ***REMOVED*** Core - system info
├── DashBoard.asp         ***REMOVED*** Core - overview
├── DocsisOffline.asp     ***REMOVED*** Core - offline state
├── index.html            ***REMOVED*** Core - detection
├── README.md
└── extended/             ***REMOVED*** Reference files
    ├── EventLog.asp
    ├── GPL_rev1.htm
    └── SetPassword.asp
```

***REMOVED******REMOVED*** Core Fixtures

| File | Description | Key Data |
|------|-------------|----------|
| `DocsisStatus.asp` | DOCSIS channel data | DS/US channels, frequencies, power, SNR |
| `RouterStatus.asp` | System information | Hardware/firmware version, network config |
| `DashBoard.asp` | Connection overview | Internet status, device counts |
| `DocsisOffline.asp` | Offline error page | Error display template |
| `index.html` | Main frameset page | Firmware version, device type |

***REMOVED******REMOVED*** Extended Fixtures (`extended/`)

| File | Description |
|------|-------------|
| `EventLog.asp` | Event logs (table structure only) |
| `SetPassword.asp` | Password change page (form structure only) |
| `GPL_rev1.htm` | GPL license (no data) |

***REMOVED******REMOVED*** Known Firmware Limitations

The CM600 firmware (V1.01.22) does **NOT** expose:
- **System Uptime** - Index [35] in RouterStatus is always empty
- **Current System Time** - Index [36] in RouterStatus is always empty
- **Last Boot Time** - Cannot be calculated without uptime

These fields exist in the HTML as placeholders but are never populated by the firmware.

---

***REMOVED******REMOVED*** Complete Data Field Inventory

***REMOVED******REMOVED******REMOVED*** DocsisStatus.asp

***REMOVED******REMOVED******REMOVED******REMOVED*** InitTagValue() - DOCSIS Status
| Index | Field | Example Value | Notes |
|-------|-------|---------------|-------|
| 0 | Acquire DS Frequency | `141000000` | Hz |
| 1 | Acquire DS Status | `Locked` | Locked/Not Locked |
| 2 | Connectivity State | `OK` | |
| 3 | Connectivity Comment | `Operational` | |
| 4 | Boot State | `OK` | |
| 5 | Boot State Comment | `Operational` | |
| 6 | Config File Status | `OK` | |
| 7 | Config File Name | `yawming\yawmingCM.cfg` | |
| 8 | Security Status | `Disabled` | Enabled/Disabled |
| 9 | Security Type | `Disabled` | BPI+/Disabled |
| 10 | Current System Time | `Fri Dec 12 ***IPv6*** 2014` | **REDACTED/PLACEHOLDER** |
| 11 | Startup Frequency | `141000000` | Hz |
| 12 | DS Partial Service | `0` | 0=full, 1=partial |
| 13 | US Partial Service | `0` | 0=full, 1=partial |

***REMOVED******REMOVED******REMOVED******REMOVED*** InitDsTableTagValue() - Downstream Channels
| Index | Field | Example Value | Notes |
|-------|-------|---------------|-------|
| 0 | Channel Count | `8` | Number of DS channels |

**Per Channel (9 fields each, starting at index 1):**
| Offset | Field | Example | Notes |
|--------|-------|---------|-------|
| +0 | Channel Number | `1` | Display number |
| +1 | Lock Status | `Locked` | Locked/Not Locked |
| +2 | Modulation | `QAM256` | QAM256/QAM64 |
| +3 | Channel ID | `1` | DOCSIS Channel ID |
| +4 | Frequency | `141000000 Hz` | In Hz |
| +5 | Power | `-5` | dBmV |
| +6 | SNR | `41.9` | dB |
| +7 | Corrected | `0` | Correctable errors |
| +8 | Uncorrected | `0` | Uncorrectable errors |

**Sample Downstream Data (8 channels):**
| Ch | Lock | Mod | ID | Frequency | Power | SNR | Corr | Uncorr |
|----|------|-----|----|-----------:|------:|----:|-----:|-------:|
| 1 | Locked | QAM256 | 1 | 141 MHz | -5.0 dBmV | 41.9 dB | 0 | 0 |
| 2 | Locked | QAM256 | 2 | 147 MHz | -4.7 dBmV | 43.6 dB | 0 | 0 |
| 3 | Locked | QAM256 | 3 | 153 MHz | -4.7 dBmV | 44.2 dB | 0 | 0 |
| 4 | Locked | QAM256 | 4 | 159 MHz | -4.6 dBmV | 44.4 dB | 0 | 0 |
| 5 | Locked | QAM256 | 5 | 165 MHz | -5.0 dBmV | 43.9 dB | 0 | 0 |
| 6 | Locked | QAM256 | 6 | 171 MHz | -5.7 dBmV | 43.1 dB | 0 | 0 |
| 7 | Locked | QAM256 | 7 | 177 MHz | -7.1 dBmV | 42.2 dB | 0 | 0 |
| 8 | Locked | QAM256 | 8 | 183 MHz | -7.2 dBmV | 42.4 dB | 0 | 0 |

***REMOVED******REMOVED******REMOVED******REMOVED*** InitUsTableTagValue() - Upstream Channels
| Index | Field | Example Value | Notes |
|-------|-------|---------------|-------|
| 0 | Channel Count | `4` | Number of US channels |

**Per Channel (7 fields each, starting at index 1):**
| Offset | Field | Example | Notes |
|--------|-------|---------|-------|
| +0 | Channel Number | `1` | Display number |
| +1 | Lock Status | `Locked` | Locked/Not Locked |
| +2 | Channel Type | `ATDMA` | ATDMA/TDMA/SCDMA |
| +3 | Channel ID | `1` | DOCSIS Channel ID |
| +4 | Symbol Rate | `2560` | Ksym/sec |
| +5 | Frequency | `13400000 Hz` | In Hz |
| +6 | Power | `50` | dBmV |

**Sample Upstream Data (4 channels):**
| Ch | Lock | Type | ID | Symbol Rate | Frequency | Power |
|----|------|------|----:|------------:|----------:|------:|
| 1 | Locked | ATDMA | 1 | 2560 Ksym/s | 13.4 MHz | 50.0 dBmV |
| 2 | Locked | ATDMA | 2 | 2560 Ksym/s | 16.7 MHz | 50.0 dBmV |
| 3 | Locked | ATDMA | 3 | 2560 Ksym/s | 20.0 MHz | 49.0 dBmV |
| 4 | Locked | ATDMA | 4 | 2560 Ksym/s | 23.3 MHz | 48.3 dBmV |

***REMOVED******REMOVED******REMOVED******REMOVED*** InitProvRateTableTagValue() - Provisioned Rates
| Index | Field | Example Value | Notes |
|-------|-------|---------------|-------|
| 0 | Is Genie | `0` | 0=no, 1=yes |
| 1 | DS Provisioned Rate | `0` | bps (0 = not available) |
| 2 | US Provisioned Rate | `0` | bps (0 = not available) |

***REMOVED******REMOVED******REMOVED******REMOVED*** InitCmIpProvModeTag() - IP Provisioning
| Index | Field | Example Value | Notes |
|-------|-------|---------------|-------|
| 0 | Is Retail | `1` | 0=ISP, 1=retail |
| 1 | IP Prov Mode | `Honor MDD` | IPv4/IPv6/Dual/Honor MDD |
| 2 | MIB Value | `honorMdd(4)` | SNMP MIB value |

---

***REMOVED******REMOVED******REMOVED*** RouterStatus.asp

***REMOVED******REMOVED******REMOVED******REMOVED*** InitTagValue() - System Information
| Index | Field | Example Value | Notes |
|-------|-------|---------------|-------|
| 0 | Hardware Version | `1.01B` | |
| 1 | Firmware Version | `V1.01.22` | |
| 2 | Serial Number | `***SERIAL***` | Redacted in fixtures |
| 3 | DOCSIS Mode | `1` | |
| 4 | Cable MAC | `XX:XX:XX:XX:XX:XX` | Redacted |
| 5 | Internet IP/Mask | `***.***.***.173/16` | Redacted |
| 6 | Internet Gateway | `***.***.***.254` | Redacted |
| 7 | DNS Servers | `168.95.1.1, ...` | |
| 8 | CM Certificate | `Allowed` | Allowed/Not Allowed |
| 9 | LAN MAC | `XX:XX:XX:XX:XX:XX` | Redacted |
| 10 | WAN IP | `---.---.---.---` | Empty if not available |
| 11 | DHCP Mode | `DHCP Client` | |
| 12 | WAN Gateway | `---.---.---.---` | Empty |
| 13 | LAN DNS | `168.95.1.1` | |
| 14 | LAN MAC (alt) | `XX:XX:XX:XX:XX:XX` | Redacted |
| 15 | LAN IP/Mask | `192.168.0.1/24` | |
| 16 | Guest Network | `Off` | On/Off |
| 17-34 | Wireless Settings | (empty) | Not applicable (no WiFi) |
| **35** | **System Uptime** | **(empty)** | **NOT POPULATED** |
| **36** | **System Time** | **(empty)** | **NOT POPULATED** |
| 37-47 | Reserved | (empty) | |
| 48 | Unknown flag | `0` | |
| 49-56 | Unknown | `---` | |
| 57-60 | Unknown flags | `0, 0, 1, 0` | |

---

***REMOVED******REMOVED******REMOVED*** DashBoard.asp

***REMOVED******REMOVED******REMOVED******REMOVED*** InitTagValue() - Dashboard Status
| Index | Field | Example Value | Notes |
|-------|-------|---------------|-------|
| 0 | Unknown | `0` | |
| 1 | Internet Status | `Good` | Good/Bad |
| 2-7 | Unknown | (empty) | |
| 8 | Attached Devices | `2` | Count |
| 9-11 | Unknown flags | `0, 1, 0` | |
| 12-16 | Unknown | (empty) | |
| 17-24 | Status flags | `0` | |
| 25 | Unknown flag | `1` | |
| 26-29 | Unknown | `0` | |
| 30 | WAN IP | `---.---.---.---` | Empty |

---

***REMOVED******REMOVED******REMOVED*** index.html

***REMOVED******REMOVED******REMOVED******REMOVED*** InitTagValue() - Basic Info
| Index | Field | Example Value | Notes |
|-------|-------|---------------|-------|
| 0 | Firmware Version | `V1.01.22` | |
| 1-4 | Unknown flags | `0` | |
| 5 | Device Type | `retail` | retail/ISP |
| 6-12 | Unknown flags | `0` | |

---

***REMOVED******REMOVED*** Contributor Information

- **Original Issue**: [***REMOVED***3 - Netgear CM600 Login Doesn't Work](https://github.com/solentlabs/cable_modem_monitor/issues/3)
- **Contributor**: @chairstacker
- **Fixtures Captured**: November 2025
- **Parser Status**: Verified working (v3.5.1+)

***REMOVED******REMOVED*** Notes for Parser Development

1. **Primary data source**: `DocsisStatus.asp` contains all channel data
2. **System info**: `RouterStatus.asp` has hardware/firmware versions
3. **No uptime data**: Firmware limitation, cannot be worked around
4. **Restart endpoint**: POST to `/goform/RouterStatus` with `RsAction=2`
5. **Restart behavior**: Connection drops immediately (treat as success)
