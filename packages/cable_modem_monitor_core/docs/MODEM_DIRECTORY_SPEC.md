# Modem Directory Structure

Each supported modem has a directory under `modems/{manufacturer}/{model}/`
inside the `solentlabs-cable-modem-monitor-catalog` package.

**Design principles:**
- Single source of truth — all modem-specific files in one location
- Self-contained — everything needed to test a modem is in its directory
- Drop-in — add a directory, no registration or changes elsewhere

---

## Directory Structure

```
modems/
└── {manufacturer}/
    └── {model}/
        ├── parser.yaml             # Declarative extraction config (at least one of parser.yaml/parser.py required)
        ├── parser.py               # Code override hooks (at least one of parser.yaml/parser.py required)
        ├── modem.yaml              # REQUIRED: identity, auth, metadata (single-variant)
        ├── modem-{variant}.yaml    # OPTIONAL: per-variant identity, auth, metadata (multi-variant)
        └── tests/                  # REQUIRED: HAR captures + expected output golden files
            ├── modem.har                  # Primary capture
            ├── modem.expected.json        # Expected ModemData output for primary capture
            ├── modem-{variant}.har        # OPTIONAL: variant captures
            └── modem-{variant}.expected.json  # Expected output for variant capture
```

---

## Files

### parser.yaml (Parsing — declarative)

Declarative extraction config consumed by `BaseParser` implementations.
Defines field mappings that tell the parser how to extract data from
resources:

- Table selectors (CSS selector or string match to find the right table)
- Column/field mappings (which column is frequency, power, SNR)
- Table layout (standard rows=channels or transposed rows=metrics)
- Companion table merging (`merge_by` — join fields from a separate
  table into primary channels by key fields)
- JS variable names and delimiters (for JSEmbedded strategy)
- JSON field paths (for json format)
- HNAP field/record delimiters (for HNAP strategy)

**Capabilities are implicit.** The presence of a mapping IS the capability
declaration. A downstream channel mapping = `qam_downstream` capability.
No mapping = no capability = no entity created in HA.

**parser.yaml never contains auth or metadata.**

### parser.py (Parsing — optional post-processor)

Optional post-processing hooks for modem-specific quirks that can't be
expressed in parser.yaml. Not a subclass — a plain class with hook
methods (`parse_downstream`, `parse_upstream`, `parse_system_info`)
that the `ModemParserCoordinator` invokes after `BaseParser` extraction.

Each hook receives the `BaseParser` extraction output plus the raw
resources, and returns the final section data. See PARSING_SPEC.md for
the full post-processing contract.

At least one of parser.yaml or parser.py is required. They can be
mixed — parser.yaml handles standard extraction, parser.py
post-processes sections that need code. When extraction is too complex
for declarative config, parser.py alone is valid (see Examples).

**Rules:**
- Define per-section hooks (`parse_downstream`, `parse_system_info`),
  not a modem-level method — the coordinator owns the pipeline
- When a pattern recurs across 3+ modems, it graduates to a parser.yaml
  config field and the hooks are deleted
- No network calls — only pre-fetched resources are available

**parser.py never contains auth or metadata.**

### modem.yaml / modem-{variant}.yaml (Required)

Everything about the modem except parsing. Each file represents one
firmware variant that a user can select during config flow.

Contains:
- `manufacturer`, `model` — identity (must match across variants)
- `model_aliases` — alternative model names for config flow search (e.g., `XB7` for `cgm4981com`)
- `brands` — product branding for config flow search (e.g., `Xfinity`, `Surfboard`)
- `transport` — http, hnap
- `auth` — single auth strategy config (includes login URLs)
- `hardware` — DOCSIS version, chipset, release date
- `default_host` — default modem IP
- `session` — cookie name, concurrency, headers
- `status` — per-variant verification status
- `attribution` — per-variant contributors
- `isps` — ISPs known to use this variant
- `notes`, `references` — per-variant documentation

**modem.yaml never contains extraction logic (field mappings, column
indices, table selectors, delimiters).**

**Single-variant modems** use just `modem.yaml`.

**Multi-variant modems** use `modem-{variant}.yaml` files — one per auth
variant. Fields that are shared across variants (transport, hardware) are duplicated in each file. This is intentional — each
variant file is a complete modem config (except parsing), not a fragment.

**`modem.yaml` is the default variant.** Multi-variant modems may also
have a `modem.yaml` alongside `modem-{variant}.yaml` files. This is the
default variant — the one loaded when no variant is specified. When a
single-variant modem is later split into multiple variants, the original
behavior stays as `modem.yaml` and new variants get named suffixes. This
ensures existing config entries (with `variant: null`) continue to work
without migration. **When splitting, never delete or rename `modem.yaml`.**

Files sharing the same `model` field group under one dropdown entry in the
config flow. Variant selection happens on Step 2 (see
`CONFIG_FLOW_SPEC.md`).

### tests/ Directory (Required)

Test fixtures — HAR captures (pipeline input) and expected output golden
files (pipeline assertions). No test code lives here — the test harness
in Core discovers and consumes these files.

**File naming:**

| File | Description |
|------|-------------|
| `modem.har` | Primary/default HAR capture |
| `modem.expected.json` | Expected `ModemData` output for `modem.har` |
| `modem-{name}.har` | Additional HAR captures (variant or compatibility) |
| `modem-{name}.expected.json` | Expected output for that capture |

