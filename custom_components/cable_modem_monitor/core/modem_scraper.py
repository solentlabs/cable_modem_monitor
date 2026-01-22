"""Web scraper for cable modem data.

This module provides the ModemScraper class for fetching and parsing data from
cable modem web interfaces. It handles authentication, parser detection, and
multi-page data collection.

Architecture:
    ModemScraper is used in two contexts:

    1. **Polling (every 30s)** - Uses stored config from discovery:
       - auth_strategy, auth_form_config, etc. from config entry
       - parser_name to load cached parser directly
       - cached_url for fast path (skip URL discovery)

    2. **Discovery (config_flow)** - Full auto-detection:
       - Tiered URL probing (Tier 1: cached, Tier 2: index, Tier 3: fallback)
       - Parser detection via login_markers and model_strings
       - Auth discovery via AuthHandler

URL Discovery Tiers:
    Tier 1: Cached URL + parser (instant, from previous success)
    Tier 2: Index-driven (modem.yaml URL patterns for detected parser)
    Tier 3: Fallback paths (/index.html, /home.html, etc.)

Parser Detection:
    1. Instant detection - Use authenticated_html from auth discovery
    2. Login markers - Match pre-auth HTML against modem.yaml markers
    3. Model strings - Match post-auth HTML for disambiguation
    4. Heuristics - Last resort pattern matching

Key Classes:
    ModemScraper: Main scraper class
    CapturingSession: Session wrapper for diagnostics capture

See Also:
    - core/discovery/pipeline.py: Discovery orchestration (runs before scraper)
    - core/auth/handler.py: Authentication execution
    - core/base_parser.py: Parser base class
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

import requests
from bs4 import BeautifulSoup

from ..const import DEFAULT_TIMEOUT
from ..modem_config.adapter import get_auth_adapter_for_parser, get_url_patterns_for_parser
from .actions import ActionFactory, ActionType
from .auth.handler import AuthHandler
from .auth.types import AuthStrategyType
from .base_parser import ModemParser
from .discovery_helpers import (
    DiscoveryCircuitBreaker,
    HintMatcher,
    ParserHeuristics,
    ParserNotFoundError,
)
from .loaders import ResourceLoaderFactory

# Import ssl_adapter to ensure SSL warning suppression is active.
# The suppression is centralized there - see ssl_adapter.py docstring.
from .ssl_adapter import LegacySSLAdapter  # noqa: F401

if TYPE_CHECKING:
    from .base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)


def _get_parser_url_patterns(parser_or_class: ModemParser | type[ModemParser]) -> list[dict]:
    """Get URL patterns from modem.yaml (preferred) or parser class (fallback).

    Args:
        parser_or_class: Parser instance or class

    Returns:
        List of URL pattern dicts, or empty list if none found.
    """
    # Get class name - handle Mock objects in tests
    try:
        if isinstance(parser_or_class, type):
            class_name = parser_or_class.__name__
        else:
            class_name = parser_or_class.__class__.__name__
    except AttributeError:
        # Mock objects may not have __name__
        class_name = None

    # Try modem.yaml first (skip if we couldn't get class name)
    if class_name:
        patterns = get_url_patterns_for_parser(class_name)
        if patterns:
            return patterns

    # Fall back to parser class attribute
    if hasattr(parser_or_class, "url_patterns") and parser_or_class.url_patterns:
        return list(parser_or_class.url_patterns)

    return []


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

        # Determine description based on URL and request headers
        description = "Parser fetch"

        # Check for HNAP/SOAP requests (uses SOAPAction header)
        headers = kwargs.get("headers", {})
        soap_action = headers.get("SOAPAction", "")
        if soap_action or "/hnap" in url.lower():
            # Extract action name from SOAPAction header (e.g., '"http://...Login"' -> 'Login')
            action_name = soap_action.strip('"').split("/")[-1] if soap_action else "unknown"
            description = f"HNAP: {action_name}"
        elif "login" in url.lower() or "auth" in url.lower():
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
    """Scrape data from cable modem web interface.

    This class handles the complete data fetch cycle:
    1. Authentication (via AuthHandler with stored strategy)
    2. Page fetching (base page + additional pages from modem.yaml)
    3. Data parsing (via detected/cached ModemParser)

    For polling, construct with stored config entry values (fast path).
    For discovery, construct with minimal params and call get_modem_data().

    Main entry point: get_modem_data() -> dict with downstream/upstream channels
    """

    def __init__(
        self,
        host: str,
        username: str | None = None,
        password: str | None = None,
        parser: ModemParser | list[type[ModemParser]] | None = None,
        cached_url: str | None = None,
        parser_name: str | None = None,
        verify_ssl: bool = False,
        legacy_ssl: bool = False,
        auth_strategy: str | None = None,
        auth_form_config: dict[str, Any] | None = None,
        auth_hnap_config: dict[str, Any] | None = None,
        auth_url_token_config: dict[str, Any] | None = None,
        authenticated_html: str | None = None,
        session_pre_authenticated: bool = False,
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
            legacy_ssl: Use legacy SSL ciphers (SECLEVEL=0) for older modem firmware
            auth_strategy: Discovered auth strategy type (from config entry)
            auth_form_config: Form configuration for form-based auth (from config entry)
            auth_hnap_config: HNAP configuration (endpoint, namespace) from config entry
            auth_url_token_config: URL token configuration (login_prefix, etc.) from config entry
            authenticated_html: Pre-fetched HTML from auth discovery (for instant parser detection)
            session_pre_authenticated: Session is already authenticated from auth discovery (skip _login)
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
        self.legacy_ssl = legacy_ssl
        self.session = requests.Session()

        # Mount legacy SSL adapter for HTTPS if needed (older modem firmware)
        if legacy_ssl and self.base_url.startswith("https://"):
            self.session.mount("https://", LegacySSLAdapter())
            _LOGGER.info("Legacy SSL cipher support enabled (SECLEVEL=0) for older modem firmware")

        # Configure SSL verification
        # Note: SSL warning suppression is handled globally by ssl_adapter.py
        if not self.verify_ssl:
            self.session.verify = False
            _LOGGER.debug(
                "SSL certificate verification disabled (common for cable modems with self-signed certificates)"
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
        self._failed_urls: list[dict[str, Any]] = []  # Track failed fetches for diagnostics
        self._capture_enabled: bool = False  # Flag to enable HTML capture

        # Auth strategy from config entry
        # This enables response-driven auth during polling
        self._auth_handler = AuthHandler(
            strategy=auth_strategy,
            form_config=auth_form_config,
            hnap_config=auth_hnap_config,
            url_token_config=auth_url_token_config,
        )
        self._auth_strategy = auth_strategy

        # Pre-fetched HTML from auth discovery for instant parser detection
        self._authenticated_html = authenticated_html

        # Flag to skip _login() when session was pre-authenticated by auth discovery
        self._session_pre_authenticated = session_pre_authenticated

        _LOGGER.debug(
            "Scraper initialized with auth strategy: %s, pre-fetched HTML: %s",
            self._auth_handler.strategy.value if self._auth_handler else "none",
            "yes" if authenticated_html else "no",
        )

    def clear_auth_cache(self) -> None:
        """Clear cached authentication and create fresh session.

        Call this after modem restart to force re-authentication on next poll.
        The modem invalidates all sessions on reboot, so cached credentials
        and session cookies become stale, causing 500 errors.
        """
        import requests as req

        # Close old session to release connections
        # This is critical for single-session modems that reject concurrent connections
        old_verify = self.session.verify if hasattr(self.session, "verify") else not self.verify_ssl
        with contextlib.suppress(Exception):
            self.session.close()

        # Create fresh session
        self.session = req.Session()
        self.session.verify = old_verify

        # Clear HNAP builder auth cache via auth handler (not parser)
        if self._auth_handler:
            hnap_builder = self._auth_handler.get_hnap_builder()
            if hnap_builder:
                hnap_builder.clear_auth_cache()

        _LOGGER.debug("Cleared auth cache and created fresh session")

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

            # Capture timing data for performance analysis
            elapsed_ms = response.elapsed.total_seconds() * 1000 if hasattr(response, "elapsed") else None

            self._captured_urls.append(
                {
                    "url": response.url,
                    "method": response.request.method if response.request else "GET",
                    "status_code": response.status_code,
                    "content_type": response.headers.get("Content-Type", "unknown"),
                    "size_bytes": len(response.text) if hasattr(response, "text") else 0,
                    "elapsed_ms": elapsed_ms,
                    "content": response.text if hasattr(response, "text") else "",
                    "parser": parser_name,
                    "description": description,
                }
            )
            _LOGGER.debug("Captured response: %s (%d bytes) - %s", response.url, len(response.text), description)
        except (AttributeError, TypeError, KeyError) as e:
            # Intentionally broad: capture can fail due to malformed response objects
            _LOGGER.warning(
                "Failed to capture response from %s: %s", response.url if hasattr(response, "url") else "unknown", e
            )

    def _record_failed_url(
        self,
        url: str,
        reason: str,
        status_code: int | None = None,
        exception_type: str | None = None,
        resource_type: str = "unknown",
        response_body: str | None = None,
    ) -> None:
        """Record a failed URL fetch for diagnostics.

        Args:
            url: The URL that failed to fetch
            reason: Human-readable reason for failure
            status_code: HTTP status code if available
            exception_type: Exception class name if applicable
            resource_type: Type of resource (html, javascript, etc.)
            response_body: Response body content (for error pages like session conflicts)
        """
        if not self._capture_enabled:
            return

        from datetime import datetime

        entry = {
            "url": url,
            "reason": reason,
            "status_code": status_code,
            "exception_type": exception_type,
            "resource_type": resource_type,
            "timestamp": datetime.now().isoformat(),
        }
        # Include response body for error pages - helps diagnose session conflicts, auth errors, etc.
        if response_body:
            entry["content"] = response_body
            entry["size_bytes"] = len(response_body)

        self._failed_urls.append(entry)
        _LOGGER.debug("Recorded failed URL: %s - %s", url, reason)

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

        url_patterns = _get_parser_url_patterns(self.parser)
        if not url_patterns:
            _LOGGER.debug("Parser %s has no url_patterns defined", self.parser.name)
            return

        _LOGGER.info("Fetching all %d URL patterns from parser: %s", len(url_patterns), self.parser.name)

        for pattern in url_patterns:
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
                continue  # Already captured, skip silently

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

                response = self.session.get(url, timeout=DEFAULT_TIMEOUT, auth=auth)

                if response.status_code == 200:
                    self._capture_response(response, f"Parser URL pattern: {path}")
                    _LOGGER.debug("Successfully captured: %s (%d bytes)", url, len(response.text))
                else:
                    _LOGGER.debug("Got status %d from parser URL: %s", response.status_code, url)
                    self._record_failed_url(
                        url=url,
                        reason=f"HTTP {response.status_code}",
                        status_code=response.status_code,
                        resource_type="parser_pattern",
                        response_body=response.text if hasattr(response, "text") else None,
                    )

            except requests.RequestException as e:
                _LOGGER.debug("Failed to fetch parser URL %s: %s", url, e)
                self._record_failed_url(
                    url=url,
                    reason=str(e),
                    exception_type=type(e).__name__,
                    resource_type="parser_pattern",
                )
                continue

        _LOGGER.info("Finished fetching parser URL patterns. Total captured: %d pages", len(self._captured_urls))

    def _crawl_additional_pages(self, max_pages: int = 50) -> None:  # noqa: C901
        """Comprehensive crawl to capture ALL modem resources.

        Modern cable modem UIs use JavaScript to dynamically build navigation.
        Simple <a href> extraction misses most pages. This method:

        1. Extracts JS/CSS/fragment references from HTML
        2. Fetches JS files and parses them for URL patterns (menu configs, etc.)
        3. Fetches discovered HTML pages and fragments
        4. Repeats until no new resources are found

        This builds a comprehensive fixture database for parser development.

        Args:
            max_pages: Maximum total resources to capture (default 50)
        """
        from custom_components.cable_modem_monitor.lib.html_crawler import (
            RESOURCE_TYPE_API,
            RESOURCE_TYPE_CSS,
            RESOURCE_TYPE_FRAGMENT,
            RESOURCE_TYPE_HTML,
            RESOURCE_TYPE_JS,
            discover_all_resources,
            normalize_url,
        )

        if not self._captured_urls:
            return

        _LOGGER.info("Starting comprehensive resource capture (max %d resources)", max_pages)

        # Track what we've already captured (normalized URLs)
        captured_url_set = {normalize_url(item["url"]) for item in self._captured_urls}
        total_fetched = 0
        iteration = 0
        max_iterations = 5  # Prevent infinite loops

        while iteration < max_iterations and total_fetched < max_pages:
            iteration += 1
            _LOGGER.info("Discovery iteration %d (captured so far: %d)", iteration, len(captured_url_set))

            # Discover all resources from currently captured pages
            resources = discover_all_resources(self._captured_urls, self.base_url)

            # Collect all URLs to try, prioritized by type
            # Priority: JS first (contains menu configs), then fragments, then HTML, then CSS
            urls_to_try: list[tuple[str, str]] = []

            for url in resources[RESOURCE_TYPE_JS]:
                if normalize_url(url) not in captured_url_set:
                    urls_to_try.append((url, "javascript"))

            for url in resources[RESOURCE_TYPE_FRAGMENT]:
                if normalize_url(url) not in captured_url_set:
                    urls_to_try.append((url, "fragment"))

            for url in resources[RESOURCE_TYPE_HTML]:
                if normalize_url(url) not in captured_url_set:
                    urls_to_try.append((url, "html"))

            for url in resources[RESOURCE_TYPE_CSS]:
                if normalize_url(url) not in captured_url_set:
                    urls_to_try.append((url, "stylesheet"))

            # Also try API endpoints (best effort)
            for url in resources[RESOURCE_TYPE_API]:
                if normalize_url(url) not in captured_url_set:
                    urls_to_try.append((url, "api"))

            if not urls_to_try:
                _LOGGER.info("No new resources discovered in iteration %d", iteration)
                break

            _LOGGER.info("Found %d new resources to fetch in iteration %d", len(urls_to_try), iteration)

            # Fetch discovered resources
            fetched_this_iteration = 0
            for url, resource_type in urls_to_try:
                if total_fetched >= max_pages:
                    _LOGGER.info("Reached max_pages limit (%d)", max_pages)
                    break

                try:
                    _LOGGER.debug("Fetching %s: %s", resource_type, url)
                    response = self.session.get(url, timeout=DEFAULT_TIMEOUT)

                    if response.status_code == 200:
                        # Capture with resource type info
                        description = f"Comprehensive crawl: {resource_type}"
                        self._capture_response(response, description)
                        captured_url_set.add(normalize_url(url))
                        total_fetched += 1
                        fetched_this_iteration += 1
                        _LOGGER.debug(
                            "Captured %s (%d bytes): %s",
                            resource_type,
                            len(response.text),
                            url,
                        )
                    else:
                        _LOGGER.debug("Got status %d from %s: %s", response.status_code, resource_type, url)
                        self._record_failed_url(
                            url=url,
                            reason=f"HTTP {response.status_code}",
                            status_code=response.status_code,
                            resource_type=resource_type,
                            response_body=response.text if hasattr(response, "text") else None,
                        )

                except requests.RequestException as e:
                    _LOGGER.debug("Failed to fetch %s %s: %s", resource_type, url, e)
                    self._record_failed_url(
                        url=url,
                        reason=str(e),
                        exception_type=type(e).__name__,
                        resource_type=resource_type,
                    )
                    continue

            _LOGGER.info(
                "Iteration %d complete: fetched %d new resources",
                iteration,
                fetched_this_iteration,
            )

            # If we didn't fetch anything new, stop
            if fetched_this_iteration == 0:
                break

        # Final summary
        total_captured = len(self._captured_urls)
        _LOGGER.info(
            "Comprehensive capture complete: %d total resources captured in %d iterations",
            total_captured,
            iteration,
        )

    def _login(self) -> tuple[bool, str | None]:  # noqa: C901
        """
        Log in to the modem web interface.

        Uses the auth handler with the stored strategy.
        Falls back to parser hints or parser.login() for old config entries.

        Returns:
            tuple[bool, str | None]: (success, authenticated_html)
                - success: True if login succeeded or no login required
                - authenticated_html: HTML from login response, or None
        """
        if not self.username or not self.password:
            _LOGGER.debug("No credentials provided, skipping login")
            return (True, None)

        # Skip login if session was pre-authenticated by auth discovery
        # This avoids redundant authentication during config flow validation
        if self._session_pre_authenticated:
            _LOGGER.debug("Session pre-authenticated by auth discovery, skipping login")
            # Clear flag after first use (subsequent polls need re-auth)
            self._session_pre_authenticated = False
            return (True, None)

        # Use auth handler if we have a stored strategy
        if self._auth_handler and self._auth_strategy:
            # If strategy is UNKNOWN but parser has hints, use hints instead of logging warning
            result = self._try_parser_hints_for_unknown_strategy()
            if result is not None:
                return result

            _LOGGER.debug(
                "Using auth handler with strategy: %s",
                self._auth_handler.strategy.value,
            )
            auth_result = self._auth_handler.authenticate(self.session, self.base_url, self.username, self.password)

            if auth_result.success:
                return auth_result.success, auth_result.response_html

            # Stored strategy failed - try parser hints fallback
            # This handles cases where discovery found form_plain but parser needs form_base64
            if not auth_result.success and self.parser:
                _LOGGER.info(
                    "Stored auth strategy %s failed (error: %s), trying parser hints fallback",
                    self._auth_handler.strategy.value,
                    auth_result.error_type.value if auth_result.error_type else "unknown",
                )
                result = self._login_with_parser_hints()
                if result is not None:
                    return result

            return auth_result.success, auth_result.response_html

        # No auth strategy stored - try parser hints fallback
        if self.parser:
            result = self._login_with_parser_hints()
            if result is not None:
                return result

        # No auth strategy or parser hints - assume no authentication required
        # This handles modems that don't need login (e.g., status pages are public)
        _LOGGER.debug("No auth strategy or parser hints found, assuming no auth required")
        return (True, None)

    def _create_loader(self):
        """Create a resource loader based on parser's modem.yaml config.

        Returns:
            ResourceLoader instance, or None if config not available.
        """
        if not self.parser:
            return None

        adapter = get_auth_adapter_for_parser(self.parser.__class__.__name__)
        if not adapter:
            _LOGGER.debug("No modem.yaml adapter for %s, using legacy parse path", self.parser.name)
            return None

        try:
            modem_config = adapter.get_modem_config_dict()
            url_token_config = adapter.get_url_token_config_for_loader()
            hnap_builder = self._auth_handler.get_hnap_builder() if self._auth_handler else None

            fetcher = ResourceLoaderFactory.create(
                session=self.session,
                base_url=self.base_url,
                modem_config=modem_config,
                verify_ssl=self.verify_ssl,
                hnap_builder=hnap_builder,
                url_token_config=url_token_config,
            )
            _LOGGER.debug("Created %s for %s", fetcher.__class__.__name__, self.parser.name)
            return fetcher
        except (KeyError, TypeError, ValueError, AttributeError) as e:
            # Intentionally broad: loader creation depends on config structure
            _LOGGER.warning("Failed to create loader for %s: %s", self.parser.name, e)
            return None

    def _load_resources(self, loader) -> dict[str, Any]:
        """Fetch all resources using the loader.

        Args:
            loader: ResourceLoader instance

        Returns:
            Dict of resources, or empty dict on failure.
        """
        try:
            resources: dict[str, Any] = loader.fetch()
            _LOGGER.debug(
                "Fetched %d resources: %s",
                len(resources),
                list(resources.keys())[:5],  # Log first 5 keys
            )
            return resources
        except (requests.RequestException, KeyError, TypeError, ValueError) as e:
            # Intentionally broad: loading can fail via network or parsing issues
            _LOGGER.warning("Loader failed: %s", e)
            return {}

    def _try_parser_hints_for_unknown_strategy(self) -> tuple[bool, str | None] | None:
        """Try parser hints when auth strategy is UNKNOWN.

        Returns:
            tuple[bool, str | None] if hints were found and auth succeeded
            None if strategy is not UNKNOWN, no hints, or auth failed (caller continues)
        """
        if not self._auth_handler or self._auth_handler.strategy != AuthStrategyType.UNKNOWN:
            return None

        if not self.parser:
            return None

        _LOGGER.debug("Auth strategy is UNKNOWN, checking for parser hints first")
        result = self._login_with_parser_hints()
        if result is not None:
            return result

        # No hints found - return None to fall through to unknown strategy handling
        return None

    def _login_with_parser_hints(self) -> tuple[bool, str | None] | None:  # noqa: C901
        """
        Attempt login using auth hints from modem.yaml or parser class.

        Prefers modem.yaml hints (via adapter) over parser class attributes.

        Returns:
            tuple[bool, str | None] if hints were found and auth was attempted
            None if no hints were found (caller should try legacy path)
        """
        if not self.parser:
            return None

        # Get adapter for modem.yaml hints (preferred source)
        adapter = get_auth_adapter_for_parser(self.parser.__class__.__name__)

        # Check for HNAP hints (S33, MB8611)
        # HNAP config is in modem.yaml auth.hnap section
        hints = None
        if adapter:
            hints = adapter.get_hnap_hints()
            if hints:
                _LOGGER.debug("Using modem.yaml hnap_hints for HNAP authentication")
        if hints:
            temp_handler = AuthHandler(strategy="hnap_session", hnap_config=hints)
            auth_result = temp_handler.authenticate(self.session, self.base_url, self.username, self.password)
            if auth_result.success:
                # Save handler for subsequent polls (loader will get builder via get_hnap_builder())
                self._auth_handler = temp_handler
                _LOGGER.debug("Saved HNAP auth handler for future polls")
            return auth_result.success, auth_result.response_html

        # Check for URL token hints (SB8200)
        # URL token config is in modem.yaml auth.url_token section
        hints = None
        if adapter:
            hints = adapter.get_js_auth_hints()
            if hints:
                _LOGGER.debug("Using modem.yaml js_auth_hints for URL token authentication")
        if hints:
            url_token_config = {
                "login_page": hints.get("login_page", "/cmconnectionstatus.html"),
                "login_prefix": hints.get("login_prefix", "login_"),
                "session_cookie_name": hints.get("session_cookie_name", "credential"),
                "data_page": hints.get("data_page", "/cmconnectionstatus.html"),
                "token_prefix": hints.get("token_prefix", "ct_"),
                "success_indicator": hints.get("success_indicator", "Downstream"),
            }
            temp_handler = AuthHandler(strategy="url_token_session", url_token_config=url_token_config)
            auth_result = temp_handler.authenticate(self.session, self.base_url, self.username, self.password)
            if auth_result.success:
                self._auth_handler = temp_handler
                _LOGGER.debug("Saved URL token auth handler for future polls")
            return auth_result.success, auth_result.response_html

        # Check for form hints (MB7621, CGA2121, G54, CM2000)
        # Try modem.yaml first, fall back to parser class
        hints = None
        if adapter:
            hints = adapter.get_auth_form_hints()
            if hints:
                _LOGGER.debug("Using modem.yaml auth_form_hints for form authentication")
        if not hints and hasattr(self.parser, "auth_form_hints") and self.parser.auth_form_hints:
            hints = self.parser.auth_form_hints
            _LOGGER.debug("Using parser's auth_form_hints for form authentication")
        if hints:
            # Build form_config from hints (password_encoding controls encoding behavior)
            form_config = {
                "action": hints.get("login_url", ""),
                "method": "POST",
                "username_field": hints.get("username_field", "username"),
                "password_field": hints.get("password_field", "password"),
                "password_encoding": hints.get("password_encoding", "plain"),
            }

            temp_handler = AuthHandler(strategy="form_plain", form_config=form_config)
            auth_result = temp_handler.authenticate(self.session, self.base_url, self.username, self.password)
            if auth_result.success:
                self._auth_handler = temp_handler
                _LOGGER.debug("Saved form auth handler (strategy=form_plain) for future polls")
            return auth_result.success, auth_result.response_html

        return None  # No hints found

    def _get_tier1_urls(self) -> list[tuple[str, str, type[ModemParser]]]:
        """Get URLs for Tier 1: User explicitly selected a parser."""
        if self.parser is None:
            raise RuntimeError("Tier 1 URLs requested but parser is None")
        _LOGGER.debug("Tier 1: Using explicitly selected parser: %s", self.parser.name)
        urls = []
        for pattern in _get_parser_url_patterns(self.parser):
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

    def _add_parser_urls(self, urls: list, parser_class: type[ModemParser]) -> None:
        """Add URLs from a parser to the list in priority order (data page first)."""
        for pattern in _get_parser_url_patterns(parser_class):
            url = f"{self.base_url}{pattern['path']}"
            urls.append((url, pattern["auth_method"], parser_class))

    def _get_tier2_urls(self) -> list[tuple[str, str, type[ModemParser]]]:
        """Get URLs for Tier 2: Cached parser from previous detection."""
        _LOGGER.debug("Tier 2: Looking for cached parser: %s", self.parser_name)
        cached_parser = self._find_cached_parser()
        if not cached_parser:
            return []

        # Cast to type[ModemParser] to satisfy type checker after None check
        parser = cached_parser
        _LOGGER.debug("Found cached parser: %s", parser.name)
        urls: list[tuple[str, str, type[ModemParser]]] = []

        # Add URLs from parser in priority order (data page first)
        # Note: cached_url is only used for protocol detection, not page selection
        self._add_parser_urls(urls, parser)

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
        URLs are returned in priority order (data page first for each parser).
        """
        _LOGGER.debug("Tier 3: Auto-detection mode - trying all parsers")
        urls = []

        # Add all parser URLs in priority order (excluding fallback)
        # Note: cached_url is only used for protocol detection, not page selection
        for parser_class in self.parsers:
            # Skip fallback parser - it should only be tried as last resort during detection
            if parser_class.manufacturer == "Unknown":
                _LOGGER.debug("Skipping fallback parser in URL discovery: %s", parser_class.name)
                continue

            for pattern in _get_parser_url_patterns(parser_class):
                url = f"{self.base_url}{pattern['path']}"
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

            for url_template, auth_method, parser_class in urls_to_try:
                # Replace protocol in URL to match current attempt
                target_url = url_template.replace(self.base_url, current_base_url)

                try:
                    _LOGGER.debug(
                        "Attempting to fetch %s (auth: %s, parser: %s)",
                        target_url,
                        auth_method,
                        parser_class.name if parser_class else "unknown",
                    )
                    auth = None
                    if auth_method == "basic" and self.username and self.password:
                        auth = (self.username, self.password)

                    # Use configured SSL verification setting
                    response = self.session.get(target_url, timeout=DEFAULT_TIMEOUT, auth=auth, verify=self.verify_ssl)

                    if response.status_code == 200:
                        _LOGGER.debug(
                            "Successfully fetched %s (%s bytes)",
                            target_url,
                            len(response.text),
                        )
                        self.last_successful_url = target_url

                        # Capture raw HTML if requested
                        self._capture_response(response, "Initial connection page")

                        # Update base_url to the working protocol
                        _LOGGER.debug("About to update base_url from %s to %s", self.base_url, current_base_url)
                        self.base_url = current_base_url
                        _LOGGER.debug("Updated! base_url is now: %s", self.base_url)
                        return response.text, target_url, parser_class
                    else:
                        _LOGGER.debug("Got status %s from %s", response.status_code, target_url)
                except requests.RequestException as e:
                    _LOGGER.debug("Failed to fetch from %s: %s: %s", target_url, type(e).__name__, e)
                    continue

        return None

    def _try_anonymous_probing(self, circuit_breaker, attempted_parsers: list) -> ModemParser | None:
        """Try anonymous probing for modems with public pages.

        Fetches public URLs defined in modem.yaml and uses HintMatcher for detection.
        Note: Excludes fallback parser - only tries real modem parsers.
        """
        _LOGGER.debug("Phase 1: Attempting anonymous probing before authentication")
        hint_matcher = HintMatcher.get_instance()

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
                    circuit_breaker.record_attempt(parser_class.name)

                    # Use HintMatcher for detection
                    matches = hint_matcher.match_login_markers(anon_html)
                    if any(m.parser_name == parser_class.__name__ for m in matches):
                        _LOGGER.debug(
                            "Detected modem via anonymous probing: %s (%s)",
                            parser_class.name,
                            parser_class.manufacturer,
                        )
                        return cast(type[ModemParser], parser_class)()
                    else:
                        attempted_parsers.append(parser_class.name)
            except (requests.RequestException, AttributeError, TypeError, KeyError) as e:
                # Intentionally broad: probing tries many parsers with varied failures
                _LOGGER.debug("Anonymous probing failed for %s: %s", parser_class.name, e)

        return None

    def _try_authenticated_probing(self, circuit_breaker, attempted_parsers: list) -> ModemParser | None:
        """Try authenticated probing for modems that require auth for all content pages.

        This is called after anonymous probing fails. Uses the authenticated session
        to fetch protected pages and uses HintMatcher for detection.

        Note: Excludes fallback parser - only tries real modem parsers.
        """
        _LOGGER.debug("Phase 1b: Attempting authenticated probing (session has auth cookies)")
        hint_matcher = HintMatcher.get_instance()

        for parser_class in self.parsers:
            # Skip fallback parser
            if parser_class.manufacturer == "Unknown":
                continue

            if not circuit_breaker.should_continue():
                break

            try:
                auth_result = ParserHeuristics.check_authenticated_access(
                    self.base_url, parser_class, self.session, self.verify_ssl
                )
                if auth_result:
                    auth_html, auth_url = auth_result
                    circuit_breaker.record_attempt(parser_class.name)

                    # Use HintMatcher for detection (model_strings for post-auth pages)
                    matches = hint_matcher.match_model_strings(auth_html)
                    if any(m.parser_name == parser_class.__name__ for m in matches):
                        _LOGGER.debug(
                            "Detected modem via authenticated probing: %s (%s)",
                            parser_class.name,
                            parser_class.manufacturer,
                        )
                        return cast(type[ModemParser], parser_class)()
                    else:
                        if parser_class.name not in attempted_parsers:
                            attempted_parsers.append(parser_class.name)
            except (requests.RequestException, AttributeError, TypeError, KeyError) as e:
                # Intentionally broad: probing tries many parsers with varied failures
                _LOGGER.debug("Authenticated probing failed for %s: %s", parser_class.name, e)

        return None

    def _try_suggested_parser(
        self, soup, url: str, html: str, suggested_parser, circuit_breaker, attempted_parsers: list
    ) -> ModemParser | None:
        """Try the suggested parser from URL pattern matching.

        Uses HintMatcher to verify the suggested parser matches the HTML.
        """
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

            # Use HintMatcher for detection (try both login_markers and model_strings)
            hint_matcher = HintMatcher.get_instance()
            login_matches = hint_matcher.match_login_markers(html)
            model_matches = hint_matcher.match_model_strings(html)

            if any(m.parser_name == suggested_parser.__name__ for m in login_matches + model_matches):
                _LOGGER.debug(
                    "Detected modem using suggested parser: %s (%s)",
                    suggested_parser.name,
                    suggested_parser.manufacturer,
                )
                return cast(type[ModemParser], suggested_parser)()
            else:
                attempted_parsers.append(suggested_parser.name)
                _LOGGER.debug("Suggested parser %s did not match via HintMatcher", suggested_parser.name)
        except (AttributeError, TypeError, KeyError, ValueError) as e:
            # Intentionally broad: parser detection can fail in various ways
            _LOGGER.error("Suggested parser %s detection failed: %s", suggested_parser.name, e, exc_info=True)
            attempted_parsers.append(suggested_parser.name)

        return None

    def _try_prioritized_parsers(
        self, soup, url: str, html: str, suggested_parser, circuit_breaker, attempted_parsers: list
    ) -> ModemParser | None:
        """Try parsers in prioritized order using heuristics.

        Note: Excludes fallback parser - only tries real modem parsers.
        """
        _LOGGER.debug("Phase 3: Using parser heuristics to prioritize likely parsers")
        prioritized_parsers = ParserHeuristics.get_likely_parsers(
            self.base_url, self.parsers, self.session, self.verify_ssl
        )

        _LOGGER.debug("Attempting to detect parser from %s available parsers (prioritized)", len(prioritized_parsers))
        hint_matcher = HintMatcher.get_instance()

        # Pre-compute matches once for efficiency
        login_matches = hint_matcher.match_login_markers(html)
        model_matches = hint_matcher.match_model_strings(html)
        all_matched_parsers = {m.parser_name for m in login_matches + model_matches}

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
                if parser_class.__name__ in all_matched_parsers:
                    _LOGGER.debug("Detected modem: %s (%s)", parser_class.name, parser_class.manufacturer)
                    return parser_class()
                else:
                    attempted_parsers.append(parser_class.name)
                    _LOGGER.debug("Parser %s did not match via HintMatcher", parser_class.name)
            except (AttributeError, TypeError, KeyError, ValueError) as e:
                # Intentionally broad: parser detection can fail in various ways
                _LOGGER.error("Parser %s detection failed: %s", parser_class.name, e, exc_info=True)
                attempted_parsers.append(parser_class.name)

        return None

    def _try_instant_detection(self) -> None:
        """Use pre-fetched HTML from auth discovery for instant parser detection.

        This is a fast path optimization: auth discovery already fetched HTML,
        so we can detect the parser without making additional HTTP requests.
        """
        if not self._authenticated_html or self.parser:
            return

        _LOGGER.debug("Attempting instant parser detection using pre-fetched HTML from auth discovery")
        hint_matcher = HintMatcher.get_instance()
        parser = self._try_login_markers_detection(self._authenticated_html, hint_matcher)

        if parser:
            self.parser = parser
            _LOGGER.info(
                "Instant parser detection successful: %s (skipping HTTP probing)",
                parser.name,
            )
        else:
            _LOGGER.debug("Pre-fetched HTML did not match any parser, falling back to HTTP probing")

        # Clear pre-fetched HTML after use (one-time optimization)
        self._authenticated_html = None

    def _try_login_markers_detection(self, html: str, hint_matcher: HintMatcher) -> ModemParser | None:
        """Phase 0a: Try detection via login_markers.

        Returns parser if single confident match or best match after disambiguation.
        """
        login_matches = hint_matcher.match_login_markers(html)
        if not login_matches:
            return None

        _LOGGER.debug(
            "Phase 0a: Found %d login_markers matches: %s",
            len(login_matches),
            [m.parser_name for m in login_matches[:3]],
        )

        # Single confident match - use it directly
        if len(login_matches) == 1:
            match = login_matches[0]
            parser = self._get_parser_by_name(match.parser_name)
            if parser:
                _LOGGER.info(
                    "Detected modem via login_markers: %s (%s) - matched: %s",
                    match.parser_name,
                    match.manufacturer,
                    match.matched_markers[:3],
                )
                return parser

        # Multiple matches - try model_strings disambiguation (Phase 0b)
        parser = self._disambiguate_with_model_strings(html, login_matches, hint_matcher)
        if parser:
            return parser

        # Use best login match if no model match disambiguation
        best_match = login_matches[0]
        parser = self._get_parser_by_name(best_match.parser_name)
        if parser:
            _LOGGER.info(
                "Detected modem via best login_markers match: %s (%s) - %d markers matched",
                best_match.parser_name,
                best_match.manufacturer,
                len(best_match.matched_markers),
            )
        return parser

    def _disambiguate_with_model_strings(
        self, html: str, login_matches: list, hint_matcher: HintMatcher
    ) -> ModemParser | None:
        """Phase 0b: Disambiguate login_markers matches using model_strings."""
        _LOGGER.debug("Phase 0b: Disambiguating with model_strings")
        model_matches = hint_matcher.match_model_strings(html)

        if not model_matches:
            return None

        # Find intersection: matches that appear in both login and model
        login_names = {m.parser_name for m in login_matches}
        for model_match in model_matches:
            if model_match.parser_name in login_names:
                parser = self._get_parser_by_name(model_match.parser_name)
                if parser:
                    _LOGGER.info(
                        "Detected modem via model_strings: %s (%s) - matched: %s",
                        model_match.parser_name,
                        model_match.manufacturer,
                        model_match.matched_markers,
                    )
                    return parser
        return None

    def _try_quick_detection(self, soup, html: str, url: str) -> ModemParser | None:
        """Phase 0: Quick detection using HintMatcher.

        Uses index-driven detection for O(1) lookups:
        - Phase 0a: login_markers for pre-auth page detection
        - Phase 0b: model_strings for exact model identification

        Args:
            soup: Parsed HTML as BeautifulSoup object
            html: Raw HTML content
            url: URL that returned this HTML

        Returns:
            Parser instance if detected, None otherwise.
        """
        # Phase 0a/0b: HintMatcher-based detection
        _LOGGER.debug("Phase 0a: HintMatcher login_markers detection")
        hint_matcher = HintMatcher.get_instance()

        return self._try_login_markers_detection(html, hint_matcher)

    def _get_parser_by_name(self, parser_name: str) -> ModemParser | None:
        """Get a parser instance by class name.

        Args:
            parser_name: Parser class name (e.g., "MotorolaMB7621Parser")

        Returns:
            Parser instance or None if not found
        """
        for parser_class in self.parsers:
            if parser_class.__name__ == parser_name:
                return cast(type[ModemParser], parser_class)()
        _LOGGER.debug("Parser %s not found in available parsers", parser_name)
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
        # Increased max_attempts to handle anonymous + authenticated probing phases
        circuit_breaker = DiscoveryCircuitBreaker(max_attempts=40, timeout_seconds=90)
        attempted_parsers: list[str] = []

        # Phase 0: Quick detection via YAML hints (HintMatcher)
        parser = self._try_quick_detection(soup, html, url)
        if parser:
            return parser

        # Phase 1: Anonymous probing (public URLs) - only if quick detection failed
        parser = self._try_anonymous_probing(circuit_breaker, attempted_parsers)
        if parser:
            return parser

        # Phase 1b: Authenticated probing (protected URLs with session cookies)
        parser = self._try_authenticated_probing(circuit_breaker, attempted_parsers)
        if parser:
            return parser

        # Phase 2: Try suggested parser from URL matching
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
        """Parse data from the modem.

        Uses the Loader architecture:
        1. Creates a loader based on modem.yaml config
        2. Fetches all resources (HTML pages, HNAP actions, REST endpoints)
        3. Calls parser.parse_resources() with the fetched resources

        If fetcher is unavailable (no modem.yaml), falls back to single-page parsing.
        """
        if self.parser is None:
            raise RuntimeError("Cannot parse data: parser is not set")

        # Create loader based on modem.yaml config
        fetcher = self._create_loader()
        if fetcher:
            resources = self._load_resources(fetcher)
            if resources:
                # Add the initial HTML as a resource for parsers that need it
                soup = BeautifulSoup(html, "html.parser")
                resources["/"] = soup
                _LOGGER.debug("Fetched %d resources via loader", len(resources))
                return self.parser.parse_resources(resources)

        # No loader available - parse single page via parse()
        # This calls parse_resources({"/": soup}) via base class
        _LOGGER.debug("No loader available, using single-page parse")
        soup = BeautifulSoup(html, "html.parser")
        return self.parser.parse(soup)

    def get_modem_data(self, capture_raw: bool = False) -> dict:
        """Fetch and parse modem data.

        Args:
            capture_raw: If True, capture raw HTML responses for diagnostics

        Returns:
            Dictionary with modem data and optionally raw HTML captures
        """
        # Clear previous captures and enable capture mode
        self._captured_urls = []
        self._failed_urls = []
        self._capture_enabled = capture_raw

        # Replace session with capturing session if capture is enabled
        original_session = None
        if capture_raw:
            original_session = self.session
            self.session = CapturingSession(self._capture_response)
            # Copy SSL verification settings to capturing session
            self.session.verify = original_session.verify
            # Copy cookies from original session (required for authenticated captures)
            self.session.cookies.update(original_session.cookies)
            # Copy legacy SSL adapter if needed (fixes capture for older modem firmware)
            if self.legacy_ssl and self.base_url.startswith("https://"):
                self.session.mount("https://", LegacySSLAdapter())
            _LOGGER.debug("Enabled HTML capture mode with CapturingSession")

        # Fast path: Use pre-fetched HTML from auth discovery for instant parser detection
        self._try_instant_detection()

        try:
            fetched_data = self._fetch_data(capture_raw=capture_raw)
            if not fetched_data:
                return self._create_error_response("unreachable")

            html, successful_url, suggested_parser = fetched_data

            # Detect or instantiate parser
            if not self._ensure_parser(html, successful_url, suggested_parser):
                return self._create_error_response("offline")

            # Authenticate and get usable HTML (re-fetches if session had expired)
            authenticated = self._authenticate(html, data_url=successful_url)
            if authenticated is None:
                return self._create_error_response("auth_failed")
            html = authenticated

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
                    "failed_urls": self._failed_urls,  # Include failed fetches for diagnostics
                }
                _LOGGER.info(
                    "Captured %d HTML pages for diagnostics (%d URLs failed)",
                    len(self._captured_urls),
                    len(self._failed_urls),
                )

            return response

        except (requests.RequestException, AttributeError, TypeError, KeyError) as e:
            # Top-level catch for unexpected errors during data fetch
            _LOGGER.error("Error fetching modem data: %s", e, exc_info=True)
            return self._create_error_response("unreachable")
        finally:
            # End session for single-session modems (before restoring original session)
            self._perform_logout()

            # Restore original session if we replaced it
            if original_session is not None:
                self.session = original_session
                _LOGGER.debug("Restored original session")

    def _create_error_response(self, status: str) -> dict:
        """Create error response dictionary."""
        return {"cable_modem_connection_status": status, "cable_modem_downstream": [], "cable_modem_upstream": []}

    def _perform_logout(self) -> None:
        """End session for modems that only support one authenticated session.

        Some modems (e.g., Netgear C7000v2) only allow one authenticated session
        at a time. If the integration holds the session, users can't access the
        modem's web interface. Calling the logout endpoint frees the session.

        Checks modem.yaml config first, falls back to parser attribute.
        """
        if not self.parser:
            return

        # Check modem.yaml first (preferred source of truth)
        logout_endpoint = None
        try:
            from custom_components.cable_modem_monitor.modem_config.adapter import (
                get_auth_adapter_for_parser,
            )

            adapter = get_auth_adapter_for_parser(self.parser.__class__.__name__)
            if adapter:
                logout_endpoint = adapter.get_logout_endpoint()
        except (ImportError, AttributeError, KeyError):
            pass  # Fall through to parser attribute

        # Fall back to parser attribute (legacy)
        if not logout_endpoint:
            logout_endpoint = getattr(self.parser, "logout_endpoint", None)

        if not logout_endpoint:
            return

        try:
            logout_url = f"{self.base_url}{logout_endpoint}"
            self.session.get(logout_url, timeout=5)
            _LOGGER.debug("Session ended via %s", logout_endpoint)
        except requests.RequestException as e:
            # Don't fail the poll if logout fails - it's just cleanup
            _LOGGER.debug("Logout request failed (non-critical): %s", e)

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

    def _authenticate(self, html: str, data_url: str | None = None) -> str | None:
        """Authenticate and return usable HTML for parsing.

        If the original HTML is a login page (session expired), re-fetches
        the data URL after successful authentication.

        Args:
            html: Original HTML from _fetch_data (might be login page if session expired)
            data_url: URL that was fetched (for re-fetching after auth if needed)

        Returns:
            Usable HTML for parsing, or None if authentication failed
        """
        from .auth.detection import is_login_page

        # Check if original HTML is a login page (no active session)
        # This is normal on first poll or when logout_required is configured
        original_was_login_page = is_login_page(html)
        if original_was_login_page:
            _LOGGER.debug("Login page detected - authenticating before data fetch")

        success, authenticated_html = self._login()

        if not success:
            _LOGGER.error("Failed to log in to modem")
            return None

        # Use authenticated HTML from login if available
        if authenticated_html:
            _LOGGER.debug("Using authenticated HTML from login (%s bytes)", len(authenticated_html))
            return authenticated_html

        # If original was a login page, re-fetch the data URL now that we're authenticated
        if original_was_login_page and data_url:
            _LOGGER.debug("Re-fetching data URL after authentication: %s", data_url)
            try:
                response = self.session.get(data_url, timeout=DEFAULT_TIMEOUT, verify=self.session.verify)
                if response.ok:
                    # Verify we didn't get another login page
                    if not is_login_page(response.text):
                        _LOGGER.debug("Re-fetch successful (%s bytes)", len(response.text))
                        return response.text
                    else:
                        _LOGGER.warning("Re-fetch after auth still returned login page - auth may have failed")
                else:
                    _LOGGER.warning("Re-fetch failed with status %s", response.status_code)
            except requests.RequestException as e:
                _LOGGER.warning("Failed to re-fetch data URL after auth: %s", e)

        return html

    def _build_response(self, data: dict) -> dict:
        """Build response dictionary from parsed data."""
        downstream = data.get("downstream", [])
        upstream = data.get("upstream", [])
        system_info = data.get("system_info", {})

        # Only calculate totals if we have channel data - None indicates unavailable, not 0
        total_corrected = sum(ch.get("corrected") or 0 for ch in downstream) if downstream else None
        total_uncorrected = sum(ch.get("uncorrected") or 0 for ch in downstream) if downstream else None

        # Determine connection status
        # If fallback mode is active (unsupported modem), use "limited" status
        # This allows installation to succeed without showing dummy channel data
        if system_info.get("fallback_mode"):
            status = "limited"
        elif system_info.get("no_signal"):
            # Parser found valid page structure but no signal data
            # This means modem is online but has no cable connection
            status = "no_signal"
            parser_name = self.parser.name if self.parser else "Unknown"
            system_info["status_message"] = (
                f"📡 No Cable Signal\n\n"
                f"Connected to {parser_name}, but no signal data available.\n\n"
                f"This is normal if:\n"
                f"• Modem is not connected to cable service\n"
                f"• Cable line is disconnected\n"
                f"• Modem is still acquiring signal after power-on\n\n"
                f"The modem's web interface is working correctly."
            )
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

    def _get_modem_config_adapter(self):
        """Get the modem config adapter for the current parser, or None if unavailable."""
        try:
            from custom_components.cable_modem_monitor.modem_config.adapter import (
                get_auth_adapter_for_parser,
            )

            return get_auth_adapter_for_parser(self.parser.__class__.__name__)
        except Exception:
            return None

    def _populate_detection_info_from_yaml(self, info: dict, adapter, parser: ModemParser) -> None:
        """Populate detection info from modem.yaml via adapter."""
        # Fields from modem.yaml (source of truth) with legacy parser fallback for release_date
        if release_date := adapter.get_release_date() or parser.release_date:
            info["release_date"] = release_date
        if docsis_version := adapter.get_docsis_version():
            info["docsis_version"] = docsis_version

        # Status and verification
        status = adapter.get_status()
        info["verified"] = status == "verified"
        info["status"] = status
        if verification_source := adapter.get_verification_source():
            info["verification_source"] = verification_source

        # Fields from modem.yaml (no fallback to parser - yaml is source of truth)
        info["logout_endpoint"] = adapter.get_logout_endpoint()
        info["capabilities"] = adapter.get_capabilities() or []

        # Fixtures path from modem.yaml
        if fixtures_path := adapter.get_fixtures_path():
            info["fixtures_path"] = fixtures_path
            info["fixtures_url"] = f"{ModemParser.GITHUB_REPO_URL}/tree/main/{fixtures_path}"

    def _populate_detection_info_from_parser(self, info: dict, parser: ModemParser) -> None:
        """Populate detection info from parser class attributes only.

        DEPRECATED: This is a legacy fallback for modems without modem.yaml.
        All modems should have modem.yaml as the source of truth.
        Only release_date and capabilities are still available from parser.
        """
        if parser.release_date:
            info["release_date"] = parser.release_date
        # Status fields now only in modem.yaml - default for legacy modems
        info["verified"] = False
        info["logout_endpoint"] = None
        info["capabilities"] = [cap.value for cap in parser.capabilities]

    def get_detection_info(self) -> dict[str, str | bool | list[str] | None]:
        """Get information about detected modem and successful URL.

        Returns parser metadata including:
        - modem_name: Parser display name
        - manufacturer: Modem manufacturer
        - successful_url: URL that worked for data retrieval
        - release_date: When modem was first released (e.g., "2017")
        - docsis_version: DOCSIS specification version (e.g., "3.1")
        - fixtures_path: Path to test fixtures in repo
        - fixtures_url: GitHub URL to fixtures directory
        - verified: Whether parser has been verified by users

        Reads from modem.yaml first, falls back to parser class attributes.
        """
        if not self.parser:
            return {}

        info: dict[str, str | bool | list[str] | None] = {
            "modem_name": self.parser.name,
            "manufacturer": self.parser.manufacturer,
            "successful_url": self.last_successful_url,
        }

        # Populate from modem.yaml or fallback to parser
        if adapter := self._get_modem_config_adapter():
            self._populate_detection_info_from_yaml(info, adapter, self.parser)
        else:
            self._populate_detection_info_from_parser(info, self.parser)

        return info

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

        except (requests.RequestException, AttributeError, TypeError, KeyError) as e:
            # Top-level catch for unexpected errors during restart
            _LOGGER.error("Error restarting modem: %s", e, exc_info=True)
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
        """Validate that modem supports restart functionality.

        Checks modem.yaml actions.restart config via ActionFactory.

        Returns:
            True if modem supports restart, False otherwise
        """
        if self.parser is None:
            _LOGGER.warning("Cannot validate restart capability: parser is not set")
            return False

        # Check modem.yaml for restart action config
        adapter = get_auth_adapter_for_parser(self.parser.__class__.__name__)
        if not adapter:
            _LOGGER.warning("No modem.yaml adapter for %s - restart not supported", self.parser.name)
            return False

        modem_config = adapter.get_modem_config_dict()
        if not ActionFactory.supports(ActionType.RESTART, modem_config):
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
        """Execute the restart command using the action layer.

        Uses ActionFactory to create the appropriate restart action based on
        modem.yaml configuration. All restart logic is in the action layer,
        keeping parsers focused on parsing only.

        Returns:
            True if restart command succeeded, False otherwise
        """
        if self.parser is None:
            _LOGGER.error("Cannot execute restart: parser is not set")
            return False

        _LOGGER.info("Attempting to restart modem using action layer for %s", self.parser.name)

        # Get modem config from adapter
        adapter = get_auth_adapter_for_parser(self.parser.__class__.__name__)
        if not adapter:
            _LOGGER.error("No modem.yaml adapter for %s - restart not supported", self.parser.name)
            return False

        modem_config = adapter.get_modem_config_dict()

        # Create restart action
        action = ActionFactory.create_restart_action(modem_config)
        if not action:
            _LOGGER.error("No restart action configured for %s in modem.yaml", self.parser.name)
            return False

        # Execute the action (action extracts what it needs from auth_handler)
        result = action.execute(self.session, self.base_url, self._auth_handler)

        if result.success:
            _LOGGER.info("Modem restart command sent successfully: %s", result.message)
        else:
            _LOGGER.error("Modem restart command failed: %s", result.message)

        return result.success
