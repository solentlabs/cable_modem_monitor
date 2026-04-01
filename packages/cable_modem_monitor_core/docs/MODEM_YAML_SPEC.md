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
| [Hardware](#hardware) | DOCSIS version, chipset |
| [Timeout](#timeout) | Per-request override |
| [Health](#health) | Health probe configuration (fragile modems) |
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
  cookie_name: "sessionId"        # auth owns the cookie it produces
  token_prefix: "ct_"             # url_token only
  # ... strategy-specific fields

# Session (lifecycle only — independent from auth)
session:
  # ... session fields

# Actions (optional)
actions:
  restart:
    # ... action config
  logout:
    # ... action config

# Hardware
hardware:
  docsis_version: "3.1"
  chipset: "Broadcom BCM3390"

# Timeout (optional, default 10)
timeout: 15

# Health (optional, defaults are correct for most modems)
health:
  http_probe: false      # disable HTTP probes for fragile modems
  supports_head: false   # modem rejects HTTP HEAD (use GET)
  supports_icmp: true    # hint; auto-detection overrides at setup

# Metadata
status: confirmed
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
|-------|------| :--------: |-------------|
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

**Success detection:** Always succeeds — no login is attempted.

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
  cookie_name: ""
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `challenge_cookie` | bool | `false` | If `true`, retry with server-set cookie on initial 401. Some modems (CM1200 HTTPS) return a challenge cookie that must be included in the retry. |
| `cookie_name` | string | `""` | Session cookie produced by login. Empty = stateless. Auth owns the cookie it produces — see ARCHITECTURE_DECISIONS.md "Session is lifecycle, auth owns the cookie." |

**Success detection:** Always succeeds. Basic auth is per-request
(credentials sent on every request), so there is no login response
to evaluate. If `challenge_cookie` is enabled and the initial request
fails with a network error, that is reported as a failure.

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
  cookie_name: "SessionID"
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
| `cookie_name` | string | `""` | Session cookie produced by login. Auth owns the cookie it produces — see ARCHITECTURE_DECISIONS.md. |
| `hidden_fields` | map | `{}` | Additional form fields to include (e.g., CSRF tokens, static values) |
| `login_page` | string | `""` | Page to fetch before login to extract hidden fields or nonces. If empty, POST directly without pre-fetch. |
| `form_selector` | string | `""` | CSS selector to find the login form on `login_page` (for extracting action URL and hidden fields dynamically) |
| `success.redirect` | string | `""` | Expected redirect URL after successful login |
| `success.indicator` | string | `""` | String to match in response body to confirm success |

**Success detection:** If `success` is provided, checks `redirect`
(path substring match) and/or `indicator` (body substring match).
Both are optional; if both present, both must pass. If `success` is
omitted, any response that is not HTTP 401 is treated as success.

Evidence: modems with HTML login forms. Encoding, field names, and
success indicators vary by manufacturer. Both `goform` and `cgi-bin`
style endpoints are common.

### `form_nonce`

Form POST with a **client-generated nonce** — a random value
created fresh for each login request and sent alongside credentials
as a separate form field.

#### What is a nonce?

A **nonce** ("**n**umber used **once**") is a random value included
in a request to prevent replay attacks. If an attacker intercepts a
login POST, they cannot resubmit it later because the server
expects each request to carry a fresh, unique nonce. The concept
originates from cryptographic protocols and is formalized in
standards including:

- **RFC 7616** (HTTP Digest Authentication) — server-generated
  nonces in `WWW-Authenticate` challenges
- **RFC 6749 / RFC 9207** (OAuth 2.0) — `state` parameter as a
  CSRF/replay nonce
- **OWASP CSRF Prevention** — synchronizer tokens and
  double-submit cookies

Cable modem `form_nonce` auth is a simplified variant: the client
generates a random numeric string (like OAuth 1.0's `oauth_nonce`)
and includes it in the login POST. No server challenge is needed —
the nonce is purely client-originated.

#### Core pattern

Two properties distinguish `form_nonce` from `form`:

1. **Client-generated nonce** — a random value created by JavaScript
   before submission (not extracted from the server or a page).
   Contrast with server-generated tokens like CSRF `webToken` fields,
   which belong to the `form` strategy with `login_page` pre-fetch.
2. **Text-prefix response** — the server returns a plain-text body
   starting with `Url:` (success, followed by redirect path) or
   `Error:` (failure, followed by message). No HTTP redirect, no
   Set-Cookie on the login response itself.

These two properties are the **invariants** of the strategy. The
variable parts (field names, nonce length, credential encoding)
are configurable per modem. When a new modem matches both
invariants, it should use `form_nonce` with its own field names —
not a new strategy.

#### Distinguishing from similar patterns

| Pattern | Nonce source | Response evaluation | Strategy |
|---------|-------------|-------------------|----------|
| Plain form login | None | Redirect or cookie | `form` |
| Form with server token | Server (hidden field in login page) | Redirect or cookie | `form` with `login_page` |
| Form with client nonce | Client (JavaScript random) | Text prefix (`Url:` / `Error:`) | `form_nonce` |
| AJAX with client nonce + base64 | Client (JavaScript random) | Text prefix | `form_nonce` (same endpoint, different encoding) |

```yaml
auth:
  strategy: form_nonce
  action: "/cgi-bin/adv_pwd_cgi"
  username_field: "username"
  password_field: "password"
  nonce_field: "ar_nonce"
  nonce_length: 8
  cookie_name: "credential"
  success_prefix: "Url:"
  error_prefix: "Error:"
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `action` | string | required | Form POST URL |
| `username_field` | string | `"username"` | Form field name for the username credential |
| `password_field` | string | `"password"` | Form field name for the password credential |
| `nonce_field` | string | required | Form field name for the client-generated nonce |
| `nonce_length` | int | `8` | Length of the random nonce string (digits only) |
| `cookie_name` | string | `""` | Session cookie produced by login. Auth owns the cookie it produces — see ARCHITECTURE_DECISIONS.md. |
| `success_prefix` | string | `"Url:"` | Response body prefix indicating successful login |
| `error_prefix` | string | `"Error:"` | Response body prefix indicating failed login |

**Success detection:** Matches the response body text against
`success_prefix` (default `"Url:"`) and `error_prefix` (default
`"Error:"`). If the body starts with `error_prefix`, the login
failed and the text after the prefix is the error message. If it
starts with `success_prefix`, the login succeeded and the text
after the prefix is the redirect path. Both are configurable per
modem.

Evidence: observed in modem firmware where the login page JavaScript
generates a random numeric nonce client-side, serializes credentials
as plain form fields alongside the nonce, and evaluates the response
by text prefix. The CGI endpoint may also accept base64-encoded
credentials via an AJAX code path, but the plain form field format
is the canonical implementation.

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
  cookie_name: "sessionId"
  token_prefix: "ct_"
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `login_page` | string | required | Page URL that accepts the token login |
| `login_prefix` | string | `""` | Prefix before base64 token in login URL. Empty = bare base64. |
| `success_indicator` | string | `""` | Dual-purpose field: auth success check AND response type discriminator. See below. |
| `ajax_login` | bool | `false` | Include `X-Requested-With: XMLHttpRequest` header on login |
| `auth_header_data` | bool | `false` | Include `Authorization: Basic` header on data requests |
| `cookie_name` | string | `""` | Session cookie produced by login. Auth owns the cookie it produces — see ARCHITECTURE_DECISIONS.md. |
| `token_prefix` | string | `""` | URL token prefix for subsequent data page requests (e.g., `ct_`). The token value is extracted by the auth manager from the login response body. |

**Success detection and response type discrimination:**

`success_indicator` serves two roles for `url_token`:

1. **Data page detection:** Response body **contains** `success_indicator`
   → the body is the data page itself (modem served data directly during
   login). Token is `None` — no URL injection needed. The response is
   passed to the loader as an auth response reuse candidate.
2. **Token extraction gate:** Response body **does not contain** indicator
   → the body is treated as a server-issued session token (typically
   20-40 chars alphanumeric). Extracted via `response.text.strip()` →
   `auth_context.url_token`.
3. **Empty body fallback:** Body is empty → fall back to cookie via
   `cookie_name`.
4. **Empty cookie fallback:** Cookie is empty → no token injection
   (loader attempts without).

The collector prefers `auth_context.url_token` (body-derived) over
cookie extraction when both are available. This ordering matters because
on some firmware variants (SB8200, Issue #81) the response body token
differs from the cookie value.

Without the `success_indicator` guard, the auth manager would use an
entire HTML data page as a URL parameter, silently breaking any
url_token variant where the login response returns data directly.

**Pre-login cookie clearing:** Before the login request, the auth
manager deletes any existing session cookie (`cookie_name`) from the
session. This matches the browser's `eraseCookie("sessionId")` call
before `$.ajax` login — without it, the modem rejects re-login
attempts with 401 because it sees an active session.

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
session mechanism (`uid` + `PrivateKey` cookies, `HNAP_AUTH` header), and
protocol are all fixed. Only the HMAC algorithm varies across modems.

**Success detection:** The HNAP login response is a JSON object with
a `LoginResult` field. Accepted values: `"OK"` or `"OK_CHANGED"`
(success). `"FAILED"` means wrong credentials. `"LOCKUP"` or
`"REBOOT"` mean the firmware's anti-brute-force mechanism has
triggered (temporary lockout or forced device restart). These are
protocol-fixed — not configurable per modem.

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
  cookie_name: "PHPSESSID"

session:
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
| `cookie_name` | string | `""` | Session cookie produced by login. Auth owns the cookie it produces — see ARCHITECTURE_DECISIONS.md. |

Session-wide headers and logout are declared in their respective
sections. See [Session](#session) and [Actions](#actions).

**Success detection:** The login response JSON is checked for an
`error` key — if present and truthy, login failed (the `message`
key provides the error detail). HTTP 401 is also treated as failure.
Any other response is treated as success. These checks are
hardcoded — not configurable per modem.

Evidence: modems with JavaScript SPA interfaces that use PBKDF2
key derivation for login. Parameters are typically derived from the
modem's login.js source code in HAR captures.

### `form_sjcl`

SJCL (Stanford JavaScript Crypto Library) AES-CCM encrypted form
auth. Some modem firmwares use the SJCL JavaScript library to
encrypt credentials client-side with AES-CCM before POSTing. The
server response is also encrypted — must decrypt to extract the
CSRF nonce. Key is derived via PBKDF2 from the password and a
per-session salt provided by the server.

Requires the ``cryptography`` package. Install Core with the
``[sjcl]`` extra: ``pip install solentlabs-cable-modem-monitor-core[sjcl]``.

```yaml
auth:
  strategy: form_sjcl
  login_page: "/"
  login_endpoint: "/php/ajaxSet_Password.php"
  session_validation_endpoint: "/php/ajaxSet_Session.php"
  pbkdf2_iterations: 1000
  pbkdf2_key_length: 128
  ccm_tag_length: 16
  encrypt_aad: "loginPassword"
  decrypt_aad: "nonce"
  csrf_header: "csrfNonce"
  cookie_name: "PHPSESSID"

session:
  max_concurrent: 1
  headers:
    X-Requested-With: "XMLHttpRequest"

actions:
  logout:
    type: http
    method: GET
    endpoint: "/php/logout.php"
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `login_page` | string | `"/"` | Page to GET for per-session IV, salt, and session ID (parsed from JS variables `myIv`, `mySalt`, `currentSessionId`) |
| `login_endpoint` | string | required | URL for the encrypted credential POST |
| `session_validation_endpoint` | string | `""` | URL for the post-login session validation POST. If empty, session validation is skipped. |
| `pbkdf2_iterations` | int | required | PBKDF2 iteration count for key derivation |
| `pbkdf2_key_length` | int | required | Derived key length in bits (128 for AES-128) |
| `ccm_tag_length` | int | `16` | AES-CCM authentication tag length in bytes |
| `encrypt_aad` | string | `"loginPassword"` | AAD (Additional Authenticated Data) for encrypting the login payload |
| `decrypt_aad` | string | `"nonce"` | AAD for decrypting the server's nonce response |
| `csrf_header` | string | `""` | Header name for the CSRF nonce extracted from the decrypted login response. If empty, nonce decryption is skipped. |
| `cookie_name` | string | `""` | Session cookie produced by login. Auth owns the cookie it produces — see ARCHITECTURE_DECISIONS.md. |

**Auth flow:**

1. **GET login page** — extract `myIv`, `mySalt`, `currentSessionId`
   from JS variable assignments in the response.
2. **Derive key** — `PBKDF2(password, mySalt, iterations, key_length)`.
3. **Encrypt** — AES-CCM encrypt `{"Password": "<pw>", "Nonce": "<sessionId>"}`
   with the derived key, IV from `myIv`, and AAD from `encrypt_aad`.
4. **POST login** — send `{"EncryptData": "<hex>", "Name": "<user>",
   "AuthData": "<encrypt_aad>"}`. Server responds with
   `{"p_status": "AdminMatch", "encryptData": "<hex>"}`.
5. **Decrypt nonce** — AES-CCM decrypt the response `encryptData`
   with AAD from `decrypt_aad` to extract the CSRF nonce.
6. **POST session validation** — if `session_validation_endpoint` is
   configured, POST with the `csrf_header` to finalize the session.

**Success detection:** The login response JSON `p_status` field must
be `"AdminMatch"` or `"Match"`. Any other value is treated as failure.

Evidence: Arris Touchstone gateway firmwares (e.g., TG3442DE) that
embed the SJCL library in their web interface. Constants are found
in `base_95x.js` or similar JS files in HAR captures.

---

## Session

Session owns post-login lifecycle: concurrency limits and session-wide
HTTP headers. Auth strategies own login mechanics and cookie names —
the cookie is an output of the login flow, so auth owns it. See
ARCHITECTURE_DECISIONS.md "Session is lifecycle, auth owns the cookie."

How to end a session (logout) is declared in `actions.logout` — see
[Actions](#actions). Session declares the *lifecycle*; auth declares
the *credentials and cookies*; actions declare the *operations*.

For HNAP, session is implicit (always `uid` + `PrivateKey` cookies,
`HNAP_AUTH` header) — no session block needed.

```yaml
session:
  max_concurrent: 1
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_concurrent` | int | `0` | Max concurrent sessions. `0` = unlimited. `1` = single-session modem. |
| `headers` | map | `{}` | Static headers added to all requests for this session (e.g., `X-Requested-With: XMLHttpRequest` for SPA-style modems). Dynamic headers (CSRF tokens, HNAP signatures, auth tokens) are managed by auth strategies — each strategy defines its own fields for token acquisition and header injection. |

### Stateless

No session section needed (or `session: {}`). Each request is
independent — the auth manager attaches credentials per-request.
Common with `none` and `basic` auth.

### Cookie-based

Cookie-based modems declare `cookie_name` on the auth strategy (not
in session). The session section is only needed if the modem has
concurrency limits, explicit logout, or session-wide headers. After
successful auth, the modem sets the cookie declared in `auth.cookie_name`.
The session maintains this cookie across requests.

### Single-session modems

Some modems allow only one active session. If a second session is
attempted while one is active, login fails.

```yaml
auth:
  strategy: form
  # ... strategy fields ...
  cookie_name: "session"

session:
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
|-------|------| :--------: |-------------|
| `type` | enum | yes | `http` or `hnap` |
| `method` | string | yes | HTTP method (`GET`, `POST`, etc.). No default — must be explicit. |
| `endpoint` | string | yes | URL path to send the request to |
| `params` | map | no | Form parameters. If present, body is `application/x-www-form-urlencoded`. If absent, no request body. |
| `headers` | map | no | Per-action headers. Merged with session-level `headers` (action wins on conflict). |
| `pre_fetch_url` | string | no | URL to fetch before the action (establish session state or extract dynamic endpoint) |
| `endpoint_pattern` | string | no | Keyword to match within form action attributes on the pre-fetch page. Core wraps this in a form-action regex — not a raw regex. See Architecture Decision below. |

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
|-------|------| :--------: |-------------|
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
    endpoint_pattern: "logout"
    params:
      nowTime: ""
```

**Empty-body POST with CSRF:**

The CSRF token is managed by the `form_pbkdf2` auth strategy
(`csrf_init_endpoint` + `csrf_header` in auth config). The action
config doesn't need CSRF awareness.

### Architecture Decision: endpoint_pattern

`endpoint_pattern` is a **keyword/substring**, not a regex. Core
provides form-action extraction as a built-in strategy — it wraps the
keyword in a `<form ... action="...keyword...">` regex internally.

**Why:** modem.yaml selects from core-provided behaviours and supplies
parameters. This follows the same pattern as auth strategies — the
modem declares *what* to find, core handles *how*. Contributors supply
a simple keyword, not a fragile regex.

**Extraction logic (in `orchestration/actions/http_action.py`):**

1. Fetch `pre_fetch_url`
2. Search for `<form ... action="...keyword...">` (case-insensitive)
3. If found → use the full action attribute value as the endpoint
4. If not found and `endpoint` is set → fallback with ERROR log
5. If not found and no `endpoint` → fail the action

**Logging on extraction failure:**

- ERROR with the keyword, fallback endpoint (if any), and a 500-char
  page content preview for diagnostics.

**Extensibility:** If a future modem needs non-form extraction (e.g.,
JavaScript variable), add an `extraction_mode` field to the schema and
a new core strategy. Don't build until needed.

```yaml
auth:
  strategy: form_pbkdf2
  csrf_init_endpoint: "/api/v1/session/init_page"
  csrf_header: "X-CSRF-TOKEN"
  cookie_name: "PHPSESSID"
  # ... other form_pbkdf2 fields

session:
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

## Hardware

```yaml
hardware:
  docsis_version: "3.1"
  chipset: "Broadcom BCM3390"
```

| Field | Type | Required | Description |
|-------|------| :--------: |-------------|
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

## Health

```yaml
health:
  http_probe: false
  supports_head: false
  supports_icmp: true
```

Health check configuration. Controls how the HealthMonitor probes
this modem.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `http_probe` | bool | `true` | Whether HTTP health probes are enabled |
| `supports_head` | bool | `true` | Whether the modem handles HTTP HEAD correctly |
| `supports_icmp` | bool | `true` | Whether ICMP ping is expected to work |

When `http_probe` is `false`, the HealthMonitor skips HTTP HEAD/GET
probes entirely — only ICMP runs (if supported). Use this for fragile
modems where every HTTP request carries crash risk (e.g., S33v2, #117).

When `supports_head` is `false`, the HealthMonitor uses GET instead
of HEAD for HTTP probes. Some modems return 405 or unexpected
responses to HEAD requests. This is a modem characteristic — set
per-model in modem.yaml.

`supports_icmp` is a network-dependent hint. Auto-detection during
setup overrides this default. User options override both. Useful for
ISP-managed modems known to block ICMP.

**Precedence:** modem.yaml provides defaults → auto-detection
overrides at setup → user options (highest priority).

Most modems omit this section — defaults are correct. Only declare it
when a modem is known to be fragile.

---

## Metadata

Metadata is required for all modems, including `unsupported` entries.
It documents what we know about a modem even before we can monitor it.

### Status

```yaml
status: confirmed
```

| Value | Meaning |
|-------|---------|
| `confirmed` | Full pipeline verified on real hardware (modem.verified.json present) |
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
| `http` | `none`, `basic`, `form`, `form_nonce`, `url_token`, `form_pbkdf2`, `form_sjcl` | stateless, cookie, CSRF, url_token | `table`, `table_transposed`, `html_fields`, `javascript`, `javascript_json`, `json` | `http` |
| `hnap` | `hnap` | implicit (uid + HNAP_AUTH) | `hnap` | `hnap` |

The format field in parser.yaml determines how the response is decoded.
HTML formats produce `BeautifulSoup`, structured formats produce `dict`.
See ARCHITECTURE.md Constraint Summary for details.
(`xml` format is planned but not yet implemented — no XML modems exist.)

Violations are rejected at both **build time** (Pydantic validation in
Catalog's dev-gate) and **load time** (`load_modem_config()` in Core)
with a clear error message — not at runtime with mysterious parsing
failures.

### Required fields by status

| Field | `confirmed` / `awaiting_verification` | `in_progress` | `unsupported` |
|-------| :------------------------------------: | :--------------: | :-------------: |
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

- `auth.strategy: none` + `auth.cookie_name` → N/A (`none` has no
  `cookie_name` field — cookie-tracking requires an auth strategy)
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

```text
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
   are per-variant. A variant can be `confirmed` while another is
   `awaiting_verification`.

### Single-variant modems

Most modems: one `modem.yaml` file. No variant suffix needed.

```text
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

status: confirmed
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

status: confirmed
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

status: confirmed
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

status: confirmed
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
