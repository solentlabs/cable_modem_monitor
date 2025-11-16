# License Analysis and Code Comparison

## Executive Summary

This document provides:
1. **License compatibility analysis** for similar projects
2. **MB8600 vs MB8611 implementation comparison**
3. **SNMP viability assessment** for cable modem monitoring

**Bottom Line:**
- ✅ **andresp/cablemodem-status** (MIT) - Safe to use, excellent modem coverage
- ✅ **PyPNM** (MIT) - Safe to use for PNM features
- ❌ **emresaglam/netgear** (GPL-3.0) - Incompatible with our MIT license
- ❌ **Other projects** - No license found, avoid using
- 🚫 **SNMP approach** - Not recommended (ISPs lock it down)

---

## 1. License Compatibility Analysis

Our project is **MIT licensed**, which is a permissive license that allows:
- Using, copying, modifying, merging, publishing, distributing, sublicensing, and selling
- Combining with code under various licenses (with restrictions)

### License Compatibility Matrix

| Project | License | Compatible? | Notes |
|---------|---------|-------------|-------|
| **andresp/cablemodem-status** | MIT | ✅ YES | Fully compatible, can adapt code with attribution |
| **mgarcia01752/PyPNM** | MIT | ✅ YES | Fully compatible for PNM features |
| **emresaglam/netgear-cable-modem-status-scraper** | GPL-3.0 | ❌ NO | Copyleft license incompatible with MIT |
| **sarabveer/cable-modem-stats** | None found | ⚠️ AVOID | No license = all rights reserved |
| **andrewfraley/arris_cable_modem_stats** | None found | ⚠️ AVOID | No license = all rights reserved |
| **twstokes/arris-scrape** | Network error | ⚠️ VERIFY | Need to check directly on GitHub |

### GPL-3.0 Incompatibility Explanation

GPL-3.0 is a "copyleft" license that requires:
- Any derivative work must also be GPL-3.0 licensed
- All source code must be made available
- Cannot be combined with proprietary or more permissive licenses

Since our project is MIT licensed, we **cannot** incorporate GPL-3.0 code without changing our entire project license to GPL-3.0, which would affect all users and contributors.

### Unlicensed Projects Risk

Projects without explicit licenses default to "all rights reserved" under copyright law:
- No legal right to use, modify, or distribute the code
- Could result in copyright infringement claims
- Should contact authors for clarification before use

**Recommendation:** Only use **andresp/cablemodem-status** (MIT) and **PyPNM** (MIT) as code references.

---

## 2. MB8600 vs MB8611 Comparison

### Overview

Both are Motorola cable modems with similar capabilities:
- **MB8600**: DOCSIS 3.1, 32x8 channels, Gigabit capable
- **MB8611**: DOCSIS 3.1, 32x8 channels, 2.5 Gigabit capable (upgraded hardware)

The MB8611 is essentially an upgraded version of the MB8600 with better Ethernet port.

### Implementation Comparison

#### andresp/cablemodem-status MB8600 Implementation

**File:** `/tmp/cablemodem-status/src/docsismodem/modems/motorola_mb8600.py`

**Architecture:**
```python
class MotorolaMB8600(ObservableModem):
    - Extends abstract base class
    - Tightly coupled to InfluxDB for data storage
    - Single parsing approach (HTML scraping)
```

**Authentication:**
```python
def login(self):
    modemAuthentication = {
        'loginUsername': self.config['Modem']['Username'],
        'loginPassword': base64.b64encode(self.config['Modem']['Password'].encode('ascii'))
    }
    self.session.post(self.baseUrl + "/goform/login", data=modemAuthentication)
```

**Key Characteristics:**
- **URL:** `/MotoConnection.asp` (different from MB8611)
- **Parsing:** BeautifulSoup with CSS class selector `moto-table-content`
- **Tables:** Hardcoded table indices (tables[3] = downstream, tables[4] = upstream)
- **Data Output:** InfluxDB Points (tightly coupled)
- **OFDM Detection:** Checks for "OFDM PLC" modulation type
- **Password:** Base64 encoded before transmission

