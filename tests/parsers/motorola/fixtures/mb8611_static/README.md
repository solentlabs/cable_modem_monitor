***REMOVED*** Motorola MB8611 Static Parser Test Fixtures

***REMOVED******REMOVED*** Modem Information

| Property | Value |
|----------|-------|
| **Model** | MB8611 |
| **Manufacturer** | Motorola |
| **Type** | Cable Modem (standalone, no router) |
| **DOCSIS Version** | 3.1 |
| **Channel Bonding** | 32x8 (DOCSIS 3.0) + OFDM (DOCSIS 3.1) |
| **Max Speed** | 2.5 Gbps downstream |
| **Firmware Tested** | 8611-19.2.18 |
| **Hardware Version** | V1.0 |

***REMOVED******REMOVED*** Links

- [Motorola MB8611 Product Page](https://www.motorola.com/us/mb8611)
- [Related Issues: ***REMOVED***4, ***REMOVED***6](https://github.com/kwschulz/cable_modem_monitor/issues/4) - HNAP authentication issues

***REMOVED******REMOVED*** Parser Variant

This fixture set is for the **static HTML parser** which scrapes data directly from HTML pages. The MB8611 also has an HNAP/SOAP API (see `mb8611_hnap` fixtures), but HNAP authentication has known SSL and protocol issues.

***REMOVED******REMOVED*** Authentication

- **Method**: None required for static pages
- **Default IP**: `192.168.100.1`
- **Note**: Some pages may require authentication depending on firmware

***REMOVED******REMOVED*** Fixture Files

| File | Description | Key Data |
|------|-------------|----------|
| `MotoHome.html` | Home/Dashboard | Basic status overview |
| `MotoStatusConnection.html` | DOCSIS channel data | DS/US channels, OFDM, frequencies, power, SNR |
| `MotoStatusSoftware.html` | Software information | Hardware/firmware version, serial number |
| `MotoStatusSecurity.html` | Security settings | Certificate status |
| `MotoStatusLog.html` | Event logs | Log entries |

***REMOVED******REMOVED*** Data Available

***REMOVED******REMOVED******REMOVED*** MotoStatusSoftware.html - Software Information

| Field | Example Value |
|-------|---------------|
| Cable Specification Version | DOCSIS 3.1 |
| Hardware Version | V1.0 |
| Software Version | 8611-19.2.18 |
| Cable Modem MAC Address | (redacted) |
| Cable Modem Serial Number | 2750-MB8611-30-5259 |
| CM Certificate | Installed |
| Customer Version | Prod_19.2_d31 |

***REMOVED******REMOVED******REMOVED*** MotoStatusConnection.html - Channel Data

| Data Type | Details |
|-----------|---------|
| Downstream Channels | Up to 32 DOCSIS 3.0 channels |
| Upstream Channels | Up to 8 DOCSIS 3.0 channels |
| OFDM Downstream | DOCSIS 3.1 OFDM channels |
| OFDM Upstream | DOCSIS 3.1 OFDMA channels |
| System Up Time | Available |

***REMOVED******REMOVED*** Contributor Information

- **Parser Status**: Unverified (static fallback parser)
- **Purpose**: Fallback when HNAP authentication fails

***REMOVED******REMOVED*** Comparison with HNAP Parser

| Feature | Static Parser | HNAP Parser |
|---------|--------------|-------------|
| Authentication | None/Simple | HNAP SOAP |
| Data Format | HTML scraping | JSON/XML API |
| Reliability | Higher | SSL/protocol issues |
| Data Completeness | Good | Full API access |

***REMOVED******REMOVED*** Notes for Parser Development

1. HTML uses span elements with IDs for data (e.g., `StatusSoftwareSpecVer`)
2. Data is populated via JavaScript after page load
3. System uptime available in `MotoConnSystemUpTime` element
4. No restart capability in static parser (requires HNAP)
