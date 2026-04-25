"""Phase 2 auth-detection result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..types import CoreGap


@dataclass
class AuthDetail:
    """Result of Phase 2 auth detection."""

    strategy: str
    fields: dict[str, Any] = field(default_factory=dict)
    confidence: str = "high"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for MCP tool output."""
        return {
            "strategy": self.strategy,
            "fields": self.fields,
            "confidence": self.confidence,
        }

    @classmethod
    def detect(
        cls,
        entries: list[dict[str, Any]],
        transport: str,
        warnings: list[str],
        hard_stops: list[str],
        core_gaps: list[CoreGap] | None = None,
    ) -> AuthDetail:
        """Detect auth strategy from HAR entries.

        Dispatches to transport-specific detection:
        - HNAP: always ``hnap`` strategy, detect hmac_algorithm
        - HTTP: walks the Phase 2 decision tree

        Args:
            entries: HAR ``log.entries`` list.
            transport: Detected transport (``http`` or ``hnap``).
            warnings: Mutable list to append warnings to.
            hard_stops: Mutable list to append hard stops to.
            core_gaps: Mutable list to append core gap items to.

        Returns:
            AuthDetail with strategy, extracted fields, and confidence.
        """
        # Late imports: sibling dispatchers import from this module, so
        # top-level imports would create a cycle.
        from .hnap import detect_hnap_auth
        from .http import detect_http_auth

        if core_gaps is None:
            core_gaps = []
        if transport == "hnap":
            return detect_hnap_auth(entries, warnings)
        return detect_http_auth(entries, warnings, hard_stops, core_gaps)
