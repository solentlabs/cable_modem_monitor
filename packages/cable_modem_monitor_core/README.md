# Cable Modem Monitor Core

> **Internal dependency of [Cable Modem Monitor](https://github.com/solentlabs/cable_modem_monitor).**
> Not intended for direct use — install the HA integration via [HACS](https://hacs.xyz/).

Platform-agnostic DOCSIS monitoring engine. Provides:

- **Config models** — Pydantic-validated modem configuration (auth, endpoints, parsing)
- **Auth managers** — Pluggable authentication strategies (form, basic, HNAP, PBKDF2, SJCL)
- **Parsers** — Declarative channel and system info extraction from HTML, JSON, and HNAP
- **Orchestration** — Session management, polling coordination, circuit breakers
- **Health monitoring** — ICMP ping and HTTP probes on independent cadence
- **MCP tools** — Onboarding pipeline for new modem configs from HAR captures

## Installation

This package is installed automatically as a dependency of the
[Cable Modem Monitor](https://github.com/solentlabs/cable_modem_monitor)
Home Assistant integration.

```
pip install solentlabs-cable-modem-monitor-core
```

## License

MIT
