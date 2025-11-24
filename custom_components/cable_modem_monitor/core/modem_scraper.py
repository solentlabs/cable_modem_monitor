"""Web scraper for cable modem data."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

import requests
from bs4 import BeautifulSoup

from ..parsers.base_parser import ModemParser
from .discovery_helpers import (
    DiscoveryCircuitBreaker,
    ParserHeuristics,
    ParserNotFoundError,
)

if TYPE_CHECKING:
    from ..parsers.base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)


class CapturingSession(requests.Session):
    """Session wrapper that captures responses for diagnostics."""

    def __init__(self, capture_callback: Callable[[requests.Response, str], None]):
        """Initialize capturing session.

        Args:
            capture_callback: Function to call with each response
        """
        super().__init__()
        self._capture_callback = capture_callback

    def request(self, method: str, url: str, **kwargs) -> requests.Response:  # type: ignore[override]
        """Override request to capture responses."""
        response = super().request(method, url, **kwargs)

        # Determine description based on URL
        description = "Parser fetch"
        if "login" in url.lower() or "auth" in url.lower():
            description = "Login/Auth page"
        elif "status" in url.lower():
            description = "Status page"
        elif "software" in url.lower() or "version" in url.lower():
            description = "Software info page"
        elif "log" in url.lower() or "event" in url.lower():
            description = "Event log page"
        elif "home" in url.lower():
            description = "Home page"

        self._capture_callback(response, description)
        return response


class ModemScraper:
    """Scrape data from cable modem web interface."""

    def __init__(
        self,
        host: str,
        username: str | None = None,
        password: str | None = None,
        parser: ModemParser | list[type[ModemParser]] | None = None,
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
        if host.startswith(("http://", "https://")):
            self.base_url = host.rstrip("/")
        elif cached_url and (cached_url.startswith("http://") or cached_url.startswith("https://")):
            # Optimization: Use protocol from cached working URL (skip protocol discovery)
            protocol = "https" if cached_url.startswith("https://") else "http"
            self.base_url = f"{protocol}://{host}"
            _LOGGER.debug("Using cached protocol %s from working URL: %s", protocol, cached_url)
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
            self.parsers: list[Any] = parser
            self.parser: ModemParser | None = None
        elif parser and isinstance(parser, type):
            # Parser class passed in
            self.parsers = [parser]
            self.parser = None
        elif parser:
            # Parser instance passed in
            self.parsers = [parser]
            self.parser = parser
        else:
            self.parsers = []
            self.parser = None

        self.cached_url = cached_url
        self.parser_name = parser_name  # For Tier 2: load cached parser by name
        self.last_successful_url = ""
        self._captured_urls: list[dict[str, Any]] = []  # For HTML capture feature
        self._capture_enabled: bool = False  # Flag to enable HTML capture

    def _capture_response(self, response: requests.Response, description: str = "") -> None:
        """Capture HTTP response for diagnostics.

        Args:
            response: The HTTP response to capture
            description: Optional description of what this request was for
        """
        if not self._capture_enabled:
            return

        try:
            # Normalize URL for deduplication
            from urllib.parse import urlparse, urlunparse

            def normalize_url(url: str) -> str:
                """Normalize URL for deduplication."""
                parsed = urlparse(url)
                # Remove fragment, normalize path
                path = parsed.path.rstrip("/") if parsed.path != "/" else "/"
                normalized = urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, ""))
                return normalized

            normalized_url = normalize_url(response.url)

            # Check if we've already captured this URL
            for existing in self._captured_urls:
                if normalize_url(existing["url"]) == normalized_url:
                    _LOGGER.debug(
                        "Skipping duplicate capture: %s (already captured as '%s')",
                        response.url,
                        existing["description"],
                    )
                    return

            # Get parser name if available
            parser_name = self.parser.name if self.parser else "unknown"

            self._captured_urls.append(
                {
                    "url": response.url,
                    "method": response.request.method if response.request else "GET",
                    "status_code": response.status_code,
                    "content_type": response.headers.get("Content-Type", "unknown"),
                    "size_bytes": len(response.text) if hasattr(response, "text") else 0,
                    "html": response.text if hasattr(response, "text") else "",
                    "parser": parser_name,
                    "description": description,
                }
            )
            _LOGGER.debug("Captured response: %s (%d bytes) - %s", response.url, len(response.text), description)
        except Exception as e:
            _LOGGER.warning(
                "Failed to capture response from %s: %s", response.url if hasattr(response, "url") else "unknown", e
            )

    def _fetch_parser_url_patterns(self) -> None:  # noqa: C901
        """Fetch all URLs defined in the parser's url_patterns.

        This ensures that all parser-defined URLs are captured, even if they're
        not linked from the main pages. This is critical for modems like the
        Netgear C3700 where DocsisStatus.htm is not linked but contains essential
        channel data.
        """
        if not self.parser:
            _LOGGER.debug("No parser available, skipping parser URL pattern fetch")
            return

        if not hasattr(self.parser, "url_patterns") or not self.parser.url_patterns:
            _LOGGER.debug("Parser %s has no url_patterns defined", self.parser.name)
            return

        _LOGGER.info("Fetching all %d URL patterns from parser: %s", len(self.parser.url_patterns), self.parser.name)

        for pattern in self.parser.url_patterns:
            path = pattern.get("path", "")
            if not path:
                continue

            url = f"{self.base_url}{path}"

            # Skip if already captured (avoid duplicates)
            from urllib.parse import urlparse, urlunparse

            def normalize_url(url_str: str) -> str:
                parsed = urlparse(url_str)
                path_normalized = parsed.path.rstrip("/") if parsed.path != "/" else "/"
                return urlunparse((parsed.scheme, parsed.netloc, path_normalized, parsed.params, parsed.query, ""))

            normalized_url = normalize_url(url)
            if any(normalize_url(item["url"]) == normalized_url for item in self._captured_urls):
                _LOGGER.debug("Skipping already captured URL: %s", url)
                continue

            try:
                _LOGGER.debug("Fetching parser URL pattern: %s", url)

                # Check if auth is required
                auth = None
                if (
                    pattern.get("auth_required", False)
                    and pattern.get("auth_method") == "basic"
                    and self.username
                    and self.password
                ):
                    auth = (self.username, self.password)
                    _LOGGER.debug("Using basic auth for %s", url)

                response = self.session.get(url, timeout=10, auth=auth)

                if response.status_code == 200:
                    self._capture_response(response, f"Parser URL pattern: {path}")
                    _LOGGER.debug("Successfully captured: %s (%d bytes)", url, len(response.text))
                else:
                    _LOGGER.debug("Got status %d from parser URL: %s", response.status_code, url)

            except Exception as e:
                _LOGGER.debug("Failed to fetch parser URL %s: %s", url, e)
                continue

        _LOGGER.info("Finished fetching parser URL patterns. Total captured: %d pages", len(self._captured_urls))

    def _crawl_additional_pages(self, max_pages: int = 20) -> None:
        """Crawl additional pages by following links found in captured HTML.

        This enhances HTML capture by automatically discovering and fetching
        additional modem pages that might contain useful information for
        parser development.

        Uses the reusable html_crawler utility for link discovery.

        Args:
            max_pages: Maximum number of additional pages to crawl (default 20)
        """
        from custom_components.cable_modem_monitor.lib.html_crawler import (
            discover_links_from_pages,
            get_new_links_to_crawl,
            normalize_url,
        )

        if not self._captured_urls:
            return

        _LOGGER.info("Starting link crawl to discover additional pages (max %d pages)", max_pages)

        # Get already captured URLs (normalized)
        captured_url_set = {normalize_url(item["url"]) for item in self._captured_urls}
        _LOGGER.debug("Already captured %d unique pages (normalized)", len(captured_url_set))

        # Discover all links from captured pages using utility
        discovered_links = discover_links_from_pages(self._captured_urls, self.base_url)

        # Get new links to crawl (not already captured)
        links_to_try = get_new_links_to_crawl(discovered_links, captured_url_set, max_pages)

        if not links_to_try:
            _LOGGER.info("No new links discovered to crawl")
            return

        _LOGGER.info("Found %d new links to crawl", len(links_to_try))

        # Crawl discovered links
        pages_crawled = 0
        for link_url in links_to_try:
            try:
                _LOGGER.debug("Crawling additional page: %s", link_url)
                response = self.session.get(link_url, timeout=5)

                if response.status_code == 200:
                    self._capture_response(response, "Link crawl")
                    pages_crawled += 1
                    _LOGGER.debug("Successfully captured: %s (%d bytes)", link_url, len(response.text))
                else:
                    _LOGGER.debug("Got status %d from: %s", response.status_code, link_url)

            except Exception as e:
                _LOGGER.debug("Failed to fetch %s: %s", link_url, e)
                continue

        total_captured = len(self._captured_urls)
        _LOGGER.info("Link crawl complete: captured %d additional pages (total: %d)", pages_crawled, total_captured)

    def _login(self) -> bool | tuple[bool, str | None]:
        """
        Log in to the modem web interface.

        Returns:
            bool: True if login successful (old style)
            tuple[bool, str | None]: (success, html) where html is authenticated page content
                                     or None if no credentials provided or login failed (new style)
        """
        if not self.username or not self.password:
            _LOGGER.debug("No credentials provided, skipping login")
            return True

        if not self.parser:
            _LOGGER.error("No parser detected, cannot log in")
            return False

        return self.parser.login(self.session, self.base_url, self.username, self.password)

    def _get_tier1_urls(self) -> list[tuple[str, str, type[ModemParser]]]:
        """Get URLs for Tier 1: User explicitly selected a parser."""
        if self.parser is None:
            raise RuntimeError("Tier 1 URLs requested but parser is None")
        _LOGGER.info("Tier 1: Using explicitly selected parser: %s", self.parser.name)
        urls = []
        for pattern in self.parser.url_patterns:
            url = f"{self.base_url}{pattern['path']}"
            urls.append((url, str(pattern["auth_method"]), type(self.parser)))
        return urls

    def _find_cached_parser(self) -> type[ModemParser] | None:
        """Find parser by name from available parsers."""
        for parser_class in self.parsers:
            if parser_class.name == self.parser_name:
                # Cast to type[ModemParser] to satisfy type checker
                return cast(type[ModemParser], parser_class)
        return None

    def _find_matching_pattern(self, url_patterns: list[dict], cached_url: str) -> dict | None:
        """Find pattern that matches cached URL, or return first pattern as fallback."""
        for pattern in url_patterns:
            path = pattern.get("path")
            if isinstance(path, str) and path in cached_url:
                return pattern
        return url_patterns[0] if url_patterns else None

    def _add_cached_url_if_matching(self, urls: list, cached_parser: type[ModemParser], cached_url: str) -> None:
        """Add cached URL to list if a matching pattern is found."""
        cached_pattern = self._find_matching_pattern(cached_parser.url_patterns, cached_url)
        if cached_pattern:
            urls.append((cached_url, cached_pattern["auth_method"], cached_parser))

    def _add_parser_urls(self, urls: list, parser_class: type[ModemParser], exclude_url: str | None = None) -> None:
        """Add URLs from a parser to the list, optionally excluding a specific URL."""
        for pattern in parser_class.url_patterns:
            url = f"{self.base_url}{pattern['path']}"
            if exclude_url is None or url != exclude_url:
                urls.append((url, pattern["auth_method"], parser_class))

    def _get_tier2_urls(self) -> list[tuple[str, str, type[ModemParser]]]:
        """Get URLs for Tier 2: Cached parser from previous detection."""
        _LOGGER.info("Tier 2: Looking for cached parser: %s", self.parser_name)
        cached_parser = self._find_cached_parser()
        if not cached_parser:
            return []

        # Cast to type[ModemParser] to satisfy type checker after None check
        parser = cached_parser
        _LOGGER.info("Found cached parser: %s", parser.name)
        urls: list[tuple[str, str, type[ModemParser]]] = []

        # Try cached URL first if available
        if self.cached_url:
            self._add_cached_url_if_matching(urls, parser, self.cached_url)

        # Add other URLs from cached parser
        self._add_parser_urls(urls, parser, exclude_url=self.cached_url)

        # Add other parsers as fallback (excluding fallback parser itself)
        for parser_class in self.parsers:
            if parser_class.name != self.parser_name:
                # Skip fallback parser - it should only be tried as last resort
                if parser_class.manufacturer == "Unknown":
                    continue
                # Cast to type[ModemParser] to satisfy type checker
                self._add_parser_urls(urls, cast(type[ModemParser], parser_class))

        return urls

    def _get_tier3_urls(self) -> list[tuple[str, str, type[ModemParser]]]:
        """Get URLs for Tier 3: Auto-detection mode - try all parsers.

        Note: Excludes fallback parser (Unknown manufacturer) from URL discovery.
        Fallback parser should only be tried as last resort during detection phases.
        """
        _LOGGER.info("Tier 3: Auto-detection mode - trying all parsers")
        urls = []

        # Try cached URL first with any compatible parser (excluding fallback)
        if self.cached_url:
            for parser_class in self.parsers:
                # Skip fallback parser - it should only be tried as last resort
                if parser_class.manufacturer == "Unknown":
                    continue

                for pattern in parser_class.url_patterns:
                    path = pattern.get("path")
                    if isinstance(path, str) and path in self.cached_url:
                        urls.append((self.cached_url, str(pattern["auth_method"]), parser_class))
                        break

        # Add all parser URLs (excluding fallback)
        for parser_class in self.parsers:
            # Skip fallback parser - it should only be tried as last resort during detection
            if parser_class.manufacturer == "Unknown":
                _LOGGER.debug("Skipping fallback parser in URL discovery: %s", parser_class.name)
                continue

            for pattern in parser_class.url_patterns:
                url = f"{self.base_url}{pattern['path']}"
                if url != self.cached_url:
                    urls.append((url, str(pattern["auth_method"]), parser_class))

        return urls

    def _get_url_patterns_to_try(self) -> list[tuple[str, str, type[ModemParser]]]:
        """
        Get list of (url, auth_method, parser_class) tuples to try.

        Returns URLs in priority order based on 3-tier strategy:
        1. If parser is set (user selected): use only that parser's URLs
        2. If parser_name cached: load that parser and use its URLs first
        3. Auto-detect mode: try all parsers' URLs
        """
        # Tier 1: User explicitly selected a parser
        if self.parser:
            return self._get_tier1_urls()

        # Tier 2: Cached parser from previous successful detection
        if self.parser_name and self.parsers:
            urls = self._get_tier2_urls()
            if urls:
                return urls

        # Tier 3: Auto-detection mode
        return self._get_tier3_urls()

    def _fetch_data(self, capture_raw: bool = False) -> tuple[str, str, type[ModemParser]] | None:
        """
        Fetch data from the modem using parser-defined URL patterns.
        Automatically tries both HTTPS and HTTP protocols.

        Args:
            capture_raw: If True, capture raw HTML responses for diagnostics

        Returns:
            tuple of (html, successful_url, parser_class) or None if failed
        """
        urls_to_try = self._get_url_patterns_to_try()

        if not urls_to_try:
            _LOGGER.error("No URL patterns available to try")
            return None

        # Try HTTPS first, then HTTP fallback for each URL
        protocols_to_try = ["https", "http"] if self.base_url.startswith("https://") else ["http"]
        _LOGGER.debug("Protocols to try: %s (base_url: %s)", protocols_to_try, self.base_url)

        for protocol in protocols_to_try:
            current_base_url = self.base_url.replace("https://", f"{protocol}://").replace("http://", f"{protocol}://")
            _LOGGER.debug("Trying protocol: %s (current_base_url: %s)", protocol, current_base_url)

            for url, auth_method, parser_class in urls_to_try:
                # Replace protocol in URL to match current attempt
                url = url.replace(self.base_url, current_base_url)

                try:
                    _LOGGER.debug(
                        "Attempting to fetch %s (auth: %s, parser: %s)",
                        url,
                        auth_method,
                        parser_class.name if parser_class else "unknown",
                    )
                    auth = None
                    if auth_method == "basic" and self.username and self.password:
                        auth = (self.username, self.password)

                    # Use configured SSL verification setting
                    response = self.session.get(url, timeout=10, auth=auth, verify=self.verify_ssl)

                    if response.status_code == 200:
                        parser_name = parser_class.name if parser_class else "unknown"
                        _LOGGER.info(
                            "Successfully connected to %s (HTML: %s bytes, parser: %s)",
                            url,
                            len(response.text),
                            parser_name,
                        )
                        self.last_successful_url = url

                        # Capture raw HTML if requested
                        self._capture_response(response, "Initial connection page")

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

    def _try_anonymous_probing(self, circuit_breaker, attempted_parsers: list) -> ModemParser | None:
        """Try anonymous probing for modems with public pages.

        Note: Excludes fallback parser - only tries real modem parsers.
        """
        _LOGGER.info("Phase 1: Attempting anonymous probing before authentication")

        for parser_class in self.parsers:
            # Skip fallback parser - it should only be used as last resort
            if parser_class.manufacturer == "Unknown":
                continue

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
                        _LOGGER.info(
                            "✓ Detected modem via anonymous probing: %s (%s)",
                            parser_class.name,
                            parser_class.manufacturer,
                        )
                        return cast(type[ModemParser], parser_class)()
                    else:
                        attempted_parsers.append(parser_class.name)
            except Exception as e:
                _LOGGER.debug("Anonymous probing failed for %s: %s", parser_class.name, e)

        return None

    def _try_suggested_parser(
        self, soup, url: str, html: str, suggested_parser, circuit_breaker, attempted_parsers: list
    ) -> ModemParser | None:
        """Try the suggested parser from URL pattern matching."""
        if not suggested_parser:
            return None

        if not circuit_breaker.should_continue():
            raise ParserNotFoundError(
                modem_info={"title": soup.title.string if soup.title else "NO TITLE"},
                attempted_parsers=attempted_parsers,
            )

        try:
            circuit_breaker.record_attempt(suggested_parser.name)
            _LOGGER.debug("Testing suggested parser: %s", suggested_parser.name)
            if suggested_parser.can_parse(soup, url, html):
                _LOGGER.info(
                    "Detected modem using suggested parser: %s (%s)",
                    suggested_parser.name,
                    suggested_parser.manufacturer,
                )
                return cast(type[ModemParser], suggested_parser)()
            else:
                attempted_parsers.append(suggested_parser.name)
                _LOGGER.debug("Suggested parser %s returned False for can_parse", suggested_parser.name)
        except Exception as e:
            _LOGGER.error(f"Suggested parser {suggested_parser.name} detection failed: {e}", exc_info=True)
            attempted_parsers.append(suggested_parser.name)

        return None

    def _try_prioritized_parsers(
        self, soup, url: str, html: str, suggested_parser, circuit_breaker, attempted_parsers: list
    ) -> ModemParser | None:
        """Try parsers in prioritized order using heuristics.

        Note: Excludes fallback parser - only tries real modem parsers.
        """
        _LOGGER.info("Phase 3: Using parser heuristics to prioritize likely parsers")
        prioritized_parsers = ParserHeuristics.get_likely_parsers(
            self.base_url, self.parsers, self.session, self.verify_ssl
        )

        _LOGGER.debug("Attempting to detect parser from %s available parsers (prioritized)", len(prioritized_parsers))

        for parser_class in prioritized_parsers:
            # Skip fallback parser - it should only be used as last resort
            if parser_class.manufacturer == "Unknown":
                _LOGGER.debug("Skipping fallback parser in detection: %s", parser_class.name)
                continue

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

        return None

    def _detect_parser(
        self, html: str, url: str, suggested_parser: type[ModemParser] | None = None
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
        attempted_parsers: list[str] = []

        # Try anonymous probing first
        parser = self._try_anonymous_probing(circuit_breaker, attempted_parsers)
        if parser:
            return parser

        # Try suggested parser from URL matching
        parser = self._try_suggested_parser(soup, url, html, suggested_parser, circuit_breaker, attempted_parsers)
        if parser:
            return parser

        # Try prioritized parsers using heuristics
        parser = self._try_prioritized_parsers(soup, url, html, suggested_parser, circuit_breaker, attempted_parsers)
        if parser:
            return parser

        # No parser matched - raise detailed error
        # User can manually select "Unknown Modem (Fallback Mode)" from the list
        modem_info = {
            "title": soup.title.string if soup.title else "NO TITLE",
            "url": url,
        }
        _LOGGER.error(
            "No parser matched after trying %s parsers: %s. Modem title: %s",
            len(attempted_parsers),
            ", ".join(attempted_parsers) if attempted_parsers else "none",
            modem_info["title"],
        )

        raise ParserNotFoundError(modem_info=modem_info, attempted_parsers=attempted_parsers)

    def _parse_data(self, html: str) -> dict:
        """Parse data from the modem."""
        if self.parser is None:
            raise RuntimeError("Cannot parse data: parser is not set")
        soup = BeautifulSoup(html, "html.parser")
        # Pass session and base_url to parser in case it needs to fetch additional pages
        data = self.parser.parse(soup, session=self.session, base_url=self.base_url)
        return data

    def get_modem_data(self, capture_raw: bool = False) -> dict:
        """Fetch and parse modem data.

        Args:
            capture_raw: If True, capture raw HTML responses for diagnostics

        Returns:
            Dictionary with modem data and optionally raw HTML captures
        """
        # Clear previous captures and enable capture mode
        self._captured_urls = []
        self._capture_enabled = capture_raw

        # Replace session with capturing session if capture is enabled
        original_session = None
        if capture_raw:
            original_session = self.session
            self.session = CapturingSession(self._capture_response)
            # Copy SSL verification settings to capturing session
            self.session.verify = original_session.verify
            _LOGGER.debug("Enabled HTML capture mode with CapturingSession")

        try:
            fetched_data = self._fetch_data(capture_raw=capture_raw)
            if not fetched_data:
                return self._create_error_response("unreachable")

            html, successful_url, suggested_parser = fetched_data

            # Detect or instantiate parser
            if not self._ensure_parser(html, successful_url, suggested_parser):
                return self._create_error_response("offline")

            # Login and get authenticated HTML
            html_or_none = self._handle_login_result(html)
            if html_or_none is None:
                return self._create_error_response("unreachable")
            html = html_or_none

            # Parse data and build response
            data = self._parse_data(html)
            response = self._build_response(data)

            # Capture additional pages if in capture mode
            if capture_raw and self._captured_urls:
                # First, fetch all URLs defined in the parser's url_patterns
                # This ensures we get critical pages like DocsisStatus.htm that may not be linked
                self._fetch_parser_url_patterns()

                # Then crawl for additional pages by following links
                self._crawl_additional_pages()

            # Include captured HTML if requested
            if capture_raw and self._captured_urls:
                from datetime import datetime, timedelta

                response["_raw_html_capture"] = {
                    "timestamp": datetime.now().isoformat(),
                    "trigger": "manual",
                    "ttl_expires": (datetime.now() + timedelta(minutes=5)).isoformat(),
                    "urls": self._captured_urls,
                }
                _LOGGER.info("Captured %d HTML pages for diagnostics", len(self._captured_urls))

            return response

        except Exception as e:
            _LOGGER.error("Error fetching modem data: %s", e)
            return self._create_error_response("unreachable")
        finally:
            # Restore original session if we replaced it
            if original_session is not None:
                self.session = original_session
                _LOGGER.debug("Restored original session")

    def _create_error_response(self, status: str) -> dict:
        """Create error response dictionary."""
        return {"cable_modem_connection_status": status, "cable_modem_downstream": [], "cable_modem_upstream": []}

    def _ensure_parser(self, html: str, successful_url: str, suggested_parser: type[ModemParser] | None) -> bool:
        """Ensure parser is detected or instantiated.

        Returns:
            True if parser is available, False otherwise
        """
        if self.parser:
            return True

        try:
            self.parser = self._detect_parser(html, successful_url, suggested_parser)
        except ParserNotFoundError as e:
            _LOGGER.error("No compatible parser found: %s", e.get_user_message())
            _LOGGER.info(
                "Troubleshooting steps:\n%s", "\n".join(f"  - {step}" for step in e.get_troubleshooting_steps())
            )
            # Re-raise so config_flow can show detailed error
            raise

        if not self.parser:
            _LOGGER.error("No compatible parser found for modem at %s.", successful_url)
            return False

        return True

    def _handle_login_result(self, html: str) -> str | None:
        """Handle login result and return authenticated HTML if available.

        Returns:
            HTML string (possibly updated from login) or None if login failed
        """
        login_result = self._login()

        if isinstance(login_result, tuple):
            success, authenticated_html = login_result
            if not success:
                _LOGGER.error("Failed to log in to modem")
                return None
            # Use the authenticated HTML from login if available
            if authenticated_html:
                _LOGGER.debug("Using authenticated HTML from login (%s bytes)", len(authenticated_html))
                return authenticated_html
            return html
        else:
            # Old-style boolean return for parsers that don't return HTML
            if not login_result:
                _LOGGER.error("Failed to log in to modem")
                return None
            return html

    def _build_response(self, data: dict) -> dict:
        """Build response dictionary from parsed data."""
        downstream = data.get("downstream", [])
        upstream = data.get("upstream", [])
        system_info = data.get("system_info", {})

        total_corrected = sum(ch.get("corrected") or 0 for ch in downstream)
        total_uncorrected = sum(ch.get("uncorrected") or 0 for ch in downstream)

        # Determine connection status
        # If fallback mode is active (unsupported modem), use "limited" status
        # This allows installation to succeed without showing dummy channel data
        if system_info.get("fallback_mode"):
            status = "limited"
        elif not downstream and not upstream:
            # Known parser detected but extracted no channel data
            # This could happen if: modem in bridge mode, parser bug, HTML format changed
            status = "parser_issue"
            # Add helpful status message if not already present
            if "status_message" not in system_info:
                parser_name = self.parser.name if self.parser else "Unknown"
                system_info["status_message"] = (
                    f"⚠️  Parser Issue: No Channel Data\n\n"
                    f"Connected to {parser_name}, but unable to extract channel data.\n\n"
                    f"Possible causes:\n"
                    f"• Modem is in bridge mode (no RF data available)\n"
                    f"• Modem firmware changed HTML structure\n"
                    f"• Modem still initializing after reboot\n\n"
                    f"What you can do:\n"
                    f"1. Check if modem is in bridge mode (contact ISP)\n"
                    f"2. Click 'Capture HTML' to help debug parser\n"
                    f"3. Wait a few minutes if modem just rebooted"
                )
        else:
            # Normal operation - parser found channel data
            status = "online"

        # Prefix system_info keys with cable_modem_
        prefixed_system_info = {f"cable_modem_{key}": value for key, value in system_info.items()}

        return {
            "cable_modem_connection_status": status,
            "cable_modem_downstream": downstream,
            "cable_modem_upstream": upstream,
            "cable_modem_total_corrected": total_corrected,
            "cable_modem_total_uncorrected": total_uncorrected,
            "cable_modem_downstream_channel_count": len(downstream),
            "cable_modem_upstream_channel_count": len(upstream),
            **prefixed_system_info,
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
            if not self._prepare_for_restart():
                return False

            if not self._validate_restart_capability():
                return False

            if not self._perform_restart_login():
                return False

            return self._execute_restart()

        except Exception as e:
            _LOGGER.error("Error restarting modem: %s", e)
            return False

    def _prepare_for_restart(self) -> bool:
        """Prepare for restart by fetching data and detecting parser.

        Returns:
            True if preparation successful, False otherwise
        """
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
            self._update_base_url_from_successful_url(successful_url)

        if not self.parser:
            _LOGGER.error("Cannot restart modem: no parser detected")
            return False

        return True

    def _update_base_url_from_successful_url(self, successful_url: str) -> None:
        """Update base_url from successful URL to ensure protocol matches."""
        from urllib.parse import urlparse

        parsed_url = urlparse(successful_url)
        self.base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        _LOGGER.debug("Updated base_url to %s from successful connection", self.base_url)

    def _validate_restart_capability(self) -> bool:
        """Validate that parser supports restart functionality.

        Returns:
            True if parser supports restart, False otherwise
        """
        if self.parser is None:
            _LOGGER.warning("Cannot validate restart capability: parser is not set")
            return False
        if not hasattr(self.parser, "restart"):
            _LOGGER.warning("Parser %s does not support restart functionality", self.parser.name)
            return False
        return True

    def _perform_restart_login(self) -> bool:
        """Perform login if credentials are provided.

        Returns:
            True if login successful or not needed, False if login failed
        """
        if not self.username or not self.password:
            return True

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

        return True

    def _execute_restart(self) -> bool:
        """Execute the restart command.

        Returns:
            True if restart command succeeded, False otherwise
        """
        if self.parser is None:
            _LOGGER.error("Cannot execute restart: parser is not set")
            return False
        _LOGGER.info("Attempting to restart modem using %s parser", self.parser.name)
        # Use getattr to access restart method dynamically (not all parsers support it)
        restart_method = getattr(self.parser, "restart", None)
        if restart_method is None:
            _LOGGER.error("Parser does not support restart functionality")
            return False
        success: bool = restart_method(self.session, self.base_url)

        if success:
            _LOGGER.info("Modem restart command sent successfully")
        else:
            _LOGGER.error("Modem restart command failed")

        return success
