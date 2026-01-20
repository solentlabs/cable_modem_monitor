# Guide: Adding a New Modem Parser

This guide provides step-by-step instructions for adding support for a new cable modem model, based on the patterns established in this project.

## Prerequisites

- Python 3.9+
- Access to the modem's web interface (or HTML captures)
- Knowledge of BeautifulSoup and HTML parsing

**Note:** As of v3.12.0, parsers no longer handle authentication. Auth is auto-detected
by the `AuthDiscovery` system before parser detection runs.

## Overview

Adding a new parser involves:
1. Creating the parser module
2. Implementing required methods
3. Adding test fixtures
4. Writing unit tests
5. Documenting the changes

**Note:** Parser registry updates are **no longer required**! The discovery system automatically finds and registers new parsers.

## Step 1: Create Parser Module

### 1.1 Choose Directory Structure

Parsers are organized by manufacturer in the `modems/` directory (source of truth):

```
modems/
├── arris/
│   ├── sb8200/
│   │   ├── modem.yaml      # Modem configuration
│   │   ├── parser.py       # Parser implementation
│   │   ├── fixtures/       # Test fixtures
│   │   └── tests/          # Unit tests
│   └── s33/
│       └── ...
├── motorola/
│   └── mb8611/
│       └── ...
└── [your_manufacturer]/
    └── [model]/
        ├── modem.yaml
        ├── parser.py
        ├── fixtures/
        └── tests/
```

**Note:** Run `make sync` to copy modem.yaml and parser.py to `custom_components/modems/` for deployment.

### 1.2 Create Parser File

**File:** `modems/[manufacturer]/[model]/parser.py`

```python
"""Parser for [Manufacturer] [Model] cable modem.

Brief description of the modem and its capabilities.

Firmware tested: V1.0.0

Key pages:
- /: Main page
- /status.html: Channel status page

Note: Authentication is auto-detected by AuthDiscovery (v3.12.0+).
No auth_config or login() method needed unless non-standard form fields.

Related: Issue #[number] (if applicable)
"""

from __future__ import annotations

import logging
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)


class [Manufacturer][Model]Parser(ModemParser):
    """Parser for [Manufacturer] [Model] cable modem."""

    # Identity fields - used for detection and display
    name = "[Manufacturer] [Model]"
    manufacturer = "[Manufacturer]"
    models = ["[MODEL]"]  # List of model numbers this parser supports

    # Capabilities - what this parser can extract (implementation detail)
    capabilities = {
        ModemCapability.DOWNSTREAM_CHANNELS,
        ModemCapability.UPSTREAM_CHANNELS,
    }

    # NOTE: As of v3.12.0, the following are configured in modem.yaml, NOT here:
    # - url_patterns (pages.public, pages.protected)
    # - auth_form_hints (auth.form)
    # - hnap_hints (auth.hnap)
    # - js_auth_hints (auth.url_token)
    # See: modems/{manufacturer}/{model}/modem.yaml

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Parse all data from the modem.

        Args:
            soup: BeautifulSoup object of the main page
            session: Optional requests session for multi-page parsing
            base_url: Optional base URL for fetching additional pages

        Returns:
            Dictionary with downstream, upstream, and system_info keys
        """
        return {
            "downstream": self.parse_downstream(soup),
            "upstream": self.parse_upstream(soup),
            "system_info": self.parse_system_info(soup),
        }

    # NOTE: can_parse() is DEPRECATED - do NOT implement it!
    # Detection is now handled by YAML hints in modem.yaml (v3.12+).
    #
    # In your modem.yaml, define:
    #
    #   auth:
    #     login_markers:           # Phase 1: Pre-auth detection (login page)
    #       - "[MANUFACTURER]"     # Brand name
    #       - "[MODEL]"            # Model string visible pre-auth
    #
    #   detection:
    #     model_strings:           # Phase 2: Post-auth detection (data pages)
    #       - "[MODEL]-VARIANT"    # Model variants visible after login
    #
    # The HintMatcher will use these patterns to auto-detect your modem.

    def parse_downstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse downstream channel data.

        Returns:
            List of channel dictionaries with the following keys:
            - channel_id: Channel identifier (string)
            - frequency: Frequency in Hz (int)
            - power: Power level in dBmV (float)
            - snr: Signal-to-noise ratio in dB (float)
            - modulation: Modulation type (string, e.g., "QAM256", "OFDM PLC")
            - channel_type: Channel technology - "qam" or "ofdm" (REQUIRED for DOCSIS 3.1)
            - corrected: Corrected error count (int)
            - uncorrected: Uncorrected error count (int)

        Note on channel_type vs modulation:
            - channel_type: The DOCSIS transport technology (qam/ofdm for downstream)
            - modulation: The encoding scheme (QAM256, QAM4096, etc.)
            An OFDM channel uses QAM4096 modulation internally. The channel_type
            is used for entity naming (sensor.cable_modem_ds_ofdm_ch_1_power).
        """
        channels = []

        # Implement downstream parsing logic
        # Example: Find table and extract rows
        table = soup.find("table", {"id": "downstream_table"})
        if not table:
            _LOGGER.warning("Downstream table not found")
            return channels

        rows = table.find_all("tr")[1:]  # Skip header row

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 7:
                continue

            try:
                channel = {
                    "channel_id": cells[0].text.strip(),
                    "frequency": int(cells[1].text.strip()),
                    "power": float(cells[2].text.strip()),
                    "snr": float(cells[3].text.strip()),
                    "modulation": cells[4].text.strip(),
                    "corrected": int(cells[5].text.strip()),
                    "uncorrected": int(cells[6].text.strip()),
                }
                channels.append(channel)
            except (ValueError, IndexError) as e:
                _LOGGER.warning("Error parsing downstream channel: %s", e)
                continue

        _LOGGER.info("Parsed %d downstream channels", len(channels))
        return channels

    def parse_upstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse upstream channel data.

        Returns:
            List of channel dictionaries with the following keys:
            - channel_id: Channel identifier (string)
            - frequency: Frequency in Hz (int)
            - power: Power level in dBmV (float)
            - modulation: Modulation type (string, e.g., "64QAM", "ATDMA")
            - channel_type: Channel technology - "atdma" or "ofdma" (REQUIRED for DOCSIS 3.1)
            - symbol_rate: Symbol rate in Ksym/sec (int)
        """
        channels = []

        # Implement upstream parsing logic
        # Similar to downstream but with different fields

        return channels

    def parse_system_info(self, soup: BeautifulSoup) -> dict:
        """Parse system information.

        Returns:
            Dictionary with system information:
            - model: Modem model (string)
            - hardware_version: Hardware version (string)
            - software_version: Software/firmware version (string)
            - uptime: Uptime in seconds (int, optional)
            - mac_address: MAC address (string, optional)
        """
        info = {}

        # Implement system info parsing
        # Extract model, firmware version, uptime, etc.

        return info
```

