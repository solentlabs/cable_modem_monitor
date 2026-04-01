# Field Registry

Field names follow a three-tier system. This registry is the naming
authority for all fields that cross the parser → Core → HA boundary.

Core defines **Tier 1 canonical fields** — the fields Core validates
and uses for entity identity, health checks, and status derivation.
See [PARSING_SPEC.md](PARSING_SPEC.md#field-guarantees)
for canonical field definitions and guarantees.

This document owns **Tier 2 registered fields** — standardized names
for pass-through fields that multiple modems expose. Core maintains
this registry because it defines what fields are valid across the
parser → Core → HA boundary; the Catalog populates them.

---

## Tier 1 — Canonical Fields (defined by Core)

Core validates these. Parsers must use exactly these names.

| Section | Fields |
|---------|--------|
| downstream | `channel_id`, `frequency`, `power`, `snr`, `lock_status`, `modulation`, `channel_type`, `corrected`, `uncorrected` |
| upstream | `channel_id`, `frequency`, `power`, `lock_status`, `modulation`, `channel_type`, `symbol_rate` |
| system_info | `software_version`, `hardware_version`, `system_uptime`, `network_access` |

---

## Tier 2 — Registered Fields

Standardized names for pass-through fields that multiple modems expose.
Core does not use these, but the test harness validates that parsers
use the registered name when the data is semantically equivalent. This
prevents the same concept from appearing under different names across
modems (e.g., `chan_width` vs `channel_width` vs `bandwidth`).

```yaml
# field_registry.yaml
registered_fields:
  downstream:
    channel_width:
      type: integer
      unit: "Hz"
      description: "OFDM channel bandwidth"
    active_subcarriers:
      type: integer
      description: "Number of active OFDM subcarriers"
    fft_size:
      type: integer
      description: "FFT size for OFDM channel"
    profile_id:
      type: string
      description: "OFDM downstream profile ID"
  upstream:
    channel_width:
      type: integer
      unit: "Hz"
      description: "OFDMA channel bandwidth"
    ranging_status:
      type: string
      description: "Upstream ranging status"
  system_info:
    docsis_version:
      type: string
      description: "DOCSIS specification version"
    boot_status:
      type: string
      description: "DOCSIS boot sequence status"
    serial_number:
      type: string
      description: "Modem serial number"
    temperature:
      type: float
      unit: "°C"
      description: "Modem internal temperature"
```

### Graduation Criteria

A field graduates from unregistered to registered when 3+ modems
expose semantically equivalent data. The pull request adding the
registration also updates all existing parser.yaml files to use the
standardized name.

---

## Tier 3 — Unregistered Fields

Modem-specific pass-throughs with no registry entry. These follow
the naming rules below and flow to downstream attributes unchanged.
No validation beyond format.

Examples: `t3_timeouts`, `t4_timeouts`, `security_type`,
`provisioned_speed_down`, `provisioned_speed_up`.

---

## HA Entity Mapping

Tiers define naming authority — which fields Core validates and which
the registry standardizes. How each field becomes an HA entity is
determined by the data section it belongs to, not its tier:

- **Channel fields:** Tier 1 numeric fields (`power`, `snr`, etc.)
  become their own sensor entity. All other channel fields (any tier)
  become attributes on that channel's sensor.
- **System info fields:** Fields with a dedicated sensor class
  (currently Tier 1 canonical + aggregates) are consumed by that class.
  All remaining fields (any tier) become a dynamic
  `SystemInfoFieldSensor` entity.

See [ENTITY_MODEL_SPEC.md § Field Pass-Through](../../../custom_components/cable_modem_monitor/docs/ENTITY_MODEL_SPEC.md#field-pass-through)
for the full mapping rules.

---

## Naming Rules (all tiers)

- snake_case, lowercase, no abbreviations except industry-standard
  (`snr`, `fft`, `ofdm`)
- Units are always the base SI unit in the value — `frequency` is Hz,
  `power` is dBmV, `channel_width` is Hz — never scaled (no MHz, no kHz)
- Boolean fields use `is_` prefix: `is_bonded`, `is_primary`
- Status fields use `_status` suffix: `lock_status`, `ranging_status`
