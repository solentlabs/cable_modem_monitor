# Modem Support Status

> Auto-generated. Run `scripts/generate_catalog_index.py` to refresh.

**51 configurations supported** — 33 confirmed on real hardware, 18 awaiting verification.

---

## Capture column

How each fixture was produced, read from the HAR's `creator` field.
Definitions and rules:
[MODEM_INTAKE_WORKFLOW.md § Assembled fixtures](https://github.com/solentlabs/cable_modem_monitor/blob/main/packages/cable_modem_monitor_catalog_tools/docs/MODEM_INTAKE_WORKFLOW.md#assembled-fixtures).

| Value | Meaning |
|-------|---------|
| `—` | Recorded from real hardware by a browser or capture tool |
| `hybrid` | Assembled from multiple real captures of the same unit; every byte observed |
| `reconstructed` | Built on a sibling model's template; structure never observed on this hardware |
| `synthetic` | Built from partial evidence; the fixture names its producer |
| `generated` | Built from partial evidence; no producer recorded in the file |

An entry showing anything other than `—` would benefit from a real
capture. Where an entry has several fixtures, the weakest is shown.

---

## Restart column

Whether the entry's own capture holds the request its declared restart sends.
A restart the capture lacks replays against a synthesized answer, so a passing
test proves only that Core sends the declared request, not that the firmware
accepts it.

| Value | Meaning |
|-------|---------|
| `captured` | A captured request is the declared restart (`http`: method and path; `hnap`: action name; `cbn`: `fun` code; `json_rpc`: method) |
| `not captured` | A restart is declared and no captured request matches |
| `n/a` | No restart declared |

An entry showing `not captured` would benefit from a capture that includes
pressing Restart. Read it with the Capture column: a restart inside a
`synthetic`, `generated` or `reconstructed` fixture was written to match Core,
not observed. Where a config replays against several fixtures, one holding the
restart is enough.

---

## Needs Testing

The integration is implemented and CI passes for these modems.
They just need someone with that hardware to confirm it works
and share a diagnostics snapshot.

| Modem | Transport | ISPs | Capture | Restart |
|-------|-----------|------|---------|---------|
| S34 | HNAP | Comcast, Cox, Spectrum, Xfinity | synthetic | not captured |
| SB8200 (Form Login CBN) | CBN | Comcast, Cox, Spectrum, Xfinity | synthetic | not captured |
| G54 | HTML | Cox, Spectrum, Xfinity | generated | n/a |
| C3700 | HTML | Comcast, Cox, Spectrum | synthetic | not captured |
| CM2000 | HTML | Comcast, Cox, Spectrum, Xfinity | synthetic | not captured |
| CM2500 | HTML | Comcast, Cox, Spectrum | reconstructed | captured |
| CM600 | HTML | Comcast, Cox, Spectrum, TWC | synthetic | not captured |
| NE6037 | JSON-RPC | Play | — | captured |
| CGA2121 | HTML | Telia | generated | n/a |
| CGA4236 | HTML | Unknown | — | n/a |
| CGA6444VF | HTML | Vodafone | — | n/a |
| TC4400 | HTML | Comcast, Cox, Spectrum, Rogers, Shaw, Videotron, Vodafone Germany, Unitymedia, Teksavvy | — | n/a |
| EVW32C-0N | HTML | Telemach | hybrid | captured |

## Pending Review

These have a hardware report on file but haven't been promoted to Confirmed yet.
May have open repair work — review individually.

| Modem | Transport | ISPs | Capture | Restart |
|-------|-----------|------|---------|---------|
| SB6190 | HTML | Comcast, Cox, Spectrum, TWC | — | n/a |
| SB8200 (cookie) | HTML | Spectrum | synthetic | n/a |
| SB8200 (url-token) | HTML | Comcast, Cox, Spectrum, Xfinity | synthetic | n/a |
| SB8200 (No Authentication) | HTML | Service Electric Cablevision | synthetic | n/a |
| CM1200 | HTML | Comcast, Spectrum, Cox | — | n/a |

## Confirmed

Working on real hardware with a report on file.
Entries with an open capability gap are listed above, not here.

| Modem | Transport | ISPs | Capture | Restart |
|-------|-----------|------|---------|---------|
| CM3500B | HTML | Vodafone Germany, Vodafone | generated | n/a |
| CM820B | HTML | Volya | synthetic | n/a |
| S33 | HNAP | Comcast, Cox, Spectrum, Xfinity | — | captured |
| S33 (v2) | HNAP | Comcast, Cox, Spectrum, Xfinity | — | not captured |
| S33 (v3) | HNAP | Comcast, Cox, Spectrum, Xfinity | — | not captured |
| SB6141 | HTML | Comcast, Cox, Spectrum, TWC, Mediacom | hybrid | n/a |
| SB6183 | HTML | Comcast, Cox, Spectrum, Xfinity, Mediacom | synthetic | n/a |
| SB6190 (form-nonce) | HTML | Comcast, Spectrum | — | n/a |
| SB8200 (body-token) | HTML | Spectrum | synthetic | n/a |
| SB8200 (HNAP) | HNAP | Cox | — | n/a |
| SB8200 (php) | HTML | RCN | — | n/a |
| SBG7400AC2 | HTML | Cox | — | captured |
| SBG8300 | HTML | Comcast, Cox, Spectrum | — | captured |
| TG3442DE | HTML | Vodafone DE | synthetic | n/a |
| TG3442S | HTML | LIWEST | — | captured |
| TM1602A | HTML | Spectrum | — | n/a |
| CH7465MT | CBN | Magenta AT | — | captured |
| CODA56 | HTML | Comcast, Xfinity | — | n/a |
| MB7621 | HTML | Comcast, Cox, Spectrum, TWC, CableOne, RCN, Comcast Xfinity, Suddenlink, BrightHouse | — | captured |
| MB8600 | HNAP | Comcast, Xfinity, Cox, Spectrum | synthetic | not captured |
| MB8611 | HNAP | Comcast, Xfinity, Cox, Spectrum | synthetic | captured |
| C7000v2 | HTML | Comcast | — | not captured |
| CM1100 | HTML | Comcast | — | n/a |
| CM1200 (basic) | HTML | Comcast, Spectrum, Cox | — | n/a |
| CM2050V | HTML | Comcast, Xfinity | — | n/a |
| CM3000 | HTML | Comcast, Cox, Spectrum, Xfinity | — | n/a |
| F3896LG-VMB | HTML | Virgin Media UK | generated | captured |
| F3896LG-ZG | HTML | Ziggo | — | not captured |
| DM1000 | HTML | Koodo | hybrid | captured |
| XB10 | HTML | Xfinity | — | not captured |
| XB6 | HTML | Rogers | — | n/a |
| XB7 | HTML | Rogers, Comcast, Xfinity | generated | n/a |
| XB8 | HTML | Rogers, Comcast, Xfinity, Cox | — | captured |

---

Generated by `scripts/generate_catalog_index.py`.
