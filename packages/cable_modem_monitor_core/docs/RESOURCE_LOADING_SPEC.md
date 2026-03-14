# Resource Loading Specification

Resource loaders fetch data from the modem and return a keyed dict for the
parser. The loader is the bridge between authentication and parsing — it
uses the authenticated session but owns no auth state, and it builds the
dict the parser consumes but extracts no data.

The fetch list is derived from parser.yaml — the orchestrator collects
`resource` paths (HTML/REST) or `response_key` values (HNAP) at startup.

**Design principles:**
- Loaders are paradigm-specific transports — they know *how* to fetch, not *what* to extract
- The resource dict is the contract between loader and parser
- Loaders signal errors (status codes, timeouts); the orchestrator decides retry policy
- Pages are fetched once even when multiple semantic names share a path

---

## Resource Dict Contract

The resource dict is `dict[str, Any]` — keys identify resources, values are
the fetched content in a paradigm-specific type. Parsers access resources
by key and cast to the expected type.

### HTML Paradigm

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

### REST Paradigm

Keys are URL paths from parser.yaml `resource` fields. Values are parsed JSON.

```python
{
    "/rest/v1/cablemodem/state_": dict,
    "/rest/v1/cablemodem/downstream": dict,
    "/rest/v1/cablemodem/upstream": dict,
}
```

- Same key convention as HTML — path only
- Values are `dict` from `json.loads(response_body)`
- REST and HTML loaders share the same key format; the difference is the
  value type (parsed JSON vs parsed HTML)

### HNAP Paradigm

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

**Action names vary by manufacturer.** Arris S33/S34 uses
`GetCustomer*` prefix. Motorola MB8611 uses `GetMoto*` prefix. The
loader returns whatever actions the modem responds with — parsers
reference the action names via `response_key` in parser.yaml.

---

## Loader Behavior

### Page Fetching (HTML and REST)

For each unique `resource` path from parser.yaml:

1. Build the full URL: `{protocol}://{host}{path}`
2. Attach auth credentials to the request (strategy-specific):
   - **URL token** — append token as query parameter (e.g., `?ct_<token>`)
   - **Cookie-based** — session cookies are on the `requests.Session`
   - **Basic auth** — credentials are on the `requests.Session`
3. Send `GET` request with the modem's configured timeout
4. Parse the response:
   - HTML: `BeautifulSoup(response.text, "html.parser")`
   - REST: `response.json()`
5. Key the result by path (not by semantic name)

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

- **HTML and REST:** Collects all unique `resource` paths from
  parser.yaml sections (downstream, upstream, system_info sources)
- **HNAP:** Derives action names from parser.yaml `response_key`
  values (strip `Response` suffix) and batches them in a single
  `GetMultipleHNAPs` request

See [PARSING_SPEC.md](PARSING_SPEC.md#fetch-list-derivation) for
details on how parser.yaml drives the fetch list.

---

## URL Token Auth

URL token auth modems (e.g., Arris SB8200 with Comcast firmware) require
a session token appended to every data page URL. The token is extracted
from the login response body during authentication.

**Flow:**

1. Auth manager authenticates via form POST
2. Login response body contains the session token
3. Auth manager stores the token and passes it to the loader via config
4. Loader appends the token to each page URL:
   `{protocol}://{host}{path}?{token_prefix}{token}`

The token prefix (e.g., `ct_`) and extraction method are configured in
modem.yaml's auth section. The loader doesn't know how the token was
obtained — it just appends whatever the auth manager provides.

---

## Loader Selection

The paradigm declared in modem.yaml determines which loader is
instantiated:

| `paradigm` | Loader | Value type |
|------------|--------|------------|
| `html` | HTMLLoader | `BeautifulSoup` |
| `rest_api` | RESTLoader | `dict` (JSON) |
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
| Empty response body | Empty parsed result | Parser handles gracefully |
| SSL handshake failure | `SSLError` | Check `legacy_ssl` flag |

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

| Paradigm | HTTP requests per poll | Typical latency |
|----------|----------------------|-----------------|
| HTML | 1 per unique path in parser.yaml (typically 2-4) | 1-5s total (modem-dependent) |
| REST | 1 per unique path in parser.yaml (typically 2-3) | 1-3s total |
| HNAP | 1 batched POST (all actions) | 1-2s |

HNAP is the most efficient — one request regardless of action count.
HTML and REST scale with the number of unique data pages, but most
modems have 2-4 data pages.

Page deduplication keeps the request count at the number of unique paths,
not the number of semantic names. A modem with 5 semantic names pointing
to 2 unique paths makes 2 HTTP requests.
