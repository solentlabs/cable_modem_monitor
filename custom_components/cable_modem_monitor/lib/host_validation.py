"""Host validation utilities for preventing command injection.

Shared by config_flow.py and health_monitor.py to avoid code duplication.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from ..const import INVALID_HOST_CHARS

# Compiled regex patterns for host validation
_IPV4_PATTERN = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")
_IPV6_PATTERN = re.compile(r"^([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}$")
_HOSTNAME_PATTERN = re.compile(
    r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?" r"(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$"
)


def is_valid_host(host: str) -> bool:
    """
    Check if hostname or IP address is valid and safe.

    Args:
        host: Hostname or IP address to validate

    Returns:
        bool: True if host is valid and contains no injection characters
    """
    if not host or len(host) > 253:  # Max domain name length
        return False

    # Block shell metacharacters
    if any(char in host for char in INVALID_HOST_CHARS):
        return False

    # Must match one of: IPv4, IPv6, or valid hostname
    return bool(_IPV4_PATTERN.match(host) or _IPV6_PATTERN.match(host) or _HOSTNAME_PATTERN.match(host))


def extract_hostname(host: str) -> str:
    """
    Extract and validate hostname from host string (may include URL).

    Args:
        host: Hostname, IP address, or full URL

    Returns:
        str: Cleaned hostname

    Raises:
        ValueError: If validation fails
    """
    if not host:
        raise ValueError("Host cannot be empty")

    host_clean = host.strip()

    # Extract hostname from URL if provided
    if host_clean.startswith(("http://", "https://")):
        try:
            parsed = urlparse(host_clean)
            if parsed.scheme not in ["http", "https"]:
                raise ValueError("Only HTTP and HTTPS protocols are allowed")
            if not parsed.netloc:
                raise ValueError("Invalid URL format")
            hostname = parsed.hostname or parsed.netloc.split(":")[0]
        except Exception as err:
            raise ValueError(f"Invalid URL format: {err}") from err
    elif ":" in host_clean and "//" not in host_clean:
        # Handle IP:port format (e.g., "192.168.1.1:8080")
        # But not protocol schemes like "ftp://..."
        hostname = host_clean.split(":")[0]
    else:
        hostname = host_clean

    # Validate the extracted hostname
    if not is_valid_host(hostname):
        raise ValueError("Invalid host format. Must be a valid IP address or hostname")

    return hostname


def parse_host_input(raw: str) -> tuple[str, str | None]:
    """Decompose raw user input into (hostname_with_port, protocol_or_none).

    Examples:
        "192.168.100.1"           -> ("192.168.100.1", None)
        "https://192.168.100.1"   -> ("192.168.100.1", "https")
        "http://192.168.100.1/"   -> ("192.168.100.1", "http")
        "192.168.100.1:8080"      -> ("192.168.100.1:8080", None)
        "HTTPS://192.168.100.1"   -> ("192.168.100.1", "https")

    Args:
        raw: Raw user input (bare IP, hostname, or URL with protocol).

    Returns:
        Tuple of (host_with_optional_port, protocol_or_none).
    """
    stripped = raw.strip()
    lower = stripped.lower()

    if lower.startswith(("http://", "https://")):
        parsed = urlparse(stripped)
        protocol = parsed.scheme.lower()
        # netloc includes host and optional port
        host = parsed.netloc
        if not host:
            # Malformed URL — fall through to bare host
            return (stripped, None)
        return (host, protocol)

    return (stripped, None)


def build_url(host: str, protocol: str | None = None) -> str:
    """Reconstruct URL from host and optional protocol.

    Args:
        host: Hostname or IP, optionally with port (e.g., "192.168.100.1:8080").
        protocol: "http", "https", or None (defaults to "http").

    Returns:
        Full URL string (e.g., "https://192.168.100.1").
    """
    scheme = protocol or "http"
    return f"{scheme}://{host}"
