# modem.yaml Schema Specification

**Status:** Current
**Created:** 2026-01-05
**Updated:** 2026-01-18
**Purpose:** Define the declarative configuration format for self-contained modem definitions.

---

## Related Documentation

- **[MODEM_DIRECTORY_SPEC.md](./MODEM_DIRECTORY_SPEC.md)** - Directory structure for modem files
- **[../reference/PARSER_GUIDE.md](../reference/PARSER_GUIDE.md)** - Writing parsers
- **[../reference/ARCHITECTURE.md](../reference/ARCHITECTURE.md)** - System architecture

---

## Goals

1. **Single source of truth** - One file declares everything about a modem
2. **Reduce Python code** - New modems = YAML + minimal parser logic
3. **Enable tooling** - Generate tests, validate configs, auto-discover
4. **Standardize structure** - Every modem follows the same pattern

---

## Schema Overview

```yaml
# =============================================================================
# IDENTITY (Required)
# =============================================================================
manufacturer: string        # e.g., "Motorola", "Arris", "Netgear"
model: string               # e.g., "MB7621", "S33", "CM1200"
paradigm: string            # "html" | "hnap" | "rest_api"

# =============================================================================
# NETWORK
# =============================================================================
# Protocol (HTTP/HTTPS) is auto-detected at setup time - not specified here
default_host: string        # Usually "192.168.100.1"

# =============================================================================
# HARDWARE
# =============================================================================
hardware:
  docsis_version: string    # "3.0" | "3.1"
  chipset: string           # Optional. e.g., "Broadcom BCM3390"
  release_date: string      # Optional. "YYYY" or "YYYY-MM"
  end_of_life: string       # Optional. null = still current

# =============================================================================
# AUTHENTICATION
# =============================================================================
auth:
  strategy: string          # "none" | "basic" | "form" | "hnap" | "url_token" | "rest_api"
  form: { ... }             # Form auth config (if strategy=form)
  hnap: { ... }             # HNAP auth config (if strategy=hnap)
  url_token: { ... }        # URL token config (if strategy=url_token)
  rest_api: { ... }         # REST API config (if strategy=rest_api)
  session: { ... }          # Session management config

# =============================================================================
# PAGES
# =============================================================================
pages:
  public: [string]          # Pages that don't require auth
  protected: [string]       # Pages that require auth
  data:                     # Data source pages by type
    downstream_channels: string
    upstream_channels: string
    system_info: string
  hnap_actions:             # HNAP action names (if paradigm=hnap)
    downstream_channels: string
    upstream_channels: string

# =============================================================================
# PARSER
# =============================================================================
parser:
  class: string             # Python class name
  module: string            # Full module path
  format:
    type: string            # "html" | "json" | "xml"
    table_layout: string    # "standard" | "transposed" | "javascript_embedded"
    delimiters:             # For HNAP field parsing
      field: string
      record: string

# =============================================================================
# DETECTION
# =============================================================================
detection:
  pre_auth: [string]        # Patterns to match on login page (AND logic)
  post_auth: [string]       # Patterns to match on data pages (AND logic)
  page_hint: string         # Path for post_auth matching
  model_aliases: [string]   # Alternative model names

# =============================================================================
# CAPABILITIES
# =============================================================================
capabilities:               # List of Capability enum values
  - scqam_downstream        # SC-QAM downstream channels
  - scqam_upstream          # SC-QAM/ATDMA upstream channels
  - ofdm_downstream         # OFDM downstream (DOCSIS 3.1)
  - ofdma_upstream          # OFDMA upstream (DOCSIS 3.1)
  - system_uptime           # Uptime string
  - last_boot_time          # Boot timestamp
  - hardware_version        # Hardware version
  - software_version        # Firmware version
  - restart                 # Supports remote restart

# =============================================================================
# ACTIONS (Optional)
# =============================================================================
actions:
  restart:
    type: string            # "hnap" | "html_form" | "rest"
    # Type-specific params...

# =============================================================================
# BEHAVIORS (Optional)
# =============================================================================
behaviors:
  restart:                  # Restart-related parsing behaviors
    window_seconds: int     # Filter zero-power channels for N seconds after restart
    zero_power_reported: bool  # Whether modem reports zero during restart

# =============================================================================
# PROVENANCE
# =============================================================================
sources:
  chipset: string           # Source for chipset info
  hardware: string          # Source for hardware info
  auth_config: string       # Source for auth config
  detection_hints: string   # Source for detection patterns

# =============================================================================
# METADATA
# =============================================================================
status_info:
  status: string            # "in_progress" | "awaiting_verification" | "verified" | "unsupported"
  verification_source: string  # Link to issue/PR confirming status

fixtures:
  path: string              # Relative path to fixtures directory
  source: string            # "diagnostics" | "har"
  firmware_tested: string   # Firmware version tested
  last_validated: string    # Date of last validation

attribution:
  contributors:
    - github: string        # GitHub username
      contribution: string  # What they provided
```

