# Virgin Media SuperHub 5 Modem Fixtures


<!-- AUTO-GENERATED FROM metadata.yaml - DO NOT EDIT BELOW -->
## Quick Facts

| Spec | Value |
|------|-------|
| **DOCSIS** | 3.1 |
| **Released** | 2021 |
| **Status** | Current |
| **ISPs** | Virgin Media UK |
| **Parser** | ⏳ Pending |

<!-- END AUTO-GENERATED -->

## Modem Information

| Property | Value |
|----------|-------|
| **Brand** | Virgin Media Hub 5 |
| **OEM Manufacturer** | Sagemcom |
| **OEM Model** | F3896LG-VMB |
| **Chipset** | Broadcom 3390S |
| **Firmware Tested** | bbt076-b |
| **Related Issue** | [#82](https://github.com/solentlabs/cable_modem_monitor/issues/82) |
| **Data Contributed By** | [@Dinth](https://github.com/Dinth) |
| **Capture Date** | December 2025 |

**Sources:**
- OEM/chipset info: [ISPreview](https://www.ispreview.co.uk/index.php/2021/10/virgin-media-o2-officially-launches-hub-5-broadband-router.html)
- User's `bootFilename` shows `vmdg660` - linkage to F3896LG-VMB is inferred

## Authentication

**Type:** None - REST API endpoints are unauthenticated

## REST API Endpoints

The SuperHub 5 exposes a REST API at `/rest/v1/cablemodem/`. Fixtures are named after endpoint paths:

| Endpoint | Fixture | Description |
|----------|---------|-------------|
| `/rest/v1/cablemodem/downstream` | `downstream.json` | SC-QAM + OFDM channels |
| `/rest/v1/cablemodem/upstream` | `upstream.json` | ATDMA + OFDMA channels |
| `/rest/v1/cablemodem/state_` | `state.json` | Uptime, DOCSIS, status |
| `/rest/v1/cablemodem/serviceflows` | `serviceflows.json` | Bandwidth/QoS |

Note: Some endpoints have trailing underscores (`state_`, `primary_`).

## Channel Summary

**Downstream:**
- 33 SC-QAM channels (QAM256, 8 MHz each)
- 1 OFDM channel (QAM4096, 94 MHz, 4K FFT)

**Upstream:**
- 5 ATDMA channels (QAM64)
- 1 OFDMA channel (QAM256, 10 MHz, 2K FFT)

## Notes

- **Mock server candidate** - simple JSON, no auth, clear endpoints
- Modem mode uses 192.168.100.1, router mode uses 192.168.0.1
