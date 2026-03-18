"""HAR Analysis Tool -- MCP tool.

Orchestrates Phases 1-4 of the ONBOARDING_SPEC decision tree:
1. Transport detection (HNAP vs HTTP)
2. Auth strategy detection and field extraction
3. Session detection (cookies, headers, tokens)
4. Action detection (logout, restart)

Phases 5-6 (format detection, field mapping) are deferred to Step 3.

Per ONBOARDING_SPEC.md ``analyze_har`` tool contract.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .analysis.actions import ActionsDetail, detect_actions
from .analysis.auth import AuthDetail, detect_auth
from .analysis.session import SessionDetail, detect_session
from .analysis.transport import TransportResult, detect_transport


@dataclass
class AnalysisResult:
    """Complete result of HAR analysis (Phases 1-4).

    The ``sections`` field is populated by Phases 5-6 (Step 3).
    """

    transport: TransportResult
    auth: AuthDetail
    session: SessionDetail
    actions: ActionsDetail
    sections: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    hard_stops: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict matching the MCP tool output contract."""
        return {
            "transport": self.transport.transport,
            "confidence": self.transport.confidence,
            "auth": self.auth.to_dict(),
            "session": self.session.to_dict(),
            "actions": self.actions.to_dict(),
            "sections": self.sections,
            "warnings": self.warnings,
            "hard_stops": self.hard_stops,
        }


def analyze_har(har_path: str | Path) -> AnalysisResult:
    """Run HAR analysis Phases 1-4.

    Loads the HAR file, then runs transport detection, auth strategy
    detection, session detection, and action detection in sequence.

    Args:
        har_path: Path to a validated ``.har`` file.

    Returns:
        AnalysisResult with detected transport, auth, session, actions,
        and any warnings or hard stops.

    Raises:
        FileNotFoundError: If har_path does not exist.
        ValueError: If HAR file cannot be parsed or has no entries.
    """
    har_path = Path(har_path)
    entries = _load_har_entries(har_path)

    warnings: list[str] = []
    hard_stops: list[str] = []

    # Phase 1: Transport
    transport_result = detect_transport(entries)

    # Phase 2: Auth
    auth_result = detect_auth(entries, transport_result.transport, warnings, hard_stops)

    # Phase 3: Session
    session_result = detect_session(entries, transport_result.transport, auth_result.strategy, warnings)

    # Phase 4: Actions
    actions_result = detect_actions(entries, transport_result.transport)

    return AnalysisResult(
        transport=transport_result,
        auth=auth_result,
        session=session_result,
        actions=actions_result,
        warnings=warnings,
        hard_stops=hard_stops,
    )


def _load_har_entries(har_path: Path) -> list[dict[str, Any]]:
    """Load HAR file and return entries list.

    Performs minimal structural loading -- not full validation.
    ``validate_har`` should be called before ``analyze_har``.

    Raises:
        FileNotFoundError: If har_path does not exist.
        ValueError: If HAR file cannot be parsed or has no entries.
    """
    if not har_path.exists():
        raise FileNotFoundError(f"HAR file not found: {har_path}")

    try:
        data = json.loads(har_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in HAR file: {exc}") from exc

    entries: list[dict[str, Any]] = data.get("log", {}).get("entries", [])
    if not entries:
        raise ValueError("HAR file has no entries in log.entries")

    return entries