---

## Section Details

### Authentication (`auth`)

The `auth` section defines how to authenticate with the modem.

**Strategy: `none`**
```yaml
auth:
  strategy: none
```

**Strategy: `basic`** (HTTP Basic Auth)
```yaml
auth:
  strategy: basic
  session:
    cookie_name: "session"
    logout_endpoint: "/Logout.htm"
    logout_required: true
```

**Strategy: `form`** (HTML Form)
```yaml
auth:
  strategy: form
  form:
    action: "/goform/login"
    method: POST
    username_field: "loginUsername"
    password_field: "loginPassword"
    password_encoding: plain  # or "base64"
    hidden_fields: {}
    success:
      redirect: "/MotoHome.asp"
  session:
    cookie_name: "session"
```

**Strategy: `hnap`** (HNAP/SOAP)
```yaml
auth:
  strategy: hnap
  hnap:
    endpoint: "/HNAP1/"
    namespace: "http://purenetworks.com/HNAP1/"
    hmac_algorithm: md5  # REQUIRED: "md5" or "sha256"
    empty_action_value: ""
    formats:
      - json
    actions:
      login: "Login"
      downstream: "GetCustomerStatusDownstreamChannelInfo"
      upstream: "GetCustomerStatusUpstreamChannelInfo"
      restart: "SetArrisConfigurationInfo"
  session:
    cookie_name: "uid"
```

**Strategy: `url_token`** (URL Token Session)
```yaml
auth:
  strategy: url_token
  url_token:
    login_page: "/cmconnectionstatus.html"
    login_prefix: "login_"
    token_prefix: "ct_"
    session_cookie: "sessionId"
    success_indicator: "Downstream Bonded Channels"
```

**Strategy: `rest_api`** (JSON REST API)
```yaml
auth:
  strategy: rest_api
  rest_api:
    base_path: "/rest/v1/cablemodem"
    endpoints:
      state: "/state_"
      downstream: "/downstream"
      upstream: "/upstream"
```

### Actions (`actions`)

The `actions` section defines modem operations like restart.

**HNAP Restart:**
```yaml
actions:
  restart:
    type: hnap
    # Optional: Pre-fetch current config to preserve settings
    pre_fetch_action: "GetArrisConfigurationInfo"
    pre_fetch_response_key: "GetArrisConfigurationInfoResponse"
    params:
      Action: "reboot"
      # Variable substitution from pre-fetch: ${field:default}
      SetEEEEnable: "${ethSWEthEEE:0}"
      LED_Status: "${LedStatus:1}"
    response_key: "SetArrisConfigurationInfoResponse"
    result_key: "SetArrisConfigurationInfoResult"
    success_value: "OK"
```

**HTML Form Restart:**
```yaml
actions:
  restart:
    type: html_form
    endpoint: "/goform/RouterStatus"
    params:
      RsAction: "2"
```

### Behaviors (`behaviors`)

The `behaviors` section defines **parsing behaviors**, not actions.

```yaml
behaviors:
  restart:
    window_seconds: 300     # Seconds after restart to filter bad data
    zero_power_reported: true  # Modem reports 0 power during restart
```

**When to use behaviors:**
- Only define `behaviors` if the modem needs special parsing logic
- If undefined, the parser uses defaults (no filtering)
- Currently only `restart` behaviors are supported

**How parsers use this:**
```python
# Parser reads from modem.yaml via adapter
behaviors = get_behaviors_for_parser(self.__class__.__name__)
restart_behaviors = behaviors.get("restart") if behaviors else None
if restart_behaviors:
    self._restart_window_seconds = restart_behaviors.get("window_seconds", 0)
```

### Capabilities (`capabilities`)

