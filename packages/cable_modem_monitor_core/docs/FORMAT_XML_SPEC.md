# XML Format Specification

> Parent spec: [PARSING_SPEC.md](PARSING_SPEC.md) — common concepts, output contract, channel type detection

The XMLParser extracts channel data from XML element children via tag
name navigation. This document covers schema, properties, and
extraction algorithms for XML-format parser configurations.

## Contents

| Section | Description |
| ------- | ----------- |
| [XMLParser](#xmlparser) | Overview and multi-table concatenation model |
| [Channel Section Schema](#channel-section-schema) | `parser.yaml` schema for downstream/upstream channel tables |
| [Section-Level Properties](#section-level-properties) | Top-level section fields |
| [Table-Level Properties](#table-level-properties) | Per-table fields within `tables` |
| [System Info Schema](#system-info-schema) | `parser.yaml` schema for system info sources |
| [System Info Properties](#system-info-properties) | Field reference for system info sources |
| [Extraction Algorithm (Channels)](#extraction-algorithm-channels) | Step-by-step channel extraction logic |
| [Extraction Algorithm (System Info)](#extraction-algorithm-system-info) | Step-by-step system info extraction logic |

## XMLParser

Extracts channel data from XML responses. The resource dict value is
a `defusedxml.ElementTree.Element` (the parsed XML root). Each section
contains one or more **tables**, each fetching from a different XML
resource. Results are concatenated in table order.

This supports modems that serve QAM and OFDM channels from separate
API calls (e.g., DOCSIS 3.1 modems with `fun=10` for DS QAM and
`fun=9` for DS OFDM).

## Channel Section Schema

**parser.yaml schema (channel section):**

```yaml
downstream:
  format: xml
  tables:
    # Table 1: DS QAM channels from fun=10
    - resource: "10"
      root_element: downstream_table
      child_element: downstream
      columns:
        - source: chid
          field: channel_id
          type: integer
        - source: freq
          field: frequency
          type: frequency
        - source: pow
          field: power
          type: float
        - source: snr
          field: snr
          type: float
        - source: mod
          field: modulation
          type: string
        - source: PreRs
          field: corrected
          type: integer
        - source: PostRs
          field: uncorrected
          type: integer
      channel_type:
        field: modulation
        map:
          "256qam": "qam"
          "OFDM": "ofdm"
      lock_status:
        all_of:
          - IsQamLocked
          - IsFECLocked
          - IsMpegLocked
      filter:
        frequency:
          not: 0
    # Table 2: DS OFDM channels from fun=9
    - resource: "9"
      root_element: downstream_table
      child_element: downstream
      columns:
        - source: dsid
          field: channel_id
          type: integer
        - source: plcFrequency
          field: frequency
          type: frequency
        - source: PLCPower
          field: power
          type: float
      channel_type:
        fixed: "ofdm"
      lock_status:
        all_of:
          - ofdmIsLocked

upstream:
  format: xml
  tables:
    - resource: "11"
      root_element: upstream_table
      child_element: upstream
      columns:
        - source: usid
          field: channel_id
          type: integer
        - source: srate
          field: symbol_rate
          type: float
          scale: 1000             # Msym/s → ksym/s
      channel_type:
        field: modulation
        map:
          "64qam": "qam"
          "OFDMA": "ofdma"
      fixed_fields:
        lock_status: "locked"     # presence in table implies lock
      filter:
        frequency:
          not: 0
```

## Section-Level Properties

| Property | Type | Required | Description |
|----------|------|:--------:|-------------|
| `format` | string | yes | `"xml"` |
| `tables` | list | yes | One or more table definitions (min 1). Results concatenated in order. |

## Table-Level Properties

Each item in `tables`:

| Property | Type | Required | Description |
|----------|------|:--------:|-------------|
| `resource` | string | yes | Key in the resource dict (for `cbn`, the `fun` parameter value) |
| `root_element` | string | yes | Tag name of the root XML element (e.g., `"downstream_table"`) |
| `child_element` | string | yes | Tag name of repeated child elements (e.g., `"downstream"`) |
| `columns` | list | yes | Mappings from XML sub-element tags to canonical field names |
| `columns[].source` | string | yes | XML child element tag name (e.g., `"freq"`, `"pow"`) |
| `columns[].field` | string | yes | Canonical field name (from field registry) |
| `columns[].type` | string | yes | Target type: `integer`, `float`, `string`, `frequency`, `boolean`, `lock_status`, `uptime` |
| `columns[].scale` | number | no | Multiplier applied after type conversion (e.g., `1000` for Msym/s → ksym/s). Whole-number results cast to int. |
| `channel_type` | object | no | Fixed or field-derived channel type assignment |
| `lock_status` | object | no | `all_of`: list of sub-element tag names whose boolean values are ANDed — all true → `"locked"`, otherwise `"not_locked"` |
| `fixed_fields` | map | no | Static field values for every channel. Applied after column extraction and channel_type. |
| `filter` | map | no | Field-based row filtering (same as HTML table filter) |

## System Info Schema

**parser.yaml schema (system info source):**

```yaml
system_info:
  sources:
    - format: xml
      resource: "2"
      root_element: cm_system_info
      fields:
        - source: cm_hardware_version
          field: hardware_version
        - source: cm_system_uptime
          field: system_uptime
```

## System Info Properties

| Property | Type | Required | Description |
|----------|------|:--------:|-------------|
| `format` | string | yes | `"xml"` |
| `resource` | string | yes | Key in the resource dict |
| `root_element` | string | yes | Tag name of the root XML element containing the fields |
| `fields` | list | yes | Mappings from XML sub-element tags to system_info field names |
| `fields[].source` | string | yes | XML element tag name |
| `fields[].field` | string | yes | Canonical field name |
| `fields[].map` | dict | no | Value mapping (exact match, applied before type conversion) |

## Extraction Algorithm (Channels)

1. For each table in `tables` (in order):
   a. Get `Element` from resource dict by table's `resource` key
   b. Find the root element by tag name (`root_element`). If the
      parsed root IS the target element, use it directly; otherwise
      search children.
   c. Iterate child elements matching `child_element` tag name
   d. For each child: read `.text` of sub-elements named by each
      column's `source` field
   e. Apply type conversion (`integer`, `float`, `string`, etc.)
   f. If `scale` is set on a column, multiply the converted value;
      cast whole-number floats to int
   g. Apply `channel_type` (fixed or field-derived mapping)
   h. If `lock_status.all_of` is set, AND the boolean values of the
      listed sub-elements — `"locked"` if all true, `"not_locked"`
      otherwise
   i. Apply `fixed_fields` — static values override/fill fields on
      every channel
   j. Apply `filter` — exclude channels by field value
2. Concatenate channels from all tables in order
3. Auto-assign `channel_number` from 1-based element index when not
   already mapped by parser.yaml (see
   [CHANNEL_IDENTIFICATION_SPEC.md](CHANNEL_IDENTIFICATION_SPEC.md) §10)

## Extraction Algorithm (System Info)

1. Get `Element` from resource dict by `resource` key
2. Find the root element by tag name (`root_element`)
3. For each field mapping: find sub-element by `source` tag name,
   read `.text` as the field value
