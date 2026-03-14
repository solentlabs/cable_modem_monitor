# Parsing Specification

Parsers extract DOCSIS signal data from modem web interface responses.
Every modem's web UI is different — different page structures, different
data formats, different field names — but the output is always the same:
channels with frequency, power, SNR, and error counts.

The parsing system absorbs this variety through three distinct roles:

- **`BaseParser` (ABC)** — the extraction interface. Seven format-specific
  implementations (`HTMLTableParser`, `HTMLTableTransposedParser`,
  `HTMLFieldsParser`, `JSEmbeddedParser`, `HNAPParser`, and
  `StructuredParser` (ABC) → `JSONParser`, `XMLParser`),
  each parameterized by parser.yaml section config.
- **`ModemParserCoordinator`** — factory and orchestrator. Reads
  parser.yaml, creates `BaseParser` instances per section, runs them,
  chains parser.py post-processing, assembles `ModemData`.
- **parser.py** — optional post-processor for modem-specific quirks.
  Receives extraction output + raw resources, can modify or replace.

`parser.yaml` declares the format and field mappings per data section.
`parser.py` handles modem-specific quirks that can't be expressed
declaratively.

**Design principles:**
- At least one of parser.yaml or parser.py is required — every modem package must have one
- parser.yaml is the primary expression mode — code is the escape hatch
- When parser.yaml is present, it drives the fetch list — the orchestrator reads it to know what resources to load
- Format selection is per-section, not per-modem — a modem can mix formats
- `BaseParser` implementations are format experts, not modem experts
- Capabilities are implicit from mappings — no separate declarations
- Parsing is pure — no network calls, no auth, no session state

## Contents

