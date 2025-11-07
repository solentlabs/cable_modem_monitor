"""Helper utilities for modem discovery and detection."""
import logging
import time
import requests
from typing import List, Type, Optional, Tuple
from bs4 import BeautifulSoup

_LOGGER = logging.getLogger(__name__)


class ParserHeuristics:
    """Quick checks to narrow parser search space and speed up detection."""

    @staticmethod
    def get_likely_parsers(
        base_url: str, parsers: List[Type], session: requests.Session, verify_ssl: bool = False
    ) -> List[Type]:
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
        likely_parsers = []
        unlikely_parsers = []

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
                        _LOGGER.debug("Heuristics: %s is LIKELY (found '%s' in title/header)",
                                      parser_class.name, manufacturer)
                        likely_parsers.append(parser_class)
                    # Weak indicators (anywhere in page) or model numbers
                    elif any(model.lower() in html for model in parser_class.models):
                        _LOGGER.debug("Heuristics: %s is LIKELY (found model number)", parser_class.name)
                        likely_parsers.append(parser_class)
                    else:
                        unlikely_parsers.append(parser_class)

            else:
                _LOGGER.debug("Heuristics: Root page returned status %s, skipping heuristics",
                              response.status_code)
                return parsers  # Return all parsers if heuristics fail

        except (requests.RequestException, Exception) as e:
            _LOGGER.debug("Heuristics: Failed to fetch root page (%s), trying all parsers", type(e).__name__)
            return parsers  # Return all parsers if heuristics fail

        # If we found likely parsers, return those first, then the rest
        if likely_parsers:
            result = likely_parsers + unlikely_parsers
            _LOGGER.info("Heuristics: Narrowed search to %s likely parsers (out of %s total)",
                         len(likely_parsers), len(parsers))
            return result

        # No heuristics matched, return all parsers
        _LOGGER.debug("Heuristics: No strong indicators found, trying all parsers")
        return parsers

    @staticmethod
    def check_anonymous_access(
        base_url: str, parser_class: Type, session: requests.Session, verify_ssl: bool = False
    ) -> Optional[Tuple[str, str]]:
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
        # Check if parser has URL patterns marked as not requiring auth
        if not hasattr(parser_class, 'url_patterns'):
            return None

        for pattern in parser_class.url_patterns:
            # Look for patterns explicitly marked as not requiring auth
            if not pattern.get('auth_required', True):
                url = f"{base_url}{pattern['path']}"
                try:
                    _LOGGER.debug("Trying anonymous access to %s for parser %s",
                                  url, parser_class.name)
                    response = session.get(url, timeout=5, verify=verify_ssl)

                    if response.status_code == 200:
                        _LOGGER.info("Anonymous access successful to %s (%s bytes)",
                                     url, len(response.text))
                        return (response.text, url)
                    else:
                        _LOGGER.debug("Anonymous access to %s returned status %s",
                                      url, response.status_code)
                except requests.RequestException as e:
                    _LOGGER.debug("Anonymous access to %s failed: %s", url, type(e).__name__)
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
        self.start_time = None
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

        # Start timer on first attempt
        if self.start_time is None:
            self.start_time = time.time()

        # Check max attempts
        if self.attempts >= self.max_attempts:
            _LOGGER.warning(
                "Discovery circuit breaker: Max attempts reached (%s). "
                "Stopping detection to prevent endless loops.",
                self.max_attempts
            )
            self._broken = True
            return False

        # Check timeout
        elapsed = time.time() - self.start_time
        if elapsed > self.timeout:
            _LOGGER.warning(
                "Discovery circuit breaker: Timeout reached (%.1fs > %ss). "
                "Stopping detection.",
                elapsed, self.timeout
            )
            self._broken = True
            return False

        return True

    def record_attempt(self, parser_name: Optional[str] = None):
        """
        Record an authentication/detection attempt.

        Args:
            parser_name: Name of parser being attempted (for logging)
        """
        self.attempts += 1
        elapsed = time.time() - self.start_time if self.start_time else 0

        if parser_name:
            _LOGGER.debug(
                "Discovery attempt %s/%s (%.1fs elapsed): %s",
                self.attempts, self.max_attempts, elapsed, parser_name
            )
        else:
            _LOGGER.debug(
                "Discovery attempt %s/%s (%.1fs elapsed)",
                self.attempts, self.max_attempts, elapsed
            )

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

    def __init__(self, message: str, diagnostics: Optional[dict] = None):
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

    def get_troubleshooting_steps(self) -> List[str]:
        """Get list of troubleshooting steps for user."""
        return []


class ParserNotFoundError(DetectionError):
    """Raised when no parser can be detected for the modem."""

    def __init__(self, modem_info: Optional[dict] = None, attempted_parsers: Optional[List[str]] = None):
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

    def get_troubleshooting_steps(self) -> List[str]:
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

    def get_troubleshooting_steps(self) -> List[str]:
        """Get troubleshooting steps."""
        return [
            "Verify username and password are correct",
            "Try logging in manually through a web browser",
            "Check if modem requires admin/password reset",
            "Some modems use 'admin'/'password' as defaults",
            "Check modem documentation for default credentials",
        ]


class ConnectionError(DetectionError):
    """Raised when cannot connect to modem."""

    def get_troubleshooting_steps(self) -> List[str]:
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

    def get_troubleshooting_steps(self) -> List[str]:
        """Get troubleshooting steps."""
        return [
            "Check if modem is responsive (try accessing web interface manually)",
            "Verify credentials are correct",
            "Check network connectivity between Home Assistant and modem",
            "Try rebooting the modem",
            "Try manually selecting your modem model instead of auto-detect",
        ]
