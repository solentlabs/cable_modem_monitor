"""Tests for Phase 1: Transport detection.

Transport detection tests are fixture-driven. Serialization tests
are inline behavioral (dataclass constructor with scalar inputs).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from solentlabs.cable_modem_monitor_core.mcp.analysis.transport import (
    TransportResult,
    detect_transport,
)

from tests.conftest import collect_fixtures, load_fixture

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "transport"
VALID_DIR = FIXTURES_DIR / "valid"

VALID_FIXTURES = collect_fixtures(VALID_DIR)


# =====================================================================
# Transport detection - fixture-driven
# =====================================================================


@pytest.mark.parametrize("fixture_path", VALID_FIXTURES, ids=[f.stem for f in VALID_FIXTURES])
def test_detect_transport(fixture_path: Path) -> None:
    """Transport detection returns correct transport for each fixture."""
    data = load_fixture(fixture_path)
    result = detect_transport(data["_entries"])
    assert result.transport == data["_expected_transport"]
    assert result.confidence == "high"


# =====================================================================
# Serialization - inline behavioral
# =====================================================================


class TestTransportResultSerialization:
    """TransportResult.to_dict() produces expected output."""

    def test_to_dict_http(self) -> None:
        """HTTP transport serializes correctly."""
        result = TransportResult(transport="http", confidence="high")
        assert result.to_dict() == {"transport": "http", "confidence": "high"}

    def test_to_dict_hnap(self) -> None:
        """HNAP transport serializes correctly."""
        result = TransportResult(transport="hnap", confidence="high")
        assert result.to_dict() == {"transport": "hnap", "confidence": "high"}
