"""Web scraper for cable modem data."""
import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Type

from ..parsers.base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)


class ModemScraper:
    """Scrape data from cable modem web interface."""

    def __init__(
        self,
        host: str,
        username: str = None,
        password: str = None,
        parser: ModemParser | List[Type[ModemParser]] = None,
        cached_url: str = None,
        parser_name: str = None,
    ):
        """
        Initialize the modem scraper.

        Args:
            host: Modem IP address
            username: Optional login username
            password: Optional login password
            parser: Either a single parser instance, a parser class, or list of parser classes
            cached_url: Previously successful URL (optimization)
            parser_name: Name of cached parser to use (skips auto-detection)
        """
        self.host = host
        self.base_url = f"http://{host}"
        self.username = username
        self.password = password
        self.session = requests.Session()

        # Handle parser parameter - can be instance, class, or list of classes
        if isinstance(parser, list):
            self.parsers = parser
            self.parser = None
        elif parser and isinstance(parser, type):
            # Parser class passed in
            self.parsers = [parser]
            self.parser = None
        elif parser:
            # Parser instance passed in
            self.parsers = []
            self.parser = parser
        else:
            self.parsers = []
            self.parser = None

        self.cached_url = cached_url
        self.parser_name = parser_name  # For Tier 2: load cached parser by name
        self.last_successful_url = None

    def _login(self) -> bool:
        """Log in to the modem web interface."""
        if not self.username or not self.password:
            _LOGGER.debug("No credentials provided, skipping login")
            return True

        if not self.parser:
            _LOGGER.error("No parser detected, cannot log in")
            return False

        return self.parser.login(self.session, self.base_url, self.username, self.password)

    def _get_url_patterns_to_try(self) -> list[tuple[str, str, Type[ModemParser] | None]]:
        """
        Get list of (url, auth_method, parser_class) tuples to try.

        Returns URLs in priority order based on 3-tier strategy:
        1. If parser is set (user selected): use only that parser's URLs
        2. If parser_name cached: load that parser and use its URLs first
        3. Auto-detect mode: try all parsers' URLs
        """
        urls_to_try = []

        # Tier 1: User explicitly selected a parser
        if self.parser:
            _LOGGER.info(f"Tier 1: Using explicitly selected parser: {self.parser.name}")
            for pattern in self.parser.url_patterns:
                url = f"{self.base_url}{pattern['path']}"
                urls_to_try.append((url, pattern['auth_method'], type(self.parser)))
            return urls_to_try

        # Tier 2: Cached parser from previous successful detection
        if self.parser_name and self.parsers:
            _LOGGER.info(f"Tier 2: Looking for cached parser: {self.parser_name}")
            cached_parser = next((p for p in self.parsers if p.name == self.parser_name), None)
            if cached_parser:
                _LOGGER.info(f"Found cached parser: {cached_parser.name}")
                # Try cached URL first if available
                if self.cached_url:
                    # Find the auth method for cached URL
                    cached_pattern = next(
                        (p for p in cached_parser.url_patterns if p['path'] in self.cached_url),
                        cached_parser.url_patterns[0] if cached_parser.url_patterns else None
                    )
                    if cached_pattern:
                        urls_to_try.append((self.cached_url, cached_pattern['auth_method'], cached_parser))

                # Add other URLs from this parser
                for pattern in cached_parser.url_patterns:
                    url = f"{self.base_url}{pattern['path']}"
                    if url != self.cached_url:  # Don't duplicate cached URL
                        urls_to_try.append((url, pattern['auth_method'], cached_parser))

                # Add other parsers as fallback
                for parser_class in self.parsers:
                    if parser_class.name != self.parser_name:
                        for pattern in parser_class.url_patterns:
                            url = f"{self.base_url}{pattern['path']}"
                            urls_to_try.append((url, pattern['auth_method'], parser_class))
                return urls_to_try

        # Tier 3: Auto-detection mode - try all parsers
        _LOGGER.info("Tier 3: Auto-detection mode - trying all parsers")

        # If we have a cached URL, try it first with any compatible parser
        if self.cached_url:
            for parser_class in self.parsers:
                for pattern in parser_class.url_patterns:
                    if pattern['path'] in self.cached_url:
                        urls_to_try.append((self.cached_url, pattern['auth_method'], parser_class))
                        break

        # Add all parser URLs
        for parser_class in self.parsers:
            for pattern in parser_class.url_patterns:
                url = f"{self.base_url}{pattern['path']}"
                if url != self.cached_url:  # Don't duplicate
                    urls_to_try.append((url, pattern['auth_method'], parser_class))

        return urls_to_try

    def _fetch_data(self) -> tuple[str, str, Type[ModemParser]] | None:
        """
        Fetch data from the modem using parser-defined URL patterns.

        Returns:
            tuple of (html, successful_url, parser_class) or None if failed
        """
        urls_to_try = self._get_url_patterns_to_try()

        if not urls_to_try:
            _LOGGER.error("No URL patterns available to try")
            return None

        for url, auth_method, parser_class in urls_to_try:
            try:
                _LOGGER.debug(f"Attempting to fetch {url} (auth: {auth_method}, parser: {parser_class.name if parser_class else 'unknown'})")
                auth = None
                if auth_method == 'basic' and self.username and self.password:
                    auth = (self.username, self.password)

                response = self.session.get(url, timeout=10, auth=auth)

                if response.status_code == 200:
                    _LOGGER.info(
                        f"Successfully connected to {url} "
                        f"(HTML: {len(response.text)} bytes, parser: {parser_class.name if parser_class else 'unknown'})"
                    )
                    self.last_successful_url = url
                    return response.text, url, parser_class
                else:
                    _LOGGER.debug(f"Got status {response.status_code} from {url}")
            except requests.RequestException as e:
                _LOGGER.debug(f"Failed to fetch from {url}: {type(e).__name__}: {e}")
                continue

        return None

    def _detect_parser(self, html: str, url: str, suggested_parser: Type[ModemParser] = None) -> ModemParser | None:
        """
        Detect the parser for the modem.

        Args:
            html: HTML content from modem
            url: URL that returned this HTML
            suggested_parser: Parser class suggested by URL pattern match (Tier 2/3)

        Returns:
            Parser instance or None
        """
        if self.parser:
            return self.parser

        soup = BeautifulSoup(html, "html.parser")

        # If we have a suggested parser from URL matching, try it first
        if suggested_parser:
            try:
                _LOGGER.debug(f"Testing suggested parser: {suggested_parser.name}")
                if suggested_parser.can_parse(soup, url, html):
                    _LOGGER.info(f"Detected modem using suggested parser: {suggested_parser.name} ({suggested_parser.manufacturer})")
                    return suggested_parser()
                else:
                    _LOGGER.debug(f"Suggested parser {suggested_parser.name} returned False for can_parse")
            except Exception as e:
                _LOGGER.error(f"Suggested parser {suggested_parser.name} detection failed: {e}", exc_info=True)

        # Fall back to trying all parsers
        _LOGGER.debug(f"Attempting to detect parser from {len(self.parsers)} available parsers")
        for parser_class in self.parsers:
            if suggested_parser and parser_class == suggested_parser:
                continue  # Already tried this one

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
        # Pass session and base_url to parser in case it needs to fetch additional pages
        data = self.parser.parse(soup, session=self.session, base_url=self.base_url)
        return data

    def get_modem_data(self) -> dict:
        """Fetch and parse modem data."""
        try:
            fetched_data = self._fetch_data()
            if not fetched_data:
                return {
                    "cable_modem_connection_status": "unreachable",
                    "cable_modem_downstream": [],
                    "cable_modem_upstream": []
                }

            html, successful_url, suggested_parser = fetched_data

            # Detect or instantiate parser
            if not self.parser:
                self.parser = self._detect_parser(html, successful_url, suggested_parser)

            if not self.parser:
                _LOGGER.error(f"No compatible parser found for modem at {successful_url}.")
                return {
                    "cable_modem_connection_status": "offline",
                    "cable_modem_downstream": [],
                    "cable_modem_upstream": []
                }

            # Login and get authenticated HTML
            login_result = self._login()
            if isinstance(login_result, tuple):
                success, authenticated_html = login_result
                if not success:
                    _LOGGER.error("Failed to log in to modem")
                    return {
                        "cable_modem_connection_status": "unreachable", 
                        "downstream": [], 
                        "upstream": []
                    }
                # Use the authenticated HTML from login if available
                if authenticated_html:
                    html = authenticated_html
                    _LOGGER.debug(f"Using authenticated HTML from login ({len(html)} bytes)")
            else:
                # Old-style boolean return for parsers that don't return HTML
                if not login_result:
                    _LOGGER.error("Failed to log in to modem")
                    return {
                        "cable_modem_connection_status": "unreachable", 
                        "downstream": [], 
                        "upstream": []
                    }

            data = self._parse_data(html)

            total_corrected = sum(ch.get("corrected") or 0 for ch in data["downstream"])
            total_uncorrected = sum(ch.get("uncorrected") or 0 for ch in data["downstream"])

            # Prefix system_info keys with cable_modem_
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
            return {
                "cable_modem_connection_status": "unreachable", 
                "cable_modem_downstream": [], 
                "cable_modem_upstream": []
            }

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
            # Ensure we have fetched data and detected parser
            if not self.parser:
                fetched_data = self._fetch_data()
                if not fetched_data:
                    _LOGGER.error("Cannot restart modem: unable to connect")
                    return False
                html, successful_url, suggested_parser = fetched_data
                self.parser = self._detect_parser(html, successful_url, suggested_parser)

            if not self.parser:
                _LOGGER.error("Cannot restart modem: no parser detected")
                return False

            # Check if parser supports restart
            if not hasattr(self.parser, 'restart'):
                _LOGGER.error(f"Parser {self.parser.name} does not support restart functionality")
                return False

            # Perform restart
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
