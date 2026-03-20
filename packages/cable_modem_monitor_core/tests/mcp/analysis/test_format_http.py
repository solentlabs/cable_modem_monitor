"""Tests for Phase 5: HTTP format detection.

Data page identification, format classification, table detection,
JavaScript detection, label pair detection, and orientation detection.

Fixture-driven where HTML content is involved. Table-driven for
pure-function tests (direction, selector, row classification).
Behavioral tests for edge cases with trivial inputs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from solentlabs.cable_modem_monitor_core.mcp.analysis.format.html_parsing import (
    detect_label_pairs,
    detect_tables,
)
from solentlabs.cable_modem_monitor_core.mcp.analysis.format.http import (
    _parse_json_body,
    analyze_page,
    classify_page_format,
    identify_data_pages,
)
from solentlabs.cable_modem_monitor_core.mcp.analysis.format.table_analysis import (
    detect_row_start,
    detect_table_direction,
    detect_table_selector,
    is_data_row,
    is_transposed,
)
from solentlabs.cable_modem_monitor_core.mcp.analysis.format.types import DetectedTable

from tests.conftest import collect_fixtures, load_fixture  # type: ignore[attr-defined]

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "format"
VALID_DIR = FIXTURES_DIR / "valid"
INVALID_DIR = FIXTURES_DIR / "invalid"
TABLE_DETECTION_DIR = FIXTURES_DIR / "table_detection"
EDGE_CASES_DIR = FIXTURES_DIR / "edge_cases"
JS_EDGE_CASES_DIR = FIXTURES_DIR / "js_edge_cases"

VALID_FIXTURES = collect_fixtures(VALID_DIR)
INVALID_FIXTURES = collect_fixtures(INVALID_DIR)
TABLE_DETECTION_FIXTURES = sorted(TABLE_DETECTION_DIR.glob("*.json"))
EDGE_CASE_FIXTURES = sorted(EDGE_CASES_DIR.glob("*.json"))
JS_EDGE_CASE_FIXTURES = sorted(JS_EDGE_CASES_DIR.glob("*.json"))


def _load(path: Path) -> dict[str, Any]:
    """Load a JSON fixture."""
    return dict(json.loads(path.read_text()))


# =====================================================================
# Data page identification (behavioral — trivial HTML)
# =====================================================================


class TestIdentifyDataPages:
    """Tests for data page filtering."""

    def test_filters_non_200(self) -> None:
        """Non-200 responses are excluded."""
        entries = [
            _make_entry("/status.html", 302, "text/html", "<html></html>"),
        ]
        assert identify_data_pages(entries) == []

    def test_filters_static_resources(self) -> None:
        """CSS, JS, images are excluded."""
        entries = [
            _make_entry("/style.css", 200, "text/css", "body{}"),
            _make_entry("/app.js", 200, "application/javascript", "var x=1;"),
            _make_entry("/logo.png", 200, "image/png", "data"),
        ]
        assert identify_data_pages(entries) == []

    def test_filters_empty_responses(self) -> None:
        """Empty responses are excluded."""
        entries = [
            _make_entry("/status.html", 200, "text/html", ""),
        ]
        entries[0]["response"]["content"]["size"] = 0
        assert identify_data_pages(entries) == []

    def test_includes_html_data_pages(self) -> None:
        """HTML pages with content are included."""
        entries = [
            _make_entry("/status.html", 200, "text/html", "<html>data</html>"),
        ]
        result = identify_data_pages(entries)
        assert len(result) == 1

    def test_includes_json_data_pages(self) -> None:
        """JSON responses are included."""
        entries = [
            _make_entry("/api/data", 200, "application/json", '{"data": 1}'),
        ]
        result = identify_data_pages(entries)
        assert len(result) == 1

    def test_deduplicates_by_path(self) -> None:
        """Same path is only included once."""
        entries = [
            _make_entry("/status.html", 200, "text/html", "<html>1</html>"),
            _make_entry("/status.html", 200, "text/html", "<html>2</html>"),
        ]
        result = identify_data_pages(entries)
        assert len(result) == 1


# =====================================================================
# Format classification — fixture-driven
# =====================================================================


@pytest.mark.parametrize("fixture_path", VALID_FIXTURES, ids=[f.stem for f in VALID_FIXTURES])
def test_format_classification(fixture_path: Path) -> None:
    """Correct format detected for each valid fixture."""
    data = load_fixture(fixture_path)
    page = analyze_page(data["_entry"])
    fmt = classify_page_format(page)
    assert fmt == data["_expected_format"]


@pytest.mark.parametrize("fixture_path", INVALID_FIXTURES, ids=[f.stem for f in INVALID_FIXTURES])
def test_invalid_format_classification(fixture_path: Path) -> None:
    """Invalid/unrecognizable pages return expected format."""
    data = load_fixture(fixture_path)
    page = analyze_page(data["_entry"])
    fmt = classify_page_format(page)
    assert fmt == data["_expected_format"]


# =====================================================================
# Table detection — fixture-driven
# =====================================================================


@pytest.mark.parametrize(
    "fixture_path",
    TABLE_DETECTION_FIXTURES,
    ids=[f.stem for f in TABLE_DETECTION_FIXTURES],
)
def test_table_detection(fixture_path: Path) -> None:
    """Table detection from HAR entry fixtures."""
    data = _load(fixture_path)
    page = analyze_page(data["_entry"])

    assert len(page.tables) == data["_expected_table_count"]

    if data.get("_expected_headers"):
        assert page.tables[0].headers == data["_expected_headers"]
    if data.get("_expected_table_id"):
        assert page.tables[0].table_id == data["_expected_table_id"]


# =====================================================================
# JavaScript detection — fixture-driven
# =====================================================================


class TestJsDetection:
    """Tests for JavaScript-embedded data detection."""

    def test_detects_js_functions(self) -> None:
        """Init*TagValue functions are detected."""
        data = load_fixture(VALID_DIR / "javascript_embedded.json")
        page = analyze_page(data["_entry"])
        assert len(page.js_functions) >= 1
        names = [f.name for f in page.js_functions]
        for expected in data["_expected_js_functions"]:
            assert expected in names

    def test_js_delimiter_detected(self) -> None:
        """Pipe delimiter is correctly detected."""
        data = load_fixture(VALID_DIR / "javascript_embedded.json")
        page = analyze_page(data["_entry"])
        assert page.js_functions[0].delimiter == "|"


@pytest.mark.parametrize(
    "fixture_path",
    JS_EDGE_CASE_FIXTURES,
    ids=[f.stem for f in JS_EDGE_CASE_FIXTURES],
)
def test_js_edge_cases(fixture_path: Path) -> None:
    """JS detection edge cases from fixtures."""
    data = _load(fixture_path)
    page = analyze_page(data["_entry"])
    assert len(page.js_functions) == data["_expected_js_count"]


# =====================================================================
# Label pair detection
# =====================================================================


class TestLabelPairDetection:
    """Tests for HTML label-value pair detection."""

    def test_detects_label_pairs(self) -> None:
        """Label-value pairs are detected from table cells."""
        data = load_fixture(VALID_DIR / "html_fields_sysinfo.json")
        page = analyze_page(data["_entry"])
        assert len(page.label_pairs) >= 1
        labels = [p.label for p in page.label_pairs]
        assert "System Up Time" in labels


# =====================================================================
# Table direction detection — table-driven
# =====================================================================

# fmt: off
DIRECTION_CASES = [
    # (preceding_text,    title_row_text,                  table_id,   headers[0],    expected)
    ("",                  "Downstream Bonded Channels",    "",         "Channel ID",  "downstream"),
    ("",                  "Upstream Bonded Channels",      "",         "Channel ID",  "upstream"),
    ("Downstream",        "",                              "",         "Channel ID",  "downstream"),
    ("Upstream",          "",                              "",         "Channel ID",  "upstream"),
    ("",                  "",                              "dsTable",  "Channel ID",  "downstream"),
    ("",                  "",                              "usTable",  "Channel ID",  "upstream"),
    ("",                  "",                              "",         "Downstream",  "downstream"),
    ("",                  "",                              "",         "Upstream",    "upstream"),
    ("",                  "",                              "dataTable","Channel ID",  "unknown"),
    ("",                  "",                              "",         "Channel ID",  "unknown"),
]
# fmt: on


@pytest.mark.parametrize(
    "preceding,title,table_id,first_header,expected",
    DIRECTION_CASES,
    ids=[c[4] + "_" + str(i) for i, c in enumerate(DIRECTION_CASES)],
)
def test_table_direction(preceding: str, title: str, table_id: str, first_header: str, expected: str) -> None:
    """Table direction detected from various signal sources."""
    table = DetectedTable(
        table_id=table_id,
        css_class="",
        headers=[first_header, "Frequency"],
        rows=[["1", "507000000"]],
        preceding_text=preceding,
        title_row_text=title,
        table_index=0,
    )
    assert detect_table_direction(table) == expected


# =====================================================================
# Table selector detection — table-driven
# =====================================================================

# fmt: off
SELECTOR_CASES = [
    # (table_id,   css_class,   title_row_text,         preceding_text,  table_idx,  expected_type)
    ("dsTable",    "",          "",                      "",              0,          "id"),
    ("",           "",          "Downstream Channels",   "",              0,          "header_text"),
    ("",           "",          "",                      "Downstream",    0,          "header_text"),
    ("",           "data-tbl",  "",                      "",              0,          "css"),
    ("",           "",          "",                      "",              2,          "nth"),
]
# fmt: on


@pytest.mark.parametrize(
    "table_id,css,title,preceding,idx,expected_type",
    SELECTOR_CASES,
    ids=[c[5] + "_" + str(i) for i, c in enumerate(SELECTOR_CASES)],
)
def test_table_selector(table_id: str, css: str, title: str, preceding: str, idx: int, expected_type: str) -> None:
    """Selector priority: id > header_text > css > nth."""
    table = DetectedTable(
        table_id=table_id,
        css_class=css,
        headers=["Channel ID"],
        rows=[["1"]],
        preceding_text=preceding,
        title_row_text=title,
        table_index=idx,
    )
    selector = detect_table_selector(table)
    assert selector["type"] == expected_type


# =====================================================================
# Row start detection
# =====================================================================


class TestRowStartDetection:
    """Tests for data row start index detection."""

    def test_simple_header_plus_data(self) -> None:
        """Single header row: data starts at row 1."""
        table = DetectedTable(
            table_id="",
            css_class="",
            headers=["Channel ID", "Frequency"],
            rows=[["1", "507000000"], ["2", "513000000"]],
            preceding_text="",
            title_row_text="",
            table_index=0,
        )
        assert detect_row_start(table) == 1

    def test_title_row_plus_header(self) -> None:
        """Title row + header: data starts at row 2."""
        table = DetectedTable(
            table_id="",
            css_class="",
            headers=["Channel ID", "Frequency"],
            rows=[["1", "507000000"]],
            preceding_text="",
            title_row_text="Downstream Bonded Channels",
            table_index=0,
        )
        assert detect_row_start(table) == 2


# =====================================================================
# Table orientation detection
# =====================================================================


class TestTableOrientation:
    """Tests for standard vs transposed table detection."""

    def test_standard_table(self) -> None:
        """Headers in first row with data below = standard."""
        table = DetectedTable(
            table_id="",
            css_class="",
            headers=["Channel ID", "Frequency", "Power"],
            rows=[["1", "507000000", "3.2"], ["2", "513000000", "3.1"]],
            preceding_text="",
            title_row_text="",
            table_index=0,
        )
        assert not is_transposed(table)

    def test_transposed_table(self) -> None:
        """Field labels in first column = transposed."""
        table = DetectedTable(
            table_id="",
            css_class="",
            headers=["Downstream", "Ch 1", "Ch 2"],
            rows=[
                ["Channel ID", "1", "2"],
                ["Frequency", "507000000", "513000000"],
                ["Power", "3.2", "3.1"],
                ["SNR", "38.5", "37.8"],
            ],
            preceding_text="",
            title_row_text="",
            table_index=0,
        )
        assert is_transposed(table)


# =====================================================================
# HTML table edge cases — fixture-driven
# =====================================================================


@pytest.mark.parametrize(
    "fixture_path",
    EDGE_CASE_FIXTURES,
    ids=[f.stem for f in EDGE_CASE_FIXTURES],
)
def test_html_edge_cases(fixture_path: Path) -> None:
    """HTML table detection edge cases from fixtures."""
    data = _load(fixture_path)
    html = data["_html"]

    if "_expected_label_ids" in data:
        # Label pair test
        pairs = detect_label_pairs(html)
        ids = [p.element_id for p in pairs if p.element_id]
        for expected_id in data["_expected_label_ids"]:
            assert expected_id in ids
        return

    tables = detect_tables(html)
    assert len(tables) == data["_expected_table_count"]

    if data.get("_expected_title_row_text"):
        assert tables[0].title_row_text == data["_expected_title_row_text"]
    if data.get("_expected_css_class"):
        assert tables[0].css_class == data["_expected_css_class"]
    if data.get("_expected_first_header"):
        assert tables[0].headers[0] == data["_expected_first_header"]
    if data.get("_expected_row_count"):
        assert len(tables[0].rows) == data["_expected_row_count"]
    if data.get("_expected_preceding_text"):
        assert tables[0].preceding_text == data["_expected_preceding_text"]


# =====================================================================
# is_data_row edge cases — table-driven
# =====================================================================

# fmt: off
DATA_ROW_CASES = [
    # (row,                                    expected, desc)
    ([],                                       False,    "empty row"),
    (["", "  ", ""],                           False,    "all whitespace"),
    (["-", "--", "---"],                       False,    "all dashes"),
    (["N/A", "n/a"],                           False,    "all N/A"),
    (["", "42", ""],                           True,     "mixed empty and numeric"),
    (["3.2 dBmV", "38 dB"],                   True,     "numeric with units"),
    (["Locked", "QAM256", "Active"],           True,     "string data non-label first cell"),
    (["Channel ID", "Frequency"],              False,    "field label in first cell"),
    (["Status", "Lock Status"],                False,    "status label in first cell"),
]
# fmt: on


@pytest.mark.parametrize(
    "row,expected,desc",
    DATA_ROW_CASES,
    ids=[c[2] for c in DATA_ROW_CASES],
)
def test_is_data_row(row: list[str], expected: bool, desc: str) -> None:
    """Data row classification handles edge cases."""
    assert is_data_row(row) == expected


# =====================================================================
# detect_row_start with non-data rows before data
# =====================================================================


class TestRowStartWithNonDataRows:
    """Row start detection when non-data rows precede data."""

    def test_non_data_rows_before_data(self) -> None:
        """Non-data rows (dashes) before data rows increase skip count."""
        table = DetectedTable(
            table_id="",
            css_class="",
            headers=["Channel ID", "Frequency"],
            rows=[
                ["-", "-"],
                ["1", "507000000"],
                ["2", "513000000"],
            ],
            preceding_text="",
            title_row_text="",
            table_index=0,
        )
        # skip=1 (header) + 1 (dash row) = 2
        assert detect_row_start(table) == 2


# =====================================================================
# JSON body parsing edge cases (behavioral — no HTML)
# =====================================================================


class TestJsonBodyParsing:
    """Edge cases for _parse_json_body."""

    def test_empty_body(self) -> None:
        """Empty string returns None."""
        assert _parse_json_body("") is None

    def test_non_dict_json(self) -> None:
        """JSON array (not dict) returns None."""
        assert _parse_json_body("[1, 2, 3]") is None

    def test_invalid_json(self) -> None:
        """Invalid JSON string returns None."""
        assert _parse_json_body("{not json}") is None

    def test_valid_dict(self) -> None:
        """Valid JSON dict is returned."""
        result = _parse_json_body('{"key": "value"}')
        assert result == {"key": "value"}


# =====================================================================
# Helpers
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
