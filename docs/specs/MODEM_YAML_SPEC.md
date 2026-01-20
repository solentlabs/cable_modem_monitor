# modem.yaml Schema Specification

**Status:** Draft
**Created:** 2026-01-05
**Updated:** 2026-01-06
**Purpose:** Define the declarative configuration format for self-contained modem definitions.

---

## Related Documentation

- **[MODEM_DIRECTORY_SPEC.md](./MODEM_DIRECTORY_SPEC.md)** - Directory structure for modem files
- **[../plans/har-parser-validation.md](../plans/har-parser-validation.md)** - HAR testing plan

---

## Goals

1. **Single source of truth** - One file declares everything about a modem
2. **Reduce Python code** - New modems = YAML + minimal parser logic
3. **Enable tooling** - Generate tests, validate configs, auto-discover
4. **Standardize structure** - Every modem follows the same pattern

---

## Design Philosophy

**modem.yaml provides hints, not strict rules.**

The auth handler and parser use modem.yaml to prioritize strategies, but retain intelligent fallback behavior. This handles firmware variations and ISP customizations gracefully:

1. **Discovery phase** - Single request identifies the modem
2. **Config selection** - Detection rules match ONE modem.yaml
3. **Targeted execution** - Use hints to prioritize, fallback if needed
4. **Rich diagnostics** - Log enough context to debug failures and request captures

90% of modem behavior is declarative. 10% is edge-case handling with fallbacks.

---

## Directory Structure

> **Full specification:** See [MODEM_DIRECTORY_SPEC.md](./MODEM_DIRECTORY_SPEC.md)

```
modems/
└── {manufacturer}/
    └── {model}/
        ├── modem.yaml        # Config + hints (this spec) - REQUIRED
        ├── fixtures/         # Extracted HTML responses - OPTIONAL
        │   ├── {page}.html        # Actual page names from modem
        │   ├── {page}.asp
        │   └── metadata.yaml      # Firmware version, contributor, capture date
        └── har/              # Sanitized HAR captures - OPTIONAL
            ├── modem.har          # Primary capture (uses $fixture refs)
            └── modem-{variant}.har  # Variant captures (e.g., modem-basic-auth.har)
```

**Key principles:**
- **File naming:** Use actual endpoint names (`MotoStatus.asp`, not `status_page.html`)
- **HAR format:** Uses `$fixture` references to avoid duplicating HTML content
- **Variants:** Different auth configs use `modem-{variant}.har` naming
- **Sanitization:** Happens at capture time, not after

---

## Schema Definition

