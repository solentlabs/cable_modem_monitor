# Architecture Decisions

Distilled decisions and their rationale — the "why" behind the
architecture. Grouped by theme. For the full design, see the spec
files; this document explains the choices that shaped them.

---

## Package Boundaries

### Three packages with strict dependency direction

**Decision:** Core (engine) ← Catalog (content) ← HA Integration
(adapter), enforced through real Python packaging.

**Rationale:** Import violations are missing module errors, not lint
warnings. Core is platform-agnostic and could power any consumer —
HA, a CLI tool, a Prometheus exporter. Catalog is content-only (YAML
configs, parser overrides, HAR captures) with no business logic. The
HA integration is a thin adapter that maps Core output to HA platforms.

**Constrains:** Core cannot import from Catalog or HA. Catalog cannot
import from HA. No circular dependencies. Adding modem-specific
knowledge to Core is a design violation.

### Test harness lives in Core, not Catalog

**Decision:** Core owns the test harness (HAR replay framework, golden
file comparison, schema validators). Catalog contains only data files
(HAR captures, golden files).

**Rationale:** Catalog contributors cannot accidentally modify test
assertions or loader logic. Catalog's CI installs Core and runs Core's
test suite pointed at catalog files. Adding a modem never requires
writing test code.

**Constrains:** Test assertions cannot be customized per-modem.
Strategy changes are validated across all modems automatically.

---

## Transport and Constraint Model

### Transport is a protocol identifier, not a constraint funnel

**Decision:** The `transport` field in modem.yaml identifies the transport
protocol. Two values: `http` and `hnap`. For `http`, auth, session, and
format are configured independently (qualified — some auth/session
pairings are linked; see MODEM_YAML_SPEC.md auth-session-action
consistency rules). For `hnap`, the protocol constrains everything.

**Rationale:** All 33 non-HNAP modems use HTTP requests regardless of
whether the response is HTML, JSON, or XML. The difference between an
HTML table scraper and a JSON API modem is response format, not transport.
Keeping transport separate from format means each does one thing:
transport selects the loader, format (in parser.yaml) selects the decode
step and extraction strategy. Auth strategies are orthogonal to both —
any auth can appear with any format over HTTP. HNAP is genuinely a
different protocol (SOAP POST + HMAC signing), so it warrants its own
transport value where the protocol constrains auth, session, and format.

Evidence: across all 32 modem directories, no auth strategy is structurally
tied to a response format. Basic auth modems serve HTML tables today, but
nothing prevents a basic-auth modem from serving JSON. The pairings
observed in the current population are coincidental, not architectural.
See the HAR corpus analysis (local reference data) for the full modem inventory and
stress test results.

**Constrains:** Format strategies must be compatible with the value type
they receive. HTML formats expect `BeautifulSoup`, structured formats
expect `dict`. Misconfigured modem.yaml is rejected at load time.

### Capabilities are implicit from parser output

**Decision:** No `capabilities` field in modem.yaml. A mapping in
parser.yaml or an override in parser.py IS the capability declaration.
No mapping = no entity.

**Rationale:** Eliminates a separate capabilities list that drifts from
actual parser output. The parser output is the single source of truth.
Absent capability = absent entity — no greyed-out buttons, no "not
supported" placeholders.

**Constrains:** The only way to declare a capability is to implement
the extraction. The exception is `actions.restart` in modem.yaml, which
declares restart capability (a modem command, not parsed data).

---

## Auth Architecture

### Seven discrete strategies, not composable primitives

**Decision:** Auth is a discriminated union of seven self-contained
strategy types: `none`, `basic`, `form`, `form_nonce`, `url_token`,
`hnap`, `form_pbkdf2`. Each strategy has a per-strategy dataclass and
a single audited implementation. The alternative — a toolkit of
composable primitives (encoding, CSRF, nonce generation) that you mix
and match per-modem — was rejected.

**Rationale:** The boundary between "separate strategy" and "config
flag" is structural behavior — how the auth protocol works. `form_nonce`
parses text prefixes, not redirects. `form_pbkdf2` requires multi-round
challenge-response with server salts. These are structurally different
protocols, not variations you can compose from shared building blocks.
Meanwhile, base64 encoding, CSRF tokens, dynamic endpoints, and
AJAX-style login are all config flags on `form` — same
POST-evaluate-redirect flow.

**Constrains:** Adding a new auth strategy requires a new dataclass,
a new `BaseAuthStrategy` subclass, a new factory registration, and a
new `auth.strategy` string. No existing strategy code is touched.
No per-modem auth hooks — all variation is modem.yaml config.

### No per-modem auth hooks

**Decision:** Auth and session have no override points. All variation
is expressed through modem.yaml configuration.

**Rationale:** Auth touches credentials. One audited implementation per
strategy, not per-modem overrides that could mishandle passwords or
leak tokens. The variation across 31 modems is wide but shallow —
different values (field names, encoding, cookie names), not different
behaviors. If a modem needs a genuinely new auth flow, that's a new
Core strategy.

