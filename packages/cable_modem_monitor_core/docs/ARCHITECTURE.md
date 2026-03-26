# Architecture

A Home Assistant integration that polls cable modems over their local web
interface and exposes DOCSIS signal data as sensors.

The core challenge: every modem manufacturer implements their web UI differently.
Different auth mechanisms, different page structures, different data formats.
The architecture absorbs this variety through a config-driven strategy pattern
where modem behavior is driven by YAML configuration, not code.

**Evidence base:** 31 HAR captures (23 real, 8 synthetic) across
7 manufacturers.

---

## Packages

Two pip packages and an HA integration in a monorepo with strict dependency
direction. Each pip package has its own `pyproject.toml` and enforces boundaries
through real Python packaging — import violations are missing module errors, not
lint warnings. The HA integration is distributed via HACS.

**Naming convention:** `cable_modem_monitor_` prefix for all packages in the
`solentlabs` namespace. The HA integration name (`cable_modem_monitor`) is
locked to the HACS store.

```mermaid
graph TD
    HA["<b>HA Integration</b><hr/>cable-modem-monitor"] --> Core["<b>pip package</b><hr/>solentlabs-cable-modem-monitor-core"]
    HA --> Catalog["<b>pip package</b><hr/>solentlabs-cable-modem-monitor-catalog"]
    Catalog --> Core
```

**Import paths:**
- `from solentlabs.cable_modem_monitor_core import ...`
- `from solentlabs.cable_modem_monitor_catalog import CATALOG_PATH`

**Repository layout:**
```
packages/
├── cable_modem_monitor_core/
│   ├── pyproject.toml              # name = "solentlabs-cable-modem-monitor-core"
│   └── solentlabs/cable_modem_monitor_core/
└── cable_modem_monitor_catalog/
    ├── pyproject.toml              # name = "solentlabs-cable-modem-monitor-catalog"
    └── solentlabs/cable_modem_monitor_catalog/
custom_components/
└── cable_modem_monitor/            # HA integration
```

### Optional extras

Core's base dependencies are minimal — what the runtime engine needs.
Additional functionality is available via optional extras:

| Extra | Install | What it adds | Who uses it |
|-------|---------|--------------|-------------|
| `[mcp]` | `pip install solentlabs-cable-modem-monitor-core[mcp]` | `pydantic>=2.0` | MCP server tools (`validate_har`, `analyze_har`, `enrich_metadata`, `generate_config`, `generate_golden_file`, `write_modem_package`, `run_tests`, `validate_config`), Catalog's build-time validation, dev-gate CI |

The `[mcp]` extra provides Pydantic for config schema validation. The HA
integration never imports the `models` module — it uses parsed dicts from
the coordinator. Pydantic is only needed by the MCP onboarding tools and
Catalog's dev-time validation pipeline.

Catalog's dev dependencies reference the extra:
```toml
[dependency-groups]
dev = ["solentlabs-cable-modem-monitor-core[mcp]"]
```

### Core — `solentlabs-cable-modem-monitor-core`

The complete engine. Given a path to modem files and user credentials, Core
does everything: loads config, authenticates, fetches data, parses responses,
coordinates the poll cycle, and recovers from errors. The orchestrator is a
scheduler and policy engine that delegates to specialized components
(ModemDataCollector, HealthMonitor, RestartMonitor) — each independently testable
with a clear input→output contract. Platform-agnostic — no `homeassistant.*`
imports, no catalog imports.

Core is bounded by interfaces and abstract base classes. Concrete
implementations live here too (auth strategies, resource loaders, actions),
but modem-specific behavior comes from config, not from Core code.

| Responsibility | What |
|----------------|------|
| Data models | `ModemData`, `ChannelData`, `SystemInfo`, `HealthInfo`, `ModemIdentity` |
| Config schemas | `ModemConfig`, `AuthConfig`, `PageConfig`, `ParserConfig` |
| ABCs / base classes | `BaseParser`, `BaseAuthStrategy`, `BaseAction` |
| Parser coordinator | `ModemParserCoordinator` — factory + orchestration: parser.yaml → `BaseParser` instances → parser.py chaining → `ModemData` |
| Auth strategies | `none`, `basic`, `form`, `form_nonce`, `form_pbkdf2`, `form_sjcl`, `hnap`, `url_token` |
| Resource loaders | HTTP → `BeautifulSoup` or `dict` (format-dependent), HNAP → JSON |
| Orchestrator | Policy engine: signal→policy dispatch, circuit breaker, status derivation |
| ModemDataCollector | Single collection cycle: auth → load → parse → `ModemData` or signal |
| HealthMonitor | Health probes on independent cadence → `HealthInfo` |
| RestartMonitor | Two-phase restart recovery: wait for response → wait for channel sync |
| Auth Manager | Strategy dispatch, session reuse, backoff |
| Modem loader | `load_modem_config(path, mfr, model, variant)` — knows the directory convention |
| Catalog Manager | `list_modems(catalog_path)` → `list[ModemSummary]` — walks catalog, returns identity fields for config flow display and filtering |
| Connectivity | Protocol detection, legacy SSL, health probes |
| Exceptions | `LoginLockoutError`, `AuthFailedError`, `ParseError` |
| Test harness | Schema validators, HAR replay framework, parser output assertions |

The test harness lives in Core so that Catalog contributors cannot
accidentally modify test assertions or loader logic. Catalog's CI installs
Core and runs Core's test suite pointed at the catalog files.

Core could power any platform — Home Assistant, a Windows service, a CLI
tool, a Prometheus exporter. The platform tells Core where the modem files
are and provides credentials; Core does the rest.

### Catalog — `solentlabs-cable-modem-monitor-catalog`

