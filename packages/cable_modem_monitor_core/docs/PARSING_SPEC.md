# Parsing Specification

Parsers extract DOCSIS signal data from modem web interface responses.
Every modem's web UI is different — different page structures, different
data formats, different field names — but the output is always the same:
channels with frequency, power, SNR, and error counts.

The parsing system absorbs this variety through six extraction formats,
each implemented by a strategy class that knows how to extract data from
one response format. `parser.yaml` declares the format and field mappings
per data section. `parser.py` handles modem-specific quirks that can't
be expressed declaratively.

**Design principles:**
- parser.yaml is required — every modem package must have one
- parser.yaml is the primary expression mode — code is the escape hatch
- parser.yaml drives the fetch list — the orchestrator reads it to know what resources to load
- Format selection is per-section, not per-modem — a modem can mix formats
- Strategies are format experts, not modem experts
- Capabilities are implicit from mappings — no separate declarations
- Parsers are pure functions — no network calls, no auth, no session state

---

## Two Layers: Paradigm and Format

**Paradigm** (modem.yaml) controls *how data is fetched* — the resource
loader. It determines the transport and the value types in the resource
dict.

**Format** (parser.yaml, per-section) controls *how data is extracted* —
the extraction strategy. Each section (`downstream`, `upstream`,
`system_info`) declares its own format independently.

```
modem.yaml paradigm → resource loader (how to fetch)
parser.yaml format  → extraction strategy (how to extract, per-section)
```

These are orthogonal. An HTML page can contain standard tables,
transposed tables, JavaScript variables, or even JSON blobs. The
paradigm says "fetch this page as HTML," but downstream extraction might
use `table` format while system_info uses `javascript` format.

### Extraction Formats

| Format | Strategy | Extracts from | Scope |
|--------|----------|---------------|-------|
| **HTML** | | | |
| `table` | HTMLTableStrategy | `<table>` elements, rows=channels, cols=metrics | any section |
| `table_transposed` | HTMLTableTransposedStrategy | `<table>` elements, rows=metrics, cols=channels | any section |
| `html_fields` | HTMLFieldsStrategy | Named fields in HTML via label text or element id | system_info only |
| **HTML (embedded JS)** | | | |
| `javascript` | JSEmbeddedStrategy | Delimited strings in JS variables/functions | any section |
| **JSON** | | | |
| `hnap` | HNAPStrategy | Delimiter-separated values in HNAP JSON responses | any section |
| `json` | RESTStrategy | JSON response structures via field paths | any section |

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

**Strategy classes live in Core.** They consume parser.yaml config and
provide overridable leaf methods. Adding a modem never requires changing
a strategy — if it does, the strategy is missing a config field.

---

## Resource Dict

The resource dict is the contract between the resource loader and the
parser. It contains pre-fetched response data keyed by resource
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
`GetMultipleHNAPs` request. The `response_key` values map to
`hnap_actions` entries in modem.yaml.

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

**parser.yaml never contains auth, pages, session config, or metadata.**

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

### HTMLTableStrategy

Extracts data from `<table>` elements where rows are channels and
columns are fields. Supports one or more tables per data section —
multiple tables are concatenated into a single channel list.

#### Single table with mixed channel types

SC-QAM and OFDM channels are mixed in one table. The strategy
classifies each row by an indicator field:

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
        default: "scqam"
        ofdm_indicator:
          field: modulation
          value: "Other"
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
        fixed: "scqam"
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
| `format` | string | yes | `table` — selects HTMLTableStrategy |
| `resource` | string | yes | URL path key in the resource dict |
| `tables` | list | yes | One or more table definitions (concatenated in order) |
| `tables[].selector` | object | yes | How to find the table in the page |
| `tables[].selector.type` | string | yes | `header_text`, `css`, `id`, `nth` |
| `tables[].selector.match` | string | yes | Search value (text, CSS selector, ID, or index) |
| `tables[].skip_rows` | integer | no | Number of header rows to skip (default 0) |
| `tables[].columns` | list | yes | Ordered column→field mappings |
| `tables[].columns[].index` | integer | yes | Column position (0-based) |
| `tables[].columns[].field` | string | yes | Canonical output field name |
| `tables[].columns[].type` | string | yes | Field type (see table above) |
| `tables[].columns[].unit` | string | no | Unit suffix to strip |
| `tables[].channel_type` | object | no | Channel type: `fixed` or indicator-based |
| `tables[].filter` | object | no | Row filter rules |

**Table selector types:**

| Type | Behavior | Example |
|------|----------|---------|
| `header_text` | Find `<th>` or `<td>` containing text, return parent `<table>` | `"Downstream Bonded Channels"` |
| `css` | CSS selector returning a `<table>` element | `"table.moto-table-content"` |
| `id` | Table element with matching `id` attribute | `"dsTable"` |
| `nth` | Nth `<table>` element on the page (0-based) | `2` |

