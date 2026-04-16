# JSON Format Specification

> Parent spec: [PARSING_SPEC.md](PARSING_SPEC.md) --- common concepts, output contract, channel type detection

The JSONParser extracts channel data from JSON API responses using
field paths and array navigation. Modems that expose REST-style JSON
endpoints declare their structure in parser.yaml --- the parser walks
dot-notation paths to locate channel arrays, then maps keys to
canonical fields.

## Contents

| Section | What it covers |
|---------|----------------|
| [JSONParser](#jsonparser) | Flat form config, multi-array form, per-array resources, extraction algorithm |

## JSONParser

Extracts data from JSON API responses using path navigation and direct
key access.

```yaml
# parser.yaml --- JSON API with dot-notation path to channel array
downstream:
  format: json
  resource: "/rest/v1/cablemodem/downstream"
  array_path: "downstream.channels"
  fields:
    - key: "channelId"
      field: channel_id
      type: integer
    - key: "lockStatus"
      field: lock_status
      type: boolean
      truthy: true
    - key: "modulation"
      field: modulation
      type: string
    - key: "frequency"
      field: frequency
      type: integer
    - key: "power"
      field: power
      type: float
    - key: "rxMer"
      field: snr
      type: float
      fallback_key: "snr"
    - key: "correctedErrors"
      field: corrected
      type: integer
    - key: "uncorrectedErrors"
      field: uncorrected
      type: integer
    - key: "channelType"
      field: channel_type
      type: string
      map:
        "sc-qam": "qam"
        "ofdm": "ofdm"

upstream:
  format: json
  resource: "/rest/v1/cablemodem/upstream"
  array_path: "upstream.channels"
  fields:
    - key: "channelId"
      field: channel_id
      type: integer
    - key: "frequency"
      field: frequency
      type: integer
    - key: "power"
      field: power
      type: float
    - key: "symbolRate"
      field: symbol_rate
      type: integer
```

**Config fields (flat form):**

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `format` | string | yes | `json` --- selects `JSONParser` |
| `resource` | string | yes | URL path key in the resource dict |
| `array_path` | string | yes* | Dot-notation path to the channel array |
| `fields` | list | yes* | Key-to-field mappings within each JSON object |
| `fields[].key` | string | yes | JSON key name in the source object |
| `fields[].fallback_key` | string | no | Alternative key if primary is missing |
| `fields[].format` | string | no | Input format for types that require it (e.g., `seconds` for `uptime`). |
| `fields[].scale` | number | no | Multiplier applied after type conversion. Whole-number results cast to int. |
| `arrays` | list | yes* | Multi-array form (alternative to array_path/fields) |

\* Mutually exclusive: use either flat form (`array_path` + `fields`)
or multi-array form (`arrays`).

**Multi-array form** --- for modems with multiple channel arrays in one
response (e.g., QAM + OFDM in separate JSON arrays):

```yaml
downstream:
  format: json
  resource: "/api/status"
  arrays:
    - array_path: "docsis.qam_channels"
      fields:
        - key: "channelID"
          field: channel_id
          type: integer
      channel_type:
        fixed: "qam"

    - array_path: "docsis.ofdm_channels"
      fields:
        - key: "ofdmID"
          field: channel_id
          type: integer
      channel_type:
        fixed: "ofdm"
```

Each array entry has its own `array_path`, `fields`, `channel_type`,
and `filter`. Results from all arrays are concatenated.

**Per-array resources** --- when channel data lives on separate API
endpoints (following the same pattern as XML tables), each array can
specify its own ``resource``:

```yaml
downstream:
  format: json
  encoding: base64
  arrays:
    - resource: "/api/qam"
      array_path: "nodes"
      channel_type:
        fixed: qam
      fields: [...]
    - resource: "/api/ofdm"
      array_path: "nodes"
      channel_type:
        fixed: ofdm
      fields: [...]
```

When a per-array ``resource`` is set, it overrides the section-level
resource for that array. Either provide a shared section-level
``resource`` or give every array its own --- partial coverage is a
validation error.

**Extraction algorithm:**

1. Get resource dict entry by path
2. Navigate to array(s) using dot-notation path
3. For each object in each array, map keys to canonical fields
4. Concatenate results from all arrays
5. Auto-assign `channel_number` from 1-based array index when not
   already mapped by parser.yaml (see
   [CHANNEL_IDENTIFICATION_SPEC.md](CHANNEL_IDENTIFICATION_SPEC.md) §10)