**Code Sample:**
```python
def collectStatus(self):
    sampleTime = datetime.utcnow().isoformat()
    response = self.session.get(self.baseUrl + "/MotoConnection.asp")

    statusPage = BeautifulSoup(response.content, features="lxml")
    tables = statusPage.find_all("table", { "class": "moto-table-content" })

    downstreamData = tables[3].find_all("tr")  # Hardcoded index
    upstreamData = tables[4].find_all("tr")    # Hardcoded index
```

---

#### Our MB8611 Implementation

**Files:**
- `custom_components/cable_modem_monitor/parsers/motorola/mb8611_hnap.py`
- `custom_components/cable_modem_monitor/parsers/motorola/mb8611_static.py`

**Architecture:**
```python
class MotorolaMB8611HnapParser(ModemParser):
    - Dual approach: HNAP API (priority 101) + Static HTML fallback (priority 100)
    - Decoupled from storage layer
    - Returns generic dict format for flexibility
```

**Authentication:**
```python
auth_config = HNAPAuthConfig(
    strategy=AuthStrategyType.HNAP_SESSION,
    login_url="/Login.html",
    hnap_endpoint="/HNAP1/",
    soap_action_namespace="http://purenetworks.com/HNAP1/",
)
```

**Key Characteristics:**

**HNAP Parser (Priority):**
- **Protocol:** HNAP/SOAP API (GetMultipleHNAPs batching)
- **Format:** JSON responses with delimited data (`^` and `|+|`)
- **URL:** `/HNAP1/` endpoint
- **Authentication:** HNAP session-based with AuthFactory
- **Advantages:** More reliable, structured API, less fragile than HTML parsing

**Static HTML Parser (Fallback):**
- **URL:** `/MotoStatusConnection.html` (different from MB8600)
- **Parsing:** BeautifulSoup with element IDs (e.g., `MotoConnDownstreamChannel`)
- **Tables:** ID-based lookup (more stable than index-based)
- **Password:** Not required (unauthenticated HTML access)

**Code Sample (HNAP):**
```python
def parse(self, soup, session, base_url):
    soap_actions = [
        "GetMotoStatusStartupSequence",
        "GetMotoStatusConnectionInfo",
        "GetMotoStatusDownstreamChannelInfo",
        "GetMotoStatusUpstreamChannelInfo",
        "GetMotoLagStatus",
    ]
    json_response = builder.call_multiple(session, base_url, soap_actions)
    # Parse delimited data: "1^Locked^QAM256^20^543.0^ 1.4^45.1^41^0^"
```

**Code Sample (Static):**
```python
def _parse_downstream_from_html(self, soup):
    downstream_table = soup.find("table", id="MotoConnDownstreamChannel")  # ID-based
    for row in rows[1:]:
        cells = row.find_all("td")
        channels.append({
            "channel_id": int(cells[0].text.strip()),
            "frequency": int(round(float(cells[4].text.strip()) * 1_000_000)),
            # ... standardized field names
        })
```

---

### Key Differences

| Aspect | MB8600 (andresp) | MB8611 (ours) |
|--------|------------------|---------------|
| **Parsing Strategy** | Single HTML scraping | Dual: HNAP API + HTML fallback |
| **URL** | `/MotoConnection.asp` | `/MotoStatusConnection.html` or `/HNAP1/` |
| **Table Lookup** | Hardcoded indices (`tables[3]`, `tables[4]`) | Element IDs (`MotoConnDownstreamChannel`) |
| **Data Format** | InfluxDB Points (coupled) | Generic dict (decoupled) |
| **Authentication** | Base64 password to `/goform/login` | HNAP session or none (static) |
| **HNAP Support** | No | Yes (primary method) |
| **Error Handling** | Minimal | Try/except with logging |
| **Frequency Units** | String (MHz) stored in tags | Integer (Hz) for consistency |
| **Modulation Detection** | "OFDM PLC" string check | Generic modulation field |