### HTMLTableTransposedStrategy

Extracts data from `<table>` elements where rows are metrics and
columns are channels. The strategy pivots the data — for each column
index, it collects values from all metric rows to build one channel.

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
    default: "scqam"
```

**Config fields (differs from HTMLTableStrategy):**

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `format` | string | yes | `table_transposed` — selects HTMLTableTransposedStrategy |
| `resource` | string | yes | URL path key in the resource dict |
| `selector` | object | yes | How to find the table (same types as HTMLTableStrategy) |
| `rows` | list | yes | Row label→field mappings (replaces `columns`) |
| `rows[].label` | string | yes | Row header text to match |
| `rows[].field` | string | yes | Canonical output field name |
| `rows[].type` | string | yes | Field type (see Common Concepts) |
| `rows[].unit` | string | no | Unit suffix to strip |
| `channel_type` | object | no | Channel type detection rules |

The strategy scans table rows for matching labels, builds a
`{label: [values]}` map, then iterates column indices to assemble
channels. Channel count is inferred from the number of values in any
mapped row.

**Error stats from a separate table** require parser.py — the base
strategy handles one table per data section. parser.py merges error
stats by overriding `parse_downstream` to call `super()` and then
enrich channels with data from a second table.

### JSEmbeddedStrategy

Extracts data from JavaScript variables embedded in HTML pages. The
source data is a delimited string inside a JS function body.

```yaml
# parser.yaml — JS-embedded delimited strings, multiple functions per section
downstream:
  format: javascript
  resource: "/DocsisStatus.htm"
  functions:
    - name: "InitDsTableTagValue"
      channel_type: "scqam"
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
| `format` | string | yes | `javascript` — selects JSEmbeddedStrategy |
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

### HNAPStrategy

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
    default: "scqam"
    ofdm_indicator:
      index: 2
      value: "OFDM"
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
    default: "atdma"
    ofdma_indicator:
      index: 2
      value: "OFDMA"
```

**Config fields:**

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `format` | string | yes | `hnap` — selects HNAPStrategy |
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

### RESTStrategy

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
    default: "scqam"
    ofdm_indicator:
      key: "channelType"
      value: "ofdm"

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
| `format` | string | yes | `json` — selects RESTStrategy |
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
      response_key: "GetArrisDeviceStatusResponse"
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

**HTML — label-based fields from multiple pages (MB7621):**

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

**HTML — id-based fields with regex extraction (CM600):**

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

**Mixed formats — html_fields + JS variables (CM600):**

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

**REST — single source (SuperHub5):**

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

The strategy processes each source in order and merges the resulting
dicts. If two sources extract the same field name, the later source
wins (last-write-wins). In practice, fields should not overlap — each
source owns distinct fields.

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
because the strategy tries multiple structural patterns. New patterns
added to the cascade benefit all modems without config changes.

System info fields are open-ended — modems expose different fields.
The strategy extracts whatever is declared in parser.yaml. Fields not
declared are not extracted (implicit capabilities).

---

## parser.py — Code Override Hooks

parser.py handles modem-specific quirks that can't be expressed
declaratively in parser.yaml. It extends `ModemParser` (the base class
in Core) and overrides leaf methods for specific data sections.

Since format selection is per-section in parser.yaml, parser.py no
longer inherits from a specific strategy class. Instead, it extends
`ModemParser` and overrides only the sections that need code.
`parse_resources()` dispatches each section to the format-appropriate
strategy (from parser.yaml) or to the parser.py override — whichever
applies.

### When to Use parser.py

- Multi-table merging (error stats from a separate table)
- Complex uptime/boot time string parsing
- Restart window filtering (needs runtime state)
- Frequency range→center conversion
- Any extraction that requires conditional logic beyond simple filtering

### Override Contract

```python
class ExampleModemParser(ModemParser):
    """Override specific sections. Sections not overridden here
    are handled declaratively by parser.yaml.

    Naming convention: {Manufacturer}{Model}Parser
    or {Manufacturer}{Model}{Paradigm}Parser for disambiguation.
    """

    def parse_downstream(self, resources: dict[str, Any]) -> list[dict]:
        """Override to merge error stats from a separate table."""
        # Call super() for the standard parser.yaml-driven path
        channels = super().parse_downstream(resources)
        # Enrich with error stats from a second table
        error_stats = self._parse_error_table(resources)
        return self._merge_error_stats(channels, error_stats)

    def parse_system_info(self, resources: dict[str, Any]) -> dict:
        """Override for non-standard system info layout."""
        # Completely replace the standard path
        soup = resources.get("/network_setup.jst")
        return self._extract_system_info(soup)

    # parse_upstream is NOT overridden — parser.yaml handles it
