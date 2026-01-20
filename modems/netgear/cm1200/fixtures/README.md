# Netgear CM1200 Modem Fixtures


<!-- AUTO-GENERATED FROM metadata.yaml - DO NOT EDIT BELOW -->
## Quick Facts

| Spec | Value |
|------|-------|
| **DOCSIS** | 3.1 |
| **Released** | 2019 |
| **Status** | Current |
| **ISPs** | Comcast, Spectrum, Cox |
| **Parser** | ✅ Verified |

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

## Parser Architecture

The CM1200 does **NOT** use HTML tables with column headers. Instead, channel data is
embedded in JavaScript functions that return pipe-delimited strings:

```
┌─────────────────────────────────────────────────────────────────┐
│  <script>                                                       │
│    function InitDsTableTagValue() {                             │
│      var tagValueList = '32|1|Locked|QAM256|32|765000000...';   │
│      return tagValueList.split("|");                            │
│    }                                                            │
│  </script>                                                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  _extract_tagvaluelist(soup, "InitDsTableTagValue")             │
│    → Regex extracts: var tagValueList = '...'                   │
│    → Splits by '|' into positional array                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  values = ['32', '1', 'Locked', 'QAM256', '32', '765000000 Hz'] │
│              ↓      ↓     ↓        ↓       ↓         ↓          │
│           count  ch_num lock   modulation ch_id    freq         │
│                                                                  │
│  Position-based parsing (NO column names in data!)              │
└─────────────────────────────────────────────────────────────────┘
```

### Why channel_type is hardcoded

Since there are **4 separate JavaScript functions** for each channel type, the parser
knows which type it's parsing based on which function it extracts from:

| JS Function | Channel Type | Parser Method |
|-------------|--------------|---------------|
| `InitDsTableTagValue()` | QAM | `_parse_downstream_from_js()` |
| `InitDsOfdmTableTagValue()` | OFDM | `_parse_ofdm_downstream()` |
| `InitUsTableTagValue()` | ATDMA | `_parse_upstream_from_js()` |
| `InitUsOfdmaTableTagValue()` | OFDMA | `_parse_ofdma_upstream()` |

The `channel_type` is implicit in the function name, not in the data itself.

## Channel Data Formats

### Downstream QAM (InitDsTableTagValue)
```
count|num|lock|modulation|channel_id|frequency|power|snr|corrected|uncorrected
```
- Up to 32 SC-QAM channels (QAM256)
- 9 fields per channel

### Downstream OFDM (InitDsOfdmTableTagValue)
```
count|num|lock|profile|channel_id|frequency|power|snr|range|unerrored|correctable|uncorrectable
```
- Up to 2 OFDM channels
- 11 fields per channel

### Upstream ATDMA (InitUsTableTagValue)
```
count|num|lock|type|channel_id|symbol_rate|frequency|power
```
- Up to 8 channels
- 7 fields per channel
- Note: Symbol Rate comes before Frequency (different from CM2000)
- `type` field contains "ATDMA" from the data itself

### Upstream OFDMA (InitUsOfdmaTableTagValue)
```
count|num|lock|profile|channel_id|frequency|power
```
- Up to 2 OFDMA channels
- 6 fields per channel

### System Info (InitTagValue)
- Index 10: Current System Time
- Index 14: System Uptime

## Notes

- DOCSIS 3.1 modem with both SC-QAM and OFDM/OFDMA support
- Similar to CM2000 but uses HTTP Basic Auth instead of form-based auth
