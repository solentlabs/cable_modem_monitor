# Modem Fixture Library

Auto-generated index of modem fixtures.

**Data Sources:**
- `metadata.yaml` - Release dates, EOL, DOCSIS version, ISPs
- Parser classes - Verified status, manufacturer
- `README.md` - Model name, contributor notes

**Total Modems:** 12

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

| Manufacturer | Model | DOCSIS | ISPs | Files | Status |
|--------------|-------|--------|------|-------|--------|
| Arris/CommScope | [S33](arris/fixtures/s33/README.md) | 3.1 | ![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast") ![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications") ![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)") | 2 | ⏳ Awaiting |
| ARRIS | [SB6141](arris/fixtures/sb6141/README.md) | 3.0 | ![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast") ![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications") ![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)") ![TWC](https://img.shields.io/badge/-TWC-7799aa?style=flat-square "Time Warner Cable") ![MED](https://img.shields.io/badge/-MED-557799?style=flat-square "Mediacom") | 1 | ✅ Verified |
| ARRIS | [SB6190](arris/fixtures/sb6190/README.md) | 3.0 | ![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast") ![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications") ![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)") ![TWC](https://img.shields.io/badge/-TWC-7799aa?style=flat-square "Time Warner Cable") | 1 | ✅ Verified |
| ARRIS | [SB8200](arris/fixtures/sb8200/README.md) | 3.1 | ![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast") ![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications") ![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)") | 3 | ✅ Verified |
| Motorola | [MB7621](motorola/fixtures/mb7621/README.md) | 3.0 | ![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast") ![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications") ![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)") ![TWC](https://img.shields.io/badge/-TWC-7799aa?style=flat-square "Time Warner Cable") ![RCN](https://img.shields.io/badge/-RCN-556688?style=flat-square "RCN Corporation") ![C1](https://img.shields.io/badge/-C1-7788aa?style=flat-square "Cable One") | 5 | ✅ Verified |
| Motorola | [MB8600](motorola/fixtures/mb8600/README.md) | 3.1 | ![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast") ![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications") ![C1](https://img.shields.io/badge/-C1-7788aa?style=flat-square "Cable One") | 1 | 🔧 In Progress |
| Motorola | [MB8611](motorola/fixtures/mb8611/README.md) | 3.1 | ![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast") ![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications") ![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)") | 6 | ⏳ Awaiting |
| Netgear | [C3700-100NAS](netgear/fixtures/c3700/README.md) | 3.0 | ![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast") ![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications") ![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)") | 6 | ✅ Verified |
| Netgear | [CM2000 (Nighthawk)](netgear/fixtures/cm2000/README.md) | 3.1 | ![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast") ![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications") ![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)") | 7 | ⏳ Awaiting |
| Netgear | [CM600 (CM600-100NAS)](netgear/fixtures/cm600/README.md) | 3.0 | ![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast") ![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications") ![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)") ![TWC](https://img.shields.io/badge/-TWC-7799aa?style=flat-square "Time Warner Cable") | 5 | ✅ Verified |
| Technicolor | [TC4400](technicolor/fixtures/tc4400/README.md) | 3.1 | ![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast") ![COX](https://img.shields.io/badge/-COX-cc9966?style=flat-square "Cox Communications") ![SPEC](https://img.shields.io/badge/-SPEC-6699aa?style=flat-square "Spectrum (Charter)") ![ROG](https://img.shields.io/badge/-ROG-aa6666?style=flat-square "Rogers Communications") ![SHAW](https://img.shields.io/badge/-SHAW-668899?style=flat-square "Shaw Communications") ![VID](https://img.shields.io/badge/-VID-779988?style=flat-square "Vidéotron") | 3 | ✅ Verified |
| Technicolor | [XB7 / CGM4331COM](technicolor/fixtures/xb7/README.md) | 3.1 | ![COM](https://img.shields.io/badge/-COM-5588aa?style=flat-square "Comcast") | 1 | ✅ Verified |

## Model Timeline

```
DOCSIS 3.0
├── 2011  ARRIS       SB6141     ░███████████░░░░░░░░   8yr  EOL 2019
├── 2014  Netgear     C3700-100N ░░░░░███████████░░░░   8yr  EOL 2022
├── 2016  Netgear     CM600      ░░░░░░░░█████████░░░   7yr  EOL 2023
├── 2016  ARRIS       SB6190     ░░░░░░░░█████████░░░   7yr  EOL 2023
└── 2017  Motorola    MB7621     ░░░░░░░░░███████████   8yr  Current

DOCSIS 3.1
├── 2017  Motorola    MB8600     ░░░░░░░░░███████████   8yr  Current
├── 2017  ARRIS       SB8200     ░░░░░░░░░███████████   8yr  Current
├── 2017  Technicolor TC4400     ░░░░░░░░░███████████   8yr  Current
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

---
*Generated by `scripts/generate_fixture_index.py`*
