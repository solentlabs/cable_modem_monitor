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
    else:
        hostname = host_clean

    # Validate the extracted hostname
    if not is_valid_host(hostname):
        raise ValueError("Invalid host format. Must be a valid IP address or hostname")

    return hostname
