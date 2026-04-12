# SNMP on Cable Modems — Research Findings

> Status: **Deferred.** Research complete, implementation not planned.
> If revisited, consider a standalone utility rather than CMM integration.
>
> Date: 2026-04-11
> Test hardware: Motorola MB7621 (Zoom Telephonics 4590), firmware
> 7621-5.7.1.5, Comcast Xfinity, DOCSIS 3.0

## Summary

SNMP on ISP-managed cable modems is effectively locked down from the
LAN side. v1/v2c are blocked by the ISP via DOCSIS filters. v3 responds
to engine discovery but serves no MIB data without ISP-provisioned
credentials. The cable modem monitoring community has independently
converged on HTTP/HNAP as the data collection method.

The only unique data accessible via SNMP is v3 engine metadata (reboot
count, manufacturer OID, uptime) — three fields available from a single
unauthenticated UDP packet. This does not justify the complexity of an
SNMP transport within CMM.

## Why v1/v2c Are Blocked

ISPs control LAN-side SNMP access via the DOCSIS config file. The
`docsDevNmAccessTable` ([RFC 4639][rfc4639]) filters community-string
access by interface. All tested community strings (`public`, `private`,
`cable-docsis`, `motorola`, and 8 others) timed out — no agent response.

## Why v3 Responds but Is Useless

The DOCSIS `NmAccessTable` only applies to v1/v2c traffic. Per
[RFC 4639][rfc4639]:

> "This table exists only on SNMPv1 or v2c agents and does not exist on
> SNMPv3 agents."

v3 is unfiltered on the LAN side, but the SNMP user table is empty:

- **ISP-provisioned users** (created via TLV34 DH key exchange) are
  bound to the WAN/HFC interface. They don't appear on the LAN side.
- **No firmware default users** exist. Tested 16 common usernames
  (`docsisManager`, `initial`, `admin`, `broadcom`, etc.) — all
  returned "Unknown USM user."
- **Web UI credentials** are separate from SNMP credentials. The
  username `admin` does not exist in the USM user table.

Without a valid USM username, the agent rejects every MIB read. Signal
levels, interface stats, DOCSIS diagnostics — all inaccessible.

## What v3 Engine Discovery Returns

A single raw UDP packet (empty engine ID, empty username, no credentials)
triggers an engine discovery response:

| Field | Example (MB7621) |
|-------|-----------------|
| enterprise_oid | 1.3.6.1.4.1.4590 (Zoom Telephonics) |
| engine_boots | 217 (reboot count) |
| engine_time | ~365,000s (~4.2 days since last boot) |
| engine_id | Contains MAC address (PII) |

This data is **not available from the web UI**. However, it's three
metadata fields — not signal data.

## Counter Side Effects

Every v3 engine discovery increments `usmStatsUnknownEngineIDs` by 1.
On the MB7621 this counter is:

- Not visible in the web UI
- Not logged in the event log
- Only readable via SNMP itself (in the Report PDU)

The counter is defined by [RFC 3414][rfc3414] and is mandatory. There
is no way to perform v3 engine discovery without incrementing it.

## Community Evidence

The cable modem monitoring community uses HTTP/HNAP, not SNMP:

- **[prometheus-moto-exporter][prom-moto]** (MB8600) — uses HNAP.
  Developer: "My device, as configured by the ISP, has SNMP disabled."
- **[going-flying.com][going-flying]** (Arris) — HTTP scraping
- **CMM** — HTTP transport with modem-specific parsers

No cable modem monitoring project uses SNMP for data collection.

## Published Research

- **[IMC '21: Exploiting SNMPv3 for Router Fingerprinting][imc21]** —
  4.6M devices fingerprinted via unauthenticated v3 engine discovery.
  Confirms engine ID contains MAC (PII) and reveals manufacturer.
- **[runZero: Security Surprises with SNMP v3][runzero]** — Devices
  with strong v2 credentials still disclose info via unauthenticated v3.
- **[StringBleed (CVE-2017-5135)][stringbleed]** — SNMP auth bypass
  on 78+ cable modem models (v1/v2c only, not v3).

## Decision

SNMP does not justify integration into CMM:

1. The data that matters (signal levels, error counts) is inaccessible
   via SNMP on ISP-managed modems.
2. The HTTP transport already collects that data.
3. The unique SNMP data (3 metadata fields) doesn't warrant the added
   complexity (pysnmp dependency, raw UDP, PII scrubbing, options UI).
4. The community independently reached the same conclusion.

If SNMP becomes viable (open community strings on business modems,
ISP policy changes), a **standalone SNMP discovery utility** is the
appropriate vehicle — not CMM core integration.

## References

[rfc3414]: https://datatracker.ietf.org/doc/html/rfc3414
[rfc4639]: https://www.rfc-editor.org/rfc/rfc4639.html
[rfc5343]: https://datatracker.ietf.org/doc/html/rfc5343
[imc21]: https://arxiv.org/abs/2109.15095
[runzero]: https://www.runzero.com/blog/security-surprises-with-snmp-v3/
[stringbleed]: https://www.bleepingcomputer.com/news/security/several-cable-modem-models-affected-by-snmp-god-mode-flaw/
[prom-moto]: https://github.com/jahkeup/prometheus-moto-exporter
[going-flying]: https://www.going-flying.com/blog/arris-cable-modem-monitoring.html
[docsis-snmp]: https://docsis.org/forums/docsis-chat/snmp-over-lan-interface
[docsis-v3]: https://www.docsis.org/node/9895
