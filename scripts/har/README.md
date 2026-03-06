# scripts/har/ — HAR Processing Tools

Tools for extracting and analyzing modem HAR (HTTP Archive) captures.
Auth extraction is the first stage; additional decomposition scripts will follow.

## Scripts

| Script | Purpose |
|--------|---------|
| `har_auth_extractor.py` | Extract authentication patterns → JSON |
| `har_auth_format.py` | Render extractor JSON as human-readable text or YAML |

## Usage

```bash
# Extract → JSON (machine-readable)
python scripts/har/har_auth_extractor.py path/to/file.har

# Extract + cross-validate against modem.yaml
python scripts/har/har_auth_extractor.py path/to/file.har \
    --modem-yaml modems/arris/s33/modem.yaml

# Pipe into formatter for human-readable text
python scripts/har/har_auth_extractor.py file.har | python scripts/har/har_auth_format.py

# Verbose text (includes page_auth_map detail)
python scripts/har/har_auth_extractor.py file.har | python scripts/har/har_auth_format.py -v

# YAML-like output
python scripts/har/har_auth_extractor.py file.har | python scripts/har/har_auth_format.py --yaml

# Formatter can also read from a file
python scripts/har/har_auth_format.py auth.json
python scripts/har/har_auth_format.py --yaml < auth.json
```

---

## Auth Extractor Output Schema

The extractor outputs a flat JSON object via `dataclasses.asdict(AuthFlow)`.
Nested dataclasses (`SessionSummary`, `FormField`, `GhostCookie`, `ProbeReport`,
`PageAuthSummary`) are serialized inline.

### Top-Level Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `modem_name` | `str \| null` | `null` | Inferred modem model (e.g. `"S33"`, `"SB8200"`) |
| `auth_pattern` | `str` | `"unknown"` | Classified pattern: `basic_http`, `form_plain`, `hnap_session`, `url_token_session`, `credential_csrf`, `unknown` |
| `protocol` | `str` | `"http"` | `"http"` or `"https"`, from first entry URL |
| `interface_type` | `str` | `"unknown"` | `"hnap"`, `"rest"`, `"html"`, `"unknown"` |
| `auth_confidence` | `str` | `"low"` | Evidence quality: `"high"`, `"medium"`, `"low"`, `"insufficient_evidence"` |
| `is_post_auth` | `bool` | `false` | `true` if capture started with an existing session |

### Login / Form Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `login_url` | `str \| null` | `null` | URL of the page containing a password form |
| `form_action` | `str \| null` | `null` | Form `action` attribute or POST target path |
| `form_method` | `str` | `"POST"` | HTTP method on the login form |
| `form_fields` | `list[FormField]` | `[]` | All `<input>` fields from the login form |
| `username_field` | `str \| null` | `null` | Detected username/email field name |
| `password_field` | `str \| null` | `null` | Detected password field name |

#### `FormField` object

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Input `name` attribute |
| `field_type` | `str` | `"text"`, `"password"`, `"hidden"`, `"submit"` |
| `value` | `str \| null` | Pre-filled value (hidden fields, submit buttons) |

### CSRF

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `csrf_field` | `str \| null` | `null` | CSRF token field/header name |
| `csrf_source` | `str \| null` | `null` | Where the token comes from: `"cookie"`, `"hidden_field"`, `"header"`, `"form_field"` |

### Session Management (flat — legacy)

These flat fields predate the `session` summary and are still emitted:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `session_cookie` | `str \| null` | `null` | Server-set session cookie name |
| `session_header` | `str \| null` | `null` | Session header (e.g. `"HNAP_AUTH"`) |
| `credential_cookie` | `str \| null` | `null` | Cookie containing credential material |

### Session Management (structured)

