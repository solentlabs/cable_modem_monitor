# Catalog Tools Documentation

Documentation for the catalog authoring lifecycle. Catalog Tools
covers both ends of a modem's life in the catalog: **intake**
(turning a HAR capture into modem.yaml + parser.yaml + test_data +
golden files) and **confirmation** (turning a contributor's HA
diagnostics into a `verified.json` fixture and flipping the
modem's status from `awaiting_verification` to `confirmed`). Open
to contributors with hardware and (typically) AI assistance for
the judgment layer.

For the integration's core specs, see the
[Core documentation](../../cable_modem_monitor_core/docs/).
For the modem data catalog itself, see the
[Catalog documentation](../../cable_modem_monitor_catalog/docs/).

| Document | Covers |
| -------- | ------ |
| [ONBOARDING_SPEC.md](ONBOARDING_SPEC.md) | Intake pipeline specification — contracts between stages, validation rules |
| [INTAKE_PIPELINE.md](INTAKE_PIPELINE.md) | Pipeline overview — who does what, extension points, fleet patterns |
| [MODEM_INTAKE_WORKFLOW.md](MODEM_INTAKE_WORKFLOW.md) | Runnable workflow — intake (Steps 1–11) and confirmation (Steps 12–15) |

## Why this package is separate

See `../../cable_modem_monitor_core/docs/ARCHITECTURE_DECISIONS.md`
section "catalog_tools is a developer accelerator, never a runtime
dep" for the rationale. In short: Core + Catalog is the minimum
required surface. Catalog Tools helps authors reach a working
configuration faster — it is never installed by Home Assistant.

**Operational test:** deleting this package directory must leave
Core + Catalog + HA fully functional.
