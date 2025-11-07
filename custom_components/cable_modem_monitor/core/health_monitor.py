"""Modem Health Monitor - Dual-layer network diagnostics."""
import asyncio
import logging
import re
import ssl
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse
import aiohttp

_LOGGER = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""

    timestamp: float
    ping_success: bool
    ping_latency_ms: Optional[float]
    http_success: bool
    http_latency_ms: Optional[float]

    @property
    def is_healthy(self) -> bool:
        """Return True if modem is responding to either ping or HTTP."""
        return self.ping_success or self.http_success

    @property
    def status(self) -> str:
        """Return human-readable status."""
        if self.ping_success and self.http_success:
            return "healthy"
        elif self.ping_success and not self.http_success:
            return "degraded"
        elif not self.ping_success and self.http_success:
            return "icmp_blocked"
        else:
            return "unresponsive"

    @property
    def diagnosis(self) -> str:
        """Return detailed diagnosis."""
        if self.ping_success and self.http_success:
            return "Fully responsive"
        elif self.ping_success and not self.http_success:
            return "Web server issue"
        elif not self.ping_success and self.http_success:
            return "ICMP blocked (firewall)"
        else:
            return "Network down / offline"


class ModemHealthMonitor:
    """
    Monitor modem health using dual-layer diagnostics.

    Performs both ICMP ping (Layer 3) and HTTP HEAD (Layer 7) checks
    to distinguish between network issues, web server issues, and firewall blocks.
    """

    def __init__(self, max_history: int = 100, verify_ssl: bool = False, ssl_context=None):
        """Initialize health monitor.

        Args:
            max_history: Maximum number of health check results to retain
            verify_ssl: Enable SSL certificate verification (default: False for self-signed certs)
            ssl_context: Pre-created SSL context (optional, to avoid blocking I/O in event loop)
        """
        self.max_history = max_history
        self.verify_ssl = verify_ssl
        self.history: list[HealthCheckResult] = []
        self.consecutive_failures = 0
        self.total_checks = 0
        self.successful_checks = 0

        # Use provided SSL context or create a new one
        # NOTE: If creating here, ensure this __init__ is NOT called from async context
        if ssl_context is not None:
            self._ssl_context = ssl_context
        else:
            self._ssl_context = ssl.create_default_context()
            if not verify_ssl:
                self._ssl_context.check_hostname = False
                self._ssl_context.verify_mode = ssl.CERT_NONE
            _LOGGER.debug(
                "SSL certificate verification is disabled for this modem connection. "
                "This is common for cable modems with self-signed certificates."
            )

    async def check_health(self, base_url: str) -> HealthCheckResult:
        """
        Perform dual-layer health check.

        Args:
            base_url: Modem URL (e.g., http://192.168.100.1)

        Returns:
            HealthCheckResult with ping and HTTP status
        """
        # Extract host from URL using proper URL parsing
        try:
            parsed = urlparse(base_url)
            host = parsed.hostname or parsed.netloc.split(':')[0] if parsed.netloc else base_url

            # Validate host format (basic IP or hostname validation)
            if not host or not self._is_valid_host(host):
                _LOGGER.error("Invalid host extracted from URL: %s", base_url)
                host = None
        except Exception as e:
            _LOGGER.error("Failed to parse URL %s: %s", base_url, e)
            host = None

        # Run ping and HTTP check in parallel (skip ping if host is invalid)
        if host:
            ping_result, http_result = await asyncio.gather(
                self._check_ping(host),
                self._check_http(base_url),
                return_exceptions=True
            )

            # Handle exceptions
            if isinstance(ping_result, BaseException):
                _LOGGER.debug("Ping check exception: %s", ping_result)
                ping_success, ping_latency = False, None
            else:
                ping_success, ping_latency = ping_result

            if isinstance(http_result, BaseException):
                _LOGGER.debug("HTTP check exception: %s", http_result)
                http_success, http_latency = False, None
            else:
                http_success, http_latency = http_result
        else:
            # Invalid host - both checks fail
            ping_success, ping_latency = False, None
            http_success, http_latency = False, None

        # Create result
        result = HealthCheckResult(
            timestamp=time.time(),
            ping_success=ping_success,
            ping_latency_ms=ping_latency,
            http_success=http_success,
            http_latency_ms=http_latency,
        )

        # Update statistics
        self._update_stats(result)

        # Store in history
        self.history.append(result)
        if len(self.history) > self.max_history:
            self.history.pop(0)

        _LOGGER.debug(
            "Health check: %s (ping=%s, http=%s)",
            result.status,
            ping_success,
            http_success
        )

        return result

    async def _check_ping(self, host: str) -> tuple[bool, float | None]:
        """
        Perform ICMP ping check with input validation.

        Args:
            host: Validated hostname or IP address

        Returns:
            tuple: (success: bool, latency_ms: float | None)
        """
        try:
            # Additional validation to prevent command injection
            if not host or not self._is_valid_host(host):
                _LOGGER.error("Invalid host for ping: %s", host)
                return False, None

            # Use system ping command (works on Linux and Windows)
            # -c 1 = send 1 packet (Linux)
            # -W 2 = timeout 2 seconds (Linux)
            start_time = time.time()

            # Run ping command with validated host
            # Using asyncio.create_subprocess_exec with separate arguments prevents shell injection
            proc = await asyncio.create_subprocess_exec(
                'ping', '-c', '1', '-W', '2', host,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await proc.communicate()
            latency_ms = (time.time() - start_time) * 1000

            # Check return code (0 = success)
            success = proc.returncode == 0

            return success, latency_ms if success else None

        except Exception as e:
            _LOGGER.debug("Ping exception for %s: %s", host, e)
            return False, None

    async def _check_http(self, base_url: str) -> tuple[bool, float | None]:
        """
        Perform HTTP check with SSL verification and redirect validation.

        Returns:
            tuple: (success: bool, latency_ms: float | None)
        """
        try:
            start_time = time.time()

            # Validate base URL before making request
            if not self._is_valid_url(base_url):
                _LOGGER.error("Invalid URL for HTTP check: %s", base_url)
                return False, None

            # Use pre-configured SSL context (created during __init__ to avoid blocking I/O in event loop)
            timeout = aiohttp.ClientTimeout(total=5)
            connector = aiohttp.TCPConnector(ssl=self._ssl_context)

            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                # Try HEAD first (lightweight)
                try:
                    async with session.head(base_url, allow_redirects=False) as response:
                        # Validate redirect if present
                        if response.status in (301, 302, 303, 307, 308):
                            redirect_url = response.headers.get('Location', '')
                            if not self._is_safe_redirect(base_url, redirect_url):
                                _LOGGER.warning("Unsafe redirect detected: %s -> %s", base_url, redirect_url)
                                return False, None

                        latency_ms = (time.time() - start_time) * 1000
                        # Accept any response (2xx, 3xx, 4xx) as "alive"
                        success = response.status < 500
                        return success, latency_ms if success else None
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    # HEAD failed, try GET (some modems don't support HEAD)
                    start_time = time.time()  # Reset timer
                    async with session.get(base_url, allow_redirects=False) as response:
                        # Validate redirect if present
                        if response.status in (301, 302, 303, 307, 308):
                            redirect_url = response.headers.get('Location', '')
                            if not self._is_safe_redirect(base_url, redirect_url):
                                _LOGGER.warning("Unsafe redirect detected: %s -> %s", base_url, redirect_url)
                                return False, None

                        latency_ms = (time.time() - start_time) * 1000
                        success = response.status < 500
                        return success, latency_ms if success else None

        except asyncio.TimeoutError:
            _LOGGER.debug("HTTP check timeout for %s", base_url)
            return False, None
        except aiohttp.ClientConnectorError as e:
            _LOGGER.debug("HTTP check connection error for %s: %s", base_url, e)
            return False, None
        except Exception as e:
            _LOGGER.debug("HTTP check exception for %s: %s", base_url, e)
            return False, None

    def _update_stats(self, result: HealthCheckResult):
        """Update running statistics."""
        self.total_checks += 1

        if result.is_healthy:
            self.consecutive_failures = 0
            self.successful_checks += 1
        else:
            self.consecutive_failures += 1

    @property
    def average_ping_latency(self) -> Optional[float]:
        """Calculate average ping latency from recent history."""
        latencies = [
            h.ping_latency_ms for h in self.history
            if h.ping_success and h.ping_latency_ms is not None
        ]
        if not latencies:
            return None
        return sum(latencies) / len(latencies)

    @property
    def average_http_latency(self) -> Optional[float]:
        """Calculate average HTTP latency from recent history."""
        latencies = [
            h.http_latency_ms for h in self.history
            if h.http_success and h.http_latency_ms is not None
        ]
        if not latencies:
            return None
        return sum(latencies) / len(latencies)

    def get_status_summary(self) -> dict:
        """Get current health status summary."""
        if not self.history:
            return {
                "status": "unknown",
                "consecutive_failures": 0,
                "total_checks": 0,
            }

        latest = self.history[-1]
        return {
            "status": latest.status,
            "diagnosis": latest.diagnosis,
            "consecutive_failures": self.consecutive_failures,
            "total_checks": self.total_checks,
            "ping_success": latest.ping_success,
            "ping_latency_ms": latest.ping_latency_ms,
            "http_success": latest.http_success,
            "http_latency_ms": latest.http_latency_ms,
            "avg_ping_latency_ms": self.average_ping_latency,
            "avg_http_latency_ms": self.average_http_latency,
        }

    def _is_valid_host(self, host: str) -> bool:
        """
        Validate hostname or IP address to prevent command injection.

        Args:
            host: Hostname or IP address to validate

        Returns:
            bool: True if host is valid
        """
        if not host or len(host) > 253:  # Max domain name length
            return False

        # Allow IPv4, IPv6, and hostnames
        # Block shell metacharacters and whitespace
        invalid_chars = [';', '&', '|', '$', '`', '\n', '\r', '\t', ' ', '<', '>', '(', ')', '{', '}']
        if any(char in host for char in invalid_chars):
            return False

        # Basic pattern validation for IP or hostname
        # IPv4: x.x.x.x where x is 0-255
        # IPv6: valid hex groups with colons
        # Hostname: alphanumeric with dots and hyphens
        ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        ipv6_pattern = r'^([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}$'
        hostname_pattern = (
            r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?'
            r'(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
        )

        return (re.match(ipv4_pattern, host) is not None or
                re.match(ipv6_pattern, host) is not None or
                re.match(hostname_pattern, host) is not None)

    def _is_valid_url(self, url: str) -> bool:
        """
        Validate URL format and scheme.

        Args:
            url: URL to validate

        Returns:
            bool: True if URL is valid
        """
        try:
            parsed = urlparse(url)
            # Only allow http and https schemes
            if parsed.scheme not in ['http', 'https']:
                return False
            # Must have a valid netloc
            if not parsed.netloc:
                return False
            # Validate the host part
            host = parsed.hostname or parsed.netloc.split(':')[0]
            return self._is_valid_host(host)
        except Exception:
            return False

    def _is_safe_redirect(self, original_url: str, redirect_url: str) -> bool:
        """
        Validate that a redirect URL is safe (same host or whitelisted).

        Args:
            original_url: Original request URL
            redirect_url: Redirect target URL

        Returns:
            bool: True if redirect is safe
        """
        try:
            # Parse both URLs
            original_parsed = urlparse(original_url)
            redirect_parsed = urlparse(redirect_url)

            # If redirect is relative, it's safe
            if not redirect_parsed.scheme:
                return True

            # Only allow http/https redirects
            if redirect_parsed.scheme not in ['http', 'https']:
                _LOGGER.warning("Redirect to non-HTTP scheme blocked: %s", redirect_parsed.scheme)
                return False

            # Check if redirect is to the same host
            original_host = original_parsed.hostname or original_parsed.netloc
            redirect_host = redirect_parsed.hostname or redirect_parsed.netloc

            if original_host == redirect_host:
                return True

            # For modem health checks, we typically expect same-host redirects
            # External redirects are suspicious and blocked by default
            _LOGGER.warning("Cross-host redirect blocked: %s -> %s", original_host, redirect_host)
            return False

        except Exception as e:
            _LOGGER.error("Error validating redirect: %s", e)
            return False
