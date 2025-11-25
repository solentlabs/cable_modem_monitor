***REMOVED*** Guide: Adding a New Modem Parser

This guide provides step-by-step instructions for adding support for a new cable modem model, based on the patterns established in this project.

***REMOVED******REMOVED*** Prerequisites

- Python 3.9+
- Access to the modem's web interface (or HTML captures)
- Understanding of the modem's authentication mechanism
- Knowledge of BeautifulSoup and HTML parsing

***REMOVED******REMOVED*** Overview

Adding a new parser involves:
1. Creating the parser module
2. Implementing required methods
3. Adding test fixtures
4. Writing unit tests
5. Documenting the changes

**Note:** Parser registry updates are **no longer required**! The discovery system automatically finds and registers new parsers.

***REMOVED******REMOVED*** Step 1: Create Parser Module

***REMOVED******REMOVED******REMOVED*** 1.1 Choose Directory Structure

Parsers are organized by manufacturer:

```
custom_components/cable_modem_monitor/parsers/
├── arris/
│   ├── __init__.py
│   ├── sb6141.py
│   └── sb6190.py
├── motorola/
│   ├── __init__.py
│   ├── mb8611_hnap.py
│   └── mb8611_static.py
├── netgear/
│   ├── __init__.py
│   └── cm600.py
└── [your_manufacturer]/
    ├── __init__.py
    └── [model].py
```

***REMOVED******REMOVED******REMOVED*** 1.2 Create Parser File

**File:** `custom_components/cable_modem_monitor/parsers/[manufacturer]/[model].py`

```python
"""Parser for [Manufacturer] [Model] cable modem.

Brief description of the modem and its capabilities.

Firmware tested: V1.0.0

Key pages:
- /: Main page
- /status.html: Channel status page

Authentication: HTTP Basic Auth / Form-based / HNAP / None

Related: Issue ***REMOVED***[number] (if applicable)
"""

from __future__ import annotations

import logging
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.auth_config import BasicAuthConfig
from custom_components.cable_modem_monitor.core.authentication import AuthStrategyType
from ..base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)


class [Manufacturer][Model]Parser(ModemParser):
    """Parser for [Manufacturer] [Model] cable modem."""

    name = "[Manufacturer] [Model]"
    manufacturer = "[Manufacturer]"
    models = ["[MODEL]"]  ***REMOVED*** List of model numbers this parser supports
    priority = 50  ***REMOVED*** Standard priority (1-100, higher = preferred)

    ***REMOVED*** Authentication configuration
    auth_config = BasicAuthConfig(
        strategy=AuthStrategyType.BASIC_HTTP,
        ***REMOVED*** Add other auth parameters as needed
    )

    ***REMOVED*** URL patterns to try for modem data
    url_patterns = [
        {"path": "/", "auth_method": "basic", "auth_required": False},
        {"path": "/status.html", "auth_method": "basic", "auth_required": False},
    ]

    def login(self, session, base_url, username, password) -> bool:
        """Perform login to the modem.

        Args:
            session: Requests session object
            base_url: Base URL of the modem (e.g., http://192.168.100.1)
            username: Username for authentication
            password: Password for authentication

        Returns:
            True if login successful or not required, False otherwise
        """
        ***REMOVED*** Implement authentication logic
        ***REMOVED*** For HTTP Basic Auth, this may be a no-op as session handles it
        return True

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

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """Detect if this parser can handle the given HTML.

        This method is called during auto-detection to determine which
        parser should be used for a particular modem.

        Args:
            soup: BeautifulSoup object of the page
            url: URL that was fetched
            html: Raw HTML string

        Returns:
            True if this parser can handle the page, False otherwise
        """
        ***REMOVED*** Implement detection logic
        ***REMOVED*** Example: Check for specific text in title or meta tags
        title = soup.find("title")
        if title and "[MODEL]" in title.text.upper():
            return True

        ***REMOVED*** Check for manufacturer name in HTML
        if "[MANUFACTURER]" in html.upper() and "[MODEL]" in html.upper():
            return True

        return False

    def parse_downstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse downstream channel data.

        Returns:
            List of channel dictionaries with the following keys:
            - channel_id: Channel identifier (string)
            - frequency: Frequency in Hz (int)
            - power: Power level in dBmV (float)
            - snr: Signal-to-noise ratio in dB (float)
            - modulation: Modulation type (string, e.g., "QAM256")
            - corrected: Corrected error count (int)
            - uncorrected: Uncorrected error count (int)
        """
        channels = []

        ***REMOVED*** Implement downstream parsing logic
        ***REMOVED*** Example: Find table and extract rows
        table = soup.find("table", {"id": "downstream_table"})
        if not table:
            _LOGGER.warning("Downstream table not found")
            return channels

        rows = table.find_all("tr")[1:]  ***REMOVED*** Skip header row

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
            - modulation: Modulation type (string)
            - symbol_rate: Symbol rate in Ksym/sec (int)
        """
        channels = []

        ***REMOVED*** Implement upstream parsing logic
        ***REMOVED*** Similar to downstream but with different fields

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

        ***REMOVED*** Implement system info parsing
        ***REMOVED*** Extract model, firmware version, uptime, etc.

        return info
```