## Step 2: Authentication (Simplified in v3.12+)

**Parsers no longer handle authentication.** The `AuthDiscovery` system automatically
detects and handles auth before parser detection runs.

### What Parsers DON'T Need

- No `auth_config` attribute
- No `login()` method
- No auth strategy selection
- No auth hints on the parser class (these go in modem.yaml)

### Auth Configuration in modem.yaml

Auth hints are now configured in `modems/{manufacturer}/{model}/modem.yaml`:

#### Form Field Hints

If your modem's login form uses non-standard field names:

```yaml
# In modem.yaml
auth:
  strategy: form_plain
  form:
    login_url: "/"
    action: "/goform/login"
    username_field: webUserName  # Non-standard field name
    password_field: webPassKey   # Non-standard field name
```

#### HNAP Hints (S33, MB8611)

For HNAP/SOAP modems:

```yaml
# In modem.yaml
auth:
  strategy: hnap_session
  hnap:
    endpoint: "/HNAP1/"
    namespace: "http://purenetworks.com/HNAP1/"
    empty_action_value: ""  # All known HNAP modems use ""
```

#### URL Token Hints (SB8200)

For modems using JavaScript-based URL token authentication:

```yaml
# In modem.yaml
auth:
  strategy: url_token_session
  url_token:
    login_page: "/cmconnectionstatus.html"
    login_prefix: "login_"
    token_prefix: "ct_"
    session_cookie: "credential"
```

### How Auth Detection Works

1. `AuthDiscovery` fetches the modem page anonymously
2. Inspects the response (200 + data, 401, form, redirect, etc.)
3. Auto-detects the appropriate strategy
4. Reads auth hints from modem.yaml via adapter
5. Stores strategy in config entry for polling

For details, see `core/auth/README.md`.

## Step 3: Add Test Fixtures

### 3.1 Capture Modem HTML

