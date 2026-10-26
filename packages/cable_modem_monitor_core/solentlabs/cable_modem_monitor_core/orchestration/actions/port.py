"""Port and scheme override for actions served from a second web server."""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit


def with_port(base_url: str, port: int | None, scheme: str | None = None) -> str:
    """Return ``base_url`` with its port and scheme replaced where given; the host is kept."""
    if port is None and scheme is None:
        return base_url
    parts = urlsplit(base_url)
    if port is not None:
        host = parts.hostname or ""
        if ":" in host:
            host = f"[{host}]"
        parts = parts._replace(netloc=f"{host}:{port}")
    if scheme is not None:
        parts = parts._replace(scheme=scheme)
    return urlunsplit(parts)
