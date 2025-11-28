"""Parser for Netgear CM2000 (Nighthawk) cable modem.

The Netgear CM2000 is a DOCSIS 3.1 cable modem with multi-gigabit capability.

Firmware tested: V8.01.02
Hardware version: 1.01

Key pages:
- / or /index.htm: Login page (unauthenticated)
- /DocsisStatus.htm: DOCSIS channel data (REQUIRED for parsing, auth required)
- /Login.htm: Redirect target when unauthenticated

Authentication: Form-based POST to /goform/Login
- Username field: loginName
- Password field: loginPassword

Data format (InitTagValue):
- [10] Current System Time (e.g., "Tue Nov 25 12:48:02 2025")
- [14] System Up Time (e.g., "7 days 00:00:01")

Channel data:
- 32 downstream (DOCSIS 3.0, QAM256)
- 8 upstream (DOCSIS 3.0, ATDMA)
- OFDM downstream (DOCSIS 3.1)
- OFDM upstream (DOCSIS 3.1)

Related: Issue ***REMOVED***38 (Netgear CM2000 Support Request)
Contributor: @m4dh4tt3r-88
"""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.auth_config import FormAuthConfig
from custom_components.cable_modem_monitor.core.authentication import AuthStrategyType

from ..base_parser import ModemCapability, ModemParser

_LOGGER = logging.getLogger(__name__)


