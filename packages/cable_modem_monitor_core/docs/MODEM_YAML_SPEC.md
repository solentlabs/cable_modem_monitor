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
paradigm: html                    # html | hnap | rest_api
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
| `paradigm` | enum | yes | `html`, `hnap`, or `rest_api` |
| `default_host` | string | yes | Default IP address (e.g., "192.168.100.1") |

`paradigm` is the master constraint. It determines which auth
strategies, session mechanisms, and loader behaviors are valid. See
[Validation Rules](#validation-rules) for the constraint table.

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

Evidence: SB6141, CM820B, SB8200 (Spectrum LA firmware), CM1200 (HTTP),
SuperHub 5.

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

Evidence: TC4400, CM600, CM1200 (HTTPS variant). Note: C3700 and
C7000v2 are classified as `basic` in v3.13 but lack pre-auth HAR
captures to verify. C7000v2 has an XSRF_TOKEN ghost cookie that
contradicts stateless Basic Auth — its actual auth mechanism is
uncertain.

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

Evidence: MB7621 (base64), CGA2121 (plain), XB7 (plain), CM3500B
(plain, cgi-bin), G54 (plain, LuCI).

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

Evidence: SB6190 (firmware 9.1.103+).

### `url_token`

Credentials encoded in the URL query string. The response sets a
session cookie; subsequent requests use a server-issued token in the
query string.

```yaml
auth:
  strategy: url_token
  login_page: "/cmconnectionstatus.html"
  login_prefix: "login_"
  token_prefix: "ct_"
  session_cookie: "sessionId"
  success_indicator: "Downstream Bonded Channels"
  ajax_login: true
  auth_header_data: false
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `login_page` | string | required | Page URL that accepts the token login |
| `login_prefix` | string | `""` | Prefix before base64 token in login URL. Empty = bare base64. |
| `token_prefix` | string | `""` | Prefix before session token in subsequent data requests |
| `session_cookie` | string | required | Cookie name set after successful login |
| `success_indicator` | string | `""` | String to match in login response body |
| `ajax_login` | bool | `false` | Include `X-Requested-With: XMLHttpRequest` header on login |
| `auth_header_data` | bool | `false` | Include `Authorization: Basic` header on data requests |

Evidence: SB8200 HTTPS variants (two firmware builds with different
login_prefix values).

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

HNAP auth is fully constrained by the paradigm. The endpoint (`/HNAP1/`),
session mechanism (`uid` cookie + `HNAP_AUTH` header), and protocol are
all fixed. Only the HMAC algorithm varies across modems.

Evidence: S33 (MD5), S34 (SHA256), MB8611 (MD5), MB8600 (MD5).

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
  csrf_header: "X-CSRF-TOKEN"
  csrf_init_endpoint: "/api/v1/session/init_page"
  session_cookie: "PHPSESSID"
  logout_endpoint: "/api/v1/session/logout"
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `login_endpoint` | string | required | URL for both salt request and login POST |
| `salt_trigger` | string | `"seeksalthash"` | Password value that triggers salt response |
| `pbkdf2_iterations` | int | required | PBKDF2 iteration count |
| `pbkdf2_key_length` | int | required | Derived key length in bits |
| `double_hash` | bool | `true` | Hash twice: first with `salt`, then with `saltwebui` |
| `csrf_header` | string | `"X-CSRF-TOKEN"` | CSRF token header name |
| `csrf_init_endpoint` | string | `""` | Endpoint to fetch initial CSRF token |
| `session_cookie` | string | `"PHPSESSID"` | Cookie name set after login |
| `logout_endpoint` | string | `""` | Logout URL |

Evidence: Technicolor CGA4236, CGA6444VF. Parameters derived from
login.js source code in HAR captures.

---

## Session

Session configuration is independent from auth — the same auth
strategy can use different session mechanisms across modems. For HNAP,
session is implicit (always `uid` cookie + `HNAP_AUTH` header).

```yaml
session:
  cookie_name: "session"
  logout_url: "/goform/logout"
  max_concurrent: 1
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `cookie_name` | string | `""` | Session cookie name. Empty = stateless (no cookie tracking). |
| `logout_url` | string | `""` | URL to end the session. Empty = no logout needed. |
| `max_concurrent` | int | `0` | Max concurrent sessions. `0` = unlimited. `1` = must logout before new login. |
| `csrf_header` | string | `""` | CSRF token header name for subsequent requests |
| `csrf_field` | string | `""` | CSRF token form field name |
| `token_prefix` | string | `""` | URL token prefix for subsequent requests (url_token auth only) |

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

Some modems allow only one active session. If a previous session
exists, login fails until that session is ended.

```yaml
session:
  cookie_name: "session"
  logout_url: "/goform/logout"
  max_concurrent: 1
```

The orchestrator calls the logout URL before each login attempt when
`max_concurrent` is set. See RUNTIME_POLLING_SPEC.md for the session
lifecycle.

Evidence: MB7621, C3700, C7000v2. All require explicit logout before
a new login succeeds.

---

## Actions

Optional section declaring modem actions beyond data reading.
Currently only `restart` is supported.

### HTML form restart

```yaml
actions:
  restart:
    type: form_post
    endpoint: "/goform/MotoSecurity"
    params:
      UserId: ""
      MotoSecurityAction: "1"
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | enum | `form_post` or `hnap` |
| `endpoint` | string | URL to POST to |
| `params` | map | Form parameters to include |
| `pre_fetch_url` | string | Optional URL to fetch before POST (extract dynamic endpoint or CSRF token) |
| `endpoint_pattern` | string | Regex to extract the actual endpoint from pre-fetch response |

### HNAP restart

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

| Field | Type | Description |
|-------|------|-------------|
| `action_name` | string | HNAP SOAP action to invoke |
| `pre_fetch_action` | string | Optional action to call first (extract current config for template vars) |
| `params` | map | SOAP parameters. Values with `${key:default}` are replaced with pre-fetch values. |
| `response_key` | string | Key in the SOAP response to check |
| `result_key` | string | Key within the response to match |
| `success_value` | string | Expected value indicating success |

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
render data pages. Evidence: CM820B (15s, Intel Puma 5), TC4400 (20s),
CM1200 HTTPS (20s).

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

### Paradigm constraints

The paradigm constrains which auth strategies and session mechanisms
are valid:

| Paradigm | Valid auth strategies | Valid session |
|----------|---------------------|--------------|
| `html` | `none`, `basic`, `form`, `form_nonce`, `url_token` | stateless, cookie, CSRF |
| `hnap` | `hnap` | implicit (uid + HNAP_AUTH) |
| `rest_api` | `none`, `form`, `form_pbkdf2` | stateless, cookie + CSRF |

Violations are rejected at config load time with a clear error message
— not at runtime with mysterious parsing failures.

### Required fields by status

| Field | `verified` / `awaiting_verification` | `in_progress` | `unsupported` |
|-------|:------------------------------------:|:--------------:|:-------------:|
| `manufacturer` | required | required | required |
| `model` | required | required | required |
| `paradigm` | required | required | required |
| `default_host` | required | required | required |
| `auth` | required | required | — |
| `session` | optional | optional | — |
| `hardware` | required | required | optional |
| `status` | required | required | required |
| `attribution` | required | optional | optional |
| `isps` | required | optional | optional |

### Auth-session consistency

- `auth.strategy: none` + `session.cookie_name` → warning (stateless
  auth with session cookie is unusual but not invalid — some modems
  set a cookie even without login)
- `auth.strategy: basic` + `session.max_concurrent: 1` → error (Basic
  Auth is stateless, concurrent session limits don't apply)
- `auth.strategy: hnap` + explicit `session` block → error (HNAP
  session is implicit, cannot be overridden)

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
4. **Same paradigm.** All variants in a directory share a paradigm.
   Different paradigm = different directory.
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

### HTML — no auth (simplest)

```yaml
manufacturer: "Arris"
model: "SB6141"
brands:
  - "Surfboard"
paradigm: html
default_host: "192.168.100.1"

auth:
  strategy: none

hardware:
  docsis_version: "3.0"

status: verified
sources:
  auth_config: "HA Community Forum"
attribution:
  contributors:
    - github: "kwschulz"
      contribution: "Initial implementation"
isps:
  - "Various"
```

### HTML — form auth with session

```yaml
manufacturer: "Motorola"
model: "MB7621"
paradigm: html
default_host: "192.168.100.1"


auth:
  strategy: form
  action: "/goform/login"
  username_field: "loginUsername"
  password_field: "loginPassword"
  encoding: base64

session:
  cookie_name: "session"
  logout_url: "/goform/logout"
  max_concurrent: 1

hardware:
  docsis_version: "3.0"
  chipset: "Broadcom BCM3384"

status: verified
sources:
  auth_config: "HAR capture"
attribution:
  contributors:
    - github: "kwschulz"
      contribution: "Initial implementation"
isps:
  - "Various"
notes: |
  Single-session modem — must logout before new login.
```

### HNAP

```yaml
manufacturer: "Arris"
model: "S33"
model_aliases:
  - "CommScope S33"
brands:
  - "Surfboard"
paradigm: hnap
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
  auth_config: "#98, #117"
attribution:
  contributors:
    - github: "contributor"
      contribution: "HAR capture and testing"
isps:
  - "Comcast"
```

### REST API

```yaml
manufacturer: "Virgin Media"
model: "Hub 5"
model_aliases:
  - "Super Hub 5"
paradigm: rest_api
default_host: "192.168.100.1"

auth:
  strategy: none

hardware:
  docsis_version: "3.1"

status: verified
sources:
  auth_config: "#82"
attribution:
  contributors:
    - github: "contributor"
      contribution: "REST API analysis"
isps:
  - "Virgin Media"
```

### Unsupported (placeholder)

```yaml
manufacturer: "Compal"
model: "CH8978E"
paradigm: html
default_host: "10.0.0.1"

hardware:
  docsis_version: "3.1"

status: unsupported
notes: |
  Awaiting HAR capture from user. Issue #79.
references:
  issues:
    - 79
```
