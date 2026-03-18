"""Shared result types for HAR analysis phases.

These types are used across transport-specific modules (auth_http,
auth_hnap, actions_http, actions_hnap) and the phase dispatchers
(auth, actions). They live here to avoid circular imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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


@dataclass
class ActionDetail:
    """A single detected action (logout or restart)."""

    type: str  # "http" or "hnap"
    method: str  # "GET", "POST"
    endpoint: str
    params: dict[str, str] = field(default_factory=dict)
    action_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for MCP tool output."""
        result: dict[str, Any] = {
            "type": self.type,
            "method": self.method,
            "endpoint": self.endpoint,
        }
        if self.params:
            result["params"] = self.params
        if self.action_name:
            result["action_name"] = self.action_name
        return result


@dataclass
class ActionsDetail:
    """Result of Phase 4 action detection."""

    logout: ActionDetail | None = None
    restart: ActionDetail | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for MCP tool output."""
        return {
            "logout": self.logout.to_dict() if self.logout else None,
            "restart": self.restart.to_dict() if self.restart else None,
        }
