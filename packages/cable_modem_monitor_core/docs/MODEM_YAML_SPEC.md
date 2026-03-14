# modem.yaml Specification

modem.yaml is the configuration file for a cable modem. It declares
everything the system needs to connect, authenticate, and interact with
a modem's web interface — everything except parsing, which lives in
parser.yaml and parser.py.

Single-variant modems use `modem.yaml`. Multi-variant modems use
`modem-{variant}.yaml` files — one per firmware variant. All variants
in a directory share the same `parser.yaml` (and optional `parser.py`).

See [MODEM_DIRECTORY_SPEC.md](MODEM_DIRECTORY_SPEC.md) for the full
directory layout and multi-variant assembly contract.

## Contents

| Section | What it covers |
|---------|----------------|
| [Schema Overview](#schema-overview) | Complete YAML skeleton with annotations |
| [Identity](#identity) | manufacturer, model, transport, default_host, aliases |
| [Auth](#auth) | 7 strategy types with full config examples |
| [Session](#session) | Cookie, single-session, SPA patterns |
| [Actions](#actions) | Restart and logout — http and hnap types |
| [Aggregate](#aggregate) | Derived fields from channel data (e.g., error totals) |
| [Hardware](#hardware) | DOCSIS version, chipset |
| [Timeout](#timeout) | Per-request override |
| [Metadata](#metadata) | Status, attribution, sources, ISPs, notes |
| [Validation Rules](#validation-rules) | Transport constraints, required fields, consistency checks |
| [Multi-Variant Modems](#multi-variant-modems) | Naming, shared files, assembly |
| [Capabilities](#capabilities) | Implicit from parser output |
| [Complete Examples](#complete-examples) | 5 pattern-based modem configs |

---

## Schema Overview

```yaml
# Identity
manufacturer: "Arris"
model: "SB8200"
model_aliases:                    # optional — config flow search
  - "CommScope SB8200"
brands:                           # optional — config flow search
  - "Surfboard"
transport: http                    # http | hnap
default_host: "192.168.100.1"

# Auth
auth:
  strategy: url_token
  # ... strategy-specific fields

# Session (independent from auth)
session:
  cookie_name: "sessionId"
  # ... session fields

# Actions (optional)
actions:
  restart:
    # ... action config
  logout:
    # ... action config

# Aggregate (optional — derived fields from channel data)
aggregate:
  total_corrected:
    sum: corrected
    channels: downstream
  total_uncorrected:
    sum: uncorrected
    channels: downstream

# Hardware
hardware:
  docsis_version: "3.1"
  chipset: "Broadcom BCM3390"

# Timeout (optional, default 10)
timeout: 15

# Metadata
status: verified
sources:
  auth_config: "#81"
  chipset: "FCC filing"
attribution:
  contributors:
    - github: "contributor123"
      contribution: "Initial HAR capture and fixtures"
isps:
  - "Comcast"
  - "Spectrum"
notes: |
  SB8200 HTTPS variant with URL token auth.
references:
  issues:
    - 42
    - 81
```

---

## Identity

| Field | Type | Required | Description |
|-------|------|:--------:|-------------|
| `manufacturer` | string | yes | Manufacturer name (e.g., "Arris", "Netgear", "Motorola") |
| `model` | string | yes | Model identifier (e.g., "SB8200", "CM1200") |
| `model_aliases` | list[string] | no | Alternative model names for config flow search (e.g., `["SB8200v2", "CommScope SB8200"]`) |
| `brands` | list[string] | no | Product branding for config flow search (e.g., `["Surfboard"]`) |
| `transport` | enum | yes | `http` or `hnap` |
| `default_host` | string | yes | Default IP address (e.g., "192.168.100.1") |

`transport` identifies the transport protocol (`http` or `hnap`).
For `http`, auth, session, and format are configured independently.
For `hnap`, the protocol constrains all other axes. See
[Validation Rules](#validation-rules) for details.

`default_host` is the pre-filled value in the config flow. Users can
override it during setup. Most cable modems use `192.168.100.1`.

---

## Auth

Auth declares how the system authenticates with the modem's web
interface. The `strategy` field selects the auth implementation; the
remaining fields are strategy-specific configuration.

```yaml
auth:
  strategy: form            # Discriminator — selects the auth class
  action: "/goform/login"   # Strategy-specific fields
  username_field: "loginUsername"
  password_field: "loginPassword"
  encoding: base64
```

Each modem.yaml (or modem-{variant}.yaml) has exactly one auth
strategy. Multi-variant modems that differ only in auth get separate
variant files.

### `none`

No authentication required. Data endpoints are publicly accessible.

```yaml
auth:
  strategy: none
```

No additional fields. This is the simplest case — modems that expose
their status pages without any login.

Evidence: modems with publicly accessible status pages (no login
required). Common on older DOCSIS 3.0 modems and some ISP-branded
devices that expose read-only status endpoints.

### `basic`

HTTP Basic Authentication. Credentials sent as `Authorization: Basic`
header on every request.

```yaml
auth:
  strategy: basic
  challenge_cookie: false
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `challenge_cookie` | bool | `false` | If `true`, retry with server-set cookie on initial 401. Some modems (CM1200 HTTPS) return a challenge cookie that must be included in the retry. |

Evidence: modems that return a `WWW-Authenticate: Basic` header on
401 responses. Some modems also require a challenge cookie on retry.

### `form`

HTML form POST login. The system POSTs credentials to the specified
endpoint and evaluates the response for success.

```yaml
auth:
  strategy: form
  action: "/goform/login"
  method: POST
  username_field: "loginUsername"
  password_field: "loginPassword"
  encoding: plain
  hidden_fields:
    webToken: ""
  success:
    redirect: "/MotoHome.asp"
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `action` | string | required | Form POST URL |
| `method` | string | `POST` | HTTP method |
| `username_field` | string | `"username"` | Form field name for username |
| `password_field` | string | `"password"` | Form field name for password |
| `encoding` | enum | `plain` | `plain` or `base64` — how the password is encoded before POST |
| `hidden_fields` | map | `{}` | Additional form fields to include (e.g., CSRF tokens, static values) |
| `login_page` | string | `""` | Page to fetch before login to extract hidden fields or nonces. If empty, POST directly without pre-fetch. |
| `form_selector` | string | `""` | CSS selector to find the login form on `login_page` (for extracting action URL and hidden fields dynamically) |
| `success.redirect` | string | `""` | Expected redirect URL after successful login |
| `success.indicator` | string | `""` | String to match in response body to confirm success |

Evidence: modems with HTML login forms. Encoding, field names, and
success indicators vary by manufacturer. Both `goform` and `cgi-bin`
style endpoints are common.

### `form_nonce`

Form POST with a client-generated nonce. Structurally different from
`form` because the response is evaluated by parsing text prefixes
(`Url:` / `Error:`), not by redirect or cookie presence.

```yaml
auth:
  strategy: form_nonce
  action: "/cgi-bin/adv_pwd_cgi"
  nonce_field: "nonce"
  nonce_length: 8
  credential_format: "{nonce}:{password}:{username}"
  success_prefix: "Url:"
  error_prefix: "Error:"
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `action` | string | required | Form POST URL |
| `nonce_field` | string | required | Form field name for the client-generated nonce |
| `nonce_length` | int | `8` | Length of the random nonce string |
| `credential_format` | string | required | Template for the credential string (variables: `{nonce}`, `{password}`, `{username}`) |
| `success_prefix` | string | `"Url:"` | Response body prefix indicating successful login |
| `error_prefix` | string | `"Error:"` | Response body prefix indicating failed login |

Evidence: modems where firmware generates a client-side nonce and
evaluates login success via text prefix responses rather than
redirects or cookies.

### `url_token`

Credentials encoded in the URL query string. The response sets a
session cookie; subsequent requests use a server-issued token in the
query string.

```yaml
auth:
  strategy: url_token
  login_page: "/cmconnectionstatus.html"
  login_prefix: "login_"
  success_indicator: "Downstream Bonded Channels"
  ajax_login: true
  auth_header_data: false

session:
  cookie_name: "sessionId"
  token_prefix: "ct_"
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `login_page` | string | required | Page URL that accepts the token login |
| `login_prefix` | string | `""` | Prefix before base64 token in login URL. Empty = bare base64. |
| `success_indicator` | string | `""` | String to match in login response body |
| `ajax_login` | bool | `false` | Include `X-Requested-With: XMLHttpRequest` header on login |
| `auth_header_data` | bool | `false` | Include `Authorization: Basic` header on data requests |

Session cookie and token prefix for subsequent requests are declared in
the `session` section — see [Session](#session).

Evidence: modems that encode credentials in URL query strings and
issue session tokens for subsequent requests. Firmware variants of
the same model may use different login prefix values.

### `hnap`

HNAP HMAC challenge-response authentication. The system performs a
Login SOAP action, computes an HMAC signature from the challenge, and
signs all subsequent requests with `HNAP_AUTH` headers.

```yaml
auth:
  strategy: hnap
  hmac_algorithm: md5
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `hmac_algorithm` | enum | required | `md5` or `sha256` |

HNAP auth is fully constrained by the transport. The endpoint (`/HNAP1/`),
session mechanism (`uid` cookie + `HNAP_AUTH` header), and protocol are
all fixed. Only the HMAC algorithm varies across modems.

Evidence: modems using the HNAP protocol with HMAC challenge-response.
The HMAC algorithm (MD5 or SHA256) varies across models and hardware
revisions.

### `form_pbkdf2`

Multi-round-trip challenge-response using PBKDF2 key derivation.
The client requests server-provided salts, derives a key via PBKDF2,
and submits the derived hash. Structurally closer to HNAP's
challenge-response than to a simple form POST.

```yaml
auth:
  strategy: form_pbkdf2
  login_endpoint: "/api/v1/session/login"
  salt_trigger: "seeksalthash"
  pbkdf2_iterations: 1000
  pbkdf2_key_length: 128
  double_hash: true
  csrf_init_endpoint: "/api/v1/session/init_page"
  csrf_header: "X-CSRF-TOKEN"

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

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `login_endpoint` | string | required | URL for both salt request and login POST |
| `salt_trigger` | string | `"seeksalthash"` | Password value that triggers salt response |
| `pbkdf2_iterations` | int | required | PBKDF2 iteration count |
| `pbkdf2_key_length` | int | required | Derived key length in bits |
| `double_hash` | bool | `true` | Hash twice: first with `salt`, then with `saltwebui` |
| `csrf_init_endpoint` | string | `""` | Endpoint to fetch a fresh CSRF token (e.g., `/api/v1/session/init_page`). Called before each POST that requires CSRF (login, logout). If empty, CSRF token is extracted from the login response and reused for all POSTs. |
| `csrf_header` | string | `""` | Header name for the CSRF token (e.g., `X-CSRF-TOKEN`). The `form_pbkdf2` strategy fetches the token value (via `csrf_init_endpoint` or login response) and attaches it as this header. Which requests carry the token and how the token is obtained are strategy-specific — other strategies that need CSRF may define their own fields. |

Session cookie, CSRF header, and session-wide headers are declared
in the `session` section. Logout is declared in `actions.logout`.
See [Session](#session) and [Actions](#actions).

Evidence: modems with JavaScript SPA interfaces that use PBKDF2
key derivation for login. Parameters are typically derived from the
modem's login.js source code in HAR captures.

---

## Session

Session owns post-login state: cookie names, CSRF headers, token
prefixes, concurrency limits, and session-wide HTTP headers. Auth
strategies own login mechanics only — if a field is needed to complete
login (e.g., `csrf_init_endpoint`), it stays in auth. Everything the
system needs after login succeeds belongs here.

How to end a session (logout) is declared in `actions.logout` — see
[Actions](#actions). Session declares the *state*; actions declare
the *operations*.

The same auth strategy can use different session mechanisms across
modems. For HNAP, session is implicit (always `uid` cookie +
`HNAP_AUTH` header).

```yaml
session:
  cookie_name: "session"
  max_concurrent: 1
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `cookie_name` | string | `""` | Session cookie name. Empty = stateless (no cookie tracking). |
| `max_concurrent` | int | `0` | Max concurrent sessions. `0` = unlimited. `1` = single-session modem. |
| `token_prefix` | string | `""` | URL token prefix for subsequent requests (url_token auth only) |
| `headers` | map | `{}` | Static headers added to all requests for this session (e.g., `X-Requested-With: XMLHttpRequest` for SPA-style modems). Dynamic headers (CSRF tokens, HNAP signatures, auth tokens) are managed by auth strategies — each strategy defines its own fields for token acquisition and header injection. |

### Stateless

No session section needed (or `session: {}`). Each request is
independent — the auth manager attaches credentials per-request.
Common with `none` and `basic` auth.

### Cookie-based

```yaml
session:
  cookie_name: "session"
```

After successful auth, the modem sets a cookie. The session maintains
this cookie across requests. No further configuration needed unless
the modem has concurrency limits or requires explicit logout.

### Single-session modems

Some modems allow only one active session. If a second session is
attempted while one is active, login fails.

```yaml
session:
  cookie_name: "session"
  max_concurrent: 1

actions:
  logout:
    type: http
    method: GET
    endpoint: "/logout.asp"
```

When `max_concurrent: 1`, the auth manager executes `actions.logout`
**after each poll** to free the session for the user (so they can
access the modem's web UI between polls). There is no pre-login
logout — the integration cannot clear another client's session (it
doesn't have their cookie), and its own stale sessions from a crash
are lost in memory and timeout on the modem side.

If the user (or another client) is already logged in when we attempt
to poll, login fails with `AuthResult.FAILURE` and status reports
`auth_failed`. Recovery happens naturally when the other session ends
(explicit logout or modem-side timeout).

See RUNTIME_POLLING_SPEC.md for the full session lifecycle.

Evidence: modems that reject concurrent sessions — a second login
attempt fails while an existing session is active.

### SPA-style modems

Some modems have JavaScript SPA web interfaces where every request
uses `XMLHttpRequest`. Declare
session-wide headers to apply to all requests:

```yaml
session:
  cookie_name: "PHPSESSID"
  headers:
    X-Requested-With: "XMLHttpRequest"
```

Dynamic headers like CSRF tokens are managed by the auth strategy,
not declared in `session.headers`. Each strategy defines its own
fields for token acquisition and header injection. See
[form_pbkdf2](#form_pbkdf2) for an example.

Action-level `headers` override session-level headers for a specific
action if needed.

---

## Actions

Optional section declaring modem-side actions. Two actions are
supported: `restart` (user-triggered) and `logout` (system-triggered).

The integration's purpose is read-only monitoring. Logout is session
cleanup — the auth manager ends its session so the user can access
the modem's web UI between polls. Restart is the sole state-changing
action, explicitly declared per-modem. No other modem commands are
supported — this is a security and terms-of-service boundary.

Both actions share the same schema with two type discriminators:
`http` for standard HTTP requests and `hnap` for HNAP SOAP-over-JSON.

### Action schema — `type: http`

Standard HTTP request. Covers form-encoded POST, plain GET, and
empty-body POST patterns.

```yaml
actions:
  restart:
    type: http
    method: POST
    endpoint: "/goform/MotoSecurity"
    params:
      UserId: ""
      MotoSecurityAction: "1"
```

| Field | Type | Required | Description |
|-------|------|:--------:|-------------|
| `type` | enum | yes | `http` or `hnap` |
| `method` | string | yes | HTTP method (`GET`, `POST`, etc.). No default — must be explicit. |
| `endpoint` | string | yes | URL path to send the request to |
| `params` | map | no | Form parameters. If present, body is `application/x-www-form-urlencoded`. If absent, no request body. |
| `headers` | map | no | Per-action headers. Merged with session-level `headers` (action wins on conflict). |
| `pre_fetch_url` | string | no | URL to fetch before the action (extract dynamic endpoint or tokens) |
| `endpoint_pattern` | string | no | Regex to extract the actual endpoint from pre-fetch response |

### Action schema — `type: hnap`

HNAP SOAP-over-JSON request. Endpoint (`/HNAP1/`), method (POST),
and content type (`application/json`) are fixed by protocol.

```yaml
actions:
  restart:
    type: hnap
    action_name: "SetArrisConfigurationInfo"
    pre_fetch_action: "GetArrisConfigurationInfo"
    params:
      Action: "reboot"
    response_key: "SetArrisConfigurationInfoResponse"
    result_key: "SetArrisConfigurationInfoResult"
    success_value: "OK"
```

| Field | Type | Required | Description |
|-------|------|:--------:|-------------|
| `type` | enum | yes | `http` or `hnap` |
| `action_name` | string | yes | HNAP SOAP action to invoke |
| `pre_fetch_action` | string | no | Action to call first (extract current config for template vars) |
| `params` | map | no | SOAP parameters. Values with `${key:default}` are replaced with pre-fetch values. |
| `response_key` | string | no | Key in the SOAP response to check |
| `result_key` | string | no | Key within the response to match |
| `success_value` | string | no | Expected value indicating success |

### Logout examples

**Simple GET logout:**

```yaml
actions:
  logout:
    type: http
    method: GET
    endpoint: "/logout.asp"
```

**Form POST with dynamic endpoint:**

```yaml
actions:
  logout:
    type: http
    method: POST
    endpoint: "/goform/logout"
    pre_fetch_url: "/Logout.htm"
    endpoint_pattern: "action='(/goform/logout[^']*)'"
    params:
      nowTime: ""
```

**Empty-body POST with CSRF:**

The CSRF token is managed by the `form_pbkdf2` auth strategy
(`csrf_init_endpoint` + `csrf_header` in auth config). The action
config doesn't need CSRF awareness.

```yaml
auth:
  strategy: form_pbkdf2
  csrf_init_endpoint: "/api/v1/session/init_page"
  csrf_header: "X-CSRF-TOKEN"
  # ... other form_pbkdf2 fields

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

### Behaviors

```yaml
behaviors:
  restart:
    window_seconds: 300
```

| Field | Type | Description |
|-------|------|-------------|
| `restart.window_seconds` | int | Seconds to wait after restart before resuming polling |

---

## Aggregate

Optional section declaring fields derived from channel data. Each entry
defines a field name, an aggregation operation, and the channel scope.

```yaml
aggregate:
  total_corrected:
    sum: corrected
    channels: downstream
  total_uncorrected:
    sum: uncorrected
    channels: downstream
```

| Field | Type | Required | Description |
|-------|------|:--------:|-------------|
| `sum` | string | yes | Channel field to sum (e.g., `corrected`, `uncorrected`) |
| `channels` | string | yes | Scope: `downstream`, `upstream`, or type-qualified `downstream.qam`, `downstream.ofdm`, `upstream.atdma`, `upstream.ofdma` |

**Operations:** Only `sum` is supported. This section is purpose-built
for error totals, not a general aggregation engine.

**Ownership:** Aggregation is a behavioral declaration — the modem
package decides whether and how totals are computed. Parser.yaml stays
pure extraction.

**Execution:** The orchestrator reads `aggregate` after parsing
completes and computes the fields from the parsed channel data. Results
are added to the response alongside parser output.

**Conflict rule:** If parser.yaml maps a `system_info` field with the
same name as an `aggregate` entry (e.g., both produce `total_corrected`),
build-time validation rejects the config. One source per field — modem-
native totals mapped in parser.yaml OR orchestrator-derived totals
declared here, never both.

Modems that provide native totals in their web UI (e.g., "Total
Correctable Codewords" in an HTML table) should map them as
`system_info` fields in parser.yaml instead of using `aggregate`.

**Channel counts** (`downstream_channel_count`, `upstream_channel_count`)
are not part of `aggregate` — they are implicit orchestrator behavior.
If downstream or upstream channels exist in parser output, the
orchestrator counts them automatically. See
[RUNTIME_POLLING_SPEC.md](RUNTIME_POLLING_SPEC.md) for details.

---

## Hardware

```yaml
hardware:
  docsis_version: "3.1"
  chipset: "Broadcom BCM3390"
```

| Field | Type | Required | Description |
|-------|------|:--------:|-------------|
| `docsis_version` | string | yes | DOCSIS specification version ("3.0" or "3.1") |
| `chipset` | string | no | Modem chipset (informational) |

---

## Timeout

```yaml
timeout: 15
```

Per-request timeout in seconds. Applies to each individual HTTP request
(page fetch, HNAP call), not to the total poll cycle. Default: 10
seconds.

Override for slow modems — some cable modems take 12-20 seconds to
render data pages, particularly those with older chipsets or HTTPS
endpoints.

---

## Metadata

Metadata is required for all modems, including `unsupported` entries.
It documents what we know about a modem even before we can monitor it.

### Status

```yaml
status: verified
```

| Value | Meaning |
|-------|---------|
| `verified` | Parser works, confirmed by user reports |
| `awaiting_verification` | Parser written, waiting for user confirmation |
| `in_progress` | Work underway, not yet functional |
| `unsupported` | Placeholder — awaiting user data |

`unsupported` modems have identity and hardware fields only — no auth,
no pages, no parser. They document modems we know about but can't
support yet.

### Attribution

```yaml
attribution:
  contributors:
    - github: "contributor123"
      contribution: "Initial HAR capture and parser"
    - github: "contributor456"
      contribution: "HTTPS variant testing"
```

Credits to the community members who provided HAR captures, test
results, or parser contributions.

### Sources

```yaml
sources:
  auth_config: "#81, #124"
  chipset: "FCC filing"
  detection_hints: "HAR capture"
  release_date: "Amazon listing"
```

Provenance tracking — documents where each piece of configuration data
came from. Freeform strings referencing GitHub issues, HAR captures,
FCC filings, manufacturer documentation, or contributor reports. This
helps future maintainers understand why the config says what it says
and where to look if something seems wrong.

Common source fields: `auth_config`, `chipset`, `detection_hints`,
`release_date`. Any key is valid — use whatever describes the source.

### ISPs and notes

```yaml
isps:
  - "Comcast"
  - "Spectrum"
notes: |
  HTTPS variant requires login. HTTP variant works without auth.
  See issue #81 for firmware differences.
references:
  issues:
    - 42
    - 81
  prs:
    - 57
```

---

## Validation Rules

### Transport constraints

The transport identifies the protocol. For HNAP, it constrains all other
axes. For HTTP, auth, session, and format are configured independently,
subject to the [auth-session-action consistency](#auth-session-action-consistency)
rules below.

| Transport | Valid auth strategies | Valid session | Valid formats | Valid action types |
|-----------|---------------------|--------------|---------------|-------------------|
| `http` | `none`, `basic`, `form`, `form_nonce`, `url_token`, `form_pbkdf2` | stateless, cookie, CSRF, url_token | `table`, `table_transposed`, `html_fields`, `javascript`, `json`, `xml` | `http` |
| `hnap` | `hnap` | implicit (uid + HNAP_AUTH) | `hnap` | `hnap` |

The format field in parser.yaml determines how the response is decoded.
HTML formats produce `BeautifulSoup`, structured formats produce `dict`.
See ARCHITECTURE.md Constraint Summary for details.

Violations are rejected at both **build time** (Pydantic validation in
Catalog's dev-gate) and **load time** (`load_modem_config()` in Core)
with a clear error message — not at runtime with mysterious parsing
failures.

### Required fields by status

| Field | `verified` / `awaiting_verification` | `in_progress` | `unsupported` |
|-------|:------------------------------------:|:--------------:|:-------------:|
| `manufacturer` | required | required | required |
| `model` | required | required | required |
| `transport` | required | required | required |
| `default_host` | required | required | required |
| `auth` | required | required | — |
| `session` | optional | optional | — |
| `hardware` | required | required | optional |
| `status` | required | required | required |
| `attribution` | required | optional | optional |
| `isps` | required | optional | optional |

### Auth-session-action consistency

- `auth.strategy: none` + `session.cookie_name` → warning (stateless
  auth with session cookie is unusual but not invalid — some modems
  set a cookie even without login)
- `auth.strategy: basic` + `session.max_concurrent: 1` → error (Basic
  Auth is stateless, concurrent session limits don't apply)
- `auth.strategy: hnap` + explicit `session` block → error (HNAP
  session is implicit, cannot be overridden)
- `session.max_concurrent: 1` without `actions.logout` → error
  (single-session modem without logout locks users out of their
  modem's web UI between polls)

---

## Multi-Variant Modems

When a modem model has firmware variants that differ in auth, protocol,
or behavior, each variant gets its own yaml file:

```
modems/arris/sb8200/
├── parser.yaml                 # Shared extraction config
├── parser.py                   # Shared code overrides
├── modem.yaml                  # auth: none (HTTP, default variant)
├── modem-url-token.yaml        # auth: url_token (login_ prefix, ct_ tokens)
├── modem-cookie.yaml           # auth: url_token (no prefix, cookie-only)
└── tests/
    ├── modem.har
    ├── modem.expected.json
    ├── modem-url-token.har
    ├── modem-url-token.expected.json
    ├── modem-cookie.har
    └── modem-cookie.expected.json
```

### Rules

1. **One auth strategy per file.** No `auth.types` with multiple
   strategies — each variant file has one `auth.strategy`.
2. **Variant name in filename.** `modem-{variant}.yaml` where variant
   is a short descriptive name (`noauth`, `url-token`, `basic`).
3. **Shared parser.** All variants in a directory share `parser.yaml`
   and `parser.py`. If variants need different parsers, they belong in
   separate directories.
4. **Same transport.** All variants in a directory share a transport.
   Different transport = different directory.
5. **Per-variant metadata.** Status, attribution, ISPs, and references
   are per-variant. A variant can be `verified` while another is
   `awaiting_verification`.

### Single-variant modems

Most modems: one `modem.yaml` file. No variant suffix needed.

```
modems/motorola/mb7621/
├── parser.yaml
├── modem.yaml
└── tests/
    ├── modem.har
    └── modem.expected.json
```

---

## Capabilities

Capabilities are **not declared in modem.yaml**. They are implicit
from parser.yaml and parser.py — the presence of a mapping IS the
capability declaration.

- Downstream channel mapping in parser.yaml → downstream capability
- `system_uptime` field in parser.yaml → system uptime capability
- `parse_downstream` override in parser.py → downstream capability

No separate capabilities list to maintain. No mapping = no entity.
See [PARSING_SPEC.md](PARSING_SPEC.md#capabilities-are-implicit) for
details.

---

## Complete Examples

### HTTP — no auth (simplest)

```yaml
manufacturer: "{Manufacturer}"
model: "{Model}"
brands:
  - "{BrandName}"
transport: http
default_host: "192.168.100.1"

auth:
  strategy: none

hardware:
  docsis_version: "3.0"

status: verified
sources:
  auth_config: "Community forum"
attribution:
  contributors:
    - github: "{contributor}"
      contribution: "Initial implementation"
isps:
  - "Various"
```

### HTTP — form auth with session

```yaml
manufacturer: "{Manufacturer}"
model: "{Model}"
transport: http
default_host: "192.168.100.1"

auth:
  strategy: form
  action: "/goform/login"
  username_field: "loginUsername"
  password_field: "loginPassword"
  encoding: base64

session:
  cookie_name: "session"
  max_concurrent: 1

actions:
  logout:
    type: http
    method: GET
    endpoint: "/logout.asp"

hardware:
  docsis_version: "3.0"
  chipset: "Broadcom BCM3384"

status: verified
sources:
  auth_config: "HAR capture"
attribution:
  contributors:
    - github: "{contributor}"
      contribution: "Initial implementation"
isps:
  - "Various"
notes: |
  Single-session modem — must logout before new login.
```

### HNAP

```yaml
manufacturer: "{Manufacturer}"
model: "{Model}"
model_aliases:
  - "{AlternativeName}"
brands:
  - "{BrandName}"
transport: hnap
default_host: "192.168.100.1"

auth:
  strategy: hnap
  hmac_algorithm: md5

actions:
  restart:
    type: hnap
    action_name: "SetArrisConfigurationInfo"
    pre_fetch_action: "GetArrisConfigurationInfo"
    params:
      Action: "reboot"
    response_key: "SetArrisConfigurationInfoResponse"
    result_key: "SetArrisConfigurationInfoResult"
    success_value: "OK"

behaviors:
  restart:
    window_seconds: 300

hardware:
  docsis_version: "3.1"
  chipset: "Broadcom BCM3390"

status: verified
sources:
  auth_config: "HAR capture, user testing"
attribution:
  contributors:
    - github: "{contributor}"
      contribution: "HAR capture and testing"
isps:
  - "{ISP}"
```

### HTTP — structured data (JSON API)

```yaml
manufacturer: "{Manufacturer}"
model: "{Model}"
model_aliases:
  - "{AlternativeName}"
transport: http
default_host: "192.168.100.1"

auth:
  strategy: none

hardware:
  docsis_version: "3.1"

status: verified
sources:
  auth_config: "HAR capture"
attribution:
  contributors:
    - github: "{contributor}"
      contribution: "REST API analysis"
isps:
  - "{ISP}"
```

### Unsupported (placeholder)

```yaml
manufacturer: "{Manufacturer}"
model: "{Model}"
transport: http
default_host: "10.0.0.1"

hardware:
  docsis_version: "3.1"

status: unsupported
notes: |
  Awaiting HAR capture from user.
references:
  issues:
    - 123
```
