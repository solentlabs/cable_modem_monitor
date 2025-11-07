"""Web scraper for cable modem data."""
import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Type

from ..parsers.base_parser import ModemParser
from .discovery_helpers import (
    ParserHeuristics,
    DiscoveryCircuitBreaker,
    ParserNotFoundError,
)

_LOGGER = logging.getLogger(__name__)


class ModemScraper:
    """Scrape data from cable modem web interface."""

    def __init__(
        self,
        host: str,
        username: str | None = None,
        password: str | None = None,
        parser: ModemParser | List[Type[ModemParser]] | None = None,
        cached_url: str | None = None,
        parser_name: str | None = None,
        verify_ssl: bool = False,
    ):
        """
        Initialize the modem scraper.

        Args:
            host: Modem IP address (or full URL with http:// or https://)
            username: Optional login username
            password: Optional login password
            parser: Either a single parser instance, a parser class, or list of parser classes
            cached_url: Previously successful URL (optimization)
            parser_name: Name of cached parser to use (skips auto-detection)
            verify_ssl: Enable SSL certificate verification (default: False for compatibility with self-signed certs)
        """
        self.host = host
        # Support both plain IP addresses and full URLs (http:// or https://)
        if host.startswith(('http://', 'https://')):
            self.base_url = host.rstrip('/')
        else:
            # Try HTTPS first (MB8611 and newer modems), fallback to HTTP
            self.base_url = f"https://{host}"
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.session = requests.Session()

        # Configure SSL verification with security warnings
        if not self.verify_ssl:
            # Disable SSL warnings for the session only (not globally)
            import urllib3
            self.session.verify = False
            # Disable warnings only for this session
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            _LOGGER.info(
                "SSL certificate verification is disabled for this modem connection. "
                "This is common for cable modems with self-signed certificates."
            )
        else:
            self.session.verify = True
            _LOGGER.info("SSL certificate verification is enabled for secure connections")

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

    def _login(self) -> bool | tuple[bool, str]:
        """
        Log in to the modem web interface.

        Returns:
            bool: True if login successful (old style)
            tuple[bool, str]: (success, html) where html is authenticated page content (new style)
        """
        if not self.username or not self.password:
            _LOGGER.debug("No credentials provided, skipping login")
            return True

        if not self.parser:
            _LOGGER.error("No parser detected, cannot log in")
            return False

        return self.parser.login(self.session, self.base_url, self.username, self.password)

    def _get_url_patterns_to_try(self) -> list[tuple[str, str, Type[ModemParser]]]:
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
            _LOGGER.info("Tier 1: Using explicitly selected parser: %s", self.parser.name)
            for pattern in self.parser.url_patterns:
                url = f"{self.base_url}{pattern['path']}"
                urls_to_try.append((url, pattern['auth_method'], type(self.parser)))
            return urls_to_try

        # Tier 2: Cached parser from previous successful detection
        if self.parser_name and self.parsers:
            _LOGGER.info("Tier 2: Looking for cached parser: %s", self.parser_name)
            cached_parser = next((p for p in self.parsers if p.name == self.parser_name), None)
            if cached_parser:
                _LOGGER.info("Found cached parser: %s", cached_parser.name)
                # Try cached URL first if available
                if self.cached_url:
                    # Find the auth method for cached URL
                    cached_pattern = next(
                        (p for p in cached_parser.url_patterns
                         if isinstance(p.get('path'), str) and p.get('path') in self.cached_url),
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
        Automatically tries both HTTPS and HTTP protocols.

        Returns:
            tuple of (html, successful_url, parser_class) or None if failed
        """
        urls_to_try = self._get_url_patterns_to_try()

        if not urls_to_try:
            _LOGGER.error("No URL patterns available to try")
            return None

        # Try HTTPS first, then HTTP fallback for each URL
        protocols_to_try = ['https', 'http'] if self.base_url.startswith('https://') else ['http']
        _LOGGER.debug("Protocols to try: %s (base_url: %s)", protocols_to_try, self.base_url)

        for protocol in protocols_to_try:
            current_base_url = self.base_url.replace('https://', f'{protocol}://').replace('http://', f'{protocol}://')
            _LOGGER.debug("Trying protocol: %s (current_base_url: %s)", protocol, current_base_url)

            for url, auth_method, parser_class in urls_to_try:
                # Replace protocol in URL to match current attempt
                url = url.replace(self.base_url, current_base_url)

                try:
                    _LOGGER.debug(
                        "Attempting to fetch %s (auth: %s, parser: %s)",
                        url, auth_method, parser_class.name if parser_class else 'unknown'
                    )
                    auth = None
                    if auth_method == 'basic' and self.username and self.password:
                        auth = (self.username, self.password)

                    # Use configured SSL verification setting
                    response = self.session.get(url, timeout=10, auth=auth, verify=self.verify_ssl)

                    if response.status_code == 200:
                        parser_name = parser_class.name if parser_class else 'unknown'
                        _LOGGER.info(
                            "Successfully connected to %s (HTML: %s bytes, parser: %s)",
                            url, len(response.text), parser_name
                        )
                        self.last_successful_url = url
                        # Update base_url to the working protocol
                        _LOGGER.debug("About to update base_url from %s to %s", self.base_url, current_base_url)
                        self.base_url = current_base_url
                        _LOGGER.debug("Updated! base_url is now: %s", self.base_url)
                        return response.text, url, parser_class
                    else:
                        _LOGGER.debug("Got status %s from %s", response.status_code, url)
                except requests.RequestException as e:
                    _LOGGER.debug("Failed to fetch from %s: %s: %s", url, type(e).__name__, e)
                    continue

        return None

    def _detect_parser(
        self, html: str, url: str, suggested_parser: Type[ModemParser] | None = None
    ) -> ModemParser | None:
        """
        Detect the parser for the modem with Phase 3 enhancements.

        Args:
            html: HTML content from modem
            url: URL that returned this HTML
            suggested_parser: Parser class suggested by URL pattern match (Tier 2/3)

        Returns:
            Parser instance or None

        Raises:
            ParserNotFoundError: If no parser matches after exhaustive search
        """
        if self.parser:
            return self.parser

        soup = BeautifulSoup(html, "html.parser")
        circuit_breaker = DiscoveryCircuitBreaker(max_attempts=15, timeout_seconds=90)
        attempted_parsers = []

        # Phase 3: Try anonymous probing first (for modems with public pages)
        _LOGGER.info("Phase 3: Attempting anonymous probing before authentication")
        for parser_class in self.parsers:
            if not circuit_breaker.should_continue():
                break

            try:
                anon_result = ParserHeuristics.check_anonymous_access(
                    self.base_url, parser_class, self.session, self.verify_ssl
                )
                if anon_result:
                    anon_html, anon_url = anon_result
                    anon_soup = BeautifulSoup(anon_html, "html.parser")
                    circuit_breaker.record_attempt(parser_class.name)

                    if parser_class.can_parse(anon_soup, anon_url, anon_html):
                        _LOGGER.info("✓ Detected modem via anonymous probing: %s (%s)",
                                     parser_class.name, parser_class.manufacturer)
                        return parser_class()
                    else:
                        attempted_parsers.append(parser_class.name)
            except Exception as e:
                _LOGGER.debug("Anonymous probing failed for %s: %s", parser_class.name, e)

        # If we have a suggested parser from URL matching, try it first
        if suggested_parser:
            if not circuit_breaker.should_continue():
                raise ParserNotFoundError(
                    modem_info={"title": soup.title.string if soup.title else "NO TITLE"},
                    attempted_parsers=attempted_parsers
                )

            try:
                circuit_breaker.record_attempt(suggested_parser.name)
                _LOGGER.debug("Testing suggested parser: %s", suggested_parser.name)
                if suggested_parser.can_parse(soup, url, html):
                    _LOGGER.info("Detected modem using suggested parser: %s (%s)",
                                 suggested_parser.name, suggested_parser.manufacturer)
                    return suggested_parser()
                else:
                    attempted_parsers.append(suggested_parser.name)
                    _LOGGER.debug("Suggested parser %s returned False for can_parse", suggested_parser.name)
            except Exception as e:
                _LOGGER.error(f"Suggested parser {suggested_parser.name} detection failed: {e}", exc_info=True)
                attempted_parsers.append(suggested_parser.name)

        # Phase 3: Use parser heuristics to narrow search space
        _LOGGER.info("Phase 3: Using parser heuristics to prioritize likely parsers")
        prioritized_parsers = ParserHeuristics.get_likely_parsers(
            self.base_url, self.parsers, self.session, self.verify_ssl
        )

        # Try parsers in prioritized order
        _LOGGER.debug("Attempting to detect parser from %s available parsers (prioritized)",
                      len(prioritized_parsers))
        for parser_class in prioritized_parsers:
            if not circuit_breaker.should_continue():
                break

            if suggested_parser and parser_class == suggested_parser:
                continue  # Already tried this one

            try:
                circuit_breaker.record_attempt(parser_class.name)
                _LOGGER.debug("Testing parser: %s", parser_class.name)
                if parser_class.can_parse(soup, url, html):
                    _LOGGER.info("✓ Detected modem: %s (%s)", parser_class.name, parser_class.manufacturer)
                    return parser_class()
                else:
                    attempted_parsers.append(parser_class.name)
                    _LOGGER.debug("Parser %s returned False for can_parse", parser_class.name)
            except Exception as e:
                _LOGGER.error(f"Parser {parser_class.name} detection failed with exception: {e}", exc_info=True)
                attempted_parsers.append(parser_class.name)

        # No parser matched - raise detailed error
        modem_info = {
            "title": soup.title.string if soup.title else "NO TITLE",
            "url": url,
        }
        _LOGGER.error("No parser matched after trying %s parsers. Title: %s",
                      len(attempted_parsers), modem_info["title"])

        raise ParserNotFoundError(
            modem_info=modem_info,
            attempted_parsers=attempted_parsers
        )

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
                try:
                    self.parser = self._detect_parser(html, successful_url, suggested_parser)
                except ParserNotFoundError as e:
                    _LOGGER.error("No compatible parser found: %s", e.get_user_message())
                    _LOGGER.info("Troubleshooting steps:\n%s",
                                 "\n".join(f"  - {step}" for step in e.get_troubleshooting_steps()))
                    # Re-raise so config_flow can show detailed error
                    raise

            if not self.parser:
                _LOGGER.error("No compatible parser found for modem at %s.", successful_url)
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
                    _LOGGER.debug("Using authenticated HTML from login (%s bytes)", len(html))
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

            # Use .get() with defaults to prevent KeyError
            downstream = data.get("downstream", [])
            upstream = data.get("upstream", [])
            system_info = data.get("system_info", {})

            total_corrected = sum(ch.get("corrected") or 0 for ch in downstream)
            total_uncorrected = sum(ch.get("uncorrected") or 0 for ch in downstream)

            # Prefix system_info keys with cable_modem_
            prefixed_system_info = {}
            for key, value in system_info.items():
                prefixed_key = f"cable_modem_{key}"
                prefixed_system_info[prefixed_key] = value

            return {
                "cable_modem_connection_status": "online" if (downstream or upstream) else "offline",
                "cable_modem_downstream": downstream,
                "cable_modem_upstream": upstream,
                "cable_modem_total_corrected": total_corrected,
                "cable_modem_total_uncorrected": total_uncorrected,
                "cable_modem_downstream_channel_count": len(downstream),
                "cable_modem_upstream_channel_count": len(upstream),
                **prefixed_system_info,
            }

        except Exception as e:
            _LOGGER.error("Error fetching modem data: %s", e)
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
            # Always fetch data to ensure we have the correct protocol (HTTP vs HTTPS)
            # This is critical because the saved config might have HTTPS but modem only supports HTTP
            _LOGGER.debug("restart_modem() called - about to fetch data")
            fetched_data = self._fetch_data()
            if not fetched_data:
                _LOGGER.error("Cannot restart modem: unable to connect")
                return False

            html, successful_url, suggested_parser = fetched_data
            _LOGGER.debug("Successfully fetched data from: %s, base_url is now: %s", successful_url, self.base_url)

            # Detect parser if not already set
            if not self.parser:
                self.parser = self._detect_parser(html, successful_url, suggested_parser)

                # Extract and update base_url from the successful_url to ensure protocol matches
                # This ensures restart operations use the same protocol that worked during detection
                from urllib.parse import urlparse
                parsed_url = urlparse(successful_url)
                self.base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                _LOGGER.debug("Updated base_url to %s from successful connection", self.base_url)

            if not self.parser:
                _LOGGER.error("Cannot restart modem: no parser detected")
                return False

            # Check if parser supports restart
            if not hasattr(self.parser, 'restart'):
                _LOGGER.error("Parser %s does not support restart functionality", self.parser.name)
                return False

            # Login if credentials provided
            if self.username and self.password:
                _LOGGER.debug("Attempting login with base_url: %s", self.base_url)
                login_result = self._login()
                # Handle both old-style bool and new-style tuple returns
                if isinstance(login_result, tuple):
                    success, _ = login_result
                    if not success:
                        _LOGGER.error("Cannot restart modem: login failed")
                        return False
                elif not login_result:
                    _LOGGER.error("Cannot restart modem: login failed")
                    return False

            # Perform restart
            _LOGGER.info("Attempting to restart modem using %s parser", self.parser.name)
            success = self.parser.restart(self.session, self.base_url)

            if success:
                _LOGGER.info("Modem restart command sent successfully")
            else:
                _LOGGER.error("Modem restart command failed")

            return success

        except Exception as e:
            _LOGGER.error("Error restarting modem: %s", e)
            return False
