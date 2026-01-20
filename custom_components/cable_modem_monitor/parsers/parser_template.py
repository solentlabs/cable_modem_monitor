"""Template for creating a new modem parser.

This template provides a starting point for adding support for a new modem model.
Follow the steps below to create a parser for your modem.

STEP-BY-STEP GUIDE:
===================

1. RENAME THIS FILE
   - Copy this file to a new name: your_modem_name.py
   - Use lowercase with underscores (e.g., netgear_cm1000.py)

2. UPDATE CLASS NAME AND METADATA
   - Change "YourModemParser" to match your modem (e.g., "NetgearCM1000Parser")
   - Update name, manufacturer, and models list

3. CONFIGURE DETECTION HINTS (in modem.yaml)
   - Detection is handled by YAML hints in modem.yaml, not by code
   - Define login_markers for pre-auth detection (login page)
   - Define model_strings for post-auth detection (data pages)

4. CONFIGURE AUTH HINTS (if needed)
   - For standard auth (no auth, Basic Auth, standard forms): No hints needed
   - For non-standard form fields: Add auth_form_hints dict
   - For JavaScript-based auth: Add js_auth_hints dict
   - Authentication is handled automatically by AuthDiscovery at setup time

5. IMPLEMENT parse() - REQUIRED
   - Main method that returns ALL modem data
   - Returns dict with: downstream, upstream, system_info
   - Can use helper methods to organize code (see steps 6-8)

6. IMPLEMENT _parse_downstream() (HELPER METHOD - OPTIONAL)
   - Extract downstream channel data from HTML
   - Return list of dicts with: channel_id, frequency, power, snr
   - Called from main parse() method

7. IMPLEMENT _parse_upstream() (HELPER METHOD - OPTIONAL)
   - Extract upstream channel data from HTML
   - Return list of dicts with: channel_id, frequency, power
   - Called from main parse() method

8. IMPLEMENT _parse_system_info() (HELPER METHOD - OPTIONAL)
   - Extract modem info like software_version, system_uptime
   - Return dict with available info
   - Called from main parse() method

9. TEST YOUR PARSER
   - Place modem HTML in tests/fixtures/your_modem.html
   - Run: pytest tests/test_modem_scraper.py -v
   - Verify all channels parsed correctly

8. SUBMIT
   - Create a pull request on GitHub
   - Include sample HTML (redact any personal info)
   - Describe what modem model(s) you tested

EXAMPLE USAGE:
==============
See these parsers for real-world examples:
- Simple (single page): custom_components/cable_modem_monitor/parsers/arris/sb6141.py
- Complex (multi-page): custom_components/cable_modem_monitor/parsers/netgear/cm600.py
- With authentication: custom_components/cable_modem_monitor/parsers/motorola/generic.py
"""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)


