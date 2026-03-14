# v3.14 Specifications

| Document | Governs |
|----------|---------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design — packages, contracts, invariants, strategies |
| [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md) | Design rationale — the "why" behind the architecture |
| [MODEM_YAML_SPEC.md](MODEM_YAML_SPEC.md) | modem.yaml schema — identity, auth, session, actions |
| [MODEM_DIRECTORY_SPEC.md](MODEM_DIRECTORY_SPEC.md) | Catalog directory structure, file roles, assembly rules |
| [PARSING_SPEC.md](PARSING_SPEC.md) | 6 extraction formats, parser.yaml schema, parser.py contract |
| [RESOURCE_LOADING_SPEC.md](RESOURCE_LOADING_SPEC.md) | Resource dict contract, loader behavior, HNAP batching |
| [RUNTIME_POLLING_SPEC.md](RUNTIME_POLLING_SPEC.md) | Poll cycle, session lifecycle, health pipeline, restart recovery |
| [FIELD_REGISTRY.md](FIELD_REGISTRY.md) | Three-tier field naming authority |
| [VERIFICATION_STATUS.md](VERIFICATION_STATUS.md) | Parser status enum and verification lifecycle |
| [ONBOARDING_SPEC.md](ONBOARDING_SPEC.md) | MCP-driven modem onboarding workflow |

### HA Integration Specs

| Document | Governs |
|----------|---------|
| [CONFIG_FLOW_SPEC.md](../../../custom_components/cable_modem_monitor/docs/CONFIG_FLOW_SPEC.md) | Setup wizard — steps, config entry, variant resolution |
| [ENTITY_MODEL_SPEC.md](../../../custom_components/cable_modem_monitor/docs/ENTITY_MODEL_SPEC.md) | Core output → HA entities, attributes, availability |
