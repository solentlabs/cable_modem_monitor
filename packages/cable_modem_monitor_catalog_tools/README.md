# Cable Modem Monitor Catalog Tools

Maintainer authoring tools for the Cable Modem Monitor catalog.

This package contains the intake pipeline — HAR analysis, YAML
generation, golden-file construction, verification ingest, fleet
pattern scanning, and trial parsing. It is run by maintainers to
produce and validate catalog entries; it is **never installed by
Home Assistant**.

Runtime consumers install [Core](../cable_modem_monitor_core/) plus
[Catalog](../cable_modem_monitor_catalog/). The minimum required
surface is those two packages — a maintainer could hand-author a
valid `parser.yaml` and `modem.yaml` and the integration would work
end-to-end. This package exists to reach a working configuration
faster and more consistently, not to make configuration possible.

## Install (developers)

```bash
pip install -e packages/cable_modem_monitor_catalog_tools
```

In the repo dev workflow, the standard install installs all three
packages — see `docs/setup/GETTING_STARTED.md`.

## Docs

See [`docs/README.md`](docs/README.md) for the full index — intake
pipeline overview, onboarding spec, step-by-step workflow.

## Contract

See `../cable_modem_monitor_core/docs/ARCHITECTURE_DECISIONS.md`
section "catalog_tools is a developer accelerator, never a runtime
dep" for the rules this package operates under.