Use the provided tool to capture HTML from your modem:

```bash
python tools/capture_modem_html.py --url http://192.168.100.1 --output tests/parsers/[manufacturer]/fixtures/[model]/
```

Or manually save HTML pages:
1. Open modem web interface in browser
2. Right-click → Save Page As → Complete HTML
3. Save to `tests/parsers/[manufacturer]/fixtures/[model]/`

### 3.2 Organize Fixtures

```
tests/parsers/[manufacturer]/fixtures/[model]/
├── index.html           # Main page
├── status.html          # Channel status page
├── logs.html            # Event logs (optional)
└── README.md            # Document fixture source and details
```

**README.md example:**
```markdown
# [Manufacturer] [Model] Test Fixtures

**Source:** Real [Model] modem
**Firmware:** V1.0.0
**ISP:** Comcast
**Date Captured:** 2025-11-14

## Files

- `index.html`: Main page (/)
- `status.html`: Channel status (/status.html)

## Notes

- Sensitive information (MAC addresses, serial numbers) has been redacted
- All channels are operational in this capture
```

## Step 4: Write Unit Tests

**File:** `tests/parsers/[manufacturer]/test_[model].py`

```python
"""Tests for [Manufacturer] [Model] parser."""

import os
import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.parsers.[manufacturer].[model] import [ParserClass]


@pytest.fixture
def fixture_path():
    """Return path to test fixtures."""
    return os.path.join(
        os.path.dirname(__file__),
        "fixtures",
        "[model]",
    )


@pytest.fixture
def sample_html(fixture_path):
    """Load sample HTML from status page."""
    with open(os.path.join(fixture_path, "status.html"), "r") as f:
        return f.read()


@pytest.fixture
def soup(sample_html):
    """Create BeautifulSoup object from sample HTML."""
    return BeautifulSoup(sample_html, "html.parser")


def test_can_parse(soup, sample_html):
    """Test modem detection."""
    assert [ParserClass].can_parse(soup, "http://192.168.100.1/", sample_html)


def test_can_parse_negative():
    """Test detection rejects non-matching HTML."""
    html = "<html><title>Different Modem</title></html>"
    soup = BeautifulSoup(html, "html.parser")
    assert not [ParserClass].can_parse(soup, "http://192.168.100.1/", html)


def test_parse_downstream(soup):
    """Test downstream channel parsing."""
    parser = [ParserClass]()
    channels = parser.parse_downstream(soup)

    # Verify we got channels
    assert len(channels) > 0, "Expected at least one downstream channel"

    # Verify channel structure
    channel = channels[0]
    assert "channel_id" in channel
    assert "frequency" in channel
    assert "power" in channel
    assert "snr" in channel
    assert "modulation" in channel
    assert "corrected" in channel
    assert "uncorrected" in channel

    # Verify data types
    assert isinstance(channel["channel_id"], str)
    assert isinstance(channel["frequency"], int)
    assert isinstance(channel["power"], float)
    assert isinstance(channel["snr"], float)
    assert isinstance(channel["modulation"], str)
    assert isinstance(channel["corrected"], int)
    assert isinstance(channel["uncorrected"], int)

    # Verify reasonable values (adjust based on your modem)
    assert channel["frequency"] > 0
    assert -20 <= channel["power"] <= 20  # Typical range
    assert 0 <= channel["snr"] <= 50      # Typical range


def test_parse_upstream(soup):
    """Test upstream channel parsing."""
    parser = [ParserClass]()
    channels = parser.parse_upstream(soup)

    assert len(channels) > 0, "Expected at least one upstream channel"

    channel = channels[0]
    assert "channel_id" in channel
    assert "frequency" in channel
    assert "power" in channel
    assert "modulation" in channel

    # Verify data types
    assert isinstance(channel["frequency"], int)
    assert isinstance(channel["power"], float)


def test_parse_system_info(soup):
    """Test system information parsing."""
    parser = [ParserClass]()
    info = parser.parse_system_info(soup)

    # At minimum, should have model info
    assert "model" in info or "software_version" in info


def test_parse_full(soup):
    """Test full parsing returns expected structure."""
    parser = [ParserClass]()
    data = parser.parse(soup)

    # Verify structure
    assert "downstream" in data
    assert "upstream" in data
    assert "system_info" in data

    # Verify types
    assert isinstance(data["downstream"], list)
    assert isinstance(data["upstream"], list)
    assert isinstance(data["system_info"], dict)


def test_parse_empty_html():
    """Test parser handles empty HTML gracefully."""
    parser = [ParserClass]()
    soup = BeautifulSoup("<html></html>", "html.parser")

    # Should not raise exceptions
    channels = parser.parse_downstream(soup)
    assert isinstance(channels, list)
    assert len(channels) == 0


def test_parse_malformed_html():
    """Test parser handles malformed data gracefully."""
    parser = [ParserClass]()
    html = "<html><table><tr><td>Invalid</td></tr></table></html>"
    soup = BeautifulSoup(html, "html.parser")

    # Should not raise exceptions
    data = parser.parse(soup)
    assert isinstance(data, dict)
```

