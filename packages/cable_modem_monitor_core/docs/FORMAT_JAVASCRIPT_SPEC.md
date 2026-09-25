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

**Object variable, several arrays.** Some firmware assigns one object
holding every channel array (Arris actionHandler UI, `wan.php`):

```html
<script>
let channelData = {"ds_channels": [{"ChannelID": "1", ...}],
                   "ofdm_channels": [{"ChannelID": "33", ...}],
                   "error_codewords": [{"ChannelID": "1", "Correctable": "0", ...}]};
</script>
```

The `arrays` form reads it. Each entry selects one array by
`array_path` (dot-separated, as in the `json` format) and carries its
own mappings. Entries without `merge_by` are primary: their channels
are concatenated in order. An entry with `merge_by` is a companion:
its rows only add fields to primary channels with the same key values,
under the rules in
[FORMAT_TABLE_SPEC.md § Companion Tables](FORMAT_TABLE_SPEC.md#companion-tables-merge_by)
(primary wins on conflicts, unmatched primaries stay, companions never
create channels).

```yaml
downstream:
  format: javascript_json
  resource: "/wan.php"
  variable: "channelData"
  arrays:
    - array_path: "ds_channels"
      channel_type: {fixed: qam}
      mappings: [...]
    - array_path: "ofdm_channels"
      channel_type: {fixed: ofdm}
      mappings: [...]
    - array_path: "error_codewords"
      merge_by: [channel_id]
      mappings:
        - {key: ChannelID, field: channel_id, type: integer}
        - {key: Correctable, field: corrected, type: integer}
        - {key: Uncorrectable, field: uncorrected, type: integer}
```

**Config fields:**

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `format` | string | yes | `javascript_json` — selects `JSJsonParser` |
| `resource` | string | yes | URL path key in the resource dict |
| `variable` | string | yes | JS variable name: an array in the flat form, an object in the `arrays` form |
| `mappings` | list | flat form | JSON key→field mappings (same as `json` format) |
| `mappings[].key` | string | yes | JSON object key name |
| `mappings[].field` | string | yes | Canonical output field name |
| `mappings[].type` | string | yes | Field type (see Common Concepts) |
| `channel_type` | object | no | Channel type detection config (flat form) |
| `filter` | dict | no | Row filter for mixed-type arrays (flat form) |
| `arrays` | list | `arrays` form | One entry per array in the object |
| `arrays[].array_path` | string | yes | Dot-separated path to the array inside the object |
| `arrays[].mappings` | list | yes | Mappings for that array, as above |
| `arrays[].channel_type` | object | no | Channel type for that array |
| `arrays[].filter` | dict | no | Row filter for that array |
| `arrays[].merge_by` | list[string] | no | Makes the array a companion merged by these canonical fields |

The flat form (`mappings` at section level) and the `arrays` form are
mutually exclusive, and a section with `arrays` needs at least one
primary entry.

**Extraction algorithm:**

1. Decode response as HTML (BeautifulSoup)
2. Find `<script>` tag containing the variable name
3. Locate the assignment `{variable}\s*=\s*` and parse the JSON value
   that follows it with a JSON decoder's `raw_decode`, which ends
   where the value ends. A regex cannot delimit an object whose
   arrays nest brackets.
4. Flat form: the value must be an array. `arrays` form: the value
   must be an object; each `array_path` selects an array in it.
5. Map each object's keys to canonical fields via its mappings, then
   merge companions into the primary channels.

The `variable` field distinguishes downstream from upstream when both
share the same resource URL (e.g., `json_dsData` vs `json_usData`).
In the `arrays` form both sections name the same object and select
different arrays.

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
- `JSJsonParser`: variable not found, or its value does not decode,
  parser logs the equivalent warning, contributes no channels. In the
  `arrays` form an `array_path` that resolves to nothing warns and
  contributes nothing for that entry. An array that is present but
  empty is data, not a failure: the modem has no channels of that
  kind. Each primary entry is its own anchor, so a page missing all of
  them still reads as a stub.

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