**Constrains:** Cannot customize auth behavior per-modem. Any new auth
pattern requires a Core change — but this is intentional, as it
becomes available to all future modems using the same protocol.

### Session is independent from auth

**Decision:** Session config (`cookie_name`, `max_concurrent`,
`token_prefix`, `headers`) is a separate top-level section in
modem.yaml, not nested under auth.

**Rationale:** The same auth strategy can use different session
mechanisms across modems. Session owns post-login state; auth owns
login mechanics. Logout is an action (`actions.logout`), not a session
field — HAR evidence shows logout needs the same config surface as
restart (method, endpoint, params, pre-fetch).

**Constrains:** No `logout_url` or `logout_required` convenience
fields. The `max_concurrent: 1` constraint requires `actions.logout`
to be declared (build-time validation error).

---

## Parsing Architecture

### Three roles: BaseParser, ModemParserCoordinator, parser.py

**Decision:** Parsing has three distinct roles instead of a single
class hierarchy. `BaseParser` (ABC) is the extraction interface with
seven format-specific implementations — including `StructuredParser`
(ABC), an intermediate base for `JSONParser` and `XMLParser` that
holds the shared dict-path extraction pipeline.
`ModemParserCoordinator` is the factory and orchestrator. `parser.py`
is an optional post-processor.

**Rationale:** The original design conflated extraction, orchestration,
and customization into one class — a god class risk. Separating them
makes each independently testable. The coordinator is a thin ~50-line
orchestrator. Extraction complexity lives in `BaseParser`
implementations. parser.py is a hook, not an inheritance override.

**Constrains:** parser.py cannot subclass `BaseParser` or the
coordinator. It receives extraction output + raw resources and returns
final section data. Per-section hooks only (`parse_downstream`,
`parse_upstream`, `parse_system_info`) — no modem-level hook.

### Format selection is per-section, not per-modem

**Decision:** Each parser.yaml section (`downstream`, `upstream`,
`system_info`) declares its own `format` independently. A modem can
mix formats.

**Rationale:** Real modems mix formats — transposed tables for channels
plus JavaScript for system info, or html_fields from multiple pages.
Per-section format selection accommodates this without forcing a
single format choice.

**Constrains:** Every section must explicitly declare its format. No
inheritance, no defaults to guess.

### parser.yaml is primary, parser.py is the escape hatch

**Decision:** At least one of parser.yaml or parser.py is required.
parser.yaml is the primary expression mode. When both exist, parser.yaml
handles standard extraction and parser.py post-processes sections that
need code. When extraction is too complex for declarative config,
parser.py alone is valid.

**Rationale:** Declarative config (parser.yaml) is reviewable,
validatable, and consistent. Code (parser.py) handles genuine
structural variety that can't be expressed declaratively. When a
parser.py pattern recurs across 3+ modems, it graduates to a
parser.yaml config field.

**Constrains:** parser.py hooks cannot make network calls — only
pre-fetched resources are available. parser.py never contains auth
or metadata. modem.yaml never contains extraction logic.

### Companion tables merge via config, not code

**Decision:** The `merge_by` field on `tables[]` entries tells the
coordinator to merge companion table fields into primary channels by
declared key fields, instead of appending them as separate channels.

**Rationale:** Some modems split channel data across primary and
companion tables. This was a parser.py use case that
graduated to config. `merge_by` is a list of field names forming the
lookup key — primary table wins on field conflicts.

**Constrains:** All tables in a section share the section-level
`resource`. Companion tables must have matching key fields for the
merge to work.

---

## Session and Action Model

### Signal/policy separation

**Decision:** Protocol layers (auth manager, resource loader, parser)
signal conditions. The orchestrator owns all policy (retry, backoff,
error reporting).

**Rationale:** When a layer both signals a condition and decides what
to do about it, callers inherit hidden policy they can't override.
Keeping signal and policy separate gives the orchestrator full
visibility and full control. Auth strategies raise
`LoginLockoutError` but don't track lockout state. The orchestrator
sets backoff counters and suppresses login attempts.

**Constrains:** Protocol layers never retry, back off, or decide what
to do about failures. All policy state (backoff counters, session
reuse decisions) lives on the orchestrator.

### Session reuse across polls

**Decision:** Sessions persist across polls. The auth manager reuses
valid sessions instead of re-authenticating every cycle.

**Rationale:** HNAP modems have firmware anti-brute-force that can lock
out or reboot the modem after repeated login attempts (HNAP modem
firmware `LOCKUP` and `REBOOT` states). Session reuse
is the primary defense. Backoff (3-poll suppression on lockout) is the
safety net.

**Constrains:** Session state must be maintained across polls. Stale
session detection requires a within-poll retry mechanism (zero channels
on reused session → clear and retry once).

### Two modem-side actions only

**Decision:** Two actions: restart (user-triggered) and logout
(system-triggered). Both share the same action schema with two type
discriminators: `http` and `hnap`.