A content package. No business logic — just modem config files, parser
overrides, and HAR evidence. Depends on Core only (parser.py files are
optional post-processors invoked by Core's `ModemParserCoordinator`).

| Content | What |
|---------|------|
| `modem.yaml` / `modem-{variant}.yaml` | Identity, auth config, metadata |
| `parser.yaml` | Declarative extraction mappings |
| `parser.py` | Optional post-processor for modem-specific extraction quirks |
| `tests/` | HAR captures and expected output golden files |

```
solentlabs/cable_modem_monitor_catalog/
├── __init__.py              # exposes CATALOG_PATH
└── modems/
    └── {mfr}/{model}/
        ├── modem.yaml
        ├── parser.yaml
        ├── parser.py
        └── tests/
```

No loader, no discovery, no test code. Adding a modem means adding a
directory — no registration, no changes to Catalog package code.

### HA Integration — `cable-modem-monitor`

Thin platform adapter. Translates between Home Assistant's lifecycle and
Core's engine. Depends on both Core and Catalog.

| Responsibility | What |
|----------------|------|
| Config flow | Manufacturer dropdown → model filter → variant → connection → validate. Uses Core's `list_modems()` with Catalog's `CATALOG_PATH` |
| Runtime storage | `CableModemRuntimeData` on `entry.runtime_data` (HA 2024.12+) |
| Data coordinator | Wraps Core's `Orchestrator.get_modem_data()` in HA's `DataUpdateCoordinator` |
| Health coordinator | Second `DataUpdateCoordinator` wrapping `HealthMonitor.ping()`. Conditional — only created if probes work. Independent cadence (default 30s) |
| Entities | Maps Core's `ModemSnapshot` → HA sensors. Channel sensors unavailable when `modem_data` is None |
| Status sensor | Priority cascade over `connection_status`, `health_status`, `docsis_status`. `diagnosis` attribute derived in HA from `health_status` enum |
| Restart button | Maps HA button press → `orchestrator.restart()` in executor thread with `cancel_event` for clean shutdown |
| Update button | Triggers immediate poll via `coordinator.async_request_refresh()` |
| Reset entities button | Removes all entities from HA registry and reloads the integration |
| Reauth flow | Circuit breaker triggers HA native `async_step_reauth`. Calls `orchestrator.reset_auth()` on success |
| Diagnostics | Combines Core's `OrchestratorDiagnostics` with HA-side sanitized logs, channel dump, PII checklist |
| Dashboard generator | Service that generates Lovelace YAML for modem dashboard based on current channels |

No parsing, no auth, no modem-specific knowledge. The Capture button from
v3.13 was removed — `har-capture` is the tool for collecting raw modem data
for parser development.

**Startup example:**
```python
from solentlabs.cable_modem_monitor_catalog import CATALOG_PATH
from solentlabs.cable_modem_monitor_core.orchestration import (
    HealthMonitor,
    ModemDataCollector,
    Orchestrator,
)

# Load configs from catalog
modem_config = load_modem_config(CATALOG_PATH / "arris" / "sb8200" / "modem.yaml")
parser_config = load_parser_config(CATALOG_PATH / "arris" / "sb8200" / "parser.yaml")

# Create components
collector = ModemDataCollector(
    modem_config, parser_config, post_processor=None,
    base_url="http://192.168.100.1", username="admin", password="...",
)
health_monitor = HealthMonitor(
    base_url="http://192.168.100.1",
    supports_icmp=True, supports_head=True,
)
orchestrator = Orchestrator(collector, health_monitor, modem_config)

# Poll
snapshot = orchestrator.get_modem_data()
```

---

## Transport and Format

The `transport` field in modem.yaml is the first config decision — it
identifies the wire protocol (`http` or `hnap`) and determines whether
the remaining axes are free or locked. For `http`, auth, session, and
format are configured independently (qualified — some auth/session
pairings are linked, marked with 🔗 below). For `hnap`, the protocol
locks all axes to fixed values.

```mermaid
graph TD
    T[transport] --> HNAP["<b>hnap</b><hr/>HNAPLoader → dict"]
    T --> HTTP["<b>http</b><hr/>HTTPLoader → BeautifulSoup | dict"]

    HNAP --> HA["<b>AUTH</b><hr/>• HMAC challenge-response"]
    HA --> HS["<b>SESSION</b><hr/>• uid cookie + HNAP_AUTH header"]
    HS --> HF["<b>FORMAT</b><hr/>• hnap (JSON + delimiters)"]

    HTTP --> HTA["<b>AUTH</b><hr/>• none<br/>• basic<br/>• form<br/>• form_nonce<br/>• url_token 🔗<br/>• form_pbkdf2 🔗<br/>• form_sjcl 🔗"]
    HTA --> HTS["<b>SESSION</b><hr/>• stateless<br/>• cookie<br/>• CSRF 🔗<br/>• url_token 🔗"]
    HTS --> HTF["<b>FORMAT</b><hr/>• table<br/>• table_transposed<br/>• javascript<br/>• javascript_json<br/>• html_fields<br/>• json<br/>• xml"]
```

*🔗 Implies specific session mechanism — see
[MODEM_YAML_SPEC.md](MODEM_YAML_SPEC.md#auth-session-action-consistency)
for validation rules.*

Both sides follow the same pipeline order: auth → session → format. The
difference is constraint: for HNAP, each step has exactly one valid choice.
For HTTP, each step is configured independently — choosing `basic` auth
doesn't restrict format to HTML tables, and choosing `json` format doesn't
require `form_pbkdf2` auth.

### HNAP — Fully Constrained

- The protocol defines everything: auth, session, format
- Only two values vary per modem: HMAC algorithm and action names
- One strategy handles all HNAP modems

### HTTP — Independent Axes

- Auth, session, and format are configured independently
  (some auth strategies imply specific session mechanisms — see 🔗 above)
- This is where all the complexity (and variety) lives
- 33 modems: from simple unauthenticated HTML table scraping to
  PBKDF2 challenge-response with JSON APIs

### Constraint Summary

| Transport | Loader | Valid Auth | Valid Formats | Valid Action Types |
|-----------|--------|-----------|--------------|-------------------|
| `hnap` | HNAPLoader → `dict` | `hnap` only | `hnap` only | `hnap` |
| `http` | HTTPLoader → BeautifulSoup or dict | `none`, `basic`, `form`, `form_nonce`, `url_token`, `form_pbkdf2`, `form_sjcl` | `table`, `table_transposed`, `javascript`, `javascript_json`, `html_fields`, `json`, `xml` | `http` |

At runtime, the format declared in parser.yaml determines how the response
is decoded. HTML formats (`table`, `table_transposed`, `javascript`,
`javascript_json`, `html_fields`) are parsed into `BeautifulSoup`.
Structured formats (`json`, `xml`) are decoded into `dict`. Any format supports an optional
`encoding` property (e.g., `encoding: base64` for modems that wrap
JSON in base64). The encoding is a pre-step — the loader
unwraps the encoding before the format-specific decoder runs. The
format-to-value-type mapping is deterministic and validated at config
load time.

These constraints are validated at both **build time** (Pydantic validation
in Catalog's dev-gate) and **load time** (`load_modem_config()` in Core).
A misconfigured modem.yaml is rejected with a clear error, not at runtime
with mysterious parsing failures.

### Extension Model

Adding a new format, auth strategy, or transport is **additive only** — no
existing entries change.

- **New format for `http`:** Add the `BaseParser` implementation, add the
  format string to the valid formats list, update validators. Existing
  modem configs and tests are untouched.
- **New auth strategy for `http`:** Add the dataclass, the auth strategy
  class, and the factory registration. Add the strategy string to the
  valid auth list, update validators.
- **New transport:** Add a new loader, new `BaseParser` implementation(s),
  a new row in the constraint table, and validator updates. No existing
  code changes. Future transports (`snmp`, `ftp`, `soap`, etc.) are
  additive — new transport value, new loader, new constraint row.

The constraint table is an allowlist, not a lock. It prevents
misconfigurations without preventing growth.

---

## Core Components

Everything below lives in `solentlabs-cable-modem-monitor-core`. These are
generic — no modem-specific knowledge, no HA imports.

### Auth Manager

Handles authentication for all transports through configuration, not code.
Each auth strategy is a single audited implementation that reads its parameters
from modem.yaml:

| Strategy | Transport | Stateless? |
|----------|-----------|:----------:|
| `none` | HTTP | Yes |
| `basic` | HTTP | Yes |
| `form` | HTTP | No |
| `form_nonce` | HTTP | No |
| `hnap` | HNAP | No |
| `form_pbkdf2` | HTTP | No |
| `form_sjcl` | HTTP | No |
| `url_token` | HTTP | No |

See [MODEM_YAML_SPEC.md](MODEM_YAML_SPEC.md#auth) for per-strategy
config fields.

**Key points:**
- `form` and `form_nonce` are separate strategies because they have different
  response handling — `form` evaluates redirects and cookies, `form_nonce`
  parses text prefixes (`Url:` / `Error:`)
- `form_pbkdf2` is separate from `form` because it requires a multi-round-trip
  challenge-response: POST to get server-provided salts, client-side PBKDF2
  key derivation, then POST the derived hash. This is structurally closer to
  HNAP's challenge-response than to a simple form POST with encoding flags
- `form_sjcl` is separate from `form_pbkdf2` because it adds client-side
  AES-CCM encryption of credentials (via SJCL — Stanford JavaScript Crypto
  Library) and requires decrypting the server response to extract a CSRF
  nonce. Both use PBKDF2 key derivation, but `form_sjcl` encrypts the
  payload and decrypts the response, while `form_pbkdf2` hashes the password
  and sends it in plaintext JSON. Requires the `cryptography` package
  (install Core with `[sjcl]` extra)
- All other form differences (encoding, CSRF, field names, session cookies)
  are config flags on `form`. Specifically: base64 password encoding is
  `encoding: base64`, dynamic endpoint discovery is `login_page` +
  `form_selector`, and AJAX-style login is handled through `form`'s
  existing config surface — none of these warrant separate strategies
- Auth strategy **selection** is purely config-driven — no runtime inspection
  of login pages to determine which strategy to use.
  Auth **execution** routinely interacts with login
  pages: `form` fetches the page to extract hidden fields, `form_nonce` extracts
  a server-generated nonce, `form_pbkdf2` fetches salts before computing the
  password hash. The distinction: config decides *what* to do, runtime
  interaction is *how* the configured strategy executes.
- Multi-variant modems use separate `modem-{variant}.yaml` files — one per
  firmware variant, each with a single `auth` block. The config flow presents
  variants as user choices during setup. Protocol (HTTP vs HTTPS) is detected
  automatically and is independent of firmware variant — the user selects based
  on their network, not their protocol. See `CONFIG_FLOW_SPEC.md` for the
  full setup flow.

#### `url_token` Strategy — Config Reference

URL token auth appends base64-encoded credentials to the URL query string
instead of using an Authorization header or form POST. The response sets a
session cookie; subsequent requests use a server-issued token in the query
string.

Evidence base: modems with HTTPS variants that encode credentials in URL
query strings. Two firmware builds use different token formats — one prefixes
a string before the base64 token, the other sends bare base64. Both produce
the same session mechanism.

**Auth flow:**
```
1. Encode credentials: base64("username:password")
2. Login request:
   GET /cmconnectionstatus.html?{login_prefix}{base64_token}
   Headers: Authorization: Basic {base64_token}  (if auth_header_data)
            X-Requested-With: XMLHttpRequest      (if ajax_login)
3. Response sets session cookie (session.cookie_name)
4. Subsequent data requests:
   GET /cmswinfo.html?{session.token_prefix}{session_token}
```

**Auth config fields** (login mechanics only):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `login_page` | string | required | Page URL that accepts the token login (e.g., `/cmconnectionstatus.html`) |
| `login_prefix` | string | `""` | Prefix before base64 token in login URL. Some firmware uses `login_`, others use bare base64. If empty, no prefix is added. |
| `success_indicator` | string | `""` | String to match in login response body to confirm success (e.g., `Downstream Bonded Channels`) |
| `ajax_login` | bool | `false` | If true, login request includes `X-Requested-With: XMLHttpRequest` header (matches browser jQuery behavior observed in HAR) |
| `auth_header_data` | bool | `false` | If true, include `Authorization: Basic {token}` header on data requests (not just login). Most firmware only needs the session cookie. |

Session cookie and token prefix are declared in the `session` section
— see `MODEM_YAML_SPEC.md` Session.

**Example:**
```yaml
auth:
  strategy: url_token
  login_page: "/cmconnectionstatus.html"
  login_prefix: "login_"       # Some firmware builds use "", others use "login_"
  success_indicator: "Downstream Bonded Channels"
  ajax_login: true
  auth_header_data: false

session:
  cookie_name: "sessionId"
  token_prefix: "ct_"
```

**Handling `login_prefix` variance:** When `login_prefix` is configured, the
strategy uses it. If a modem family has firmware builds that differ only in
prefix (e.g., one build uses a prefix, another sends bare base64), the strategy can be configured to
try both — first with the prefix, then without on failure. This avoids
needing separate modem configs for what is otherwise identical behavior.

#### `form_pbkdf2` Strategy — Config Reference

PBKDF2 (Password-Based Key Derivation Function 2, RFC 8018) auth uses
server-provided salts and client-side key derivation to authenticate without
sending plaintext passwords over the wire. The multi-round-trip flow resembles
HNAP's challenge-response more than a standard form POST.

Evidence base: modems using a shared REST API platform with PHPSESSID sessions,
CSRF tokens, and a JavaScript login flow that performs double PBKDF2 hashing.

**Auth flow:**
```
1. POST /api/v1/session/login  { password: "seeksalthash" }
   → Response: { salt: "<salt>", saltwebui: "<saltwebui>" }
2. Client computes: hash1 = PBKDF2(password, salt, iterations, keylen)
3. Client computes: hash2 = PBKDF2(hash1, saltwebui, iterations, keylen)
4. POST /api/v1/session/login  { password: "<hash2>" }
   → Response: sets PHPSESSID cookie (session.cookie_name), returns CSRF token
5. Subsequent GETs use PHPSESSID cookie only (no CSRF on GETs)
6. Subsequent POSTs (e.g., logout) include PHPSESSID cookie + X-CSRF-TOKEN header (auth.csrf_header)
   If csrf_init_endpoint is set, fetch a fresh token before each POST
```

**Auth config fields** (login mechanics only):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `login_endpoint` | string | required | URL that accepts both salt request and login POST (e.g., `/api/v1/session/login`) |
| `salt_trigger` | string | `"seeksalthash"` | Password value that triggers the server to return salts instead of authenticating. Observed in modem login.js source code. |
| `pbkdf2_iterations` | int | required | PBKDF2 iteration count (e.g., 1000). From login.js `doPbkdf2NotCoded()` parameters. |
| `pbkdf2_key_length` | int | required | Derived key length in bits (e.g., 128). From login.js parameters. |
| `double_hash` | bool | `true` | If true, hash twice: first with `salt`, then with `saltwebui`. All known modems with this auth pattern use double hashing. |
| `csrf_init_endpoint` | string | `""` | Endpoint to fetch a fresh CSRF token (e.g., `/api/v1/session/init_page`). Called before each POST that requires CSRF (login step 4, logout). If empty, CSRF token is extracted from the login response and reused for all POSTs. |

Session cookie, logout URL, and CSRF header for subsequent requests
are declared in the `session` section — see `MODEM_YAML_SPEC.md` Session.

**Example:**
```yaml
auth:
  strategy: form_pbkdf2
  login_endpoint: "/api/v1/session/login"
  salt_trigger: "seeksalthash"
  pbkdf2_iterations: 1000
  pbkdf2_key_length: 128
  double_hash: true
  csrf_init_endpoint: "/api/v1/session/init_page"

session:
  cookie_name: "PHPSESSID"
  max_concurrent: 1
  headers:
    X-Requested-With: "XMLHttpRequest"

actions:
  logout:
    type: http
    method: POST
    endpoint: "/api/v1/session/logout"
```

**Evidence gaps:** The full auth flow is derived from login.js source code
captured in HAR entries, not from observing all HTTP transactions. Only the
first POST (salt request) was captured in the HAR captures for these modems.
The second POST (hashed password) was executed by JavaScript but not recorded
in the HAR entries. The PBKDF2 function parameters are partially redacted in
one HAR (`***REDACTED***`) but visible in another's login.js
(SJCL PBKDF2, 1000 iterations, 128-bit key). Config values should be verified
against real login traffic when these modems are implemented.

**Salt fallback:** These modems' login.js contain a
`salt == "none"` branch that skips PBKDF2 and sends the plaintext password.
This triggers when no password has been configured (first-time setup,
factory reset, ISP default credentials). The `form_pbkdf2` strategy handles
this inline: if the salt response is `"none"`, POST the plaintext password
instead of performing key derivation. This is a branch within the strategy,
not a fallback to a different strategy.

#### `form_sjcl` Strategy — Config Reference

SJCL (Stanford JavaScript Crypto Library) AES-CCM auth encrypts credentials
client-side before POSTing, and decrypts the server's response to extract a
CSRF nonce. The key is derived via PBKDF2 from the password and a
per-session salt embedded in the login page's JavaScript.

Evidence base: gateway firmwares that use the SJCL library for client-side
encryption. The login page embeds `myIv`, `mySalt`, and `currentSessionId`
as JavaScript variables; the login script uses these to AES-CCM encrypt the
credentials before submission.

**Auth flow:**
```
1. GET login page (login_page)
   → Parse JS variables: myIv (hex), mySalt, currentSessionId
2. Derive AES key: PBKDF2(password, mySalt, iterations, key_len)
3. Encrypt credentials:
   plaintext = {"Password": "<pw>", "Nonce": "<sessionId>"}
   ciphertext = AES-CCM(key, iv, plaintext, aad=encrypt_aad)
4. POST login (login_endpoint):
   {"EncryptData": "<hex>", "Name": "<user>", "AuthData": "<encrypt_aad>"}
   → Response: {"p_status": "Match", "encryptData": "<hex>", ...}
   → Sets session cookie (session.cookie_name)
5. Decrypt response:
   AES-CCM decrypt encryptData with aad=decrypt_aad → CSRF nonce
   → Set csrf_header on session for subsequent requests
6. POST session validation (session_validation_endpoint, optional):
   Empty JSON POST with csrf_header → finalizes session
```

**Auth config fields** (login mechanics only):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `login_page` | string | `"/"` | Page URL containing the JS variables (`myIv`, `mySalt`, `currentSessionId`) |
| `login_endpoint` | string | required | URL that accepts the encrypted login POST |
| `session_validation_endpoint` | string | `""` | Optional endpoint to finalize session after login. If set, a POST with the CSRF header is sent after successful decryption. |
| `pbkdf2_iterations` | int | required | PBKDF2 iteration count (from login.js) |
| `pbkdf2_key_length` | int | required | Derived key length in bits (from login.js) |
| `ccm_tag_length` | int | `16` | AES-CCM authentication tag length in bytes |
| `encrypt_aad` | string | `"loginPassword"` | AAD (Additional Authenticated Data) for encrypting the login payload |
| `decrypt_aad` | string | `"nonce"` | AAD for decrypting the server response to extract the CSRF nonce |
| `csrf_header` | string | `""` | Header name for the CSRF nonce on subsequent requests. If empty, no CSRF nonce is extracted. |

Session cookie and logout are declared in the `session` and `actions`
sections — see `MODEM_YAML_SPEC.md`.

**Example:**
```yaml
auth:
  strategy: form_sjcl
  login_page: "/"
  login_endpoint: "/api/login"
  session_validation_endpoint: "/api/session"
  pbkdf2_iterations: 1000
  pbkdf2_key_length: 128
  ccm_tag_length: 16
  encrypt_aad: "loginPassword"
  decrypt_aad: "nonce"
  csrf_header: "csrfNonce"

session:
  cookie_name: "sid"
  max_concurrent: 1
  headers:
    X-Requested-With: "XMLHttpRequest"

actions:
  logout:
    type: http
    method: POST
    endpoint: "/api/session"
```

**Dependency:** `form_sjcl` requires the `cryptography` package for
AES-CCM primitives. Install Core with the `[sjcl]` extra:
`pip install solentlabs-cable-modem-monitor-core[sjcl]`. If the package is
missing at runtime, the strategy returns `AuthResult.FAILURE` with an
install instruction — no import error crash.

### Session Management

Maintains authenticated state between requests. For the HTTP transport,
session is independent from auth — the same auth strategy can use different
session mechanisms across modems. For HNAP, session is locked to the transport.

| Mechanism | Transport |
|-----------|-----------|
| Stateless | HTTP |
| Cookie | HTTP |
| CSRF token | HTTP |
| Nonce | HTTP |
| URL token | HTTP |
| HNAP session | HNAP |

Session config is independent from auth config — different modems using
the same auth strategy often have different session mechanisms. See
[MODEM_YAML_SPEC.md](MODEM_YAML_SPEC.md#session) for config fields
(cookie names, token prefixes, concurrency limits, headers, logout).

### Resource Loaders

Fetch the resources declared in parser.yaml and return them as a keyed dict
for the parser. Transport determines the fetch mechanism (HTTP GET/POST vs
HNAP SOAP), and format determines the decode step (`BeautifulSoup` for HTML
formats, `dict` for structured formats and HNAP). Auth and session state
are already established upstream — the loader attaches credentials to
requests but doesn't manage them.

See `RESOURCE_LOADING_SPEC.md` for the full resource dict contract, loader
behavior per transport, URL construction, path deduplication, and HNAP
batching details.

### Parsing: parser.yaml + parser.py

Parsing has three distinct roles:

**`BaseParser` (ABC)** — the extraction interface. Eight format-specific
implementations: `HTMLTableParser`, `HTMLTableTransposedParser`,
`HTMLFieldsParser`, `JSEmbeddedParser`, `JSJsonParser`, `HNAPParser`, and
`StructuredParser` (ABC) with two subclasses — `JSONParser` and
`XMLParser`. Both structured formats receive `dict` from the loader
(via `json.loads()` or `xmltodict.parse()`); `StructuredParser` holds
the shared dict-path extraction pipeline, while `XMLParser` adds
normalization for xmltodict quirks (`@attribute` keys, `#text`
unwrapping, single-element list coercion). `JSJsonParser` extracts
JSON arrays from JavaScript variable assignments
(`varName = [{...}];`) inside `<script>` tags — distinct from
`JSEmbeddedParser` which handles pipe-delimited `tagValueList` strings.
It reuses `JSONParser`'s field extraction and channel type logic.
Each takes section config + resources and returns extracted data
(channel list or system_info dict). Field normalization (type
conversion, unit stripping, frequency normalization), channel type
detection, and filter application happen during extraction — they are
`BaseParser` implementation responsibilities.

**`ModemParserCoordinator`** — factory and orchestrator. This is what
the rest of the system calls: `parse(resources) → ModemData`.
Internally it reads parser.yaml, creates `BaseParser` instances per
section based on the `format` field (factory), runs them against the
resource dict, merges companion table fields into primary channels
(when `merge_by` is declared), passes results + resources to parser.py
if present (chaining), and assembles `ModemData` from section results.

**parser.py** — optional post-processor, not a subclass. Receives the
`BaseParser` output plus the raw resources for a section. Can enrich
(add fields), transform (convert values), filter (remove channels),
or fully replace the extraction output. Its output is final —
last-write-wins. parser.py is per-modem and can only affect its own
modem's output.

**Pipeline:**

```
ModemParserCoordinator.parse(resources)
  for each section (downstream, upstream, system_info):
    parse primary tables → concatenate → channel list
    parse companion tables (merge_by) → merge fields into channel list
    parser.py post-processes (if present) → final section data
  assemble → ModemData
```

Eight extraction formats in two tiers. Seven general-purpose formats
(`table`, `table_transposed`, `javascript`, `javascript_json`, `hnap`,
`json`, `xml`) are valid for any section. One section-level format
(`html_fields`) is valid only for `system_info` sources. Format selection
is per-section — a modem's `downstream` can use `table_transposed` while
its `system_info` uses `html_fields` or `javascript`. `parser.yaml`
declares the format and field mappings per section. Capabilities are
implicit — the presence of a mapping IS the capability declaration.

See `PARSING_SPEC.md` for the full specification: per-section format
selection, parser.yaml schema per format, parser.py post-processing
contract, resource dict contract, and output format.

### Data Models

Two collection models with independent lifecycles:

- **`ModemData`** — parsed modem data, updated on the data polling cadence
  - `downstream`, `upstream` — lists of `ChannelData`
  - `system_info` — `SystemInfo` fields
  - `docsis_lock_state` — derived from channel lock status during parsing
- **`HealthInfo`** — operational health, updated on the health check cadence
  - `icmp_latency_ms` — ICMP round-trip time
  - `http_latency_ms` — HTTP probe response time (None when collection evidence suppresses the probe)
  - `health_status` — derived composite state (see below)

**Why two models?** Ping is lightweight. Parsing is heavy. A flaky modem
may need fast heartbeats (ping every 30s) without hammering the web
interface (data poll every 10 minutes). Each model has its own cadence and
lifecycle.

**`ModemSnapshot`** — return type of `get_modem_data()`, combining
collection results with health and operational state. Carries
`connection_status` and `docsis_status` (derived by the orchestrator),
`modem_data` from the collector (None on failure), and `health_info`
from the health monitor. Channel counts and aggregate fields are
already in `system_info` — computed by the parser coordinator.

**`OrchestratorDiagnostics`** — operational diagnostics snapshot from
`diagnostics()`, including poll timing, auth failure streak, circuit
breaker state, and per-resource fetch details (`ResourceFetch`).

**`ChannelData`** — per-channel metrics for downstream and upstream:
  - Fixed fields: channel ID, frequency, power, SNR, lock status,
    modulation, channel type, corrected and uncorrected codewords
  - Upstream adds `symbol_rate`, omits SNR and codewords

**`SystemInfo`** — mix of structured and dynamic fields:
  - Structured: `system_uptime`, `last_boot_time`, `software_version`,
    `hardware_version`, `model_name`
  - Dynamic: modem-specific fields (e.g., `connectivity_state`,
    `boot_status`) pass through without core needing to understand them
  - Core derives `last_boot_time` from `system_uptime` when the modem
    doesn't provide it natively — consumers see the same field regardless
    of source

**`ModemIdentity`** — static modem metadata from modem.yaml, populated
once at config load time. Built by `load_modem_config()`. Consumers
use it for display and device registration.

See [ORCHESTRATION_SPEC.md](ORCHESTRATION_SPEC.md#data-models) for
field-level definitions of `ModemSnapshot`, `OrchestratorDiagnostics`,
`ResourceFetch`, and `ModemIdentity`.

**Status** — three independent signals, each derived from different data:

- `connection_status` (on `ModemSnapshot`) — from pipeline outcome
- `docsis_status` (on `ModemSnapshot`) — from channel `lock_status` fields
- `health_status` (on `HealthInfo`) — from probe results

See [ORCHESTRATION_SPEC.md](ORCHESTRATION_SPEC.md#data-models) for
per-value definitions (`ConnectionStatus`, `DocsisStatus`, `HealthStatus`).

Consumers compose these into a display state. The HA integration's
Status sensor uses a priority cascade — see `ENTITY_MODEL_SPEC.md`.

**Capabilities are implicit.** A field mapping in parser.yaml or an
override in parser.py declares the capability. If downstream channels
are mapped, the modem has downstream channel sensors. If `system_uptime`
is mapped, the modem has an uptime sensor. No separate capabilities list
in modem.yaml — the parser output IS the capability declaration.

The two exceptions are modem-side actions: `actions.restart` in
modem.yaml declares restart capability (user-triggered), and
`actions.logout` declares logout capability (system-triggered session
cleanup). Both use the same action schema (`type: http` or
`type: hnap`). No other modem commands are supported — the
integration is read-only monitoring plus session lifecycle management.
See MODEM_YAML_SPEC.md Actions section for the full schema.

**Absent capability = absent entity.** If the parser doesn't extract a
field, the corresponding HA entity is never created — no greyed-out
buttons, no disabled switches, no "not supported" placeholders. The UI
only shows what the modem can actually do.

This is deliberate. A disabled button invites questions ("why can't I click
this?") and support requests. A missing button is invisible — users don't
miss what was never there. It also avoids false promises: some modems had
reboot disabled in firmware after the 2015–2016 ARRIS CSRF vulnerability
that affected 135 million devices. The modem literally has no restart
endpoint, so showing a greyed-out reboot button would be misleading.

### Config Schema

Schema that defines modem.yaml structure. Pydantic models validate
during development and CI — an HTTP modem declaring HNAP auth is
rejected before it ships. Runtime loads into dataclasses.

modem.yaml serves two purposes based on `status`:
- **Working modems** (`verified`, `awaiting_verification`, `in_progress`) —
  full config including auth, session, actions, hardware
- **Database entries** (`unsupported`) — identity and hardware info only,
  documents modems awaiting data or locked down

#### Auth config is a discriminated union

The `auth.strategy` field selects a **per-strategy dataclass**. Each
strategy has its own config type with only the fields that strategy uses:

```python
@dataclass
class FormAuthConfig:
    action: str
    username_field: str = "username"
    password_field: str = "password"
    encoding: str = "plain"
    hidden_fields: dict = field(default_factory=dict)
    login_page: str = ""
    form_selector: str = ""
    success_redirect: str = ""
    success_indicator: str = ""

@dataclass
class HnapAuthConfig:
    hmac_algorithm: str   # "md5" or "sha256"
```

`load_modem_config()` reads `auth.strategy`, selects the matching
dataclass, and populates it from the YAML fields. The result is a
typed config where invalid fields don't exist — a `FormAuthConfig`
has no `hmac_algorithm`, an `HnapAuthConfig` has no `encoding`.

**Strategies accept only their own config dataclass:**

```python
class FormAuthManager(BaseAuthManager):
    def __init__(self, config: FormAuth): ...

class HnapAuthManager(BaseAuthManager):
    def __init__(self, config: HnapAuth): ...
```

No dict intermediary, no generic `AuthConfig` bag of optional fields,
no `SessionConfig` — session state is handled by the runner after auth
completes. The dataclass IS the runtime config — the strategy accepts
exactly the type the loader produces.

---

## Core Extraction Pipeline

The extraction pipeline is the core data path — it runs identically at
runtime (against a real modem) and during testing (against a HAR mock
server). The only difference is the server: real network endpoint vs
localhost replay. Every other component — auth, loaders, coordinator,
parsers — is the same code on the same path.

```
Auth Manager ──▶ Resource Loader ──▶ Coordinator + Parsers ──▶ Post-Parse Filters ──▶ ModemData
     │                  │                     │                       │
     ▼                  ▼                     ▼                       ▼
 AuthResult         resources dict      parsed channels         filtered channels
 (session,          {path: content}     + system_info           + system_info
  cookies,
  private_key)
```

### Stage 1: Authentication

**Input:** modem.yaml (auth config), session, base URL, credentials
**Output:** `AuthResult` (success/failure, session cookies, auth context)
**Component:** `auth.factory.create_auth_manager()` → strategy-specific adapter

The auth manager is created from modem.yaml's `auth` block. It configures
the session (headers, cookies), then authenticates against the server. On
success, the session carries auth state (cookies, tokens) for subsequent
requests. HNAP auth also produces a `private_key` for request signing.

### Stage 2: Resource Loading

**Input:** parser.yaml (resource URLs), authenticated session, base URL
**Output:** `resources` dict — `{url_path: content}`
**Component:** `HTTPResourceLoader` or `HNAPLoader`

Two transport paths, selected by `modem.yaml.transport`:

**HTTP transport** (`HTTPResourceLoader`):
- Derives fetch targets from parser.yaml via `collect_fetch_targets()`
- Fetches each resource URL independently over HTTP
- HTML responses → `BeautifulSoup` objects
- JSON responses → parsed dicts
- URL token modems append session token to query string

**HNAP transport** (`HNAPLoader`):
- Derives HNAP action names from parser.yaml response keys
- Sends a single batched SOAP POST to `/HNAP1/`
- Signs request with HMAC (MD5 or SHA256) using the private key from auth
- Returns `{"hnap_response": {merged_action_responses}}`

### Stage 3: Parsing

**Input:** `resources` dict, parser.yaml, parser.py (optional)
**Output:** `ModemData` dict — `{downstream: [...], upstream: [...], system_info: {...}}`
**Component:** `ModemParserCoordinator`

The coordinator iterates parser.yaml sections (downstream, upstream,
system_info). For each section, it selects the format-specific parser
based on the `format` field:

| Format | Parser | Input Type |
|--------|--------|------------|
| `table` | `HTMLTableParser` | BeautifulSoup |
| `table_transposed` | `HTMLTableTransposedParser` | BeautifulSoup |
| `javascript` | `JSEmbeddedParser` | BeautifulSoup (script tags) |
| `javascript_json` | `JSJsonParser` | BeautifulSoup (script tags) |
| `json` | `JsonParser` | dict |
| `hnap` | `HNAPParser` | dict (hnap_response) |
| `html_fields` | `HTMLFieldsParser` | BeautifulSoup |

Each parser extracts channels (list of field dicts) or system_info
(flat field dict) from the resource content using the field mappings
in parser.yaml.

If a `parser.py` post-processor exists, its `PostProcessor.process()`
method runs after the config-driven extraction, allowing custom logic
that parser.yaml can't express.

### Stage 4: Post-Parse Filtering

**Input:** `ModemData` dict, modem.yaml behaviors config
**Output:** filtered `ModemData` dict
**Component:** `filter_restart_window()`

Optional. If modem.yaml declares `behaviors.zero_power_reported` and
`behaviors.restart.window_seconds`, channels with zero power during
the restart window are filtered out.

### Test Harness: Same Pipeline, Mock Server

The test harness (`test_harness/runner.py`) exercises this exact pipeline.
The substitution:

| Runtime | Test |
|---------|------|
| Real modem at `192.168.100.1` | `HARMockServer` on localhost |
| User-provided credentials | Fixed `admin`/`password` |
| Live HTTP/HNAP responses | HAR-captured response replay |

Everything else is identical — same auth factory, same loaders, same
coordinator, same parsers. The mock server:

1. Builds a route table from HAR response bodies
2. Creates an auth handler from modem.yaml (simulates the modem's auth)
3. Serves responses on an ephemeral localhost port
4. The pipeline runs against this server as if it were a real modem

**Golden file comparison** follows the pipeline: the output `ModemData`
is compared field-by-field against the committed `modem.expected.json`.
Zero diffs = pipeline produces the same output as when the golden file
was reviewed and committed. Any diff is a regression.

When a test runs, the actual pipeline output is written to
`modem.actual.json` alongside the HAR file. On pass, the file is
cleaned up. On failure, the file persists for inspection and
side-by-side diffing against the golden file. These files are
gitignored (`*.actual.json`) and never committed.

**Golden file trust assumption:** The golden file is reviewed once by a
human during the intake process and then becomes the regression baseline.
All future test runs validate against it. If the initial HAR
interpretation is incorrect — wrong field mapping, misidentified format,
bad channel_type inference — the tests will reinforce the incorrect
output indefinitely. The golden file review during intake is the critical
correctness gate. After commit, the regression only guards against drift
from whatever was committed, right or wrong. This is by design — the
intake process (MCP scaffolding + LLM iteration + human review) is where
correctness must be established.

### Two Regression Scopes

**Core regression** — committed configs through the extraction pipeline:
- Uses committed modem.yaml + parser.yaml + parser.py
- Runs HAR through mock server → auth → load → parse → golden file comparison
- Tests: does the existing, working system still work?
- Implemented by: catalog test suite (auto-discovered HAR/golden file pairs)
- Pass criteria: zero golden file drift

**MCP regression** — MCP-generated configs through the extraction pipeline:
- Uses HAR → MCP intake pipeline → generated modem.yaml + parser.yaml
- Overwrites committed configs with generated versions
- Runs same extraction pipeline → golden file comparison
- Tests: can the MCP pipeline reproduce working configs from a HAR alone?
- Pass criteria: zero golden file drift (MCP output = manual curation)
- Current state: significant drift (pipeline gaps in field mapping, type
  normalization, channel type inference, format-specific extraction)

---

## Runtime Polling Loop

After setup, the integration polls the modem on a user-configured cadence
(default 10 minutes). The orchestrator is a policy engine that delegates
execution to three specialized components. Consumers own scheduling —
HA uses DataUpdateCoordinator, CLI tools use a loop.

```
Orchestrator (policy + composition)
 ├─ ModemDataCollector — one collection cycle → ModemData | signal
 ├─ HealthMonitor      — probe cycle → HealthInfo
 └─ RestartMonitor     — recovery cycle → complete | timeout
```

**Orchestrator** — decides *what to do* with results. Owns all policy:
backoff, circuit breaker, error recovery, status derivation, state
transitions. Does not own scheduling or threads. Consumers call
`get_modem_data()` when they want data.

**ModemDataCollector** — executes a single collection cycle: auth manager
→ resource loader → parser. Returns `ModemData` on success or a signal
(auth failure, parse error, connectivity error) on failure. Stateless
per invocation — the auth manager handles session reuse across calls.

**HealthMonitor** — runs health probes (ICMP → HEAD → data poll fallback)
on its own cadence, independent of data polling. Returns `HealthInfo`.
Lightweight — never triggers full auth or parsing.

**RestartMonitor** — manages two-phase restart recovery after a planned
restart (user button press) or unplanned restart (ISP/power). Phase 1:
wait for modem to respond. Phase 2: wait for channel counts to stabilize.
Used by both planned restarts (orchestrator dispatches restart action,
then hands off to RestartMonitor) and unplanned restarts (orchestrator
detects `unreachable → online` transition, hands off for phase 2).

Protocol layers signal conditions (exceptions, return values); the
orchestrator owns all policy (retry, backoff, error reporting). This
separation ensures no hidden policy in protocol layers.

See `RUNTIME_POLLING_SPEC.md` for the full specification: poll cycle
sequence, signal and policy separation, session lifecycle (reuse, stale
retry, backoff, single-session logout), health pipeline, modem restart
(planned and unplanned), and per-poll diagnostics.

---

## Modem Contract

What a modem must provide to plug into the system:

### Required

- **`modem.yaml`** (or `modem-{variant}.yaml`) — everything about the modem
  except parsing: identity (manufacturer, model, model_aliases, brands,
  transport), auth strategy config, hardware, session config,
  metadata (status, attribution, ISPs).

  Single-variant modems use `modem.yaml`. Multi-variant modems use
  `modem-{variant}.yaml` files — one per firmware variant. All variants in a
  directory must declare the same `model` value.

  See `MODEM_DIRECTORY_SPEC.md` for the multi-variant merge contract.

- **`tests/`** — test fixtures directory. Contains HAR captures (pipeline
  input) and expected output golden files (pipeline assertions). No test
  code — the test harness lives in Core.

- **`tests/modem.har`** — PII-scrubbed HAR capture. Source of truth for
  analysis, testing, and validation. Required for working modems
  (`verified`, `awaiting_verification`, `in_progress`). Not required for
  `unsupported` modems.

  **Completeness criteria** — a HAR must demonstrate:
  - Pre-auth flow visible (first request returns 401 or login page, not
    cached/authenticated session data)
  - Auth mechanism identifiable from response headers or login sequence
  - All data endpoints exercised with actual response content
  - One capture per firmware variant (should match variant yaml names)
  - Captured with har-capture v0.4.4+ (includes HTTP probe and cookie
    snapshots) when possible

- **`tests/modem.expected.json`** — golden file containing the expected
  `ModemData` output (downstream channels, upstream channels, system_info)
  when the paired HAR is replayed through the full pipeline. Generated by
  running the pipeline against a HAR mock server, then reviewed and
  committed. All future runs are regression tests against this file.

  **Naming convention:** `{name}.har` pairs with `{name}.expected.json`.
  For variants: `modem-{variant}.har` → `modem-{variant}.expected.json`.

### Parsing (at least one required)

- **`parser.yaml`** — declarative extraction config. Defines field mappings,
  table selectors, column indices, delimiters, and JSON paths that the
  `BaseParser` implementations consume. The `format` field selects which
  parser (e.g., `table` → `HTMLTableParser`). The presence of a mapping
  declares the capability — no separate capabilities list needed.

- **`parser.py`** — optional post-processor for modem-specific quirks that
  can't be expressed declaratively. Receives the `BaseParser` output plus
  raw resources, and can enrich, transform, or replace the extracted data.
  Not a subclass — a hook invoked by `ModemParserCoordinator`.

At least one of parser.yaml or parser.py is required. They can be mixed —
parser.yaml handles standard extraction, parser.py post-processes
sections that need code. When extraction is too complex for declarative
config (e.g., JSEmbedded with dynamic field discovery), parser.py alone
is valid. The implementer decides where to draw the line.

**parser.yaml and parser.py never contain auth or metadata.
modem.yaml never contains extraction logic.**

### What the modem gets back

Its data parsed into the standard `ModemData` shape — channels with frequency,
power, SNR, and error counts. The modem doesn't need to know about HA sensors,
coordinators, or any upstream concerns.

---

## Firmware Variants and Modem Families

Some modem models ship with multiple firmware families that differ in
protocol, auth mechanism, or data format. These aren't minor config
differences — they can require different parsing strategies, making them
functionally distinct modems that share a model name.

### parser.yaml + modem-{variant}.yaml (Decided)

Extraction config is per-modem and shared. Auth config and metadata
(contributors, verification status, ISPs) are per-variant.

**`parser.yaml`** (and/or `parser.py`) defines how to extract data from
resources — field mappings, table selectors, delimiters. Capabilities are
implicit from the mappings. Shared across all firmware variants.

**`modem.yaml`** (or `modem-{variant}.yaml`) defines everything else —
identity, transport, auth, hardware, metadata. Each
variant file has one auth strategy. Per-variant verification and
attribution are natural — they live in the variant file, not a shared blob.

Single-variant modems: `modem.yaml` + `parser.yaml` (and/or `parser.py`)
Multi-variant modems: `modem-{variant}.yaml` files + shared `parser.*`

See `MODEM_DIRECTORY_SPEC.md` for the full assembly contract and examples.

### Same transport = same directory

If firmware variants share a transport (same parsing, same endpoints), they
belong in one directory with shared `parser.*`. Each variant gets its
own `modem-{variant}.yaml` with a single auth strategy.

```
modems/netgear/cm1200/
├── parser.py               # JSEmbedded extraction
├── modem-noauth.yaml       # auth: none
├── modem-basic.yaml        # auth: basic (challenge_cookie)
└── tests/
    ├── modem.har
    ├── modem.expected.json
    ├── modem-basic.har
    └── modem-basic.expected.json
```

### Different transport = different directory

If variants require a different **transport** (e.g., `http` vs `hnap`), they
need separate modem directories. A transport change means different parser,
different auth strategy, different endpoints — it's a different modem that
happens to share a model number.

**The determinant is usually ISP-provisioned firmware, not hardware revision.**
Cable modems receive firmware via DOCSIS provisioning. The same hardware
revision can run different firmware depending on the ISP. Users cannot
determine their firmware family during setup — they can only answer behavioral
questions like "does your modem require login?"

### Modem families (shared UI across models)

Some manufacturers use the same web interface across multiple model numbers,
sharing identical page structure, auth, and endpoints — only the model name
and metadata differ.

With the parser.yaml + modem-{variant}.yaml split, families share one
`parser.yaml` (extraction mappings) and each model gets its own variant
yaml with per-model metadata. `model_aliases` and `brands` in `modem.yaml`
provide alternative names for config flow search.

### Evidence: Multi-Variant Modem

A modem with three firmware families can produce four variants. All HTML
variants use the same HTML table structure and share one parser, but have
fundamentally different auth flows.

| Firmware family | Auth | Post-login session | Variant file |
|-----------------|------|--------------------|--------------|
| No-auth firmware | `none` | N/A | `modem-noauth.yaml` |
| Token firmware (build A) | `url_token` (with prefix) | Token in URL (`?ct_<token>`) | `modem-url-token.yaml` |
| Token firmware (build B) | `url_token` (bare base64) | Cookie only (no token in URL) | `modem-cookie.yaml` |
| HNAP firmware | HNAP (HMAC-MD5) | `sessionToken` cookie | Separate dir |

Two variants from the same firmware family can differ in more than just
`login_prefix`. Their entire post-login session mechanisms may be different:
one extracts a token from the login response body and appends it to
subsequent URLs (`?ct_<token>`), the other gets an empty response body and
relies on cookies only. Each needs its own complete `url_token` config — its
own variant yaml.

```
modems/<mfr>/<model>/
├── parser.yaml             # table selectors, column mappings (shared)
├── modem-noauth.yaml       # auth: none (ISP firmware with no login)
├── modem-url-token.yaml    # auth: url_token (prefix variant)
├── modem-cookie.yaml       # auth: url_token (cookie-only session)
├── parser.py
└── tests/
    ├── modem.har
    ├── modem.expected.json
    ├── modem-url-token.har
    ├── modem-url-token.expected.json
    ├── modem-cookie.har
    └── modem-cookie.expected.json
```

An HNAP variant is a separate directory — different transport, different
parsing config, needs its own parser.

Hardware version does not determine the variant: multiple hardware revisions
can run the same firmware with identical behavior. The same hardware revision
can also appear on a different firmware build with a different token format.
The firmware is ISP-provisioned.

---

## Hooks and Configuration Boundaries

Only parsing exposes override hooks (`parser.py`). Auth and session are
fully handled in core through configuration (`modem.yaml`).

### Why parsing has two expression modes

Parsing has genuine structural variety — HTML tables, JavaScript variables,
transposed layouts, HNAP delimiters. `parser.yaml` handles the common
patterns declaratively via `BaseParser` implementations. `parser.py`
post-processes the rest via code. Both produce the same `ModemData` output.

See "Parsing: parser.yaml + parser.py" in Core Components for details.

### Why auth and session have no hooks

The auth and session variety across supported modems is wide but shallow — different
values, not different behaviors. Every variation maps to a config field:

| Variation | Config |
|-----------|--------|
| Form POST URL | `auth.action` |
| Password field name | `auth.password_field` |
| Password encoding | `auth.encoding` |
| HMAC algorithm | `auth.hmac_algorithm` |
| Session cookie name | `session.cookie_name` |
| Logout mechanism | `actions.logout` (shared action schema) |
| Concurrency limit | `session.max_concurrent` |
| CSRF token | `auth.csrf_header` (strategy-specific; `form_pbkdf2` currently) |

No auth hooks means:
- **Smaller security surface.** Auth touches credentials. One audited
  implementation per strategy, not per-modem overrides that could mishandle
  passwords or leak tokens.
- **New patterns belong in core.** If a modem needs a genuinely new auth flow
  (OAuth, digest, etc.), that's a new core strategy — not a per-modem hook.
  It applies to any future modem using the same protocol.

### Summary

| Layer | Config | Code Hooks | Rationale |
|-------|--------|------------|-----------|
| Parsing | `parser.yaml` | `parser.py` | Structural variety; declarative where possible, code where needed |
| Auth | `modem.yaml` | None | Variation is values, not behavior; smaller security surface |
| Session | `modem.yaml` | None | Cookie names, URLs, headers are config |

---

## Testing

Testing is organized by package boundary. Each package has its own test
concerns, fixtures, and assertion style. Detailed test specifications
will live in per-package docs; this section defines the architectural
decisions that affect directory structure and package boundaries.

### Three test scopes

**1. Core — isolated unit tests**

Strategy extraction logic, auth strategies, config schema validation,
data model invariants. Tests use synthetic inputs (hand-crafted HTML
snippets, JSON structures, delimiter strings) designed to exercise
specific code paths. No real modem data, no HAR files, no network.

Core also owns the **test harness** — shared infrastructure for HAR
replay, golden file comparison, and structural assertions. The harness
lives in Core so that Catalog contributors cannot modify test assertions
or loader logic. Catalog's CI installs Core and uses Core's test harness.

**2. Catalog — HAR replay integration tests**

Each modem's `tests/` directory contains HAR captures (input) and
expected output golden files (assertions). The test harness in Core
discovers these fixtures, replays each HAR through a mock server, runs
the full pipeline (auth → load → parse), and compares the output
against the golden file.

```
modems/{mfr}/{model}/tests/
├── modem.har                  # HAR capture (pipeline input)
├── modem.expected.json        # golden file (expected ModemData output)
├── modem-{variant}.har        # variant HAR
└── modem-{variant}.expected.json  # variant golden file
```

**Naming convention:** `{name}.har` pairs with `{name}.expected.json`.
The test harness discovers HAR files, finds the matching expected
output, and resolves which `modem*.yaml` applies (base or variant).

**Golden file lifecycle:**
1. Contributor submits HAR capture via `har-capture`
2. MCP pipeline: `validate_har` → `analyze_har` → `enrich_metadata` → `generate_config` → `generate_golden_file` → `write_modem_package`
3. `run_tests` replays HAR against mock server, compares output to golden file
4. Developer reviews golden file against the raw HAR responses
5. Reviewed output is committed as `{name}.expected.json`
6. All future runs are regression tests against the golden file

Golden files contain the full `ModemData` output — downstream channels,
upstream channels, and system_info dict. If anything changes, the diff
shows exactly what shifted.

**Structural assertions** are also derived from parser.yaml at test
time — field presence, field types, frequency normalization, canonical
channel_type values, filter rules applied. These catch a class of bugs
that golden file comparison alone might miss (e.g., a field present
with the wrong type that happens to serialize identically).

**Regression firewall:** `BaseParser` tests run against **all modems that
use that parser**, not just the modem being worked on. Enhancing
`HTMLTableParser` triggers every Catalog modem test that uses
`format: table`.

**3. HA Integration — adapter tests**

Config flow, coordinator, entity model, device registry. Tests mock
Core's engine interface — they verify HA-specific behavior (entity
creation, state updates, availability) without running the real
pipeline. Scope and details TBD in a dedicated HA test spec.

### No test code in Catalog

The `tests/` directory in each modem contains only data files — HAR
captures and golden files. No pytest files, no conftest, no helpers.
The test harness in Core consumes these fixtures. This means:

- Adding a modem never requires writing test code — provide a HAR and
  a reviewed golden file
- Strategy changes are validated across all modems automatically
- Contributors cannot accidentally weaken assertions

---

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| `parser.yaml` + `parser.py` for parsing, `modem.yaml` for everything else | Clean separation: parser.* is ONLY responsible for parsing. modem.yaml owns identity, auth, metadata. Implementer decides where to draw the declarative/code line per modem. |
| Capabilities are implicit from parser.yaml/parser.py | Presence of a mapping IS the capability declaration. No separate capabilities list to maintain. No mapping = no entity. |
| `modem-{variant}.yaml` for firmware variants | Each file represents one firmware variant with its own auth, session, and ISP config. Multi-variant modems get one file per variant. Implicit merge — no explicit references between variant files. |
| Monorepo with two pip packages + HA integration | Single repo for cross-cutting changes; real package boundaries for AI safety; HA integration distributed via HACS |
| `solentlabs` namespace, `cable_modem_monitor_` prefix | PyPI uniqueness, consistent branding, ties packages to the HA integration name |
| Core is the complete engine | Platform-agnostic — could power HA, a Windows service, a CLI tool. All business logic, ABCs, strategies, loaders, orchestration, test harness. No HA imports, no catalog imports |
| Catalog is content only | No business logic — just YAML configs, parser overrides, HAR files. Core owns the loader that reads them. Test harness lives in Core so catalog contributors can't modify assertions |
| HA Integration is a thin adapter | Config flow, coordinator, entities, diagnostics. Swappable for any platform adapter |
| Base64 encoding is `encoding: base64` on `form`, not a separate strategy | Simpler, already works for modems with base64 form encoding |
| `form_pbkdf2` is a separate strategy, not a flag on `form` | Multi-round-trip challenge-response with server-provided salts and client-side key derivation. Structurally different from form POST with encoding. Affects modems using the same REST API platform with PBKDF2 challenge-response. |
| All non-HNAP modems use `transport: http` | Both HTML-scraping modems and JSON/XML API modems use HTTP requests — the difference is response format, not transport protocol. Format lives in parser.yaml. |
| JS-driven auth handled as `form` variant | Not distinct enough for a separate type |
| HAR captures via `har-capture` utility | Launches fresh browser context — no stale cookies or cached sessions |
| `HealthInfo` separate from `ModemData` | Different cadences — ping is lightweight, parsing is heavy. Each has its own lifecycle |
| Health probe: ICMP → HEAD → data poll | Use lightest available probe; never hammer modem web server unnecessarily |
| No auth discovery | Strategy *selection* is config-driven only. No runtime login page inspection to *determine* auth type — too fragile. Strategies may interact with login pages during *execution* (extracting hidden fields, nonces, salts). |
| No fallback/auto-detection | If no modem.yaml exists, we can't help. User submits HAR, we add support |
| `last_boot_time` derived in core | Transparent to consumers — same field whether modem provides it or core calculates from uptime |
| Dynamic `SystemInfo` fields | Modem-specific fields pass through without core changes. Core only understands structured fields |
| `AuthResult.auth_context` is typed `AuthContext` | Auth strategies store downstream state in a typed `AuthContext` dataclass with `url_token` and `private_key` fields. Runner reads by attribute based on `modem_config.transport`. Adding a transport means adding a field to `AuthContext`, not a magic string key. |
| Coordinator parser registry | Section type → parser function dispatch via dict, not isinstance chain. Five known section types registered; unimplemented formats are stubs that raise `NotImplementedError` with the missing parser name. Adding a format is one registry entry + parser implementation. |
| `enrich_metadata` separates inference from config assembly | `generate_config` assembles YAML from known facts. Inferring facts from HAR analysis (default_host from request URLs, DOCSIS version from channel types) is a different concern. `enrich_metadata` provides structured guidance on inferred/missing/conflicting fields — essential for self-service contributors who need to know what's missing when their PR validation fails. |
| `write_modem_package` for file placement | Pipeline produces configs and golden files in memory. Rather than relying on the LLM to write files with correct names and directory structure, a dedicated tool writes the standard catalog structure. Guarantees file layout matches what the test harness expects. |

---

## Logging

All Core modules use Python's `logging` module with `__name__`-scoped
loggers. Consumers (HA, CLI, test harness) configure handlers and
levels; Core only emits log records.

### Level Conventions

| Level | Use | Examples |
|-------|-----|----------|
| `DEBUG` | Internal state, wire data, parsing details | Challenge received, record too short, pattern did not match |
| `INFO` | Pipeline milestones | Auth succeeded, resource loaded, parse complete, restart-window filter applied |
| `WARNING` | Recoverable issues | Resource not found, table not found, unknown strategy, unmapped channel type |
| `ERROR` | Unrecoverable failures | Auth failed after retries, config load error, golden file mismatch |

### Guidelines

- **DEBUG is the default working level.** Most log calls are DEBUG.
  A modem owner running the integration locally should see clean logs
  at INFO; switching to DEBUG reveals the full pipeline trace.
- **INFO marks success milestones.** One INFO per major pipeline stage
  (auth, load, parse) — not per channel or per field.
- **WARNING means the pipeline continued but data may be incomplete.**
  Missing optional fields, fallback paths taken.
- **ERROR means the pipeline stopped.** Auth rejection, malformed
  config, assertion failure. These map to HA persistent notifications
  or test failures.
- **Never log secrets.** Passwords, tokens, HMAC keys, and session
  cookies must not appear in log output at any level.

---

## Invariants

1. **A `BaseParser` implementation never imports from a modem directory.**
   Modem-specific behavior comes from parser.yaml config or parser.py
   post-processing.

2. **Same config + same responses = same output.** Parsing is deterministic.

3. **Adding a modem cannot break another modem.** Isolated by config, no shared
   mutable state.

4. **Enhancing a `BaseParser` implementation runs all modem tests for that
   format.** The regression firewall.

5. **Core and Catalog have no HA dependencies.** No `homeassistant.*` imports
   in either package. CI enforces this — import boundary violations fail the
   build.

6. **parser.py cannot make network calls.** `ModemParserCoordinator` only
   passes pre-fetched resources — no session, no HTTP client.

7. **Auth and session have no per-modem hooks.** All variation is modem.yaml
   config fields, not code.

8. **`ModemData` and `HealthInfo` are independent.** Neither model depends
   on the other's cadence.

9. **parser.* is ONLY responsible for parsing.** parser.yaml and parser.py
   never contain auth or metadata. modem.yaml never
   contains extraction logic.

10. **Capabilities are implicit.** A mapping in parser.yaml or an override
    in parser.py declares the capability. No separate capabilities list.

11. **Protocol layers signal, orchestrator decides.** Auth, loading, and
    parsing never own retry, backoff, or fallback policy. They raise
    exceptions or return results; the orchestrator decides what to do next.

---

## References

| Document | Purpose |
|----------|---------|
| `ARCHITECTURE_DECISIONS.md` | Design rationale — the "why" behind the architecture |
| `MODEM_YAML_SPEC.md` | modem.yaml schema — identity, auth, session, actions |
| `MODEM_DIRECTORY_SPEC.md` | Catalog directory structure, file roles, assembly rules |
| `PARSING_SPEC.md` | Extraction formats, parser.yaml schema, parser.py contract, output format |
| `RESOURCE_LOADING_SPEC.md` | Resource dict contract, loader behavior per transport |
| `ORCHESTRATION_SPEC.md` | Orchestrator, collector, health monitor, restart monitor — interface contracts and data models |
| `ORCHESTRATION_USE_CASES.md` | Scenario-based use cases — normal ops, auth failures, connectivity, restart, health, lifecycle |
| `RUNTIME_POLLING_SPEC.md` | Poll cycle, session lifecycle, health pipeline, restart recovery |
| `FIELD_REGISTRY.md` | Three-tier field naming authority |
| `VERIFICATION_STATUS.md` | Parser status lifecycle |
| `ONBOARDING_SPEC.md` | MCP-driven modem onboarding workflow |
<!-- Cross-package links: these relative paths work in the monorepo but
     will need updating if packages are published separately to PyPI. -->
| `../../../custom_components/cable_modem_monitor/docs/CONFIG_FLOW_SPEC.md` | Setup wizard step sequence |
| `../../../custom_components/cable_modem_monitor/docs/ENTITY_MODEL_SPEC.md` | Core output → HA entities, attributes, availability |
| `../../../custom_components/cable_modem_monitor/docs/HA_ADAPTER_SPEC.md` | HA wiring — runtime data, coordinators, polling modes, restart, reauth |
