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

3. IMPLEMENT can_parse()
   - Add detection logic to identify your modem's HTML
   - Check for unique page title, CSS classes, or URL patterns
   - Return True if this is your modem, False otherwise

4. IMPLEMENT parse_downstream()
   - Extract downstream channel data from HTML
   - Return list of dicts with: channel_id, frequency, power, snr
   - Include corrected/uncorrected if available

5. IMPLEMENT parse_upstream()
   - Extract upstream channel data from HTML
   - Return list of dicts with: channel_id, frequency, power

6. IMPLEMENT parse_system_info() (OPTIONAL)
   - Extract modem info like software_version, system_uptime
   - Return dict with available info

7. TEST YOUR PARSER
   - Place modem HTML in tests/fixtures/your_modem.html
   - Run: pytest tests/test_modem_scraper.py -v
   - Verify all channels parsed correctly

8. SUBMIT
   - Create a pull request on GitHub
   - Include sample HTML (redact any personal info)
   - Describe what modem model(s) you tested

EXAMPLE USAGE:
==============
See motorola_mb.py or arris_sb6141.py for real-world examples.
"""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from .base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)


class YourModemParser(ModemParser):
    """Parser for [Your Modem Brand/Model]."""

    ***REMOVED*** =========================================================================
    ***REMOVED*** STEP 2: UPDATE THESE METADATA FIELDS
    ***REMOVED*** =========================================================================
    name = "Your Modem Model"  ***REMOVED*** e.g., "Netgear CM1000"
    manufacturer = "Your Manufacturer"  ***REMOVED*** e.g., "Netgear"
    models = ["MODEL1", "MODEL2"]  ***REMOVED*** e.g., ["CM1000", "CM1100"]

    ***REMOVED*** =========================================================================
    ***REMOVED*** STEP 3: IMPLEMENT MODEM DETECTION
    ***REMOVED*** =========================================================================
    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """Detect if this is your modem.

        Args:
            soup: BeautifulSoup object of the page
            url: URL that was fetched
            html: Raw HTML string

        Returns:
            True if this parser can handle this modem, False otherwise

        Detection strategies (use one or more):
        - Check page title: soup.find("title")
        - Check for unique CSS classes: soup.find("div", class_="unique-class")
        - Check URL pattern: "yourmodem.asp" in url
        - Check for unique text: "YourBrand" in html
        - Check table structure: specific number/format of tables

        Example:
            title = soup.find("title")
            if title and "YourBrand Cable Modem" in title.text:
                return True

            if "yourmodem_status.html" in url.lower():
                return True

            return False
        """
        ***REMOVED*** TODO: Implement your detection logic here
        ***REMOVED*** Example checks:

        ***REMOVED*** Check page title
        title = soup.find("title")
        if title and "YOUR MODEM NAME" in title.text:
            return True

        ***REMOVED*** Check for unique CSS class
        if soup.find("div", class_="your-unique-class"):
            return True

        ***REMOVED*** Check URL pattern
        return "your_modem_page.html" in url.lower()

    ***REMOVED*** =========================================================================
    ***REMOVED*** STEP 4: IMPLEMENT DOWNSTREAM CHANNEL PARSING
    ***REMOVED*** =========================================================================
    def parse_downstream(self, soup: BeautifulSoup) -> list[dict]:
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
            ***REMOVED*** TODO: Find the downstream table
            ***REMOVED*** Example: Look for table with "Downstream" in header
            tables = soup.find_all("table")

            for table in tables:
                ***REMOVED*** Check if this is the downstream table
                header_row = table.find("tr")
                if not header_row:
                    continue

                header_text = header_row.text.lower()
                if "downstream" not in header_text:
                    continue

                ***REMOVED*** Parse each data row
                for row in table.find_all("tr")[1:]:  ***REMOVED*** Skip header
                    cols = row.find_all("td")

                    if len(cols) < 4:  ***REMOVED*** Need at least channel, freq, power, snr
                        continue

                    try:
                        channel = {
                            "channel_id": str(cols[0].text.strip()),
                            "frequency": int(cols[1].text.strip()),  ***REMOVED*** Adjust index
                            "power": float(cols[2].text.strip()),
                            "snr": float(cols[3].text.strip()),
                        }

                        ***REMOVED*** Add optional error stats if available
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

    ***REMOVED*** =========================================================================
    ***REMOVED*** STEP 5: IMPLEMENT UPSTREAM CHANNEL PARSING
    ***REMOVED*** =========================================================================
    def parse_upstream(self, soup: BeautifulSoup) -> list[dict]:
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
            ***REMOVED*** TODO: Find the upstream table
            tables = soup.find_all("table")

            for table in tables:
                header_row = table.find("tr")
                if not header_row:
                    continue

                header_text = header_row.text.lower()
                if "upstream" not in header_text:
                    continue

                ***REMOVED*** Parse each data row
                for row in table.find_all("tr")[1:]:  ***REMOVED*** Skip header
                    cols = row.find_all("td")

                    if len(cols) < 3:  ***REMOVED*** Need at least channel, freq, power
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

    ***REMOVED*** =========================================================================
    ***REMOVED*** STEP 6: IMPLEMENT SYSTEM INFO PARSING (OPTIONAL)
    ***REMOVED*** =========================================================================
    def parse_system_info(self, soup: BeautifulSoup) -> dict:
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
            ***REMOVED*** TODO: Find system info
            ***REMOVED*** Example: Look for specific labels in the HTML

            ***REMOVED*** Software version
            version_elem = soup.find(text="Software Version")
            if version_elem:
                ***REMOVED*** Get the value (might be in next sibling, parent, etc.)
                value = version_elem.find_next("td")
                if value:
                    info["software_version"] = value.text.strip()

            ***REMOVED*** System uptime
            uptime_elem = soup.find(text="Uptime")
            if uptime_elem:
                value = uptime_elem.find_next("td")
                if value:
                    info["system_uptime"] = value.text.strip()

            _LOGGER.debug(f"Parsed system info: {info}")

        except Exception as e:
            _LOGGER.error(f"Error parsing system info: {e}")

        return info


***REMOVED*** =============================================================================
***REMOVED*** TESTING CHECKLIST
***REMOVED*** =============================================================================
"""
Before submitting your parser, verify:

□ can_parse() returns True ONLY for your modem
□ can_parse() returns False for other modems
□ parse_downstream() returns valid channel data
□ parse_upstream() returns valid channel data
□ All channel IDs are present
□ Frequencies are in Hz (not MHz)
□ Power levels are reasonable (-15 to +15 dBmV typical)
□ SNR values are reasonable (30-45 dB typical)
□ Empty/missing data handled gracefully
□ Logs helpful debug/warning messages
□ No exceptions on valid HTML
□ Works with your modem's actual HTML

To test:
1. Save your modem's HTML: curl http://192.168.100.1 > tests/fixtures/your_modem.html
2. Run tests: pytest tests/test_modem_scraper.py -v
3. Check logs for warnings/errors
4. Verify channel counts and values look correct
"""
