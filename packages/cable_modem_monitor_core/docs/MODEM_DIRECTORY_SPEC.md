# Modem Directory Structure

Each supported modem has a directory under `modems/{manufacturer}/{model}/`
inside the `solentlabs-cable-modem-monitor-catalog` package.

**Design principles:**

- Single source of truth — all modem-specific files in one location
- Self-contained — everything needed to test a modem is in its directory
- Drop-in — add a directory, no registration or changes elsewhere

---

## Directory Structure

To support scaling to hundreds of modems, the catalog uses a
**Manufacturer-based Hierarchy**. This allows for "Lazy Loading"
during the Home Assistant config flow — only fetching the models
for a selected manufacturer rather than scanning the entire tree at
startup.

```text
modems/
└── {manufacturer}/
    ├── (metadata.json)             # Optional manufacturer-wide metadata
    └── {model}/
        ├── parser.yaml             # Declarative extraction config
        ├── parser.py               # Code override hooks
        ├── modem.yaml              # REQUIRED: identity, auth, metadata
        ├── modem-{variant}.yaml    # OPTIONAL: per-variant identity, auth, metadata
        └── test_data/              # REQUIRED: HAR captures + expected output
            ├── modem.har                  # Primary capture
            ├── modem.expected.json        # Expected ModemData output
            ├── modem-{variant}.har        # OPTIONAL: variant captures
            └── modem-{variant}.expected.json  # Expected output for variant
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
- `model_aliases` — internal or rebranded names for search matching, not shown in the config flow UI (e.g., `CGM4140COM` for XB6). See `MODEM_YAML_SPEC.md` § Aliases vs Separate Entries.
- `brands` — product branding for config flow search (e.g., `Xfinity`, `Surfboard`)
- `transport` — http, hnap
- `auth` — single auth strategy config (includes login URLs)
- `hardware` — DOCSIS version, chipset, release date
- `default_host` — default modem IP
- `session` — cookie name, concurrency, headers
- `status` — verification status (see [Verification Status](#verification-status))
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

### test_data/ Directory (Required)

Test fixtures — HAR captures (pipeline input) and expected output golden
files (pipeline assertions). No test code lives here — the test harness
in Core discovers and consumes these files.

**File naming:**

| File | Description |
|------|-------------|
| `modem.har` | Primary/default HAR capture |
| `modem.expected.json` | Expected `ModemData` output for `modem.har` |
| `modem.verified.json` | Real hardware verification artifact (see [Verification Status](#verification-status)) |
| `modem-{name}.har` | Additional HAR captures (variant or compatibility) |
| `modem-{name}.expected.json` | Expected output for that capture |
| `modem-{name}.verified.json` | Variant verification artifact |

Each `{name}.har` pairs with `{name}.expected.json`. The test harness
discovers HAR files, locates the matching golden file, resolves which
`modem*.yaml` applies, and runs the full pipeline against the `HARMockServer`.

**Config resolution for HAR files** (most specific wins):

1. **Exact match:** `modem-form-nonce-b64.yaml`
2. **Stem walk:** strip trailing `-segment` and retry →
   `modem-form-nonce.yaml`, then `modem-form.yaml`, etc.
3. **Fallback:** `modem.yaml`

Stem walking supports **test variants** — multiple HARs that share
one config but exercise different firmware behaviour detected at
runtime. For example, `modem-form-nonce-b64.har` tests a firmware
that base64-encodes credentials, but the auth config is identical
to `modem-form-nonce.yaml` because the encoding is auto-detected
from the login page.

**Distinction:** A `modem-{name}.yaml` file means a distinct
**config variant** (different auth strategy, different fields).
A `modem-{name}.har` without a matching YAML means a **test
variant** (same config, different firmware behaviour). Stem walking
connects test variants to their config.

Different model numbers that share a platform get their own catalog
directories, not shared HARs. See `MODEM_YAML_SPEC.md` § Aliases vs
Separate Entries.

**HAR sanitization** happens at capture time. HAR files committed to
the repo must have PII scrubbed — passwords, MAC addresses, serial
numbers, IP addresses.

**Golden file lifecycle:**

1. Contributor submits HAR capture via `har-capture`
2. Skill/MCP generates modem.yaml, parser.yaml, and parser.py if needed
3. First pipeline run against `HARMockServer` produces `ModemData` output
4. Developer reviews output against raw HAR responses
5. Reviewed output is committed as `{name}.expected.json`
6. All future runs are regression tests against the golden file

**Action test fixtures** live in the same capture as data collection —
one HAR per variant. `discover_restart_tests` replays `modem.har` when
`modem.yaml` declares `actions.restart`; there is no dedicated restart
capture file. When the restart evidence arrives in a separate capture
of the same device, assemble one fixture per
MODEM_INTAKE_WORKFLOW § Assembled fixtures. Pass/fail for restart tests
is determined by `ActionResult.success`, not golden file comparison.

**Restart entries in `modem.har` structure:**

For **HTTP transport** (e.g., `action_auth: bearer`), two entries in order:

1. `POST {login_endpoint}` — response contains the token at `token_path`
2. `POST {restart.endpoint}` — 200 response (body ignored)

For **HNAP transport**, entries covering:

1. HNAP login exchange (phase 1 challenge + phase 2 login POSTs to `/HNAP1/`)
2. Pre-fetch action response (POST `/HNAP1/`, if `pre_fetch_action` is declared)
3. Main action response (POST `/HNAP1/`, with the `{action_name}Response` key
   and `{result_key}: {success_value}` in the body)

The mock server merges all HNAP data responses into one combined response, so the
pre-fetch and action responses can be captured in any order — the test runner will
find the expected keys regardless of call order.

**Synthesized HARs** are acceptable when the real exchange has not been
captured yet — document the synthesis in `log.creator.comment` and cite
the source of the response shapes. Replace with a real capture once a
contributor provides one. Synthesized files still exercise the full
action pipeline: config parsing, token extraction, and HTTP dispatch.

---

## Verification Status

The `status` field in modem.yaml tracks how thoroughly a modem config
has been validated. Each level builds on the previous.

| Status | Meaning | Evidence |
|--------|---------|----------|
| `unsupported` | Placeholder — no parser, awaiting contributor data | None |
| `awaiting_verification` | Config exists, golden file tests pass against HAR replay | `test_data/*.expected.json` |
| `confirmed` | Full pipeline verified on real hardware | `test_data/modem.verified.json` |

### Verification artifact

When a modem reaches `confirmed`, a verification artifact is committed
to `test_data/`. This is a sanitized HA diagnostics dump capturing
the integration's output from a real modem — proof that auth, parsing,
health checks, and entity creation all work end-to-end.

**File naming** follows the existing convention:

| File | Description |
|------|-------------|
| `modem.verified.json` | Default variant verification |
| `modem-{variant}.verified.json` | Named variant verification |

Each variant gets its own verification artifact because each has its
own auth strategy and potentially different channel data.

**Contents:** The verified file is a faithful copy of the HA
diagnostics `data` section with two additions (`verified_at`,
`version`) and PII/environment sections removed. All modem data —
including `system_info`, coordinator state, `lock_status` on channels,
full `core_diagnostics` (auth strategy, resource fetches, timestamps),
and raw numeric precision — must be preserved verbatim.

**Key structure:** The diagnostics output disassembles Core's nested
`modem_data` dict into separate top-level keys. `modem_data` contains
orchestrator-derived evaluated state (connection + health).
`system_info` is the full pass-through of Core's parser-extracted and
computed fields (counts, totals, version, uptime). The diagnostics
builder never copies values from `system_info` into `modem_data`. See
HA_ADAPTER_SPEC § Diagnostics Top-Level Keys for the full schema.

**Stripped sections** (not modem data):

- `home_assistant` — host environment
- `custom_components` — installed integrations
- `integration_manifest` — derivable from code
- `setup_times` — internal HA timings
- `_solentlabs` — tool metadata
- `_review_before_sharing` — instruction text
- `recent_logs` — ephemeral log lines

Everything else stays exactly as the diagnostics produced it. Do not
round numbers, reorder fields, or drop fields that are part of the
modem's live output.

See `arris/s33v2/test_data/modem.verified.json` for the reference
example.

### Promotion procedure

When a user reports a successful install and attaches their diagnostics
download (`config_entry-cable_modem_monitor-*.json`):

1. Open the user's diagnostics file and take the `data` section.
2. Strip the sections listed under **Stripped sections** above.
3. Prepend two top-level fields: `verified_at` (ISO date, `YYYY-MM-DD`)
   and `version` (the version string the user ran — whatever was
   visible in their Home Assistant install, e.g. `3.14.0-beta.1`).
   Both appear before `config_entry` in the output file for diff
   readability.
4. Preserve everything else verbatim — no rounding, no field drops, no
   reordering within preserved sections.
5. Write to `test_data/modem.verified.json` (or the matching
   `modem-{variant}.verified.json` if the user confirmed a variant).
6. Flip `modem.yaml` `status` from `awaiting_verification` to
   `confirmed`.
7. Run the catalog test suite (`pytest packages/cable_modem_monitor_catalog`)
   to confirm the artifact parses and schema checks pass.
8. Stage and commit; remove the `needs-testing` issue label.

This procedure is currently manual. Automation is tracked in the beta
backlog.

---

## Config Assembly

The loader assembles a complete modem config from two sources:

```text
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

### Single variant, parser.yaml + parser.py

```text
modems/{manufacturer}/{model}/
├── parser.yaml           # declarative extraction config
├── parser.py             # post-processor for quirks
├── modem.yaml            # transport, auth, metadata
└── test_data/
    ├── modem.har
    └── modem.expected.json
```

### Multi-variant, shared transport

```text
modems/{manufacturer}/{model}/
├── parser.yaml           # shared extraction config
├── parser.py             # shared post-processor
├── modem.yaml            # default variant (e.g., auth: none)
├── modem-{variant}.yaml  # additional variant (e.g., different auth)
├── modem-{variant}.yaml  # another variant
└── test_data/
    ├── modem.har
    ├── modem.expected.json
    ├── modem-{variant}.har
    ├── modem-{variant}.expected.json
    ├── modem-{variant}.har
    └── modem-{variant}.expected.json
```

### Config variant + test variant (e.g., SB6190)

```text
modems/arris/sb6190/
├── parser.yaml
├── modem.yaml                  # auth: none (older firmware)
├── modem-form-nonce.yaml       # auth: form_nonce (newer firmware)
└── test_data/
    ├── modem.har                       # no-auth firmware
    ├── modem.expected.json
    ├── modem-form-nonce.har            # form_nonce, plain encoding
    ├── modem-form-nonce.expected.json
    ├── modem-form-nonce-b64.har        # form_nonce, b64 encoding (test variant)
    └── modem-form-nonce-b64.expected.json
```

`modem-form-nonce-b64.har` has no matching YAML — stem walking
resolves it to `modem-form-nonce.yaml`. Same auth config, different
firmware encoding detected at runtime.

### HNAP, single variant, 100% parser.yaml

```text
modems/{manufacturer}/{model}/
├── parser.yaml           # HNAP delimiters, field mappings
├── modem.yaml            # transport: hnap, auth, metadata
└── test_data/
    ├── modem.har
    ├── modem.expected.json
    ├── modem-{compat}.har          # firmware compatibility test
    └── modem-{compat}.expected.json
```

### Multi-variant, 100% parser.py

```text
modems/{manufacturer}/{model}/
├── parser.py             # extraction too complex for declarative config
├── modem-{variant}.yaml  # variant 1
├── modem-{variant}.yaml  # variant 2
└── test_data/
    ├── modem.har
    ├── modem.expected.json
    ├── modem-{variant}.har
    └── modem-{variant}.expected.json
```