***REMOVED******REMOVED*** Step 2: Handle Authentication

***REMOVED******REMOVED******REMOVED*** Common Authentication Types

***REMOVED******REMOVED******REMOVED******REMOVED*** HTTP Basic Auth
```python
from custom_components.cable_modem_monitor.core.auth_config import BasicAuthConfig
from custom_components.cable_modem_monitor.core.authentication import AuthStrategyType

auth_config = BasicAuthConfig(
    strategy=AuthStrategyType.BASIC_HTTP,
)

def login(self, session, base_url, username, password) -> bool:
    ***REMOVED*** HTTP Basic Auth is handled automatically by the session
    return True
```

***REMOVED******REMOVED******REMOVED******REMOVED*** Form-Based Auth
```python
from custom_components.cable_modem_monitor.core.auth_config import FormAuthConfig

auth_config = FormAuthConfig(
    strategy=AuthStrategyType.FORM_POST,
    login_url="/login.html",
    username_field="username",
    password_field="password",
)

def login(self, session, base_url, username, password) -> bool:
    response = session.post(
        f"{base_url}/login.html",
        data={"username": username, "password": password}
    )
    return response.status_code == 200
```

***REMOVED******REMOVED******REMOVED******REMOVED*** HNAP (Home Network Administration Protocol)
```python
from custom_components.cable_modem_monitor.core.auth_config import HNAPAuthConfig

auth_config = HNAPAuthConfig(
    strategy=AuthStrategyType.HNAP_SESSION,
    login_url="/Login.html",
    hnap_endpoint="/HNAP1/",
    soap_action_namespace="http://purenetworks.com/HNAP1/",
)

def login(self, session, base_url, username, password) -> bool:
    ***REMOVED*** HNAP authentication is handled by the auth framework
    return True
```

***REMOVED******REMOVED*** Step 3: Add Test Fixtures

***REMOVED******REMOVED******REMOVED*** 3.1 Capture Modem HTML

Use the provided tool to capture HTML from your modem:

```bash
python tools/capture_modem_html.py --url http://192.168.100.1 --output tests/parsers/[manufacturer]/fixtures/[model]/
```

Or manually save HTML pages:
1. Open modem web interface in browser
2. Right-click → Save Page As → Complete HTML
3. Save to `tests/parsers/[manufacturer]/fixtures/[model]/`

***REMOVED******REMOVED******REMOVED*** 3.2 Organize Fixtures

```
tests/parsers/[manufacturer]/fixtures/[model]/
├── index.html           ***REMOVED*** Main page
├── status.html          ***REMOVED*** Channel status page
├── logs.html            ***REMOVED*** Event logs (optional)
└── README.md            ***REMOVED*** Document fixture source and details
```

**README.md example:**
```markdown
***REMOVED*** [Manufacturer] [Model] Test Fixtures

**Source:** Real [Model] modem
**Firmware:** V1.0.0
**ISP:** Comcast
**Date Captured:** 2025-11-14

***REMOVED******REMOVED*** Files

- `index.html`: Main page (/)
- `status.html`: Channel status (/status.html)

***REMOVED******REMOVED*** Notes

- Sensitive information (MAC addresses, serial numbers) has been redacted
- All channels are operational in this capture
```

