# =============================================================================
# AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY
#
# Source: modems/motorola/mb7621/parser.py
# This file is synced from modems/ during build. Edit the source file, then run:
#     make sync
# =============================================================================

"""Parser for Motorola MB7621 cable modem.

The Motorola MB7621 is a DOCSIS 3.0 cable modem with 24x8 channel bonding.

Key pages:
- /MotoSwInfo.asp: Software/hardware info (requires auth)
- /MotoConnection.asp: Channel data (requires auth)
- /MotoHome.asp: System info (requires auth)
- /MotoSecurity.asp: Security settings / restart

Authentication: Form-based with Base64-encoded password
"""

from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.base_parser import ModemParser
from custom_components.cable_modem_monitor.lib.utils import extract_float, extract_number, parse_uptime_to_seconds

_LOGGER = logging.getLogger(__name__)

# During modem restart, power readings may be temporarily zero.
# Ignore zero power readings during the first 5 minutes after boot.
RESTART_WINDOW_SECONDS = 300


class MotorolaMB7621Parser(ModemParser):
    """Parser for the Motorola MB7621 cable modem."""

    # Auth handled by AuthDiscovery (v3.12.0+) - form hints now in modem.yaml auth.form
    # MB7621 requires Base64-encoded passwords (configured in modem.yaml)
    # URL patterns now in modem.yaml pages config

    def parse_resources(self, resources: dict[str, Any]) -> dict:
        """Parse all data from pre-fetched resources.

        Expected resources:
            "/MotoConnection.asp": BeautifulSoup (channel data, uptime)
            "/MotoHome.asp": BeautifulSoup (system info, software version)
            "/MotoSwInfo.asp": BeautifulSoup (software/hardware info)
            "/": BeautifulSoup (may be any of the above)
        """
        system_info: dict[str, Any] = {}

        # Get specific pages from resources
        conn_soup = resources.get("/MotoConnection.asp")
        home_soup = resources.get("/MotoHome.asp")
        sw_info_soup = resources.get("/MotoSwInfo.asp")

        # If we have the main page ("/"), use it as fallback
        main_soup = resources.get("/")
        if main_soup is None:
            # Use first available BeautifulSoup as fallback
            for value in resources.values():
                if isinstance(value, BeautifulSoup):
                    main_soup = value
                    break

        # Determine which soup to use for channel data
        # Priority: /MotoConnection.asp > main page (any soup that might have channel tables)
        # Note: _has_channel_tables() only checks for downstream tables (Pwr+SNR)
        # but upstream tables (with Symb. Rate) may exist without downstream tables
        channel_soup = conn_soup if conn_soup else main_soup

        # Parse system info from all available pages
        # Each page may have different info, so we collect from all
        if sw_info_soup:
            sw_info = self._parse_system_info(sw_info_soup)
            system_info.update(sw_info)
            _LOGGER.debug("Parsed system_info from MotoSwInfo.asp: %s", sw_info)

        if conn_soup:
            conn_info = self._parse_system_info(conn_soup)
            system_info.update(conn_info)
            _LOGGER.debug("Parsed system_info from MotoConnection.asp: %s", conn_info)

        if home_soup:
            home_info = self._parse_system_info(home_soup)
            system_info.update(home_info)
            _LOGGER.debug("Parsed system_info from MotoHome.asp: %s", home_info)

        # Parse main page last if it's different from the specific pages
        if main_soup and main_soup not in (conn_soup, home_soup, sw_info_soup):
            main_info = self._parse_system_info(main_soup)
            system_info.update(main_info)
            _LOGGER.debug("Parsed system_info from main page: %s", main_info)

        # Parse channel data from any available soup
        # The _parse_downstream and _parse_upstream methods handle finding their own tables
        downstream_channels: list[dict] = []
        upstream_channels: list[dict] = []
        if channel_soup:
            downstream_channels = self._parse_downstream(channel_soup, system_info)
            upstream_channels = self._parse_upstream(channel_soup, system_info)

        _LOGGER.debug("Final system_info being returned: %s", system_info)
        return {
            "downstream": downstream_channels,
            "upstream": upstream_channels,
            "system_info": system_info,
        }

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Parse all data from the modem (legacy interface).

        This method maintains backwards compatibility by building a resources dict
        and delegating to parse_resources().
        """
        resources: dict[str, Any] = {"/": soup}

        # Legacy path: fetch additional pages if session provided
        if session and base_url:
            # Check if we need to fetch connection page for channel data
            has_channel_data = self._has_channel_tables(soup)
            if not has_channel_data:
                _LOGGER.debug("No channel tables found, fetching MotoConnection.asp for channel data")
                try:
                    conn_response = session.get(f"{base_url}/MotoConnection.asp", timeout=10)
                    if conn_response.status_code == 200:
                        conn_soup = BeautifulSoup(conn_response.text, "html.parser")
                        resources["/MotoConnection.asp"] = conn_soup
                        _LOGGER.debug("Fetched MotoConnection.asp (%d bytes)", len(conn_response.text))
                    else:
                        _LOGGER.warning("Failed to fetch MotoConnection.asp: status %d", conn_response.status_code)
                except Exception as e:
                    _LOGGER.error("Failed to fetch MotoConnection.asp: %s", e)

            # Check if we need software version from MotoHome.asp
            # Parse what we have so far to check for software_version
            temp_info = self._parse_system_info(soup)
            if "/MotoConnection.asp" in resources:
                conn_info = self._parse_system_info(resources["/MotoConnection.asp"])
                temp_info.update(conn_info)

            if not temp_info.get("software_version"):
                _LOGGER.debug("Software version not found, fetching MotoHome.asp")
                try:
                    home_response = session.get(f"{base_url}/MotoHome.asp", timeout=10)
                    if home_response.status_code == 200:
                        home_soup = BeautifulSoup(home_response.text, "html.parser")
                        resources["/MotoHome.asp"] = home_soup
                        _LOGGER.debug("Fetched MotoHome.asp (%d bytes)", len(home_response.text))
                except Exception as e:
                    _LOGGER.error("Failed to fetch MotoHome.asp: %s", e)

        return self.parse_resources(resources)

    def _has_channel_tables(self, soup: BeautifulSoup) -> bool:
        """Check if the soup contains channel data tables (not just system info tables).

        MotoHome.asp has moto-table-content tables with system info, but no channel data.
        MotoConnection.asp has moto-table-content tables WITH Pwr/SNR headers for channels.
        """
        tables = soup.find_all("table", class_="moto-table-content")
        for table in tables:
            headers = [
                th.text.strip()
                for th in table.find_all(["th", "td"], class_=["moto-param-header-s", "moto-param-header"])
            ]
            if self._is_downstream_table(headers):
                return True
        return False

    def _is_downstream_table(self, headers: list[str]) -> bool:
        """Check if table headers indicate a downstream channel table."""
        return any("Pwr" in h for h in headers) and any("SNR" in h for h in headers)

    def _filter_restart_values(
        self, power: float | None, snr: float | None, is_restarting: bool
    ) -> tuple[float | None, float | None]:
        """Filter out zero values during restart window."""
        if is_restarting:
            if power == 0:
                power = None
            if snr == 0:
                snr = None
        return power, snr

    def _parse_downstream_row(self, cols: list, is_restarting: bool) -> dict | None:
        """Parse a single downstream channel row.

        Table structure:
        Channel | Lock Status | Modulation | Channel ID | Freq (MHz) | Pwr | SNR | Corrected | Uncorrected
        cols[0]   cols[1]       cols[2]      cols[3]      cols[4]      [5]   [6]    [7]         [8]

        Note: Table may include a "Total" summary row at the end which is silently skipped.
        """
        if len(cols) < 9:
            return None

        # Skip summary/total rows (expected in MB7621 downstream tables)
        first_col = cols[0].text.strip().lower()
        if first_col in ("total", "totals"):
            _LOGGER.debug("Skipping summary row (label='%s')", cols[0].text.strip())
            return None

        try:
            # Channel ID is in column 3 (not column 0 which is just a row counter)
            channel_id = extract_number(cols[3].text)
            if channel_id is None:
                _LOGGER.debug(
                    "Skipping row - could not extract channel_id (col[3]='%s', row label='%s')",
                    cols[3].text.strip(),
                    cols[0].text.strip(),
                )
                return None

            freq_mhz = extract_float(cols[4].text)
            freq_hz = freq_mhz * 1_000_000 if freq_mhz is not None else None

            power = extract_float(cols[5].text)
            snr = extract_float(cols[6].text)
            _LOGGER.debug("Ch %s: Raw Power=%s, Raw SNR=%s", channel_id, power, snr)

            power, snr = self._filter_restart_values(power, snr, is_restarting)

            # DOCSIS 3.0 downstream is always SC-QAM (no OFDM)
            modulation = cols[2].text.strip()
            channel_data = {
                "channel_id": str(channel_id),
                "frequency": freq_hz,
                "power": power,
                "snr": snr,
                "corrected": extract_number(cols[7].text),
                "uncorrected": extract_number(cols[8].text),
                "modulation": modulation,
                "channel_type": "qam",  # DOCSIS 3.0 = SC-QAM only
            }
            _LOGGER.debug("Parsed downstream channel: %s", channel_data)
            return channel_data
        except Exception as e:
            _LOGGER.error("Error parsing downstream channel row: %s", e)
            return None

    def _parse_downstream(self, soup: BeautifulSoup, system_info: dict) -> list[dict]:
        """Parse downstream channel data."""
        uptime_seconds = parse_uptime_to_seconds(system_info.get("system_uptime", ""))
        is_restarting = uptime_seconds is not None and uptime_seconds < RESTART_WINDOW_SECONDS
        _LOGGER.debug(
            "Uptime: %s, Seconds: %s, Restarting: %s", system_info.get("system_uptime"), uptime_seconds, is_restarting
        )

        channels = []
        try:
            tables_found = soup.find_all("table", class_="moto-table-content")
            _LOGGER.debug("Found %s tables with class 'moto-table-content'", len(tables_found))

            for table in tables_found:
                headers = [
                    th.text.strip()
                    for th in table.find_all(["th", "td"], class_=["moto-param-header-s", "moto-param-header"])
                ]
                _LOGGER.debug("Table headers found: %s", headers)

                if self._is_downstream_table(headers):
                    rows = table.find_all("tr")[1:]
                    _LOGGER.debug("Found downstream table with %s rows", len(rows))

                    for row in rows:
                        cols = row.find_all("td")
                        channel_data = self._parse_downstream_row(cols, is_restarting)
                        if channel_data:
                            channels.append(channel_data)
                    break
        except Exception as e:
            _LOGGER.error("Error parsing downstream channels: %s", e)

        _LOGGER.debug("Parsed %s downstream channels", len(channels))
        return channels

    def _parse_upstream(self, soup: BeautifulSoup, system_info: dict) -> list[dict]:
        """Parse upstream channel data.

        Table structure:
        Channel | Lock Status | Channel Type | Channel ID | Symb. Rate | Freq (MHz) | Pwr
        cols[0]   cols[1]       cols[2]        cols[3]      cols[4]      cols[5]      cols[6]
        """
        uptime_seconds = parse_uptime_to_seconds(system_info.get("system_uptime", ""))
        is_restarting = uptime_seconds is not None and uptime_seconds < RESTART_WINDOW_SECONDS
        _LOGGER.debug(
            "Uptime: %s, Seconds: %s, Restarting: %s", system_info.get("system_uptime"), uptime_seconds, is_restarting
        )
        channels = []
        try:
            for table in soup.find_all("table", class_="moto-table-content"):
                headers = [
                    th.text.strip()
                    for th in table.find_all(["th", "td"], class_=["moto-param-header-s", "moto-param-header"])
                ]
                if any("Symb. Rate" in h for h in headers):
                    rows = table.find_all("tr")[1:]
                    _LOGGER.debug("Found upstream table with %s rows", len(rows))
                    for row in rows:
                        cols = row.find_all("td")
                        if len(cols) >= 7:
                            try:
                                # Channel ID is in column 3 (not column 0 which is just a row counter)
                                channel_id = extract_number(cols[3].text)
                                if channel_id is None:
                                    _LOGGER.debug("Skipping row - could not extract channel_id from: %s", cols[3].text)
                                    continue

                                lock_status = cols[1].text.strip()
                                if "not locked" in lock_status.lower():
                                    _LOGGER.debug(
                                        "Skipping channel %s - not locked (status: %s)", channel_id, lock_status
                                    )
                                    continue

                                freq_mhz = extract_float(cols[5].text)
                                freq_hz = freq_mhz * 1_000_000 if freq_mhz is not None else None

                                power = extract_float(cols[6].text)
                                _LOGGER.debug("Ch %s: Raw Power=%s", channel_id, power)

                                if is_restarting and power == 0:
                                    power = None

                                # cols[2] is "Channel Type" (e.g., "ATDMA"), not modulation
                                channel_type = cols[2].text.strip().lower()
                                channel_data = {
                                    "channel_id": str(channel_id),
                                    "frequency": freq_hz,
                                    "power": power,
                                    "modulation": channel_type.upper(),  # Use channel type as modulation
                                    "channel_type": channel_type,  # Set channel_type explicitly
                                }
                                _LOGGER.debug("Parsed upstream channel: %s", channel_data)
                                channels.append(channel_data)
                            except Exception as e:
                                _LOGGER.error("Error parsing upstream channel row: %s", e)
                                continue
                    break
        except Exception as e:
            _LOGGER.error("Error parsing upstream channels: %s", e)

        _LOGGER.debug("Parsed %s upstream channels", len(channels))
        return channels

    def _parse_system_info(self, soup: BeautifulSoup) -> dict:
        """Parse system information."""
        info = {}
        try:
            hw_version_tag = soup.find("td", text=lambda t: bool(t and "Hardware Version" in t))
            if hw_version_tag:
                hw_version_value = hw_version_tag.find_next_sibling("td")
                if hw_version_value:
                    info["hardware_version"] = hw_version_value.text.strip()
            else:
                _LOGGER.debug("Hardware Version tag not found in HTML")

            sw_version_tag = soup.find("td", text=lambda t: bool(t and "Software Version" in t))
            if sw_version_tag:
                sw_version_value = sw_version_tag.find_next_sibling("td")
                if sw_version_value:
                    info["software_version"] = sw_version_value.text.strip()
            else:
                _LOGGER.debug("Software Version tag not found in HTML")

            uptime_tag = soup.find("td", text=lambda t: bool(t and "System Up Time" in t))
            if uptime_tag:
                uptime_value = uptime_tag.find_next_sibling("td")
                if uptime_value:
                    info["system_uptime"] = uptime_value.text.strip()
                    _LOGGER.debug("Found uptime: %s", info["system_uptime"])
            else:
                _LOGGER.debug("System Up Time tag not found in HTML")
        except Exception as e:
            _LOGGER.error("Error parsing system info: %s", e)

        return info

    def restart(self, session, base_url) -> bool:
        """Restart the modem."""
        try:
            security_url = f"{base_url}/MotoSecurity.asp"
            _LOGGER.debug("Accessing security page: %s", security_url)
            security_response = session.get(security_url, timeout=10)

            if security_response.status_code != 200:
                _LOGGER.error("Failed to access security page: %s", security_response.status_code)
                return False

            restart_url = f"{base_url}/goform/MotoSecurity"
            _LOGGER.info("Sending restart command to %s", restart_url)

            restart_data = {
                "UserId": "",
                "OldPassword": "",
                "NewUserId": "",
                "Password": "",
                "PasswordReEnter": "",
                "MotoSecurityAction": "1",
            }
            response = session.post(restart_url, data=restart_data, timeout=10)
            _LOGGER.debug("Restart response: status=%s, content_length=%s", response.status_code, len(response.text))

            if response.status_code == 200:
                _LOGGER.info("Restart command sent successfully")
                return True
            else:
                _LOGGER.error("Restart failed with status code: %s", response.status_code)
                return False

        except ConnectionResetError:
            _LOGGER.info("Restart command sent successfully (connection reset by rebooting modem)")
            return True
        except Exception as e:
            if "Connection aborted" in str(e) or "Connection reset" in str(e):
                _LOGGER.info("Restart command sent successfully (connection reset by rebooting modem)")
                return True
            _LOGGER.error("Error sending restart command: %s", e)
            return False