class NetgearCM2000Parser(ModemParser):
    """Parser for Netgear CM2000 (Nighthawk) cable modem."""

    name = "Netgear CM2000"
    manufacturer = "Netgear"
    models = ["CM2000"]
    priority = 50  ***REMOVED*** Standard priority

    ***REMOVED*** Verification status - auth confirmed, parsing fixes pending user verification
    verified = False  ***REMOVED*** Auth works, parsing fixes need user confirmation - Issue ***REMOVED***38
    verification_source = "https://github.com/kwschulz/cable_modem_monitor/issues/38 (@m4dh4tt3r-88)"

    ***REMOVED*** Device metadata
    release_date = "2020-08"
    docsis_version = "3.1"
    fixtures_path = "tests/parsers/netgear/fixtures/cm2000"

    ***REMOVED*** CM2000 uses form-based authentication
    auth_config = FormAuthConfig(
        strategy=AuthStrategyType.FORM_PLAIN,
        login_url="/goform/Login",
        username_field="loginName",
        password_field="loginPassword",
        success_indicator="DocsisStatus",  ***REMOVED*** Redirect or page content after login
    )

    ***REMOVED*** Capabilities - CM2000 provides full system info including uptime
    capabilities = {
        ModemCapability.DOWNSTREAM_CHANNELS,
        ModemCapability.UPSTREAM_CHANNELS,
        ModemCapability.OFDM_DOWNSTREAM,
        ModemCapability.OFDM_UPSTREAM,
        ModemCapability.SYSTEM_UPTIME,
        ModemCapability.LAST_BOOT_TIME,
        ModemCapability.CURRENT_TIME,
        ModemCapability.SOFTWARE_VERSION,
    }

    ***REMOVED*** URL patterns to try for modem data
    url_patterns = [
        {"path": "/", "auth_method": "form", "auth_required": False},
        {"path": "/index.htm", "auth_method": "form", "auth_required": False},
        {"path": "/DocsisStatus.htm", "auth_method": "form", "auth_required": True},
    ]

    def login(self, session, base_url, username, password) -> bool:
        """Perform login using form-based authentication with dynamic form ID.

        The CM2000 login form includes a dynamic ID parameter in the form action:
            <form action="/goform/Login?id=XXXXXXXXXX">

        This ID must be extracted from the login page and included in the POST.

        Args:
            session: Requests session
            base_url: Modem base URL
            username: Username for authentication
            password: Password for authentication

        Returns:
            True if login successful
        """
        if not username or not password:
            _LOGGER.debug("CM2000: No credentials provided, skipping login")
            return True

        try:
            ***REMOVED*** Step 1: Extract login URL from the login page
            login_url = self._extract_login_url(session, base_url)
            if login_url is None:
                return False

            ***REMOVED*** Step 2: Submit login form
            if not self._submit_login_form(session, login_url, username, password):
                return False

            ***REMOVED*** Step 3: Verify login success
            return self._verify_login_success(session, base_url)

        except Exception as e:
            _LOGGER.error("CM2000: Login exception: %s", e, exc_info=True)
            return False

    def _extract_login_url(self, session, base_url: str) -> str | None:
        """Extract the login URL with dynamic ID from the login page."""
        _LOGGER.debug("CM2000: Fetching login page to extract form action")
        login_page_response = session.get(f"{base_url}/", timeout=10)

        if login_page_response.status_code != 200:
            _LOGGER.warning("CM2000: Failed to fetch login page, status %d", login_page_response.status_code)
            return None

        login_soup = BeautifulSoup(login_page_response.text, "html.parser")
        form = login_soup.find("form", {"name": "loginform"})

        if not form:
            form = login_soup.find("form", {"id": "target"})

        if not form:
            _LOGGER.warning("CM2000: Could not find login form on page")
            return f"{base_url}/goform/Login"

        form_action = str(form.get("action", "/goform/Login"))
        if form_action.startswith("/"):
            login_url = f"{base_url}{form_action}"
        elif form_action.startswith("http"):
            login_url = form_action
        else:
            login_url = f"{base_url}/{form_action}"

        _LOGGER.debug("CM2000: Extracted login URL: %s", login_url)
        return login_url

    def _submit_login_form(self, session, login_url: str, username: str, password: str) -> bool:
        """Submit the login form with credentials."""
        login_data = {
            self.auth_config.username_field: username,
            self.auth_config.password_field: password,
        }

        _LOGGER.debug("CM2000: Submitting login to %s", login_url)
        login_response = session.post(
            login_url, data=login_data, timeout=10, allow_redirects=True, verify=session.verify
        )

        if login_response.status_code != 200:
            _LOGGER.warning("CM2000: Login POST failed with status %d", login_response.status_code)
            return False

        return True

    def _verify_login_success(self, session, base_url: str) -> bool:
        """Verify login by checking if DocsisStatus.htm is accessible with channel data."""
        _LOGGER.debug("CM2000: Verifying login by fetching DocsisStatus.htm")
        verify_response = session.get(f"{base_url}/DocsisStatus.htm", timeout=10)

        if verify_response.status_code != 200:
            _LOGGER.warning("CM2000: DocsisStatus.htm returned status %d", verify_response.status_code)
            return False

        ***REMOVED*** Check if we got redirected back to login page
        if "redirect()" in verify_response.text and "Login.htm" in verify_response.text:
            _LOGGER.warning("CM2000: Login failed - got redirected to login page")
            return False

        ***REMOVED*** Check if we got actual channel data
        if "InitDsTableTagValue" in verify_response.text or "InitUsTableTagValue" in verify_response.text:
            _LOGGER.info("CM2000: Login successful - DocsisStatus.htm contains channel data")
            return True

        ***REMOVED*** If we got a 200 but no channel data, login might have worked
        _LOGGER.warning("CM2000: DocsisStatus.htm accessible but no channel data found")
        return True

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Parse all data from the modem.

        Args:
            soup: BeautifulSoup object of the page
            session: Requests session (optional, for multi-page parsing)
            base_url: Base URL of the modem (optional)

        Returns:
            Dictionary with downstream, upstream, and system_info
        """
        ***REMOVED*** CM2000 requires fetching DocsisStatus.htm for channel data
        docsis_soup = soup  ***REMOVED*** Default to provided soup

        if session and base_url:
            try:
                _LOGGER.debug("CM2000: Fetching DocsisStatus.htm for channel data")
                docsis_url = f"{base_url}/DocsisStatus.htm"
                docsis_response = session.get(docsis_url, timeout=10)

                if docsis_response.status_code == 200:
                    ***REMOVED*** Check if we got redirected to login page
                    if "redirect()" in docsis_response.text and "Login.htm" in docsis_response.text:
                        _LOGGER.warning("CM2000: Session expired, got login redirect")
                    else:
                        docsis_soup = BeautifulSoup(docsis_response.text, "html.parser")
                        _LOGGER.debug(
                            "CM2000: Successfully fetched DocsisStatus.htm (%d bytes)", len(docsis_response.text)
                        )
                else:
                    _LOGGER.warning(
                        "CM2000: Failed to fetch DocsisStatus.htm, status %d - using provided page",
                        docsis_response.status_code,
                    )
            except Exception as e:
                _LOGGER.warning("CM2000: Error fetching DocsisStatus.htm: %s - using provided page", e)

        ***REMOVED*** Parse channel data from DocsisStatus.htm
        downstream_channels = self.parse_downstream(docsis_soup)
        upstream_channels = self.parse_upstream(docsis_soup)

        ***REMOVED*** Parse system info
        system_info = self.parse_system_info(docsis_soup)

        return {
            "downstream": downstream_channels,
            "upstream": upstream_channels,
            "system_info": system_info,
        }

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """Detect if this is a Netgear CM2000.

        Detection strategy:
        - Check for "NETGEAR Modem CM2000" in title
        - Check for meta description containing "CM2000"
        - Check for "Nighthawk CM2000" in page content

        Args:
            soup: BeautifulSoup object of the page
            url: URL that was fetched
            html: Raw HTML string

        Returns:
            True if this is a Netgear CM2000, False otherwise
        """
        ***REMOVED*** Check title tag
        title = soup.find("title")
        if title and "CM2000" in title.text and "NETGEAR" in title.text:
            _LOGGER.info("Detected Netgear CM2000 from page title")
            return True

        ***REMOVED*** Check meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            content = meta_desc.get("content", "")
            if isinstance(content, str) and "CM2000" in content:
                _LOGGER.info("Detected Netgear CM2000 from meta description")
                return True

        ***REMOVED*** Check for CM2000 in page text with NETGEAR
        ***REMOVED*** Make sure it's not another model that mentions CM2000
        if (
            "CM2000" in html
            and "NETGEAR" in html.upper()
            and ("Nighthawk CM2000" in html or "My Modem:</b> Nighthawk CM2000" in html)
        ):
            _LOGGER.info("Detected Netgear CM2000 from page content")
            return True

        return False

    def parse_downstream(self, soup: BeautifulSoup) -> list[dict]:  ***REMOVED*** noqa: C901
        """Parse downstream channel data from DocsisStatus.htm.

        The CM2000 likely embeds channel data in JavaScript variables similar to C3700.
        Format expected:
        - InitDsTableTagValue() function contains tagValueList
        - Format: 'count|ch1_data|ch2_data|...'
        - Each channel: num|lock|modulation|id|frequency|power|snr|corrected|uncorrected

        Returns:
            List of downstream channel dictionaries
        """
        channels: list[dict] = []

        try:
            ***REMOVED*** Method 1: Try JavaScript variable extraction (like C3700)
            channels = self._parse_downstream_from_js(soup)

            ***REMOVED*** Method 2: Try HTML table extraction (like CM600) if JS method fails
            if not channels:
                channels = self._parse_downstream_from_table(soup)

            _LOGGER.info("CM2000: Parsed %d downstream channels", len(channels))

        except Exception as e:
            _LOGGER.error("Error parsing CM2000 downstream channels: %s", e, exc_info=True)

        return channels

    def _parse_downstream_from_js(self, soup: BeautifulSoup) -> list[dict]:  ***REMOVED*** noqa: C901
        """Parse downstream channels from JavaScript variables."""
        channels: list[dict] = []

        try:
            regex_pattern = re.compile("InitDsTableTagValue")
            all_scripts = soup.find_all("script")

            for script in all_scripts:
                if script.string and regex_pattern.search(script.string):
                    ***REMOVED*** Extract the function body
                    func_match = re.search(
                        r"function InitDsTableTagValue\(\)[^{]*\{(.*?)\n\}", script.string, re.DOTALL
                    )
                    if not func_match:
                        continue

                    func_body = func_match.group(1)
                    ***REMOVED*** Remove block comments
                    func_body_clean = re.sub(r"/\*.*?\*/", "", func_body, flags=re.DOTALL)

                    ***REMOVED*** Find tagValueList
                    match = re.search(r"^\s+var tagValueList = [\"']([^\"']+)[\"']", func_body_clean, re.MULTILINE)
                    if not match:
                        continue

                    values = match.group(1).split("|")
                    _LOGGER.debug("CM2000 Downstream JS: Found %d values", len(values))

                    if len(values) < 10:  ***REMOVED*** Need at least count + 1 channel
                        continue

                    ***REMOVED*** First value is channel count
                    channel_count = int(values[0])
                    fields_per_channel = 9
                    idx = 1

                    for i in range(channel_count):
                        if idx + fields_per_channel > len(values):
                            break

                        try:
                            freq_str = values[idx + 4].replace(" Hz", "").strip()
                            freq = int(freq_str)
                            lock_status = values[idx + 1]

                            if freq == 0 or lock_status != "Locked":
                                idx += fields_per_channel
                                continue

                            channel = {
                                "channel_id": values[idx + 3],
                                "frequency": freq,
                                "power": float(values[idx + 5]),
                                "snr": float(values[idx + 6]),
                                "modulation": values[idx + 2],
                                "corrected": int(values[idx + 7]),
                                "uncorrected": int(values[idx + 8]),
                            }
                            channels.append(channel)

                        except (ValueError, IndexError) as e:
                            _LOGGER.warning("CM2000 Downstream: Error parsing channel %d: %s", i + 1, e)

                        idx += fields_per_channel

                    break  ***REMOVED*** Found data, stop searching

        except Exception as e:
            _LOGGER.debug("CM2000: JS downstream parsing failed: %s", e)

        return channels

    def _parse_downstream_from_table(self, soup: BeautifulSoup) -> list[dict]:  ***REMOVED*** noqa: C901
        """Parse downstream channels from HTML table (fallback method)."""
        channels: list[dict] = []

        try:
            ***REMOVED*** Look for downstream table by id or class
            ds_table = soup.find("table", {"id": "dsTable"})
            if not ds_table:
                ***REMOVED*** Try finding by header text
                tables = soup.find_all("table")
                for table in tables:
                    header = table.find("tr")
                    if header and "downstream" in header.get_text().lower():
                        ds_table = table
                        break

            if not ds_table:
                return channels

            rows = ds_table.find_all("tr")[1:]  ***REMOVED*** Skip header

            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 9:
                    continue

                try:
                    lock_status = cells[1].get_text(strip=True)
                    if lock_status != "Locked":
                        continue

                    freq_str = cells[4].get_text(strip=True).replace(" Hz", "").replace("Hz", "").strip()
                    freq = int(freq_str)
                    if freq == 0:
                        continue

                    channel = {
                        "channel_id": cells[3].get_text(strip=True),
                        "frequency": freq,
                        "power": float(cells[5].get_text(strip=True).replace(" dBmV", "").replace("dBmV", "")),
                        "snr": float(cells[6].get_text(strip=True).replace(" dB", "").replace("dB", "")),
                        "modulation": cells[2].get_text(strip=True),
                        "corrected": int(cells[7].get_text(strip=True)),
                        "uncorrected": int(cells[8].get_text(strip=True)),
                    }
                    channels.append(channel)

                except (ValueError, IndexError) as e:
                    _LOGGER.warning("CM2000 Downstream table: Error parsing row: %s", e)
                    continue

        except Exception as e:
            _LOGGER.debug("CM2000: Table downstream parsing failed: %s", e)

        return channels

    def parse_upstream(self, soup: BeautifulSoup) -> list[dict]:  ***REMOVED*** noqa: C901
        """Parse upstream channel data from DocsisStatus.htm.

        Returns:
            List of upstream channel dictionaries
        """
        channels: list[dict] = []

        try:
            ***REMOVED*** Method 1: Try JavaScript variable extraction
            channels = self._parse_upstream_from_js(soup)

            ***REMOVED*** Method 2: Try HTML table extraction if JS method fails
            if not channels:
                channels = self._parse_upstream_from_table(soup)

            _LOGGER.info("CM2000: Parsed %d upstream channels", len(channels))

        except Exception as e:
            _LOGGER.error("Error parsing CM2000 upstream channels: %s", e, exc_info=True)

        return channels

    def _parse_upstream_from_js(self, soup: BeautifulSoup) -> list[dict]:  ***REMOVED*** noqa: C901
        """Parse upstream channels from JavaScript variables."""
        channels: list[dict] = []

        try:
            regex_pattern = re.compile("InitUsTableTagValue")
            all_scripts = soup.find_all("script")

            for script in all_scripts:
                if script.string and regex_pattern.search(script.string):
                    func_match = re.search(
                        r"function InitUsTableTagValue\(\)[^{]*\{(.*?)\n\}", script.string, re.DOTALL
                    )
                    if not func_match:
                        continue

                    func_body = func_match.group(1)
                    func_body_clean = re.sub(r"/\*.*?\*/", "", func_body, flags=re.DOTALL)

                    match = re.search(r"^\s+var tagValueList = [\"']([^\"']+)[\"']", func_body_clean, re.MULTILINE)
                    if not match:
                        continue

                    values = match.group(1).split("|")
                    _LOGGER.debug("CM2000 Upstream JS: Found %d values", len(values))

                    if len(values) < 8:  ***REMOVED*** Need at least count + 1 channel
                        continue

                    channel_count = int(values[0])
                    fields_per_channel = 7
                    idx = 1

                    for i in range(channel_count):
                        if idx + fields_per_channel > len(values):
                            break

                        try:
                            freq_str = values[idx + 5].replace(" Hz", "").strip()
                            freq = int(freq_str)
                            lock_status = values[idx + 1]

                            if freq == 0 or lock_status != "Locked":
                                idx += fields_per_channel
                                continue

                            power_str = values[idx + 6].replace(" dBmV", "").strip()
                            channel = {
                                "channel_id": values[idx + 3],
                                "frequency": freq,
                                "power": float(power_str),
                                "channel_type": values[idx + 2],
                            }
                            channels.append(channel)

                        except (ValueError, IndexError) as e:
                            _LOGGER.warning("CM2000 Upstream: Error parsing channel %d: %s", i + 1, e)

                        idx += fields_per_channel

                    break

        except Exception as e:
            _LOGGER.debug("CM2000: JS upstream parsing failed: %s", e)

        return channels

    def _parse_upstream_from_table(self, soup: BeautifulSoup) -> list[dict]:  ***REMOVED*** noqa: C901
        """Parse upstream channels from HTML table (fallback method)."""
        channels: list[dict] = []

        try:
            us_table = soup.find("table", {"id": "usTable"})
            if not us_table:
                tables = soup.find_all("table")
                for table in tables:
                    header = table.find("tr")
                    if header and "upstream" in header.get_text().lower():
                        us_table = table
                        break

            if not us_table:
                return channels

            rows = us_table.find_all("tr")[1:]

            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 7:
                    continue

                try:
                    lock_status = cells[1].get_text(strip=True)
                    if lock_status != "Locked":
                        continue

                    freq_str = cells[5].get_text(strip=True).replace(" Hz", "").replace("Hz", "").strip()
                    freq = int(freq_str)
                    if freq == 0:
                        continue

                    channel = {
                        "channel_id": cells[3].get_text(strip=True),
                        "frequency": freq,
                        "power": float(cells[6].get_text(strip=True).replace(" dBmV", "").replace("dBmV", "")),
                        "channel_type": cells[2].get_text(strip=True),
                    }
                    channels.append(channel)

                except (ValueError, IndexError) as e:
                    _LOGGER.warning("CM2000 Upstream table: Error parsing row: %s", e)
                    continue

        except Exception as e:
            _LOGGER.debug("CM2000: Table upstream parsing failed: %s", e)

        return channels

    def parse_system_info(self, soup: BeautifulSoup) -> dict:
        """Parse system information from DocsisStatus.htm.

        Returns:
            Dictionary with available system info
        """
        info = {}

        try:
            ***REMOVED*** Try to extract from JavaScript InitTagValue function
            ***REMOVED*** Filter script tags manually to satisfy mypy (find_all with both name and string has typing issues)
            script_tags = [
                tag for tag in soup.find_all("script") if tag.string and re.search("InitTagValue", tag.string)
            ]

            for script in script_tags:
                if not script.string:
                    continue

                ***REMOVED*** Look for InitTagValue function
                func_match = re.search(r"function InitTagValue\(\)[^{]*\{(.*?)\n\}", script.string, re.DOTALL)
                if not func_match:
                    continue

                func_body = func_match.group(1)
                func_body_clean = re.sub(r"/\*.*?\*/", "", func_body, flags=re.DOTALL)

                match = re.search(r"var tagValueList = [\"']([^\"']+)[\"']", func_body_clean)
                if match:
                    values = match.group(1).split("|")
                    ***REMOVED*** Extract current system time (index 10)
                    if len(values) > 10 and values[10] and values[10] != "&nbsp;":
                        info["current_time"] = values[10]
                        _LOGGER.debug("CM2000: Parsed current time: %s", values[10])

                    ***REMOVED*** Extract system uptime (index 14) - CM2000 provides this!
                    if len(values) > 14 and values[14] and values[14] != "&nbsp;":
                        info["system_uptime"] = values[14]
                        _LOGGER.debug("CM2000: Parsed system uptime: %s", values[14])

                        ***REMOVED*** Calculate last boot time from uptime
                        boot_time = self._calculate_boot_time(values[14])
                        if boot_time:
                            info["last_boot_time"] = boot_time
                            _LOGGER.debug("CM2000: Calculated last boot time: %s", boot_time)

                    _LOGGER.debug("CM2000: Parsed system info from InitTagValue")
                    break

            ***REMOVED*** Also try to find firmware version from page content
            fw_match = re.search(r"Cable Firmware Version[:\s]*([^\s<]+)", str(soup))
            if fw_match:
                info["software_version"] = fw_match.group(1)

        except Exception as e:
            _LOGGER.error("Error parsing CM2000 system info: %s", e)

        return info

    def _calculate_boot_time(self, uptime_str: str) -> str | None:
        """Calculate boot time from uptime string.

        Args:
            uptime_str: Uptime string like "7 days 00:00:01" (days HH:MM:SS format)

        Returns:
            ISO format datetime string of boot time or None if parsing fails
        """
        from datetime import datetime, timedelta

        try:
            total_seconds = 0

            ***REMOVED*** Parse days (e.g., "7 days")
            days_match = re.search(r"(\d+)\s*days?", uptime_str, re.IGNORECASE)
            if days_match:
                total_seconds += int(days_match.group(1)) * 86400

            ***REMOVED*** Parse HH:MM:SS format (e.g., "00:00:01")
            time_match = re.search(r"(\d{1,2}):(\d{2}):(\d{2})", uptime_str)
            if time_match:
                hours = int(time_match.group(1))
                minutes = int(time_match.group(2))
                seconds = int(time_match.group(3))
                total_seconds += hours * 3600 + minutes * 60 + seconds

            if total_seconds == 0:
                return None

            ***REMOVED*** Calculate boot time: current time - uptime
            uptime_delta = timedelta(seconds=total_seconds)
            boot_time = datetime.now() - uptime_delta

            return boot_time.isoformat()

        except Exception as e:
            _LOGGER.error("Error calculating boot time from '%s': %s", uptime_str, e)
            return None