Each `{name}.har` pairs with `{name}.expected.json`. The test harness
discovers HAR files, locates the matching golden file, resolves which
`modem*.yaml` applies, and runs the full pipeline against a mock server.

**Config resolution for HAR files:**

1. `modem.har` → always uses `modem.yaml`
2. `modem-{name}.har` → look for `modem-{name}.yaml`
   - Found → use it (this is a distinct auth variant)
   - Not found → fall back to `modem.yaml` (this is a compatibility test)

**Two use cases for multiple HARs against one config:**

- **Firmware compatibility** — same model, different firmware revisions.
  Two hardware revisions share identical auth and page structure.
  `modem-{revision}.har` validates the same `modem.yaml` against a
  different firmware build.

- **Model aliases** — different model numbers, same platform and web UI.
  A manufacturer reuses the same web interface across several model
  numbers. `modem-{alias}.har` validates that the shared config works
  across models. Golden files may differ (different channel counts,
  firmware strings) but the pipeline and config are identical.

**HAR sanitization** happens at capture time. HAR files committed to
the repo must have PII scrubbed — passwords, MAC addresses, serial
numbers, IP addresses.

**Golden file lifecycle:**
1. Contributor submits HAR capture via `har-capture`
2. Skill/MCP generates modem.yaml, parser.yaml, and parser.py if needed
3. First pipeline run against HAR mock server produces `ModemData` output
4. Developer reviews output against raw HAR responses
5. Reviewed output is committed as `{name}.expected.json`
6. All future runs are regression tests against the golden file

---

## Config Assembly

The loader assembles a complete modem config from two sources:

```
modem.yaml       +  parser.yaml  →  complete config (single-variant)
modem-noauth.yaml + parser.yaml  →  complete config (variant 1)
modem-basic.yaml  +  parser.yaml  →  complete config (variant 2)
```

**Assembly rules:**
1. Each `modem*.yaml` is a near-complete config (everything except parsing)
2. `parser.yaml` provides the extraction mappings (and implicitly, capabilities)
3. The assembled result must pass the full Pydantic schema
4. All variants must declare the same `model` value
5. If parser.yaml is absent, parser.py must provide all extraction logic

**No merge conflicts possible.** modem.yaml and parser.yaml own disjoint
concerns — there's nothing to override or deep-merge. The loader combines
them, not overlays one onto the other.

---

## Transport Boundary

**Same transport = same directory.** Auth variants that share a transport
(and therefore share parser config) belong in one directory.

**Different transport = different directory.** If a model number has
firmware variants that use different transports (e.g., HTTP vs HNAP),
they are separate directories because they need fundamentally different
parser configs.

### Why shared parser.yaml is safe across auth variants

Auth variants change *how you authenticate*, not *what the response
looks like*. This is structurally guaranteed by two design decisions:

1. **Resource dict keys are path-only.** Keys never include query
   strings, headers, or credentials (see RESOURCE_LOADING_SPEC.md).
   Auth strategies that modify the URL (e.g., `url_token` appending
   `?ct_<token>`) affect the HTTP request, not the resource dict key.
   All variants produce the same keys for the same parser.yaml.

2. **Auth gates the page, not its structure.** Firmware variants
   change the authentication gate (login form, HTTP Basic challenge,
   token requirement) but serve identical HTML/JSON behind that gate.
   The same `<table>` structure, the same column layout, the same
   field names. This holds across all current multi-variant modems.

**When this breaks:** If a firmware variant changes the *data page
structure* (different tables, different columns, different endpoints),
it needs a different parser — which means a different directory. In
practice this only happens with transport-level differences (HTTP vs
HNAP), not auth-level differences.

**Validation:** Catalog HAR replay tests verify this per-variant.
Each variant's HAR replays through the shared parser.yaml and the
output is compared against a reviewed golden file. If a future
variant changes response structure, the golden file test catches it.

---

## Examples

**Single variant, parser.yaml + parser.py**
```
modems/{manufacturer}/{model}/
├── parser.yaml           # declarative extraction config
├── parser.py             # post-processor for quirks
├── modem.yaml            # transport, auth, metadata
└── tests/
    ├── modem.har
    └── modem.expected.json
```

**Multi-variant, shared transport**
```
modems/{manufacturer}/{model}/
├── parser.yaml           # shared extraction config
├── parser.py             # shared post-processor
├── modem.yaml            # default variant (e.g., auth: none)
├── modem-{variant}.yaml  # additional variant (e.g., different auth)
├── modem-{variant}.yaml  # another variant
└── tests/
    ├── modem.har
    ├── modem.expected.json
    ├── modem-{variant}.har
    ├── modem-{variant}.expected.json
    ├── modem-{variant}.har
    └── modem-{variant}.expected.json
```

**HNAP, single variant, 100% parser.yaml**
```
modems/{manufacturer}/{model}/
├── parser.yaml           # HNAP delimiters, field mappings
├── modem.yaml            # transport: hnap, auth, metadata
└── tests/
    ├── modem.har
    ├── modem.expected.json
    ├── modem-{compat}.har          # firmware compatibility test
    └── modem-{compat}.expected.json
```

**Multi-variant, 100% parser.py**
```
modems/{manufacturer}/{model}/
├── parser.py             # extraction too complex for declarative config
├── modem-{variant}.yaml  # variant 1
├── modem-{variant}.yaml  # variant 2
└── tests/
    ├── modem.har
    ├── modem.expected.json
    ├── modem-{variant}.har
    └── modem-{variant}.expected.json
```