```yaml
# =============================================================================
# MODEM IDENTITY
# =============================================================================

manufacturer: string        # Required. e.g., "Motorola", "Arris", "Netgear"
model: string               # Required. e.g., "MB7621", "S33", "CM1200"
aliases: [string]           # Optional. Other model names this covers

# =============================================================================
# DATA PARADIGM (for Discovery Intelligence)
# =============================================================================

paradigm: string            # Required. How the modem presents data:
                            #   - "html" (default) - Standard web pages with tables
                            #   - "hnap" - HNAP/SOAP protocol
                            #   - "rest_api" - JSON REST API
                            # Used by Discovery Intelligence to filter candidates
                            # See: docs/reference/ARCHITECTURE.md#discovery-intelligence

# =============================================================================
# HARDWARE INFO
# =============================================================================

hardware:
  docsis_version: string    # "3.0" | "3.1" | "4.0"
  release_year: int         # e.g., 2020
  end_of_life: date | null  # null = still current
  chipset: string           # Optional. e.g., "Broadcom BCM3390"

# =============================================================================
# NETWORK PROTOCOL
# =============================================================================

protocol: string            # Required. "HTTP" | "HTTPS" | "HNAP" | "REST_API"
default_host: string        # Default IP. Usually "192.168.100.1"
default_port: int           # Usually 80 or 443

ssl:
  required: bool            # true if HTTPS-only
  legacy_ciphers: bool      # true if needs legacy SSL support
  verify: bool              # false for self-signed certs (most modems)

# =============================================================================
# AUTHENTICATION
# =============================================================================

auth:
  strategy: string          # Required. One of:
                            #   - no_auth
                            #   - basic_http
                            #   - form_plain
                            #   - form_base64
                            #   - form_plain_and_base64
                            #   - redirect_form
                            #   - hnap_session
                            #   - url_token_session
                            #   - credential_csrf

  # ----- Form-based auth (form_plain, form_base64, redirect_form) -----
  form:
    login_url: string       # Page with login form. e.g., "/" or "/login.html"
    action: string          # Form POST target. e.g., "/goform/login"
    method: string          # "POST" (default) or "GET"
    username_field: string  # e.g., "loginUsername"
    password_field: string  # e.g., "loginPassword"
    extra_fields: object    # Optional static fields. e.g., {remember: "1"}

    encoding: string        # "plain" | "base64" | "url_then_base64"

    success:
      indicator: string     # URL fragment or min response size
      redirect: string      # Expected redirect URL on success

  # ----- HTTP Basic auth -----
  basic:
    realm: string           # Optional. Expected realm string

  # ----- HNAP/SOAP auth (S33, S34, MB8611) -----
  hnap:
    endpoint: string        # "/HNAP1/"
    namespace: string       # "http://purenetworks.com/HNAP1/"
    use_json: bool          # true for JSON HNAP, false for XML SOAP
    hmac_algorithm: string  # "md5" (S33, MB8611) | "sha256" (S34)
    empty_action_value: string  # "" for S33/S34/MB8611
    cookie_name: string     # Session cookie name

  # ----- URL Token auth (SB8200 HTTPS variant) -----
  url_token:
    login_page: string      # e.g., "/login.html"
    login_prefix: string    # e.g., "login_"
    token_prefix: string    # e.g., "ct_"
    session_cookie: string  # e.g., "credential"
    credential_header: string  # Header name for auth

  # ----- Credential CSRF (CM3500B) -----
  credential_csrf:
    login_url: string
    csrf_field: string
    credential_field: string

# =============================================================================
# PARSER CONFIGURATION
# =============================================================================

parser:
  class: string             # Python class name. e.g., "MotorolaMB7621Parser"
  module: string            # Optional. Full module path if not in standard location

  data_pages:               # Pages to scrape for channel data
    - path: string          # e.g., "/MotoStatus.asp"
      type: string          # "html" | "json" | "hnap"

  hnap_actions:             # For HNAP modems
    - name: string          # e.g., "GetCustomerStatusDownstreamChannelInfo"
      value: string         # Usually "" or {}

# =============================================================================
# DETECTION
# =============================================================================

detection:
  # How to identify this modem from an HTTP response
  title_contains: string    # HTML <title> substring
  body_contains: [string]   # Strings that must appear in response
  headers:                  # Response headers to match
    - name: string
      contains: string
  hnap_model_field: string  # For HNAP: field containing model name

# =============================================================================
# ISP COMPATIBILITY
# =============================================================================

isps:
  verified: [string]        # Known working. e.g., ["Comcast", "Cox"]
  reported: [string]        # User-reported but unverified
  blocked: [string]         # ISP-locked, won't work

# =============================================================================
# FIXTURE & ATTRIBUTION
# =============================================================================

fixtures:
  firmware_tested: string   # Firmware version fixtures were captured from
  captured_from_issue: int  # GitHub issue number
  last_validated: date      # When fixtures were last confirmed working

attribution:
  contributors:
    - github: string        # GitHub username
      issue: int            # Issue number
      contribution: string  # What they provided
```

---

## Examples

### MB7621 (Form Base64)

```yaml
manufacturer: Motorola
model: MB7621
paradigm: html           # Standard web scraping

hardware:
  docsis_version: "3.0"
  release_year: 2017

protocol: HTTP
default_host: "192.168.100.1"

auth:
  strategy: form_base64
  form:
    login_url: "/"
    action: "/goform/login"
    username_field: loginUsername
    password_field: loginPassword
    encoding: base64
    success:
      redirect: "/MotoHome.asp"

parser:
  class: MotorolaMB7621Parser
  data_pages:
    - path: "/MotoStatus.asp"
      type: html

detection:
  title_contains: "Motorola Cable Modem"
```