***REMOVED******REMOVED*** Step 4: Write Unit Tests

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

    ***REMOVED*** Verify we got channels
    assert len(channels) > 0, "Expected at least one downstream channel"

    ***REMOVED*** Verify channel structure
    channel = channels[0]
    assert "channel_id" in channel
    assert "frequency" in channel
    assert "power" in channel
    assert "snr" in channel
    assert "modulation" in channel
    assert "corrected" in channel
    assert "uncorrected" in channel

    ***REMOVED*** Verify data types
    assert isinstance(channel["channel_id"], str)
    assert isinstance(channel["frequency"], int)
    assert isinstance(channel["power"], float)
    assert isinstance(channel["snr"], float)
    assert isinstance(channel["modulation"], str)
    assert isinstance(channel["corrected"], int)
    assert isinstance(channel["uncorrected"], int)

    ***REMOVED*** Verify reasonable values (adjust based on your modem)
    assert channel["frequency"] > 0
    assert -20 <= channel["power"] <= 20  ***REMOVED*** Typical range
    assert 0 <= channel["snr"] <= 50      ***REMOVED*** Typical range


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

    ***REMOVED*** Verify data types
    assert isinstance(channel["frequency"], int)
    assert isinstance(channel["power"], float)


def test_parse_system_info(soup):
    """Test system information parsing."""
    parser = [ParserClass]()
    info = parser.parse_system_info(soup)

    ***REMOVED*** At minimum, should have model info
    assert "model" in info or "software_version" in info


def test_parse_full(soup):
    """Test full parsing returns expected structure."""
    parser = [ParserClass]()
    data = parser.parse(soup)

    ***REMOVED*** Verify structure
    assert "downstream" in data
    assert "upstream" in data
    assert "system_info" in data

    ***REMOVED*** Verify types
    assert isinstance(data["downstream"], list)
    assert isinstance(data["upstream"], list)
    assert isinstance(data["system_info"], dict)


def test_parse_empty_html():
    """Test parser handles empty HTML gracefully."""
    parser = [ParserClass]()
    soup = BeautifulSoup("<html></html>", "html.parser")

    ***REMOVED*** Should not raise exceptions
    channels = parser.parse_downstream(soup)
    assert isinstance(channels, list)
    assert len(channels) == 0


def test_parse_malformed_html():
    """Test parser handles malformed data gracefully."""
    parser = [ParserClass]()
    html = "<html><table><tr><td>Invalid</td></tr></table></html>"
    soup = BeautifulSoup(html, "html.parser")

    ***REMOVED*** Should not raise exceptions
    data = parser.parse(soup)
    assert isinstance(data, dict)
```

***REMOVED******REMOVED*** Step 5: Verify Auto-Discovery

Your parser will be **automatically discovered** - no registry updates needed!

To verify your parser is being discovered:

```python
***REMOVED*** In Python console or test
from custom_components.cable_modem_monitor.parsers import get_parsers

for parser in get_parsers():
    print(f"{parser.name} ({parser.manufacturer})")
```

Your new parser should appear in the list.

***REMOVED******REMOVED*** Step 6: Update Documentation

***REMOVED******REMOVED******REMOVED*** 6.1 README.md

Add your modem to the supported modems table:

```markdown
| Manufacturer | Model | DOCSIS | Channels | Status |
|--------------|-------|--------|----------|--------|
| [Manufacturer] | [Model] | 3.0/3.1 | 24x8 | ✅ Supported |
```

***REMOVED******REMOVED******REMOVED*** 6.2 CHANGELOG.md

Document the addition:

```markdown
***REMOVED******REMOVED*** [Unreleased]

***REMOVED******REMOVED******REMOVED*** Added
- Support for [Manufacturer] [Model] cable modem (***REMOVED***[issue])
```

***REMOVED******REMOVED******REMOVED*** 6.3 Parser Documentation

Ensure your parser has:
- Module docstring describing the modem
- Class docstring
- Method docstrings for all public methods
- Inline comments for complex logic

***REMOVED******REMOVED*** Step 7: Code Quality Checks

***REMOVED******REMOVED******REMOVED*** Run Linters

```bash
***REMOVED*** Ruff (linting)
ruff check custom_components/cable_modem_monitor/parsers/[manufacturer]/[model].py

***REMOVED*** Mypy (type checking)
mypy custom_components/cable_modem_monitor/parsers/[manufacturer]/[model].py

