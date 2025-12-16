# ARRIS SB8200 Modem Fixtures


<!-- AUTO-GENERATED FROM metadata.yaml - DO NOT EDIT BELOW -->
## Quick Facts

| Spec | Value |
|------|-------|
| **DOCSIS** | 3.1 |
| **Released** | 2017 |
| **Status** | Current |
| **ISPs** | Comcast, Cox, Spectrum |
| **Parser** | ✅ Verified |

<!-- END AUTO-GENERATED -->

## Modem Information

| Property | Value |
|----------|-------|
| **Model** | SB8200 |
| **Manufacturer** | ARRIS |
| **Type** | Cable Modem (standalone, no router) |
| **DOCSIS Version** | 3.1 |
| **Release Year** | 2017 |
| **ISPs** | Comcast, Xfinity, Cox, Spectrum, and most major ISPs |
| **Max Speed** | 2 Gbps downstream (with LAG) |
| **Related Issue** | [#42](https://github.com/solentlabs/cable_modem_monitor/issues/42) |
| **Contributor** | @undotcom |
| **Capture Date** | November 2025 |
| **Parser Status** | Verified |

## Known URLs

Complete page inventory from `main_arris.js` menu structure:

| Page | URL | Status | Purpose |
|------|-----|--------|---------|
| STATUS | `/cmconnectionstatus.html` | ✅ Captured | Channel data, startup status |
| PRODUCT INFO | `/cmswinfo.html` | ✅ Captured | Uptime, versions, serial |
| EVENT LOG | `/cmeventlog.html` | ❌ Not captured | System event log |
| ADDRESSES | `/cmaddress.html` | ✅ Captured | MAC/IP addresses |
| CONFIGURATION | `/cmconfiguration.html` | ✅ Captured | DOCSIS config file info |
| ADVANCED | `/lagcfg.html` | ✅ Captured | Link aggregation settings |
| HELP | `/cmstatushelp.html` | ✅ Captured | Status page documentation |

**Base URL:** `http://192.168.100.1`

## Authentication

**Type:** None required

The SB8200 status pages are publicly accessible without authentication.

## Reboot Capability

**Status:** Disabled (blocked server-side by ISP/firmware)

### Historical Context

In 2015-2016, ARRIS SURFboard modems (particularly the SB6141) were found to have a critical security vulnerability: the admin interface at `192.168.100.1` required **no authentication**, allowing anyone on the local network unrestricted access. Worse, the interface was vulnerable to CSRF attacks—attackers could embed malicious image tags like `<img src="http://192.168.100.1/reset.htm">` in webpages to remotely trigger modem reboots or factory resets when users visited compromised sites.

With over 135 million affected modems worldwide, this created a significant attack surface. Rather than implementing proper authentication controls, ARRIS chose to disable reboot/reset functionality in firmware updates—a decision that persists in modern models like the SB8200.

**Source:** [The Hacker News - 135 Million Modems Open to Remote Factory Reset Attack](https://thehackernews.com/2016/04/hack-modem-internet.html)

> **Community Action:** User @undotcom posted an [open letter to ARRIS](https://community.surfboard.com/sb8200-59/open-letter-to-arris-why-do-you-disable-basic-functionality-e-g-software-reboot-on-the-sb8200-5829) asking why software reboot is disabled. If you're affected by this limitation, consider adding your voice.

### Technical Details

The SB8200 firmware includes a reboot button in `cmconfiguration.html` with a `disabled` attribute. Testing confirmed the restriction is enforced server-side—direct POST requests to `/cmconfiguration.html` with `Rebooting=1` are rejected by ISP firmware (Spectrum).

## Available Fixtures

### cmconnectionstatus.html

- **Source:** Issue #42 attachment (SB8200.Arris.Modem.files.zip)
- **Size:** 21 KB
- **Content:** Full connection status page with all channel data (32 DS + 3 US channels)

### cmswinfo.html

- **Source:** Issue #42 Fallback capture by @undotcom
- **Size:** 4 KB
- **Content:** Product information page (uptime, hardware/software versions)

### Extended Files

Reference files not used by parser but useful for documentation:

| File | Size | Content |
|------|------|---------|
| `extended/cmaddress.html` | 4 KB | MAC addresses, IP configuration |
| `extended/cmconfiguration.html` | 6 KB | DOCSIS config file details |
| `extended/cmstatushelp.html` | 5 KB | Help documentation |
| `extended/lagcfg.html` | 5 KB | Link aggregation (LAG) settings |
| `extended/main_arris.js` | 15 KB | Menu structure, page URLs |

## Related Issues

- **Issue #42:** ARRIS SB8200 support request (@undotcom)
