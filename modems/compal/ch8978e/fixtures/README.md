# Compal CH8978E (Pyür Germany)


<!-- AUTO-GENERATED FROM metadata.yaml - DO NOT EDIT BELOW -->
## Quick Facts

| Spec | Value |
|------|-------|
| **DOCSIS** | 3.1 |
| **Released** | 2023 |
| **Status** | Current |
| **ISPs** | Pyür |

<!-- END AUTO-GENERATED -->

## Status: 🚫 Unsupported (Blocked)

Hidden status pages are not directly accessible. Firmware uses PHP pages that only load embedded in `index.php`.

## Related Issue

[#79](https://github.com/solentlabs/cable_modem_monitor/issues/79) - User confirmed hidden URLs don't work (2026-01-08).

## Research Findings

**CH7485E/CH7467CE (older models)** - hidden ASP pages work:
- `https://192.168.100.1/RgConnect.asp` - signal levels
- `https://192.168.100.1/RgEventLog.asp` - event log
- Login: `admin/tc`

**CH8978E (this model)** - confirmed NOT working:
- No `.asp` pages exist
- Uses PHP pages that only load embedded in `index.php`
- Known pages: `RgWanStatus.php`, `RgConnect.php`, `MtaStatus.php`
- These return empty/broken when accessed directly

**Sources:**
- [pyforum.de/t=1345](https://www.pyforum.de/viewtopic.php?t=1345) - older model how-to
- [pyforum.de/t=1998](https://www.pyforum.de/viewtopic.php?t=1998) - CH7485E confirmation

## Chipset

Unknown. Older Compal model CH7465LG used Intel Puma ([source](https://deviwiki.com/wiki/Compal_Broadband_Networks_CH7465LG-LC)). CH8978E chipset not found in hardware databases.

## Possible Paths Forward

1. Reverse engineer how `index.php` loads embedded pages (session/auth requirement?)
2. Wait for firmware update that exposes data
3. Find alternative user with different firmware version
