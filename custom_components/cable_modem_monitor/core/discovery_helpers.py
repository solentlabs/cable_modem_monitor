"""Helper utilities for modem discovery and detection.

This module provides supporting classes for the modem discovery pipeline:

Classes:
    HintMatcher: Index-driven detection using pre-computed index.yaml.
        Performs O(1) pattern lookups instead of iterating all parsers.
        - match_pre_auth(): Phase 1 - match login page content
        - match_post_auth(): Phase 2 - match data page content
        - get_page_hint(): Get which page has detection patterns

    ParserHeuristics: Quick checks to narrow parser search space.
        - get_likely_parsers(): Heuristic matching from root page
        - check_anonymous_access(): Try public URLs (no auth)
        - check_authenticated_access(): Try protected URLs with session

    DiscoveryCircuitBreaker: Prevents endless detection attempts.
        Tracks attempts and elapsed time, breaks circuit if thresholds exceeded.

    Exception Classes (all inherit from DetectionError):
        - ParserNotFoundError: No parser matched the modem
        - AuthenticationError: Authentication failed
        - SessionExpiredError: Session expired mid-request
        - ModemConnectionError: Cannot connect to modem
        - CircuitBreakerError: Circuit breaker tripped

Architecture:
    These helpers are used by core/discovery/__init__.py (the discovery pipeline).
    HintMatcher loads index.yaml which is generated from modem.yaml files by
    scripts/generate_modem_index.py.

Note:
    This module is part of core/ and has no Home Assistant dependencies.
    It can be extracted to a standalone library.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import requests
import yaml  # type: ignore[import-untyped]
from bs4 import BeautifulSoup

from ..modem_config.adapter import get_url_patterns_for_parser
from .base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)


# =============================================================================
# HINT MATCHER - Index-driven modem detection
# =============================================================================


@dataclass
class HintMatch:
    """A modem that matched against hints."""

    parser_name: str
    manufacturer: str
    model: str
    path: str
    matched_markers: list[str]  # Which markers matched


class HintMatcher:
    """Index-driven hint matcher for two-phase modem detection.

    Uses pre-computed index.yaml for O(1) hint lookups instead of
    iterating through all parser classes.

    Phase 1 (pre-auth): Match login page content against detection.pre_auth
    Phase 2 (post-auth): Match data page content against detection.post_auth
    """

    _instance: HintMatcher | None = None
    _index: dict | None = None

    def __init__(self):
        """Initialize HintMatcher and load index."""
        if HintMatcher._index is None:
            self._load_index()

    @classmethod
    def get_instance(cls) -> HintMatcher:
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_index(self) -> None:
        """Load modem index from YAML file."""
        index_path = Path(__file__).parent.parent / "modems" / "index.yaml"
        try:
            with open(index_path) as f:
                HintMatcher._index = yaml.safe_load(f) or {"modems": {}}
            _LOGGER.debug("Loaded modem index with %s entries", len(HintMatcher._index.get("modems", {})))
        except FileNotFoundError:
            _LOGGER.error("Modem index not found at %s", index_path)
            HintMatcher._index = {"modems": {}}
        except Exception as e:
            _LOGGER.error("Failed to load modem index: %s", e)
            HintMatcher._index = {"modems": {}}

    def match_pre_auth(self, content: str) -> list[HintMatch]:
        """Match content against pre_auth patterns (Phase 1 detection).

        Args:
            content: HTML/text content from login/entry page

        Returns:
            List of HintMatch objects for modems whose pre_auth patterns matched
        """
        if not HintMatcher._index:
            return []

        content_lower = content.lower()
        matches: list[HintMatch] = []

        for parser_name, entry in HintMatcher._index.get("modems", {}).items():
            detection = entry.get("detection", {})
            pre_auth = detection.get("pre_auth", [])
            if not pre_auth:
                continue

            matched = []
            for pattern in pre_auth:
                if pattern.lower() in content_lower:
                    matched.append(pattern)

            # Require at least one pattern match
            if matched:
                matches.append(
                    HintMatch(
                        parser_name=parser_name,
                        manufacturer=entry.get("manufacturer", "Unknown"),
                        model=entry.get("model", "Unknown"),
                        path=entry.get("path", ""),
                        matched_markers=matched,
                    )
                )
                _LOGGER.debug(
                    "Phase 1 match: %s (%s pre_auth: %s)",
                    parser_name,
                    len(matched),
                    matched[:3],  # Log first 3
                )

        # Sort by number of matches (most specific first)
        matches.sort(key=lambda m: len(m.matched_markers), reverse=True)

        return matches

    # Backwards compatibility alias
    match_login_markers = match_pre_auth

    def match_post_auth(self, content: str) -> list[HintMatch]:
        """Match content against post_auth patterns (Phase 2 detection).

        Args:
            content: HTML/text/JSON content from data page

        Returns:
            List of HintMatch objects for modems whose post_auth patterns matched
        """
        if not HintMatcher._index:
            return []

        content_lower = content.lower()
        matches: list[HintMatch] = []

        for parser_name, entry in HintMatcher._index.get("modems", {}).items():
            detection = entry.get("detection", {})
            post_auth = detection.get("post_auth", [])
            if not post_auth:
                continue

            matched = []
            for pattern in post_auth:
                if pattern.lower() in content_lower:
                    matched.append(pattern)

            # Require at least one pattern match
            if matched:
                matches.append(
                    HintMatch(
                        parser_name=parser_name,
                        manufacturer=entry.get("manufacturer", "Unknown"),
                        model=entry.get("model", "Unknown"),
                        path=entry.get("path", ""),
                        matched_markers=matched,
                    )
                )
                _LOGGER.debug(
                    "Phase 2 match: %s (post_auth: %s)",
                    parser_name,
                    matched,
                )

        # Sort by number of matches (most specific first)
        matches.sort(key=lambda m: len(m.matched_markers), reverse=True)

        return matches

    # Backwards compatibility alias
    match_model_strings = match_post_auth

    def get_page_hint(self, parser_name: str) -> str | None:
        """Get the page_hint for a parser (which page has post_auth patterns).

        Args:
            parser_name: Parser class name

        Returns:
            Page path hint or None if not available
        """
        if not HintMatcher._index:
            return None

        entry = HintMatcher._index.get("modems", {}).get(parser_name, {})
        detection = entry.get("detection", {})
        page_hint: str | None = detection.get("page_hint")
        return page_hint

    def get_all_modems(self) -> list[dict]:
        """Get all modem entries from the index.

        Returns:
            List of modem entry dictionaries with parser_name, manufacturer, model
        """
        if not HintMatcher._index:
            return []

        return [
            {
                "parser_name": parser_name,
                "manufacturer": entry.get("manufacturer", "Unknown"),
                "model": entry.get("model", "Unknown"),
                "path": entry.get("path", ""),
            }
            for parser_name, entry in HintMatcher._index.get("modems", {}).items()
        ]


class ParserHeuristics:
    """Quick checks to narrow parser search space and speed up detection."""

    @staticmethod
    def get_likely_parsers(
        base_url: str,
        parsers: Sequence[type[ModemParser]],
        session: requests.Session,
        verify_ssl: bool = False,
    ) -> list[type[ModemParser]]:
        """
        Return parsers likely to match based on quick heuristic checks.

        Args:
            base_url: Modem base URL
            parsers: List of all available parser classes
            session: requests.Session object
            verify_ssl: SSL verification setting

        Returns:
            List of parser classes, sorted by likelihood (most likely first)
        """
        likely_parsers: list[type[ModemParser]] = []
        unlikely_parsers: list[type[ModemParser]] = []

        _LOGGER.debug("Running parser heuristics to narrow search space")

        # Try to fetch root page quickly (no auth) for heuristics
        try:
            response = session.get(f"{base_url}/", timeout=3, verify=verify_ssl)
            if response.status_code == 200:
                html = response.text.lower()
                soup = BeautifulSoup(response.text, "html.parser")
                title = soup.title.string.lower() if soup.title and soup.title.string else ""

                _LOGGER.debug("Heuristics: Got root page (%s bytes, title: '%s')", len(html), title)

                # Check for manufacturer indicators
                for parser_class in parsers:
                    manufacturer = parser_class.manufacturer.lower()

                    # Strong indicators (in title or prominent text)
                    if manufacturer in title or manufacturer in html[:1000]:
                        _LOGGER.debug(
                            "Heuristics: %s is LIKELY (found '%s' in title/header)",
                            parser_class.name,
                            manufacturer,
                        )
                        likely_parsers.append(parser_class)
                    # Weak indicators (anywhere in page) or model numbers
                    elif any(model.lower() in html for model in parser_class.models):
                        _LOGGER.debug("Heuristics: %s is LIKELY (found model number)", parser_class.name)
                        likely_parsers.append(parser_class)
                    else:
                        unlikely_parsers.append(parser_class)

            else:
                _LOGGER.debug("Heuristics: Root page returned status %s, skipping heuristics", response.status_code)
                return list(parsers)  # Return all parsers if heuristics fail

        except (requests.RequestException, Exception) as e:
            _LOGGER.debug("Heuristics: Failed to fetch root page (%s), trying all parsers", type(e).__name__)
            return list(parsers)  # Return all parsers if heuristics fail

        # If we found likely parsers, return those first, then the rest
        if likely_parsers:
            result = likely_parsers + unlikely_parsers
            _LOGGER.info(
                "Heuristics: Narrowed search to %s likely parsers (out of %s total)",
                len(likely_parsers),
                len(parsers),
            )
            return result

        # No heuristics matched, return all parsers
        _LOGGER.debug("Heuristics: No strong indicators found, trying all parsers")
        return list(parsers)

    @staticmethod
    def check_anonymous_access(
        base_url: str, parser_class: type[ModemParser], session: requests.Session, verify_ssl: bool = False
    ) -> tuple[str, str] | None:
        """
        Check if parser has public (non-authenticated) URLs that can be accessed.

        Args:
            base_url: Modem base URL
            parser_class: Parser class to check
            session: requests.Session object
            verify_ssl: SSL verification setting

        Returns:
            Tuple of (html, url) if successful, None otherwise
        """
        # Get URL patterns from modem.yaml (preferred) or parser class (fallback)
        try:
            class_name = parser_class.__name__
            url_patterns = get_url_patterns_for_parser(class_name)
        except AttributeError:
            # Mock objects in tests may not have __name__
            url_patterns = None
        if not url_patterns and hasattr(parser_class, "url_patterns"):
            url_patterns = parser_class.url_patterns
        if not url_patterns:
            return None

        for pattern in url_patterns:
            # Look for patterns explicitly marked as not requiring auth
            if not pattern.get("auth_required", True):
                url = f"{base_url}{pattern['path']}"
                try:
                    _LOGGER.debug("Trying anonymous access to %s for parser %s", url, parser_class.name)
                    # Short timeout - local modems should respond quickly
                    response = session.get(url, timeout=2, verify=verify_ssl)

                    if response.status_code == 200:
                        _LOGGER.info("Public URL access to %s (%s bytes)", url, len(response.text))
                        return (response.text, url)
                    else:
                        _LOGGER.debug("Anonymous access to %s returned status %s", url, response.status_code)
                except requests.RequestException as e:
                    _LOGGER.debug("Anonymous access to %s failed: %s", url, type(e).__name__)
                    continue

        return None

    @staticmethod
    def check_authenticated_access(
        base_url: str, parser_class: type[ModemParser], session: requests.Session, verify_ssl: bool = False
    ) -> tuple[str, str] | None:
        """
        Check if parser has protected URLs that can be accessed with authenticated session.

        Use this after auth discovery succeeds to detect modems that require auth
        for all content pages.

        Args:
            base_url: Modem base URL
            parser_class: Parser class to check
            session: requests.Session object (should have auth cookies)
            verify_ssl: SSL verification setting

        Returns:
            Tuple of (html, url) if successful, None otherwise
        """
        # Get URL patterns from modem.yaml (preferred) or parser class (fallback)
        try:
            class_name = parser_class.__name__
            url_patterns = get_url_patterns_for_parser(class_name)
        except AttributeError:
            url_patterns = None
        if not url_patterns and hasattr(parser_class, "url_patterns"):
            url_patterns = parser_class.url_patterns
        if not url_patterns:
            return None

        for pattern in url_patterns:
            # Look for patterns that require auth (protected pages)
            if pattern.get("auth_required", True):
                path = str(pattern["path"])
                # Skip static assets - they don't help with detection
                if path.endswith((".css", ".jpg", ".png", ".gif", ".js")):
                    continue
                url = f"{base_url}{path}"
                try:
                    _LOGGER.debug("Trying authenticated access to %s for parser %s", url, parser_class.name)
                    response = session.get(url, timeout=2, verify=verify_ssl)

                    if response.status_code == 200:
                        _LOGGER.info("Authenticated URL access to %s (%s bytes)", url, len(response.text))
                        return (response.text, url)
                    else:
                        _LOGGER.debug("Authenticated access to %s returned status %s", url, response.status_code)
                except requests.RequestException as e:
                    _LOGGER.debug("Authenticated access to %s failed: %s", url, type(e).__name__)
                    continue

        return None


class DiscoveryCircuitBreaker:
    """Circuit breaker to prevent endless authentication attempts during detection."""

    def __init__(self, max_attempts: int = 10, timeout_seconds: int = 60):
        """
        Initialize circuit breaker.

        Args:
            max_attempts: Maximum number of attempts before breaking
            timeout_seconds: Maximum time to allow for detection
        """
        self.max_attempts = max_attempts
        self.timeout = timeout_seconds
        self.start_time = 0.0
        self.attempts = 0
        self._broken = False

    def should_continue(self) -> bool:
        """
        Check if detection should continue or circuit should break.

        Returns:
            True if detection should continue, False if circuit is broken
        """
        if self._broken:
            return False

        # Start timer on first call only
        if self.start_time == 0.0:
            self.start_time = time.time()

        # Check max attempts
        if self.attempts >= self.max_attempts:
            _LOGGER.warning(
                "Discovery circuit breaker: Max attempts reached (%s). " "Stopping detection to prevent endless loops.",
                self.max_attempts,
            )
            self._broken = True
            return False

        # Check timeout
        elapsed = time.time() - self.start_time
        if elapsed > self.timeout:
            _LOGGER.warning(
                "Discovery circuit breaker: Timeout reached (%.1fs > %ss). " "Stopping detection.",
                elapsed,
                self.timeout,
            )
            self._broken = True
            return False

        return True

    def record_attempt(self, parser_name: str | None = None):
        """
        Record an authentication/detection attempt.

        Args:
            parser_name: Name of parser being attempted (for logging)
        """
        self.attempts += 1
        elapsed = time.time() - self.start_time if self.start_time else 0

        if parser_name:
            _LOGGER.debug(
                "Discovery attempt %s/%s (%.1fs elapsed): %s", self.attempts, self.max_attempts, elapsed, parser_name
            )
        else:
            _LOGGER.debug("Discovery attempt %s/%s (%.1fs elapsed)", self.attempts, self.max_attempts, elapsed)

    def is_broken(self) -> bool:
        """Check if circuit is broken."""
        return self._broken

    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        elapsed = time.time() - self.start_time if self.start_time else 0
        return {
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "elapsed_seconds": elapsed,
            "timeout_seconds": self.timeout,
            "is_broken": self._broken,
        }


class DetectionError(Exception):
    """Base exception for detection errors with diagnostic information."""

    def __init__(self, message: str, diagnostics: dict | None = None):
        """
        Initialize detection error.

        Args:
            message: Error message
            diagnostics: Dictionary of diagnostic information
        """
        super().__init__(message)
        self.diagnostics = diagnostics or {}

    def get_user_message(self) -> str:
        """Get user-friendly error message."""
        return str(self)

    def get_troubleshooting_steps(self) -> list[str]:
        """Get list of troubleshooting steps for user."""
        return []


class ParserNotFoundError(DetectionError):
    """Raised when no parser can be detected for the modem."""

    def __init__(self, modem_info: dict | None = None, attempted_parsers: list[str] | None = None):
        """
        Initialize parser not found error.

        Args:
            modem_info: Information about the modem (from HTML)
            attempted_parsers: List of parser names that were attempted
        """
        self.modem_info = modem_info or {}
        self.attempted_parsers = attempted_parsers or []

        message = "Could not detect modem type. No parser matched."
        diagnostics = {
            "modem_info": self.modem_info,
            "attempted_parsers": self.attempted_parsers,
            "parser_count": len(self.attempted_parsers),
        }

        super().__init__(message, diagnostics)

    def get_user_message(self) -> str:
        """Get user-friendly error message."""
        title = self.modem_info.get("title", "Unknown")
        msg = f"Unsupported modem detected: {title}\n\n"
        msg += f"Tried {len(self.attempted_parsers)} parsers, none matched.\n"
        msg += "Your modem may not be supported yet."
        return msg

    def get_troubleshooting_steps(self) -> list[str]:
        """Get troubleshooting steps."""
        return [
            "Verify the modem IP address is correct",
            "Check if credentials are required and provided",
            "Try accessing the modem web interface manually in a browser",
            "Check if your modem model is in the supported list",
            "Open a GitHub issue with your modem model and HTML sample",
        ]


class AuthenticationError(DetectionError):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed", diagnostics: dict | None = None):
        """Initialize authentication error."""
        super().__init__(message, diagnostics)

    def get_troubleshooting_steps(self) -> list[str]:
        """Get troubleshooting steps."""
        return [
            "Verify username and password are correct",
            "Try logging in manually through a web browser",
            "Check if modem requires admin/password reset",
            "Some modems use 'admin'/'password' as defaults",
            "Check modem documentation for default credentials",
        ]


class SessionExpiredError(AuthenticationError):
    """Raised when session expires mid-request.

    This indicates the modem's session timed out during data fetch,
    requiring re-authentication. Common indicators:
    - Login form in data response
    - "UN-AUTH" or session timeout strings
    - HTTP 401 on previously-authenticated endpoint
    """

    def __init__(self, indicator: str | None = None, diagnostics: dict | None = None):
        """Initialize session expired error.

        Args:
            indicator: What triggered the detection (e.g., "UN-AUTH", "login form")
            diagnostics: Additional diagnostic info
        """
        self.indicator = indicator
        message = "Session expired during data fetch"
        if indicator:
            message += f" (detected: {indicator})"
        super().__init__(message, diagnostics)

    def get_troubleshooting_steps(self) -> list[str]:
        """Get troubleshooting steps."""
        return [
            "This is usually temporary - retry should work",
            "If persistent, modem may have short session timeout",
            "Check if someone else logged into modem web interface",
            "Try increasing polling interval to reduce session conflicts",
        ]


class ModemConnectionError(DetectionError):
    """Raised when cannot connect to modem.

    Named ModemConnectionError to avoid shadowing Python's built-in ConnectionError.
    """

    def get_troubleshooting_steps(self) -> list[str]:
        """Get troubleshooting steps."""
        return [
            "Verify the modem IP address is correct (try 192.168.100.1 or 192.168.0.1)",
            "Ensure Home Assistant can reach the modem network",
            "Check if modem web interface is enabled",
            "Try pinging the modem from Home Assistant host",
            "Check firewall settings",
            "Verify modem is powered on and connected",
        ]


class CircuitBreakerError(DetectionError):
    """Raised when circuit breaker trips during detection."""

    def __init__(self, stats: dict):
        """Initialize circuit breaker error with stats."""
        self.stats = stats
        message = f"Detection timeout: Tried {stats['attempts']} parsers in {stats['elapsed_seconds']:.1f}s"
        super().__init__(message, stats)

    def get_user_message(self) -> str:
        """Get user-friendly error message."""
        return (
            f"Detection took too long and was stopped to prevent endless attempts.\n\n"
            f"Attempts: {self.stats['attempts']}/{self.stats['max_attempts']}\n"
            f"Time: {self.stats['elapsed_seconds']:.1f}s / {self.stats['timeout_seconds']}s\n\n"
            f"This usually means the modem is responding slowly or authentication is failing repeatedly."
        )

    def get_troubleshooting_steps(self) -> list[str]:
        """Get troubleshooting steps."""
        return [
            "Check if modem is responsive (try accessing web interface manually)",
            "Verify credentials are correct",
            "Check network connectivity between Home Assistant and modem",
            "Try rebooting the modem",
            "Try manually selecting your modem model instead of auto-detect",
        ]
