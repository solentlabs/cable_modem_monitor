"""Phase 2 auth-detection result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AuthDetail:
    """Result of Phase 2 auth detection."""

    strategy: str
    fields: dict[str, Any] = field(default_factory=dict)
    confidence: str = "high"
    # When the strategy is an auth.strategy ambiguity, strategy is empty and
    # each candidate's fields wait here for the resolution to pick one.
    candidates: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for MCP tool output."""
        result: dict[str, Any] = {
            "strategy": self.strategy,
            "fields": self.fields,
            "confidence": self.confidence,
        }
        if self.candidates:
            result["candidates"] = self.candidates
        return result
