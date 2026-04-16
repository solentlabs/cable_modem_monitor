"""HAR Analysis Tool -- MCP tool.

Orchestrates Phases 1-6 of the ONBOARDING_SPEC decision tree:
1. Transport detection (HNAP vs HTTP)
2. Auth strategy detection and field extraction
3. Session detection (cookies, headers, tokens)
4. Action detection (logout, restart)
5. Format detection (table, table_transposed, javascript, json, hnap)
6. Field mapping extraction (header-to-field, column/offset/key mappings)

Per ONBOARDING_SPEC.md ``analyze_har`` tool contract.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..har import load_har_json
from .analysis.actions import ActionsDetail
from .analysis.auth import AuthDetail
from .analysis.format import detect_sections
from .analysis.js_endpoints import detect_uncaptured_endpoints
from .analysis.request_requirements import detect_request_requirements
from .analysis.session import SessionDetail
from .analysis.transport import TransportResult
from .analysis.types import CoreGap, FleetPatterns


@dataclass
class AnalysisResult:
    """Complete result of HAR analysis (Phases 1-6)."""

    transport: TransportResult
    auth: AuthDetail
    session: SessionDetail
    actions: ActionsDetail
    sections: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    hard_stops: list[str] = field(default_factory=list)
    core_gaps: list[CoreGap] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict matching the MCP tool output contract."""
        result: dict[str, Any] = {
            "transport": self.transport.transport,
            "confidence": self.transport.confidence,
            "auth": self.auth.to_dict(),
            "session": self.session.to_dict(),
            "actions": self.actions.to_dict(),
            "sections": self.sections,
            "warnings": self.warnings,
            "hard_stops": self.hard_stops,
        }
        if self.core_gaps:
            result["core_gaps"] = [gap.to_dict() for gap in self.core_gaps]
        return result


def analyze_har(
    har_path: str | Path,
    fleet: FleetPatterns | None = None,
) -> AnalysisResult:
    """Run HAR analysis Phases 1-6.

    Loads the HAR file, then runs transport detection, auth strategy
    detection, session detection, action detection, format detection,
    and field mapping extraction in sequence.

    Args:
        har_path: Path to a validated ``.har`` file.
        fleet: Optional fleet patterns from the Catalog scanner.
            When provided, fleet-derived patterns augment Core's
            baseline detection for table direction and system_info
            label resolution.

    Returns:
        AnalysisResult with detected transport, auth, session, actions,
        sections (format + field mappings), and any warnings or hard stops.

    Raises:
        FileNotFoundError: If har_path does not exist.
        ValueError: If HAR file cannot be parsed or has no entries.
    """
    har_path = Path(har_path)
    entries = _load_har_entries(har_path)

    warnings: list[str] = []
    hard_stops: list[str] = []
    core_gaps: list[CoreGap] = []

    # Phase 1: Transport
    transport_result = TransportResult.detect(entries)

    # Phase 2: Auth
    auth_result = AuthDetail.detect(entries, transport_result.transport, warnings, hard_stops, core_gaps)

    # Phase 3: Session
    session_result = SessionDetail.detect(entries, transport_result.transport, auth_result.strategy, warnings)

    # Phase 4: Actions
    actions_result = ActionsDetail.detect(entries, transport_result.transport, warnings, core_gaps)

    # Phase 5-6: Format detection and field mapping
    sections = detect_sections(entries, transport_result.transport, warnings, hard_stops, fleet=fleet)

    # Post-analysis: JS endpoint discovery
    detect_uncaptured_endpoints(entries, warnings)

    # Post-analysis: Request requirements detection
    detect_request_requirements(entries, transport_result.transport, session_result, warnings)

    return AnalysisResult(
        transport=transport_result,
        auth=auth_result,
        session=session_result,
        actions=actions_result,
        sections=sections if sections else None,
        warnings=warnings,
        hard_stops=hard_stops,
        core_gaps=core_gaps,
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
        data = load_har_json(har_path)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in HAR file: {exc}") from exc

    entries: list[dict[str, Any]] = data.get("log", {}).get("entries", [])
    if not entries:
        raise ValueError("HAR file has no entries in log.entries")

    return entries