## Step 5: Verify Auto-Discovery

Your parser will be **automatically discovered** - no registry updates needed!

To verify your parser is being discovered:

```python
# In Python console or test
from custom_components.cable_modem_monitor.parsers import get_parsers

for parser in get_parsers():
    print(f"{parser.name} ({parser.manufacturer})")
```

Your new parser should appear in the list.

## Step 6: Update Documentation

### 6.1 README.md

Add your modem to the supported modems table:

```markdown
| Manufacturer | Model | DOCSIS | Channels | Status |
|--------------|-------|--------|----------|--------|
| [Manufacturer] | [Model] | 3.0/3.1 | 24x8 | ✅ Supported |
```

### 6.2 CHANGELOG.md

Document the addition:

```markdown
## [Unreleased]

### Added
- Support for [Manufacturer] [Model] cable modem (#[issue])
```

### 6.3 Parser Documentation

Ensure your parser has:
- Module docstring describing the modem
- Class docstring
- Method docstrings for all public methods
- Inline comments for complex logic

## Step 7: Code Quality Checks

### Run Linters

```bash
# Ruff (linting)
ruff check custom_components/cable_modem_monitor/parsers/[manufacturer]/[model].py

# Mypy (type checking)
mypy custom_components/cable_modem_monitor/parsers/[manufacturer]/[model].py

# Black (formatting)
black custom_components/cable_modem_monitor/parsers/[manufacturer]/[model].py
```

### Fix Issues

- Resolve any linting errors
- Add type hints where missing
- Format code to match project style

## Step 8: Test with Real Modem (Optional)

If you have access to the physical modem:

1. Install the component in Home Assistant
2. Configure with your modem's IP and credentials
3. Verify data collection works
4. Check Home Assistant logs for errors
5. Validate sensor data in UI

## Step 9: Submit Pull Request

### 9.1 Commit Changes

```bash
git add custom_components/cable_modem_monitor/parsers/[manufacturer]/
git add tests/parsers/[manufacturer]/
git add README.md CHANGELOG.md

git commit -m "feat: Add support for [Manufacturer] [Model] modem"
```

**Note:** You don't need to modify `parsers/__init__.py` - auto-discovery handles registration.

### 9.2 Create Pull Request

Include in your PR description:
- Modem model and DOCSIS version
- Firmware version tested
- Test results (unit tests, real modem if available)
- Any known limitations or issues
- Screenshots (optional but helpful)

## Common Parsing Patterns

### Pattern 1: Table Parsing

```python
def parse_downstream(self, soup: BeautifulSoup) -> list[dict]:
    channels = []
    table = soup.find("table", {"id": "downstream"})
    if not table:
        return channels

    rows = table.find_all("tr")[1:]  # Skip header
    for row in rows:
        cells = row.find_all("td")
        if len(cells) >= 7:
            channels.append({
                "channel_id": cells[0].text.strip(),
                "frequency": int(cells[1].text.strip()),
                # ... more fields
            })
    return channels
```

### Pattern 2: JavaScript Variable Extraction

```python
import re

def parse_downstream(self, soup: BeautifulSoup) -> list[dict]:
    channels = []
    script = soup.find("script", text=re.compile("var channelData"))
    if script:
        match = re.search(r"var channelData = ['"]([^'"]+)['"]", script.string)
        if match:
            data = match.group(1).split("|")
            # Parse split data into channels
    return channels
```

### Pattern 3: Multi-Page Parsing

```python
def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
    # Parse main page
    system_info = self.parse_system_info(soup)

    # Fetch additional page for channel data
    if session and base_url:
        response = session.get(f"{base_url}/channels.asp")
        channel_soup = BeautifulSoup(response.text, "html.parser")
        downstream = self.parse_downstream(channel_soup)
        upstream = self.parse_upstream(channel_soup)
    else:
        downstream = []
        upstream = []

    return {
        "downstream": downstream,
        "upstream": upstream,
        "system_info": system_info,
    }
```