The `session` key is a `SessionSummary` that consolidates the flat fields above
plus ghost cookie data:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `session.mechanism` | `str` | `"unknown"` | `"cookie"`, `"header"`, `"url_token"`, `"stateless"`, `"unknown"` |
| `session.cookies` | `list[str]` | `[]` | Server-set session cookie names |
| `session.js_cookies` | `list[str]` | `[]` | Ghost cookies (JS-set, session/csrf category) |
| `session.headers` | `list[str]` | `[]` | Session-bearing headers |
| `session.csrf` | `str \| null` | `null` | CSRF field name (mirrors `csrf_field`) |
| `session.csrf_source` | `str \| null` | `null` | CSRF source (mirrors `csrf_source`) |

### URL Token Auth (SB8200 pattern)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url_token_prefix` | `str \| null` | `null` | Query prefix: `"login_"` (auth) or `"ct_"` (CSRF) |
| `auth_header` | `str \| null` | `null` | `Authorization` header value if present |

### Debug / Entry Indices

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `login_entry_index` | `int \| null` | `null` | HAR entry index of the login page |
| `auth_entry_index` | `int \| null` | `null` | HAR entry index of the auth POST/request |

### Ghost Cookies

`ghost_cookies` is a list of cookies that appeared in requests but were never
set via `Set-Cookie` by the server (typically set by JavaScript).

#### `GhostCookie` object

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Cookie name |
| `first_seen_entry` | `int` | HAR entry index where cookie first appeared |
| `first_seen_url` | `str` | URL of that entry |
| `category` | `str` | `"session"`, `"csrf"`, `"preference"`, `"artifact"` |

Known classifications (from code):

- **session**: `uid`, `PrivateKey`, `SID`, `credential`, `sysauth`, `sessionToken`
- **csrf**: `XSRF_TOKEN`, `csrfp_token`, `x-csrf-token`
- **artifact**: `Secure` (firmware bug in S33 family)
- **preference**: everything else

### Probe Data (har-capture v0.4.1+)

`probe` is `null` for pre-v0.4.0 captures. When present:

#### `ProbeReport` object

| Field | Type | Description |
|-------|------|-------------|
| `auth_status_code` | `int \| null` | Status code from unauthenticated probe request |
| `www_authenticate` | `str \| null` | `WWW-Authenticate` header value |
| `auth_set_cookies` | `list[str]` | Cookies set by the probe response |
| `auth_error` | `str \| null` | Error string if probe failed |
| `icmp_reachable` | `bool \| null` | Whether the modem responded to ICMP ping |

### Page Auth Map

`page_auth_map` is a `dict[path, PageAuthSummary]` providing per-URL auth evidence.

#### `PageAuthSummary` object

| Field | Type | Description |
|-------|------|-------------|
| `path` | `str` | URL path (e.g. `"/cmconnectionstatus.html"`) |
| `status_codes` | `list[int]` | All HTTP status codes seen for this path |
| `has_401` | `bool` | Whether a 401 or `WWW-Authenticate` was seen |
| `www_authenticate` | `str \| null` | `WWW-Authenticate` header value |
| `request_cookies` | `list[str]` | Cookie names sent in requests to this path |
| `response_set_cookies` | `list[str]` | Cookie names set by responses from this path |
| `has_login_form` | `bool` | Whether the response contained a password field |
| `has_auth_header` | `bool` | Whether requests included an `Authorization` header |
| `response_content_type` | `str \| null` | MIME type (e.g. `"text/html"`, `"application/json"`) |

### Diagnostics

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `issues` | `list[str]` | `[]` | Structural issues (missing login page, no password field) |
| `warnings` | `list[str]` | `[]` | Analysis warnings (post-auth capture detected) |
| `modem_yaml_auth` | `str \| null` | `null` | Auth type declared in modem.yaml (only with `--modem-yaml`) |
| `cross_validation_issues` | `list[str]` | `[]` | Mismatches between HAR evidence and modem.yaml |

---

## Proposed Hierarchy

The current output is a flat bag of ~30 fields plus nested objects. The goal is
to restructure into a four-level hierarchy that mirrors how modem auth actually
works: **interface → auth → session → data**.

### Target structure