---

### Why MB8600 and MB8611 URLs Differ

The different URLs suggest firmware variations:
- **MB8600** uses older `.asp` (Active Server Pages) interface
- **MB8611** uses `.html` static pages + HNAP API

However, Motorola modems often support multiple URLs for backward compatibility. The MB8611 might also support `/MotoConnection.asp` with proper authentication.

---

### Leveraging MB8600 Code for MB8611

**What we can learn:**
1. **Base64 password encoding** - MB8600 shows this is required for form-based auth
2. **Alternative URL** - `/MotoConnection.asp` might work on MB8611 as fallback
3. **Table structure similarity** - Same column order in HTML tables
4. **OFDM vs QAM detection** - Checking modulation field to differentiate channel types

**What we already do better:**
1. ✅ HNAP API support (more reliable than HTML scraping)
2. ✅ ID-based element lookup (more stable than index-based)
3. ✅ Decoupled architecture (works with any storage backend)
4. ✅ Standardized field names and units
5. ✅ Comprehensive error handling

**Potential improvements from MB8600:**
- Could test `/MotoConnection.asp` as tertiary fallback
- Could add CSS class-based parsing as another fallback method
- Could implement separate measurements for OFDM vs QAM channels

---

## 3. Adding MB8600 Parser Support

Since the MB8600 and MB8611 are very similar, we could:

### Option A: Extend MB8611 Static Parser

Add MB8600 as a supported model with URL override:

```python
class MotorolaMB8611StaticParser(ModemParser):
    name = "Motorola MB8611/MB8600 (Static)"
    models = ["MB8611", "MB8612", "MB8600"]  # Add MB8600

    url_patterns = [
        {"path": "/MotoStatusConnection.html", "auth_method": "none", "auth_required": False},
        {"path": "/MotoConnection.asp", "auth_method": "form", "auth_required": True},  # MB8600
    ]
```

### Option B: Create Dedicated MB8600 Parser

Reference the andresp implementation but adapt to our architecture:

```python
class MotorolaMB8600Parser(ModemParser):
    """Parser for Motorola MB8600 using /MotoConnection.asp"""
    # Based on andresp/cablemodem-status implementation (MIT licensed)
    # https://github.com/andresp/cablemodem-status
```

**Recommendation:** Option A is simpler if the HTML table structure is identical. Option B provides more flexibility if there are significant differences.

---

## 4. Other Modems from andresp/cablemodem-status (MIT)

Since this project is MIT licensed, we can reference these implementations:

| Modem | File | Notes |
|-------|------|-------|
| **Motorola MB8600** | `motorola_mb8600.py` | ✅ Reviewed above |
| **Hitron Coda56** | `hitron_coda56.py` | European/Canadian market |
| **Netgear CM2000** | `netgear_cm2000.py` | Popular US market modem |
| **Technicolor XB7** | `technicolor_xb7.py` | ISP-provided gateway (Comcast) |
| **Arris TG3492** | `touchstone_tg3492_upc_ch.py` | Swiss market (UPC.CH) |

**Action Items:**
1. Read each parser file from `/tmp/cablemodem-status/src/docsismodem/modems/`
2. Document the parsing approach for each
3. Create parsers for high-demand models (CM2000, XB7)
4. Add proper MIT license attribution in code comments

---

## 5. SNMP Viability Assessment

### Question: Should we pursue SNMP-based monitoring?

**Answer: No, not recommended for consumer cable modem monitoring.**

---

### Background: SNMP in DOCSIS

**SNMP (Simple Network Management Protocol)** is theoretically supported:
- DOCSIS standard mandates SNMP support via RFC 2669 and RFC 4639
- Cable Device MIB (DOCS-CABLE-DEVICE-MIB) defines standard objects
- CMTSs (Cable Modem Termination Systems) use SNMP to manage modems

