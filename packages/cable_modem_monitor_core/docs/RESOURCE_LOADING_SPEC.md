# Resource Loading Specification

Resource loaders fetch data from the modem and return a keyed dict for the
parser. The loader is the bridge between authentication and parsing — it
uses the authenticated session but owns no auth state, and it builds the
dict the parser consumes but extracts no data.

The fetch list is derived from parser.yaml — the orchestrator collects
`resource` paths (HTML/REST) or `response_key` values (HNAP) at startup.

**Design principles:**
- Loaders are transport-specific — they know *how* to fetch, not *what* to extract
- The resource dict is the contract between loader and parser
- Loaders signal errors (status codes, timeouts); the orchestrator decides retry policy
- Pages are fetched once even when multiple semantic names share a path

---

## Resource Dict Contract

The resource dict is `dict[str, Any]` — keys identify resources, values are
the fetched content in a format-dependent type. Parsers access resources
by key and cast to the expected type.

### HTTP Transport — HTML Formats

Keys are URL paths from parser.yaml `resource` fields. Values are parsed HTML.

```python
{
    "/MotoConnection.asp": BeautifulSoup,
    "/MotoHome.asp": BeautifulSoup,
    "/MotoSwInfo.asp": BeautifulSoup,
}
```

- Keys are the path component only (no host, no query string).
  This is load-bearing: auth strategies that modify the URL (e.g.,
  `url_token` appending `?ct_<token>`) produce the same resource
  dict keys as unauthenticated variants. This enables multi-variant
  modems to share a single parser.yaml.
- Values are `BeautifulSoup` objects parsed from the response body
- One entry per unique path (see deduplication below)

### HTTP Transport — Structured Formats

Keys are URL paths from parser.yaml `resource` fields. Values are parsed
structured data (dict).

```python
{
    "/rest/v1/cablemodem/state_": dict,
    "/rest/v1/cablemodem/downstream": dict,
    "/rest/v1/cablemodem/upstream": dict,
}
```

- Same key convention as HTML formats — path only
- Values are `dict` from format-specific decoding (`json.loads()`, `xmltodict.parse()`, or `b64decode()` + `json.loads()`)
- The value type is always `dict` regardless of the wire format

### HNAP Transport

HNAP uses a single batched SOAP request, not per-page fetches. The resource
dict reflects this different transport.

```python
{
    "hnap_response": {
        "GetCustomerStatusDownstreamChannelInfoResponse": {...},
        "GetCustomerStatusUpstreamChannelInfoResponse": {...},
        "GetCustomerStatusStartupSequenceResponse": {...},
        ...
    },
}
```

- `hnap_response` — the full `GetMultipleHNAPsResponse` dict containing
  all action responses

**Action names vary by manufacturer** (e.g., `GetCustomer*`, `GetMoto*`). The
loader returns whatever actions the modem responds with — parsers
reference the action names via `response_key` in parser.yaml.

---

## Loader Behavior

### Page Fetching (HTTP Transport)

For each unique `resource` path from parser.yaml:

1. Build the full URL: `{protocol}://{host}{path}`
2. Attach auth credentials to the request (strategy-specific):
   - **URL token** — append token as query parameter (e.g., `?ct_<token>`)
   - **Cookie-based** — session cookies are on the `requests.Session`
   - **Basic auth** — credentials are on the `requests.Session`
3. Send `GET` request with the modem's configured timeout
4. If `encoding: base64` is set on the section, decode first:
   `b64decode(response.text)` → raw text
5. Parse the response (format-dependent):
   - HTML formats: `BeautifulSoup(text, "html.parser")`
   - `json`: `json.loads(text)`
   - `xml`: `xmltodict.parse(text)`
6. Key the result by path (not by semantic name)

**SSL handling:** If the config entry has `legacy_ssl: true` (detected
during validation), the loader configures the session for `SECLEVEL=0`
to support older modem firmware with weak TLS ciphers.

### HNAP Batching

HNAP modems expose all data through a single `/HNAP1/` endpoint via
SOAP-style POST requests. Instead of fetching pages individually, the
loader batches all actions into one `GetMultipleHNAPs` request.

1. Derive action names from parser.yaml `response_key` values (strip `Response` suffix)
2. Call `hnap_builder.call_multiple(session, base_url, actions)`
   - The builder handles HMAC signing (MD5 or SHA256 per modem config)
   - Single HTTP POST to `/HNAP1/` with `SOAPAction: GetMultipleHNAPs`
