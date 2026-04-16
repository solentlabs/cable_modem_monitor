# Table Format Specification

> Parent spec: [PARSING_SPEC.md](PARSING_SPEC.md) — common concepts, output contract, channel type detection

This specification covers the two HTML table format parsers
(`HTMLTableParser` and `HTMLTableTransposedParser`) and the companion
table merging mechanism (`merge_by`) used to join split channel data.

## Contents

| Section | What it covers |
| ------- | -------------- |
| [HTMLTableParser](#htmltableparser) | Standard row-per-channel tables, selectors, column mappings |
| [HTMLTableTransposedParser](#htmltabletransposedparser) | Transposed tables (rows are metrics, columns are channels) |
| [Companion Tables (merge\_by)](#companion-tables-merge_by) | Joining split channel data from multiple tables |

## HTMLTableParser

Extracts data from `<table>` elements where rows are channels and
columns are fields. Supports one or more tables per data section —
multiple tables are concatenated into a single channel list.

### Single table with mixed channel types

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
      row_start: 1
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

### Separate tables per channel type

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
      row_start: 1
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
      row_start: 1
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

### Upstream example

```yaml
upstream:
  format: table
  resource: "/cmconnectionstatus.html"
  tables:
    - selector:
        type: header_text
        match: "Upstream Bonded Channels"
      row_start: 1
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
| `tables[].row_start` | integer | no | 0-based index of the first data row (default 0) |
| `tables[].columns` | list | yes | Ordered column→field mappings |
| `tables[].columns[].index` | integer | yes | Column position (0-based) |
| `tables[].columns[].field` | string | yes | Canonical output field name |
| `tables[].columns[].type` | string | yes | Field type (see table above) |
| `tables[].columns[].unit` | string | no | Unit suffix to strip |
| `tables[].columns[].pattern` | string | no | Regex with a capture group — applied to cell text before type conversion. Extracts a substring (e.g., `"(\\d+)"` to pull a number from `"1 QAM256"`). |
| `tables[].columns[].map` | dict | no | Value mapping (exact match, applied before type conversion) |
| `tables[].channel_type` | object | no | Channel type: `fixed`, `map`, or explicit field |
| `tables[].filter` | object | no | Row filter rules |
| `tables[].merge_by` | list[string] | no | Merge into primary channels by these key fields instead of concatenating. See [Companion Tables](#companion-tables-merge_by). |

**Table selector types:**

| Type | Behavior | Example |
|------|----------|---------|
| `header_text` | Find `<th>` or `<td>` containing text (case-insensitive substring), return parent `<table>` | `"SNR"` |
| `css` | CSS selector; returns element if `<table>`, otherwise walks to parent `<table>` | `"table.channel-data"` |
| `id` | Element with matching `id` attribute; returns if `<table>`, otherwise walks to parent | `"dsTable"` |
| `nth` | Nth `<table>` on the page (0-based). Fragile — use as last resort | `2` |
| `attribute` | Element with matching HTML attributes; returns if `<table>`, otherwise walks to parent | `{"data-section": "downstream"}` |

All selectors support an optional `fallback` — another selector tried
if the primary returns no match:

```yaml
selector:
  type: id
  match: "dsTable"
  fallback:
    type: header_text
    match: "SNR"
```

**Choosing a selector:**

Use **`id`** when the table has a unique `id` attribute. Common on
Netgear (`dsTable`, `usTable`), Arris (`CustomerConnDownstreamChannel`),
and Hitron (`cmdocsisdsTb`) modems. Most reliable — no ambiguity.

Use **`header_text`** when the table has no `id`. Match on **column
header text** that is unique to the target table on the page. Section
titles (e.g., "Downstream Bonded Channels") often live outside the
data table — in wrapper elements, preceding headings, or sibling title
tables — and will not match. Column headers are always inside the data
table and are the most reliable self-identifying feature across all
known modem HTML structures.

Examples of good `header_text` selectors:

- `"SNR"` — matches `"SNR (dB)"` header, unique to downstream tables
- `"Symb. Rate"` — matches `"Symb. Rate (Ksym/sec)"`, unique to upstream
- `"Channel Width"` — unique to OFDM tables

Use **`css`** when neither `id` nor `header_text` can disambiguate —
e.g., when a table has a unique CSS class.

Use **`nth`** only as a last resort — it depends on table position
in the HTML, which can change across firmware versions.

**Wrapper cell filtering:** The `header_text` selector skips cells
that contain nested `<table>` elements. These are layout wrapper
cells whose `get_text()` includes descendant text from nested tables.
Without this filter, a wrapper `<td>` containing a data table would
match before the actual header cells inside it.

## HTMLTableTransposedParser

Extracts data from `<table>` elements where rows are metrics and
columns are channels. The strategy pivots the data — for each column
index, it collects values from all metric rows to build one channel.

### Single table (flat config)

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

### Multiple tables with companion merge

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
| `rows[].map` | dict | no | Value mapping (exact match, applied before type conversion) |
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

## Channel Number Assignment

Both `HTMLTableParser` and `HTMLTableTransposedParser` auto-assign
`channel_number` from the 1-based row (or column) position when it
is not already present on the channel dict — i.e., when parser.yaml
does not map a column to `field: channel_number`.

When parser.yaml maps a column to `channel_number`, the modem-provided
value is used as-is. This covers modems that include an explicit
position column (e.g., MB7621 "Channel", TC4400 "Channel Index").
For columns containing mixed text (e.g., CM3500B "1 QAM256"), use
the `pattern` field to extract the number:

```yaml
- index: 0
  field: channel_number
  type: integer
  pattern: "(\\d+)"
```

Auto-assignment happens after companion table merging, so the final
channel list has stable 1-based positions. See
[CHANNEL_IDENTIFICATION_SPEC.md](CHANNEL_IDENTIFICATION_SPEC.md) §10.
