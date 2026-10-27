"""Port and scheme override for actions served from a second web server."""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

_DEFAULT_PORTS = {"http": 80, "https": 443}


def with_port(base_url: str, port: int | None, scheme: str | None = None) -> str:
    """Return ``base_url`` with its port and scheme replaced where given; the host is kept."""
    if port is None and scheme is None:
        return base_url
    parts = urlsplit(base_url)
    if port is not None:
        parts = parts._replace(netloc=_netloc(parts.hostname, port))
    elif scheme is not None and scheme != parts.scheme and parts.port == _DEFAULT_PORTS.get(parts.scheme):
        # The default port belongs to the scheme being replaced, so it goes with it.
        parts = parts._replace(netloc=_netloc(parts.hostname, None))
    if scheme is not None:
        parts = parts._replace(scheme=scheme)
    return urlunsplit(parts)


def _netloc(hostname: str | None, port: int | None) -> str:
    """Host with an optional port, bracketing an IPv6 literal."""
    host = hostname or ""
    if ":" in host:
        host = f"[{host}]"
    return host if port is None else f"{host}:{port}"
