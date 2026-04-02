"""Tests for Phase 6: System info detection.

Label matching, multi-source detection, and format-specific
system info extraction.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from solentlabs.cable_modem_monitor_core.mcp.analysis.format.types import (
    DetectedJsFunction,
    DetectedLabelPair,
    PageAnalysis,
)
from solentlabs.cable_modem_monitor_core.mcp.analysis.mapping.system_info import (
    _is_directional_js,
    _match_label,
    detect_system_info,
)

from tests.conftest import collect_fixtures, load_fixture

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "system_info"
VALID_DIR = FIXTURES_DIR / "valid"
VALID_FIXTURES = collect_fixtures(VALID_DIR)


# =====================================================================
# JS direction filter - table-driven
# =====================================================================

# fmt: off
JS_DIRECTION_CASES = [
    # (function_name,              expected, desc)
    ("InitDsTagValue",             True,     "ds keyword — directional"),
    ("InitUsTagValue",             True,     "us keyword — directional"),
    ("InitDsOfdmTagValue",         True,     "ds compound — directional"),
    ("InitUsOfdmaTagValue",        True,     "us compound — directional"),
    ("InitDownstreamData",         True,     "downstream keyword — directional"),
    ("InitUpstreamData",           True,     "upstream keyword — directional"),
    ("InitTagValue",               False,    "generic — non-directional"),
    ("InitDiagTagValue",           False,    "diagnostic — non-directional"),
    ("InitSystemInfoTagValue",     False,    "system info — non-directional"),
]
# fmt: on


@pytest.mark.parametrize(
    "name,expected,desc",
    JS_DIRECTION_CASES,
    ids=[c[2] for c in JS_DIRECTION_CASES],
)
def test_is_directional_js(name: str, expected: bool, desc: str) -> None:
    """JS function names are correctly classified as directional or not."""
    assert _is_directional_js(name) is expected


# =====================================================================
# Label-to-field mapping - table-driven
# =====================================================================

# fmt: off
LABEL_CASES = [
    # (label,                    selector_type, expected_field,      desc)
    ("System Up Time",           "label",       "system_uptime",     "canonical uptime"),
    ("Uptime",                   "label",       "system_uptime",     "uptime variant"),
    ("Software Version",         "label",       "software_version",  "software version"),
    ("Firmware Version",         "label",       "software_version",  "firmware variant"),
    ("Hardware Version",         "label",       "hardware_version",  "hardware version"),
    ("Cable Modem Status",       "label",       "network_access",    "cable modem status"),
    ("Network Access",           "label",       "network_access",    "network access"),
    ("Boot Status",              "label",       "boot_status",       "tier 2 boot status"),
    ("Serial Number",            "label",       "serial_number",     "tier 2 serial"),
    ("DOCSIS Version",           "label",       "docsis_version",    "tier 2 docsis"),
    ("systemuptime",             "id",          "system_uptime",     "id-based uptime"),
    ("firmwareversion",          "id",          "software_version",  "id-based firmware"),
    ("Unknown Label",            "label",       "",                  "unrecognized label"),
]
# fmt: on


@pytest.mark.parametrize(
    "label,selector_type,expected_field,desc",
    LABEL_CASES,
    ids=[c[3] for c in LABEL_CASES],
)
def test_label_to_field(label: str, selector_type: str, expected_field: str, desc: str) -> None:
    """Labels map to correct system info fields."""
    field, _tier = _match_label(label, selector_type)
    assert field == expected_field


# =====================================================================
# HTML label pair detection - fixture-driven
# =====================================================================


@pytest.mark.parametrize(
    "fixture_path",
    [f for f in VALID_FIXTURES if load_fixture(f).get("_expected_format") == "html_fields"],
    ids=[f.stem for f in VALID_FIXTURES if load_fixture(f).get("_expected_format") == "html_fields"],
)
def test_html_system_info_detection(fixture_path: Path) -> None:
    """HTML label pairs produce expected system info fields."""
    data = load_fixture(fixture_path)
    page_data = data["_page"]

    # Build PageAnalysis from fixture
    label_pairs = [DetectedLabelPair(**lp) for lp in page_data["label_pairs"]]
    page = PageAnalysis(
        resource=page_data["resource"],
        content_type=page_data["content_type"],
        label_pairs=label_pairs,
    )

    result = detect_system_info([page], [])
    assert result is not None

    detected_fields = set()
    for source in result.sources:
        for f in source.fields:
            detected_fields.add(f.field)

    for expected in data["_expected_fields"]:
        assert expected in detected_fields, f"Missing system_info field: {expected}"


# =====================================================================
# JSON system info detection - fixture-driven
# =====================================================================


@pytest.mark.parametrize(
    "fixture_path",
    [f for f in VALID_FIXTURES if load_fixture(f).get("_expected_format") == "json"],
    ids=[f.stem for f in VALID_FIXTURES if load_fixture(f).get("_expected_format") == "json"],
)
def test_json_system_info_detection(fixture_path: Path) -> None:
    """JSON data produces expected system info fields."""
    data = load_fixture(fixture_path)
    page_data = data["_page"]

    page = PageAnalysis(
        resource=page_data["resource"],
        content_type=page_data["content_type"],
        json_data=page_data.get("json_data"),
    )

    result = detect_system_info([page], [])
    assert result is not None

    detected_fields = set()
    for source in result.sources:
        for f in source.fields:
            detected_fields.add(f.field)

    for expected in data["_expected_fields"]:
        assert expected in detected_fields, f"Missing system_info field: {expected}"


# =====================================================================
# Multi-source detection
# =====================================================================


class TestMultiSourceDetection:
    """Tests for system_info from multiple pages."""

    def test_fields_from_multiple_pages(self) -> None:
        """Fields from different pages are combined into multi-source list."""
        page1 = PageAnalysis(
            resource="/info.html",
            content_type="text/html",
            label_pairs=[
                DetectedLabelPair(
                    label="System Up Time",
                    value="3 days",
                    selector_type="label",
                    selector_value="System Up Time",
                    element_id="",
                ),
            ],
        )
        page2 = PageAnalysis(
            resource="/version.html",
            content_type="text/html",
            label_pairs=[
                DetectedLabelPair(
                    label="Software Version",
                    value="1.0.4",
                    selector_type="label",
                    selector_value="Software Version",
                    element_id="",
                ),
            ],
        )

        result = detect_system_info([page1, page2], [])
        assert result is not None
        assert len(result.sources) == 2
        assert result.sources[0].resource == "/info.html"
        assert result.sources[1].resource == "/version.html"

    def test_no_system_info_returns_none(self) -> None:
        """Pages without system info produce None."""
        page = PageAnalysis(
            resource="/data.html",
            content_type="text/html",
            label_pairs=[
                DetectedLabelPair(
                    label="Random Data",
                    value="42",
                    selector_type="label",
                    selector_value="Random Data",
                    element_id="",
                ),
            ],
        )

        result = detect_system_info([page], [])
        assert result is None


# =====================================================================
# Serialization
# =====================================================================


class TestSystemInfoSerialization:
    """SystemInfoDetail.to_dict() produces expected output."""

    def test_html_fields_serialization(self) -> None:
        """HTML label-pair source serializes correctly."""
        data = load_fixture(VALID_DIR / "html_label_pairs.json")
        page_data = data["_page"]
        label_pairs = [DetectedLabelPair(**lp) for lp in page_data["label_pairs"]]
        page = PageAnalysis(
            resource=page_data["resource"],
            content_type=page_data["content_type"],
            label_pairs=label_pairs,
        )

        result = detect_system_info([page], [])
        assert result is not None

        d = result.to_dict()
        assert "sources" in d
        assert len(d["sources"]) >= 1
        src = d["sources"][0]
        assert src["format"] == "html_fields"
        assert src["resource"] == "/info.html"
        assert "fields" in src
        assert len(src["fields"]) >= 1
        assert "field" in src["fields"][0]
        assert "label" in src["fields"][0]


# =====================================================================
# JavaScript system info detection
# =====================================================================


class TestJsSystemInfoDetection:
    """Tests for JavaScript-embedded system info detection."""

    def test_js_function_with_system_info_labels(self) -> None:
        """JS function named InitSystemInfo with label values detected."""
        page = PageAnalysis(
            resource="/info.html",
            content_type="text/html",
            js_functions=[
                DetectedJsFunction(
                    name="InitSystemInfoTagValue",
                    body="var tagValueList = '...';",
                    delimiter="|",
                    values=["", "System Up Time", "3 days 5 hours", "Software Version", "1.0.4"],
                ),
            ],
        )
        result = detect_system_info([page], [])
        assert result is not None

        detected_fields = set()
        for source in result.sources:
            for f in source.fields:
                detected_fields.add(f.field)

        assert "system_uptime" in detected_fields
        assert "software_version" in detected_fields

    def test_directional_js_function_skipped(self) -> None:
        """Directional JS functions (ds/us) are skipped for system_info."""
        page = PageAnalysis(
            resource="/data.html",
            content_type="text/html",
            js_functions=[
                DetectedJsFunction(
                    name="InitDsTagValue",
                    body="",
                    delimiter="|",
                    values=["System Up Time", "3 days"],
                ),
            ],
        )
        result = detect_system_info([page], [])
        # Directional function skipped — no JS system_info sources
        assert result is None

    def test_non_directional_js_function_checked(self) -> None:
        """Non-directional JS functions are checked for system_info labels."""
        page = PageAnalysis(
            resource="/status.htm",
            content_type="text/html",
            js_functions=[
                DetectedJsFunction(
                    name="InitTagValue",
                    body="var tagValueList = '...';",
                    delimiter="|",
                    values=["", "System Up Time", "5 days 2 hours"],
                ),
            ],
        )
        result = detect_system_info([page], [])
        assert result is not None

        detected_fields = {f.field for src in result.sources for f in src.fields}
        assert "system_uptime" in detected_fields

    def test_non_directional_js_no_matching_values(self) -> None:
        """Non-directional JS function with no system_info labels yields nothing."""
        page = PageAnalysis(
            resource="/status.html",
            content_type="text/html",
            js_functions=[
                DetectedJsFunction(
                    name="InitDiagTagValue",
                    body="",
                    delimiter="|",
                    values=["0", "1", "0", "0", "0", "0", "0", "1", "", ""],
                ),
            ],
        )
        result = detect_system_info([page], [])
        # Numeric status codes don't match any label — no system_info detected
        assert result is None


# =====================================================================
# ID-based label matching edge cases
# =====================================================================


class TestIdBasedLabelMatching:
    """Edge cases for id-based system info matching."""

    def test_id_fallback_to_label_map(self) -> None:
        """ID-based selector falls back to label map with underscore→space."""
        # "boot_status" with id selector: _ID_FIELD_MAP has "bootstate" not
        # "boot_status", but fallback normalizes underscore→space.
        field, _tier = _match_label("boot_status", "id")
        assert field == "boot_status"

    def test_unknown_id_returns_empty(self) -> None:
        """Unrecognized id returns empty."""
        field, _tier = _match_label("unknownId", "id")
        assert field == ""
