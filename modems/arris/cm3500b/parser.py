"""Parser for ARRIS CM3500B cable modem.

The ARRIS CM3500B is a DOCSIS 3.1 / EuroDOCSIS 3.0 cable modem.

Key pages:
- /cgi-bin/status_cgi: DOCSIS channel data (REQUIRED for parsing, auth required)
- /cgi-bin/vers_cgi: Hardware/firmware version info
- /cgi-bin/login_cgi: Login page

Authentication: Form-based POST to /cgi-bin/login_cgi
- Username field: username
- Password field: password
- Session: Cookie-based (credential cookie)

Channel data:
- 24+ downstream QAM channels (256QAM)
- 2 downstream OFDM channels (4K FFT, DOCSIS 3.1)
- 4 upstream QAM channels (ATDMA)
- 1 upstream OFDMA channel (2K FFT, DOCSIS 3.1)

Related: Issue #73 (ARRIS CM3500B Support Request)
Contributor: @ChBi89
"""

from __future__ import annotations

import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.base_parser import ModemParser
from custom_components.cable_modem_monitor.lib.utils import extract_float, extract_number

_LOGGER = logging.getLogger(__name__)


class ArrisCM3500BParser(ModemParser):
    """Parser for ARRIS CM3500B cable modem."""

    # Auth handled by AuthDiscovery (v3.12.0+) - no auth_config needed
    # URL patterns now in modem.yaml pages config

    def login(self, session, base_url, username, password) -> tuple[bool, str | None]:
        """Perform login using form-based authentication.

        The CM3500B requires a POST to /cgi-bin/login_cgi with username/password.
        On success, a 'credential' cookie is set for the session.

        Args:
            session: Requests session
            base_url: Modem base URL
            username: Username for authentication
            password: Password for authentication

        Returns:
            tuple[bool, str | None]: (success, authenticated_html)
        """
        if not username or not password:
            _LOGGER.debug("CM3500B: No credentials provided, skipping login")
            return (True, None)

        try:
            # Submit login form
            login_url = f"{base_url}/cgi-bin/login_cgi"
            _LOGGER.debug("CM3500B: Submitting login to %s", login_url)

            session.post(
                login_url,
                data={"username": username, "password": password},
                timeout=10,
                verify=False,  # CM3500B uses self-signed HTTPS cert
            )

            # Check if login was successful by verifying we can access status page
            status_response = session.get(
                f"{base_url}/cgi-bin/status_cgi",
                timeout=10,
                verify=False,
            )

            if status_response.status_code == 200 and "Downstream" in status_response.text:
                _LOGGER.debug("CM3500B: Login successful")
                return (True, status_response.text)

            _LOGGER.warning("CM3500B: Login failed - status page not accessible")
            return (False, None)

        except Exception as e:
            _LOGGER.error("CM3500B: Login exception: %s", e, exc_info=True)
            return (False, None)

    def parse_resources(self, resources: dict[str, Any]) -> dict:
        """Parse all data from pre-fetched resources."""
        # Get soup from resources
        soup = resources.get("/")
        if soup is None:
            for value in resources.values():
                if isinstance(value, BeautifulSoup):
                    soup = value
                    break

        if soup is None:
            return {"downstream": [], "upstream": [], "system_info": {}}

        return self._parse_soup(soup)

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Parse all data from the modem (legacy interface)."""
        return self._parse_soup(soup)

    def _parse_soup(self, soup: BeautifulSoup) -> dict:
        """Parse all data from BeautifulSoup object."""
        downstream_channels = self._parse_downstream_qam(soup)
        downstream_ofdm = self._parse_downstream_ofdm(soup)
        upstream_channels = self._parse_upstream_qam(soup)
        upstream_ofdm = self._parse_upstream_ofdm(soup)
        system_info = self._parse_system_info(soup)

        # Combine OFDM channels with regular channels
        downstream_channels.extend(downstream_ofdm)
        upstream_channels.extend(upstream_ofdm)

        return {
            "downstream": downstream_channels,
            "upstream": upstream_channels,
            "system_info": system_info,
        }

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """Detect if this is an ARRIS CM3500B modem."""
        # Check body class
        body = soup.find("body", class_="CM3500")
        if body:
            return True

        # Check for model in Hardware Model field
        model_td = soup.find("td", string="Hardware Model")  # type: ignore[call-overload]
        if model_td:
            value_td = model_td.find_next_sibling("td")
            if value_td and "CM3500" in value_td.text:
                return True

        # Check for model string in page
        return bool(soup.find(string=lambda s: s and "CM3500B" in str(s)))

    def _parse_downstream_qam(self, soup: BeautifulSoup) -> list[dict]:
        """Parse downstream QAM channel data.

        Table structure (after h4 "Downstream QAM"):
        | | DCID | Freq | Power | SNR | Modulation | Octets | Correcteds | Uncorrectables |
        """
        channels: list[dict[str, Any]] = []

        # Find the Downstream QAM header
        header = soup.find("h4", string=re.compile(r"Downstream QAM", re.IGNORECASE))  # type: ignore[call-overload]
        if not header:
            _LOGGER.debug("CM3500B: Downstream QAM header not found")
            return channels

        # Find the table following the header
        table = header.find_next("table")
        if not table:
            return channels

        rows = table.find_all("tr")
        if len(rows) < 2:
            return channels

        # Skip header row
        for row in rows[1:]:
            cells = row.find_all("td")
            if len(cells) < 9:
                continue

            # First cell contains "Downstream N"
            label = cells[0].text.strip()
            if not label.startswith("Downstream"):
                continue

            # Parse frequency (format: "570.00 MHz")
            freq_text = cells[2].text.strip()
            freq_hz = self._parse_frequency_mhz(freq_text)

            channel: dict[str, Any] = {
                "channel_id": cells[1].text.strip(),  # DCID
                "frequency": freq_hz,
                "power": extract_float(cells[3].text),  # dBmV
                "snr": extract_float(cells[4].text),  # dB
                "modulation": cells[5].text.strip(),
                "corrected": extract_number(cells[7].text),
                "uncorrected": extract_number(cells[8].text),
            }

            if not channel["channel_id"] or channel["channel_id"] == "----":
                continue

            channels.append(channel)
            _LOGGER.debug("Parsed CM3500B downstream QAM channel %s", channel["channel_id"])

        return channels

    def _parse_downstream_ofdm(self, soup: BeautifulSoup) -> list[dict]:
        """Parse downstream OFDM channel data.

        Table structure (after h4 "Downstream OFDM"):
        | | FFT Type | Width(MHz) | Subcarriers | First(MHz) | Last(MHz) | MER Pilot | MER PLC | MER Data |
        """
        channels: list[dict[str, Any]] = []

        header = soup.find("h4", string=re.compile(r"Downstream OFDM", re.IGNORECASE))  # type: ignore[call-overload]
        if not header:
            _LOGGER.debug("CM3500B: Downstream OFDM header not found")
            return channels

        table = header.find_next("table")
        if not table:
            return channels

        # Find tbody for data rows (skip thead)
        tbody = table.find("tbody")
        if not tbody:
            return channels

        rows = tbody.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 9:
                continue

            label = cells[0].text.strip()
            if not label.startswith("Downstream"):
                continue

            # Extract channel number from label
            match = re.search(r"Downstream\s*(\d+)", label)
            channel_id = match.group(1) if match else label

            # Calculate center frequency from first/last subcarrier
            first_freq = extract_float(cells[4].text)
            last_freq = extract_float(cells[5].text)
            center_freq = None
            if first_freq is not None and last_freq is not None:
                center_freq = int(((first_freq + last_freq) / 2) * 1_000_000)

            channel: dict[str, Any] = {
                "channel_id": f"OFDM-{channel_id}",
                "is_ofdm": True,
                "fft_type": cells[1].text.strip(),
                "channel_width": extract_float(cells[2].text),
                "active_subcarriers": extract_number(cells[3].text),
                "first_subcarrier_freq": first_freq,
                "last_subcarrier_freq": last_freq,
                "frequency": center_freq,
                "snr": extract_float(cells[8].text),  # MER Data
                "modulation": "OFDM",
            }

            channels.append(channel)
            _LOGGER.debug("Parsed CM3500B downstream OFDM channel %s", channel["channel_id"])

        return channels

    def _parse_upstream_qam(self, soup: BeautifulSoup) -> list[dict]:
        """Parse upstream QAM channel data.

        Table structure (after h4 "Upstream QAM"):
        | | UCID | Freq | Power | Channel Type | Symbol Rate | Modulation |
        """
        channels: list[dict[str, Any]] = []

        header = soup.find("h4", string=re.compile(r"Upstream QAM", re.IGNORECASE))  # type: ignore[call-overload]
        if not header:
            _LOGGER.debug("CM3500B: Upstream QAM header not found")
            return channels

        table = header.find_next("table")
        if not table:
            return channels

        rows = table.find_all("tr")
        if len(rows) < 2:
            return channels

        # Skip header row
        for row in rows[1:]:
            cells = row.find_all("td")
            if len(cells) < 7:
                continue

            label = cells[0].text.strip()
            if not label.startswith("Upstream"):
                continue

            freq_text = cells[2].text.strip()
            freq_hz = self._parse_frequency_mhz(freq_text)

            # Parse symbol rate (format: "5120 kSym/s")
            symbol_rate_text = cells[5].text.strip()
            symbol_rate = extract_number(symbol_rate_text)

            channel: dict[str, Any] = {
                "channel_id": cells[1].text.strip(),  # UCID
                "frequency": freq_hz,
                "power": extract_float(cells[3].text),  # dBmV
                "channel_type": cells[4].text.strip(),
                "symbol_rate": symbol_rate,
                "modulation": cells[6].text.strip(),
            }

            if not channel["channel_id"] or channel["channel_id"] == "----":
                continue

            channels.append(channel)
            _LOGGER.debug("Parsed CM3500B upstream QAM channel %s", channel["channel_id"])

        return channels

    def _parse_upstream_ofdm(self, soup: BeautifulSoup) -> list[dict]:
        """Parse upstream OFDM (OFDMA) channel data.

        Table structure (after h4 "Upstream OFDM"):
        Note: CM3500B firmware has incomplete headers. Actual data has 9 columns:
        | | FFT | Width | Subcarriers | FirstIdx | LastIdx | First(MHz) | Last(MHz) | TxPower |

        The header only shows 7 columns (missing FirstIdx/LastIdx labels).
        """
        channels: list[dict[str, Any]] = []

        header = soup.find("h4", string=re.compile(r"Upstream OFDM", re.IGNORECASE))  # type: ignore[call-overload]
        if not header:
            _LOGGER.debug("CM3500B: Upstream OFDM header not found")
            return channels

        table = header.find_next("table")
        if not table:
            return channels

        rows = table.find_all("tr")
        if len(rows) < 2:
            return channels

        # Skip header row
        for row in rows[1:]:
            cells = row.find_all("td")
            if len(cells) < 7:
                continue

            label = cells[0].text.strip()
            if not label.startswith("Upstream"):
                continue

            match = re.search(r"Upstream\s*(\d+)", label)
            channel_id = match.group(1) if match else label

            # CM3500B firmware bug: data has 9 cells but header has 7
            # Cells 4,5 are subcarrier indices; 6,7 are actual frequencies in MHz
            if len(cells) >= 9:
                # Firmware with extra columns (indices + frequencies)
                first_freq = extract_float(cells[6].text)
                last_freq = extract_float(cells[7].text)
                power = extract_float(cells[8].text)
            else:
                # Standard layout matching header
                first_freq = extract_float(cells[4].text)
                last_freq = extract_float(cells[5].text)
                power = extract_float(cells[6].text)

            center_freq = None
            if first_freq is not None and last_freq is not None:
                center_freq = int(((first_freq + last_freq) / 2) * 1_000_000)

            channel: dict[str, Any] = {
                "channel_id": f"OFDMA-{channel_id}",
                "is_ofdm": True,
                "fft_type": cells[1].text.strip(),
                "channel_width": extract_float(cells[2].text),
                "active_subcarriers": extract_number(cells[3].text),
                "first_subcarrier_freq": first_freq,
                "last_subcarrier_freq": last_freq,
                "frequency": center_freq,
                "power": power,
                "modulation": "OFDMA",
            }

            channels.append(channel)
            _LOGGER.debug("Parsed CM3500B upstream OFDM channel %s", channel["channel_id"])

        return channels

    def _parse_system_info(self, soup: BeautifulSoup) -> dict:
        """Parse system information from status page."""
        info: dict[str, Any] = {}

        # Parse uptime (format: "0 d:  7 h: 40 m")
        uptime_td = soup.find("td", string=re.compile(r"System Uptime", re.IGNORECASE))  # type: ignore[call-overload]
        if uptime_td:
            value_td = uptime_td.find_next_sibling("td")
            if value_td:
                info["system_uptime"] = value_td.text.strip()
                _LOGGER.debug("CM3500B uptime: %s", info["system_uptime"])

        # Parse CM status
        status_td = soup.find("td", string=re.compile(r"CM Status", re.IGNORECASE))  # type: ignore[call-overload]
        if status_td:
            value_td = status_td.find_next_sibling("td")
            if value_td:
                info["cm_status"] = value_td.text.strip()

        # Parse current time
        time_td = soup.find("td", string=re.compile(r"Time and Date", re.IGNORECASE))  # type: ignore[call-overload]
        if time_td:
            value_td = time_td.find_next_sibling("td")
            if value_td:
                info["current_time"] = value_td.text.strip()

        # Parse hardware model
        model_td = soup.find("td", string="Hardware Model")  # type: ignore[call-overload]
        if model_td:
            value_td = model_td.find_next_sibling("td")
            if value_td:
                info["hardware_version"] = value_td.text.strip()

        return info

    def _parse_frequency_mhz(self, freq_text: str) -> int | None:
        """Parse frequency from MHz string to Hz.

        Args:
            freq_text: Frequency string like "570.00 MHz"

        Returns:
            Frequency in Hz, or None if parsing failed
        """
        try:
            freq_mhz = float(freq_text.replace("MHz", "").strip())
            return int(freq_mhz * 1_000_000)
        except (ValueError, AttributeError):
            return None
