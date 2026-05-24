# Blueprint Distribution Specification

How CMM ships reusable HA blueprints to users without making the integration
the place where opinionated interpretation lives.

**Design principles:**

- Integration translates objective modem data; blueprints interpret it
- URL import is the default distribution path; HACS is a growth-triggered option
- `docs/examples/` is the canonical in-repo location for distributed YAML
- Distributed YAML is outside the HACS integration zip, so the integration's runtime footprint is unchanged
- Contribution review covers structure and attribution, not content correctness

---

## Contents

| Section | What it covers |
|---------|----------------|
| [Problem and Use Case](#problem-and-use-case) | What we're solving and the first concrete instance |
| [Why This Approach](#why-this-approach) | Decision rationale with citations |
| [Structure](#structure) | Directory layout, file naming, organization by blueprint type |
| [User Flow](#user-flow) | How a user imports and uses a blueprint |
| [Contribution Flow](#contribution-flow) | How a contributor PRs a new blueprint |
| [Growth Path](#growth-path) | Triggers for evolving toward HACS distribution |
| [Tradeoffs](#tradeoffs) | Honest costs and benefits |
| [Out of Scope](#out-of-scope) | What this spec does not address |
| [References](#references) | Source citations |

---

## Problem and Use Case

CMM exposes objective DOCSIS data per modem as entities. Users frequently
want interpreted entities derived from that data: aggregate health summaries,
alert triggers, simplified status. The current path is hand-rolling Jinja
template sensors against entity IDs the user has to find manually. This
creates a recurring contributor pattern of feature requests asking the
integration to absorb interpretation logic.

First concrete instance: discussion
[#161](https://github.com/solentlabs/cable_modem_monitor/discussions/161)
(ccpk1, "Success story: CMM with custom signal health monitor"). A complete
template-sensor plus Lovelace dashboard that grades signal as
good/fair/poor based on user-tunable thresholds. Issue
[#144](https://github.com/solentlabs/cable_modem_monitor/issues/144) is the
corresponding feature request asking the integration to ship it as a built-in
sensor.

The principle for declining integration-side interpretation is documented:

- **ENTITY_MODEL_SPEC.md** (peer doc): *"The integration exposes what the
  modem provides... Users derive additional entities (template sensors,
  binary_sensors) from attributes as needed. The integration does not create
  entities for every possible use case."*
- **CLAUDE.md § Decision Discipline**: *"Know what you know. Don't speculate.
  Model what we actually observe; stop there. Don't add inference-based
  features when the signal is ambiguous (multi-signal voting, tunable
  thresholds, etc. are tells)."*

What was missing before this spec: a sanctioned home for user-derived
entities so they don't trap in forum posts and so future #144-shaped requests
have an answer that respects the principle.

---

## Why This Approach

Approach: HA template-entity blueprint YAML files shipped from CMM via
`docs/examples/blueprints/` for URL import into Home Assistant.

### Why blueprints rather than integration features

- **ENTITY_MODEL_SPEC** delegates this case to users (quoted above).
- **CLAUDE.md § Decision Discipline** rejects integration-level inference of
  the exact shape requested in #144 (multi-signal voting, tunable thresholds).
- **ARCHITECTURE_DECISIONS.md § "Generic timing, not per-modem knobs"**
  rejected user-tunable per-modem subjective values with rationale that
  applies to user-tunable health thresholds for the same reasons
  (firmware-version drift, plant-condition variance).

### Why URL import rather than HACS distribution today

- **CLAUDE.md § Code Discipline**: *"No infrastructure for hypothetical
  recurrence. Before adding a test, CI job, hook, script, or module to address
  a one-shot incident, state the problem in one sentence and ask: am I
  protecting against documented past failures, or against a hypothetical
  future one?"* HACS template-category repo setup for one blueprint candidate
  is hypothetical recurrence.
- HA blueprint URL import accepts any GitHub URL pointing at valid blueprint
  YAML. Verified at the HA blueprint user guide
  ([HA docs](https://www.home-assistant.io/docs/blueprint/)) and in HA Core
  source code at
  [`homeassistant/components/blueprint/models.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/blueprint/models.py).
  No HACS metadata or repo restructure is required for this path.

### Why `docs/examples/` as the location

- Project memory rule `feedback_no_inline_json_in_tests` directs example YAML
  to `docs/examples/*.yaml` as the canonical location for this kind of
  content.
- `docs/examples/` already exists in the repo.
- Files at repo-root `docs/examples/` are outside the working directory of
  the HACS integration zip command. The zip command runs from
  `custom_components/cable_modem_monitor/` per
  `.github/workflows/release.yml` lines 80-88:

  ```bash
  cd custom_components/cable_modem_monitor
  # Exclude docs/ (dev specs, not needed at runtime) and
  # any bytecode cache.
  zip -r ../../cable_modem_monitor.zip . -x 'docs/*' '*__pycache__*'
  ```

  Files under repo-root `docs/examples/` are never seen by this command, so
  they do not ship with the integration regardless of any future changes to
  the zip's include/exclude rules.

---

## Structure

Directory layout under repo-root `docs/`:

```text
docs/examples/blueprints/
├── template/                       # template-type blueprints (sensors, binary_sensors, numbers)
│   └── <name>.yaml
├── automation/                     # automation-type blueprints (added when first lands)
│   └── <name>.yaml
└── script/                         # script-type blueprints (added when first lands)
    └── <name>.yaml
```

Subdirectory-by-type mirrors HA Core's own organization at
[`homeassistant/components/automation/blueprints/`](https://github.com/home-assistant/core/tree/dev/homeassistant/components/automation/blueprints).

**File naming:** lowercase snake_case matching the dominant entity or action
the blueprint creates. Example: `signal_health.yaml` for a template-entity
blueprint that creates a sensor named "Cable Modem Signal Health."

**Blueprint metadata fields:** HA's blueprint schema requires only `name`
and `domain`. `description`, `author`, `input`, and `homeassistant` (minimum
HA version) are optional. See the
[HA blueprint schema documentation](https://www.home-assistant.io/docs/blueprint/schema/)
for the authoritative list.

CMM blueprint contributions should populate, at minimum:

| Field | Purpose |
|-------|---------|
| `name` (required by HA) | Human-readable name shown in HA's blueprint picker |
| `domain` (required by HA) | One of `automation`, `script`, `template`; matches the subdirectory |
| `description` (recommended) | One or two sentences explaining what the blueprint does and which entities it depends on |
| `author` (recommended) | Original author credit |
| `input` | Each user-configurable parameter, with `name`, `description`, and `selector` |

---

## User Flow

1. User finds the blueprint URL via CMM docs or community post. The canonical
   form is:

   ```text
   https://github.com/solentlabs/cable_modem_monitor/raw/main/docs/examples/blueprints/<type>/<name>.yaml
   ```

2. User opens Home Assistant: Settings → Automations & Scenes → Blueprints →
   Import Blueprint.
3. User pastes the URL, clicks Preview, saves.
4. The blueprint becomes available for instantiation. HA stores imported
   blueprints under `<config>/blueprints/<domain>/<source>/<filename>.yaml`,
   where `<source>` is derived from the import URL; the exact mapping for
   GitHub-org URLs is determined by HA at import time. See
   [Using blueprints](https://www.home-assistant.io/docs/automation/using_blueprints/).
5. User instantiates the blueprint:
   - **Automation / Script blueprints**: Settings → Automations & Scenes →
     Blueprints → select the blueprint → Create.
   - **Template blueprints**: no UI instantiation path exists. Add a
     `use_blueprint:` block to `configuration.yaml` referencing the blueprint
     path and supplying input values, then reload template entities. HA 2024.11
     release notes describe template blueprints as "an advanced feature only
     available using manual YAML configuration."
6. The created entity or automation behaves per the blueprint's logic with
   user-owned values.

**Updates:** HA does not auto-propagate blueprint updates. When a blueprint
file in this repo changes, users re-import to pick up the new version. This
is consistent with HA's blueprint mechanism for all URL-imported sources.

---

## Contribution Flow

1. Contributor opens a PR adding `docs/examples/blueprints/<type>/<name>.yaml`.
2. PR includes:
   - The blueprint YAML
   - Attribution to the original author if migrating from elsewhere
     (forum post, discussion, third-party blueprint)
   - A brief description in the PR body explaining the use case and the
     entities or actions the blueprint depends on
3. Maintainer review covers:
   - YAML is well-formed and importable by HA
   - HA-required fields (`name`, `domain`) are present; recommended fields per the Structure section are populated
   - Inputs are documented and use appropriate selectors
   - Attribution is correct
   - File name and location follow this spec
4. Maintainer review does NOT cover:
   - Threshold values, opinionated defaults, or any subjective content
   - Compatibility with hypothetical modems not represented in the
     contributor's setup
   - Stewardship of content correctness over time

The recipe contributor is the steward of their blueprint's accuracy. Issues
filed against a specific blueprint's content (wrong threshold defaults,
unexpected behavior on a specific modem) are routed to the steward, not
absorbed by maintainer review of the integration.

---

## Growth Path

Triggers for evolving toward HACS template-category distribution:

| Trigger | Action |
|---------|--------|
| Blueprint count grows past ~5 with diverse stewardship | Evaluate moving to a separate HACS-recognized repo with `hacs.json` declaring `category: template`. Repo name to be decided at that point. |
| Discoverability via HACS UI becomes a stated user need (documented requests, not assumed) | Migrate at that point |
| HACS default-store inclusion becomes desired | Apply via HACS submission process |

**Migration cost when triggered:** separate repo, `hacs.json` metadata file,
one-time documented URL change. Users with existing blueprint installs
continue working with their already-imported version until they re-import
from the new location.

Until any of these triggers is met, URL import from `docs/examples/blueprints/`
remains the canonical path. Following CLAUDE.md § Code Discipline, the
project does not pre-build HACS infrastructure ahead of documented need.

---

## Tradeoffs

| Aspect | URL import via docs/examples/ (chosen) | HACS template category (future) |
|--------|----------------------------------------|----------------------------------|
| Setup cost | Write the blueprint YAML | Separate repo, hacs.json, possibly default-store submission |
| User discoverability | Lower (user needs the URL) | Higher (browsable in HACS UI) |
| Install flow | Paste URL, preview, save | One click in HACS UI |
| Update propagation | Manual re-import by user | HACS-managed |
| Maintainer review burden | Curation only (well-formedness, attribution) | Same plus HACS metadata maintenance |
| Migration cost from current to future | N/A | Bounded: move files, add metadata, document URL change |

The chosen path trades user-side discoverability for project-side
setup-cost avoidance. The trade is justified by the current single-blueprint
candidate. The growth path preserves the option to revisit when volume or
demand changes.

---

## Out of Scope

This spec does NOT address:

- **Static Lovelace dashboards via HACS dashboard category.** Separate
  concern with no documented current demand. The existing
  `cable_modem_monitor.generate_dashboard` service (implemented in
  [`dev_tools.py`](../dev_tools.py), registered in
  [`services.py`](../services.py)) covers most dashboard use cases via the
  copy-paste developer-tool pattern.
- **Dashboard generator productization or JS dashboard strategies.**
  Separate concern, documented in a separate forthcoming spec.
- **Custom Lovelace cards.** General HA frontend components, not
  modem-specific.
- **HACS distribution of blueprints.** Deferred until the growth triggers
  in the Growth Path section are met.
- **Auto-population of bundled blueprints inside the integration directory.**
  HA Core's `async_populate()` mechanism (verified at
  `homeassistant/components/blueprint/models.py`) copies integration-shipped
  blueprints to user config on first setup for HA Core integrations. Whether
  this mechanism works the same way for custom integrations under
  `custom_components/` is unverified. This spec does not rely on it.
- **User-interface concerns about entity volume per modem.** Not addressed
  in this spec.

---

## References

| Source | Purpose |
|--------|---------|
| [ENTITY_MODEL_SPEC.md](ENTITY_MODEL_SPEC.md) (peer doc) | "integration does not create entities for every possible use case" |
| [CLAUDE.md](../../../CLAUDE.md) § Decision Discipline | "Know what you know — don't speculate" |
| [CLAUDE.md](../../../CLAUDE.md) § Code Discipline | "No infrastructure for hypothetical recurrence" |
| [ARCHITECTURE_DECISIONS.md](../../../packages/cable_modem_monitor_core/docs/ARCHITECTURE_DECISIONS.md) § "Generic timing, not per-modem knobs" | Rationale for rejecting per-modem subjective tuning |
| Project memory `feedback_no_inline_json_in_tests` | `docs/examples/*.yaml` as canonical location for example YAML |
| [`.github/workflows/release.yml`](../../../.github/workflows/release.yml) lines 80-88 | `docs/*` excluded from HACS integration zip |
| [HA Blueprint documentation](https://www.home-assistant.io/docs/blueprint/) | URL import mechanism, supported blueprint types |
| [HA Core `blueprint/models.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/blueprint/models.py) | Blueprint loader source code; verified URL-import behavior |
| [HA Core `automation/blueprints/`](https://github.com/home-assistant/core/tree/dev/homeassistant/components/automation/blueprints) | Precedent for subdirectory-by-type organization |
| Issue [#144](https://github.com/solentlabs/cable_modem_monitor/issues/144) | Feature request that motivated this spec |
| Discussion [#161](https://github.com/solentlabs/cable_modem_monitor/discussions/161) | First concrete blueprint candidate (signal_health) |
