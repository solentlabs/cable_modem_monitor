# Catalog Tools Documentation

Documentation for the maintainer authoring pipeline. Catalog Tools
is the package that takes HAR captures and produces catalog entries
(modem.yaml, parser.yaml, test_data/, golden files).

For the integration's core specs, see the
[Core documentation](../../cable_modem_monitor_core/docs/).
For the modem data catalog itself, see the
[Catalog documentation](../../cable_modem_monitor_catalog/docs/).

| Document | Covers |
| -------- | ------ |
| [ONBOARDING_SPEC.md](ONBOARDING_SPEC.md) | Intake pipeline specification — contracts between stages, validation rules |
| [INTAKE_PIPELINE.md](INTAKE_PIPELINE.md) | Pipeline overview — who does what, extension points, fleet patterns |
| [MODEM_INTAKE_WORKFLOW.md](MODEM_INTAKE_WORKFLOW.md) | Operator workflow — step-by-step instructions with code snippets |

## Why this package is separate

See `../../cable_modem_monitor_core/docs/ARCHITECTURE_DECISIONS.md`
section "catalog_tools is a developer accelerator, never a runtime
dep" for the rationale. In short: Core + Catalog is the minimum
required surface. Catalog Tools helps authors reach a working
configuration faster — it is never installed by Home Assistant.

**Operational test:** deleting this package directory must leave
Core + Catalog + HA fully functional.