| Section | What it covers |
|---------|----------------|
| [Two Layers: Transport and Format](#two-layers-transport-and-format) | Transport selects loader, format selects parser |
| [Resource Dict](#resource-dict) | What parsers receive — keyed by path, transport-specific values |
| [parser.yaml Schema](#parseryaml-schema) | Declarative config for all 6 extraction formats |
| [System Info](#system-info) | Extracting software version, uptime, network access |
| [Companion Tables (merge_by)](#companion-tables-merge_by) | Merging error stats from separate tables into channels |
| [parser.py — Post-Processing Hooks](#parserpy--post-processing-hooks) | When and how to use code-based post-processing |
| [Output Contract](#output-contract) | ModemData schema, field guarantees, entity identity |
| [Channel Type Detection](#channel-type-detection) | How QAM vs OFDM is determined |
| [Performance Characteristics](#performance-characteristics) | Request counts and timing by transport |

---

## Two Layers: Transport and Format

**Transport** (modem.yaml) controls *how data is fetched* — the resource
loader. It identifies the transport protocol (`http` or `hnap`).

**Format** (parser.yaml, per-section) controls *how data is extracted* —
the extraction strategy. Each section (`downstream`, `upstream`,
`system_info`) declares its own format independently.

```
modem.yaml transport → resource loader (how to fetch)
parser.yaml format   → decode step + extraction strategy (how to extract, per-section)
```

For the `http` transport, format is independent — any format can appear
with any auth strategy. A modem can mix formats across sections (e.g.,
`table` for downstream, `javascript` for system_info). For HNAP, the
transport fully constrains the format (always `hnap`).

| Transport | Valid Formats | Why |
|-----------|--------------|-----|
| `hnap` | `hnap` | Protocol-defined: SOAP JSON with delimiters |
| `http` | `table`, `table_transposed`, `html_fields`, `javascript`, `json`, `xml` | Format determines decode step; any format supports optional `encoding` property (e.g., `base64` — decoded before format-specific parsing) |

See [MODEM_YAML_SPEC.md](MODEM_YAML_SPEC.md#validation-rules) for the full transport constraint
table including auth strategies.

### Extraction Formats

| Format | BaseParser Implementation | Extracts from | Scope |
|--------|--------------------------|---------------|-------|
| **HTML** | | | |
| `table` | `HTMLTableParser` | `<table>` elements, rows=channels, cols=metrics | any section |
| `table_transposed` | `HTMLTableTransposedParser` | `<table>` elements, rows=metrics, cols=channels | any section |
| `html_fields` | `HTMLFieldsParser` | Named fields in HTML via label text or element id | system_info only |
| **HTML (embedded JS)** | | | |
| `javascript` | `JSEmbeddedParser` | Delimited strings in JS variables/functions | any section |
| **JSON** | | | |
| `hnap` | `HNAPParser` | Delimiter-separated values in HNAP JSON responses | any section |
| `json` | `JSONParser` | JSON response structures via field paths | any section |

### Per-Section Format in Practice

Most modems use one format for all sections. But some don't:

```yaml
# Mixed formats — transposed tables for channels, JS for system info
downstream:
  format: table_transposed
  resource: "/cmSignalData.htm"
  # ...

upstream:
  format: table_transposed
  resource: "/cmSignalData.htm"
  # ...

system_info:
  format: javascript
  resource: "/cmSignalData.htm"
  functions:
    - name: "InitSystemInfoTagValue"
      # ...
```

```yaml
# Single format — all sections use the same strategy
downstream:
  format: hnap
  response_key: "GetCustomerStatusDownstreamChannelInfoResponse"
  # ...

upstream:
  format: hnap
  response_key: "GetCustomerStatusUpstreamChannelInfoResponse"
  # ...

system_info:
  format: hnap
  response_key: "GetCustomerStatusConnectionInfoResponse"
  # ...
```

When all sections use the same format, parser.yaml is still explicit —
each section declares its format. No inheritance, no defaults to guess.

**`BaseParser` implementations live in Core.** They consume parser.yaml
config. Adding a modem never requires changing a parser implementation
— if it does, the implementation is missing a config field.

---

## Resource Dict

The resource dict is the contract between the resource loader and the
parser (see [RESOURCE_LOADING_SPEC.md](RESOURCE_LOADING_SPEC.md) for
loader behavior). It contains pre-fetched response data keyed by resource
identifier. Parsers receive it as `resources: dict[str, Any]` and
extract data without making network calls.

### HTML and REST

Keys are URL paths collected from `resource` fields in parser.yaml.
One entry per unique path (deduplicated by the loader).

```python
# HTML
{
    "/MotoConnection.asp": BeautifulSoup,
    "/MotoHome.asp": BeautifulSoup,
}

# REST
{
    "/rest/v1/cablemodem/downstream": dict,
    "/rest/v1/cablemodem/upstream": dict,
    "/rest/v1/cablemodem/state_": dict,
}
```

HTML values are `BeautifulSoup` objects. REST values are parsed JSON
dicts.

### HNAP

HNAP uses a single batched SOAP request. The resource dict contains the
parsed response with action responses as top-level keys.

```python
{
    "hnap_response": {
        "GetCustomerStatusDownstreamChannelInfoResponse": {...},
        "GetCustomerStatusUpstreamChannelInfoResponse": {...},
        ...
    },
}
```

`hnap_response` is the `GetMultipleHNAPsResponse` dict containing all
action responses. Individual action responses are accessed by key name
from within this dict.

The resource dict contains only data. Auth infrastructure (sessions,
builders, tokens) flows through the orchestrator, not through the
resource dict.

### Fetch List Derivation

The orchestrator reads parser.yaml at startup to build the resource
fetch list. No separate `pages.data` declaration in modem.yaml — the
parser declares what it needs, and the orchestrator ensures it gets
fetched.

**HTML and REST:** The orchestrator collects all unique `resource`
values from parser.yaml sections (downstream, upstream, system_info
sources). These are URL paths. The loader fetches each unique path
once and builds the resource dict.

```
parser.yaml                          fetch list
─────────────────────────            ──────────────
downstream:                          unique paths:
  resource: "/status.html"    ──►    - /status.html
upstream:                            - /info.html
  resource: "/status.html"
system_info:
  sources:
    - resource: "/info.html"
```

**HNAP:** Sections with `format: hnap` declare `response_key` instead
of `resource`. The orchestrator detects this and tells the HNAP loader
to batch all referenced action names into a single
`GetMultipleHNAPs` request. HNAP action names are derived from `response_key`
by stripping the `Response` suffix.

**Startup validation:** The orchestrator verifies at startup that
every `resource` path in parser.yaml is fetchable (valid path format,
modem reachable) and that every HNAP `response_key` has a
corresponding action. Missing resources fail fast with a clear error.

---

## parser.yaml Schema

parser.yaml defines how each data section is extracted from resources.
Each section declares its `format` (which selects the extraction
strategy) and the format-specific field mappings. Sections within
the same parser.yaml can use different formats.

**parser.yaml never contains auth, session config, or metadata.**

### Common Concepts

#### Field Types

Every field mapping declares a type that controls parsing and conversion:

| Type | Input | Output | Notes |
|------|-------|--------|-------|
| `integer` | `"123"`, `123` | `int` | Strip whitespace |
| `float` | `"3.14 dBmV"` | `float` | Strip unit suffix |
| `string` | any | `str` | Strip whitespace |
| `frequency` | `"507 MHz"`, `507000000` | `int` (Hz) | Auto-detect Hz vs MHz by magnitude; strip unit suffix |
| `boolean` | `true`, `"Locked"` | `bool` | Configurable truthy value |

Only explicitly mapped fields are extracted. Source fields without a
mapping in parser.yaml are ignored — no implicit pass-through from
the source. To capture additional fields, add them to the mapping.

The `frequency` type handles the most common parser quirk: some modems
report in Hz, others in MHz, some include a unit suffix, some don't.
The strategy normalizes all frequencies to Hz.

#### Unit Stripping

Numeric fields often include unit suffixes in the source data (`"3.2 dBmV"`,
`"507 MHz"`, `"-15.3 dB"`). Each field mapping can declare a `unit` suffix
that the strategy strips before type conversion.

```yaml
- field: power
  type: float
  unit: "dBmV"
```

#### Filter Rules

Channel-level filtering removes invalid or placeholder records:

```yaml
filter:
  lock_status: "Locked"          # Keep only locked channels
  frequency: { not: 0 }          # Drop zero-frequency placeholders
  channel_id: { not: 0 }         # Drop HNAP placeholder slots
```

Filters apply after field extraction. A channel that fails any filter
condition is excluded from the output.

### HTMLTableParser

Extracts data from `<table>` elements where rows are channels and
columns are fields. Supports one or more tables per data section —
multiple tables are concatenated into a single channel list.

#### Single table with mixed channel types

SC-QAM and OFDM channels are mixed in one table. The strategy
classifies each row by mapping a field's value to canonical types:

```yaml
downstream:
  format: table
  resource: "/cmconnectionstatus.html"
  tables:
    - selector:
        type: header_text
        match: "Downstream Bonded Channels"
      skip_rows: 1
      columns:
        - index: 0
          field: channel_id
          type: integer
        - index: 1
          field: lock_status
          type: string
        - index: 2
          field: modulation
          type: string
        - index: 3
          field: frequency
          type: frequency
          unit: "Hz"
        - index: 4
          field: power
          type: float
          unit: "dBmV"
        - index: 5
          field: snr
          type: float
          unit: "dB"
        - index: 6
          field: corrected
          type: integer
        - index: 7
          field: uncorrected
          type: integer
      channel_type:
        field: modulation
        map:
          "QAM256": "qam"
          "QAM64": "qam"
          "Other": "ofdm"
      filter:
        lock_status: "Locked"
```

#### Separate tables per channel type

SC-QAM and OFDM channels are in separate tables with potentially
different column layouts. Each table declares its own `channel_type`:

```yaml
downstream:
  format: table
  resource: "/cgi-bin/status_cgi"
  tables:
    - selector:
        type: header_text
        match: "Downstream QAM"
      channel_type:
        fixed: "qam"
      skip_rows: 1
      columns:
        - index: 0
          field: channel_id
          type: integer
        - index: 3
          field: frequency
          type: frequency
        - index: 4
          field: power
          type: float
        - index: 5
          field: snr
          type: float
        - index: 6
          field: corrected
          type: integer
        - index: 7
          field: uncorrected
          type: integer

    - selector:
        type: header_text
        match: "Downstream OFDM"
      channel_type:
        fixed: "ofdm"
      skip_rows: 1
      columns:
        - index: 0
          field: channel_id
          type: integer
        - index: 3
          field: frequency
          type: frequency
        - index: 4
          field: power
          type: float
        - index: 5
          field: snr
          type: float
        - index: 6
          field: corrected
          type: integer
        - index: 7
          field: uncorrected
          type: integer
        - index: 8
          field: channel_width
          type: integer
```

The strategy processes each table in order and concatenates the
results. Each table can have its own selector, column layout,
channel type, and filter rules. This handles modems that split
channel types across separate HTML tables.

#### Upstream example

```yaml
upstream:
  format: table
  resource: "/cmconnectionstatus.html"
  tables:
    - selector:
        type: header_text
        match: "Upstream Bonded Channels"
      skip_rows: 1
      columns:
        - index: 0
          field: channel_id
          type: integer
        - index: 1
          field: lock_status
          type: string
        - index: 2
          field: modulation
          type: string
        - index: 3
          field: channel_type
          type: string
        - index: 4
          field: frequency
          type: frequency
          unit: "Hz"
        - index: 5
          field: power
          type: float
          unit: "dBmV"
      filter:
        lock_status: "Locked"
```

**Config fields:**

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `format` | string | yes | `table` — selects `HTMLTableParser` |
| `resource` | string | yes | URL path key in the resource dict |
| `tables` | list | yes | One or more table definitions (concatenated in order, unless `merge_by` is set) |
| `tables[].selector` | object | yes | How to find the table in the page |
| `tables[].selector.type` | string | yes | `header_text`, `css`, `id`, `nth` |
| `tables[].selector.match` | string | yes | Search value (text, CSS selector, ID, or index) |
| `tables[].skip_rows` | integer | no | Number of header rows to skip (default 0) |
| `tables[].columns` | list | yes | Ordered column→field mappings |
| `tables[].columns[].index` | integer | yes | Column position (0-based) |
| `tables[].columns[].field` | string | yes | Canonical output field name |
| `tables[].columns[].type` | string | yes | Field type (see table above) |
| `tables[].columns[].unit` | string | no | Unit suffix to strip |
| `tables[].channel_type` | object | no | Channel type: `fixed`, `map`, or explicit field |
| `tables[].filter` | object | no | Row filter rules |
| `tables[].merge_by` | list[string] | no | Merge into primary channels by these key fields instead of concatenating. See [Companion Tables](#companion-tables-merge_by). |

**Table selector types:**

| Type | Behavior | Example |
|------|----------|---------|
| `header_text` | Find `<th>` or `<td>` containing text, return parent `<table>` | `"Downstream Bonded Channels"` |
| `css` | CSS selector returning a `<table>` element | `"table.moto-table-content"` |
| `id` | Table element with matching `id` attribute | `"dsTable"` |
| `nth` | Nth `<table>` element on the page (0-based) | `2` |

### HTMLTableTransposedParser

Extracts data from `<table>` elements where rows are metrics and
columns are channels. The strategy pivots the data — for each column
index, it collects values from all metric rows to build one channel.

#### Single table (flat config)

When a section has one transposed table, use the flat form with
`selector` and `rows` at the section level:

```yaml
# parser.yaml — transposed table with label-based row matching
downstream:
  format: table_transposed
  resource: "/st_docsis.html"
  selector:
    type: header_text
    match: "Downstream Channels"
    fallback:
      type: attribute
      match: { "data-i18n": "ds_link_downstream_channels" }
  rows:
    - label: "Channel ID"
      field: channel_id
      type: integer
    - label: "Modulation"
      field: modulation
      type: string
    - label: "SNR"
      field: snr
      type: float
      unit: "dB"
    - label: "Power Level"
      field: power
      type: float
      unit: "dBmV"
    - label: "Frequency"
      field: frequency
      type: frequency
  channel_type:
    fixed: "qam"
```

#### Multiple tables with companion merge

When a section has a primary table plus a companion table whose fields
should be merged into the primary channels, use the `tables[]` form.
See [Companion Tables (merge_by)](#companion-tables-merge_by) for the
full design. Example:

```yaml
# parser.yaml — modem with primary channel data + separate error stats table
downstream:
  format: table_transposed
  resource: "/cmSignalData.htm"
  tables:
    # Primary table — defines channels
    - selector:
        type: header_text
        match: "Downstream"
      rows:
        - label: "Channel ID"
          field: channel_id
          type: integer
        - label: "Frequency"
          field: frequency
          type: frequency
          unit: "Hz"
        - label: "Signal to Noise Ratio"
          field: snr
          type: float
          unit: "dB"
        - label: "Power Level"
          field: power
          type: float
          unit: "dBmV"
      channel_type:
        fixed: "qam"

    # Companion table — enriches channels with error stats
    - selector:
        type: header_text
        match: "Signal Stats (Codewords)"
      merge_by: [channel_id]
      rows:
        - label: "Channel ID"
          field: channel_id
          type: integer
        - label: "Total Correctable Codewords"
          field: corrected
          type: integer
        - label: "Total Uncorrectable Codewords"
          field: uncorrected
          type: integer
```

**Config fields (differs from HTMLTableParser):**

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `format` | string | yes | `table_transposed` — selects `HTMLTableTransposedParser` |
| `resource` | string | yes | URL path key in the resource dict |
| `selector` | object | conditional | How to find the table (flat form — mutually exclusive with `tables`) |
| `rows` | list | conditional | Row label→field mappings (flat form — mutually exclusive with `tables`) |
| `rows[].label` | string | yes | Row header text to match |
| `rows[].field` | string | yes | Canonical output field name |
| `rows[].type` | string | yes | Field type (see Common Concepts) |
| `rows[].unit` | string | no | Unit suffix to strip |
| `channel_type` | object | no | Channel type detection rules (flat form) |
| `tables` | list | conditional | One or more table definitions (multi-table form — mutually exclusive with `selector`/`rows`) |
| `tables[].selector` | object | yes | How to find the table (same types as HTMLTableParser) |
| `tables[].rows` | list | yes | Row label→field mappings |
| `tables[].channel_type` | object | no | Channel type detection rules |
| `tables[].merge_by` | list[string] | no | Merge into primary channels by these key fields. See [Companion Tables](#companion-tables-merge_by). |

Either `selector`/`rows` (flat form) or `tables` (multi-table form)
must be present, but not both. The flat form is syntactic sugar for a
single-element `tables[]` with no `merge_by`.

The parser scans table rows for matching labels, builds a
`{label: [values]}` map, then iterates column indices to assemble
channels. Channel count is inferred from the number of values in any
mapped row.

### JSEmbeddedParser

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
      channels:
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
      channels:
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
      channels:
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
| `functions[].channels` | list | yes | Offset→field mappings within each record |
| `functions[].channels[].offset` | integer | yes | Position within the channel record (0-based) |

**Extraction algorithm:**
1. Find `<script>` tag containing the function name
2. Extract function body via regex
3. Find `tagValueList` variable assignment
4. Split by delimiter
5. First value is channel count
6. For each channel: read `fields_per_channel` consecutive values,
   map by offset

Multiple functions in the same section (e.g., QAM + OFDM downstream)
produce channels that are concatenated into a single list.

### HNAPParser

Extracts data from HNAP SOAP responses where channel data is encoded
as delimiter-separated strings within JSON values.

```yaml
# parser.yaml — HNAP delimited strings with mixed channel types
downstream:
  format: hnap
  response_key: "GetCustomerStatusDownstreamChannelInfoResponse"
  data_key: "CustomerConnDownstreamChannel"
  record_delimiter: "|+|"
  field_delimiter: "^"
  channels:
    - index: 3
      field: channel_id
      type: integer
    - index: 4
      field: frequency
      type: frequency
    - index: 5
      field: power
      type: float
    - index: 6
      field: snr
      type: float
    - index: 7
      field: corrected
      type: integer
    - index: 8
      field: uncorrected
      type: integer
  channel_type:
    index: 2
    map:
      "SC-QAM": "qam"
      "OFDM": "ofdm"
  filter:
    channel_id: { not: 0 }

upstream:
  format: hnap
  response_key: "GetCustomerStatusUpstreamChannelInfoResponse"
  data_key: "CustomerConnUpstreamChannel"
  record_delimiter: "|+|"
  field_delimiter: "^"
  channels:
    - index: 3
      field: channel_id
      type: integer
    - index: 4
      field: symbol_rate
      type: integer
    - index: 5
      field: frequency
      type: frequency
    - index: 6
      field: power
      type: float
  channel_type:
    index: 2
    map:
      "ATDMA": "atdma"
      "OFDMA": "ofdma"
```

**Config fields:**

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `format` | string | yes | `hnap` — selects `HNAPParser` |
| `response_key` | string | yes | HNAP action response key in `hnap_response` dict |
| `data_key` | string | yes | Field within the action response containing delimited data |
| `record_delimiter` | string | yes | Separator between channel records |
| `field_delimiter` | string | yes | Separator between fields within a record |
| `channels` | list | yes | Index→field mappings within each record |

**Extraction algorithm:**
1. Navigate `hnap_response[response_key][data_key]` to get the
   delimited string
2. Split by `record_delimiter` to get channel records
3. For each record, split by `field_delimiter` to get fields
4. Map fields by index

Action names vary by manufacturer. parser.yaml declares the exact key
names — the strategy doesn't assume any naming convention.

### JSONParser

Extracts data from JSON API responses using path navigation and direct
key access.

```yaml
# parser.yaml — JSON API with dot-notation path to channel array
downstream:
  format: json
  resource: "/rest/v1/cablemodem/downstream"
  array_path: "downstream.channels"
  channels:
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
  channel_type:
    key: "channelType"
    map:
      "sc-qam": "qam"
      "ofdm": "ofdm"

upstream:
  format: json
  resource: "/rest/v1/cablemodem/upstream"
  array_path: "upstream.channels"
  channels:
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

**Config fields:**

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `format` | string | yes | `json` — selects `JSONParser` |
| `resource` | string | yes | URL path key in the resource dict |
| `array_path` | string | yes | Dot-notation path to the channel array |
| `channels` | list | yes | Key→field mappings within each JSON object |
| `channels[].key` | string | yes | JSON key name in the source object |
| `channels[].fallback_key` | string | no | Alternative key if primary is missing |

**Extraction algorithm:**
1. Get resource dict entry by path
2. Navigate to array using dot-notation path
3. For each object in the array, map keys to canonical fields

---

## System Info

System info produces a flat dict instead of a channel list. Unlike
channel sections where data typically comes from one source, system info
is often spread across multiple pages or responses. The `sources` list
handles this — each source declares its own format, resource, and fields.
Results are merged into a single dict.

### Multi-source examples

**HNAP — fields from multiple SOAP responses:**

```yaml
system_info:
  sources:
    - format: hnap
      response_key: "GetCustomerStatusConnectionInfoResponse"
      fields:
        - source: "CustomerConnNetworkAccess"
          field: network_access
          type: string

    - format: hnap
      response_key: "Get{Prefix}DeviceStatusResponse"
      fields:
        - source: "FirmwareVersion"
          field: software_version
          type: string

    - format: hnap
      response_key: "GetCustomerStatusStartupSequenceResponse"
      fields:
        - source: "CustomerConnBootStatus"
          field: boot_status
          type: string
        - source: "CustomerConnSecurityStatus"
          field: security_status
          type: string
```

**HTML — label-based fields from multiple pages:**

```yaml
system_info:
  sources:
    - format: html_fields
      resource: "/MotoHome.asp"
      fields:
        - label: "System Up Time"
          field: system_uptime
          type: string

    - format: html_fields
      resource: "/MotoSwInfo.asp"
      fields:
        - label: "Software Version"
          field: software_version
          type: string
        - label: "Hardware Version"
          field: hardware_version
          type: string

    - format: html_fields
      resource: "/MotoConnection.asp"
      fields:
        - label: "Cable Modem Status"
          field: network_access
          type: string
```

**HTML — id-based fields with regex extraction:**

```yaml
system_info:
  sources:
    - format: html_fields
      resource: "/DocsisStatus.asp"
      fields:
        - id: "SystemUpTime"
          pattern: "System Up Time:\\s*(.*)"
          field: system_uptime
          type: string
        - id: "CurrentSystemTime"
          pattern: "Current System Time:\\s*(.*)"
          field: current_time
          type: string
```

**Mixed formats — html_fields + JS variables:**

```yaml
system_info:
  sources:
    - format: html_fields
      resource: "/RouterStatus.htm"
      fields:
        - label: "Hardware Version"
          field: hardware_version
          type: string

    - format: javascript
      resource: "/RouterStatus.htm"
      functions:
        - name: "InitTagValue"
          delimiter: "|"
          fields:
            - offset: 1
              field: software_version
              type: string
            - offset: 33
              field: system_uptime
              type: string
```

**REST — single JSON source:**

```yaml
system_info:
  sources:
    - format: json
      resource: "/rest/v1/cablemodem/state_"
      object_path: "cablemodem"
      fields:
        - source: "upTime"
          field: system_uptime
          type: string
        - source: "docsisVersion"
          field: docsis_version
          type: string
        - source: "status"
          field: network_access
          type: string
```

### Source processing

The `ModemParserCoordinator` processes each source in order and merges
the resulting dicts. If two sources extract the same field name, the
later source wins (last-write-wins). In practice, fields should not
overlap — each source owns distinct fields.

### Formats for system info

| Format | Source type | How fields are found |
|--------|------------|---------------------|
| `html_fields` | HTML page | Two selector types (see below) |
| `javascript` | HTML page | JS function body → delimited string → offset |
| `hnap` | HNAP response | Action response key → JSON key |
| `json` | REST response | Object path → JSON key |

#### `html_fields` selector types

| Selector | When to use | Algorithm |
|----------|------------|-----------|
| `label: "text"` | Value appears next to a text label | Find element containing label text, cascade through structural patterns (td→sibling td, th→paired td, span→sibling span, dt→dd) to locate the adjacent value element |
| `id: "element_id"` | Value is in an element with a known HTML id | Direct element lookup via `id` attribute, extract text content |

Both selectors support an optional `pattern` field — a regex with a
single capture group applied to the extracted text. If omitted, the
full `get_text()` result is the value. Regex is compiled and validated
at config load time.

The `label` cascade is anti-fragile: firmware updates that change HTML
structure (e.g., `<th>/<td>` to `<td>/<td>`) don't break configs
because the parser tries multiple structural patterns. New patterns
added to the cascade benefit all modems without config changes.

System info fields are open-ended — modems expose different fields.
The parser extracts whatever is declared in parser.yaml. Fields not
declared are not extracted (implicit capabilities).

---

## Companion Tables (merge_by)

Some modems split channel data across multiple tables — sometimes on
the same page, sometimes on different pages. One table has the primary
channel fields (frequency, power, SNR); another has supplementary
fields for the same channels (e.g., error statistics, lock status,
modulation details). These aren't separate channel lists — they're
partial views of the same channels that must be joined by a shared key.

The `merge_by` field on a `tables[]` entry tells the coordinator:
"don't append these as new channels — look up existing channels from
the primary table by the declared key fields and add my fields to
them."

### How it works

1. **Primary tables** (no `merge_by`) are parsed first and their
   channels are concatenated into a single list — the normal `tables[]`
   behavior.
2. **Companion tables** (with `merge_by`) are parsed next. Each
   produces a list of partial channel dicts containing the key fields
   plus the enrichment fields.
3. The coordinator builds a lookup from each companion table keyed by
   the `merge_by` fields, then iterates the primary channel list and
   copies over any fields the primary doesn't already have.

Primary always wins on conflicts — if both tables have a field with the
same name, the primary table's value is kept.

All `tables[]` entries in a section share the section-level `resource`.
If a future modem has companion data on a different page, adding a
per-table `resource` override is a natural extension — but no current
modem requires it.

### merge_by is a list

`merge_by` declares which fields form the lookup key:

- `merge_by: [channel_id]` — key on channel_id alone. Sufficient when
  channel IDs are unique within the section.
- `merge_by: [channel_type, channel_id]` — composite key. Needed if
  channel IDs can collide across channel types (e.g., QAM channel 33
  and OFDM channel 33 in a DOCSIS 3.1 modem) AND the companion table
  can distinguish them.

All current modems with companion tables use `merge_by: [channel_id]`
because their channel IDs are unique within each companion table.

### Merge logic (in ModemParserCoordinator)

```python
def _merge_channels(
    self,
    primary: list[dict],
    merge_table: list[dict],
    merge_by: list[str],
) -> list[dict]:
    """Merge fields from a companion table into primary channels."""
    # Build lookup by declared key fields
    merge_map: dict[tuple, dict] = {}
    for ch in merge_table:
        key = tuple(ch.get(field) for field in merge_by)
        merge_map[key] = ch

    # Enrich primary channels (primary wins on conflicts)
    for ch in primary:
        key = tuple(ch.get(field) for field in merge_by)
        extra = merge_map.get(key, {})
        for field, value in extra.items():
            if field not in ch:
                ch[field] = value

    return primary
```

### Applies to both table formats

`merge_by` works with both `HTMLTableParser` (standard tables) and
`HTMLTableTransposedParser` (transposed tables). The companion table is
parsed by the same parser strategy as any other table in the `tables[]`
list; `merge_by` only changes what the coordinator does with the
results.

### Evidence

Some modems split channel data across a primary table (channel metrics)
and a companion table (error statistics). Both tables share a common
`channel_id` key, and `merge_by: [channel_id]` joins them. This pattern
appears in modems using `table_transposed` format where error codewords
are reported in a separate HTML table from the signal measurements.

All other current modems have their supplementary fields (error stats,
etc.) as inline columns in the primary table — no merge needed.

---

## parser.py — Post-Processing Hooks

parser.py handles modem-specific quirks that can't be expressed
declaratively in parser.yaml. It is an optional post-processor — not
a subclass of `BaseParser` or `ModemParserCoordinator`. The coordinator
invokes parser.py hooks after the `BaseParser` extraction step,
passing both the extraction output and the raw resources.

```
ModemParserCoordinator
  ├── creates BaseParser instances from parser.yaml (factory)
  │     ├── HTMLTableParser
  │     ├── HNAPParser
  │     └── ...
  ├── runs them per section:
  │     ├── parse primary tables → concatenate → channel list
  │     ├── parse companion tables (merge_by) → merge into channel list
  │     └── section data complete
  ├── passes output + resources to parser.py hooks (if present)
  └── assembles ModemData
```

parser.py does not inherit from the coordinator or from `BaseParser`.
It is a plain class with optional hook methods that the coordinator
discovers and invokes per section.

### When to Use parser.py

- Complex uptime/boot time string parsing
- Restart window filtering (needs runtime state)
- Frequency range→center conversion
- Any extraction that requires conditional logic beyond simple filtering

### Post-Processing Contract

```python
class ExampleModemPostProcessor:
    """Post-process specific sections. Sections without a hook here
    use the BaseParser extraction output as-is.

    Naming convention: {Manufacturer}{Model}PostProcessor
    """

    def parse_downstream(
        self, channels: list[dict], resources: dict[str, Any]
    ) -> list[dict]:
        """Convert OFDM frequency ranges to center frequencies."""
        for ch in channels:
            if ch.get("channel_type") == "ofdm" and ch.get("freq_start"):
                ch["frequency"] = (ch["freq_start"] + ch["freq_end"]) // 2
        return channels

    def parse_system_info(
        self, system_info: dict, resources: dict[str, Any]
    ) -> dict:
        """Replace system info with non-standard extraction."""
        soup = resources.get("/network_setup.jst")
        return self._extract_system_info(soup)

    # parse_upstream is NOT defined — BaseParser output used as-is
```

Each hook receives two arguments:
- The `BaseParser` extraction output for that section (channel list or
  system_info dict). May be empty if parser.yaml has no mapping for
  this section.
- The full resource dict (for accessing raw response data).

The hook's return value is final — it replaces the extraction output
for that section. Last-write-wins: parser.py can add fields, transform
values, filter channels, or fully replace the extraction output.

### Rules

1. **Hooks are per-section.** Define `parse_downstream`,
   `parse_upstream`, or `parse_system_info`. Sections without a hook
   use the `BaseParser` output directly. There is no modem-level hook
   — the coordinator owns the pipeline.

2. **No network calls.** parser.py receives the pre-fetched resource
   dict. No session, no HTTP client, no auth awareness. If a parser
   needs data from a URL not in the resource dict, add a `resource`
   reference in parser.yaml — the orchestrator will include it in the
   fetch list automatically.

3. **No auth or session state.** parser.py is a pure data transformer.
   Infrastructure like HNAP builders, session tokens, and cookies flow
   through the orchestrator, not through the parser.

4. **Graduate recurring patterns.** When the same hook appears in
   3+ modems, it becomes a parser.yaml config field and the hooks
   are deleted. parser.py is for genuine one-offs.

### What parser.py Returns

The same structure as `BaseParser` extraction output:

```python
# parse_downstream / parse_upstream → list of channel dicts
[
    {
        "channel_id": 1,
        "lock_status": "Locked",
        "modulation": "QAM256",
        "channel_type": "qam",
        "frequency": 507000000,
        "power": 3.2,
        "snr": 38.5,
        "corrected": 0,
        "uncorrected": 0,
    },
    ...
]

# parse_system_info → flat dict
{
    "system_uptime": "7 days 00:00:01",
    "hardware_version": "6.0",
    "software_version": "AB01.02.053",
}
```

### How parser.yaml and parser.py Combine

The `ModemParserCoordinator` processes each section independently:

```
For each section (downstream, upstream, system_info):
  parser.yaml has mapping for this section?
    └─ Yes → BaseParser extracts per table:
              ├─ primary tables (no merge_by) → concatenate → channel list
              ├─ companion tables (merge_by) → merge fields into channel list
              └─ section data
    └─ No  → empty result ([] or {})
  parser.py has hook for this section?
    └─ Yes → hook(section_data, resources) → final section data
    └─ No  → section data used as-is
```

A modem can freely mix:
- **100% parser.yaml** — all sections declarative, no parser.py
- **parser.yaml + parser.py enrichment** — BaseParser extracts base
  data, parser.py adds/transforms fields using raw resources
- **parser.py replacement** — BaseParser output is empty or ignored,
  parser.py extracts everything from raw resources
- **Mixed per-section** — parser.yaml handles some sections, parser.py
  post-processes others

---

## Output Contract

All `BaseParser` implementations and parser.py hooks produce the same
`ModemData` shape. This is the contract between parsing and everything
downstream (entities, diagnostics, HA sensors).

Channel dicts and system_info are open — canonical fields are guaranteed,
but any additional field mapped in parser.yaml or extracted by parser.py
passes through without core changes. This lets modems expose values like
`channel_width`, `active_subcarriers`, `temperature`, or `fft_size`
without modifying Core or the `BaseParser` implementations.

```python
{
    "downstream": [
        {
            # Canonical fields (Core understands these)
            "channel_id": int,         # DOCSIS channel ID
            "lock_status": str,        # "Locked" | "Not Locked"
            "modulation": str,         # "QAM256", "OFDM", etc.
            "channel_type": str,       # "qam" | "ofdm"
            "frequency": int,          # Hz (always)
            "power": float,            # dBmV
            "snr": float,              # dB
            "corrected": int,          # correctable codeword errors
            "uncorrected": int,        # uncorrectable codeword errors

            # Modem-specific fields pass through (Core ignores, HA exposes)
            # e.g., "channel_width": 192000000, "active_subcarriers": 1880
        },
    ],
    "upstream": [
        {
            # Canonical fields
            "channel_id": int,
            "lock_status": str,
            "modulation": str,
            "channel_type": str,       # "atdma" | "ofdma"
            "frequency": int,          # Hz
            "power": float,            # dBmV
            "symbol_rate": int,        # ksym/s (if available)

            # Modem-specific fields pass through
        },
    ],
    "system_info": {
        # Standard fields (present when the modem exposes them)
        "system_uptime": str,          # e.g., "7 days 00:00:01"
        "hardware_version": str,
        "software_version": str,
        "model_name": str,
        "network_access": str,         # "Allowed" | "Denied"

        # Modem-specific fields pass through
        # e.g., "boot_status", "security_status", "docsis_version"
    },
}
```

### Entity Identity Key

Channel entities are identified by the composite key
`(channel_type, channel_id)`. This key is stable across polls and
maps to HA entity IDs like `sensor.ds_qam_ch_21_power`.

- `channel_type` disambiguates DOCSIS 3.1 modems where SC-QAM and
  OFDM channels can share the same channel ID
- `channel_id` is the DOCSIS Channel ID assigned by the CMTS, not the
  display row index — ISP technicians reference channel IDs, and error
  counts accumulate per channel ID

Both fields are **required** in every channel dict. A channel without
`channel_type` or `channel_id` cannot be mapped to an entity.

When a modem reboots, the CMTS may assign different channels
(rebonding). The entity model handles this — channels that disappear
become inactive, new channels get new entities. See the entity model
specification for lifecycle details.

### Field Guarantees

**Canonical fields** — Core understands these and uses them for
entity identity, status derivation, health checks, and DOCSIS lock
detection:

- `channel_id` is always present and non-zero for valid channels
- `channel_type` uses canonical values: `qam`, `ofdm`, `atdma`, `ofdma`
- `lock_status` uses canonical values: `locked`, `not_locked`. Raw
  modem-specific values (e.g., `"Locked"`, `"Not Locked"`, `"Active"`,
  `"Inactive"`) are normalized via `map` in parser.yaml, same mechanism
  as `channel_type`. Modems that don't report lock status omit the
  field. The orchestrator uses normalized `lock_status` to derive
  `docsis_status` — see
  [RUNTIME_POLLING_SPEC.md](RUNTIME_POLLING_SPEC.md#status-derivation)
- `frequency` is always in Hz (`BaseParser` implementations normalize from MHz/GHz)
- `power` and `snr` are floats even when the source is integer
- `system_info` keys are snake_case, values are strings
- Missing optional fields are omitted (not `null` or empty string)

**Additional mapped fields** — Core does not validate or interpret
these. They flow from parser output to HA entity attributes unchanged.
Only fields explicitly mapped in parser.yaml or returned by parser.py
are included — unmapped source fields are ignored. This is how modems
expose additional data without requiring Core changes.

### Field Name Registry

Field names follow a three-tier system. Core defines Tier 1 canonical
fields (above). The Catalog maintains the full registry — Tier 2
registered fields and Tier 3 naming conventions — because it grows
with the modem collection.

See [FIELD_REGISTRY.md](FIELD_REGISTRY.md)
for the complete registry, graduation criteria, and naming rules.

### Capabilities Are Implicit

The presence of data in the output IS the capability declaration:

- Downstream channels in output → `qam_downstream` capability
- OFDM channels in output → `ofdm_downstream` capability
- `system_uptime` in system_info → `system_uptime` capability

No separate capabilities list in modem.yaml. No registration. If the
parser extracts it, the entity exists.

---

## Channel Type Detection

Modems report channel types differently. The strategy needs to classify
each channel as one of four canonical types: `qam`, `ofdm`, `atdma`,
`ofdma`.

parser.yaml supports three detection mechanisms:

### Fixed

All channels in the section (or table) are the same type. Used for
DOCSIS 3.0 modems (all QAM/ATDMA) and separate-table layouts where
each table contains one channel type:

```yaml
channel_type:
  fixed: "qam"
```

### Map

A source field's value is mapped to canonical types. Every expected
value from the modem firmware must have an explicit entry. Unrecognized
values are not silently absorbed — they produce a warning, allowing
new channel types (e.g., future DOCSIS versions) to surface rather
than be misclassified.

The accessor varies by parser format — `field` for HTML table column
names, `index` for positional formats (HNAP, JSEmbedded), `key` for
JSON object keys:

```yaml
# HTML table — map by column value
channel_type:
  field: modulation
  map:
    "QAM256": "qam"
    "QAM64": "qam"
    "Other": "ofdm"

# HNAP — map by positional index
channel_type:
  index: 2
  map:
    "SC-QAM": "qam"
    "OFDM": "ofdm"

# JSON — map by object key
channel_type:
  key: "channelType"
  map:
    "sc-qam": "qam"
    "ofdm": "ofdm"
```

### Explicit Field

The source data has a channel type field that is extracted directly
as a column/field mapping. The strategy normalizes the raw value to
a canonical type using the same map rules. Use this when the modem
provides a dedicated channel type column:

```yaml
columns:
  - index: 3
    field: channel_type
    type: string
    map:
      "SC-QAM": "qam"
      "OFDM": "ofdm"
```

---

## Performance Characteristics

| Phase | Cost | Scale factor |
|-------|------|--------------|
| parser.yaml load | Read + parse one YAML file | Once at startup |
| `BaseParser` instantiation | In-memory, no I/O | Once at startup |
| `parse_resources()` | CPU-bound HTML/JSON parsing | Per poll cycle |
| Field extraction | String splits, type casts | O(channels × fields) |

Parsing is CPU-bound and fast (< 100ms for the largest modems with 32+
channels). The bottleneck is always the HTTP fetch, not the parse.

`BaseParser` instances are created once at startup and reused
every poll cycle.
