***REMOVED*** ARRIS SB8200 Modem Fixtures


<!-- AUTO-GENERATED FROM metadata.yaml - DO NOT EDIT BELOW -->
***REMOVED******REMOVED*** Quick Facts

| Spec | Value |
|------|-------|
| **DOCSIS** | 3.1 |
| **Released** | 2017 |
| **Status** | Current |
| **ISPs** | Comcast, Cox, Spectrum |
| **Parser** | ✅ Verified |

<!-- END AUTO-GENERATED -->

***REMOVED******REMOVED*** Modem Information

| Property | Value |
|----------|-------|
| **Model** | SB8200 |
| **Manufacturer** | ARRIS |
| **Type** | Cable Modem (standalone, no router) |
| **DOCSIS Version** | 3.1 |
| **Release Year** | 2017 |
| **ISPs** | Comcast, Xfinity, Cox, Spectrum, and most major ISPs |
| **Max Speed** | 2 Gbps downstream (with LAG) |
| **Related Issue** | [***REMOVED***42](https://github.com/kwschulz/cable_modem_monitor/issues/42) |
| **Contributor** | @undotcom |
| **Capture Date** | November 2025 |
| **Parser Status** | Verified |

***REMOVED******REMOVED*** Known URLs

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

***REMOVED******REMOVED*** Authentication

**Type:** None required

The SB8200 status pages are publicly accessible without authentication. This is the simplest case for parser implementation.

***REMOVED******REMOVED*** Reboot Capability

**Status:** Present but ISP-locked (disabled button)

> **Community Action:** User @undotcom posted an [open letter to ARRIS](https://community.surfboard.com/sb8200-59/open-letter-to-arris-why-do-you-disable-basic-functionality-e-g-software-reboot-on-the-sb8200-5829) asking why software reboot is disabled. If you're affected by this limitation, consider adding your voice.

The SB8200 firmware includes reboot functionality in `cmconfiguration.html`:

```html
<form method="post" name="Configuration">
  <input type="hidden" name="Rebooting" value="">
  <input type="submit" value="Reboot" disabled onClick="resetReq();">
</form>
```

```javascript
function resetReq() {
  var agree = window.confirm('Are you sure you want to reset the modem?');
  if (agree == true) {
    window.document.configuration.Rebooting.value = 1;
  }
}
```

**Mechanism:** POST to `/cmconfiguration.html` with `Rebooting=1`

The button has `disabled` attribute in this capture (Spectrum ISP). This is a **client-side restriction only** - the server endpoint still exists. A direct POST request might work:

```python
session.post("http://192.168.100.1/cmconfiguration.html", data={"Rebooting": "1"})
```

**Testing needed:** The modem may accept the POST (UI-only restriction) or reject it (DOCSIS config blocks server-side). Worth testing on a real device.

***REMOVED******REMOVED*** Available Fixtures

***REMOVED******REMOVED******REMOVED*** cmconnectionstatus.html

- **Source:** Issue ***REMOVED***42 attachment (SB8200.Arris.Modem.files.zip)
- **Status Code:** 200 OK
- **Size:** 21 KB
- **Content:** Full connection status page with all channel data
- **Authentication:** None required (public page)

**Key Content:**
- ARRIS SB8200 branding and model identification
- Startup Procedure table (DS Lock, Connectivity, Boot, Config, Security)
- 32 downstream bonded channels in HTML table
- 3 upstream bonded channels in HTML table
- Current system time

***REMOVED******REMOVED******REMOVED*** cmswinfo.html

- **Source:** Issue ***REMOVED***42 Fallback capture by @undotcom
- **Status Code:** 200 OK
- **Size:** 4 KB
- **Content:** Product information page with system status
- **Authentication:** None required (public page)

**Key Content:**
- Hardware/Software version information
- Serial number and MAC address (redacted)
- DOCSIS specification version
- **System uptime** (format: "8 days 01h:16m:13s.00")

***REMOVED******REMOVED******REMOVED*** Extended Files

Reference files not used by parser but useful for documentation:

| File | Size | Content |
|------|------|---------|
| `extended/cmaddress.html` | 4 KB | MAC addresses, IP configuration |
| `extended/cmconfiguration.html` | 6 KB | DOCSIS config file details |
| `extended/cmstatushelp.html` | 5 KB | Help documentation |
| `extended/lagcfg.html` | 5 KB | Link aggregation (LAG) settings |
| `extended/main_arris.js` | 15 KB | **Menu structure, page URLs** |

***REMOVED******REMOVED*** Data Structure

***REMOVED******REMOVED******REMOVED*** Startup Procedure Table

| Field | Sample Value |
|-------|--------------|
| Acquire DS Channel | 435000000 Hz (Locked) |
| Connectivity State | OK (Operational) |
| Boot State | OK (Operational) |
| Configuration File | OK |
| Security | Enabled (BPI+) |
| DOCSIS Network Access | Allowed |

***REMOVED******REMOVED******REMOVED*** Downstream Channels Table (32 channels)

HTML table with columns:
| Column | Data | Format |
|--------|------|--------|
| Channel ID | Numeric ID | Plain integer |
| Lock Status | Status | "Locked" |
| Modulation | Type | "QAM256" or "Other" (OFDM) |
| Frequency | Hz | "435000000 Hz" |
| Power | dBmV | "6.2 dBmV" |
| SNR/MER | dB | "43.3 dB" |
| Corrected | Count | Plain integer |
| Uncorrectables | Count | Plain integer |

**Sample Channel Data:**
| Ch ID | Lock | Mod | Frequency | Power | SNR | Corr | Uncorr |
|-------|------|-----|-----------|-------|-----|------|--------|
| 19 | Locked | QAM256 | 435 MHz | 6.2 dBmV | 43.3 dB | 121 | 390 |
| 1 | Locked | QAM256 | 507 MHz | 6.4 dBmV | 43.1 dB | 88 | 390 |
| ... | ... | ... | ... | ... | ... | ... | ... |
| 33 | Locked | Other | 524 MHz | 6.8 dBmV | 41.8 dB | 3715091637 | 0 |

**Note:** Channel 33 with "Other" modulation is the OFDM channel (DOCSIS 3.1).

***REMOVED******REMOVED******REMOVED*** Upstream Channels Table (3 channels)

HTML table with columns:
| Column | Data | Format |
|--------|------|--------|
| Channel | Index | Plain integer |
| Channel ID | Numeric ID | Plain integer |
| Lock Status | Status | "Locked" |
| US Channel Type | Type | "SC-QAM Upstream" or "OFDM Upstream" |
| Frequency | Hz | "37000000 Hz" |
| Width | Hz | "6400000 Hz" |
| Power | dBmV | "41.0 dBmV" |

**Sample Upstream Data:**
| Ch | ID | Lock | Type | Frequency | Width | Power |
|----|-----|------|------|-----------|-------|-------|
| 1 | 4 | Locked | SC-QAM Upstream | 37.0 MHz | 6.4 MHz | 41.0 dBmV |
| 2 | 3 | Locked | SC-QAM Upstream | 30.6 MHz | 6.4 MHz | 41.0 dBmV |
| 3 | 1 | Locked | OFDM Upstream | 6.0 MHz | 17.2 MHz | 38.0 dBmV |

***REMOVED******REMOVED******REMOVED*** System Time

Format: `Tue Nov 25 19:24:13 2025`

Displayed at bottom of page as: `Current System Time: [timestamp]`

***REMOVED******REMOVED*** Parser Implementation Notes

***REMOVED******REMOVED******REMOVED*** Similarity to Existing Parsers

The SB8200 uses the **same HTML table format** as the SB6190. Key differences:

| Feature | SB8200 | SB6190 |
|---------|--------|--------|
| DOCSIS | 3.1 | 3.0 |
| OFDM Channels | Yes (DS + US) | No |
| DS Channels | 32 + 1 OFDM | 32 |
| US Channels | 2 SC-QAM + 1 OFDM | 4 |
| Table Format | Rows = channels | Rows = channels |
| Frequency Format | "XXX Hz" | "XXX MHz" |
| Auth Required | No | No |

***REMOVED******REMOVED******REMOVED*** Implementation Approach

**Option 1:** Extend SB6190 parser with OFDM support

```python
class ArrisSB8200Parser(ArrisSB6190Parser):
    name = "ARRIS SB8200"
    models = ["SB8200"]
    docsis_version = "3.1"

    @classmethod
    def can_parse(cls, soup, url, html):
        return bool(soup.find(string=lambda s: s and "SB8200" in s))
```

**Option 2:** Create standalone parser (minimal changes from SB6190)

***REMOVED******REMOVED******REMOVED*** Key Parsing Logic

Frequency parsing note: SB8200 uses "Hz" suffix while SB6190 uses "MHz":
```python
***REMOVED*** SB8200 format: "435000000 Hz"
freq_text = cells[3].text.strip()  ***REMOVED*** "435000000 Hz"
freq_hz = int(freq_text.replace(" Hz", ""))

***REMOVED*** SB6190 format: "435 MHz"
freq_mhz = float(freq_text.replace(" MHz", ""))
freq_hz = int(freq_mhz * 1_000_000)
```

***REMOVED******REMOVED******REMOVED*** Detection Logic

The SB8200 can be detected by:
```python
***REMOVED*** Look for model name in page
soup.find("span", id="thisModelNumberIs")  ***REMOVED*** Contains "SB8200"
***REMOVED*** OR
soup.find(string=lambda s: s and "SB8200" in s)
```

***REMOVED******REMOVED*** Comparison with Other ARRIS Modems

| Feature | SB6141 | SB6190 | SB8200 |
|---------|--------|--------|--------|
| DOCSIS | 3.0 | 3.0 | 3.1 |
| DS Channels | 8 | 32 | 32+OFDM |
| US Channels | 4 | 4 | 2+OFDM |
| Auth Required | No | No | No |
| Table Format | HTML rows | HTML rows | HTML rows |
| Freq Format | MHz | MHz | Hz |

***REMOVED******REMOVED*** Related Issues

- **Issue ***REMOVED***42:** ARRIS SB8200 support request
- SB6141 and SB6190 parsers exist as reference

***REMOVED******REMOVED*** Notes

- The SB8200 is a popular DOCSIS 3.1 modem widely deployed by major ISPs
- No authentication makes this one of the simplest modems to support
- OFDM channel support needed (marked as "Other" modulation in DS, "OFDM Upstream" in US)
- Frequency is in Hz (not MHz like older ARRIS modems)
- System time is available (unlike some Netgear modems)
