"""Parser for Motorola MB series cable modems."""
import logging
import base64
from bs4 import BeautifulSoup
from ..base_parser import ModemParser
from custom_components.cable_modem_monitor.lib.utils import extract_number, extract_float
from custom_components.cable_modem_monitor.core.auth_config import FormAuthConfig
from custom_components.cable_modem_monitor.core.authentication import AuthStrategyType

_LOGGER = logging.getLogger(__name__)

# During modem restart, power readings may be temporarily zero.
# Ignore zero power readings during the first 5 minutes after boot.
RESTART_WINDOW_SECONDS = 300


class MotorolaGenericParser(ModemParser):
    """Parser for Motorola MB series cable modems (MB7420, MB8600, etc.)."""

    name = "Motorola MB Series"
    manufacturer = "Motorola"
    models = ["MB7420", "MB8600", "MB8611"]
    priority = 50  # Generic fallback parser, try after model-specific parsers

    # New authentication configuration (declarative)
    # Motorola modems try both plain and Base64-encoded passwords
    auth_config = FormAuthConfig(
        strategy=AuthStrategyType.FORM_PLAIN_AND_BASE64,
        login_url="/goform/login",
        username_field="loginUsername",
        password_field="loginPassword",
        success_indicator="10000"  # Min response size indicates success
    )

    url_patterns = [
        {"path": "/MotoConnection.asp", "auth_method": "form", "auth_required": True},
        {"path": "/MotoHome.asp", "auth_method": "form", "auth_required": True},
    ]

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """Detect if this is a Motorola MB series modem."""
        return bool(soup.title and soup.title.string and "Motorola Cable Modem" in soup.title.string)

    def login(self, session, base_url, username, password) -> tuple[bool, str | None]:
        """Log in to the modem using form-based authentication.

        Returns:
            tuple: (success: bool, authenticated_html: str)

        Security Note:
            Some Motorola modems (e.g., MB7621) require Base64-encoded passwords.
            IMPORTANT: Base64 is NOT encryption - it is merely encoding and provides
            NO security against interception or attacks. The password is still sent
            in an easily reversible format. This is a modem firmware limitation.
            Always use HTTPS connections when possible to protect credentials in transit.
        """
        if not username or not password:
            _LOGGER.debug("No credentials provided, skipping login")
            return True, None

        login_url = f"{base_url}/goform/login"

        # Try plain password first, then Base64-encoded (MB7621 requires Base64)
        # SECURITY WARNING: Base64 is NOT encryption! It's just encoding.
        # The password is still transmitted in an easily reversible format.
        passwords_to_try = [
            password,  # Plain password
            base64.b64encode(password.encode("utf-8")).decode("utf-8"),  # Base64-encoded (not secure)
        ]

        for attempt, pwd in enumerate(passwords_to_try, 1):
            login_data = {
                "loginUsername": username,
                "loginPassword": pwd,
            }
            pwd_type = "plain" if attempt == 1 else "Base64-encoded"
            # Security: Do not log usernames or any credential information
            _LOGGER.info("Attempting login to %s (password encoding: %s)", login_url, pwd_type)

            # Security: Disable auto-redirects and validate manually
            response = session.post(login_url, data=login_data, timeout=10, allow_redirects=True)
            _LOGGER.debug("Login response: status=%s, url=%s", response.status_code, response.url)

            # Security check: Validate redirect stayed on same host or local network
            from urllib.parse import urlparse
            import ipaddress

            if response.url != login_url:
                response_parsed = urlparse(response.url)
                login_parsed = urlparse(login_url)

                # Allow redirects if hostnames match
                if response_parsed.hostname != login_parsed.hostname:
                    # For local network devices, allow redirects within private IP ranges
                    # This handles cases where modems redirect from IP to hostname or between IPs
                    try:
                        # Try to parse as IP addresses
                        login_ip = ipaddress.ip_address(login_parsed.hostname)
                        response_ip = ipaddress.ip_address(response_parsed.hostname)

                        # If both are private/local IPs, allow the redirect (trusted local network)
                        if login_ip.is_private and response_ip.is_private:
                            _LOGGER.debug("Allowing redirect within private network: %s -> %s",
                                        login_parsed.hostname, response_parsed.hostname)
                        else:
                            # One or both are public IPs - enforce strict matching
                            _LOGGER.error("Motorola: Security violation - redirect to different public host: %s", response.url)
                            return False, None
                    except ValueError:
                        # Not IP addresses (hostnames) - enforce strict matching for security
                        _LOGGER.error("Motorola: Security violation - redirect to different host: %s (from %s)",
                                    response_parsed.hostname, login_parsed.hostname)
                        return False, None

            test_response = session.get(f"{base_url}/MotoConnection.asp", timeout=10)
            _LOGGER.debug("Login verification: test page status=%s, length=%s", test_response.status_code, len(test_response.text))

            # Check for successful authentication - look for actual content, not login page
            if test_response.status_code == 200 and len(test_response.text) > 10000:
                _LOGGER.info("Login successful using %s password (got %s bytes)", pwd_type, len(test_response.text))
                return True, test_response.text

        _LOGGER.error("Login failed with both plain and Base64-encoded passwords")
        return False, None

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Parse all data from the modem."""
        # Parse system info first to get uptime
        system_info = self._parse_system_info(soup)

        # If software version not found and we have session/base_url, fetch MotoHome.asp
        if not system_info.get("software_version") and session and base_url:
            try:
                _LOGGER.debug("Software version not found on connection page, fetching MotoHome.asp")
                home_response = session.get(f"{base_url}/MotoHome.asp", timeout=10)
                if home_response.status_code == 200:
                    home_soup = BeautifulSoup(home_response.text, "html.parser")
                    home_info = self._parse_system_info(home_soup)
                    system_info.update(home_info)
                    _LOGGER.debug("Fetched system info from MotoHome.asp: %s", home_info)
            except Exception as e:
                _LOGGER.error("Failed to fetch system info from MotoHome.asp: %s", e)

        downstream_channels = self._parse_downstream(soup, system_info)
        upstream_channels = self._parse_upstream(soup, system_info)

        _LOGGER.debug("Final system_info being returned: %s", system_info)
        return {
            "downstream": downstream_channels,
            "upstream": upstream_channels,
            "system_info": system_info,
        }

    def _parse_downstream(self, soup: BeautifulSoup, system_info: dict) -> list[dict]:
        """Parse downstream channel data from Motorola MB modem."""
        from custom_components.cable_modem_monitor.lib.utils import parse_uptime_to_seconds

        uptime_seconds = parse_uptime_to_seconds(system_info.get("system_uptime", ""))
        is_restarting = uptime_seconds is not None and uptime_seconds < RESTART_WINDOW_SECONDS
        _LOGGER.debug("Uptime: %s, Seconds: %s, Restarting: %s", system_info.get('system_uptime'), uptime_seconds, is_restarting)

        channels = []
        try:
            tables_found = soup.find_all("table", class_="moto-table-content")
            _LOGGER.debug("Found %s tables with class 'moto-table-content'", len(tables_found))

            for table in tables_found:
                headers = [th.text.strip() for th in table.find_all(["th", "td"], class_=["moto-param-header-s", "moto-param-header"])]
                _LOGGER.debug("Table headers found: %s", headers)

                if any("Pwr" in h for h in headers) and any("SNR" in h for h in headers):
                    rows = table.find_all("tr")[1:]
                    _LOGGER.debug("Found downstream table with %s rows", len(rows))

                    for row in rows:
                        cols = row.find_all("td")
                        if len(cols) >= 9:
                            try:
                                channel_id = extract_number(cols[0].text)
                                if channel_id is None:
                                    _LOGGER.debug("Skipping row - could not extract channel_id from: %s", cols[0].text)
                                    continue

                                freq_mhz = extract_float(cols[4].text)
                                freq_hz = freq_mhz * 1_000_000 if freq_mhz is not None else None
                                
                                power = extract_float(cols[5].text)
                                snr = extract_float(cols[6].text)
                                _LOGGER.debug("Ch %s: Raw Power=%s, Raw SNR=%s", channel_id, power, snr)

                                # During restart window, filter out zero values which are typically invalid
                                if is_restarting:
                                    if power == 0:
                                        power = None
                                    if snr == 0:
                                        snr = None

                                channel_data = {
                                    "channel_id": str(channel_id),
                                    "frequency": freq_hz,
                                    "power": power,
                                    "snr": snr,
                                    "corrected": extract_number(cols[7].text),
                                    "uncorrected": extract_number(cols[8].text),
                                    "modulation": cols[2].text.strip(),
                                }
                                _LOGGER.debug("Parsed downstream channel: %s", channel_data)
                                channels.append(channel_data)
                            except Exception as e:
                                _LOGGER.error("Error parsing downstream channel row: %s", e)
                                continue
                    break
        except Exception as e:
            _LOGGER.error("Error parsing downstream channels: %s", e)

        _LOGGER.info("Parsed %s downstream channels", len(channels))
        return channels

    def _parse_upstream(self, soup: BeautifulSoup, system_info: dict) -> list[dict]:
        """Parse upstream channel data from Motorola MB modem."""
        from custom_components.cable_modem_monitor.lib.utils import parse_uptime_to_seconds

        uptime_seconds = parse_uptime_to_seconds(system_info.get("system_uptime", ""))
        is_restarting = uptime_seconds is not None and uptime_seconds < RESTART_WINDOW_SECONDS
        _LOGGER.debug("Uptime: %s, Seconds: %s, Restarting: %s", system_info.get('system_uptime'), uptime_seconds, is_restarting)
        channels = []
        try:
            for table in soup.find_all("table", class_="moto-table-content"):
                headers = [th.text.strip() for th in table.find_all(["th", "td"], class_=["moto-param-header-s", "moto-param-header"])]
                if any("Symb. Rate" in h for h in headers):
                    rows = table.find_all("tr")[1:]
                    _LOGGER.debug("Found upstream table with %s rows", len(rows))
                    for row in rows:
                        cols = row.find_all("td")
                        if len(cols) >= 7:
                            try:
                                channel_id = extract_number(cols[0].text)
                                if channel_id is None:
                                    _LOGGER.debug("Skipping row - could not extract channel_id from: %s", cols[0].text)
                                    continue

                                lock_status = cols[1].text.strip()
                                if "not locked" in lock_status.lower():
                                    _LOGGER.debug("Skipping channel %s - not locked (status: %s)", channel_id, lock_status)
                                    continue

                                freq_mhz = extract_float(cols[5].text)
                                freq_hz = freq_mhz * 1_000_000 if freq_mhz is not None else None

                                power = extract_float(cols[6].text)
                                _LOGGER.debug("Ch %s: Raw Power=%s", channel_id, power)

                                # During restart window, filter out zero power which is typically invalid
                                if is_restarting and power == 0:
                                    power = None

                                channel_data = {
                                    "channel_id": str(channel_id),
                                    "frequency": freq_hz,
                                    "power": power,
                                    "modulation": cols[2].text.strip(),
                                }
                                _LOGGER.debug("Parsed upstream channel: %s", channel_data)
                                channels.append(channel_data)
                            except Exception as e:
                                _LOGGER.error("Error parsing upstream channel row: %s", e)
                                continue
                    break
        except Exception as e:
            _LOGGER.error("Error parsing upstream channels: %s", e)

        _LOGGER.info("Parsed %s upstream channels", len(channels))
        return channels

    def _parse_system_info(self, soup: BeautifulSoup) -> dict:
        """Parse system information from Motorola MB modem."""
        info = {}
        try:
            # Use text= instead of string= for BS4 compatibility with lambda functions
            sw_version_tag = soup.find("td", text=lambda t: t and "Software Version" in t)
            if sw_version_tag:
                info["software_version"] = sw_version_tag.find_next_sibling("td").text.strip()
            else:
                _LOGGER.debug("Software Version tag not found in HTML")

            uptime_tag = soup.find("td", text=lambda t: t and "System Up Time" in t)
            if uptime_tag:
                info["system_uptime"] = uptime_tag.find_next_sibling("td").text.strip()
                _LOGGER.debug("Found uptime: %s", info['system_uptime'])
            else:
                _LOGGER.debug("System Up Time tag not found in HTML")
        except Exception as e:
            _LOGGER.error("Error parsing system info: %s", e)

        return info

    def restart(self, session, base_url) -> bool:
        """Restart the Motorola MB modem."""
        try:
            # First, access the security page to ensure we're authenticated
            security_url = f"{base_url}/MotoSecurity.asp"
            _LOGGER.debug("Accessing security page: %s", security_url)
            security_response = session.get(security_url, timeout=10)

            if security_response.status_code != 200:
                _LOGGER.error("Failed to access security page: %s", security_response.status_code)
                return False

            # Now send the restart command to the correct endpoint
            restart_url = f"{base_url}/goform/MotoSecurity"
            _LOGGER.info("Sending restart command to %s", restart_url)

            # Use the exact POST data that the web interface sends
            # MotoSecurityAction=1 triggers the reboot
            restart_data = {
                "UserId": "",
                "OldPassword": "",
                "NewUserId": "",
                "Password": "",
                "PasswordReEnter": "",
                "MotoSecurityAction": "1"
            }
            response = session.post(restart_url, data=restart_data, timeout=10)
            _LOGGER.debug("Restart response: status=%s, content_length=%s", response.status_code, len(response.text))

            # Motorola modems typically return 200 even when restart is initiated
            if response.status_code == 200:
                _LOGGER.info("Restart command sent successfully")
                return True
            else:
                _LOGGER.error("Restart failed with status code: %s", response.status_code)
                return False

        except ConnectionResetError:
            # Connection reset is expected - modem reboots immediately and drops connection
            _LOGGER.info("Restart command sent successfully (connection reset by rebooting modem)")
            return True
        except Exception as e:
            # Check if it's a connection abort/reset wrapped in another exception
            if "Connection aborted" in str(e) or "Connection reset" in str(e):
                _LOGGER.info("Restart command sent successfully (connection reset by rebooting modem)")
                return True
            _LOGGER.error("Error sending restart command: %s", e)
            return False