"""Phase 2/4 result types and pipeline-wide gap detection.

Auth and action types used by auth.http, auth.hnap, actions.http,
actions.hnap, and the phase dispatchers.

``CoreGap`` is the shared type used across all phases when the pipeline
encounters a pattern that Core does not yet support. Gaps halt the
intake process and provide wire evidence for a development effort.

Phase 5 types live in ``format/types.py``.
Phase 6 types live in ``mapping/types.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# -----------------------------------------------------------------------
# Pipeline-wide: Core gap detection
# -----------------------------------------------------------------------


@dataclass
class CoreGap:
    """A pattern the pipeline detected but Core cannot yet handle.

    When the intake pipeline encounters an auth mechanism, action
    endpoint, session pattern, or data format that doesn't match any
    known Core pattern, it creates a ``CoreGap`` with structured wire
    evidence. This halts config generation and provides enough detail
    to file a development issue or extend Core's pattern set.

    Attributes:
        phase: Pipeline phase that produced this gap.
        category: Machine-readable key (e.g., ``unmatched_login``).
        summary: Human-readable one-liner describing the gap.
        evidence: Structured wire data from the HAR for diagnosis.
    """

    phase: str
    category: str
    summary: str
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for MCP tool output."""
        return {
            "phase": self.phase,
            "category": self.category,
            "summary": self.summary,
            "evidence": self.evidence,
        }


# -----------------------------------------------------------------------
# Phase 2: Auth
# -----------------------------------------------------------------------


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


# -----------------------------------------------------------------------
# Phase 4: Actions
# -----------------------------------------------------------------------


@dataclass
class ActionDetail:
    """A single detected action (logout or restart)."""

    type: str  # "http" or "hnap"
    method: str  # "GET", "POST"
    endpoint: str
    params: dict[str, str] = field(default_factory=dict)
    action_name: str = ""
    credential_params: list[str] = field(default_factory=list)

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
        if self.credential_params:
            result["credential_params"] = self.credential_params
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