```json
{
  "interface": {
    "protocol": "http",
    "type": "html",
    "modem_name": "S33"
  },
  "auth": {
    "pattern": "form_plain",
    "confidence": "high",
    "is_post_auth": false,
    "login_url": "/login.asp",
    "form_action": "/goform/login",
    "form_method": "POST",
    "form_fields": ["..."],
    "username_field": "loginUsername",
    "password_field": "loginPassword",
    "csrf_field": "csrfp_token",
    "csrf_source": "cookie",
    "url_token_prefix": null,
    "auth_header": null
  },
  "session": {
    "mechanism": "cookie",
    "cookies": ["credential"],
    "js_cookies": ["XSRF_TOKEN"],
    "headers": [],
    "csrf": "csrfp_token",
    "csrf_source": "cookie"
  },
  "data": {
    "page_auth_map": {}
  },
  "diagnostics": {
    "issues": [],
    "warnings": [],
    "ghost_cookies": [],
    "probe": null,
    "modem_yaml_auth": null,
    "cross_validation_issues": [],
    "login_entry_index": null,
    "auth_entry_index": null
  }
}
```

### Field mapping: flat → hierarchy

| Flat field | → Hierarchy key | Notes |
|------------|-----------------|-------|
| `modem_name` | `interface.modem_name` | |
| `protocol` | `interface.protocol` | |
| `interface_type` | `interface.type` | Renamed |
| `auth_pattern` | `auth.pattern` | Renamed |
| `auth_confidence` | `auth.confidence` | Renamed |
| `is_post_auth` | `auth.is_post_auth` | Or `diagnostics`? See open questions |
| `login_url` | `auth.login_url` | |
| `form_action` | `auth.form_action` | |
| `form_method` | `auth.form_method` | |
| `form_fields` | `auth.form_fields` | |
| `username_field` | `auth.username_field` | |
| `password_field` | `auth.password_field` | |
| `csrf_field` | `auth.csrf_field` | |
| `csrf_source` | `auth.csrf_source` | |
| `url_token_prefix` | `auth.url_token_prefix` | |
| `auth_header` | `auth.auth_header` | |
| `session_cookie` | *(removed)* | Redundant — use `session.cookies` |
| `session_header` | *(removed)* | Redundant — use `session.headers` |
| `credential_cookie` | *(removed)* | Redundant — use `session.cookies` |
| `session` | `session` | Already structured, promoted to top level |
| `page_auth_map` | `data.page_auth_map` | |
| `ghost_cookies` | `diagnostics.ghost_cookies` | Or `session`? See open questions |
| `probe` | `diagnostics.probe` | |
| `issues` | `diagnostics.issues` | |
| `warnings` | `diagnostics.warnings` | |
| `modem_yaml_auth` | `diagnostics.modem_yaml_auth` | |
| `cross_validation_issues` | `diagnostics.cross_validation_issues` | |
| `login_entry_index` | `diagnostics.login_entry_index` | |
| `auth_entry_index` | `diagnostics.auth_entry_index` | |

### Open Questions

1. **`is_post_auth` placement** — `auth.is_post_auth` or `diagnostics.is_post_auth`?
   It's a quality signal about the capture, not an intrinsic auth property. But
   consumers (like `har_auth_format.py`) display it prominently alongside auth
   pattern and confidence, so `auth` may be more ergonomic.

2. **`ghost_cookies` ownership** — `diagnostics.ghost_cookies` or `session.ghost_cookies`?
   Ghost cookies with `category: "session"` or `"csrf"` are session-relevant
   (and already feed into `session.js_cookies`). But the full list includes
   artifacts and preferences that are purely diagnostic. Could split: session-
   relevant ghosts stay in `session`, the rest go to `diagnostics`.

3. **Redundant flat session fields** — `session_cookie`, `session_header`,
   `credential_cookie` are already consolidated into `session.cookies` and
   `session.headers`. Safe to drop? The formatter already reads the flat fields
   in `_text_auth_details()` and `_yaml_optional_sections()` — those would need
   updating.
