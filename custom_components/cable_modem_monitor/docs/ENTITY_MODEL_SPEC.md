# Entity Model Specification

How the HA integration maps Core output to Home Assistant entities.

Core produces `ModemData` (channels + system_info) and health-check
results (latency + status). This spec defines how those map to HA
platforms, entities, attributes, and availability.

**Design principle:** The integration exposes what the modem provides,
in standard HA format. Users derive additional entities (template
sensors, binary_sensors) from attributes as needed. The integration
does not create entities for every possible use case.

**Exception:** The adapter may add a small number of curated,
high-value interpretation entities when they summarize normalized modem
telemetry in a reusable, automation-friendly way and would otherwise
force users to rebuild the same logic in templates. Signal Health is
the example of this exception.

---

## Contents

| Section | What it covers |
|---------|----------------|
| [Platforms](#platforms) | Which HA platforms are used and why |
| [Entity Catalog](#entity-catalog) | Every entity the integration creates |
| [Channel Identity](#channel-identity) | How channels are keyed and indexed |
| [Field Pass-Through](#field-pass-through) | How parser fields flow to HA |
| [Core vs HA Boundary](#core-vs-ha-boundary) | What lives where |
| [Device Model](#device-model) | HA device registration and naming |
| [Availability](#availability) | When entities are available/unavailable |
| [Entity Naming](#entity-naming) | unique_id and entity_id patterns |

---

## Platforms

| Platform | Purpose |
|----------|---------|
| `sensor` | All modem data — metrics, counters, text, timestamps |
| `button` | Actions (restart, update, reset) |

No `binary_sensor`, `select`, `switch`, `number`. Modems are
read-only data sources. Boolean fields (`lock_status`) and enum
fields (`network_access`) are exposed as attributes on sensor
entities. Users create template entities from attributes if needed.

---

## Entity Catalog

### System Sensors

These are created when the corresponding data appears in parser
output (some gated by config).

| Entity | unique_id suffix | State | device_class | state_class | Unit | Attributes |
|--------|-----------------|-------|--------------|-------------|------|------------|
| Status | `_status` | display¹ | — | — | — | `connection_status`, `health_status`, `docsis_status`, `diagnosis` |
| Modem Info | `_info` | detected model | — | — | — | `manufacturer`, `model`, `release_date`, `docsis_version`, `status` (from Core's `ModemIdentity`) |
| Software Version | `_software_version` | string | — | — | — | — |
| System Uptime | `_system_uptime` | string | — | — | — | — |
| Last Boot Time | `_last_boot_time` | datetime | TIMESTAMP | — | — | — |
| DS Channel Count | `_downstream_channel_count` | int | — | MEASUREMENT | — | From `system_info` — native or coordinator-computed² |
| US Channel Count | `_upstream_channel_count` | int | — | MEASUREMENT | — | From `system_info` — native or coordinator-computed² |
| Total Corrected | `_total_corrected` | int | — | TOTAL_INCREASING | — | From `system_info` — native or coordinator-computed² |
| Total Uncorrected | `_total_uncorrected` | int | — | TOTAL_INCREASING | — | From `system_info` — native or coordinator-computed² |
| System Info Field³ | `_{field}` | pass-through | — | — | — | Dynamic per-field sensor for non-consumed system_info fields |

¹ See [Status Sensor](#status-sensor) for the priority cascade that
produces the display state.

² Channel counts and error totals appear in `modem_data.system_info`.

³ Dynamic sensor created for each `system_info` field not consumed by
a dedicated sensor class above. One `SystemInfoFieldSensor` class
handles all dynamic fields, parameterized by field name. Created only
when the field is present in parser output. See § Field Pass-Through.
Modems with native values have them mapped in parser.yaml. Modems
without native values declare derivation rules in parser.yaml's
`aggregate` section — the parser coordinator computes them from
channel data. Channel counts (`len(channels)`) are always computed
by the parser coordinator if not natively mapped. Consumers read from one
place regardless of source. See
[PARSING_SPEC.md](../../../packages/cable_modem_monitor_core/docs/PARSING_SPEC.md#aggregate-derived-system_info-fields).

**Implicit capabilities:** Capabilities are not declared — they are
implicit from parser.yaml mappings (see
[PARSING_SPEC.md](../../../packages/cable_modem_monitor_core/docs/PARSING_SPEC.md#capabilities-are-implicit)).
If parser.yaml maps `system_info.software_version`, the Software
Version sensor exists. If parser.yaml has a `downstream` section,
downstream channel sensors and channel counts exist. No data in
parser output → no entity created.

### Health Sensors

| Entity | unique_id suffix | State | device_class | state_class | Unit | Condition |
|--------|-----------------|-------|--------------|-------------|------|-----------|
| Ping Latency | `_ping_latency` | float | — | MEASUREMENT | ms | `supports_icmp = True` |
| TCP Latency | `_tcp_latency` | float | — | MEASUREMENT | ms | Health coordinator exists (HTTP probe enabled) |
| HTTP Latency | `_http_latency` | float | — | MEASUREMENT | ms | `supports_head = True` (HEAD-only — no GET fallback for bimodal-corrupted data) |

### Signal Health Sensor

The integration exposes this summary sensor:

| Entity | unique_id suffix | State | Condition | Notes |
|--------|-----------------|-------|-----------|-------|
| Signal Health | `_signal_health` | `good`, `fair`, `poor` | Always created as a top-level summary entity; unavailable only when current `modem_data` is absent | Summarizes RF health from normalized DOCSIS telemetry |

The Signal Health sensor is a curated interpretation entity, not a raw
modem field. Its purpose is to translate channel telemetry into one
actionable grade plus compact diagnostic context.

Its design constraints are:

- Core owns the grading rules and typed result models
- HA owns persistence of user-configurable thresholds in `entry.options`
- the entity remains available when only one metric is provisional
  (for example, first-poll error-rate baseline establishment)
- missing unsupported metrics are omitted from grading rather than
  replaced with modem-specific heuristics

See `CONFIG_FLOW_SPEC.md` for the options-flow shape and
`HA_ADAPTER_SPEC.md` for runtime and persistence expectations.

### Per-Channel Downstream Sensors

One entity per metric per channel. Entity creation and unique_id
format depend on the user's channel identity mode — see
[Channel Identity](#channel-identity).

**Position mode** (`channel_identity: "number"`):

| Entity | unique_id suffix | Unit | device_class | state_class | Condition |
|--------|-----------------|------|--------------|-------------|-----------|
| Power | `_ds_ch_{n}_power` | dBmV | — | MEASUREMENT | Always |
| SNR | `_ds_ch_{n}_snr` | dB | — | MEASUREMENT | Always |
| Frequency | `_ds_ch_{n}_frequency` | Hz | FREQUENCY | MEASUREMENT | If present |
| Corrected | `_ds_ch_{n}_corrected` | — | — | TOTAL_INCREASING | If present |
| Uncorrected | `_ds_ch_{n}_uncorrected` | — | — | TOTAL_INCREASING | If present |

**ID mode** (`channel_identity: "id"`):

| Entity | unique_id suffix | Unit | device_class | state_class | Condition |
|--------|-----------------|------|--------------|-------------|-----------|
| Power | `_ds_{type}_ch_{id}_power` | dBmV | — | MEASUREMENT | Always |
| SNR | `_ds_{type}_ch_{id}_snr` | dB | — | MEASUREMENT | Always |
| Frequency | `_ds_{type}_ch_{id}_frequency` | Hz | FREQUENCY | MEASUREMENT | If present |
| Corrected | `_ds_{type}_ch_{id}_corrected` | — | — | TOTAL_INCREASING | If present |
| Uncorrected | `_ds_{type}_ch_{id}_uncorrected` | — | — | TOTAL_INCREASING | If present |

**Attributes on every DS channel sensor:** `channel_number`,
`channel_id`, `channel_type`. Both identifiers are always present
regardless of mode. Additional Tier 2/3 fields from parser output
(lock_status, modulation, etc.) flow as attributes.

### Per-Channel Upstream Sensors

**Position mode** (`channel_identity: "number"`):

| Entity | unique_id suffix | Unit | device_class | state_class | Condition |
|--------|-----------------|------|--------------|-------------|-----------|
| Power | `_us_ch_{n}_power` | dBmV | — | MEASUREMENT | Always |
| Frequency | `_us_ch_{n}_frequency` | Hz | FREQUENCY | MEASUREMENT | If present |

**ID mode** (`channel_identity: "id"`):

| Entity | unique_id suffix | Unit | device_class | state_class | Condition |
|--------|-----------------|------|--------------|-------------|-----------|
| Power | `_us_{type}_ch_{id}_power` | dBmV | — | MEASUREMENT | Always |
| Frequency | `_us_{type}_ch_{id}_frequency` | Hz | FREQUENCY | MEASUREMENT | If present |

**Attributes on every US channel sensor:** `channel_number`,
`channel_id`, `channel_type`. Both identifiers are always present
regardless of mode. Additional fields (symbol_rate, lock_status,
modulation, ranging_status, etc.) flow as attributes.

### LAN Statistics Sensors

Created per network interface, 8 sensors each.

| Entity | unique_id suffix | Unit | device_class | state_class |
|--------|-----------------|------|--------------|-------------|
| Received Bytes | `_lan_{iface}_received_bytes` | B | DATA_SIZE | TOTAL_INCREASING |
| Received Packets | `_lan_{iface}_received_packets` | — | — | TOTAL_INCREASING |
| Received Errors | `_lan_{iface}_received_errors` | — | — | TOTAL_INCREASING |
| Received Drops | `_lan_{iface}_received_drops` | — | — | TOTAL_INCREASING |
| Transmitted Bytes | `_lan_{iface}_transmitted_bytes` | B | DATA_SIZE | TOTAL_INCREASING |
| Transmitted Packets | `_lan_{iface}_transmitted_packets` | — | — | TOTAL_INCREASING |
| Transmitted Errors | `_lan_{iface}_transmitted_errors` | — | — | TOTAL_INCREASING |
| Transmitted Drops | `_lan_{iface}_transmitted_drops` | — | — | TOTAL_INCREASING |

### Buttons

| Entity | unique_id suffix | entity_category | Availability |
|--------|-----------------|-----------------|--------------|
| Restart Modem | `_restart_button` | — | Only if `actions.restart` in modem.yaml |
| Update Modem Data | `_update_data_button` | — | Always |
| Reset Entities | `_reset_entities_button` | CONFIG | Always |

Restart Modem is only created when modem.yaml declares
`actions.restart`. The other two buttons are always created.

The Update Modem Data button and the `request_refresh` service share
the same logic (`async_request_modem_refresh`): reset connectivity
backoff, refresh health probes, then trigger a data poll. Both
short-circuit when a destructive operation holds the
`active_operation` mutex — the adapter runs its own post-operation
refresh, so a user-initiated refresh during that window is
unnecessary (see HA_ADAPTER_SPEC § Operation Mutex).

The Restart Modem and Reset Entities buttons acquire the mutex for
the duration of their work and refuse if the other is already
running. The `request_health_check` service triggers only the
health probe. All services accept a device target for multi-modem
setups. See HA_ADAPTER_SPEC.md § Services for details and automation
examples.

### Status Sensor

The Status sensor composes three inputs from the latest snapshot
into a single display state via a priority cascade. The sensor
contains no business logic — it is a pure lookup over values
derived upstream. It does **not** read recovery state; the snapshot
already tells the truth about what the modem is reporting, and
recovery windows only change polling cadence, not the snapshot's
meaning.

**Inputs** (pass-through as attributes):

| Attribute | Source | Values |
|-----------|--------|--------|
| `connection_status` | Orchestrator (pipeline outcome) | `online`, `no_signal`, `parser_issue`, `auth_failed`, `unreachable` |
| `health_status` | Health pipeline (probe results) | `responsive`, `unresponsive`, `icmp_blocked`, `degraded` |
| `docsis_status` | Orchestrator (normalized `lock_status`) | `operational`, `partial_lock`, `not_locked`, `unknown` |
| `diagnosis` | HA integration (derived from `health_status`) | Free text |

**Priority cascade** (most to least concerning):

| Priority | Condition | Display State |
|----------|-----------|---------------|
| 1 | `health_status == unresponsive` | Unresponsive |
| 2 | `connection_status == unreachable` | Unreachable |
| 3 | `connection_status == auth_failed` | Auth Failed |
| 4 | `health_status == degraded` | Degraded |
| 5 | `connection_status == parser_issue` | Parser Error |
| 6 | `connection_status == no_signal` | No Signal |
| 7 | `docsis_status == not_locked` | Not Locked |
| 8 | `docsis_status == partial_lock` | Partial Lock |
| 9 | `health_status == icmp_blocked` | ICMP Blocked |
| 10 | default | Operational |

There is no synthetic "Restarting…" label. During a recovery
window — whether triggered by a commanded restart, an observed
outage, or a reboot-signal match — the Status sensor reflects
whatever the modem is actually reporting: Unreachable while the
modem is down, Not Locked / Partial Lock while it's ranging,
Operational once it returns. The recovery window's effect is on
*polling cadence* (HA polls faster during the window; see
HA_ADAPTER_SPEC § Recovery Adapter), not on the sensor's value.

**Re-rendering:** the Status sensor re-renders on every coordinator
update — faster during recovery cadence, normal cadence otherwise.
It doesn't need to subscribe to any recovery signal; the
coordinator already drives the updates.

See [RUNTIME_POLLING_SPEC.md](../../../packages/cable_modem_monitor_core/docs/RUNTIME_POLLING_SPEC.md#status-derivation)
for the derivation rules that produce the three input values.

---

## Channel Identity

The user selects a channel identity mode at config time, stored in
`entry.data["channel_identity"]`. This is a setup-time choice —
identical in UX to the entity prefix setting. No conversion between
modes; changing requires deleting and re-adding the integration.

See
[CHANNEL_IDENTIFICATION_SPEC.md](../../../packages/cable_modem_monitor_core/docs/CHANNEL_IDENTIFICATION_SPEC.md)
for the full rationale.

### Identity modes

| Mode | Slot key | Entity example | Default |
|------|----------|----------------|---------|
| `number` | `channel_number` (modem's row position) | `sensor.cable_modem_ds_ch_1_power` | Yes (new installs) |
| `id` | `(channel_type, channel_id)` (CMTS assignment) | `sensor.cable_modem_ds_qam_ch_29_power` | No |

**Channel types:**

- **Downstream:** `qam`, `ofdm`
- **Upstream:** `atdma`, `ofdma`

### Mapping manager

The mapping manager translates Core's channel list into keyed entity
slots. It reads `channel_identity` from `entry.data` and builds
`_downstream_by_slot` and `_upstream_by_slot` dicts for O(1) lookup.

- **Position mode:** slots keyed by `channel_number` — all positions
  included. Unlocked channels return `None` metrics. Entity set is
  fixed at setup from the channel list length.
- **ID mode:** slots keyed by `(channel_type, channel_id)` — unlocked
  channels excluded (no valid key). Entity set is dynamic — entities
  are created from whatever channels the modem currently reports.

Sensors read from `_*_by_slot` for data and from
`entry.data["channel_identity"]` to select their entity ID format.

### Rebonding behavior

- **Position mode:** Entities survive reboots. Channel numbers come
  from the modem's own row positions. If the CMTS reassigns Channel
  IDs, `channel_id` attributes update but entity identity is
  unchanged.
- **ID mode:** Current behavior. Old entities show "Unknown," new
  channel IDs appear without entities. Reset Entities resolves it.

### Migration (existing installs)

`async_migrate_entry` runs once at startup when the config entry
version is V1: adds `channel_identity: "id"` to `entry.data` and
bumps the version. Pure metadata update — no entity rewrites.

---

## Field Pass-Through

All fields from parser output flow to HA. Channels and system_info use
different patterns:

- **Channel fields** that are not a sensor metric become attributes on
  the channel sensor (e.g., `modulation`, `lock_status`).
- **System info fields** that lack a dedicated sensor class become
  their own sensor entity via `SystemInfoFieldSensor`.

The integration does not decide which fields are "important enough"
for their own entity. It exposes everything the parser provides. Users
create template sensors/binary_sensors from attributes for their own
automations.

[FIELD_REGISTRY.md](../../../packages/cable_modem_monitor_core/docs/FIELD_REGISTRY.md)
defines field naming authority across three tiers (canonical, registered,
unregistered). Tiers govern naming validation, not HA entity type — the
sections below define how each data section maps to HA entities.

### Channel Field Pass-Through

| FIELD_REGISTRY Tier | HA Mapping | Examples |
|---------------------|-----------|----------|
| Tier 1 canonical, numeric | Own sensor entity (one per channel) | `power`, `snr`, `frequency`, `corrected`, `uncorrected` |
| Tier 1 canonical, string/enum | Attribute on channel sensor | `lock_status`, `modulation`, `channel_type` |
| Tier 2 registered | Attribute on channel sensor | `channel_width`, `ranging_status` |
| Tier 3 unregistered | Attribute on channel sensor | `t3_timeouts`, `security_type` |

All non-metric fields from the channel dict are exposed as
`extra_state_attributes` on the channel's primary sensor.

### System Info Pass-Through

System info fields use a consumed/dynamic pattern:

| Pattern | HA Entity | Fields |
|---------|-----------|--------|
| Consumed (dedicated class) | One sensor class per field | `software_version`, `system_uptime`, `downstream_channel_count`, `upstream_channel_count`, `total_corrected`, `total_uncorrected` |
| Dynamic (pass-through) | Generic `SystemInfoFieldSensor(field=key)` | Everything else in `system_info` |

**Consumed fields** are those with a dedicated sensor class in
`sensor.py` (see § Entity Catalog — System Sensors). They are listed
in `_CONSUMED_SYSTEM_INFO_FIELDS`:

- `software_version`, `system_uptime` — Tier 1 canonical, always
  from parser.yaml mappings
- `downstream_channel_count`, `upstream_channel_count` — always
  computed by the parser coordinator (`len(channels)`); native value from
  parser.yaml takes precedence if mapped
- `total_corrected`, `total_uncorrected` — declared in parser.yaml's
  `aggregate` section (scoped sums from channel data); native mapping
  takes precedence if the modem reports totals directly

The grouping is by HA entity ownership, not by FIELD_REGISTRY tier.

**Dynamic fields** are everything else. `_create_data_dependent_entities`
loops over `system_info` keys, skips consumed fields, and creates a
`SystemInfoFieldSensor` for each remaining key. Field presence gates
creation — no data, no sensor. Straight pass-through — no type
conversion or boolean mapping.

**Graduation:** When a dynamic field gets a dedicated sensor class, add
it to `_CONSUMED_SYSTEM_INFO_FIELDS`. The dynamic sensor for that field
stops being created. No entity migration — the dedicated class takes
over with its own unique_id.

---

## Core vs HA Boundary

| Core (platform-agnostic) | HA Integration |
|--------------------------|----------------|
| `ModemData` output (channels, system_info) | Sensor entities with HA metadata |
| `ModemIdentity` (manufacturer, model, docsis_version, release_date, status) | Modem Info sensor attributes (pass-through) |
| Field names, types, units | `device_class`, `state_class`, `unit_of_measurement` |
| Implicit capabilities (field present = capable) | Entity created if field present |
| Health check results (latency, reachability) | Health sensor entities |
| Signal-health evaluation over normalized telemetry | Signal Health sensor state, summaries, translations, and availability |
| `ActionFactory` (restart support) | Button entities |
| Channel normalization (`channel_number`, `channel_type`, `channel_id`) | Mapping manager builds slot maps; entity unique_id incorporates mode-dependent key |

Core owns the data model. HA owns the presentation. The HA adapter
passes `ModemIdentity` fields through to the Modem Info sensor — no
derivation, no URL construction, no string comparison.

---

## Device Model

### One Device Per Config Entry

Each config entry creates one HA device:

```python
DeviceInfo(
    identifiers={(DOMAIN, entry.entry_id)},
    name=device_name,
    manufacturer=detected_manufacturer,
    model=stripped_model,
    configuration_url=f"{protocol}://{host}",
)
```

**Device name is set on every entity's DeviceInfo**, not just in
`_update_device_registry`. This ensures HA generates correct
entity_ids at registration time (before the device registry update
runs).

### Entity Prefix

The user selects a naming strategy at config time:

| Prefix Setting | Device Name | Purpose |
|---------------|-------------|---------|
| `none` (Default) | "Cable Modem" | Single modem setups |
| `model` | "Cable Modem {model}" | Multi-modem by model |
| `ip` | "Cable Modem {host}" | Multi-modem by IP |

All options produce entity_ids prefixed with `cable_modem_`
(e.g., `sensor.cable_modem_status`). The `model` and `ip` options
add an extra disambiguator for multi-modem setups.

### Multi-Modem

`unique_id` always includes `entry_id` (UUID), so entities are always
globally unique regardless of prefix setting. With `prefix=none` and
two modems, HA auto-suffixes entity_ids (`_2`, `_3`, etc.). Recommend
`model` or `ip` prefix for multi-modem setups.

---

## Availability

| Scenario | Data sensors | Health sensors | Buttons |
|----------|-------------|----------------|---------|
| Normal operation | available | available | available |
| Coordinator update failed | unavailable | unavailable | available |
| Modem unreachable | unavailable | available¹ | available |
| Modem unreachable at startup | deferred² | available¹ | available |
| Parse error | unavailable | available¹ | available |
| Field not parsed by this modem | never created | n/a | n/a |

¹ Health sensors remain available when the modem is unreachable or
produces parse errors — they report the failure state itself (latency
= None, status = Unresponsive/Parser Error).

² When the modem is unreachable at HA startup, data-dependent entities
(channels, system metrics, LAN stats) are deferred until the first
successful poll. Status, Info, and Health sensors are created
immediately and remain available during the outage. A delayed
re-notification (1 second after creation) ensures deferred entities
receive their initial coordinator update, avoiding an "Unknown" state
window until the next scheduled poll. See HA_ADAPTER_SPEC § Deferred
Entity Creation.

### Sensor Availability Logic

`ModemSensorBase.available` returns `True` when:

- `coordinator.last_update_success` is `True`, AND
- modem status is in a reportable state (see `connection_status`
  values in the Status Sensor table above)

Health sensors (Ping, HTTP) have independent availability based on
whether the health check ran (`ping_success is not None`,
`http_success is not None`).

---

## Entity Naming

### unique_id Format

All unique_ids are prefixed with `{entry_id}_cable_modem_`:

```text
{entry_id}_cable_modem_{suffix}
```

**System sensors:** suffix is the sensor name (e.g., `_status`,
`_software_version`, `_total_corrected`).

**Channel sensors** (format depends on identity mode):

Position mode (`number`):

```text
{entry_id}_cable_modem_{ds|us}_ch_{channel_number}_{field}
```

Example: `abc123_cable_modem_ds_ch_1_power`

ID mode (`id`):

```text
{entry_id}_cable_modem_{ds|us}_{channel_type}_ch_{channel_id}_{field}
```

Example: `abc123_cable_modem_ds_ofdm_ch_159_power`

**LAN sensors:**

```text
{entry_id}_cable_modem_lan_{interface}_{metric}
```

**Buttons:**

```text
{entry_id}_{button_name}
```

### Entity Names

All sensor classes set `_attr_has_entity_name = True`. HA generates
the full entity name from `{device_name} {sensor_name}`.

Channel sensor names depend on identity mode:

- **Position mode:** `"{DIR} Ch {n} {Metric}"` — no channel type in
  the name. Positions are unique by definition and type-agnostic.

---

## Entity Translations And Icons

Platinum-quality entities must use Home Assistant's standard
translation and icon mechanisms rather than hardcoded UI strings where
the platform supports translation-driven behavior.

For new top-level curated entities such as Signal Health
sensor:

- add `translations/en.json` entries as the source of truth
- add best-effort matching entries to every shipped translation file
- use `translation_key` on the entity where appropriate
- add `icons.json` entries for state-based icons when the entity's
  state model benefits from icon translation

For the Signal Health sensor specifically:

- `en.json` must include the entity name and any user-facing option
  labels or descriptions
- the other shipped language files should receive best-effort matching
  entries in the same change
- `icons.json` should map `good`, `fair`, and `poor` to distinct icons

This requirement exists because a flagship summary entity is part of
the primary user experience, not an internal-only metric surface.
  Example: "DS Ch 1 Power".
- **ID mode:** `"{DIR} {TYPE} Ch {ID} {Metric}"` — channel type
  included for DOCSIS 3.1 disambiguation.
  Example: "DS OFDM Ch 159 Power".
