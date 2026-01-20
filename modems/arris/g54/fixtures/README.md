# Arris G54 Gateway Fixtures


<!-- AUTO-GENERATED FROM metadata.yaml - DO NOT EDIT BELOW -->
## Quick Facts

| Spec | Value |
|------|-------|
| **DOCSIS** | 3.1 |
| **Released** | 2023 |
| **Status** | Current |
| **ISPs** | Cox, Spectrum, Xfinity |
| **Parser** | ⏳ Pending |

<!-- END AUTO-GENERATED -->

## Modem Information

| Property | Value |
|----------|-------|
| **Model** | G54 |
| **Manufacturer** | Arris/CommScope |
| **Chipset** | Broadcom BCM3390 |
| **Type** | Gateway (modem + router) |
| **Related Issue** | [#72](https://github.com/solentlabs/cable_modem_monitor/issues/72) |
| **Captured By** | @MrAct1on |
| **Capture Date** | December 2025 |

## Authentication

**Type:** Form-based (LuCI session)

- Login endpoint: `POST /cgi-bin/luci/`
- Form fields: `luci_username`, `luci_password`
- Session: `sysauth` cookie

## Data Endpoint

`GET /cgi-bin/luci/admin/gateway/wan_status?status=1`

Returns JSON with:
- `docsis.dschannel.dschannel[]` - Downstream SC-QAM channels
- `docsis.ofdmchannel.ofdmchannel[]` - Downstream OFDM channels
- `docsis.uschannel.uschannel[]` - Upstream SC-QAM channels
- `docsis.ofdmachannel.ofdmachannel[]` - Upstream OFDMA channels
- `uptime` - System uptime in seconds
- `cm` - Cable modem info (MAC, serial)

## Files

| File | Description |
|------|-------------|
| `wan_status.json` | DOCSIS channel data from API |
| `login_page.html` | Login page for detection |
| `uptime.json` | Uptime API response |

## Notes

- This is a gateway device (modem + router combo)
- Uses LuCI (OpenWrt-based) web interface
- Different URL structure from standard Arris modems
- Modem was in Bridge mode during capture (WiFi disabled)
- Firmware contains `puma_hw_ver` fields (legacy naming, actual chipset is BCM3390)