class YourModemParser(ModemParser):
    """Parser for [Your Modem Brand/Model]."""

    # =========================================================================
    # STEP 2: UPDATE THESE METADATA FIELDS
    # =========================================================================
    name = "Your Modem Model"  # e.g., "Netgear CM1000"
    manufacturer = "Your Manufacturer"  # e.g., "Netgear"
    models = ["MODEL1", "MODEL2"]  # e.g., ["CM1000", "CM1100"]

    # =========================================================================
    # STEP 3: CONFIGURE AUTH HINTS (if non-standard auth)
    # =========================================================================
    # For modems with non-standard form field names:
    # auth_form_hints = {
    #     "username_field": "yourUsernameField",
    #     "password_field": "yourPasswordField",
    # }
    #
    # For modems with JavaScript-based auth (e.g., URL token session):
    # js_auth_hints = {
    #     "pattern": "url_token_session",
    #     "login_prefix": "login_",
    # }
    #
    # For standard auth (no auth, HTTP Basic, standard username/password forms):
    # No hints needed - AuthDiscovery will auto-detect

    # =========================================================================
    # STEP 4: MODEM DETECTION (via modem.yaml)
    # =========================================================================
    # Detection is handled by YAML hints in modem.yaml.
    #
    # In your modem.yaml, define:
    #
    #   auth:
    #     login_markers:           # Phase 1: Pre-auth detection (login page)
    #       - "YourBrand"          # Text that appears on the login page
    #       - "YourModel"          # Model string visible pre-auth
    #       - "/login.html"        # Form action or URL pattern
    #
    #   detection:
    #     model_strings:           # Phase 2: Post-auth detection (data pages)
    #       - "YourModel123"       # Model string visible after login
    #       - "Your Product Name"  # Product identifier on data pages
    #
    # The HintMatcher uses these patterns to auto-detect your modem.

    # NOTE: login() method is NOT needed for most parsers
    # Authentication is handled by AuthDiscovery at setup time.
    # Only implement login() if your modem requires special auth handling
    # that can't be expressed via auth_form_hints or js_auth_hints.

    # =========================================================================
    # STEP 5: IMPLEMENT parse() METHOD - REQUIRED
    # =========================================================================
    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Parse all data from the modem.

        This is the MAIN method that must be implemented. It should return ALL
        modem data in a standardized format.

        Args:
            soup: BeautifulSoup object of the main page
            session: Optional requests.Session for fetching additional pages
            base_url: Optional base URL of modem (e.g., "http://192.168.100.1")

        Returns:
            Dictionary with ALL parsed data:
            {
                "downstream": [...],  # List of downstream channel dicts
                "upstream": [...],    # List of upstream channel dicts
                "system_info": {...}  # Dict with system information
            }

        Tips:
        - Use helper methods (_parse_downstream, etc.) to organize code
        - If modem needs multiple pages, use session.get() to fetch them
        - Handle errors gracefully - return empty lists/dicts on failure
        - Log helpful debug/warning messages
        """
        # TODO: Implement your parsing logic

        # Option 1: Parse everything inline (simple modems)
        downstream: list[dict] = []
        upstream: list[dict] = []
        system_info: dict[str, str] = {}

        # ... your parsing code here ...

        # Option 2: Use helper methods (recommended for complex modems)
        # downstream = self._parse_downstream(soup)
        # upstream = self._parse_upstream(soup)
        # system_info = self._parse_system_info(soup)

        # Option 3: Multi-page parsing (if modem data is on multiple pages)
        # if session and base_url:
        #     # Fetch additional page
        #     response = session.get(f"{base_url}/channel_status.html", timeout=10)
        #     if response.status_code == 200:
        #         channel_soup = BeautifulSoup(response.text, "html.parser")
        #         downstream = self._parse_downstream(channel_soup)

        return {
            "downstream": downstream,
            "upstream": upstream,
            "system_info": system_info,
        }

    # =========================================================================
    # STEP 6: HELPER METHOD - DOWNSTREAM PARSING (OPTIONAL)
    # =========================================================================
    def _parse_downstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse downstream channel data.

        Returns:
            List of dictionaries, each containing:
            - channel_id: str - Channel identifier
            - frequency: int - Frequency in Hz
            - power: float - Power level in dBmV
            - snr: float - Signal-to-noise ratio in dB
            - corrected: int - Corrected errors (optional)
            - uncorrected: int - Uncorrected errors (optional)

        Tips:
        - Use soup.find_all("table") to find tables
        - Look for table headers to identify the right table
        - Use .find_all("tr") to iterate rows
        - Use .find_all("td") to get cell data
        - Handle empty/missing data gracefully
        - Log warnings for skipped channels
        """
        channels = []

        try:
            # TODO: Find the downstream table
            # Example: Look for table with "Downstream" in header
            tables = soup.find_all("table")

            for table in tables:
                # Check if this is the downstream table
                header_row = table.find("tr")
                if not header_row:
                    continue

                header_text = header_row.text.lower()
                if "downstream" not in header_text:
                    continue

                # Parse each data row
                for row in table.find_all("tr")[1:]:  # Skip header
                    cols = row.find_all("td")

                    if len(cols) < 4:  # Need at least channel, freq, power, snr
                        continue

                    try:
                        channel = {
                            "channel_id": str(cols[0].text.strip()),
                            "frequency": int(cols[1].text.strip()),  # Adjust index
                            "power": float(cols[2].text.strip()),
                            "snr": float(cols[3].text.strip()),
                        }

                        # Add optional error stats if available
                        if len(cols) > 4:
                            channel["corrected"] = int(cols[4].text.strip())
                        if len(cols) > 5:
                            channel["uncorrected"] = int(cols[5].text.strip())

                        channels.append(channel)

                    except (ValueError, AttributeError) as e:
                        _LOGGER.warning(f"Skipping downstream channel: {e}")
                        continue

            _LOGGER.debug(f"Parsed {len(channels)} downstream channels")

        except Exception as e:
            _LOGGER.error(f"Error parsing downstream channels: {e}")

        return channels

    # =========================================================================
    # STEP 7: HELPER METHOD - UPSTREAM PARSING (OPTIONAL)
    # =========================================================================
    def _parse_upstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse upstream channel data.

        Returns:
            List of dictionaries, each containing:
            - channel_id: str - Channel identifier
            - frequency: int - Frequency in Hz
            - power: float - Power level in dBmV

        Tips:
        - Similar to downstream but typically fewer fields
        - Upstream usually doesn't have SNR or error stats
        - Watch for different table structures
        """
        channels = []

        try:
            # TODO: Find the upstream table
            tables = soup.find_all("table")

            for table in tables:
                header_row = table.find("tr")
                if not header_row:
                    continue

                header_text = header_row.text.lower()
                if "upstream" not in header_text:
                    continue

                # Parse each data row
                for row in table.find_all("tr")[1:]:  # Skip header
                    cols = row.find_all("td")

                    if len(cols) < 3:  # Need at least channel, freq, power
                        continue

                    try:
                        channel = {
                            "channel_id": str(cols[0].text.strip()),
                            "frequency": int(cols[1].text.strip()),
                            "power": float(cols[2].text.strip()),
                        }

                        channels.append(channel)

                    except (ValueError, AttributeError) as e:
                        _LOGGER.warning(f"Skipping upstream channel: {e}")
                        continue

            _LOGGER.debug(f"Parsed {len(channels)} upstream channels")

        except Exception as e:
            _LOGGER.error(f"Error parsing upstream channels: {e}")

        return channels

    # =========================================================================
    # STEP 8: HELPER METHOD - SYSTEM INFO PARSING (OPTIONAL)
    # =========================================================================
    def _parse_system_info(self, soup: BeautifulSoup) -> dict:
        """Parse system information.

        Returns:
            Dictionary with any available info:
            - software_version: str - Firmware version
            - system_uptime: str - How long modem has been running
            - hardware_version: str - Hardware version (optional)
            - serial_number: str - Serial number (optional)

        Tips:
        - Look for <span>, <div>, or table cells with labels
        - Common labels: "Software Version", "Uptime", "Firmware"
        - Return empty dict if no system info available
        - This method is optional - base class has fallback
        """
        info = {}

        try:
            # TODO: Find system info
            # Example: Look for specific labels in the HTML

            # Software version
            version_elem = soup.find(text="Software Version")
            if version_elem:
                # Get the value (might be in next sibling, parent, etc.)
                value = version_elem.find_next("td")
                if value:
                    info["software_version"] = value.text.strip()

            # System uptime
            uptime_elem = soup.find(text="Uptime")
            if uptime_elem:
                value = uptime_elem.find_next("td")
                if value:
                    info["system_uptime"] = value.text.strip()

            _LOGGER.debug(f"Parsed system info: {info}")

        except Exception as e:
            _LOGGER.error(f"Error parsing system info: {e}")

        return info


# =============================================================================
# TESTING CHECKLIST
# =============================================================================
# Before submitting your parser, verify:
#
# □ modem.yaml has detection hints (login_markers, model_strings)
# □ login() authenticates successfully (or returns True if no auth needed)
# □ parse() returns dict with "downstream", "upstream", "system_info" keys
# □ parse() downstream list contains valid channel data
# □ parse() upstream list contains valid channel data
# □ All channel IDs are present
# □ Frequencies are in Hz (not MHz)
# □ Power levels are reasonable (-15 to +15 dBmV typical)
# □ SNR values are reasonable (30-45 dB typical)
# □ Empty/missing data handled gracefully
# □ Logs helpful debug/warning messages
# □ No exceptions on valid HTML
# □ Works with your modem's actual HTML
#
# To test:
# 1. Save your modem's HTML: curl http://192.168.100.1 > tests/fixtures/your_modem.html
# 2. Run tests: pytest tests/test_modem_scraper.py -v
# 3. Check logs for warnings/errors
# 4. Verify channel counts and values look correct
