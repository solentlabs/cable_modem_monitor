# ARRIS CM3500B Modem Fixtures


<!-- AUTO-GENERATED FROM metadata.yaml - DO NOT EDIT BELOW -->
## Quick Facts

| Spec | Value |
|------|-------|
| **DOCSIS** | 3.1 |
| **Status** | Current |
| **ISPs** | Vodafone Germany |
| **Parser** | ⏳ Pending |

<!-- END AUTO-GENERATED -->

## Modem Information

| Property | Value |
|----------|-------|
| **Model** | CM3500B |
| **Manufacturer** | ARRIS |
| **Related Issue** | [#73](https://github.com/solentlabs/cable_modem_monitor/issues/73) |
| **Captured By** | @ChBi89 |
| **Capture Date** | December 2025 |

## Authentication

**Type:** Form-based POST

- Login URL: `/cgi-bin/login_cgi`
- Username field: `username`
- Password field: `password`
- Session: Cookie-based (`credential`)

## Channel Summary

| Type | Count | Notes |
|------|-------|-------|
| Downstream QAM | 24+ | 256QAM |
| Downstream OFDM | 2 | 4K FFT (DOCSIS 3.1) |
| Upstream QAM | 4 | ATDMA |
| Upstream OFDMA | 1 | 2K FFT (DOCSIS 3.1) |

## Files

| File | Description |
|------|-------------|
| `status_cgi.html` | Main status page with all channel data and uptime |
| `vers_cgi.html` | Hardware/firmware version info |
| `extended/` | Additional pages (event log, CM state, etc.) |

## Notes

- European modem variant (EuroDOCSIS)
- ISP: Vodafone Germany (Unitymedia network)
- Uses MaxLinear RF chipset
- HTTPS with self-signed certificate
