---
name: modem-intake
description: Download and analyze HAR captures from modem request issues, run the intake pipeline to generate modem configs, and produce tested catalog entries. Stops cleanly when Core doesn't support a detected pattern.
---

<!-- Master copy: skills/modem-intake.md — edit there, not in .claude/skills/ -->

# Modem Intake

> **Invocation note**: Project-local skills in `skills/` are not registered as Skill tool
> targets — `Skill("modem-intake")` will return "Unknown skill". Read this file and
> execute the steps directly. This is a Claude Code limitation, not a config gap.

Follow the workflow in
`packages/cable_modem_monitor_catalog_tools/docs/MODEM_INTAKE_WORKFLOW.md`.

Read that file and execute each step in order.
