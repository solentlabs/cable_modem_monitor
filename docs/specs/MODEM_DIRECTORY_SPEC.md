# Modem Directory Structure Specification

**Status:** Approved
**Created:** 2026-01-06
**Purpose:** Define the canonical directory structure for modem-specific files.

---

## Overview

Each supported modem has a directory under `modems/{manufacturer}/{model}/` containing all modem-specific configuration, fixtures, and captures.

**Design Principles:**
1. **Single source of truth** - All modem-specific files in one location
2. **Self-contained** - Everything needed to test a modem is in its directory
3. **Optional captures** - modem.yaml is required; fixtures and HAR are optional
4. **Sanitized by default** - Captures are sanitized at capture time, safe to commit

---

## Directory Structure

```
modems/
└── {manufacturer}/
    └── {model}/
        ├── modem.yaml           # REQUIRED: Configuration and auth hints
        ├── fixtures/            # OPTIONAL: Extracted HTML/JSON responses
        │   ├── {page_name}.html
        │   ├── {page_name}.asp
        │   └── metadata.yaml    # Fixture metadata (firmware, capture date)
        └── har/                 # OPTIONAL: Sanitized HAR captures
            ├── modem.har        # Primary capture
            └── modem-{variant}.har  # Variant captures (if applicable)
```

### Examples

**Motorola MB7621 (Form Auth)**
```
modems/motorola/mb7621/
├── modem.yaml
├── fixtures/
│   ├── index.html              # Login page
│   ├── MotoConnection.asp      # Channel data
│   ├── MotoHome.asp            # System info
│   └── metadata.yaml
└── har/
    └── modem.har
```

**Arris SB8200 (Multiple Auth Variants)**
```
modems/arris/sb8200/
├── modem.yaml
├── fixtures/
│   └── cmconnectionstatus.html
└── har/
    ├── modem.har               # Default (url_token auth, HTTPS)
    └── modem-noauth.har        # No-auth variant (HTTP, older firmware)
```

**Arris S33 (HNAP)**
```
modems/arris/s33/
├── modem.yaml
├── fixtures/
│   ├── Login.html
│   └── hnap_response.json      # HNAP JSON response
└── har/
    └── modem.har
```

---

## File Specifications

### modem.yaml (Required)

The modem configuration file. See [MODEM_YAML_SPEC.md](./MODEM_YAML_SPEC.md) for full schema.

```yaml
manufacturer: Motorola
model: MB7621

auth:
  strategy: form_base64
  form:
    login_url: "/"
    action: "/goform/login"
    username_field: loginUsername
    password_field: loginPassword

parser:
  class: MotorolaMB7621Parser
  data_pages:
    - path: "/MotoConnection.asp"
      type: html
```

### fixtures/ Directory (Optional)

Contains extracted HTML/JSON responses from HAR captures. Used for:
- Parser testing without network access
- Validating parser logic against real modem output
- Reducing HAR file size via `$fixture` references

**File Naming:**
- Use actual endpoint names from the modem: `MotoStatus.asp`, not `status_page.html`
- Preserves traceability to real modem URLs

**metadata.yaml:**
```yaml
firmware_version: "8601.0.6.1.6-SCM00"
captured_date: "2026-01-04"
contributor: "@username"
issue: 123  # GitHub issue number
notes: "Captured via diagnostics export"
```

### har/ Directory (Optional)

Contains sanitized HAR (HTTP Archive) captures. Used for:
- Full auth flow testing
- Request/response sequence validation
- Debugging auth issues

**File Naming Convention:**

| File | Description |
|------|-------------|
| `modem.har` | Primary/default capture |
| `modem-{variant}.har` | Variant captures |

**Variant Naming Examples:**
- `modem-basic-auth.har` - HTTP Basic Auth variant
- `modem-noauth.har` - No authentication required
- `modem-https.har` - HTTPS-specific behavior
- `modem-comcast.har` - ISP-specific variant

**HAR Format:**

HAR files use `$fixture` references to avoid duplicating HTML content:

```json
{
  "log": {
    "entries": [
      {
        "request": {
          "method": "GET",
          "url": "http://192.168.100.1/MotoConnection.asp"
        },
        "response": {
          "status": 200,
          "content": {
            "$fixture": "MotoConnection.asp",
            "mimeType": "text/html"
          }
        }
      }
    ]
  }
}
```

