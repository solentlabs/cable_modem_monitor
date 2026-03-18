"""Phase 1 - Transport detection.

Scans HAR entries for HNAP protocol markers. If any HNAP marker is found,
transport is ``hnap``; otherwise ``http``. Confidence is always ``high``
because HNAP markers have no false positives.

Per docs/ONBOARDING_SPEC.md Phase 1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..validation.har_utils import is_hnap_request, lower_headers


@dataclass
class TransportResult:
    """Result of Phase 1 transport detection."""

    transport: str
    confidence: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for MCP tool output."""
        return {"transport": self.transport, "confidence": self.confidence}


def detect_transport(entries: list[dict[str, Any]]) -> TransportResult:
    """Detect transport protocol from HAR entries.

    Scans all entries for HNAP markers (``/HNAP1/`` URL, ``SOAPAction``
    header, ``HNAP_AUTH`` header). Any match → ``hnap``, else ``http``.

    Args:
        entries: HAR ``log.entries`` list.

    Returns:
        TransportResult with transport and confidence.
    """
    for entry in entries:
        req = entry["request"]
        url = req.get("url", "")
        req_hdrs = lower_headers(req)
        if is_hnap_request(url, req_hdrs):
            return TransportResult(transport="hnap", confidence="high")

    return TransportResult(transport="http", confidence="high")
