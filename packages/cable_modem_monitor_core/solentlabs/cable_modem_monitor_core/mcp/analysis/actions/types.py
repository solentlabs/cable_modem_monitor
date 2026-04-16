"""Phase 4 action-detection result types."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..types import CoreGap

_CREDENTIAL_NAME_KEYWORDS: frozenset[str] = frozenset({"password", "passwd", "pwd", "secret", "token"})

_SANITIZER_VALUE_PATTERN: re.Pattern[str] = re.compile(r"^(FIELD|PASS)_[0-9a-f]+$")


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

    @classmethod
    def detect(
        cls,
        entries: list[dict[str, Any]],
        transport: str,
        warnings: list[str] | None = None,
        core_gaps: list[CoreGap] | None = None,
    ) -> ActionsDetail:
        """Detect logout and restart actions from HAR entries.

        Dispatches to transport-specific detection, then classifies
        credential params across all detected actions.

        Args:
            entries: HAR ``log.entries`` list.
            transport: Detected transport (``http`` or ``hnap``).
            warnings: Mutable list to append suggestions to.
            core_gaps: Mutable list to append core gap items to.

        Returns:
            ActionsDetail with detected actions and credential annotations.
        """
        # Late imports: sibling dispatchers import from this module, so
        # top-level imports would create a cycle.
        from .hnap import detect_hnap_actions
        from .http import detect_http_actions

        if warnings is None:
            warnings = []
        if core_gaps is None:
            core_gaps = []
        if transport == "hnap":
            result = detect_hnap_actions(entries)
        else:
            result = detect_http_actions(entries, warnings, core_gaps)
        result._classify_credentials()
        return result

    def _classify_credentials(self) -> None:
        """Identify and neutralize credential params in detected actions.

        Credential values are replaced with empty strings (the sanitized
        values are meaningless artifacts). Field names are recorded in
        ``credential_params`` so the MCP output annotates which params
        were credentials vs action triggers.
        """
        for action in (self.logout, self.restart):
            if action and action.params:
                cred_names = _detect_credential_params(action.params)
                action.credential_params = sorted(cred_names)
                for name in cred_names:
                    action.params[name] = ""


def _detect_credential_params(params: dict[str, str]) -> set[str]:
    """Detect which param names are likely credentials.

    Uses two heuristics (either triggers classification):
    - Field name contains a credential keyword.
    - Value matches HAR sanitizer pattern (``FIELD_hex``, ``PASS_hex``).
    """
    credential_names: set[str] = set()
    for name, value in params.items():
        name_lower = name.lower()
        if any(kw in name_lower for kw in _CREDENTIAL_NAME_KEYWORDS) or _SANITIZER_VALUE_PATTERN.match(value):
            credential_names.add(name)
    return credential_names
