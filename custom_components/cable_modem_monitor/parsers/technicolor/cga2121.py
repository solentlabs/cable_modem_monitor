"""Parser for Technicolor CGA2121 cable modem."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.auth_config import RedirectFormAuthConfig
from custom_components.cable_modem_monitor.core.authentication import AuthStrategyType
from custom_components.cable_modem_monitor.lib.utils import extract_float, extract_number

from ..base_parser import ModemCapability, ModemParser, ParserStatus

_LOGGER = logging.getLogger(__name__)


class TechnicolorCGA2121Parser(ModemParser):
    """Parser for Technicolor CGA2121 cable modem (Telia Finland)."""

    name = "Technicolor CGA2121"
    manufacturer = "Technicolor"
    models = ["CGA2121"]

    # Parser status
    status = ParserStatus.AWAITING_VERIFICATION
    verification_source = None

    # Device metadata
    release_date = "2015"
    docsis_version = "3.0"
    fixtures_path = "tests/parsers/technicolor/fixtures/cga2121"

    # Authentication configuration - form-based POST
    # HAR analysis: POST /goform/logon -> 302 to /basicUX.html, sets sec= cookie
    auth_config = RedirectFormAuthConfig(
        strategy=AuthStrategyType.REDIRECT_FORM,
        login_url="/goform/logon",
        username_field="username_login",
        password_field="password_login",
        success_redirect_pattern="/basicUX.html",
        authenticated_page_url="/st_docsis.html",
    )

    url_patterns = [
        {"path": "/st_docsis.html", "auth_method": "form", "auth_required": True},
    ]

    # Capabilities - CGA2121 provides limited data (no frequency, no codewords)
    capabilities = {
        ModemCapability.DOWNSTREAM_CHANNELS,
        ModemCapability.UPSTREAM_CHANNELS,
    }

    def login(self, session, base_url, username, password) -> tuple[bool, str | None]:
        """
        CGA2121 uses form-based authentication.

        Returns:
            tuple: (success: bool, html: str | None) - authenticated HTML from st_docsis.html
        """
        if not username or not password:
            _LOGGER.debug("No credentials provided for CGA2121, attempting without auth")
            return False, None

        try:
            return self._perform_login(session, base_url, username, password)
        except (requests.exceptions.Timeout, requests.exceptions.ReadTimeout) as e:
            _LOGGER.debug("CGA2121 login timeout (modem may be busy or rebooting): %s", str(e))
        except requests.exceptions.ConnectionError as e:
            _LOGGER.warning("CGA2121 login connection error: %s", str(e))
        except requests.exceptions.RequestException as e:
            _LOGGER.warning("CGA2121 login request failed: %s", str(e))
        except Exception as e:
            _LOGGER.error("CGA2121 login unexpected exception: %s", str(e), exc_info=True)
        return False, None

    def _perform_login(self, session, base_url, username, password) -> tuple[bool, str | None]:
        """Execute the login POST and fetch status page."""
        login_url = f"{base_url}/goform/logon"
        login_data = {
            "username_login": username,
            "password_login": password,
            "language_selector": "en",
        }

        _LOGGER.debug("CGA2121: Posting credentials to %s", login_url)
        response = session.post(login_url, data=login_data, timeout=10, allow_redirects=True)

        # Log response details for debugging auth issues
        self._log_auth_response(response, session)

        if not self._validate_login_response(response, base_url):
            return False, None

        return self._fetch_status_page(session, base_url)

    def _log_auth_response(self, response, session) -> None:
        """Log detailed auth response info for debugging."""
        _LOGGER.debug(
            "CGA2121 auth response: status=%s, final_url=%s, history=%s",
            response.status_code,
            response.url,
            [r.status_code for r in response.history],
        )

        # Log cookies received - critical for diagnosing session issues
        cookies = session.cookies.get_dict()
        if cookies:
            # Mask cookie values but show names and value length
            masked = {k: f"<{len(str(v))} chars>" for k, v in cookies.items()}
            _LOGGER.debug("CGA2121 session cookies: %s", masked)
        else:
            _LOGGER.warning("CGA2121: No cookies received after login - session may fail")

        # Check for expected 'sec' cookie
        if "sec" not in cookies:
            _LOGGER.warning(
                "CGA2121: Expected 'sec' cookie not found. Got cookies: %s",
                list(cookies.keys()),
            )

    def _validate_login_response(self, response, base_url: str) -> bool:
        """Validate the login response for security and success."""
        if response.status_code != 200:
            _LOGGER.error(
                "CGA2121 login failed: status=%s, url=%s, response_size=%s",
                response.status_code,
                response.url,
                len(response.text),
            )
            return False

        # Security check: Ensure redirect is to same host
        redirect_parsed = urlparse(response.url)
        base_parsed = urlparse(base_url)
        if redirect_parsed.hostname != base_parsed.hostname:
            _LOGGER.error(
                "CGA2121: Security violation - redirect to different host: %s",
                response.url,
            )
            return False

        # Check if we're still on login page (wrong credentials)
        if "logon.html" in response.url.lower():
            # Log page content snippet to help diagnose login failure reason
            snippet = response.text[:500] if response.text else "<empty>"
            _LOGGER.warning(
                "CGA2121: Login failed - still on login page. " "Check credentials. Response snippet: %s",
                snippet.replace("\n", " ")[:200],
            )
            return False

        # Log successful redirect destination
        _LOGGER.debug("CGA2121: Login redirected to %s (expected /basicUX.html)", response.url)
        return True

    def _fetch_status_page(self, session, base_url: str) -> tuple[bool, str | None]:
        """Fetch the DOCSIS status page with authenticated session."""
        status_url = f"{base_url}/st_docsis.html"
        _LOGGER.debug("CGA2121: Fetching %s with authenticated session", status_url)
        status_response = session.get(status_url, timeout=10)

        if status_response.status_code != 200:
            _LOGGER.error(
                "CGA2121: Failed to fetch status page: status=%s, url=%s",
                status_response.status_code,
                status_response.url,
            )
            return False, None

        # Verify we got the actual status page
        is_login_redirect = "logon.html" in status_response.url.lower()
        has_channel_data = "Downstream Channels" in status_response.text

        if is_login_redirect:
            _LOGGER.warning(
                "CGA2121: Session expired or invalid - redirected to login. " "URL: %s, Cookies: %s",
                status_response.url,
                list(session.cookies.get_dict().keys()),
            )
            return False, None

        if not has_channel_data:
            # Log what we got instead to help diagnose
            title_match = "DOCSIS Status" in status_response.text
            page_size = len(status_response.text)
            _LOGGER.warning(
                "CGA2121: Got page but no channel data. "
                "has_title=%s, size=%s, url=%s. "
                "Page may have different structure or require different auth.",
                title_match,
                page_size,
                status_response.url,
            )
            return False, None

        _LOGGER.info("CGA2121: Successfully authenticated (%s bytes)", len(status_response.text))
        return True, status_response.text

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """
        Detect if this is a Technicolor CGA2121 modem.

        Detection criteria:
        1. URL contains "st_docsis.html"
        2. HTML contains "CGA2121" model identifier
        3. Page title is "DOCSIS Status"
        """
        # Primary detection: Model name in HTML
        if "CGA2121" in html:
            _LOGGER.debug("CGA2121 detected by model name in HTML")
            return True

        # Secondary detection: URL pattern + Technicolor branding
        if "st_docsis.html" in url.lower():
            title_tag = soup.find("title")
            has_docsis_title = title_tag and "DOCSIS Status" in title_tag.get_text()
            has_technicolor = "Technicolor" in html
            if has_docsis_title and has_technicolor:
                _LOGGER.debug("CGA2121 detected by URL + Technicolor branding")
                return True

        return False

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Parse all data from the CGA2121 modem."""
        downstream_channels = self._parse_downstream(soup)
        upstream_channels = self._parse_upstream(soup)
        system_info = self._parse_system_info(soup)

        return {
            "downstream": downstream_channels,
            "upstream": upstream_channels,
            "system_info": system_info,
        }

    def _find_channel_tbody(self, soup: BeautifulSoup, section_name: str, i18n_key: str) -> BeautifulSoup | None:
        """Find the tbody element for a channel section by header text or i18n key."""
        # Look for header containing section name
        header = None
        for h2 in soup.find_all("h2"):
            if section_name in h2.get_text():
                header = h2
                break

        # Try finding by data-i18n attribute as fallback
        if not header:
            header = soup.find("span", {"data-i18n": i18n_key})

        if not header:
            _LOGGER.warning("CGA2121: %s section not found", section_name)
            return None

        # Find the parent panel and then the table
        panel = header.find_parent("div", class_="panel")
        if not panel:
            _LOGGER.warning("CGA2121: %s panel not found", section_name)
            return None

        tables = panel.find_all("table", class_="rsp-table")
        if not tables:
            _LOGGER.warning("CGA2121: %s table not found", section_name)
            return None

        # Use the last table (the active one, not commented)
        tbody = tables[-1].find("tbody")
        if not tbody:
            _LOGGER.warning("CGA2121: %s tbody not found", section_name)
            return None

        return tbody

    def _parse_downstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse downstream channel data from CGA2121."""
        channels: list[dict] = []

        try:
            tbody = self._find_channel_tbody(soup, "Downstream Channels", "ds_link_downstream_channels")
            if not tbody:
                return channels

            for row in tbody.find_all("tr"):
                cols = row.find_all("td")
                if len(cols) >= 4:
                    channels.append(
                        {
                            "channel_id": extract_number(cols[0].get_text()),
                            "modulation": cols[1].get_text().strip(),
                            "snr": extract_float(cols[2].get_text()),
                            "power": extract_float(cols[3].get_text()),
                        }
                    )

            _LOGGER.debug("CGA2121: Parsed %d downstream channels", len(channels))

        except Exception as e:
            _LOGGER.error("Error parsing CGA2121 downstream channels: %s", e)

        return channels

    def _parse_upstream(self, soup: BeautifulSoup) -> list[dict]:
        """Parse upstream channel data from CGA2121."""
        channels: list[dict] = []

        try:
            tbody = self._find_channel_tbody(soup, "Upstream Channels", "ds_link_upstream_channels")
            if not tbody:
                return channels

            for row in tbody.find_all("tr"):
                cols = row.find_all("td")
                if len(cols) >= 3:
                    channels.append(
                        {
                            "channel_id": extract_number(cols[0].get_text()),
                            "modulation": cols[1].get_text().strip(),
                            "power": extract_float(cols[2].get_text()),
                        }
                    )

            _LOGGER.debug("CGA2121: Parsed %d upstream channels", len(channels))

        except Exception as e:
            _LOGGER.error("Error parsing CGA2121 upstream channels: %s", e)

        return channels

    def _parse_system_info(self, soup: BeautifulSoup) -> dict:
        """
        Parse system information from CGA2121.

        The status page has limited system info - mainly operational status.
        """
        info = {}

        try:
            # Try to find operational status
            for row in soup.find_all("tr"):
                header = row.find("th")
                value = row.find("td")
                if header and value:
                    header_text = header.get_text().strip()
                    value_text = value.get_text().strip()

                    if "Operational Status" in header_text:
                        info["operational_status"] = value_text
                    elif "Downstream Channels" in header_text:
                        info["downstream_channel_count"] = extract_number(value_text)
                    elif "Upstream Channels" in header_text:
                        info["upstream_channel_count"] = extract_number(value_text)
                    elif "Baseline Privacy" in header_text:
                        info["baseline_privacy"] = value_text

        except Exception as e:
            _LOGGER.error("Error parsing CGA2121 system info: %s", e)

        return info