3. Parse the JSON response
4. Extract `GetMultipleHNAPsResponse` as the `hnap_response` dict
5. Individual action responses become keys within `hnap_response`

### Path Deduplication

Multiple sections in parser.yaml can reference the same URL path.
For example, both `downstream` and `upstream` sections may declare
`resource: "/cmSignalData.htm"`. The orchestrator collects unique paths
before passing the fetch list to the loader, so the page is fetched
once. The parser receives one dict entry for `"/cmSignalData.htm"` and
extracts both downstream and upstream data from the same parsed page.

### Auth Response Reuse

If the auth step's response already returned a data page (e.g., a
post-login redirect lands on a page in the fetch list), the loader
reuses that response instead of re-fetching. This avoids an extra HTTP
round-trip and is common with form auth modems that redirect to a
dashboard page after login.

---

## Timeout

Each modem declares a `timeout` in modem.yaml (seconds). Core defines a
default (10 seconds) applied when the field is absent. Slow modems
override this — some cable modems take 12-20 seconds to render data pages.

The timeout applies per-request (each page fetch or HNAP call), not to
the entire loader operation.

---

## Fetch List Derivation

The orchestrator builds the fetch list from parser.yaml at startup:

- **HTTP:** Collects all unique `resource` paths from parser.yaml
  sections (downstream, upstream, system_info sources)
- **HNAP:** Derives action names from parser.yaml `response_key`
  values (strip `Response` suffix) and batches them in a single
  `GetMultipleHNAPs` request

