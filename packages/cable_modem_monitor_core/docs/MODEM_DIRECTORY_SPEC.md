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
        ├── modem.yaml              # REQUIRED: identity, auth, pages, metadata (single-variant)
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

Declarative extraction config consumed by the strategy base class. Defines
field mappings that tell the strategy how to extract data from resources:

- Table selectors (CSS selector or string match to find the right table)
- Column/field mappings (which column is frequency, power, SNR)
- Table layout (standard rows=channels or transposed rows=metrics)
- JS variable names and delimiters (for JSEmbedded strategy)
- JSON field paths (for REST strategy)
- HNAP field/record delimiters (for HNAP strategy)

**Capabilities are implicit.** The presence of a mapping IS the capability
declaration. A downstream channel mapping = `scqam_downstream` capability.
No mapping = no capability = no entity created in HA.

**parser.yaml never contains auth, pages, or metadata.**

### parser.py (Parsing — code overrides)

Extends the strategy base class selected by the paradigm. Overrides leaf
methods for modem-specific quirks that can't be expressed in parser.yaml.

A modem needs at least one of parser.yaml or parser.py. They can be mixed —
parser.yaml handles standard pages, parser.py overrides for non-standard
ones. The implementer decides where to draw the line per-page or per-field.

**Rules:**
- Override leaf methods (`parse_downstream`, `parse_system_info`), not
  the pipeline
- Always call `super()` for the standard path
- When a pattern recurs across 3+ modems, it graduates to a parser.yaml
  config field and the overrides are deleted
- Base class only passes pre-fetched resources — no session, no HTTP client

**parser.py never contains auth, pages, or metadata.**

### modem.yaml / modem-{variant}.yaml (Required)

Everything about the modem except parsing. Each file represents one
firmware variant that a user can select during config flow.

Contains:
- `manufacturer`, `model` — identity (must match across variants)
- `model_aliases` — alternative model names for config flow search (e.g., `XB7` for `cgm4981com`)
- `brands` — product branding for config flow search (e.g., `Xfinity`, `Surfboard`)
- `paradigm` — html, hnap, rest_api
- `auth` — single auth strategy config (includes login URLs)
- `hardware` — DOCSIS version, chipset, release date
- `default_host` — default modem IP
- `session` — cookie name, logout endpoint, concurrency
- `status_info` — per-variant verification status
- `attribution` — per-variant contributors
- `isps` — ISPs known to use this variant
- `notes`, `references` — per-variant documentation

**modem.yaml never contains extraction logic (field mappings, column
indices, table selectors, delimiters).**

**Single-variant modems** use just `modem.yaml`.

**Multi-variant modems** use `modem-{variant}.yaml` files — one per auth
variant. Fields that are shared across variants (paradigm, pages,
hardware) are duplicated in each file. This is intentional — each
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
  The S33 and S33v2 share identical auth (both MD5 HMAC) and page
  structure. `modem-s33v2.har` validates the same `modem.yaml` against
  a different firmware build.

- **Model aliases** — different model numbers, same platform and web UI.
  XB5/XB6/XB7 are all Technicolor CGM4981COM variants with the same
  interface. `modem-xb5.har` and `modem-xb6.har` validate that the
  shared config works across model numbers. Golden files may differ
  (different channel counts, firmware strings) but the pipeline and
  config are identical.

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

## Paradigm Boundary

**Same paradigm = same directory.** Auth variants that share a paradigm
(and therefore share parser config) belong in one directory.

**Different paradigm = different directory.** If a model number has
firmware variants that use different paradigms (e.g., SB8200 HTML vs
SB8200v3 HNAP), they are separate directories because they need
fundamentally different parser configs.

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
   field names. This is confirmed across all current multi-variant
   modems: SB8200 (none vs url_token), SB6190 (none vs form_nonce),
   CM1200 (none vs basic).

**When this breaks:** If a firmware variant changes the *data page
structure* (different tables, different columns, different endpoints),
it needs a different parser — which means a different directory. In
practice this only happens with paradigm-level differences (HTML vs
HNAP), not auth-level differences.

**Validation:** Catalog HAR replay tests verify this per-variant.
Each variant's HAR replays through the shared parser.yaml and the
output is compared against a reviewed golden file. If a future
variant changes response structure, the golden file test catches it.

---

## Examples

**Motorola MB7621 (single variant, form auth, mixed parsing)**
```
modems/motorola/mb7621/
├── parser.yaml           # table selectors, column mappings
├── parser.py             # override for non-standard system_info page
├── modem.yaml            # paradigm, auth: form, pages, metadata
└── tests/
    ├── modem.har
    └── modem.expected.json
```

**Arris SB8200 (multi-variant, same paradigm)**
```
modems/arris/sb8200/
├── parser.yaml           # table selectors, column mappings (shared)
├── parser.py             # shared parser overrides
├── modem.yaml            # auth: none (HTTP, default variant)
├── modem-url-token.yaml  # auth: url_token (login_ prefix, ct_ tokens)
├── modem-cookie.yaml     # auth: url_token (no prefix, cookie-only)
└── tests/
    ├── modem.har
    ├── modem.expected.json
    ├── modem-url-token.har
    ├── modem-url-token.expected.json
    ├── modem-cookie.har
    └── modem-cookie.expected.json
```

**Arris S33 (HNAP, single variant, 100% parser.yaml)**
```
modems/arris/s33/
├── parser.yaml           # HNAP delimiters, field mappings
├── modem.yaml            # paradigm: hnap, auth, pages, metadata
└── tests/
    ├── modem.har
    ├── modem.expected.json
    ├── modem-s33v2.har
    └── modem-s33v2.expected.json
```

**Netgear CM1200 (multi-variant, 100% parser.py)**
```
modems/netgear/cm1200/
├── parser.py             # JSEmbedded extraction too complex for declarative
├── modem-noauth.yaml     # auth: none
├── modem-basic.yaml      # auth: basic (challenge_cookie)
└── tests/
    ├── modem.har
    ├── modem.expected.json
    ├── modem-basic.har
    └── modem-basic.expected.json
```