Declares what data the parser can extract. The integration uses these to create sensor entities.

| Capability | Description | Parser Returns |
|------------|-------------|----------------|
| `scqam_downstream` | SC-QAM downstream channels | `downstream[]` with power, snr, frequency |
| `scqam_upstream` | SC-QAM/ATDMA upstream channels | `upstream[]` with power, frequency |
| `ofdm_downstream` | OFDM downstream (DOCSIS 3.1) | `ofdm_downstream[]` |
| `ofdma_upstream` | OFDMA upstream (DOCSIS 3.1) | `ofdma_upstream[]` |
| `system_uptime` | Human-readable uptime | `system_info.system_uptime` |
| `last_boot_time` | Boot timestamp | `system_info.last_boot_time` |
| `hardware_version` | Hardware version | `system_info.hardware_version` |
| `software_version` | Firmware version | `system_info.software_version` |
| `restart` | Supports remote restart | Parser has restart action |

### Detection (`detection`)

Patterns use AND logic - ALL patterns must match for a modem to be a candidate.

```yaml
detection:
  pre_auth:                 # Match on login page (before auth)
    - "NETGEAR"
    - "/goform/Login"
  post_auth:                # Match on data pages (after auth)
    - "CM2000"
    - "Nighthawk"
  page_hint: "/DocsisStatus.htm"  # Page to fetch for post_auth
  model_aliases:
    - "Nighthawk CM2000"
```

### Status (`status_info`)

| Status | Meaning | Requirements |
|--------|---------|--------------|
| `in_progress` | Actively being developed | `manufacturer`, `model` only |
| `awaiting_verification` | Released, needs user confirmation | Full config + `parser` |
| `verified` | Confirmed working | Full config + `parser` |
| `unsupported` | Locked/incompatible, kept for docs | `manufacturer`, `model` only |

---

## Complete Examples

### MB7621 (Form + Base64 Password)

```yaml
manufacturer: Motorola
model: MB7621
paradigm: html

hardware:
  docsis_version: "3.0"
  chipset: Broadcom BCM3384

default_host: "192.168.100.1"

auth:
  strategy: form
  form:
    action: "/goform/login"
    method: POST
    username_field: loginUsername
    password_field: loginPassword
    password_encoding: base64
    success:
      redirect: "/MotoHome.asp"

pages:
  public:
    - "/"
  protected:
    - "/MotoConnection.asp"
    - "/MotoHome.asp"
  data:
    downstream_channels: "/MotoConnection.asp"
    upstream_channels: "/MotoConnection.asp"
    system_info: "/MotoHome.asp"

parser:
  class: MotorolaMB7621Parser
  module: custom_components.cable_modem_monitor.modems.motorola.mb7621.parser
  format:
    type: html
    table_layout: standard

detection:
  pre_auth:
    - "MB7621"
    - "Motorola"
  post_auth:
    - "MB7621"
    - "Downstream Channel Status"
  page_hint: "/MotoConnection.asp"

capabilities:
  - scqam_downstream
  - scqam_upstream
  - system_uptime
  - hardware_version
  - software_version

behaviors:
  restart:
    window_seconds: 300
    zero_power_reported: true

status_info:
  status: verified
  verification_source: "https://github.com/solentlabs/cable_modem_monitor/issues/XX"

fixtures:
  path: modems/motorola/mb7621/fixtures
  source: diagnostics
  firmware_tested: "8621-19.2.18"
  last_validated: "2026-01-05"

attribution:
  contributors:
    - github: kwschulz
      contribution: "Maintainer"
```

### S33 (HNAP + MD5)

