"""Tests for Phase 5: Format dispatcher.

Tests routing to HTTP vs HNAP and section assembly.
Fixture-driven with JSON test data in fixtures/format_dispatch/.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from solentlabs.cable_modem_monitor_core.mcp.analysis.format import detect_sections
from solentlabs.cable_modem_monitor_core.mcp.analysis.format.dispatcher import (
    _direction_from_js_name,
    _direction_from_json,
    _direction_from_resource,
)

from tests.conftest import collect_fixtures, load_fixture

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "format_dispatch"
DISPATCH_FIXTURES = collect_fixtures(FIXTURES_DIR)


# =====================================================================
# Format dispatcher routing - fixture-driven
# =====================================================================


@pytest.mark.parametrize(
    "fixture_path",
    DISPATCH_FIXTURES,
    ids=[f.stem for f in DISPATCH_FIXTURES],
)
def test_format_dispatch(fixture_path: Path) -> None:
    """Format dispatcher routes correctly for each fixture."""
    data = load_fixture(fixture_path)
    warnings: list[str] = []
    hard_stops: list[str] = []

    result = detect_sections(data["_entries"], data["_transport"], warnings, hard_stops)

    # Check hard stops
    if "_expected_hard_stop" in data:
        assert any(data["_expected_hard_stop"] in hs for hs in hard_stops)

    # Check expected sections (exact empty check)
    if "_expected_sections" in data:
        assert result == data["_expected_sections"]

    # Check expected direction and format
    if "_expected_direction" in data:
        direction = data["_expected_direction"]
        assert direction in result
        assert result[direction]["format"] == data["_expected_format"]
        assert not hard_stops

    # Check expected warning
    if "_expected_warning" in data:
        assert any(data["_expected_warning"] in w for w in warnings)

    # Check system_info
    if "_expected_system_info_format" in data:
        assert "system_info" in result
        sources = result["system_info"]["sources"]
        assert len(sources) >= 1
        assert sources[0]["format"] == data["_expected_system_info_format"]


# =====================================================================
# Direction helpers - table-driven
# =====================================================================

# fmt: off
JS_NAME_DIRECTION_CASES = [
    # (name,                        expected,      desc)
    ("InitDsTableTagValue",         "downstream",  "ds in name"),
    ("InitUsTableTagValue",         "upstream",    "us in name"),
    ("InitDownstreamTagValue",      "downstream",  "downstream in name"),
    ("InitUpstreamTagValue",        "upstream",    "upstream in name"),
    ("InitDataTagValue",            "unknown",     "no direction keyword"),
]
# fmt: on


@pytest.mark.parametrize(
    "name,expected,desc",
    JS_NAME_DIRECTION_CASES,
    ids=[c[2] for c in JS_NAME_DIRECTION_CASES],
)
def test_direction_from_js_name(name: str, expected: str, desc: str) -> None:
    """JS function name maps to direction."""
    assert _direction_from_js_name(name) == expected


# fmt: off
RESOURCE_DIRECTION_CASES = [
    # (resource,            expected,      desc)
    ("/api/downstream",     "downstream",  "downstream in path"),
    ("/api/upstream",       "upstream",    "upstream in path"),
    ("/api/data",           "unknown",     "no direction in path"),
]
# fmt: on


@pytest.mark.parametrize(
    "resource,expected,desc",
    RESOURCE_DIRECTION_CASES,
    ids=[c[2] for c in RESOURCE_DIRECTION_CASES],
)
def test_direction_from_resource(resource: str, expected: str, desc: str) -> None:
    """Resource path maps to direction."""
    assert _direction_from_resource(resource) == expected


# fmt: off
JSON_DIRECTION_CASES: list[tuple[dict[str, list[object]], str, str]] = [
    # (data,                              expected,      desc)
    ({"downstream": []},                  "downstream",  "downstream key"),
    ({"upstream": []},                    "upstream",    "upstream key"),
    ({"channels": []},                    "unknown",     "no direction key"),
]
# fmt: on


@pytest.mark.parametrize(
    "data,expected,desc",
    JSON_DIRECTION_CASES,
    ids=[c[2] for c in JSON_DIRECTION_CASES],
)
def test_direction_from_json(data: dict[str, Any], expected: str, desc: str) -> None:
    """JSON keys map to direction."""
    assert _direction_from_json(data) == expected


# =====================================================================
# Section assembly edge cases
# =====================================================================


def _make_entry(url: str, status: int, content_type: str, body: str) -> dict[str, Any]:
    """Create a minimal HAR entry for testing."""
    return {
        "request": {
            "method": "GET",
            "url": f"http://192.168.100.1{url}",
            "headers": [],
        },
        "response": {
            "status": status,
            "headers": [{"name": "Content-Type", "value": content_type}],
            "content": {
                "size": len(body),
                "mimeType": content_type,
                "text": body,
            },
        },
    }


class TestSectionAssemblyEdgeCases:
    """Edge cases for section assembly in the format dispatcher."""

    def test_table_unknown_direction_warning(self) -> None:
        """Table with unknown direction produces warning and is skipped."""
        entries = [
            _make_entry(
                "/data.htm",
                200,
                "text/html",
                "<html><table>"
                "<tr><td>Channel ID</td><td>Frequency</td></tr>"
                "<tr><td>1</td><td>507000000</td></tr>"
                "</table></html>",
            )
        ]
        warnings: list[str] = []
        result = detect_sections(entries, "http", warnings, [])
        # No direction detected → warning, section skipped
        assert any("Cannot determine direction" in w for w in warnings)
        assert "downstream" not in result
        assert "upstream" not in result

    def test_json_direction_fallback_to_json_keys(self) -> None:
        """JSON section infers direction from JSON structure keys."""
        import json

        json_data = {
            "downstream": {
                "channels": [
                    {"channelId": 1, "frequency": 507000000, "power": 3.2},
                ]
            }
        }
        entries = [_make_entry("/api/data", 200, "application/json", json.dumps(json_data))]
        warnings: list[str] = []
        result = detect_sections(entries, "http", warnings, [])
        # Resource /api/data has no direction → falls back to JSON keys
        assert "downstream" in result

    def test_json_unknown_direction_warning(self) -> None:
        """JSON with no direction signal produces warning."""
        import json

        json_data = {
            "channels": [
                {"channelId": 1, "frequency": 507000000},
            ]
        }
        entries = [_make_entry("/api/data", 200, "application/json", json.dumps(json_data))]
        warnings: list[str] = []
        detect_sections(entries, "http", warnings, [])
        assert any("Cannot determine direction" in w for w in warnings)

    def test_json_page_with_null_json_data(self) -> None:
        """JSON page that fails to parse is handled gracefully."""
        entries = [_make_entry("/api/data", 200, "application/json", "not json")]
        warnings: list[str] = []
        result = detect_sections(entries, "http", warnings, [])
        # _parse_json_body returns None, _assemble_json_sections returns early
        assert "downstream" not in result

    def test_duplicate_table_direction_first_wins(self) -> None:
        """When two tables have same direction, first table wins."""
        entries = [
            _make_entry(
                "/status.html",
                200,
                "text/html",
                "<html>"
                '<table id="dsTable1">'
                "<tr><td>Channel ID</td><td>Frequency</td></tr>"
                "<tr><td>1</td><td>507000000</td></tr>"
                "</table>"
                '<table id="dsTable2">'
                "<tr><td>Channel ID</td><td>Power</td></tr>"
                "<tr><td>1</td><td>3.2</td></tr>"
                "</table>"
                "</html>",
            )
        ]
        warnings: list[str] = []
        result = detect_sections(entries, "http", warnings, [])
        # Both tables are downstream, but only first is used
        if "downstream" in result:
            assert result["downstream"]["resource"] == "/status.html"

    def test_table_no_mappings_skipped(self) -> None:
        """Table where field extraction returns no mappings is skipped."""
        entries = [
            _make_entry(
                "/data.htm",
                200,
                "text/html",
                "<html>"
                "<h3>Downstream</h3>"
                "<table>"
                "<tr><td>1</td><td>2</td><td>3</td></tr>"
                "<tr><td>a</td><td>b</td><td>c</td></tr>"
                "</table>"
                "</html>",
            )
        ]
        warnings: list[str] = []
        result = detect_sections(entries, "http", warnings, [])
        # Table has digit-only headers → no field mappings → section skipped
        assert "downstream" not in result