### S33 (HNAP Session - MD5)

```yaml
manufacturer: Arris
model: S33
paradigm: hnap           # HNAP/SOAP protocol

hardware:
  docsis_version: "3.1"
  release_year: 2021

protocol: HTTP           # Note: HNAP uses HTTP transport, paradigm describes data format
default_host: "192.168.100.1"

auth:
  strategy: hnap_session
  hnap:
    endpoint: "/HNAP1/"
    namespace: "http://purenetworks.com/HNAP1/"
    use_json: true
    hmac_algorithm: md5
    empty_action_value: ""
    cookie_name: "uid"

parser:
  class: ArrisS33HnapParser
  hnap_actions:
    - name: GetCustomerStatusDownstreamChannelInfo
      value: ""
    - name: GetCustomerStatusUpstreamChannelInfo
      value: ""

detection:
  hnap_model_field: "ModelName"
```

### S34 (HNAP Session - SHA256)

```yaml
manufacturer: Arris
model: S34

hardware:
  docsis_version: "3.1"
  release_year: 2024

protocol: HNAP
default_host: "192.168.100.1"

ssl:
  required: true
  verify: false

auth:
  strategy: hnap_session
  hnap:
    endpoint: "/HNAP1/"
    namespace: "http://purenetworks.com/HNAP1/"
    use_json: true
    hmac_algorithm: sha256  # Key difference from S33
    empty_action_value: ""
    cookie_name: "uid"

parser:
  class: ArrisS34HnapParser
  hnap_actions:
    - name: GetArrisDeviceStatus
      value: ""
    - name: GetCustomerStatusDownstreamChannelInfo
      value: ""
    - name: GetCustomerStatusUpstreamChannelInfo
      value: ""

detection:
  body_contains: ["S34"]
  hnap_model_field: "StatusSoftwareModelName"
```

### SB8200 (URL Token Session)

```yaml
manufacturer: Arris
model: SB8200

hardware:
  docsis_version: "3.1"
  release_year: 2017

protocol: HTTPS
default_host: "192.168.100.1"

ssl:
  required: true
  legacy_ciphers: true
  verify: false

auth:
  strategy: url_token_session
  url_token:
    login_page: "/login.html"
    login_prefix: "login_"
    token_prefix: "ct_"
    session_cookie: "credential"

parser:
  class: ArrisSB8200Parser
  data_pages:
    - path: "/cmconnectionstatus.html"
      type: html
```

### CM1200 (No Auth)

```yaml
manufacturer: Netgear
model: CM1200

hardware:
  docsis_version: "3.1"
  release_year: 2019

protocol: HTTP
default_host: "192.168.100.1"

auth:
  strategy: no_auth

parser:
  class: NetgearCM1200Parser
  data_pages:
    - path: "/DocsisStatus.htm"
      type: html

detection:
  title_contains: "NETGEAR"
  body_contains: ["CM1200"]
```

---

## Testing Architecture

### End-to-End Integration Tests

Tests run the **complete workflow** against a mock server powered by fixtures. No unit tests needed—the fixtures ARE the test specification.

```
┌─────────────────────────────────────────────────────────┐
│              Mock Modem Server                          │
│  (Powered by fixtures/auth_flow.json + HTML files)      │
│                                                         │
│  GET /              → fixtures/Login.html               │
│  POST /goform/login → 302 + Set-Cookie                  │
│  GET /MotoHome.asp  → fixtures/MotoHome.asp             │
│  GET /MotoStatus.asp→ fixtures/MotoStatus.asp           │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │ HTTP
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Our Actual Code (unchanged)                │
│                                                         │
│  1. GET / → Auth discovery detects strategy             │
│  2. POST login → Auth handler executes strategy         │
│  3. GET pages → Parser registry matches modem           │
│  4. Parse HTML → Extract channels + system_info         │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Assertions                                 │
│                                                         │
│  ✓ Auth strategy detected == modem.yaml.auth.strategy   │
│  ✓ Parser selected == modem.yaml.parser.class           │
│  ✓ Downstream channels parsed > 0                       │
│  ✓ System info has expected fields                      │
└─────────────────────────────────────────────────────────┘
```