```

### Rules

1. **Override leaf methods, not the pipeline.** Override
   `parse_downstream`, `parse_upstream`, `parse_system_info` — never
   `parse_resources` (the orchestration method).

2. **Call `super()` when extending, not replacing.** If the standard
   parser.yaml path handles 80% of the work, call `super()` and enrich
   the result. Only skip `super()` when the standard path doesn't apply.

3. **No network calls.** parser.py receives the pre-fetched resource
   dict. No session, no HTTP client, no auth awareness. If a parser
   needs data from a URL not in the resource dict, add a `resource`
   reference in parser.yaml — the orchestrator will include it in the
   fetch list automatically.

4. **No auth or session state.** Parsers are pure data extractors.
   Infrastructure like HNAP builders, session tokens, and cookies flow
   through the orchestrator, not through the parser.

5. **Graduate recurring patterns.** When the same override appears in
   3+ modems, it becomes a parser.yaml config field and the overrides
   are deleted. parser.py is for genuine one-offs.

### What parser.py Returns

The same structure as parser.yaml-driven extraction:

```python
# parse_downstream / parse_upstream → list of channel dicts
[
    {
        "channel_id": 1,
        "lock_status": "Locked",
        "modulation": "QAM256",
        "channel_type": "scqam",
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

### Mixing parser.yaml and parser.py

Each section (`downstream`, `upstream`, `system_info`) is resolved
independently. parser.py overrides take precedence over parser.yaml
for the same section.

```
For each section (downstream, upstream, system_info):
  parser.py overrides this section?
    └─ Yes → use parser.py override
       └─ Override calls super()? → super() runs parser.yaml path
    └─ No  → parser.yaml has mapping for this section?
       └─ Yes → use format-driven declarative extraction
       └─ No  → no data for this section (no capability)
```

A modem can freely mix across sections:
- **100% parser.yaml** — all sections are declarative
- **100% parser.py** — all sections are code overrides
- **Mixed** — parser.yaml handles some sections, parser.py others
- **Mixed within a section** — parser.py overrides `parse_downstream`,
  calls `super()` for the declarative base, then enriches the result

---

## Output Contract

All strategies and parser.py overrides produce the same `ModemData`
shape. This is the contract between parsing and everything downstream
(entities, diagnostics, HA sensors).

Channel dicts and system_info are open — canonical fields are guaranteed,
but any additional field mapped in parser.yaml or extracted by parser.py
passes through without core changes. This lets modems expose values like
`channel_width`, `active_subcarriers`, `temperature`, or `fft_size`
without modifying Core or the strategy base class.

```python
{
    "downstream": [
        {
            # Canonical fields (Core understands these)
            "channel_id": int,         # DOCSIS channel ID
            "lock_status": str,        # "Locked" | "Not Locked"
            "modulation": str,         # "QAM256", "OFDM", etc.
            "channel_type": str,       # "scqam" | "ofdm"
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
- `channel_type` uses canonical values: `scqam`, `ofdm`, `atdma`, `ofdma`
- `frequency` is always in Hz (strategies normalize from MHz/GHz)
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

See [FIELD_REGISTRY.md](../../cable_modem_monitor_catalog/docs/FIELD_REGISTRY.md)
for the complete registry, graduation criteria, and naming rules.

### Capabilities Are Implicit

The presence of data in the output IS the capability declaration:

- Downstream channels in output → `scqam_downstream` capability
- OFDM channels in output → `ofdm_downstream` capability
- `system_uptime` in system_info → `system_uptime` capability

No separate capabilities list in modem.yaml. No registration. If the
parser extracts it, the entity exists.

---

## Channel Type Detection

Modems report channel types differently. The strategy needs to classify
each channel as one of four canonical types: `scqam`, `ofdm`, `atdma`,
`ofdma`.

parser.yaml supports two detection mechanisms:

### Indicator Field

A field value signals the channel type:

```yaml
channel_type:
  default: "scqam"
  ofdm_indicator:
    field: modulation       # or index/key depending on strategy
    value: "Other"          # match value
```

If the indicator field matches the value, the channel is classified as
the OFDM variant. Otherwise, the default applies.

### Explicit Field

The source data has a channel type field:

```yaml
columns:
  - index: 3
    field: channel_type
    type: string
```

The strategy normalizes source values to canonical types. Common
normalizations: `"SC-QAM"` → `"scqam"`, `"OFDM"` → `"ofdm"`,
`"ATDMA"` → `"atdma"`, `"OFDMA"` → `"ofdma"`.

---

## Performance Characteristics

| Phase | Cost | Scale factor |
|-------|------|--------------|
| parser.yaml load | Read + parse one YAML file | Once at startup |
| Strategy instantiation | In-memory, no I/O | Once at startup |
| `parse_resources()` | CPU-bound HTML/JSON parsing | Per poll cycle |
| Field extraction | String splits, type casts | O(channels × fields) |

Parsing is CPU-bound and fast (< 100ms for the largest modems with 32+
channels). The bottleneck is always the HTTP fetch, not the parse.

Parser and strategy instances are created once at startup and reused
every poll cycle.