**Why `$fixture` references?**
- HTML responses are 80%+ of HAR file size
- Extracting to fixtures avoids duplication
- Fixtures are human-readable and editable
- HAR retains auth flow structure and headers
- Git can diff both files effectively

---

## Capture Workflow

### 1. Capture

Use the capture script which sanitizes automatically:

```bash
python scripts/capture_modem.py --ip 192.168.100.1
```

Output:
- `captures/modem_20260104_123456.har` (raw, local only)
- `captures/modem_20260104_123456.sanitized.har` (safe to share)

### 2. Sanitization

Sanitization happens at capture time via `utils/har_sanitizer.py`:

**Automatically redacted:**
- Sensitive headers: `Authorization`, `Cookie`, `Set-Cookie`
- Sensitive fields: `password`, `passwd`, `pwd`, `secret`, `token`, `key`, `auth`, `credential`
- Form POST data matching sensitive patterns
- JSON fields matching sensitive patterns
- HTML content via `sanitize_html()`

**Modem-specific fields** (from modem.yaml):
- `auth.form.username_field` value
- `auth.form.password_field` value
- `auth.hnap.cookie_name` value
- `auth.url_token.session_cookie` value

### 3. Extract Fixtures

Extract HTML responses from HAR to fixtures:

```bash
python scripts/extract_fixtures.py captures/modem.sanitized.har --modem mb7621
```

This:
1. Extracts HTML/JSON responses to `modems/{mfr}/{model}/fixtures/`
2. Replaces HAR content with `$fixture` references
3. Creates `metadata.yaml` with capture info

### 4. Validate

Before committing, validate no secrets leaked:

```bash
python scripts/validate_har_secrets.py modems/motorola/mb7621/har/modem.har
```

### 5. Commit

```bash
git add modems/motorola/mb7621/
git commit -m "feat(mb7621): add HAR capture and fixtures"
```

---

## HAR Parser Resolution

The HAR parser resolves `$fixture` references automatically:

```python
# tests/integration/har_replay/har_parser.py

class HarParser:
    def __init__(self, har_path: Path):
        self.har_path = har_path
        self.modem_path = har_path.parent.parent  # modems/{mfr}/{model}/

    def _resolve_content(self, content: dict) -> str:
        """Resolve $fixture reference to actual content."""
        if "$fixture" in content:
            fixture_path = self.modem_path / "fixtures" / content["$fixture"]
            return fixture_path.read_text()
        return content.get("text", "")
```

---

## Testing Integration

### Parser Validation Tests

Tests run parsers against fixture HTML:

```python
@requires_fixtures("mb7621")
def test_mb7621_parse_channels(modem_fixtures):
    """Parse channel data from fixture HTML."""
    html = modem_fixtures.get("MotoConnection.asp")
    soup = BeautifulSoup(html, "html.parser")

    parser = MotorolaMB7621Parser()
    data = parser.parse(soup)

    assert len(data["downstream"]) == 24
    assert len(data["upstream"]) == 8
```

### HAR Replay Tests

Tests validate auth flows against HAR captures:

```python
@requires_har("mb7621")
def test_mb7621_auth_flow(har_replay):
    """Test auth flow matches HAR capture."""
    with har_replay("mb7621") as mock:
        session = requests.Session()

        # Auth handler executes against mocked responses
        handler = FormAuthHandler(session, "http://192.168.100.1")
        result = handler.login("admin", "password")

        assert result.success
        assert mock.called("/goform/login")
```

---

## CI Integration

### Validation on PR

```yaml
# .github/workflows/ci.yml
- name: Validate HAR files
  run: |
    for har in modems/*/*/har/*.har; do
      python scripts/validate_har_secrets.py "$har"
    done
```

### Test Discovery

Tests auto-discover modems with fixtures:

```python
def discover_modems_with_fixtures():
    """Find all modems that have fixtures for testing."""
    modems_root = Path("modems")
    for modem_yaml in modems_root.glob("*/*/modem.yaml"):
        modem_dir = modem_yaml.parent
        if (modem_dir / "fixtures").exists():
            yield modem_dir
```

---

## Migration from Current Structure

### Current State
```
modems/{mfr}/{model}/           # modem.yaml + fixtures (partial)
custom_components/.../parsers/  # Parser code
tests/parsers/                  # Parser tests
RAW_DATA/                       # Unsanitized HARs (gitignored)
```

