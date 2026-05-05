# JavaScript Format Specification

> Parent spec: [PARSING_SPEC.md](PARSING_SPEC.md) — common concepts, output contract, channel type detection

Two JavaScript-based extraction formats exist for modems that embed
DOCSIS data in `<script>` tags rather than HTML tables or JSON API
responses:

- **JSEmbeddedParser** (`format: javascript`) — extracts delimited
  strings from JS function bodies. The data is a flat, separator-split
  string inside a `tagValueList` assignment.
- **JSJsonParser** (`format: javascript_json`) — extracts JSON arrays
  from JS variable assignments. Each array element is a structured
  object with named keys.

Both formats parse raw HTML pages, locate the relevant `<script>` tag,
and produce the same `ModemData` output as every other parser.

## Contents

| Section | What it covers |
|---------|----------------|
| [JSEmbeddedParser](#jsembeddedparser) | Delimited strings in JS function bodies |
| [JSJsonParser](#jsjsonparser) | JSON arrays in JS variable assignments |

---

## JSEmbeddedParser

Extracts data from JavaScript variables embedded in HTML pages. The
source data is a delimited string inside a JS function body.

```yaml
# parser.yaml — JS-embedded delimited strings, multiple functions per section
downstream:
  format: javascript
  resource: "/DocsisStatus.htm"
  functions:
    - name: "InitDsTableTagValue"
      channel_type: "qam"
      delimiter: "|"
      fields_per_channel: 9
      fields:
        - offset: 1
          field: lock_status
          type: string
        - offset: 2
          field: modulation
          type: string
        - offset: 3
          field: channel_id
          type: integer
        - offset: 4
          field: frequency
          type: frequency
          unit: "Hz"
        - offset: 5
          field: power
          type: float
          unit: "dBmV"
        - offset: 6
          field: snr
          type: float
          unit: "dB"
        - offset: 7
          field: corrected
          type: integer
        - offset: 8
          field: uncorrected
          type: integer
      filter:
        lock_status: "Locked"
    - name: "InitDsOfdmTableTagValue"
      channel_type: "ofdm"
      delimiter: "|"
      fields_per_channel: 11
      fields:
        - offset: 3
          field: channel_id
          type: integer
        - offset: 4
          field: frequency
          type: frequency
          unit: "Hz"
        - offset: 5
          field: power
          type: float
          unit: "dBmV"
        - offset: 6
          field: snr
          type: float
          unit: "dB"
        - offset: 7
          field: corrected
          type: integer
        - offset: 8
          field: uncorrected
          type: integer

upstream:
  format: javascript
  resource: "/DocsisStatus.htm"
  functions:
    - name: "InitUsTableTagValue"
      channel_type: "atdma"
      delimiter: "|"
      fields_per_channel: 7
      fields:
        - offset: 3
          field: channel_id
          type: integer
        - offset: 4
          field: symbol_rate
          type: integer
        - offset: 5
          field: frequency
          type: frequency
          unit: "Hz"
        - offset: 6
          field: power
          type: float
          unit: "dBmV"
```

**Config fields:**

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `format` | string | yes | `javascript` — selects `JSEmbeddedParser` |
| `resource` | string | yes | URL path key in the resource dict |
| `functions` | list | yes | One or more JS functions to extract from |
| `functions[].name` | string | yes | JS function name (regex target) |
| `functions[].channel_type` | string | yes | Channel type for all records from this function |
| `functions[].delimiter` | string | yes | Value separator (typically `\|`) |
| `functions[].fields_per_channel` | integer | yes | Number of values per channel record |
| `functions[].fields` | list | yes | Offset→field mappings within each record |
| `functions[].fields[].offset` | integer | yes | Position within the channel record (0-based) |
| `functions[].fields[].field` | string | yes | Canonical output field name |
| `functions[].fields[].type` | string | yes | Field type (see Common Concepts) |
| `functions[].fields[].unit` | string | no | Unit suffix to strip |
| `functions[].fields[].map` | dict | no | Value mapping (exact match, applied before type conversion) |

**Extraction algorithm:**

1. Find `<script>` tag containing the function name
2. Extract function body via regex
3. Strip comments — both block (`/* ... */`) and line (`// ...`)
   comments are removed so that commented-out example assignments
   do not shadow the real `tagValueList`
4. Find `tagValueList` variable assignment
5. Split by delimiter
6. First value is channel count
7. For each channel: read `fields_per_channel` consecutive values,
   map by offset

Multiple functions in the same section (e.g., QAM + OFDM downstream)
produce channels that are concatenated into a single list.

### Channel number assignment

When a section has multiple functions, the framework assigns unified
`channel_number` across the combined list (1-based, function order as
declared in parser.yaml). QAM channels keep their function-local
positions; OFDM channels are numbered after the last QAM channel.

The original per-function position is emitted as
`source_channel_number` when it differs from the unified
`channel_number`. This lets users correlate with modem web UIs that
display separate QAM and OFDM tables with independent numbering.

**Example:** 32 QAM channels (functions[0]) + 2 OFDM channels
(functions[1]):

| Unified `channel_number` | `source_channel_number` | Type |
|---|---|---|
| 1 | *(omitted — same)* | qam |
| ... | | |
| 32 | *(omitted — same)* | qam |
| 33 | 1 | ofdm |
| 34 | 2 | ofdm |

See [CHANNEL_IDENTIFICATION_SPEC.md](CHANNEL_IDENTIFICATION_SPEC.md)
§10 for the full format coverage.

## JSJsonParser

Extracts data from JSON arrays embedded in JavaScript variable
assignments within `<script>` tags. Unlike `javascript` format (which
parses delimited strings from function bodies), `javascript_json`
parses structured JSON objects — each array element is a channel dict
with named keys.

**Example page source (TG3442DE):**

```html
<script type="text/javascript">
json_dsData = [{"ChannelType":"SC-QAM","Modulation":"QAM256",
  "Frequency":"507 MHz","PowerLevel":"3.2 dBmV",
  "SNRLevel":"38.5 dB","LockStatus":"Locked","ChannelID":"1"}];
json_usData = [{"ChannelType":"ATDMA","Modulation":"QAM64",
  "Frequency":"37.7 MHz","PowerLevel":"45.0 dBmV","ChannelID":"1"}];
</script>
```

**Example parser.yaml:**

```yaml
downstream:
  format: javascript_json
  resource: "/php/status_docsis_data.php"
  variable: "json_dsData"
  mappings:
    - key: ChannelID
      field: channel_id
      type: integer
    - key: Frequency
      field: frequency
      type: frequency
    - key: PowerLevel
      field: power
      type: power
```

**Config fields:**

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `format` | string | yes | `javascript_json` — selects `JSJsonParser` |
| `resource` | string | yes | URL path key in the resource dict |
| `variable` | string | yes | JS variable name holding the JSON array |
| `mappings` | list | yes | JSON key→field mappings (same as `json` format) |
| `mappings[].key` | string | yes | JSON object key name |
| `mappings[].field` | string | yes | Canonical output field name |
| `mappings[].type` | string | yes | Field type (see Common Concepts) |
| `channel_type` | object | no | Channel type detection config |
| `filter` | dict | no | Row filter for mixed-type arrays |

**Extraction algorithm:**

1. Decode response as HTML (BeautifulSoup)
2. Find `<script>` tag containing the variable name
3. Extract JSON array via regex: `{variable}\s*=\s*(\[.*?\])\s*;`
4. Parse the extracted string as JSON
5. Map each object's keys to canonical fields via `mappings`

The `variable` field distinguishes downstream from upstream when both
share the same resource URL (e.g., `json_dsData` vs `json_usData`).

### Channel number assignment (javascript_json)

`channel_number` is auto-assigned from the 1-based array index when
not already mapped by parser.yaml. See
[CHANNEL_IDENTIFICATION_SPEC.md](CHANNEL_IDENTIFICATION_SPEC.md) §10.

---

## Failure modes

### Named target absent in `<script>` tag

Both formats locate their extraction sites by a configured **name**:

- `javascript` — `functions[].name` (e.g., `"InitDsTableTagValue"`)
- `javascript_json` — `variable` (e.g., `"json_dsData"`)

When that name is not present in any `<script>` tag in the response
body — for example because the modem returned an HTML stub with
chrome but no data section — the parser logs a WARNING and returns
empty for that source. No exception is raised. Per-format detail:

- `JSEmbeddedParser`: `_extract_tag_value_list` returns `None`,
  parser logs `"Function '{name}' not found in resource '{path}'"`,
  contributes no channels.
- `JSJsonParser`: variable regex match fails, parser logs the
  equivalent warning, contributes no channels.

This is intentional best-effort behavior — firmware variants may
legitimately omit individual functions or variables (e.g., a
DOCSIS 3.0 firmware revision missing OFDM anchors). Partial
fulfillment is not a failure.

**Stub-page case (all named targets absent):** When *every* configured
target across a resource is absent, the response is structurally not
a data page. The Parser Coordinator surfaces this via the
`Parser Diagnostics` contract (`PARSING_SPEC § Parser Diagnostics`)
as `expected_anchors > 0, fulfilled_anchors == 0`, and the collector
raises it to `CollectorSignal.LOAD_INTEGRITY`. See UC-19a in
`ORCHESTRATION_USE_CASES.md` for the full recovery flow.

### MCP onboarding implication

When a modem's HAR fixture replays at `fulfilled_anchors == 0`
against the proposed `parser.yaml`, that is a parser-config bug at
intake (wrong function names, wrong resource path), not a stub
response. Catalog Tools intake should flag this distinctly from
genuine stub captures — same failure shape, different cause.