```yaml
manufacturer: Arris/CommScope
model: S33
paradigm: hnap

hardware:
  docsis_version: "3.1"
  chipset: Broadcom BCM3390

default_host: "192.168.100.1"

auth:
  strategy: hnap
  hnap:
    endpoint: "/HNAP1/"
    namespace: "http://purenetworks.com/HNAP1/"
    hmac_algorithm: md5
    empty_action_value: ""
    formats:
      - json
    actions:
      login: "Login"
      downstream: "GetCustomerStatusDownstreamChannelInfo"
      upstream: "GetCustomerStatusUpstreamChannelInfo"
      restart: "SetArrisConfigurationInfo"
  session:
    cookie_name: "uid"

pages:
  public:
    - "/Login.html"
  protected:
    - "/cmconnectionstatus.html"
  data:
    downstream_channels: "/HNAP1/"
    upstream_channels: "/HNAP1/"
    system_info: "/HNAP1/"
  hnap_actions:
    downstream_channels: "GetCustomerStatusDownstreamChannelInfo"
    upstream_channels: "GetCustomerStatusUpstreamChannelInfo"

parser:
  class: ArrisS33HnapParser
  module: custom_components.cable_modem_monitor.modems.arris.s33.parser
  format:
    type: json
    delimiters:
      field: "^"
      record: "|+|"

detection:
  pre_auth:
    - "HNAP"
    - "purenetworks.com/HNAP1"
    - "SURFboard"
  post_auth:
    - "S33"
    - "ARRIS"
    - "CommScope"
  page_hint: "/HNAP1/"
  model_aliases:
    - "CommScope S33"
    - "ARRIS S33"

capabilities:
  - scqam_downstream
  - scqam_upstream
  - ofdm_downstream
  - ofdma_upstream
  - software_version
  - restart

actions:
  restart:
    type: hnap
    pre_fetch_action: "GetArrisConfigurationInfo"
    pre_fetch_response_key: "GetArrisConfigurationInfoResponse"
    params:
      Action: "reboot"
      SetEEEEnable: "${ethSWEthEEE:0}"
      LED_Status: "${LedStatus:1}"
    response_key: "SetArrisConfigurationInfoResponse"
    result_key: "SetArrisConfigurationInfoResult"
    success_value: "OK"

behaviors:
  restart:
    window_seconds: 300
    zero_power_reported: true

status_info:
  status: verified
  verification_source: "https://github.com/solentlabs/cable_modem_monitor/issues/87"

fixtures:
  path: modems/arris/s33/fixtures
  source: diagnostics
  last_validated: "2026-01-05"

attribution:
  contributors:
    - github: kwschulz
      contribution: "Maintainer - HNAP implementation from HAR analysis"
```

### CM1200 (Basic Auth, No Behaviors)

```yaml
manufacturer: Netgear
model: CM1200
paradigm: html

hardware:
  docsis_version: "3.1"

default_host: "192.168.100.1"

auth:
  strategy: basic

pages:
  public: []
  protected:
    - "/DocsisStatus.htm"
  data:
    downstream_channels: "/DocsisStatus.htm"
    upstream_channels: "/DocsisStatus.htm"
    system_info: "/DocsisStatus.htm"

parser:
  class: NetgearCM1200Parser
  module: custom_components.cable_modem_monitor.modems.netgear.cm1200.parser
  format:
    type: html
    table_layout: javascript_embedded

detection:
  pre_auth:
    - "NETGEAR"
    - "CM1200"
  post_auth:
    - "CM1200"
    - "InitDsTableTagValue"
  page_hint: "/DocsisStatus.htm"

capabilities:
  - scqam_downstream
  - scqam_upstream
  - ofdm_downstream
  - ofdma_upstream
  - system_uptime
  - last_boot_time

# No behaviors section - modem doesn't need special parsing logic

status_info:
  status: verified
  verification_source: "https://github.com/solentlabs/cable_modem_monitor/issues/63"
```

---

## Validation

All modem.yaml files are validated by the Pydantic schema in `modem_config/schema.py`.

**Run validation:**
```bash
pytest tests/modem_config/test_modem_yaml_validation.py -v
```

**Key validation rules:**
1. `manufacturer` and `model` are required
2. `auth.strategy` must match one of the AuthStrategy enum values
3. HNAP modems MUST specify `hmac_algorithm` (no default)
4. `verified` and `awaiting_verification` status require `parser.class` and `parser.module`
5. `capabilities` must be valid Capability enum values

---

## Adding a New Modem

1. Create directory: `modems/{manufacturer}/{model}/`
2. Create `modem.yaml` following this spec
3. Add `parser.py` implementing the parser class
4. Add `fixtures/` with HTML captures
5. Run validation: `pytest tests/modem_config/test_modem_yaml_validation.py`
6. Tests auto-discover the new modem

**Minimal modem.yaml for development:**
```yaml
manufacturer: Acme
model: CM9000
paradigm: html

auth:
  strategy: none

status_info:
  status: in_progress
  verification_source: "https://github.com/solentlabs/cable_modem_monitor/issues/XXX"

capabilities: []
```
