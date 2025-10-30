"""Parser for Motorola MB series cable modems."""
import logging
import base64
from bs4 import BeautifulSoup
from .base_parser import ModemParser
from ..utils import extract_number, extract_float

_LOGGER = logging.getLogger(__name__)


class MotorolaMBParser(ModemParser):
    """Parser for Motorola MB series cable modems (MB7420, MB7621, MB8600, etc.)."""

    name = "Motorola MB Series"
    manufacturer = "Motorola"
    models = ["MB7420", "MB7621", "MB8600", "MB8611"]

    url_patterns = [
        {"path": "/MotoConnection.asp", "auth_method": "form"},
        {"path": "/MotoHome.asp", "auth_method": "form"},
    ]

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """Detect if this is a Motorola MB series modem."""
        return "Motorola Cable Modem" in soup.title.string

    def login(self, session, base_url, username, password) -> tuple[bool, str]:
        """Log in to the modem using form-based authentication.

        Returns:
            tuple: (success: bool, authenticated_html: str)
        """
        if not username or not password:
            _LOGGER.debug("No credentials provided, skipping login")
            return True, None

        login_url = f"{base_url}/goform/login"

        ***REMOVED*** Try plain password first, then Base64-encoded (MB7621 requires Base64)
        passwords_to_try = [
            password,  ***REMOVED*** Plain password
            base64.b64encode(password.encode("utf-8")).decode("utf-8"),  ***REMOVED*** Base64-encoded
        ]

        for attempt, pwd in enumerate(passwords_to_try, 1):
            login_data = {
                "loginUsername": username,
                "loginPassword": pwd,
            }
            pwd_type = "plain" if attempt == 1 else "Base64-encoded"
            _LOGGER.info(f"Attempting login to {login_url} as user '{username}' (password: {pwd_type})")

            response = session.post(login_url, data=login_data, timeout=10, allow_redirects=True)
            _LOGGER.debug(f"Login response: status={response.status_code}, url={response.url}")

            test_response = session.get(f"{base_url}/MotoConnection.asp", timeout=10)
            _LOGGER.debug(f"Login verification: test page status={test_response.status_code}, length={len(test_response.text)}")

            ***REMOVED*** Check for successful authentication - look for actual content, not login page
            if test_response.status_code == 200 and len(test_response.text) > 10000:
                _LOGGER.info(f"Login successful using {pwd_type} password (got {len(test_response.text)} bytes)")
                return True, test_response.text

        _LOGGER.error("Login failed with both plain and Base64-encoded passwords")
        return False, None

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Parse all data from the modem."""
        downstream_channels = self._parse_downstream(soup)
        upstream_channels = self._parse_upstream(soup)

        ***REMOVED*** System info is on MotoConnection.asp page, try to parse from connection page first
        system_info = self._parse_system_info(soup)

        ***REMOVED*** If software version not found and we have session/base_url, fetch MotoHome.asp
        if not system_info.get("software_version") and session and base_url:
            try:
                _LOGGER.debug("Software version not found on connection page, fetching MotoHome.asp")
                home_response = session.get(f"{base_url}/MotoHome.asp", timeout=10)
                if home_response.status_code == 200:
                    home_soup = BeautifulSoup(home_response.text, "html.parser")
                    home_info = self._parse_system_info(home_soup)
                    system_info.update(home_info)
                    _LOGGER.debug(f"Fetched system info from MotoHome.asp: {home_info}")
            except Exception as e:
                _LOGGER.error(f"Failed to fetch system info from MotoHome.asp: {e}")

        _LOGGER.debug(f"Final system_info being returned: {system_info}")
        return {
            "downstream": downstream_channels,
            "upstream": upstream_channels,
            "system_info": system_info,
        }

    def _parse_downstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse downstream channel data from Motorola MB modem."""
        channels = []
        try:
            tables_found = soup.find_all("table", class_="moto-table-content")
            _LOGGER.debug(f"Found {len(tables_found)} tables with class 'moto-table-content'")

            for table in tables_found:
                headers = [th.text.strip() for th in table.find_all("td", class_="moto-param-header-s")]
                _LOGGER.debug(f"Table headers found: {headers}")

                if "Pwr (dBmV)" in headers and "SNR (dB)" in headers:
                    rows = table.find_all("tr")[1:]
                    _LOGGER.debug(f"Found downstream table with {len(rows)} rows")

                    for row in rows:
                        cols = row.find_all("td")
                        if len(cols) >= 9:
                            try:
                                channel_id = extract_number(cols[0].text)
                                if channel_id is None:
                                    _LOGGER.debug(f"Skipping row - could not extract channel_id from: {cols[0].text}")
                                    continue

                                freq_mhz = extract_float(cols[4].text)
                                freq_hz = freq_mhz * 1_000_000 if freq_mhz is not None else None

                                channel_data = {
                                    "channel_id": str(channel_id),
                                    "frequency": freq_hz,
                                    "power": extract_float(cols[5].text),
                                    "snr": extract_float(cols[6].text),
                                    "corrected": extract_number(cols[7].text),
                                    "uncorrected": extract_number(cols[8].text),
                                    "modulation": cols[2].text.strip(),
                                }
                                _LOGGER.debug(f"Parsed downstream channel: {channel_data}")
                                channels.append(channel_data)
                            except Exception as e:
                                _LOGGER.error(f"Error parsing downstream channel row: {e}")
                                continue
                    break
        except Exception as e:
            _LOGGER.error(f"Error parsing downstream channels: {e}")

        _LOGGER.info(f"Parsed {len(channels)} downstream channels")
        return channels

    def _parse_upstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse upstream channel data from Motorola MB modem."""
        channels = []
        try:
            for table in soup.find_all("table", class_="moto-table-content"):
                headers = [th.text.strip() for th in table.find_all("td", class_="moto-param-header-s")]
                if "Symb. Rate (Ksym/sec)" in headers:
                    rows = table.find_all("tr")[1:]
                    _LOGGER.debug(f"Found upstream table with {len(rows)} rows")
                    for row in rows:
                        cols = row.find_all("td")
                        if len(cols) >= 7:
                            try:
                                channel_id = extract_number(cols[0].text)
                                if channel_id is None:
                                    _LOGGER.debug(f"Skipping row - could not extract channel_id from: {cols[0].text}")
                                    continue

                                lock_status = cols[1].text.strip()
                                if "not locked" in lock_status.lower():
                                    _LOGGER.debug(f"Skipping channel {channel_id} - not locked (status: {lock_status})")
                                    continue

                                freq_mhz = extract_float(cols[5].text)
                                freq_hz = freq_mhz * 1_000_000 if freq_mhz is not None else None

                                channel_data = {
                                    "channel_id": str(channel_id),
                                    "frequency": freq_hz,
                                    "power": extract_float(cols[6].text),
                                    "modulation": cols[2].text.strip(),
                                }
                                _LOGGER.debug(f"Parsed upstream channel: {channel_data}")
                                channels.append(channel_data)
                            except Exception as e:
                                _LOGGER.error(f"Error parsing upstream channel row: {e}")
                                continue
                    break
        except Exception as e:
            _LOGGER.error(f"Error parsing upstream channels: {e}")

        _LOGGER.info(f"Parsed {len(channels)} upstream channels")
        return channels

    def _parse_system_info(self, soup: BeautifulSoup) -> dict:
        """Parse system information from Motorola MB modem."""
        info = {}
        try:
            ***REMOVED*** Use text= instead of string= for BS4 compatibility with lambda functions
            sw_version_tag = soup.find("td", text=lambda t: t and "Software Version" in t)
            if sw_version_tag:
                info["software_version"] = sw_version_tag.find_next_sibling("td").text.strip()
            else:
                _LOGGER.debug("Software Version tag not found in HTML")

            uptime_tag = soup.find("td", text=lambda t: t and "System Up Time" in t)
            if uptime_tag:
                info["system_uptime"] = uptime_tag.find_next_sibling("td").text.strip()
                _LOGGER.debug(f"Found uptime: {info['system_uptime']}")
            else:
                _LOGGER.debug("System Up Time tag not found in HTML")
        except Exception as e:
            _LOGGER.error(f"Error parsing system info: {e}")

        return info

    def restart(self, session, base_url) -> bool:
        """Restart the Motorola MB modem."""
        try:
            ***REMOVED*** First, access the security page to ensure we're authenticated
            security_url = f"{base_url}/MotoSecurity.asp"
            _LOGGER.debug(f"Accessing security page: {security_url}")
            security_response = session.get(security_url, timeout=10)

            if security_response.status_code != 200:
                _LOGGER.error(f"Failed to access security page: {security_response.status_code}")
                return False

            ***REMOVED*** Now send the restart command to the correct endpoint
            restart_url = f"{base_url}/goform/MotoSecurity"
            _LOGGER.info(f"Sending restart command to {restart_url}")

            ***REMOVED*** Use the exact POST data that the web interface sends
            ***REMOVED*** MotoSecurityAction=1 triggers the reboot
            restart_data = {
                "UserId": "",
                "OldPassword": "",
                "NewUserId": "",
                "Password": "",
                "PasswordReEnter": "",
                "MotoSecurityAction": "1"
            }
            response = session.post(restart_url, data=restart_data, timeout=10)
            _LOGGER.debug(f"Restart response: status={response.status_code}, content_length={len(response.text)}")

            ***REMOVED*** Motorola modems typically return 200 even when restart is initiated
            if response.status_code == 200:
                _LOGGER.info("Restart command sent successfully")
                return True
            else:
                _LOGGER.error(f"Restart failed with status code: {response.status_code}")
                return False

        except ConnectionResetError:
            ***REMOVED*** Connection reset is expected - modem reboots immediately and drops connection
            _LOGGER.info("Restart command sent successfully (connection reset by rebooting modem)")
            return True
        except Exception as e:
            ***REMOVED*** Check if it's a connection abort/reset wrapped in another exception
            if "Connection aborted" in str(e) or "Connection reset" in str(e):
                _LOGGER.info("Restart command sent successfully (connection reset by rebooting modem)")
                return True
            _LOGGER.error(f"Error sending restart command: {e}")
            return False