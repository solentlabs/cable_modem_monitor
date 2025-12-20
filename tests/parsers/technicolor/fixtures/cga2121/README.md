# Technicolor CGA2121 Modem Fixtures


<!-- AUTO-GENERATED FROM metadata.yaml - DO NOT EDIT BELOW -->
## Quick Facts

| Spec | Value |
|------|-------|
| **DOCSIS** | 3.0 |
| **Released** | 2015 |
| **Status** | Current |
| **ISPs** | Telia |
| **Parser** | ⏳ Pending |

<!-- END AUTO-GENERATED -->

## Modem Information

| Property | Value |
|----------|-------|
| **Model** | CGA2121 |
| **Manufacturer** | Technicolor |
| **Related Issue** | [#75](https://github.com/solentlabs/cable_modem_monitor/issues/75) |
| **Captured By** | @sgofferj |
| **Capture Date** | December 2025 |

## Authentication

**Type:** Form-based POST

- Endpoint: `/goform/logon`
- Fields: `username_login`, `password_login`, `language_selector`
- Default username: `admin`

## Files

| File | Description |
|------|-------------|
| `st_docsis.html` | DOCSIS status page with channel data |
| `extended/logon.html` | Login page (for reference) |

## Channel Data Available

| Type | Count | Fields |
|------|-------|--------|
| Downstream | 24 | Channel ID, Modulation, SNR, Power |
| Upstream | 4 | Channel ID, Modulation, Power |

## Notes

- DOCSIS 3.0 Wireless Gateway (combo modem/router)
- ISP: Telia (Finland)
- No frequency data exposed in status page
- No codeword counts exposed in status page
