***REMOVED*** Technicolor TC4400 Test Fixtures

***REMOVED******REMOVED*** Modem Information

| Property | Value |
|----------|-------|
| **Model** | TC4400 |
| **Manufacturer** | Technicolor |
| **Type** | Cable Modem (standalone) |
| **DOCSIS Version** | 3.1 |
| **Hardware Version** | TC4400 Rev:3.6.0 |
| **Firmware Tested** | 70.12.42-190604 |

***REMOVED******REMOVED*** Links

- [Technicolor TC4400 Support](https://www.technicolor.com/)
- [Related Issue: ***REMOVED***1](https://github.com/kwschulz/cable_modem_monitor/issues/1)

***REMOVED******REMOVED*** Authentication

- **Method**: HTTP Basic Authentication
- **Default Username**: `admin`
- **Default Password**: (varies by ISP)
- **Default IP**: `192.168.100.1`

***REMOVED******REMOVED*** Fixture Files

| File | Description | Key Data |
|------|-------------|----------|
| `cmconnectionstatus.html` | DOCSIS connection status | DS/US channels, OFDM, power, SNR |
| `cmswinfo.html` | Software information | Hardware/firmware version, uptime |
| `statsifc.html` | Interface statistics | Network stats |

***REMOVED******REMOVED*** Data Available

***REMOVED******REMOVED******REMOVED*** cmswinfo.html - Software Information

| Field | Example Value |
|-------|---------------|
| Standard Specification Compliant | Docsis 3.1 |
| Hardware Version | TC4400 Rev:3.6.0 |
| Software Version | 70.12.42-190604 |
| Cable Modem MAC Address | (redacted) |
| Cable Modem Serial Number | (redacted) |
| CM Certificate | Installed |
| System Up Time | 17 days 00h:38m:36s |
| Network Access | Allowed |
| Board Temperature | -99.0 degrees Celsius |

***REMOVED******REMOVED******REMOVED*** cmconnectionstatus.html - Channel Data

| Data Type | Details |
|-----------|---------|
| Downstream Channels | DOCSIS 3.0 + OFDM channels |
| Upstream Channels | DOCSIS 3.0 + OFDMA channels |
| Channel Fields | ID, Lock, Type, Bonding, Frequency, Width, SNR, Power, Modulation |
| Error Codewords | Unerrored, Corrected, Uncorrected |

**Downstream Channel Fields:**
- Channel ID
- Lock Status
- Channel Type (SC-QAM, OFDM)
- Bonding Status
- Frequency (Hz)
- Width (Hz)
- SNR (dB)
- Power Level (dBmV)
- Modulation
- Unerrored/Corrected/Uncorrected Codewords

**Upstream Channel Fields:**
- Channel ID
- Lock Status
- Channel Type (SC-QAM, OFDMA)
- Bonding Status
- Frequency (Hz)
- Width (Hz)
- Power Level (dBmV)
- Modulation

***REMOVED******REMOVED*** Parser Capabilities

| Capability | Supported |
|------------|-----------|
| Downstream Channels | Yes |
| Upstream Channels | Yes |
| System Uptime | Yes |
| Hardware Version | Yes |
| Software Version | Yes |
| Last Boot Time | No (can be calculated) |
| Restart | No |

***REMOVED******REMOVED*** Contributor Information

- **Parser Status**: Unverified (needs user confirmation)
- **Fixtures Captured**: Development testing

***REMOVED******REMOVED*** Notes for Parser Development

1. **Primary data source**: `cmconnectionstatus.html` for channel data
2. **System info**: `cmswinfo.html` for uptime and version info
3. **Table structure**: Uses `<td class='hd'>` for headers
4. **Uptime format**: "X days HHh:MMm:SSs"
5. **Detection**: Look for "Board ID:" or "Build Timestamp:" in HTML