***REMOVED*** Black (formatting)
black custom_components/cable_modem_monitor/parsers/[manufacturer]/[model].py
```

***REMOVED******REMOVED******REMOVED*** Fix Issues

- Resolve any linting errors
- Add type hints where missing
- Format code to match project style

***REMOVED******REMOVED*** Step 8: Test with Real Modem (Optional)

If you have access to the physical modem:

1. Install the component in Home Assistant
2. Configure with your modem's IP and credentials
3. Verify data collection works
4. Check Home Assistant logs for errors
5. Validate sensor data in UI

***REMOVED******REMOVED*** Step 9: Submit Pull Request

***REMOVED******REMOVED******REMOVED*** 9.1 Commit Changes

```bash
git add custom_components/cable_modem_monitor/parsers/[manufacturer]/
git add tests/parsers/[manufacturer]/
git add README.md CHANGELOG.md

git commit -m "feat: Add support for [Manufacturer] [Model] modem"
```

**Note:** You don't need to modify `parsers/__init__.py` - auto-discovery handles registration.

***REMOVED******REMOVED******REMOVED*** 9.2 Create Pull Request

Include in your PR description:
- Modem model and DOCSIS version
- Firmware version tested
- Test results (unit tests, real modem if available)
- Any known limitations or issues
- Screenshots (optional but helpful)

***REMOVED******REMOVED*** Common Parsing Patterns

***REMOVED******REMOVED******REMOVED*** Pattern 1: Table Parsing

```python
def parse_downstream(self, soup: BeautifulSoup) -> list[dict]:
    channels = []
    table = soup.find("table", {"id": "downstream"})
    if not table:
        return channels

    rows = table.find_all("tr")[1:]  ***REMOVED*** Skip header
    for row in rows:
        cells = row.find_all("td")
        if len(cells) >= 7:
            channels.append({
                "channel_id": cells[0].text.strip(),
                "frequency": int(cells[1].text.strip()),
                ***REMOVED*** ... more fields
            })
    return channels
```

***REMOVED******REMOVED******REMOVED*** Pattern 2: JavaScript Variable Extraction

```python
import re

def parse_downstream(self, soup: BeautifulSoup) -> list[dict]:
    channels = []
    script = soup.find("script", text=re.compile("var channelData"))
    if script:
        match = re.search(r"var channelData = ['"]([^'"]+)['"]", script.string)
        if match:
            data = match.group(1).split("|")
            ***REMOVED*** Parse split data into channels
    return channels
```

***REMOVED******REMOVED******REMOVED*** Pattern 3: Multi-Page Parsing

```python
def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
    ***REMOVED*** Parse main page
    system_info = self.parse_system_info(soup)

    ***REMOVED*** Fetch additional page for channel data
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

***REMOVED******REMOVED******REMOVED*** Pattern 4: Robust Error Handling

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
                    ***REMOVED*** ... more fields
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

***REMOVED******REMOVED*** Troubleshooting

***REMOVED******REMOVED******REMOVED*** Issue: Parser not detected during auto-discovery

**Solution:** Check your `can_parse()` method:
- Make sure detection logic is specific enough
- Verify title/meta tag names match actual HTML
- Add more detection criteria if needed

***REMOVED******REMOVED******REMOVED*** Issue: Authentication fails

**Solution:**
- Verify auth_config is correct for your modem type
- Check if credentials are being passed correctly
- Add logging to `login()` method to debug
- Test authentication manually with curl/Postman

***REMOVED******REMOVED******REMOVED*** Issue: Parsing returns empty data

**Solution:**
- Verify HTML fixtures match expected structure
- Add debug logging to see what's being found
- Check CSS selectors/XPath expressions
- Inspect actual HTML in browser developer tools

***REMOVED******REMOVED******REMOVED*** Issue: Tests fail with type errors

**Solution:**
- Ensure all numeric values are converted to correct types (int/float)
- Handle empty strings before conversion
- Add type checks before assignments

***REMOVED******REMOVED*** Resources

- **Project Wiki:** [Link to wiki if available]
- **Example Parsers:**
  - Simple: `arris/sb6141.py`
  - Complex: `motorola/mb8611_hnap.py`
  - Multi-page: `netgear/cm600.py`
- **Issue Tracker:** GitHub Issues
- **Community:** Discord/Forum [if available]

***REMOVED******REMOVED*** Getting Help

If you need assistance:
1. Check existing parsers for similar patterns
2. Review this guide thoroughly
3. Open a GitHub Discussion for questions
4. Join community chat for real-time help

***REMOVED******REMOVED*** Attribution

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