### Target State
```
modems/{mfr}/{model}/
├── modem.yaml                  # Config (exists)
├── fixtures/                   # HTML (exists, may need metadata.yaml)
└── har/                        # NEW: sanitized HARs
    └── modem.har

custom_components/.../parsers/  # Parser code (unchanged for now)
tests/parsers/                  # Parser tests (unchanged for now)
RAW_DATA/                       # Raw captures (remains gitignored)
```

### Migration Steps

1. **Add har/ directories** to existing modems with captures
2. **Sanitize and extract** from RAW_DATA/ HARs
3. **Add metadata.yaml** to existing fixtures/
4. **Update HAR_FILES** in test conftest.py to use new paths

---

## Open Questions (Resolved)

| Question | Resolution |
|----------|------------|
| HAR file naming? | `modem.har` (parallels modem.yaml) |
| Compression? | Uncompressed (readable, git-diffable) |
| Variant naming? | `modem-{variant}.har` (e.g., `modem-basic-auth.har`) |
| Fixture references? | `$fixture` field in HAR content |
| Sanitization timing? | At capture time, not after |
| Multiple auth configs? | Variant HAR files, single modem.yaml with detection rules |

---

## Appendix: Complete Example

### modems/motorola/mb7621/modem.yaml

```yaml
manufacturer: Motorola
model: MB7621
aliases: ["MB7621-10"]

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
    - path: "/MotoConnection.asp"
      type: html
    - path: "/MotoHome.asp"
      type: html

detection:
  title_contains: "Motorola Cable Modem"
  body_contains: ["MB7621"]
```

### modems/motorola/mb7621/fixtures/metadata.yaml

```yaml
firmware_version: "8601.0.6.1.6-SCM00"
captured_date: "2026-01-04"
contributor: "@kwschulz"
issue: 81
capture_method: "scripts/capture_modem.py"
pages:
  - name: "index.html"
    url: "/"
    description: "Login page"
  - name: "MotoConnection.asp"
    url: "/MotoConnection.asp"
    description: "Downstream/upstream channel data"
  - name: "MotoHome.asp"
    url: "/MotoHome.asp"
    description: "System info, uptime, firmware version"
```

### modems/motorola/mb7621/har/modem.har

```json
{
  "log": {
    "version": "1.2",
    "_solentlabs": {
      "tool": "cable_modem_monitor/capture_modem.py",
      "version": "3.12.0",
      "sanitized": true,
      "fixture_refs": true
    },
    "entries": [
      {
        "request": {
          "method": "GET",
          "url": "http://192.168.100.1/",
          "headers": []
        },
        "response": {
          "status": 200,
          "headers": [
            {"name": "Content-Type", "value": "text/html"}
          ],
          "content": {
            "$fixture": "index.html",
            "mimeType": "text/html"
          }
        }
      },
      {
        "request": {
          "method": "POST",
          "url": "http://192.168.100.1/goform/login",
          "headers": [
            {"name": "Content-Type", "value": "application/x-www-form-urlencoded"}
          ],
          "postData": {
            "mimeType": "application/x-www-form-urlencoded",
            "params": [
              {"name": "loginUsername", "value": "[REDACTED]"},
              {"name": "loginPassword", "value": "[REDACTED]"}
            ]
          }
        },
        "response": {
          "status": 302,
          "headers": [
            {"name": "Location", "value": "/MotoHome.asp"},
            {"name": "Set-Cookie", "value": "session=[REDACTED]; path=/"}
          ],
          "content": {}
        }
      },
      {
        "request": {
          "method": "GET",
          "url": "http://192.168.100.1/MotoHome.asp",
          "headers": [
            {"name": "Cookie", "value": "session=[REDACTED]"}
          ]
        },
        "response": {
          "status": 200,
          "content": {
            "$fixture": "MotoHome.asp",
            "mimeType": "text/html"
          }
        }
      },
      {
        "request": {
          "method": "GET",
          "url": "http://192.168.100.1/MotoConnection.asp",
          "headers": [
            {"name": "Cookie", "value": "session=[REDACTED]"}
          ]
        },
        "response": {
          "status": 200,
          "content": {
            "$fixture": "MotoConnection.asp",
            "mimeType": "text/html"
          }
        }
      }
    ]
  }
}
```
