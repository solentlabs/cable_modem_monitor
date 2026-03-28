# Cable Modem Catalog

Auto-generated index of the v3.14 modem catalog.

**Data Sources:**
- `modem.yaml` — Single source of truth (manufacturer, model, hardware, ISPs, status)

**Supported Modems:** 28 (1 ✅ confirmed, 27 ⏳ awaiting)

**Auth strategies:** form (11), none (6), basic (4), hnap (3), form_pbkdf2 (2), url_token (1), form_sjcl (1)

## Directory Structure

Each modem has a self-contained directory in the catalog package:

```
packages/cable_modem_monitor_catalog/.../modems/
└── {manufacturer}/
    └── {model}/
        ├── modem.yaml           # Configuration, auth, hardware metadata
        ├── parser.yaml          # Declarative channel/system_info extraction
        ├── parser.py            # Optional PostProcessor for complex parsing
        └── test_data/           # HAR captures and golden files
            ├── modem.har
            └── modem.expected.json
```

## Supported Modems

| Manufacturer | Model | DOCSIS | Transport | Chipset | Auth | ISPs | Names | Status |
|--------------|-------|--------|-----------|---------|------|------|-------|--------|
| ARRIS | [CM3500B](arris/cm3500b/modem.yaml) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") |  | form | [![VDF](https://img.shields.io/badge/-VDF-aa6666?style=flat-square "Vodafone Kabel")](#vodafone) | CM3500B | ⏳ Awaiting |
| ARRIS | [CM820B](arris/cm820b/modem.yaml) | 3.0 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [Puma 5](#puma-5) | none | [![VOLY](https://img.shields.io/badge/-VOLY-5599aa?style=flat-square "Volia")](#volya) ![VARI](https://img.shields.io/badge/-VARI-gray?style=flat-square "Various") | CM820B<br>Zoom 5370<br>Thomson TCM420 | ⏳ Awaiting |
| CommScope | [G54](arris/g54/modem.yaml) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3390](#bcm3390) | form | [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) [![XFI](https://img.shields.io/badge/-XFI-aa7788?style=flat-square "Xfinity")](#xfinity) | G54<br>G54_COMMSCOPE<br>G5X | ⏳ Awaiting |
| Arris | [S33](arris/s33/modem.yaml) | 3.1 | ![HNAP](https://img.shields.io/badge/-HNAP-5B8FBF?style=flat-square "SOAP-based, requires auth") | [BCM3390](#bcm3390) | hnap | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) [![XFI](https://img.shields.io/badge/-XFI-aa7788?style=flat-square "Xfinity")](#xfinity) | S33<br>S33v2 | ⏳ Awaiting |
| Arris | [S34](arris/s34/modem.yaml) | 3.1 | ![HNAP](https://img.shields.io/badge/-HNAP-5B8FBF?style=flat-square "SOAP-based, requires auth") | [BCM3390](#bcm3390) | hnap | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) [![XFI](https://img.shields.io/badge/-XFI-aa7788?style=flat-square "Xfinity")](#xfinity) | S34 | ⏳ Awaiting |
| ARRIS | [SB6141](arris/sb6141/modem.yaml) | 3.0 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3380](#bcm3380) | none | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) [![TWC](https://img.shields.io/badge/-TWC-7799aa?style=flat-square "Time Warner Cable")](#twc)<br>[![MED](https://img.shields.io/badge/-MED-557799?style=flat-square "Mediacom")](#mediacom) | SB6141<br>Motorola SB6141 | ⏳ Awaiting |
| ARRIS | [SB6190](arris/sb6190/modem.yaml) | 3.0 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [Puma 6](#puma-6) | none<br>form_nonce | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) [![TWC](https://img.shields.io/badge/-TWC-7799aa?style=flat-square "Time Warner Cable")](#twc) | SB6190 | ⏳ Awaiting |
| ARRIS | [SB8200](arris/sb8200/modem.yaml) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3390](#bcm3390) | url_token | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SERV](https://img.shields.io/badge/-SERV-778899?style=flat-square "Service Electric Cablevision")](#service-electric) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum)<br>[![XFI](https://img.shields.io/badge/-XFI-aa7788?style=flat-square "Xfinity")](#xfinity) | SB8200 | ⏳ Awaiting |
| Arris | [TG3442DE](arris/tg3442de/modem.yaml) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [Puma 7](#puma-7) | form_sjcl | [![VDF](https://img.shields.io/badge/-VDF-aa6666?style=flat-square "Vodafone Kabel")](#vodafone) | TG3442DE | ⏳ Awaiting |
| ARRIS | [TM1602A](arris/tm1602a/modem.yaml) | 3.0 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [Puma 6](#puma-6) | none | [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) | TM1602A | ⏳ Awaiting |
| Hitron | [CODA56](hitron/coda56/modem.yaml) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") |  | form | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![XFI](https://img.shields.io/badge/-XFI-aa7788?style=flat-square "Xfinity")](#xfinity) | CODA56 | ⏳ Awaiting |
| Motorola | [MB7621](motorola/mb7621/modem.yaml) | 3.0 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3384](#bcm3384) | form | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) [![TWC](https://img.shields.io/badge/-TWC-7799aa?style=flat-square "Time Warner Cable")](#twc)<br>[![C1](https://img.shields.io/badge/-C1-7788aa?style=flat-square "Cable One")](#cableone) [![RCN](https://img.shields.io/badge/-RCN-556688?style=flat-square "RCN Corporation")](#rcn) [![SUD](https://img.shields.io/badge/-SUD-6699aa?style=flat-square "Suddenlink")](#suddenlink) [![BRIG](https://img.shields.io/badge/-BRIG-6688aa?style=flat-square "BrightHouse")](#brighthouse) | MB7621 | ✅ Confirmed |
| Motorola | [MB8611](motorola/mb8611/modem.yaml) | 3.1 | ![HNAP](https://img.shields.io/badge/-HNAP-5B8FBF?style=flat-square "SOAP-based, requires auth") | [BCM3390](#bcm3390) | hnap | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![XFI](https://img.shields.io/badge/-XFI-aa7788?style=flat-square "Xfinity")](#xfinity) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) | MB8611<br>MB8600<br>MB8612 | ⏳ Awaiting |
| Netgear | [C3700](netgear/c3700/modem.yaml) | 3.0 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3383](#bcm3383) | basic | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) | C3700 | ⏳ Awaiting |
| Netgear | [C7000v2](netgear/c7000v2/modem.yaml) | 3.0 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3384](#bcm3384) | basic | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) | C7000v2 | ⏳ Awaiting |
| Netgear | [CM1100](netgear/cm1100/modem.yaml) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3390](#bcm3390) | form | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) | CM1100 | ⏳ Awaiting |
| Netgear | [CM1200](netgear/cm1200/modem.yaml) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3390](#bcm3390) | none<br>basic | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) | CM1200 | ⏳ Awaiting |
| Netgear | [CM2000](netgear/cm2000/modem.yaml) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3390](#bcm3390) | form | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) [![XFI](https://img.shields.io/badge/-XFI-aa7788?style=flat-square "Xfinity")](#xfinity) | CM2000 | ⏳ Awaiting |
| Netgear | [CM2050V](netgear/cm2050v/modem.yaml) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3390](#bcm3390) | form | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![XFI](https://img.shields.io/badge/-XFI-aa7788?style=flat-square "Xfinity")](#xfinity) | CM2050V | ⏳ Awaiting |
| Netgear | [CM600](netgear/cm600/modem.yaml) | 3.0 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3384](#bcm3384) | basic | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) [![TWC](https://img.shields.io/badge/-TWC-7799aa?style=flat-square "Time Warner Cable")](#twc) | CM600 | ⏳ Awaiting |
| Sercomm | [DM1000](sercomm/dm1000/modem.yaml) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | Broadcom | form | [![KOOD](https://img.shields.io/badge/-KOOD-77aa88?style=flat-square "Koodo")](#kood) | DM1000 | ⏳ Awaiting |
| Technicolor | [CGA2121](technicolor/cga2121/modem.yaml) | 3.0 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3384](#bcm3384) | form | [![TEL](https://img.shields.io/badge/-TEL-9966aa?style=flat-square "Telia")](#telia) | CGA2121 | ⏳ Awaiting |
| Technicolor | [CGA4236](technicolor/cga4236/modem.yaml) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") |  | form_pbkdf2 | ![UNKN](https://img.shields.io/badge/-UNKN-gray?style=flat-square "Unknown") | CGA4236<br>CGA4236TCH1 | ⏳ Awaiting |
| Technicolor | [CGA6444VF](technicolor/cga6444vf/modem.yaml) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") |  | form_pbkdf2 | [![VDF](https://img.shields.io/badge/-VDF-aa6666?style=flat-square "Vodafone Kabel")](#vodafone) | CGA6444VF | ⏳ Awaiting |
| Technicolor | [TC4400](technicolor/tc4400/modem.yaml) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3390](#bcm3390) | basic | [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications")](#cox) [![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)")](#spectrum) [![ROG](https://img.shields.io/badge/-ROG-aa6666?style=flat-square "Rogers Communications")](#rogers)<br>[![SHAW](https://img.shields.io/badge/-SHAW-668899?style=flat-square "Shaw Communications")](#shaw) [![VID](https://img.shields.io/badge/-VID-779988?style=flat-square "Vidéotron")](#videotron) [![VDF](https://img.shields.io/badge/-VDF-aa6666?style=flat-square "Vodafone Kabel")](#vodafone) [![UM](https://img.shields.io/badge/-UM-778899?style=flat-square "Unitymedia")](#unitymedia)<br>[![TEKS](https://img.shields.io/badge/-TEKS-669977?style=flat-square "Teksavvy")](#teksavvy) | TC4400<br>TC4400AM | ⏳ Awaiting |
| Technicolor | [XB6](technicolor/xb6/modem.yaml) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3390](#bcm3390) | form | [![ROG](https://img.shields.io/badge/-ROG-aa6666?style=flat-square "Rogers Communications")](#rogers) | XB6<br>CGM4140COM | ⏳ Awaiting |
| Technicolor | [XB7](technicolor/xb7/modem.yaml) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3390](#bcm3390) | form | [![ROG](https://img.shields.io/badge/-ROG-aa6666?style=flat-square "Rogers Communications")](#rogers) [![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast")](#comcast) [![XFI](https://img.shields.io/badge/-XFI-aa7788?style=flat-square "Xfinity")](#xfinity) | XB7<br>CGM4331COM | ⏳ Awaiting |
| Virgin Media | [Hub 5](virgin/superhub5/modem.yaml) | 3.1 | ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping") | [BCM3390](#bcm3390) | none | [![VM](https://img.shields.io/badge/-VM-aa4466?style=flat-square "Virgin Media")](#virgin) | Hub 5<br>SuperHub 5<br>VMDG660<br>F3896LG-VMB | ⏳ Awaiting |

## Unsupported Modems

Modems we're aware of but cannot currently support (ISP lockdown, missing data, etc.).

| Manufacturer | Model | DOCSIS | ISP | Notes |
|--------------|-------|--------|-----|-------|
| Compal | [CH8978E](compal/ch8978e/modem.yaml) | 3.1 | [![PYÜR](https://img.shields.io/badge/-PY%C3%9CR-aa6699?style=flat-square "Pyür")](#pyür) | 🚫 Unsupported |

## Model Timeline

```
DOCSIS 3.0
├── 2011  ARRIS       CM820B     ░███████████████████  15yr  Current
├── 2011  ARRIS       SB6141     ░██████████░░░░░░░░░   8yr  EOL 2019
├── 2014  Netgear     C3700      ░░░░░██████████░░░░░   8yr  EOL 2022
├── 2015  Technicolor CGA2121    ░░░░░░██████████████  11yr  Current
├── 2016  Netgear     C7000v2    ░░░░░░░█████████████  10yr  Current
├── 2016  Netgear     CM600      ░░░░░░░█████████░░░░   7yr  EOL 2023
├── 2016  ARRIS       SB6190     ░░░░░░░█████████░░░░   7yr  EOL 2023
└── 2017  Motorola    MB7621     ░░░░░░░░████████████   9yr  Current

DOCSIS 3.1
├── 2016  ARRIS       CM3500B    ░░░░░░░█████████████  10yr  Current
├── 2017  ARRIS       SB8200     ░░░░░░░░████████████   9yr  Current
├── 2017  Technicolor TC4400     ░░░░░░░░████████████   9yr  Current
├── 2019  Netgear     CM1200     ░░░░░░░░░░░█████████   7yr  Current
├── 2020  Netgear     CM2000     ░░░░░░░░░░░░████████   6yr  Current
├── 2020  Motorola    MB8611     ░░░░░░░░░░░░████████   6yr  Current
├── 2020  Arris       S33        ░░░░░░░░░░░░████████   6yr  Current
├── 2020  Technicolor XB7        ░░░░░░░░░░░░████████   6yr  Current
├── 2021  Virgin      Hub 5      ░░░░░░░░░░░░░███████   5yr  Current
├── 2023  Compal      CH8978E    ░░░░░░░░░░░░░░░░████   3yr  Current
├── 2023  CommScope   G54        ░░░░░░░░░░░░░░░░████   3yr  Current
└── 2024  Arris       S34        ░░░░░░░░░░░░░░░░░███   2yr  Current
```

_Timeline: █ = years actively supported, ░ = discontinued or not yet released_
_Scale: 2010-2026 (16 years)_

## Legend

- **Names**: All model names and part numbers that share this config (searchable)
- **Status**: ✅ Confirmed | ⏳ Awaiting Verification | 🚫 Unsupported
- **Transport**: ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square) = web scraping | ![REST](https://img.shields.io/badge/-REST-5B9A5B?style=flat-square) = JSON REST API | [![HNAP](https://img.shields.io/badge/-HNAP-5B8FBF?style=flat-square)](https://en.wikipedia.org/wiki/Home_Network_Administration_Protocol) = SOAP-based, requires auth

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
| <span id="rogers"></span>ROG | Rogers | Canada | [Official list](https://www.rogers.com/) | No BYOM; Rogers equipment required |
| <span id="shaw"></span>SHAW | Shaw Communications | Canada (Western) | [Official list](https://www.shaw.ca/) | Merged with Rogers (2023) |
| <span id="videotron"></span>VID | Vidéotron | Canada (Quebec) | [Official list](https://www.videotron.com/) | Helix service requires leased equipment |
| <span id="volia"></span>VOLY | Volia | Ukraine | [Official list](https://en.wikipedia.org/wiki/Volia_(ISP)) | Acquired by Datagroup (2021) |
| <span id="pyür"></span>PYÜR | Pyür | Germany | [Official list](https://www.pyur.com/) | Formerly Tele Columbus |
| <span id="vodafone"></span>VDF | Vodafone Kabel | Germany | [Official list](https://www.vodafone.de/) | BYOM allowed since 2016; absorbed Unitymedia |
| <span id="unitymedia"></span>UM | Unitymedia | Germany (West) | — | Merged into Vodafone (2019) |
| <span id="virgin"></span>VM | Virgin Media | UK | [Official list](https://www.virginmedia.com/) | No BYOM; modem mode available |
| <span id="telia"></span>TEL | Telia | Nordic/Baltic | [Official list](https://www.teliacompany.com/) | Sweden, Finland, Norway, Baltics |
| <span id="mediacom"></span>MED | Mediacom | US (Midwest/South) | [Official list](https://mediacomcable.com/compatible-retail-modems/) |  |
| <span id="rcn"></span>RCN | Astound (formerly RCN) | US (Northeast) | [Official list](https://www.astound.com/support/internet/bring-your-own-modem/) | No official list; DOCSIS 3.1 recommended |
| <span id="cableone"></span>C1 | Sparklight (Cable One) | US (21 states) | [Official list](https://support.sparklight.com/hc/en-us/articles/115009158227-Supported-Modems-Residential-Only) | DOCSIS 3.1 required |
| <span id="kood"></span>KOOD | Koodo | Canada | — | Telus subsidiary |
| <span id="brighthouse"></span>BRIG | BrightHouse Networks | US (Southeast) | — | Merged into Spectrum (2016). Source: https://en.wikipedia.org/wiki/Bright_House_Networks |
| <span id="service-electric"></span>SERV | Service Electric Cablevision | US (Pennsylvania) | [Official list](https://www.sectv.com/) | Family-owned regional ISP since 1948. Source: https://en.wikipedia.org/wiki/Service_Electric |
| <span id="teksavvy"></span>TEKS | Teksavvy | Canada | [Official list](https://teksavvy.com/services/internet/) | Independent Canadian ISP/reseller. Source: https://en.wikipedia.org/wiki/TekSavvy |

---
*Generated by `scripts/generate_catalog_index.py` from 29 modem configs*
