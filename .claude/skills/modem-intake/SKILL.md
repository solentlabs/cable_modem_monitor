---
name: modem-intake
description: Download and analyze HAR captures from modem request issues, run the intake pipeline to generate modem configs, and produce tested catalog entries. Stops cleanly when Core doesn't support a detected pattern.
---

# Modem Intake

Follow the workflow in
`packages/cable_modem_monitor_catalog_tools/docs/MODEM_INTAKE_WORKFLOW.md`.

Read that file and execute each step in order.

After the catalog README step, re-grade the HA quality scale (procedure:
the docstring of `scripts/generate_quality_scale_table.py`) and include
any change in the files shown to the developer.
