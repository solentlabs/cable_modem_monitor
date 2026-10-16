"""Endpoint matching: whether a captured URL addresses a declared endpoint."""

from __future__ import annotations

from .auth.base import _segments, _template_match


def url_matches_endpoint(endpoint: str, url: str) -> bool:
    """Same path segments, queries ignored, ``{...}`` segments wild."""
    declared = endpoint.split("?", 1)[0]
    sent = url.split("://", 1)[-1]
    sent_path = "/" + sent.split("/", 1)[1] if "/" in sent else "/"
    return _template_match(_segments(declared), _segments(sent_path.split("?", 1)[0]))
