---
paths:
  - "packages/cable_modem_monitor_catalog/**"
  - "packages/cable_modem_monitor_catalog_tools/**"
---

# Catalog and data rules

Loads when a catalog or catalog_tools file is touched. The hard
constraints (HAR immutability, no modem-specific behavior in `modem.yaml`,
HAR intake as the only data path) are in CLAUDE.md § Catalog & Data
Discipline.

- **Verified JSON must be faithful.** `modem.verified.json` is a
  faithful copy of the diagnostics `data` section, not a curated
  subset. Strip list and format:
  `packages/cable_modem_monitor_catalog_tools/docs/MODEM_INTAKE_WORKFLOW.md`
  § Build verified.json.
- **Source all factual claims.** Every factual claim in data files
  (`providers.json`, `chipsets.json`, modem.yaml notes/sources)
  must include a reference URL or citation. Without a source, the
  claim is indistinguishable from fabricated data. If a source
  can't be found, leave the field empty rather than guessing.
- **`packages/cable_modem_monitor_catalog/README.md` is auto-generated.**
  Never edit it directly. Run
  `.venv/bin/python packages/cable_modem_monitor_catalog/scripts/generate_catalog_index.py`
  to regenerate (plain `python3` fails to import the packages).

  Three rules: (1) Contributors are not responsible for
  regenerating it — the `/modem-confirm` and `/modem-intake` skills handle
  it as a verified final step and may bundle it with the catalog commit.
  (2) When multiple catalog changes land in one session, regenerate once
  after all changes are staged, not per-change. (3) CI gates on README
  freshness — if a PR fails this check, regenerate and amend before merging.
- **Catalog data stays true to source; normalization happens at
  presentation.** Manufacturer styling variation is real signal, not
  drift — never pre-normalize in the catalog; display layers own
  case normalization. Authority: `ARCHITECTURE_DECISIONS.md`
  § Core Schema Model → Catalog data stays true to source.