**Rationale:** The integration's purpose is read-only monitoring.
Restart is the sole state-changing action — a security and
terms-of-service boundary. Logout is session cleanup so users can
access the modem's web UI between polls. No other modem commands
are supported.

**Constrains:** Cannot add modem commands beyond restart without
expanding the action model. This is intentional.

---

## Testing Strategy

### HAR replay as integration tests

**Decision:** Each modem's `tests/` directory contains HAR captures
(pipeline input) and expected output golden files (assertions). The
test harness replays each HAR through a mock server, runs the full
pipeline, and compares output against the golden file.

**Rationale:** HAR captures are engine-independent HTTP recordings —
the most durable test fixture. Golden files capture reviewed output
against which all future runs are regression tests. If a `BaseParser`
implementation changes, all modems using that format are automatically
retested (regression firewall).

**Constrains:** Adding a modem requires a HAR capture and a reviewed
golden file. No test code in Catalog — only data files.

### Greenfield from specs, not migration from prior versions

**Decision:** No code reuse from prior versions. Build from the specs
using HAR files as the evidence base.

**Rationale:** Migration creates pressure to preserve old patterns.
"This test already exists, let's adapt it" leads to old assumptions
leaking in. A repeatable HAR-driven generation process is both cleaner
and more scalable — works identically for modem #1 and modem #33.

**Constrains:** Prior test intent (same modem, same input, same
expected output) is preserved through golden files, not through
migrated test code.

---

## Onboarding

### MCP tools for deterministic steps, Claude for judgment

**Decision:** An MCP server provides structured tools for modem
onboarding. Deterministic steps (HAR parsing, transport detection,
config generation, validation, test execution) are code. Claude handles
judgment calls (ambiguous HTML formats, metadata web search, test
failure diagnosis). The user handles approval.

**Rationale:** Deterministic logic in MCP tools is repeatable and
testable — not dependent on LLM reasoning for correctness. The
config constraints (transport, auth, format) form the decision framework.
Ambiguity is a hard stop, not a guess.

**Constrains:** HAR validation is a gate — post-auth-only HARs,
missing auth flows, and ambiguous transports halt analysis. No guessing.
Metadata not in the HAR is filled via web search with source
provenance.

### Core owns the onboarding spec

**Decision:** ONBOARDING_SPEC.md lives in Core's docs, not Catalog's.

**Rationale:** The onboarding process generates Catalog content but
uses Core's validation, test harness, and schema definitions. Core
is the authority on what constitutes a valid modem config.

**Constrains:** The MCP tools depend on Core's schema validators and
test harness.

---

## Extension Model

### How to add a modem

Add a directory under `modems/{manufacturer}/{model}/` with:
- `modem.yaml` — identity, auth, session, hardware, metadata
- `parser.yaml` — declarative extraction config
- `parser.py` — optional post-processor (only if needed)
- `tests/modem.har` + `tests/modem.expected.json` — HAR and golden file

No registration. No changes to Core or Catalog package code. Drop-in.

### How to add a format

Add a `BaseParser` implementation in Core. Add the format string to
the valid formats list. Update validators. Existing modem
configs and tests are untouched.

### How to add an auth strategy

Add a dataclass, a `BaseAuthStrategy` subclass, and a factory
registration in Core. Add the strategy string to the valid auth list.
Update validators. No existing strategy code is touched.

### How to add a transport

Add a new loader (new value type), new `BaseParser` implementation(s)
that consume that type, a new row in the constraint table, and
validator updates. No existing code changes.

---

## References

| Document | Purpose |
|----------|---------|
| `ARCHITECTURE.md` | System design, component contracts |
| `MODEM_YAML_SPEC.md` | modem.yaml schema |
| `MODEM_DIRECTORY_SPEC.md` | Catalog directory structure |
| `PARSING_SPEC.md` | Extraction formats, parser.yaml/parser.py |
| `RESOURCE_LOADING_SPEC.md` | Resource dict contract, loader behavior |
| `ORCHESTRATION_SPEC.md` | Orchestrator, collector, health monitor, restart monitor — interface contracts and data models |
| `ORCHESTRATION_USE_CASES.md` | Scenario-based use cases — normal ops, auth failures, connectivity, restart, health, lifecycle |
| `RUNTIME_POLLING_SPEC.md` | Poll cycle, session lifecycle, error recovery |
| `ONBOARDING_SPEC.md` | MCP-driven modem onboarding |
| `FIELD_REGISTRY.md` | Field naming authority |
| `VERIFICATION_STATUS.md` | Parser status lifecycle |
| `../../../custom_components/cable_modem_monitor/docs/CONFIG_FLOW_SPEC.md` | Setup wizard |
| `../../../custom_components/cable_modem_monitor/docs/ENTITY_MODEL_SPEC.md` | Core output → HA entities |
| `../../../custom_components/cable_modem_monitor/docs/HA_ADAPTER_SPEC.md` | HA wiring — runtime data, coordinators, polling modes |
