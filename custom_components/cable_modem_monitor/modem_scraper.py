"""Web scraper for cable modem data."""
import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Type

from .parsers.base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)


class ModemScraper:
    """Scrape data from cable modem web interface."""

    def __init__(self, host: str, username: str = None, password: str = None, parsers: List[Type[ModemParser]] = None, cached_url: str = None):
        """Initialize the modem scraper."""
        self.host = host
        self.base_url = f"http://{host}"
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.parsers = parsers if parsers else []
        self.parser = None
        self.cached_url = cached_url  ***REMOVED*** URL that worked last time
        self.last_successful_url = None  ***REMOVED*** Track successful URL for this session

    def _login(self) -> bool:
        """Log in to the modem web interface."""
        if not self.username or not self.password:
            _LOGGER.debug("No credentials provided, skipping login")
            return True

        if not self.parser:
            _LOGGER.error("No parser detected, cannot log in")
            return False

        return self.parser.login(self.session, self.base_url, self.username, self.password)

    def _fetch_data(self) -> tuple[str, str] | None:
        """Fetch data from the modem."""
        all_urls = [
            (f"{self.base_url}/network_setup.jst", 'basic'),       ***REMOVED*** Technicolor XB7, TC4400
            (f"{self.base_url}/MotoConnection.asp", 'form'),      ***REMOVED*** Motorola MB series
            (f"{self.base_url}/cmconnectionstatus.html", 'none'), ***REMOVED*** Various cable modems
            (f"{self.base_url}/cmSignalData.htm", 'none'),        ***REMOVED*** Arris SB6141
            (f"{self.base_url}/cmSignal.html", 'none'),           ***REMOVED*** Various cable modems
            (f"{self.base_url}/", 'none'),                        ***REMOVED*** Fallback root page
        ]

        ***REMOVED*** If we have a cached URL from previous successful connection, try it first
        urls_to_try = []
        if self.cached_url:
            _LOGGER.debug(f"Using cached URL: {self.cached_url}")
            ***REMOVED*** Find the cached URL entry in all_urls
            cached_entry = next((u for u in all_urls if u[0] == self.cached_url), None)
            if cached_entry:
                urls_to_try.append(cached_entry)
                ***REMOVED*** Add remaining URLs as fallback
                urls_to_try.extend([u for u in all_urls if u[0] != self.cached_url])
            else:
                ***REMOVED*** Cached URL not in our list, try all URLs
                urls_to_try = all_urls
        else:
            urls_to_try = all_urls

        for url, auth_type in urls_to_try:
            try:
                _LOGGER.debug(f"Attempting to fetch {url}")
                auth = None
                if auth_type == 'basic' and self.username and self.password:
                    auth = (self.username, self.password)

                response = self.session.get(url, timeout=10, auth=auth)

                if response.status_code == 200:
                    _LOGGER.info(f"Successfully connected to modem at {url} (HTML length: {len(response.text)} bytes)")
                    self.last_successful_url = url  ***REMOVED*** Track successful URL
                    return response.text, url
                else:
                    _LOGGER.debug(f"Got status {response.status_code} from {url}")
            except requests.RequestException as e:
                _LOGGER.debug(f"Failed to fetch from {url}: {type(e).__name__}: {e}")
                continue

        return None

    def _detect_parser(self, html: str, url: str) -> ModemParser | None:
        """Detect the parser for the modem."""
        soup = BeautifulSoup(html, "html.parser")
        _LOGGER.debug(f"Attempting to detect parser from {len(self.parsers)} available parsers")
        for parser_class in self.parsers:
            try:
                _LOGGER.debug(f"Testing parser: {parser_class.name}")
                if parser_class.can_parse(soup, url, html):
                    _LOGGER.info(f"Detected modem: {parser_class.name} ({parser_class.manufacturer})")
                    return parser_class()
                else:
                    _LOGGER.debug(f"Parser {parser_class.name} returned False for can_parse")
            except Exception as e:
                _LOGGER.error(f"Parser {parser_class.name} detection failed with exception: {e}", exc_info=True)

        _LOGGER.error(f"No parser matched. Title: {soup.title.string if soup.title else 'NO TITLE'}")
        return None

    def _parse_data(self, html: str) -> dict:
        """Parse data from the modem."""
        soup = BeautifulSoup(html, "html.parser")
        ***REMOVED*** Pass session and base_url to parser in case it needs to fetch additional pages
        data = self.parser.parse(soup, session=self.session, base_url=self.base_url)
        return data

    def get_modem_data(self) -> dict:
        """Fetch and parse modem data."""
        try:
            fetched_data = self._fetch_data()
            if not fetched_data:
                return {"cable_modem_connection_status": "unreachable", "cable_modem_downstream": [], "cable_modem_upstream": []}

            html, successful_url = fetched_data
            self.parser = self._detect_parser(html, successful_url)

            if not self.parser:
                _LOGGER.error(f"No compatible parser found for modem at {successful_url}.")
                return {"cable_modem_connection_status": "offline", "downstream": [], "upstream": []}

            ***REMOVED*** Login and get authenticated HTML
            login_result = self._login()
            if isinstance(login_result, tuple):
                success, authenticated_html = login_result
                if not success:
                    _LOGGER.error("Failed to log in to modem")
                    return {"cable_modem_connection_status": "unreachable", "downstream": [], "upstream": []}
                ***REMOVED*** Use the authenticated HTML from login if available
                if authenticated_html:
                    html = authenticated_html
                    _LOGGER.debug(f"Using authenticated HTML from login ({len(html)} bytes)")
            else:
                ***REMOVED*** Old-style boolean return for parsers that don't return HTML
                if not login_result:
                    _LOGGER.error("Failed to log in to modem")
                    return {"cable_modem_connection_status": "unreachable", "downstream": [], "upstream": []}

            data = self._parse_data(html)

            total_corrected = sum(ch.get("corrected") or 0 for ch in data["downstream"])
            total_uncorrected = sum(ch.get("uncorrected") or 0 for ch in data["downstream"])

            ***REMOVED*** Prefix system_info keys with cable_modem_
            prefixed_system_info = {}
            for key, value in data["system_info"].items():
                prefixed_key = f"cable_modem_{key}"
                prefixed_system_info[prefixed_key] = value

            return {
                "cable_modem_connection_status": "online" if (data["downstream"] or data["upstream"]) else "offline",
                "cable_modem_downstream": data["downstream"],
                "cable_modem_upstream": data["upstream"],
                "cable_modem_total_corrected": total_corrected,
                "cable_modem_total_uncorrected": total_uncorrected,
                "cable_modem_downstream_channel_count": len(data["downstream"]),
                "cable_modem_upstream_channel_count": len(data["upstream"]),
                **prefixed_system_info,
            }

        except Exception as e:
            _LOGGER.error(f"Error fetching modem data: {e}")
            return {"cable_modem_connection_status": "unreachable", "cable_modem_downstream": [], "cable_modem_upstream": []}

    def get_detection_info(self) -> dict:
        """Get information about detected modem and successful URL."""
        if self.parser:
            return {
                "modem_name": self.parser.name,
                "manufacturer": self.parser.manufacturer,
                "successful_url": self.last_successful_url,
            }
        return {}

    def restart_modem(self) -> bool:
        """Restart the cable modem."""
        try:
            ***REMOVED*** Ensure we have fetched data and detected parser
            if not self.parser:
                fetched_data = self._fetch_data()
                if not fetched_data:
                    _LOGGER.error("Cannot restart modem: unable to connect")
                    return False
                html, successful_url = fetched_data
                self.parser = self._detect_parser(html, successful_url)

            if not self.parser:
                _LOGGER.error("Cannot restart modem: no parser detected")
                return False

            ***REMOVED*** Check if parser supports restart
            if not hasattr(self.parser, 'restart'):
                _LOGGER.error(f"Parser {self.parser.name} does not support restart functionality")
                return False

            ***REMOVED*** Perform restart
            _LOGGER.info(f"Attempting to restart modem using {self.parser.name} parser")
            success = self.parser.restart(self.session, self.base_url)

            if success:
                _LOGGER.info("Modem restart command sent successfully")
            else:
                _LOGGER.error("Modem restart command failed")

            return success

        except Exception as e:
            _LOGGER.error(f"Error restarting modem: {e}")
            return False
