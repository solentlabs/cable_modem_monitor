# Netgear C7000v2 Modem Fixtures


<!-- AUTO-GENERATED FROM metadata.yaml - DO NOT EDIT BELOW -->
## Quick Facts

| Spec | Value |
|------|-------|
| **DOCSIS** | 3.0 |
| **Released** | 2016 |
| **Status** | Current |
| **ISPs** | Comcast |
| **Parser** | ⏳ Pending |

<!-- END AUTO-GENERATED -->

## Modem Information

| Property | Value |
|----------|-------|
| **Model** | C7000v2 |
| **Manufacturer** | Netgear |
| **Related Issue** | [#61](https://github.com/solentlabs/cable_modem_monitor/issues/61) |
| **Captured By** | @Anthranilic |
| **Capture Date** | December 2025 |

## Authentication

**Type:** HTTP Basic Auth

## Files

| File | Description |
|------|-------------|
| `DocsisStatus.htm` | DOCSIS channel data (downstream/upstream) |
| `RouterStatus.htm` | System info (firmware, uptime) |
| `index.htm` | Main page for detection |

### Extended Files

| File | Description |
|------|-------------|
| `DashBoard.htm` | Dashboard overview |
| `eventLog.htm` | Event logs |
| `DocsisOffline.htm` | Offline page |

## Notes

- User provided manually redacted diagnostics after sanitization gap was discovered
- C7000v2 uses same page structure and parsing logic as C3700
- 24x8 channel bonding (DOCSIS 3.0)
- Nighthawk AC1900 WiFi Cable Modem Router combo device
