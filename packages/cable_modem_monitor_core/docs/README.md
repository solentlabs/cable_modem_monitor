# Platform Specifications

| Document | Governs |
|----------|---------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design — packages, contracts, invariants, strategies |
| [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md) | Design rationale — the "why" behind the architecture |
| [AUTH_SJCL_SPEC.md](AUTH_SJCL_SPEC.md) | `form_sjcl` — SJCL AES-CCM protocol, encoding rules, firmware assumptions |
| [AUTH_PBKDF2_SPEC.md](AUTH_PBKDF2_SPEC.md) | `form_pbkdf2` — PBKDF2 challenge-response protocol, salt handling |
| [AUTH_CBN_SPEC.md](AUTH_CBN_SPEC.md) | `form_cbn` — CBN AES-256-CBC protocol, session token rotation |
| [MODEM_YAML_SPEC.md](MODEM_YAML_SPEC.md) | modem.yaml schema — identity, auth, session, actions |
| [MODEM_DIRECTORY_SPEC.md](MODEM_DIRECTORY_SPEC.md) | Catalog directory structure, file roles, assembly rules |
| [PARSING_SPEC.md](PARSING_SPEC.md) | Parsing overview — common concepts, output contract, channel types, aggregates, post-processing |
| [FORMAT_TABLE_SPEC.md](FORMAT_TABLE_SPEC.md) | HTMLTableParser, HTMLTableTransposedParser, companion table merging |
| [FORMAT_JAVASCRIPT_SPEC.md](FORMAT_JAVASCRIPT_SPEC.md) | JSEmbeddedParser (delimited strings), JSJsonParser (JSON in JS) |
| [FORMAT_HNAP_SPEC.md](FORMAT_HNAP_SPEC.md) | HNAPParser — delimiter-separated values in HNAP JSON responses |
| [FORMAT_JSON_SPEC.md](FORMAT_JSON_SPEC.md) | JSONParser — JSON API responses via field paths and array navigation |
| [FORMAT_XML_SPEC.md](FORMAT_XML_SPEC.md) | XMLParser — XML element children via tag name navigation |
| [SYSTEM_INFO_SPEC.md](SYSTEM_INFO_SPEC.md) | system_info extraction — multi-source, format schemas, field tiers |
| [RESOURCE_LOADING_SPEC.md](RESOURCE_LOADING_SPEC.md) | Resource dict contract, loader behavior, HNAP batching |
| [ORCHESTRATION_SPEC.md](ORCHESTRATION_SPEC.md) | Orchestrator, collector, health monitor, restart monitor — interface contracts and data models |
| [ORCHESTRATION_USE_CASES.md](ORCHESTRATION_USE_CASES.md) | 81 scenario-based use cases — normal ops, auth failures, connectivity, restart, health, lifecycle |
| [RUNTIME_POLLING_SPEC.md](RUNTIME_POLLING_SPEC.md) | Poll cycle, session lifecycle, health pipeline, restart recovery |
| [FIELD_REGISTRY.md](FIELD_REGISTRY.md) | Three-tier field naming authority |
| [VERIFICATION_STATUS.md](VERIFICATION_STATUS.md) | Parser status enum and verification lifecycle |
| [ONBOARDING_SPEC.md](ONBOARDING_SPEC.md) | MCP-driven modem onboarding workflow |
| [SNMP_RESEARCH.md](SNMP_RESEARCH.md) | SNMP on cable modems — research findings, deferred |

## HA Integration Specs

| Document | Governs |
|----------|---------|
| [CONFIG_FLOW_SPEC.md](../../../custom_components/cable_modem_monitor/docs/CONFIG_FLOW_SPEC.md) | Setup wizard — steps, config entry, variant resolution |
| [ENTITY_MODEL_SPEC.md](../../../custom_components/cable_modem_monitor/docs/ENTITY_MODEL_SPEC.md) | Core output → HA entities, attributes, availability |
| [HA_ADAPTER_SPEC.md](../../../custom_components/cable_modem_monitor/docs/HA_ADAPTER_SPEC.md) | HA wiring — runtime data, coordinators, polling modes, restart, reauth |
