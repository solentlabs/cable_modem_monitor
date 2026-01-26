# Modem Fixture Library

Auto-generated index of modem fixtures.

**Data Sources:**
- `modem.yaml` - Single source of truth (manufacturer, model, hardware, ISPs, status)

**Supported Modems:** 19 (13 ✅ verified, 5 ⏳ awaiting, 1 🔧 in progress)

## Directory Structure

Each modem has a self-contained directory:

```
modems/
└── {manufacturer}/
    └── {model}/
        ├── modem.yaml           # REQUIRED: Configuration and auth hints
        ├── fixtures/            # OPTIONAL: Extracted HTML/JSON responses
        │   └── {page_name}.html
        └── har/                 # OPTIONAL: Sanitized HAR captures
            └── modem.har        # Primary capture
```

See [docs/specs/MODEM_DIRECTORY_SPEC.md](../docs/specs/MODEM_DIRECTORY_SPEC.md) for full specification.

## Supported Modems

| Manufacturer | Model | DOCSIS | Protocol | Chipset | ISPs | Files | Status |
|--------------|-------|--------|----------|---------|------|-------|--------|
| ARRIS | [CM820B](arris/cm820b/README.md) | 3.0 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [Puma 5](#puma-5) | [![VOLY](https://img.shields.io/badge/-VOLY-5599aa?style=flat-square "Volia")](#volya) | 0 | ✅ Verified |
| Arris/CommScope | [G54](arris/g54/README.md) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3390](#bcm3390) | [![XFI](https://img.shields.io/badge/-XFI-aa7788?style=flat-square "Xfinity")](#xfinity) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) | 1 | ⏳ Awaiting |
| Arris/CommScope | [S33](arris/s33/README.md) | 3.1 | ![HNAP](https://img.shields.io/badge/-HNAP-5B8FBF?style=flat-square "SOAP-based, requires auth") | [BCM3390](#bcm3390) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) | 2 | ✅ Verified |
| Arris/CommScope | [S34](arris/s34/README.md) | 3.1 | ![HNAP](https://img.shields.io/badge/-HNAP-5B8FBF?style=flat-square "SOAP-based, requires auth") | [BCM3390](#bcm3390) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) | 6 | ✅ Verified |
| ARRIS | [SB6141](arris/sb6141/README.md) | 3.0 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3380](#bcm3380) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) [![TWC](https://img.shields.io/badge/-TWC-7799aa?style=flat-square "Time Warner Cable")](#twc) [![MED](https://img.shields.io/badge/-MED-557799?style=flat-square "Mediacom")](#mediacom) | 1 | ✅ Verified |
| ARRIS | [SB6190](arris/sb6190/README.md) | 3.0 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [Puma 6](#puma-6) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) [![TWC](https://img.shields.io/badge/-TWC-7799aa?style=flat-square "Time Warner Cable")](#twc) | 1 | ⏳ Awaiting |
| ARRIS | [SB8200](arris/sb8200/README.md) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3390](#bcm3390) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) | 3 | ⏳ Awaiting |
| Motorola | [MB7621](motorola/mb7621/README.md) | 3.0 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3384](#bcm3384) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) [![TWC](https://img.shields.io/badge/-TWC-7799aa?style=flat-square "Time Warner Cable")](#twc) [![RCN](https://img.shields.io/badge/-RCN-556688?style=flat-square "RCN Corporation")](#rcn) [![C1](https://img.shields.io/badge/-C1-7788aa?style=flat-square "Cable One")](#cableone) | 6 | ✅ Verified |
| Motorola | [MB8600](motorola/mb8600/README.md) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3390](#bcm3390) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![C1](https://img.shields.io/badge/-C1-7788aa?style=flat-square "Cable One")](#cableone) | 1 | 🔧 In Progress |
| Motorola | [MB8611](motorola/mb8611/README.md) | 3.1 | ![HNAP](https://img.shields.io/badge/-HNAP-5B8FBF?style=flat-square "SOAP-based, requires auth") | [BCM3390](#bcm3390) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) | 6 | ✅ Verified |
| Netgear | [C3700](netgear/c3700/README.md) | 3.0 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3383](#bcm3383) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) | 6 | ✅ Verified |
| Netgear | [C7000v2](netgear/c7000v2/README.md) | 3.0 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3384](#bcm3384) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) | 4 | ⏳ Awaiting |
| Netgear | [CM1200](netgear/cm1200/README.md) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3390](#bcm3390) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) | 1 | ✅ Verified |
| Netgear | [CM2000](netgear/cm2000/README.md) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3390](#bcm3390) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) | 7 | ✅ Verified |
| Netgear | [CM600](netgear/cm600/README.md) | 3.0 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3384](#bcm3384) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) [![TWC](https://img.shields.io/badge/-TWC-7799aa?style=flat-square "Time Warner Cable")](#twc) | 5 | ✅ Verified |
| Technicolor | [CGA2121](technicolor/cga2121/README.md) | 3.0 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3384](#bcm3384) | [![TEL](https://img.shields.io/badge/-TEL-9966aa?style=flat-square "Telia")](#telia) | 2 | ✅ Verified |
| Technicolor | [TC4400](technicolor/tc4400/README.md) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3390](#bcm3390) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) [![ROG](https://img.shields.io/badge/-ROG-aa6666?style=flat-square "Rogers Communications")](#rogers) [![SHAW](https://img.shields.io/badge/-SHAW-668899?style=flat-square "Shaw Communications")](#shaw) [![VID](https://img.shields.io/badge/-VID-779988?style=flat-square "Vidéotron")](#videotron) [![VDF](https://img.shields.io/badge/-VDF-aa6666?style=flat-square "Vodafone Kabel")](#vodafone) [![UM](https://img.shields.io/badge/-UM-778899?style=flat-square "Unitymedia")](#unitymedia) | 3 | ✅ Verified |
| Technicolor | [XB7](technicolor/xb7/README.md) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3390](#bcm3390) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![ROG](https://img.shields.io/badge/-ROG-aa6666?style=flat-square "Rogers Communications")](#rogers) | 1 | ✅ Verified |
| Virgin Media | [Hub 5](virgin/superhub5/README.md) | 3.1 | ![REST](https://img.shields.io/badge/-REST-5B9A5B?style=flat-square "JSON REST API") | [BCM3390](#bcm3390) | [![VM](https://img.shields.io/badge/-VM-aa4466?style=flat-square "Virgin Media")](#virgin) | 5 | ⏳ Awaiting |

## Unsupported Modems

Modems we're aware of but cannot currently support (ISP lockdown, missing data, etc.).

| Manufacturer | Model | DOCSIS | ISP | Notes |
|--------------|-------|--------|-----|-------|
| Compal | [CH8978E](compal/ch8978e/README.md) | 3.1 | [![PYÜR](https://img.shields.io/badge/-PY%C3%9CR-aa6699?style=flat-square "Pyür")](#pyür) | 🚫 Unsupported |

## Model Timeline

```
DOCSIS 3.0
├── 2011  ARRIS       CM820B     ░███████████████████  14yr  Current
├── 2011  ARRIS       SB6141     ░███████████░░░░░░░░   8yr  EOL 2019
├── 2014  Netgear     C3700      ░░░░░███████████░░░░   8yr  EOL 2022
├── 2015  Technicolor CGA2121    ░░░░░░██████████████  10yr  Current
├── 2016  Netgear     C7000v2    ░░░░░░░░████████████   9yr  Current
├── 2016  Netgear     CM600      ░░░░░░░░█████████░░░   7yr  EOL 2023
├── 2016  ARRIS       SB6190     ░░░░░░░░█████████░░░   7yr  EOL 2023
└── 2017  Motorola    MB7621     ░░░░░░░░░███████████   8yr  Current

DOCSIS 3.1
├── 2017  Motorola    MB8600     ░░░░░░░░░███████████   8yr  Current
├── 2017  ARRIS       SB8200     ░░░░░░░░░███████████   8yr  Current
├── 2017  Technicolor TC4400     ░░░░░░░░░███████████   8yr  Current
├── 2019  Netgear     CM1200     ░░░░░░░░░░░░████████   6yr  Current
├── 2020  Netgear     CM2000     ░░░░░░░░░░░░░███████   5yr  Current
├── 2020  Motorola    MB8611     ░░░░░░░░░░░░░███████   5yr  Current
├── 2020  Arris/CommS S33        ░░░░░░░░░░░░░███████   5yr  Current
├── 2020  Technicolor XB7        ░░░░░░░░░░░░░███████   5yr  Current
├── 2021  Virgin      Hub 5      ░░░░░░░░░░░░░░██████   4yr  Current
├── 2023  Compal      CH8978E    ░░░░░░░░░░░░░░░░░███   2yr  Current
├── 2023  Arris/CommS G54        ░░░░░░░░░░░░░░░░░███   2yr  Current
└── 2024  Arris/CommS S34        ░░░░░░░░░░░░░░░░░░██   1yr  Current

```

_Timeline: █ = years actively supported, ░ = discontinued or not yet released_
_Scale: 2010-2025 (15 years)_

## Legend

- **Files**: Number of fixture files (excludes README.md, metadata.yaml)
- **Status**: ✅ Verified | 🔧 In Progress | ⏳ Awaiting Verification | 🚫 Unsupported
- **Protocol**: ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square) = web scraping | ![LuCI](https://img.shields.io/badge/-LuCI-00B5E2?style=flat-square) = [OpenWrt](https://openwrt.org/docs/guide-user/luci/start) web interface | ![REST](https://img.shields.io/badge/-REST-5B9A5B?style=flat-square) = JSON REST API | [![HNAP](https://img.shields.io/badge/-HNAP-5B8FBF?style=flat-square)](https://en.wikipedia.org/wiki/Home_Network_Administration_Protocol) = [SOAP](https://www.w3.org/TR/soap/)-based, requires auth
- **📦**: GPL source code available (firmware uses open source components)

## Chipset Reference

| Chipset | Manufacturer | DOCSIS | Notes |
|---------|--------------|--------|-------|
| <span id="bcm3390"></span>[BCM3390](https://www.prnewswire.com/news-releases/broadcom-unleashes-gigabit-speeds-for-consumer-cable-modems-300016203.html) | Broadcom | 3.1 | Current flagship. 2x2 OFDM, 32x8 SC-QAM. Speeds exceeding 1 Gbps. |
| <span id="bcm3384"></span>[BCM3384](https://www.prnewswire.com/news-releases/broadcom-launches-gigabit-docsis-cable-gateway-family-186004842.html) | Broadcom | 3.0 | Reliable mid-tier. 16x4 or 24x8 channels. |
| <span id="bcm3383"></span>[BCM3383](https://www.prnewswire.com/news-releases/broadcom-launches-gigabit-docsis-cable-gateway-family-186004842.html) | Broadcom | 3.0 | Entry-level 8x4 chipset with integrated WiFi SoC. |
| <span id="bcm3380"></span>[BCM3380](https://www.webwire.com/ViewPressRel.asp?aId=92729) | Broadcom | 3.0 | Legacy 8x4 chipset. First single-chip DOCSIS 3.0 solution (2009). |
| <span id="puma-5"></span>[Puma 5](https://boxmatrix.info/wiki/Property:Puma5) | Intel | 3.0 | Legacy 8x4 chipset (TI TNETC4800). [Latency issues](https://www.theregister.com/2017/08/09/intel_puma_modem_woes/) less severe than Puma 6. |
| <span id="puma-6"></span>[Puma 6](https://boxmatrix.info/wiki/Property:Puma6) | Intel | 3.0 | ⚠️ **Avoid.** [Hardware flaw](https://www.theregister.com/2017/04/11/intel_puma_6_arris/) causes latency spikes up to 250ms under load. No fix available. |
| <span id="puma-7"></span>[Puma 7](https://boxmatrix.info/wiki/Property:Puma7) | Intel | 3.1 | ⚠️ **Avoid.** [Same architectural issues](https://www.theregister.com/2018/08/14/intel_puma_modem/) as Puma 6. Major vendors switched to Broadcom. |

## Provider Reference

| Code | Provider | Region | Approved Modems | Notes |
|------|----------|--------|-----------------|-------|
| <span id="comcast"></span>COM | Comcast Xfinity | US (nationwide) | [Official list](https://www.xfinity.com/support/articles/list-of-approved-cable-modems) | Online activation required |
| <span id="cox"></span>COX | Cox Communications | US (18 states) | [Official list](https://www.cox.com/residential/internet/learn/using-cox-compatible-modems.html) |  |
| <span id="spectrum"></span>SPEC | Spectrum (Charter) | US (41 states) | [Official list](https://www.spectrum.net/support/internet/compliant-modems-spectrum-network) | Formerly TWC, Bright House |
| <span id="twc"></span>TWC | Time Warner Cable | — | — | Merged into Spectrum (2016) |
| <span id="mediacom"></span>MED | Mediacom | US (Midwest/South) | [Official list](https://mediacomcable.com/compatible-retail-modems/) |  |
| <span id="rcn"></span>RCN | Astound (formerly RCN) | US (Northeast) | [Official list](https://www.astound.com/support/internet/bring-your-own-modem/) | No official list; DOCSIS 3.1 recommended |
| <span id="cableone"></span>C1 | Sparklight (Cable One) | US (21 states) | [Official list](https://support.sparklight.com/hc/en-us/articles/115009158227-Supported-Modems-Residential-Only) | DOCSIS 3.1 required |
| <span id="rogers"></span>ROG | Rogers | Canada | [Official list](https://www.rogers.com/) | No BYOM; Rogers equipment required |
| <span id="shaw"></span>SHAW | Shaw Communications | Canada (Western) | [Official list](https://www.shaw.ca/) | Merged with Rogers (2023) |
| <span id="videotron"></span>VID | Vidéotron | Canada (Quebec) | [Official list](https://www.videotron.com/) | Helix service requires leased equipment |
| <span id="volia"></span>VOLY | Volia | Ukraine | [Official list](https://en.wikipedia.org/wiki/Volia_(ISP)) | Acquired by Datagroup (2021) |
| <span id="pyür"></span>PYÜR | Pyür | Germany | [Official list](https://www.pyur.com/) | Formerly Tele Columbus |
| <span id="vodafone"></span>VDF | Vodafone Kabel | Germany | [Official list](https://www.vodafone.de/) | BYOM allowed since 2016; absorbed Unitymedia |
| <span id="unitymedia"></span>UM | Unitymedia | Germany (West) | — | Merged into Vodafone (2019) |
| <span id="virgin"></span>VM | Virgin Media | UK | [Official list](https://www.virginmedia.com/) | No BYOM; modem mode available |
| <span id="telia"></span>TEL | Telia | Nordic/Baltic | [Official list](https://www.teliacompany.com/) | Sweden, Finland, Norway, Baltics |

---
*Generated by `scripts/generate_fixture_index.py`*
