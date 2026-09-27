"""Phase 1 - Transport detection.

Scans HAR entries for protocol markers. An HNAP marker makes the
transport ``hnap``; a JSON-RPC 2.0 request body makes it ``jsonrpc``;
otherwise ``http``. Confidence is always ``high``: each marker is a
protocol member, not a heuristic.

Per docs/ONBOARDING_SPEC.md Phase 1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..validation.har_utils import is_hnap_request, jsonrpc_method, lower_headers


@dataclass
class TransportResult:
    """Result of Phase 1 transport detection."""

    transport: str
    confidence: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for MCP tool output."""
        return {"transport": self.transport, "confidence": self.confidence}

    @classmethod
    def detect(cls, entries: list[dict[str, Any]]) -> TransportResult:
        """Detect transport protocol from HAR entries.

        Scans all entries for HNAP markers (``/HNAP1/`` URL, ``SOAPAction``
        header, ``HNAP_AUTH`` header), then for a JSON-RPC 2.0 request
        body. HNAP → ``hnap``, JSON-RPC → ``jsonrpc``, else ``http``.

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
                return cls(transport="hnap", confidence="high")

        if any(jsonrpc_method(entry["request"]) is not None for entry in entries):
            return cls(transport="jsonrpc", confidence="high")

        return cls(transport="http", confidence="high")