### Test Implementation

```python
# tests/integration/test_modem_workflows.py

@pytest.mark.parametrize("modem_path", discover_all_modems())
def test_end_to_end(modem_path):
    """Run entire stack against mock server."""

    with MockModemServer.from_fixtures(modem_path) as server:
        # Same code path as real Home Assistant usage
        result = await async_setup_entry(
            hass=mock_hass,
            config_entry=ConfigEntry(
                host=server.host,
                username="admin",
                password="test"
            )
        )

        assert result is True

        # Verify entities were created with real data
        state = hass.states.get("sensor.cable_modem_downstream_1_power")
        assert state is not None
```

### Fixture Sources

Fixtures can be extracted from:

1. **HAR captures** - Browser network recording during login/navigation
2. **Diagnostics exports** - Home Assistant diagnostics contain raw HTML responses
3. **Manual captures** - curl/wget with appropriate auth headers

### auth_flow.json Format

Defines the request/response sequence for the mock server:

```json
{
  "auth_pattern": "form_base64",
  "form_config": {
    "login_url": "/",
    "form_action": "/goform/login",
    "username_field": "loginUsername",
    "password_field": "loginPassword",
    "success_redirect": "/MotoHome.asp"
  },
  "exchanges": [
    {
      "request": {"method": "GET", "path": "/"},
      "response": {"status": 200, "file": "Login.html"}
    },
    {
      "request": {"method": "POST", "path": "/goform/login"},
      "response": {"status": 302, "headers": {"Location": "/MotoHome.asp"}}
    },
    {
      "request": {"method": "GET", "path": "/MotoHome.asp"},
      "response": {"status": 200, "file": "MotoHome.asp"}
    },
    {
      "request": {"method": "GET", "path": "/MotoStatus.asp"},
      "response": {"status": 200, "file": "MotoStatus.asp"}
    }
  ]
}
```

### Adding a New Modem

1. Capture fixtures (HAR or diagnostics export)
2. Create `modems/{manufacturer}/{model}/` directory
3. Add `modem.yaml` with detection rules and auth config
4. Add `fixtures/` with HTML pages and `auth_flow.json`
5. Tests auto-run—no test code to write

**The fixture IS the test specification.**

---

## Validation Rules

1. `manufacturer` and `model` are required
2. `auth.strategy` must be one of the defined strategies
3. Strategy-specific fields are required when that strategy is used
4. `parser.class` must exist in the codebase
5. `data_pages` paths should match what the parser expects

---

## Migration Path

1. **Phase 1:** Create modem.yaml for existing parsers (read-only documentation)
2. **Phase 2:** Auth handler reads from modem.yaml instead of parser hints
3. **Phase 3:** Parser registry uses modem.yaml for detection
4. **Phase 4:** Test runner auto-generates tests from modem.yaml + captures/

---

## Open Questions

1. **Should parser.py be optional?** Some modems with standard HTML tables might be fully declarative. Field mappings in modem.yaml could eliminate custom parsing for simple cases.

2. **Firmware variations:** Same model, different firmware = different auth. Options:
   - Separate modem.yaml files: `sb8200.yaml`, `sb8200_no_auth.yaml`
   - Detection rules specific enough to distinguish variants
   - Fallback behavior in auth handler (try primary, log if fallback used)

3. **HACS installation:** The `modems/` directory needs to be included in the HACS package. May need manifest.json updates.

4. **Field mapping:** How do we normalize different field names to a standard schema? e.g., "Power Level" vs "power" vs "PowerLevel" → `power`

---

## Resolved Decisions

- **Directory location:** `modems/{manufacturer}/{model}/` at repo root
- **Test approach:** End-to-end integration tests with mock server, no unit tests needed
- **Fixture naming:** Use actual page names from modem (`MotoStatus.asp` not `status_page.html`)
- **HAR files:** Development artifacts only, not committed. Extract to fixtures/ for tests.
- **modem.yaml as hints:** Not strict rules—auth handler retains fallback behavior
