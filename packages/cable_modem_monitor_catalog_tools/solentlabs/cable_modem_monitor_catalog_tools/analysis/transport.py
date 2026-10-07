"""Phase 1 - Transport detection.

Scans HAR entries for protocol markers. An HNAP marker makes the
transport ``hnap``; a JSON-RPC 2.0 login call makes it ``json_rpc``; a
CBN login call makes it ``cbn``; otherwise ``http``. Confidence is
always ``high``: each marker is a protocol member, not a heuristic.

Per docs/ONBOARDING_SPEC.md Phase 1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..validation.har_utils import is_hnap_request, lower_headers
from .auth.cbn import cbn_login_params
from .auth.json_rpc import json_rpc_login_credentials


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
        header, ``HNAP_AUTH`` header), then for a JSON-RPC 2.0 login call,
        then for a CBN login call. HNAP → ``hnap``, JSON-RPC login →
        ``json_rpc``, CBN login → ``cbn``, else ``http``.

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

        # The login decides: JSON-RPC calls outside auth and data (LuCI
        # ubus plumbing) run on modems whose transport is http.
        if any(json_rpc_login_credentials(entry["request"]) is not None for entry in entries):
            return cls(transport="json_rpc", confidence="high")

        if any(cbn_login_params(entry["request"]) is not None for entry in entries):
            return cls(transport="cbn", confidence="high")

        return cls(transport="http", confidence="high")
