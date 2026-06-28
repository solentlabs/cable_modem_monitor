"""Step 4: Response body integrity.

Detects responses whose body was replaced or stripped after capture
(over-sanitization). The tell is tool-agnostic: a recorded ``content.size``
that greatly exceeds the actual body length means something shrank the body
between capture and now — typically an over-aggressive sanitizer that redacted
a whole structured payload (e.g. base64-encoded JSON) down to a single token.
Such a HAR carries no usable data; recapture is the only fix.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from .har_utils import HARD_STOP_PREFIX, is_static_resource

# A body is flagged when its recorded size dwarfs the actual text: at least
# this ratio larger AND this many bytes larger. The floor keeps tiny payloads
# (a short status blob) from tripping on noise; the ratio catches real data
# responses collapsed to a token. One flagged data endpoint condemns the HAR.
_SIZE_RATIO = 4
_SIZE_FLOOR_BYTES = 100
_MAX_LISTED = 5


def validate_response_integrity(entries: list[dict[str, Any]], issues: list[str]) -> None:
    """Flag responses whose body was stripped/replaced after capture.

    Appends a single HARD STOP when one or more data responses show a
    ``size`` vs body-length divergence indicating over-sanitization.
    """
    affected: list[str] = []

    for entry in entries:
        url = entry.get("request", {}).get("url", "")
        if is_static_resource(url):
            continue

        response = entry.get("response", {})
        status = response.get("status", 0)
        if not 200 <= status < 300:
            continue

        content = response.get("content", {})
        # No need to special-case content.encoding == "base64": legitimate base64
        # text runs ~1.33x its decoded byte size, so real binary always has
        # text_len > size and can't satisfy the divergence test below. An
        # over-sanitized body keeps the stale base64 marker but a tiny token —
        # exactly what we want to catch.
        size = content.get("size", 0)
        text_len = len(content.get("text", ""))
        # Empty text is "no body captured", a different (handled) case — only a
        # short, non-empty body sitting where a large one should be is the tell.
        if text_len == 0 or size <= 0:
            continue

        if size >= text_len * _SIZE_RATIO and size - text_len >= _SIZE_FLOOR_BYTES:
            parsed = urlparse(url)
            endpoint = parsed.path + (f"?{parsed.query}" if parsed.query else "")
            affected.append(f"{endpoint} (size {size} bytes, body {text_len} chars)")

    if not affected:
        return

    listed = ", ".join(affected[:_MAX_LISTED])
    if len(affected) > _MAX_LISTED:
        listed += f", (+{len(affected) - _MAX_LISTED} more)"
    issues.append(
        f"{HARD_STOP_PREFIX} {len(affected)} response(s) had their body stripped "
        f"after capture — the HAR was over-sanitized and carries no usable data; "
        f"recapture with a fixed sanitizer. Affected: {listed}"
    )