**Standard MIBs include:**
- IF-MIB (interface statistics)
- DOCS-CABLE-DEVICE-MIB (DOCSIS-specific objects)
- DOCS-IF-MIB (channel information)

---

### Reality: Residential Modem Restrictions

**ISPs lock down SNMP access:**

From Tom's Hardware Forum:
> "The Arris SB8200 either has SNMP locked out by Comcast or doesn't support SNMP."

From SNBForums:
> "The Motorola/Arris SB6183 may expose SNMP to CPE, but users report getting no response from SNMP queries."

From docsis.org:
> "All SNMP access settings [for Arris modems] are made in the modem configuration file."

**Key Issues:**
1. **ISP Configuration Files:** SNMP settings are controlled by DOCSIS config files provisioned by ISPs
2. **Access Control Tables:** `docsDevNmAccessTable` restricts which IPs can query SNMP
3. **Community Strings:** Often set to non-default values or disabled entirely
4. **Vendor Restrictions:** Manufacturers lock down SNMP on consumer models at ISP request

---

### SNMP vs Web Scraping Comparison

| Aspect | SNMP | Web Scraping |
|--------|------|--------------|
| **Standardization** | ✅ RFC-defined MIBs | ❌ Vendor-specific HTML |
| **Data Structure** | ✅ Structured OIDs | ❌ Unstructured HTML |
| **Stability** | ✅ Stable across firmware | ❌ Changes with UI updates |
| **Residential Access** | ❌ Locked by ISPs | ✅ Web UI accessible |
| **Authentication** | ❌ Requires community strings | ✅ Simple or no auth |
| **Implementation** | ❌ Complex (pysnmp, MIBs) | ✅ Simple (requests, BeautifulSoup) |
| **Reliability** | ❌ Depends on ISP config | ✅ Always available |
| **Performance** | ✅ Efficient binary protocol | ⚠️ HTTP overhead |

---

### Real-World Testing

**What we found:**
- 0 of the 6+ similar projects we reviewed use SNMP
- All use web scraping (HTML or HNAP/SOAP APIs)
- No recent discussions (2024-2025) mention successful SNMP access on residential modems

**Projects we reviewed:**
- twstokes/arris-scrape: Web scraping (XPath)
- sarabveer/cable-modem-stats: Web scraping
- andrewfraley/arris_cable_modem_stats: Web scraping
- andresp/cablemodem-status: Web scraping
- emresaglam/netgear: Web scraping (JavaScript rendering)

**Why they don't use SNMP:**
If SNMP worked reliably on consumer modems, these developers would have used it instead of dealing with fragile HTML parsing.

---

### PyPNM and pyDocsisMon

**PyPNM** (MIT licensed):
- Python toolkit for DOCSIS 3.0/3.1/4.0 Proactive Network Maintenance
- Focuses on PNM telemetry analysis (advanced diagnostics)
- **Does NOT provide residential modem SNMP access**
- Useful for analyzing PNM data IF you can get it (typically from ISP/CMTS side)

**pyDocsisMon**:
- Repository not found (404 error)
- Even if found, likely faces same SNMP access restrictions

---

### When SNMP Might Work

SNMP access could be viable in these scenarios:
1. **Business-class modems:** Some commercial DOCSIS modems allow SNMP
2. **Custom ISP configs:** Small/local ISPs that don't lock down modems
3. **Modified firmware:** Some users flash custom firmware (voids warranty, risky)
4. **CMTS-side monitoring:** Network operators monitoring from headend

For a **residential consumer tool** like cable_modem_monitor, SNMP is **not practical**.

---

### Recommendation: Stick with Web Scraping

**Reasons:**
1. ✅ **Universal access** - All modems have web interfaces
2. ✅ **No ISP dependency** - Works regardless of provisioning
3. ✅ **Proven approach** - All similar projects use this method
4. ✅ **Simple implementation** - Python + requests + BeautifulSoup
5. ✅ **Already working** - We have successful parsers for MB8611, SB6190

