"""Host input parsing utilities.

Decomposes raw user input (bare IP, hostname, or URL with protocol)
into structured components for the config entry.  Used by both the
config flow and ``__init__.py`` startup.

Reachability validation (is the host actually up?) is handled by
Core's ``connectivity`` module at config-flow validation time.
"""

from __future__ import annotations

from urllib.parse import urlparse


def parse_host_input(raw: str) -> tuple[str, str | None]:
    """Decompose raw user input into (hostname_with_port, protocol_or_none).

    Examples::

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
