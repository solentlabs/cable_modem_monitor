# Netgear CM1200 Modem Fixtures


<!-- AUTO-GENERATED FROM metadata.yaml - DO NOT EDIT BELOW -->
## Quick Facts

| Spec | Value |
|------|-------|
| **DOCSIS** | 3.1 |
| **Released** | 2019 |
| **Status** | Current |
| **ISPs** | Comcast, Spectrum, Cox |
| **Parser** | ⏳ Pending |

<!-- END AUTO-GENERATED -->

## Modem Information

| Property | Value |
|----------|-------|
| **Model** | CM1200 |
| **Manufacturer** | Netgear |
| **Related Issue** | [#63](https://github.com/solentlabs/cable_modem_monitor/issues/63) |
| **Captured By** | @DeFlanko |
| **Capture Date** | December 2025 |

## Authentication

**Type:** HTTP Basic Auth
- Default username: `admin`
- Password: User-configured

## Files

| File | Description |
|------|-------------|
| `DocsisStatus.htm` | Main DOCSIS status page with channel data |
| `extended/DashBoard.htm` | Dashboard page with system overview |

## Channel Data Format

### Downstream (InitDsTableTagValue)
```
count|num|lock|modulation|channel_id|frequency|power|snr|corrected|uncorrected
```
- 32 SC-QAM channels (QAM256)
- 9 fields per channel

### Upstream (InitUsTableTagValue)
```
count|num|lock|type|channel_id|symbol_rate|frequency|power
```
- Up to 8 channels (ATDMA)
- 7 fields per channel
- Note: Symbol Rate comes before Frequency (different from CM2000)

### System Info (InitTagValue)
- Index 10: Current System Time
- Index 14: System Uptime

## Notes

- DOCSIS 3.1 modem but capture shows only SC-QAM channels (no OFDM)
- May support OFDM with different ISP configuration
- Similar to CM2000 but uses HTTP Basic Auth instead of form-based auth
