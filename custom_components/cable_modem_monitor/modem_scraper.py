"""Web scraper for cable modem data."""
import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Type

from .parsers.base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)


class ModemScraper:
    """Scrape data from cable modem web interface."""

    def __init__(self, host: str, username: str = None, password: str = None, parsers: List[Type[ModemParser]] = None):
        """Initialize the modem scraper."""
        self.host = host
        self.base_url = f"http://{host}"
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.parsers = parsers if parsers else []
        self.parser = None

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
        urls_to_try = [
            f"{self.base_url}/network_setup.jst",  ***REMOVED*** Technicolor XB7
            f"{self.base_url}/MotoConnection.asp",
            f"{self.base_url}/cmconnectionstatus.html",
            f"{self.base_url}/cmSignalData.htm",
            f"{self.base_url}/cmSignal.html",
            f"{self.base_url}/",
        ]

        for url in urls_to_try:
            try:
                _LOGGER.debug(f"Attempting to fetch {url}")
                response = self.session.get(url, timeout=10)
                if response.status_code == 200:
                    _LOGGER.info(f"Successfully connected to modem at {url} (HTML length: {len(response.text)} bytes)")
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
                _LOGGER.error("Could not fetch data from any known modem URL.")
                return {"connection_status": "unreachable", "downstream": [], "upstream": []}

            html, successful_url = fetched_data
            self.parser = self._detect_parser(html, successful_url)

            if not self.parser:
                _LOGGER.error(f"No compatible parser found for modem at {successful_url}.")
                return {"connection_status": "offline", "downstream": [], "upstream": []}

            if not self._login():
                _LOGGER.error("Failed to log in to modem")
                return {"connection_status": "unreachable", "downstream": [], "upstream": []}

            data = self._parse_data(html)

            total_corrected = sum(ch.get("corrected") or 0 for ch in data["downstream"])
            total_uncorrected = sum(ch.get("uncorrected") or 0 for ch in data["downstream"])

            return {
                "connection_status": "online" if (data["downstream"] or data["upstream"]) else "offline",
                "downstream": data["downstream"],
                "upstream": data["upstream"],
                "total_corrected": total_corrected,
                "total_uncorrected": total_uncorrected,
                "downstream_channel_count": len(data["downstream"]),
                "upstream_channel_count": len(data["upstream"]),
                **data["system_info"],
            }

        except Exception as e:
            _LOGGER.error(f"Error fetching modem data: {e}")
            return {"connection_status": "unreachable", "downstream": [], "upstream": []}
