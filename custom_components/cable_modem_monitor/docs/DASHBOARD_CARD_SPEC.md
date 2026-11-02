# Dashboard Card Specification

The Cable Modem card: a custom Lovelace card the integration ships, so a
new user adds it from **Add card**, sets it up in a form, and writes no
YAML.

**Design principles:**

- The card renders; Python decides. The layout rules live in one place,
  the dashboard card builder, shared with `generate_dashboard_card`
- The card lives behind one subfolder boundary, `card/`, and the rest of
  the integration touches it through a single registration call
- The card is additive: no card failure, and no missing frontend, may
  affect modem monitoring or its configuration
- Core is unchanged. Capabilities stay implicit (ARCHITECTURE_DECISIONS.md
  § Capabilities are implicit from parser output), and the layout is HA
  presentation that belongs in the adapter
- The card's config keys are a persisted public contract

**Related specs:**

- `HA_ADAPTER_SPEC.md` § Services — `generate_dashboard_card`, the
  builder's other consumer
- `HA_ADAPTER_SPEC.md` § Notifications — the onboarding pointer to this card
- `ENTITY_MODEL_SPEC.md` — which entities exist
- `BLUEPRINT_DISTRIBUTION_SPEC.md` — lists custom cards as out of scope

---

## Contents

| Section | What it covers |
|---------|----------------|
| [Boundary](#boundary) | Subfolder layout and the one allowed coupling |
| [Layout Builder](#layout-builder) | The shared dict builder behind the action and the card |
| [Backend Access](#backend-access) | The websocket command behind the card |
| [Frontend Registration](#frontend-registration) | How the module is served and loaded |
| [Card Behavior](#card-behavior) | States, refresh, editor |
| [Config Contract](#config-contract) | Persisted keys and their stability |
| [Notifications](#notifications) | Onboarding pointer and language |
| [Verification](#verification) | What is tested and what is checked on a harness |
| [Out of Scope](#out-of-scope) | What this spec does not cover |

---

## Boundary

```text
custom_components/cable_modem_monitor/
├── card/
│   ├── __init__.py        # async_register_card(hass): the only entry point
│   ├── commands.py        # the websocket command
│   └── frontend/
│       └── cable-modem-card.js   # card element + editor, no build step
├── dev_tools.py           # layout builder (imported by card/, never the reverse)
└── __init__.py            # async_setup calls async_register_card(hass)
```

- `card/` imports the layout builder from `dev_tools.py`. Nothing in
  `dev_tools.py`, `services.py` or the platforms imports from `card/`.
- `async_setup` in `__init__.py` makes the one call that wires the card
  in. Removing `card/` and that call removes the feature.
- The folder ships in the existing HACS zip, so no packaging change.
- The card ships as one hand-written ES module with no bundler or
  dependencies; a build step is out until the module needs one.

---

## Layout Builder

The builders in `dev_tools.py` emit Lovelace card configs as dicts. The
action serialises the dict once with `yaml.safe_dump`; the card command
returns the dict as JSON.

| Rule | Detail |
|------|--------|
| One builder | `build_card_config(hass, options) -> dict` resolves the modem and returns the `vertical-stack` card. `generate_dashboard_card` serialises it; the websocket command returns it |
| Same options | Both validate against `SERVICE_GENERATE_DASHBOARD_CARD_SCHEMA`, so the option list has one definition |
| Same errors | An unresolvable modem or one with no data raises `ServiceValidationError`; the command sends its message as an error |
| Entity IDs | Resolved from the entity registry by unique ID, never from the entity prefix (HA_ADAPTER_SPEC.md § Services) |

---

## Backend Access

The card calls one read-only websocket command,
`cable_modem_monitor/card_config`, through `hass.callWS`. Its optional
`options` field is validated by `SERVICE_GENERATE_DASHBOARD_CARD_SCHEMA`
(defaults included) and passed to the builder. The result is
`{"card": <dict>, "watch": [<entity id>, ...]}`, where `watch` holds
the downstream and upstream channel-count sensors; a modem that cannot be resolved or has no data sends
the error code `card_unavailable` with the builder's message.

The websocket API is the channel for frontend-only data, so the user-facing
action keeps its single `{"yaml": ...}` response and its own contract.
The command is registered in `async_setup`, open to any authenticated
user, and exposes no more than the entities the user can already see.
Schemas use `import voluptuous as vol`, as `services.py` and
`config_flow.py` do. HA aliases `voluptuous` to its own validation
library for custom integrations (`homeassistant/__init__.py`), so the
import resolves to the library HA itself uses on every supported version.

---------|-------|--------|
| `cable_modem_monitor/card_config` | the generator options plus optional `device_id` | `{"card": <dict>}` |
| `cable_modem_monitor/card_modems` | none | `[{"device_id": ..., "name": ...}]` for loaded entries |

`card_modems` feeds the editor's modem picker. With one modem the picker
is hidden and `device_id` is omitted from the saved config.

---

## Frontend Registration

`async_register_card` does two things, once, in `async_setup`:

1. `hass.http.async_register_static_paths` serves `card/frontend/` at
   `/cable_modem_monitor/card`.
2. `frontend.add_extra_js_url` loads `/cable_modem_monitor/card/cable-modem-card.js?v=<manifest version>`.

`manifest.json` lists `frontend`, `http` and `websocket_api` under
`after_dependencies`, not `dependencies`, so a headless install without
them still loads. Registration is skipped, with a debug log, when
`frontend` or `http` is not loaded. Any exception during registration is
caught and logged as a warning; it never reaches `async_setup`.

The module defines its custom element and fills `window.customCards` at
the top level, before any `await`. HA waits up to two seconds for an
undefined `custom:` element and rebuilds when it appears
(`create-element-base.ts`), so a small module that defines immediately
stays inside that window. `add_extra_js_url` is used rather than a
Lovelace resource: it works in storage and YAML mode alike and touches no
Lovelace internals. The URL is re-added on every start because HA keeps
it in memory only.

---

## Card Behavior

- **Rendering.** The card awaits `window.loadCardHelpers()`, fetches
  `card_config`, builds the stack with `createCardElement`, and sets
  `hass` on it on every update.
- **Picker.** `window.customCards` registers `cable-modem-card` with a
  name, description and `documentationURL`. `getStubConfig` returns `{}`:
  the defaults are the generator's.
- **States.** Loading, "no modem configured", and "modem offline" (the
  command's error text) each render as a message inside `ha-card`. No
  state throws.
- **Refresh.** The card re-fetches when its config changes and when the
  state of any `watch` entity changes, since the channel counts are what
  change the layout.
- **Editor.** `getConfigForm` returns the form schema: a device selector
  limited to this integration (as in `services.yaml`), the content
  toggles, graph hours and short titles. HA renders it, so the card
  depends on no `ha-*` element. `assertConfig` throws when a YAML-only key
  is present, which keeps the visual editor off for that card so a form
  edit cannot drop the key. The form is accepted only if the harness
  check below passes; one card author reports `getConfigForm` unreliable
  for custom cards (air-quality-card v2.6.1).
- **YAML-only keys.** `channel_label`, `channel_grouping` and
  `status_card_exclude` are accepted in the card YAML and absent from the
  editor, matching the action's form (HA_ADAPTER_SPEC.md § Services).

---

## Config Contract

```yaml
type: custom:cable-modem-card
device_id: <optional>
include_status_card: true
include_downstream_power: true
...        # the generator options, same names, same defaults
graph_hours: 24
short_titles: true
```

- Keys are the generator's option names, so one name has one meaning
  across the action and the card.
- Dashboards persist these keys. A rename or removal is a breaking
  change: `setConfig` must accept the old key and map it, and the change
  needs a CHANGELOG entry.
- `setConfig` throws on an invalid value, as the card API requires.

---

## Notifications

The onboarding notification points to **Edit → Add card → Cable Modem**
instead of the action. Persistent notifications stay English, like services and
entity names (TRANSLATION_GUIDE.md § Translated Scope Is Deliberately
Limited).

---

## Verification

Tested in the suite:

- Builder output serialises to the same YAML the action returned before
  the dict refactor.
- The action's `card` response key: success, no modem, offline, multiple
  modems, invalid options.
- `async_register_card` registers the static path and the JS URL once.
- Every key in the form schema validates against the generator schema.

Checked by hand on the local harness (`ha-cable-modem-test`), because the
repo has no JS test tooling and the module holds no layout logic:

- Cold restart: the card renders without a reload.
- The picker lists the card; the form renders, saves, and the card
  updates.
- Offline modem and channel-count change refresh the card.
- Helper behavior on the 2025.1 floor.

---

## Out of Scope

- A companion-repo or HACS dashboard distribution of the card
- Cosmetic per-graph customisation in the editor (edit the YAML, or paste
  the action's output)
- Interpretation content such as signal-health grades
  (BLUEPRINT_DISTRIBUTION_SPEC.md)