See [PARSING_SPEC.md](PARSING_SPEC.md#fetch-list-derivation) for
details on how parser.yaml drives the fetch list.

---

## URL Token Auth

URL token auth modems (e.g., modems with ISP-specific firmware) require
a session token appended to every data page URL. The token is extracted
from the login response body during authentication.

**Flow:**

1. Auth manager authenticates via form POST
2. Login response body contains the session token
3. Auth manager stores the token and passes it to the loader via config
4. Loader appends the token to each page URL:
   `{protocol}://{host}{path}?{token_prefix}{token}`

The token prefix (e.g., `ct_`) is configured in modem.yaml's session
section (`session.token_prefix`). The token value itself is extracted
by the auth manager during login. The loader doesn't know how the
token was obtained — it just appends whatever the auth manager provides.

---

## Loader Selection

The transport declared in modem.yaml determines which loader is
instantiated:

| `transport` | Loader | Value type |
|-------------|--------|------------|
| `http` | HTTPLoader | Format-dependent: `BeautifulSoup` (HTML formats) or `dict` (structured formats) |
| `hnap` | HNAPLoader | `dict` (JSON) |

Selection happens once at startup (or after config change) and persists
for the integration's lifetime. The loader is instantiated by the
orchestrator's factory method.

---

## Error Signals

Loaders raise exceptions or return error indicators. They never retry,
back off, or decide what to do about failures — that's orchestrator
policy (see Signal and Policy Separation in `ARCHITECTURE.md`).

| Condition | Signal | Orchestrator response |
|-----------|--------|-----------------------|
| Connection refused | `ConnectionError` | Status `unreachable` |
| Request timeout | `Timeout` | Status `unreachable` |
| HTTP 401/403 | Status code in response | Stale session → retry auth |
| HTTP 5xx | Status code in response | Status `unreachable` |
| Login page on data URL | `LOAD_AUTH` | Clear session, increment auth streak |
| Empty response body | Empty parsed result | Parser handles gracefully |
| SSL handshake failure | `SSLError` | Check `legacy_ssl` flag |

---

## Login Page Detection

Some modems silently serve a login page at a data URL when the session
expires — HTTP 200, but the body is a login form instead of data.
Without detection, this reaches the parser and causes PARSE_ERROR,
which misclassifies the root cause (auth, not parser) and prevents
self-healing (no session clear, no auth streak increment).

### Runtime behavior

The Resource Loader checks each HTTP 200 HTML response for login page
indicators before adding it to the resource dict. Detection is
automatic for form-based auth strategies (`form`, `form_nonce`,
`form_pbkdf2`, `form_sjcl`, `url_token`). Not applicable to `none`,
`basic`, or `hnap`.

**Detection invariant:** Data pages from parser.yaml (status,
connection, channel info) do not contain `<input type="password">`.
Login pages always do. If the response contains a password input
field, it is a login page served at a data URL.

When detected, the loader signals `LOAD_AUTH` instead of returning
the response in the resource dict. The orchestrator clears the
session and increments the auth streak — the next poll starts with
a fresh login.

**Scope:** Only applies to HTTP transport, HTML format responses.
Structured formats (JSON, XML) and HNAP transport are not checked.

### Failure modes

| Failure | Impact | Likelihood | Mitigation |
|---------|--------|------------|------------|
| False positive (data page has `<input type="password">`) | Auth failure loop — session cleared every poll | Very low — parser.yaml only references status/data pages, not settings/admin pages | Detected during HAR regression; override via `session.login_page` (future, if needed) |
| False negative (login page without `<input type="password">`) | Falls through to PARSE_ERROR — wrong classification but not destructive | Low — JS-only SPA login forms | Detected during MCP onboarding (see below) |

If a false positive occurs in the field, the escape hatch is a
per-modem `session.login_page` override in modem.yaml with an
explicit indicator. This is not spec'd yet — it would be an additive
schema change if the need arises.

### MCP onboarding validation

During HAR analysis, the MCP pipeline should flag potential detection
issues:

1. **Login page without password input** — If the HAR shows a login
   page that has no `<input type="password">` in the initial HTML
   (e.g., JS-rendered SPA login), flag it: "Login page detection may
   not work for this modem — password field is dynamically rendered."

2. **Data page with password input** — If any data page response in
   the HAR contains `<input type="password">`, flag it: "Data page
   {path} contains a password field — login page detection will
   produce false positives."

Both are HARD STOP flags during onboarding — they require human
review before the modem can ship.

---

## Interaction with Other Components

```
Auth Manager ──► Resource Loader ──► Parser
   │                  │                 │
   │ provides:        │ provides:       │ receives:
   │ - session        │ - resource dict │ - resource dict
   │ - url token      │                 │
   │ - cookies        │ fetches:        │ returns:
   │                  │ - fetch list    │ - ModemData
   │                  │                 │
```

- **Auth Manager → Loader:** The authenticated `requests.Session` (with
  cookies, auth headers) and any URL tokens. The loader uses the session
  as-is — it never modifies auth state.
- **Loader → Parser:** The resource dict. The parser receives pre-fetched
  content and extracts data. No session, no HTTP client, no auth
  awareness.
- **Orchestrator → Loader:** The orchestrator creates the loader, passes
  it the session and modem config, calls `fetch()`, and receives the
  resource dict. On loader failure, the orchestrator decides retry policy.

---

## Performance Characteristics

| Transport | HTTP requests per poll | Typical latency |
|-----------|----------------------|-----------------|
| HTTP | 1 per unique path in parser.yaml (typically 2-4) | 1-5s total (modem-dependent) |
| HNAP | 1 batched POST (all actions) | 1-2s |

HNAP is the most efficient — one request regardless of action count.
HTTP scales with the number of unique data pages, but most modems
have 2-4 data pages.

### Per-Resource Timing

The loader captures wall-clock time and response size for each HTTP
request, returned alongside the resource dict as a list of
`ResourceFetch` objects (see `ORCHESTRATION_SPEC.md` § Data Models):

```python
resource_fetches: list[ResourceFetch]
# e.g., [ResourceFetch("/status.html", 800.0, 12480),
#         ResourceFetch("/info.html", 1200.0, 8192)]
# HNAP: [ResourceFetch("GetMultipleHNAPs", 1100.0, 24576)]
```

Units are milliseconds for `duration_ms` and bytes for `size_bytes`.
The orchestrator stores these on `OrchestratorMetrics.resource_fetches`
from the last successful collection. Consumers convert to display
units as needed.

Each fetch is logged at DEBUG with its elapsed time:

```
DEBUG "Resource loaded: /status.html (800ms, 12.2KB)"
DEBUG "Resource loaded: /info.html (1200ms, 8.0KB)"
```

This data is diagnostic — useful for identifying slow resources,
tracking latency trends, and troubleshooting timeout issues.

Page deduplication keeps the request count at the number of unique paths,
not the number of semantic names. A modem with 5 semantic names pointing
to 2 unique paths makes 2 HTTP requests.
