# Modem Fixture Library

Auto-generated index of modem fixtures.

**Data Sources:**
- `metadata.yaml` - Release dates, EOL, DOCSIS version, protocol, chipset, ISPs
- Parser classes - Verified status, manufacturer
- `README.md` - Model name, contributor notes

**Total Modems:** 15 (10 ✅ verified, 4 ⏳ awaiting, 1 🔧 in progress)

## Fixture Organization Guidelines

All fixture directories should follow this structure:

```
{model}/
├── metadata.yaml            # Modem specs (can be backfilled)
├── README.md                # Human-friendly notes
├── DocsisStatus.htm         # Channel data (required)
├── RouterStatus.htm         # System info
├── index.htm                # Detection/navigation
└── extended/                # Reference files (optional)
```

## Supported Modems

| Manufacturer | Model | DOCSIS | Protocol | Chipset | ISPs | Files | Status |
|--------------|-------|--------|----------|---------|------|-------|--------|
| ARRIS | [CM820B](arris/fixtures/cm820b/README.md) | 3.0 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [Puma 5](#puma-5) | [![VOLY](https://img.shields.io/badge/-VOLY-5599aa?style=flat-square "Volia")](#volya) | 2 | ✅ Verified |
| Arris/CommScope | [S33](arris/fixtures/s33/README.md) | 3.1 | **HNAP** | [BCM3390](#bcm3390) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) | 2 | ⏳ Awaiting |
| ARRIS | [SB6141](arris/fixtures/sb6141/README.md) | 3.0 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3380](#bcm3380) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) [![TWC](https://img.shields.io/badge/-TWC-7799aa?style=flat-square "Time Warner Cable")](#twc) [![MED](https://img.shields.io/badge/-MED-557799?style=flat-square "Mediacom")](#mediacom) | 1 | ✅ Verified |
| ARRIS | [SB6190](arris/fixtures/sb6190/README.md) | 3.0 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [Puma 6](#puma-6) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) [![TWC](https://img.shields.io/badge/-TWC-7799aa?style=flat-square "Time Warner Cable")](#twc) | 1 | ✅ Verified |
| ARRIS | [SB8200](arris/fixtures/sb8200/README.md) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3390](#bcm3390) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) | 3 | ✅ Verified |
| Motorola | [MB7621](motorola/fixtures/mb7621/README.md) | 3.0 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3384](#bcm3384) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) [![TWC](https://img.shields.io/badge/-TWC-7799aa?style=flat-square "Time Warner Cable")](#twc) [![RCN](https://img.shields.io/badge/-RCN-556688?style=flat-square "RCN Corporation")](#rcn) [![C1](https://img.shields.io/badge/-C1-7788aa?style=flat-square "Cable One")](#cableone) | 5 | ✅ Verified |
| Motorola | [MB8600](motorola/fixtures/mb8600/README.md) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3390](#bcm3390) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![C1](https://img.shields.io/badge/-C1-7788aa?style=flat-square "Cable One")](#cableone) | 1 | 🔧 In Progress |
| Motorola | [MB8611](motorola/fixtures/mb8611/README.md) | 3.1 | **HNAP** | [BCM3390](#bcm3390) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) | 6 | ✅ Verified |
| Netgear | [C3700-100NAS](netgear/fixtures/c3700/README.md) | 3.0 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3383](#bcm3383) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) | 6 | ✅ Verified |
| Netgear | [C7000v2](netgear/fixtures/c7000v2/README.md) | 3.0 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3384](#bcm3384) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) | 3 | ⏳ Awaiting |
| Netgear | [CM1200](netgear/fixtures/cm1200/README.md) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3390](#bcm3390) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) | 1 | ⏳ Awaiting |
| Netgear | [CM2000 (Nighthawk)](netgear/fixtures/cm2000/README.md) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3390](#bcm3390) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) | 7 | ⏳ Awaiting |
| Netgear | [CM600 (CM600-100NAS)](netgear/fixtures/cm600/README.md) | 3.0 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3384](#bcm3384) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) [![TWC](https://img.shields.io/badge/-TWC-7799aa?style=flat-square "Time Warner Cable")](#twc) | 5 | ✅ Verified |
| Technicolor | [TC4400](technicolor/fixtures/tc4400/README.md) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3390](#bcm3390) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) [![ROG](https://img.shields.io/badge/-ROG-aa6666?style=flat-square "Rogers Communications")](#rogers) [![SHAW](https://img.shields.io/badge/-SHAW-668899?style=flat-square "Shaw Communications")](#shaw) [![VID](https://img.shields.io/badge/-VID-779988?style=flat-square "Vidéotron")](#videotron) | 3 | ✅ Verified |
| Technicolor | [XB7 / CGM4331COM](technicolor/fixtures/xb7/README.md) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3390](#bcm3390) | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) | 1 | ✅ Verified |

## Model Timeline

```
DOCSIS 3.0
├── 2011  ARRIS       CM820B     ░███████████████████  14yr  Current
├── 2011  ARRIS       SB6141     ░███████████░░░░░░░░   8yr  EOL 2019
├── 2014  Netgear     C3700-100N ░░░░░███████████░░░░   8yr  EOL 2022
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
└── 2020  Technicolor XB7        ░░░░░░░░░░░░░███████   5yr  Current

```

_Timeline: █ = years actively supported, ░ = discontinued or not yet released_
_Scale: 2010-2025 (15 years)_

## Legend

- **Files**: Number of fixture files (excludes README.md, metadata.yaml)
- **Status**: ✅ Verified | 🔧 In Progress | ⏳ Awaiting Verification | ❌ Broken | ❓ No parser
- **Protocol**: ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square) = web scraping | **[HNAP](https://en.wikipedia.org/wiki/Home_Network_Administration_Protocol)** = [SOAP](https://www.w3.org/TR/soap/)-based, requires auth

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
| <span id="rogers"></span>ROG | Rogers | Canada | — | No BYOM; Rogers equipment required |
| <span id="shaw"></span>SHAW | Shaw Communications | Canada (Western) | — | Merged with Rogers (2023) |
| <span id="videotron"></span>VID | Vidéotron | Canada (Quebec) | — | Helix service requires leased equipment |
| <span id="volia"></span>VOLY | Volia | Ukraine | [Official list](https://en.wikipedia.org/wiki/Volia_(ISP)) | Acquired by Datagroup (2021) |

---
*Generated by `scripts/generate_fixture_index.py`*
