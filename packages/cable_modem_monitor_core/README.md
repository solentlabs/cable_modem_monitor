# Cable Modem Monitor Core

[![PyPI version](https://img.shields.io/pypi/v/solentlabs-cable-modem-monitor-core)](https://pypi.org/project/solentlabs-cable-modem-monitor-core/)
[![Downloads](https://img.shields.io/pypi/dm/solentlabs-cable-modem-monitor-core)](https://pypi.org/project/solentlabs-cable-modem-monitor-core/)
[![Python](https://img.shields.io/pypi/pyversions/solentlabs-cable-modem-monitor-core)](https://pypi.org/project/solentlabs-cable-modem-monitor-core/)
[![CI](https://github.com/solentlabs/cable_modem_monitor/actions/workflows/tests.yml/badge.svg)](https://github.com/solentlabs/cable_modem_monitor/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

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
