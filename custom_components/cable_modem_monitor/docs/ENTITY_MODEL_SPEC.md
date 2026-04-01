# Entity Model Specification

How the HA integration maps Core output to Home Assistant entities.

Core produces `ModemData` (channels + system_info) and health-check
results (latency + status). This spec defines how those map to HA
platforms, entities, attributes, and availability.

**Design principle:** The integration exposes what the modem provides,
in standard HA format. Users derive additional entities (template
sensors, binary_sensors) from attributes as needed. The integration
does not create entities for every possible use case.

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
parser output → no entity created. Not created in fallback mode.

### Health Sensors

| Entity | unique_id suffix | State | device_class | state_class | Unit | Condition |
|--------|-----------------|-------|--------------|-------------|------|-----------|
| Ping Latency | `_ping_latency` | float | — | MEASUREMENT | ms | `supports_icmp = True` |
| HTTP Latency | `_http_latency` | float | — | MEASUREMENT | ms | Always created |

### Per-Channel Downstream Sensors

One entity per metric per channel. Created dynamically from
coordinator data.

| Entity | unique_id suffix | Unit | device_class | state_class | Condition |
|--------|-----------------|------|--------------|-------------|-----------|
| Power | `_ds_{type}_ch_{id}_power` | dBmV | — | MEASUREMENT | Always |
| SNR | `_ds_{type}_ch_{id}_snr` | dB | — | MEASUREMENT | Always |
| Frequency | `_ds_{type}_ch_{id}_frequency` | Hz | FREQUENCY | MEASUREMENT | If present |
| Corrected | `_ds_{type}_ch_{id}_corrected` | — | — | TOTAL_INCREASING | If present |
| Uncorrected | `_ds_{type}_ch_{id}_uncorrected` | — | — | TOTAL_INCREASING | If present |

**Attributes on every DS channel sensor:** `channel_id`, `channel_type`.
Additional Tier 2/3 fields from parser output (lock_status, modulation,
etc.) flow as attributes.

### Per-Channel Upstream Sensors

| Entity | unique_id suffix | Unit | device_class | state_class | Condition |
|--------|-----------------|------|--------------|-------------|-----------|
| Power | `_us_{type}_ch_{id}_power` | dBmV | — | MEASUREMENT | Always |
| Frequency | `_us_{type}_ch_{id}_frequency` | Hz | FREQUENCY | MEASUREMENT | If present |

**Attributes on every US channel sensor:** `channel_id`, `channel_type`.
Additional fields (symbol_rate, lock_status, modulation, ranging_status,
etc.) flow as attributes.

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
backoff, refresh health probes, then trigger a data poll. The
`request_health_check` service triggers only the health probe. Both
services accept a device target for multi-modem setups. See
HA_ADAPTER_SPEC.md § Services for details and automation examples.

### Status Sensor

The Status sensor composes three inputs into a single display state
via a priority cascade. The sensor contains no business logic — it is
a pure lookup over values derived upstream.

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

See [RUNTIME_POLLING_SPEC.md](../../../packages/cable_modem_monitor_core/docs/RUNTIME_POLLING_SPEC.md#status-derivation)
for the derivation rules that produce the three input values.

---

## Channel Identity

Channels are keyed by `(channel_type, channel_id)`:
- **Downstream types:** `qam`, `ofdm`
- **Upstream types:** `atdma`, `ofdma`

The DataUpdateCoordinator normalizes raw parser output into indexed dicts
(`_downstream_by_id`, `_upstream_by_id`) for O(1) lookup. Channels
are sorted by frequency within each type and assigned a 1-based
`_index`.

Entities bind to whatever channels the modem currently reports. If the
modem reboots and bonds to different channels, the entities reflect the
new channels on the next poll. Channel IDs are stable across polls for
a given modem session but may change after reboot — this is how DOCSIS
channel bonding works.

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
| `ActionFactory` (restart support) | Button entities |
| Channel normalization (`channel_type`, `channel_id`) | Entity unique_id incorporates channel key |

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
| Modem unreachable at startup | deferred³ | available¹ | available |
| Parse error | unavailable | available¹ | available |
| Fallback mode (unknown modem) | not created² | available | available |
| Field not parsed by this modem | never created | n/a | n/a |

¹ Health sensors remain available when the modem is unreachable or
produces parse errors — they report the failure state itself (latency
= None, status = Unresponsive/Parser Error).

² In fallback mode, only Status, Modem Info, and health sensors are
created. No channel sensors, no system sensors.

³ When the modem is unreachable at HA startup, data-dependent entities
(channels, system metrics, LAN stats) are deferred until the first
successful poll. Status, Info, and Health sensors are created
immediately and remain available during the outage. See
HA_ADAPTER_SPEC § Deferred Entity Creation.

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

```
{entry_id}_cable_modem_{suffix}
```

**System sensors:** suffix is the sensor name (e.g., `_status`,
`_software_version`, `_total_corrected`).

**Channel sensors:**
```
{entry_id}_cable_modem_{ds|us}_{channel_type}_ch_{channel_id}_{field}
```

Example: `abc123_cable_modem_ds_ofdm_ch_159_power`

**LAN sensors:**
```
{entry_id}_cable_modem_lan_{interface}_{metric}
```

**Buttons:**
```
{entry_id}_{button_name}
```

### Entity Names

All sensor classes set `_attr_has_entity_name = True`. HA generates
the full entity name from `{device_name} {sensor_name}`.

Channel sensor names include type and ID:
`"DS {TYPE} Ch {ID} {Metric}"` (e.g., "DS OFDM Ch 159 Power").