### Pattern 4: Robust Error Handling

```python
def parse_downstream(self, soup: BeautifulSoup) -> list[dict]:
    channels = []

    try:
        table = soup.find("table", {"id": "downstream"})
        if not table:
            _LOGGER.warning("Downstream table not found")
            return channels

        rows = table.find_all("tr")[1:]

        for i, row in enumerate(rows):
            try:
                cells = row.find_all("td")
                if len(cells) < 7:
                    _LOGGER.debug("Row %d has insufficient cells, skipping", i)
                    continue

                channel = {
                    "channel_id": cells[0].text.strip(),
                    "frequency": int(cells[1].text.strip()),
                    "power": float(cells[2].text.strip()),
                    # ... more fields
                }
                channels.append(channel)

            except (ValueError, IndexError) as e:
                _LOGGER.warning("Error parsing channel %d: %s", i, e)
                continue

    except Exception as e:
        _LOGGER.error("Error parsing downstream channels: %s", e, exc_info=True)

    _LOGGER.info("Parsed %d downstream channels", len(channels))
    return channels
```

## Troubleshooting

### Issue: Parser not detected during auto-discovery

**Solution:** Check your `can_parse()` method:
- Make sure detection logic is specific enough
- Verify title/meta tag names match actual HTML
- Add more detection criteria if needed

### Issue: Authentication fails

**Solution (v3.12+):**
- Auth is auto-detected - check if your modem's login form uses non-standard fields
- If auto-detection fails, add `auth_form_hints` to your parser
- Check diagnostics export for `auth_discovery` section to see detected strategy
- Test authentication manually with curl/Postman to understand the flow
- For complex JS-based auth, capture HAR file and open an issue

### Issue: Parsing returns empty data

**Solution:**
- Verify HTML fixtures match expected structure
- Add debug logging to see what's being found
- Check CSS selectors/XPath expressions
- Inspect actual HTML in browser developer tools

### Issue: Tests fail with type errors

**Solution:**
- Ensure all numeric values are converted to correct types (int/float)
- Handle empty strings before conversion
- Add type checks before assignments

## Resources

### DOCSIS Standards

The parser data schema is aligned with industry standards for cable modem metrics:

| Standard | Description | Link |
|----------|-------------|------|
| **RFC 4546** | DOCSIS 2.0 RF Interface MIB - defines core metrics (`docsIfSigQSignalNoise`, `docsIfDownChannelPower`, etc.) | [IETF](https://www.rfc-editor.org/rfc/rfc4546) |
| **CableLabs MIBs** | Normative source for DOCSIS 3.0/3.1 MIB definitions | [mibs.cablelabs.com](http://mibs.cablelabs.com/MIBs/DOCSIS/) |
| **TR-181 DOCSIS** | Broadband Forum consumer-side data model | [GitHub](https://github.com/BroadbandForum/cwmp-data-models/blob/master/tr-181-2-15-0-docsis.xml) |

Schema field mapping:
- `frequency` → `docsIfDownChannelFrequency` (Hz)
- `power` → `docsIfDownChannelPower` (dBmV, standards use TenthdBmV)
- `snr` → `docsIfSigQSignalNoise` (dB, standards use TenthdB)
- `corrected` → `docsIfSigQCorrecteds`
- `uncorrected` → `docsIfSigQUncorrectables`

### Project Resources

- **Example Parsers:**
  - Simple: `arris/sb6141.py`
  - Complex: `motorola/mb8611_hnap.py`
  - Multi-page: `netgear/cm600.py`
- **Issue Tracker:** GitHub Issues
- **Community:** Discord/Forum [if available]

## Getting Help

If you need assistance:
1. Check existing parsers for similar patterns
2. Review this guide thoroughly
3. Open a GitHub Discussion for questions
4. Join community chat for real-time help

## Attribution

If you use reference code from other MIT-licensed projects:

```python
"""Parser for [Model] cable modem.

Based on implementation patterns from:
- [Project Name] by [Author] (MIT License)
  https://github.com/[user]/[repo]

Adapted for cable_modem_monitor architecture.
"""
```

---

**Happy parsing!** 🎉

Your contribution helps expand support for cable modems and benefits the entire community. Thank you for contributing!
