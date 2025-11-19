# Feature Request: Netgear CM600 Parser

**Status:** 🆕 Awaiting HTML samples
**Priority:** Medium
**Effort:** 4-6 hours
**Target Version:** v3.1.0
**Related Issue:** #3

---

## Summary

Add support for Netgear CM600 cable modem.

## Problem

User reported in Issue #3 that their Netgear CM600 is not supported. The integration cannot detect or parse this modem model.

## Current Status

❌ **No HTML samples provided yet** - Cannot implement parser without them

## What's Needed

### Required from User

1. **HTML Samples** - User needs to provide page source for:
   - Login page (if authentication is required)
   - Connection/status page with downstream/upstream channel data
   - System information page
   - Any other pages with modem metrics

2. **Information Needed:**
   - Does the modem require authentication? (username/password)
   - What is the default IP address? (probably 192.168.100.1)
   - What pages show signal data?

### How to Get HTML Samples

**Request to user:**

```markdown
To add support for your Netgear CM600, please provide HTML samples:

**Steps:**
1. Open your modem's web interface in a browser
2. Navigate to the status/connection page
3. Right-click → "View Page Source"
4. Copy the HTML and save as a .txt or .html file
5. Repeat for all relevant pages (login, status, system info)
6. Attach files to this GitHub issue

**Privacy:** Please redact:
- MAC addresses
- Serial numbers
- IP addresses
- Usernames/passwords

Thank you!
```

## Implementation Plan

Once HTML samples are received:

### Step 1: Create Test Fixtures (30 min)
```
tests/parsers/netgear/fixtures/cm600/
├── README.md
├── login.html (if auth required)
├── connection_status.html
├── system_info.html
└── ...other pages
```

### Step 2: Analyze HTML Structure (1 hour)
- Identify authentication method (basic, form, none)
- Find downstream channel table
- Find upstream channel table
- Find system info fields
- Document URL patterns

### Step 3: Create Parser (2-3 hours)
```python
# custom_components/cable_modem_monitor/parsers/netgear/cm600.py

class NetgearCM600Parser(ModemParser):
    name = "Netgear CM600"
    manufacturer = "Netgear"
    models = ["CM600"]

    # Auth config (TBD based on HTML samples)
    auth_config = NoAuthConfig()  # or BasicAuthConfig() or FormAuthConfig()

    url_patterns = [
        {"path": "/...", "auth_method": "...", "auth_required": ...},
    ]

    @classmethod
    def can_parse(cls, soup, url, html):
        # Detection logic based on HTML
        return "CM600" in html or "Netgear" in soup.title.string

    def login(self, session, base_url, username, password):
        # Use auth_config with AuthFactory
        ...

    def parse(self, soup, session=None, base_url=None):
        # Parse downstream/upstream channels and system info
        ...
```

### Step 4: Write Tests (1 hour)
```python
# tests/parsers/netgear/test_cm600.py

def test_cm600_can_parse():
    # Test detection logic
    ...

def test_cm600_parse_downstream():
    # Test channel parsing
    ...

def test_cm600_parse_upstream():
    ...

def test_cm600_parse_system_info():
    ...
```

### Step 5: Documentation (30 min)
- Add CM600 to supported modems list
- Update README
- Document any quirks or special requirements

## Expected Parser Structure

Based on typical Netgear modems:

```python
# Likely authentication: None or Basic HTTP
auth_config = NoAuthConfig()
# or
auth_config = BasicAuthConfig(strategy=AuthStrategyType.BASIC_HTTP)

# Likely URL patterns
url_patterns = [
    {"path": "/DocsisStatus.htm", "auth_method": "none", "auth_required": False},
    # or
    {"path": "/status.asp", "auth_method": "basic", "auth_required": True},
]

# Detection heuristics
def can_parse(cls, soup, url, html):
    return (
        "CM600" in html or
        "Netgear" in soup.title.string or
        "NETGEAR" in html.upper()
    )

# Parsing likely similar to other modems
# - Find table with "Downstream" header
# - Parse rows for channel data
# - Extract SNR, power, frequency, errors
```

## Benefits

- Supports Netgear CM600 users (Issue #3)
- Expands modem compatibility
- Demonstrates community responsiveness
- Netgear is a popular brand (helps many users)

## Testing Plan

1. **Unit Tests** - Test with fixtures
2. **Integration Test** - Test with user's live modem
3. **Verify** - User confirms it works
4. **Close Issue #3**

## Success Criteria

- [ ] HTML samples received from user
- [ ] Test fixtures created
- [ ] Parser implemented and tested
- [ ] User confirms it works with their modem
- [ ] Issue #3 closed

## Next Steps

1. **Ping user on Issue #3** requesting HTML samples
2. **Wait** for samples
3. **Implement** once received (4-6 hours)
4. **Test** with user
5. **Release** in v3.1.0

---

**Blocked on:** User providing HTML samples

**Related Issues:** #3

**Priority:** Medium - User is waiting, but cannot proceed without samples
