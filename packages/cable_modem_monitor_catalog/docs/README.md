# Catalog Documentation

This package contains modem configurations (modem.yaml), parser overrides
(parser.py), and test resources (HAR captures, golden files). It has no
business logic.

For architecture, specs, and field definitions, see the
[Core documentation](../../cable_modem_monitor_core/docs/).

| Document | Covers |
|----------|--------|
| [MOCK_SERVER.md](MOCK_SERVER.md) | Mock server for testing catalog entries |

Intake pipeline / onboarding workflow docs moved to
[Catalog Tools docs](../../cable_modem_monitor_catalog_tools/docs/)
in v3.14. Catalog Tools is a separate, optional maintainer package —
not installed by HA. Look there for `INTAKE_PIPELINE.md`,
`MODEM_INTAKE_WORKFLOW.md`, and `ONBOARDING_SPEC.md`.

**Note:** `FIELD_REGISTRY.md` and `VERIFICATION_STATUS.md` have moved to
[Core docs](../../cable_modem_monitor_core/docs/) — they define contracts
owned by the core package.