**Avoid SNMP because:**
1. ❌ Locked down by ISPs on residential modems
2. ❌ Requires ISP config file changes (not user-accessible)
3. ❌ Complex implementation with limited benefit
4. ❌ Zero evidence of successful residential use
5. ❌ Not worth development effort for marginal cases

---

## 6. Recommendations

### Immediate Actions

1. **Use andresp/cablemodem-status as reference** (MIT licensed)
   - Add MB8600 parser support
   - Add Netgear CM2000 parser
   - Add Hitron Coda56 parser (if requested by users)
   - Add proper attribution comments in code

2. **Add license attribution**
   ```python
   """
   Parser for Motorola MB8600 cable modem.

   Based on andresp/cablemodem-status implementation (MIT licensed):
   https://github.com/andresp/cablemodem-status
   Copyright (c) [year] [author]
   """
   ```

3. **Test MB8611 with `/MotoConnection.asp` URL**
   - May work as additional fallback
   - Could benefit MB8611 users with older firmware

4. **Do NOT pursue SNMP**
   - Not practical for residential modems
   - Focus on web scraping approaches

### Future Considerations

1. **Consider PyPNM for advanced features** (MIT licensed)
   - If we ever get PNM data access
   - Could add advanced diagnostics
   - Low priority (niche use case)

2. **Monitor for license changes**
   - Check if andrewfraley/arris_cable_modem_stats adds license
   - Check if sarabveer/cable-modem-stats adds license
   - Could leverage more implementations if they become available

3. **Document unsupported projects**
   - Update README noting GPL projects can't be used
   - Explain why (license incompatibility)

---

## 7. Code Reuse Template

When adapting code from andresp/cablemodem-status:

```python
"""
Parser for [Modem Model] cable modem.

Implementation adapted from andresp/cablemodem-status (MIT licensed):
https://github.com/andresp/cablemodem-status/blob/master/src/docsismodem/modems/[file].py

Original Copyright (c) andresp
Used under MIT License - see THIRD_PARTY_LICENSES.md

Modifications:
- Adapted to ModemParser architecture
- Decoupled from InfluxDB
- Added Home Assistant integration
- Standardized field names and units
"""

from __future__ import annotations
import logging
from bs4 import BeautifulSoup
from ..base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)


class [ModemName]Parser(ModemParser):
    """Parser for [Modem Model] from static HTML."""

    name = "[Manufacturer] [Model]"
    manufacturer = "[Manufacturer]"
    models = ["[Model1]", "[Model2]"]
    priority = 100

    # Implementation here...
```

Create `THIRD_PARTY_LICENSES.md`:
```markdown
# Third-Party Licenses

## andresp/cablemodem-status

Portions of parser implementations are adapted from:
https://github.com/andresp/cablemodem-status

MIT License

Copyright (c) andresp

[Include full MIT license text]
```

---

## Summary

✅ **Safe to use:**
- andresp/cablemodem-status (MIT) - Use for MB8600, CM2000, Hitron, XB7, TG3492
- PyPNM (MIT) - Use for future PNM features

❌ **Cannot use:**
- emresaglam/netgear (GPL-3.0) - License incompatible
- sarabveer/cable-modem-stats - No license
- andrewfraley/arris_cable_modem_stats - No license

🚫 **Not recommended:**
- SNMP approach - ISPs lock it down, not practical for residential modems

📊 **MB8600 vs MB8611:**
- Very similar hardware (MB8611 is upgraded MB8600)
- Different URLs but likely compatible table structures
- Our MB8611 implementation is more robust (HNAP + HTML fallback)
- Can easily adapt to support MB8600

---

*Analysis completed: 2025-11-12*
*Analyst: Claude (Anthropic)*
*Purpose: License compliance and technical feasibility assessment*
