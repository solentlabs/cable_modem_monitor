"""Tests for Phase 6: Field mapping extraction.

Column mapping, type/unit detection, channel_type detection,
filter detection, and three-tier field name resolution.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from solentlabs.cable_modem_monitor_core.mcp.analysis.format.types import (
    DetectedJsFunction,
    DetectedTable,
)
from solentlabs.cable_modem_monitor_core.mcp.analysis.mapping import extract_section_mappings
from solentlabs.cable_modem_monitor_core.mcp.analysis.mapping.channel_detection import (
    _build_channel_type_map,
    _build_modulation_map,
    detect_channel_type_fixed,
)
from solentlabs.cable_modem_monitor_core.mcp.analysis.mapping.dispatcher import (
    _find_channel_array,
    _infer_field_from_value,
)
from solentlabs.cable_modem_monitor_core.mcp.analysis.mapping.field_resolution import (
    detect_field_type,
    match_header_to_field,
    match_json_key_to_field,
    to_snake_case,
)
from solentlabs.cable_modem_monitor_core.mcp.analysis.mapping.types import (
    FieldMapping,
    SectionDetail,
    SystemInfoFieldDetail,
    SystemInfoSourceDetail,
)

from tests.conftest import collect_fixtures, load_fixture

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "field_mapping"
VALID_DIR = FIXTURES_DIR / "valid"
VALID_FIXTURES = collect_fixtures(VALID_DIR)


# =====================================================================
# Header-to-field mapping - table-driven
# =====================================================================

# fmt: off
HEADER_CASES = [
    # (header,                              expected_field,    tier, unit,  desc)
    ("Channel ID",                          "channel_id",      1,  "",    "canonical channel_id"),
    ("Frequency",                           "frequency",       1,  "",    "canonical frequency"),
    ("Power Level",                         "power",           1,  "",    "power level variant"),
    ("SNR/MER",                             "snr",             1,  "",    "SNR with MER"),
    ("Signal to Noise",                     "snr",             1,  "",    "signal to noise"),
    ("Total Correctable Codewords",         "corrected",       1,  "",    "correctable codewords"),
    ("Total Uncorrectable Codewords",       "uncorrected",     1,  "",    "uncorrectable codewords"),
    ("Lock Status",                         "lock_status",     1,  "",    "lock status"),
    ("Status",                              "lock_status",     1,  "",    "status shorthand"),
    ("Symbol Rate",                         "symbol_rate",     1,  "",    "symbol rate"),
    ("Symb. Rate",                          "symbol_rate",     1,  "",    "abbreviated symbol rate"),
    ("Channel Width",                       "channel_width",   2,  "",    "tier 2 channel width"),
    ("Custom Field Name",                   "custom_field_name", 3, "",   "tier 3 snake_case"),
    ("  Frequency  ",                       "frequency",       1,  "",    "whitespace stripped"),
    # Header variants with parenthesized units (Motorola MB7621/MB8611)
    ("Freq. (MHz)",                         "frequency",       1,  "MHz", "motorola freq with unit"),
    ("Pwr (dBmV)",                          "power",           1,  "dBmV","motorola power with unit"),
    ("SNR (dB)",                            "snr",             1,  "dB",  "motorola snr with unit"),
    ("Symb. Rate (Ksym/sec)",               "symbol_rate",     1,  "Ksym/sec", "motorola symbol rate with unit"),
    ("Tx Power(dBmV)",                      "power",           1,  "dBmV","cm3500b tx power with unit"),
    # Direction-prefixed headers (SB8200, CGA2121)
    ("US Channel Type",                     "channel_type",    1,  "",    "upstream-prefixed channel type"),
    ("DCID",                                "channel_id",      1,  "",    "cm3500b downstream channel id"),
    ("Correcteds",                          "corrected",       1,  "",    "cm3500b corrected variant"),
    ("Uncorrectables",                      "uncorrected",     1,  "",    "cm3500b uncorrectable variant"),
    ("Width",                               "channel_width",   2,  "",    "sb8200 width shorthand"),
]
# fmt: on


@pytest.mark.parametrize(
    "header,expected_field,expected_tier,expected_unit,desc",
    HEADER_CASES,
    ids=[c[-1] for c in HEADER_CASES],
)
def test_header_to_field(
    header: str,
    expected_field: str,
    expected_tier: int,
    expected_unit: str,
    desc: str,
) -> None:
    """Header text maps to correct canonical field, tier, and unit."""
    field, tier, unit = match_header_to_field(header)
    assert field == expected_field
    assert tier == expected_tier
    assert unit == expected_unit


# =====================================================================
# JSON key mapping - table-driven
# =====================================================================

# fmt: off
JSON_KEY_CASES = [
    # (key,                expected_field,      expected_tier, desc)
    ("channelId",          "channel_id",        1,            "camelCase channelId"),
    ("frequency",          "frequency",         1,            "lowercase frequency"),
    ("rxMer",              "snr",               1,            "rxMer -> snr"),
    ("correctedErrors",    "corrected",         1,            "correctedErrors"),
    ("channelType",        "channel_type",      1,            "channelType"),
    ("symbolRate",         "symbol_rate",        1,            "symbolRate"),
    ("customKey",          "custom_key",        3,            "tier 3 fallback"),
]
# fmt: on


@pytest.mark.parametrize(
    "key,expected_field,expected_tier,desc",
    JSON_KEY_CASES,
    ids=[c[3] for c in JSON_KEY_CASES],
)
def test_json_key_to_field(key: str, expected_field: str, expected_tier: int, desc: str) -> None:
    """JSON key maps to correct canonical field and tier."""
    field, tier = match_json_key_to_field(key)
    assert field == expected_field
    assert tier == expected_tier


# =====================================================================
# snake_case conversion - table-driven
# =====================================================================

# fmt: off
SNAKE_CASES = [
    # (input,               expected,             desc)
    ("Channel ID",          "channel_id",         "space to underscore"),
    ("SNR/MER",             "snr_mer",            "slash to underscore"),
    ("channelType",         "channel_type",       "camelCase"),
    ("PowerLevel",          "power_level",        "PascalCase"),
    ("simple",              "simple",             "already lowercase"),
    ("UPPER CASE",          "upper_case",         "all caps"),
]
# fmt: on


@pytest.mark.parametrize(
    "text,expected,desc",
    SNAKE_CASES,
    ids=[c[2] for c in SNAKE_CASES],
)
def test_to_snake_case(text: str, expected: str, desc: str) -> None:
    """Text is correctly converted to snake_case."""
    assert to_snake_case(text) == expected


# =====================================================================
# Table field extraction - fixture-driven
# =====================================================================


@pytest.mark.parametrize(
    "fixture_path",
    [f for f in VALID_FIXTURES if load_fixture(f).get("_format") == "table"],
    ids=[f.stem for f in VALID_FIXTURES if load_fixture(f).get("_format") == "table"],
)
def test_table_field_extraction(fixture_path: Path) -> None:
    """Table fixtures produce correct field mappings."""
    data = load_fixture(fixture_path)
    table_data = data["_table"]
    table = DetectedTable(**table_data)
    warnings: list[str] = []

    section = extract_section_mappings(
        fmt="table",
        table=table,
        resource="/status.html",
        direction=data.get("_direction", "downstream"),
        warnings=warnings,
    )

    assert section is not None
    assert section.format == "table"

    # Check expected fields if provided
    if "_expected_fields" in data:
        mapping_fields = {m.field: m for m in section.mappings}
        for field_name, expected in data["_expected_fields"].items():
            assert field_name in mapping_fields, f"Missing field: {field_name}"
            m = mapping_fields[field_name]
            assert m.type == expected["type"], f"{field_name} type"
            assert m.tier == expected["tier"], f"{field_name} tier"
            if "index" in expected:
                assert m.index == expected["index"], f"{field_name} index"


# =====================================================================
# Transposed field extraction - fixture-driven
# =====================================================================


@pytest.mark.parametrize(
    "fixture_path",
    [f for f in VALID_FIXTURES if load_fixture(f).get("_format") == "table_transposed"],
    ids=[f.stem for f in VALID_FIXTURES if load_fixture(f).get("_format") == "table_transposed"],
)
def test_transposed_field_extraction(fixture_path: Path) -> None:
    """Transposed table fixtures produce correct field mappings."""
    data = load_fixture(fixture_path)
    table_data = data["_table"]
    table = DetectedTable(**table_data)
    warnings: list[str] = []

    section = extract_section_mappings(
        fmt="table_transposed",
        table=table,
        resource="/status.html",
        direction=data.get("_direction", "downstream"),
        warnings=warnings,
    )

    assert section is not None
    assert section.format == "table_transposed"

    if "_expected_fields" in data:
        mapping_fields = {m.field for m in section.mappings}
        for field_name in data["_expected_fields"]:
            assert field_name in mapping_fields, f"Missing field: {field_name}"

    if "_expected_channel_count" in data:
        assert section.channel_count == data["_expected_channel_count"]


# =====================================================================
# JSON field extraction - fixture-driven
# =====================================================================


@pytest.mark.parametrize(
    "fixture_path",
    [f for f in VALID_FIXTURES if load_fixture(f).get("_format") == "json"],
    ids=[f.stem for f in VALID_FIXTURES if load_fixture(f).get("_format") == "json"],
)
def test_json_field_extraction(fixture_path: Path) -> None:
    """JSON fixtures produce correct field mappings."""
    data = load_fixture(fixture_path)
    warnings: list[str] = []

    section = extract_section_mappings(
        fmt="json",
        json_data=data["_json_data"],
        resource="/api/downstream",
        direction=data.get("_direction", "downstream"),
        warnings=warnings,
    )

    assert section is not None
    assert section.format == "json"

    if "_expected_fields" in data:
        mapping_fields = {m.field for m in section.mappings}
        for field_name in data["_expected_fields"]:
            assert field_name in mapping_fields, f"Missing field: {field_name}"

    if "_expected_channel_count" in data:
        assert section.channel_count == data["_expected_channel_count"]

    if "_expected_array_path" in data:
        assert section.array_path == data["_expected_array_path"]

    if "_expected_channel_type" in data:
        assert section.channel_type == data["_expected_channel_type"]


# =====================================================================
# Filter detection - table-driven
# =====================================================================

# fmt: off
FILTER_CASES = [
    # (fixture,              filter_key,    expected_value,  desc)
    ("table_with_filter.json", "lock_status", "Locked",      "unlocked rows trigger lock_status filter"),
    ("table_with_filter.json", "frequency",   {"not": 0},    "zero-frequency rows trigger not-0 filter"),
]
# fmt: on


@pytest.mark.parametrize(
    "fixture_name,filter_key,expected_value,desc",
    FILTER_CASES,
    ids=[c[3] for c in FILTER_CASES],
)
def test_filter_detection(fixture_name: str, filter_key: str, expected_value: object, desc: str) -> None:
    """Filter detection from table data."""
    data = load_fixture(VALID_DIR / fixture_name)
    table = DetectedTable(**data["_table"])

    section = extract_section_mappings(
        fmt="table",
        table=table,
        resource="/status.html",
        direction="downstream",
        warnings=[],
    )

    assert section is not None
    assert section.filter is not None
    assert section.filter.get(filter_key) == expected_value


# =====================================================================
# Channel type detection - table-driven
# =====================================================================

# fmt: off
CHANNEL_TYPE_CASES = [
    # (fixture,                           direction,     check,    desc)
    ("table_with_units.json",             "downstream",  "map",    "modulation column maps to channel types"),
    ("table_no_modulation_upstream.json",  "upstream",    "fixed",  "no modulation gets fixed atdma"),
]
# fmt: on


@pytest.mark.parametrize(
    "fixture_name,direction,check,desc",
    CHANNEL_TYPE_CASES,
    ids=[c[3] for c in CHANNEL_TYPE_CASES],
)
def test_channel_type_detection(fixture_name: str, direction: str, check: str, desc: str) -> None:
    """Channel type detection from table data."""
    data = load_fixture(VALID_DIR / fixture_name)
    table = DetectedTable(**data["_table"])

    section = extract_section_mappings(
        fmt="table",
        table=table,
        resource="/status.html",
        direction=direction,
        warnings=[],
    )

    assert section is not None
    assert section.channel_type is not None
    if check == "map":
        assert "map" in section.channel_type
    elif check == "fixed":
        assert section.channel_type == data["_expected_channel_type"]


# =====================================================================
# Serialization
# =====================================================================


class TestSectionDetailSerialization:
    """SectionDetail.to_dict() produces expected output."""

    def test_table_section_serialization(self) -> None:
        """Table section serializes to expected dict format."""
        data = load_fixture(VALID_DIR / "table_with_units.json")
        table = DetectedTable(**data["_table"])

        section = extract_section_mappings(
            fmt="table",
            table=table,
            resource="/status.html",
            direction="downstream",
            warnings=[],
        )

        assert section is not None
        d = section.to_dict()
        assert d["format"] == "table"
        assert d["resource"] == "/status.html"
        assert isinstance(d["mappings"], list)
        assert len(d["mappings"]) > 0
        assert "field" in d["mappings"][0]
        assert "type" in d["mappings"][0]


# =====================================================================
# JavaScript field extraction - fixture-driven
# =====================================================================


@pytest.mark.parametrize(
    "fixture_path",
    [f for f in VALID_FIXTURES if load_fixture(f).get("_format") == "javascript"],
    ids=[f.stem for f in VALID_FIXTURES if load_fixture(f).get("_format") == "javascript"],
)
def test_js_field_extraction(fixture_path: Path) -> None:
    """JavaScript fixtures produce correct field mappings."""
    data = load_fixture(fixture_path)
    js_func = DetectedJsFunction(**data["_js_function"])
    warnings: list[str] = []

    section = extract_section_mappings(
        fmt="javascript",
        js_function=js_func,
        resource="/data.htm",
        direction=data.get("_direction", "downstream"),
        warnings=warnings,
    )

    assert section is not None
    assert section.format == "javascript"

    if "_expected_fields" in data:
        mapping_fields = {m.field for m in section.mappings}
        for field_name in data["_expected_fields"]:
            assert field_name in mapping_fields, f"Missing field: {field_name}"

    if "_expected_channel_count" in data:
        assert section.channel_count == data["_expected_channel_count"]

    if "_expected_function_name" in data:
        assert section.function_name == data["_expected_function_name"]

    if "_expected_delimiter" in data:
        assert section.delimiter == data["_expected_delimiter"]

    if "_expected_fields_per_record" in data:
        assert section.fields_per_record == data["_expected_fields_per_record"]


# =====================================================================
# _infer_field_from_value - table-driven
# =====================================================================

# fmt: off
INFER_FIELD_CASES = [
    # (value,          offset, direction,      expected_field,    expected_tier, desc)
    ("Locked",         0,      "downstream",   "lock_status",     1,            "locked status"),
    ("Not Locked",     0,      "downstream",   "lock_status",     1,            "not locked status"),
    ("Unlocked",       0,      "downstream",   "lock_status",     1,            "unlocked status"),
    ("QAM256",         1,      "downstream",   "modulation",      1,            "QAM modulation"),
    ("OFDM",           1,      "downstream",   "modulation",      1,            "OFDM modulation"),
    ("OFDMA",          1,      "upstream",     "modulation",      1,            "OFDMA starts with OFDM"),
    ("SC-QAM",         0,      "downstream",   "channel_type",    1,            "SC-QAM channel type"),
    ("ATDMA",          0,      "upstream",     "channel_type",    1,            "ATDMA channel type"),
    ("507000000",      3,      "downstream",   "frequency",       1,            "large int is frequency"),
    ("5",              2,      "downstream",   "",                0,            "small int skipped"),
    ("",               0,      "downstream",   "",                0,            "empty string"),
    ("  ",             0,      "downstream",   "",                0,            "whitespace only"),
    ("hello",          0,      "downstream",   "",                0,            "non-numeric string"),
]
# fmt: on


@pytest.mark.parametrize(
    "value,offset,direction,expected_field,expected_tier,desc",
    INFER_FIELD_CASES,
    ids=[c[5] for c in INFER_FIELD_CASES],
)
def test_infer_field_from_value(
    value: str, offset: int, direction: str, expected_field: str, expected_tier: int, desc: str
) -> None:
    """JS value heuristic maps to correct field."""
    field, tier = _infer_field_from_value(value, offset, direction)
    assert field == expected_field
    assert tier == expected_tier


# =====================================================================
# detect_field_type - table-driven (unknown fields + frequency units)
# =====================================================================

# fmt: off
FIELD_TYPE_CASES = [
    # (field_name,       sample_values,       expected_type, expected_unit, desc)
    ("unknown_field",    ["507 Hz"],           "frequency",   "Hz",         "Hz unit pattern"),
    ("unknown_field",    ["600.0 MHz"],        "frequency",   "MHz",        "MHz unit pattern"),
    ("unknown_field",    ["3.2 dBmV"],         "float",       "dBmV",       "dBmV unit pattern"),
    ("unknown_field",    ["38 dB"],            "float",       "dB",         "dB unit pattern"),
    ("unknown_field",    ["10000000"],         "integer",     "",           "large int no suffix"),
    ("unknown_field",    ["42"],               "integer",     "",           "bare integer"),
    ("unknown_field",    ["3.14 units"],       "float",       "",           "bare float with text"),
    ("unknown_field",    ["hello"],            "string",      "",           "plain string"),
    ("unknown_field",    ["", "  "],           "string",      "",           "all empty values"),
    ("frequency",        ["507 Hz"],           "frequency",   "Hz",         "frequency with Hz"),
    ("frequency",        ["600.0 MHz"],        "frequency",   "MHz",        "frequency with MHz"),
    ("frequency",        ["507000000"],        "frequency",   "",           "frequency bare int"),
]
# fmt: on


@pytest.mark.parametrize(
    "field_name,sample_values,expected_type,expected_unit,desc",
    FIELD_TYPE_CASES,
    ids=[c[4] for c in FIELD_TYPE_CASES],
)
def test_detect_field_type(
    field_name: str, sample_values: list[str], expected_type: str, expected_unit: str, desc: str
) -> None:
    """Field type and unit correctly inferred from name and values."""
    ftype, unit = detect_field_type(field_name, sample_values)
    assert ftype == expected_type
    assert unit == expected_unit


# =====================================================================
# Header/key matching edge cases - table-driven
# =====================================================================

# fmt: off
HEADER_EDGE_CASES = [
    # (header,  expected_field,  expected_tier, desc)
    ("",        "",              0,             "empty header"),
    ("  ",      "",              0,             "whitespace-only header"),
    ("123",     "",              0,             "digit-only header"),
]
# fmt: on


@pytest.mark.parametrize(
    "header,expected_field,expected_tier,desc",
    HEADER_EDGE_CASES,
    ids=[c[3] for c in HEADER_EDGE_CASES],
)
def test_header_edge_cases(header: str, expected_field: str, expected_tier: int, desc: str) -> None:
    """Empty and digit-only headers return no match."""
    field, tier, _unit = match_header_to_field(header)
    assert field == expected_field
    assert tier == expected_tier


# fmt: off
JSON_KEY_EDGE_CASES = [
    # (key,   expected_field,  expected_tier, desc)
    ("",      "",              0,             "empty JSON key"),
    ("  ",    "",              0,             "whitespace-only JSON key"),
]
# fmt: on


@pytest.mark.parametrize(
    "key,expected_field,expected_tier,desc",
    JSON_KEY_EDGE_CASES,
    ids=[c[3] for c in JSON_KEY_EDGE_CASES],
)
def test_json_key_edge_cases(key: str, expected_field: str, expected_tier: int, desc: str) -> None:
    """Empty JSON keys return no match."""
    field, tier = match_json_key_to_field(key)
    assert field == expected_field
    assert tier == expected_tier


# =====================================================================
# extract_section_mappings edge cases
# =====================================================================


class TestExtractEdgeCases:
    """Edge cases for extract_section_mappings dispatch."""

    def test_unmatched_format_returns_none(self) -> None:
        """Unknown format returns None."""
        result = extract_section_mappings(fmt="unknown", resource="/data.htm")
        assert result is None

    def test_table_with_no_recognizable_headers(self) -> None:
        """Table with digit-only headers returns None (no mappings)."""
        table = DetectedTable(
            table_id="",
            css_class="",
            headers=["1", "2", "3"],
            rows=[["a", "b", "c"]],
            preceding_text="",
            title_row_text="",
            table_index=0,
        )
        result = extract_section_mappings(fmt="table", table=table, resource="/data.htm")
        assert result is None

    def test_transposed_with_empty_row(self) -> None:
        """Transposed extraction skips empty rows without error."""
        table = DetectedTable(
            table_id="",
            css_class="",
            headers=["", "Ch 1"],
            rows=[
                [],
                ["Frequency", "507000000"],
                ["Power", "3.2"],
            ],
            preceding_text="",
            title_row_text="",
            table_index=0,
        )
        result = extract_section_mappings(
            fmt="table_transposed", table=table, resource="/data.htm", direction="downstream"
        )
        assert result is not None
        fields = {m.field for m in result.mappings}
        assert "frequency" in fields

    def test_transposed_no_recognizable_labels(self) -> None:
        """Transposed table with no recognized labels returns None."""
        table = DetectedTable(
            table_id="",
            css_class="",
            headers=["", "Ch 1"],
            rows=[["123", "abc"], ["456", "def"]],
            preceding_text="",
            title_row_text="",
            table_index=0,
        )
        result = extract_section_mappings(
            fmt="table_transposed", table=table, resource="/data.htm", direction="downstream"
        )
        assert result is None

    def test_js_empty_values_returns_none(self) -> None:
        """JS function with empty values returns None."""
        js_func = DetectedJsFunction(name="InitDsTagValue", body="", delimiter="|", values=[])
        result = extract_section_mappings(fmt="javascript", js_function=js_func, resource="/data.htm")
        assert result is None

    def test_js_zero_record_count_returns_none(self) -> None:
        """JS function where first value is not a positive int returns None."""
        js_func = DetectedJsFunction(name="InitDsTagValue", body="", delimiter="|", values=["0", "a", "b"])
        result = extract_section_mappings(fmt="javascript", js_function=js_func, resource="/data.htm")
        assert result is None

    def test_js_non_numeric_count_returns_none(self) -> None:
        """JS function where first value is non-numeric returns None."""
        js_func = DetectedJsFunction(name="InitDsTagValue", body="", delimiter="|", values=["abc", "1", "2"])
        result = extract_section_mappings(fmt="javascript", js_function=js_func, resource="/data.htm")
        assert result is None

    def test_js_count_only_no_data_returns_none(self) -> None:
        """JS function with count but no data values returns None."""
        js_func = DetectedJsFunction(name="InitDsTagValue", body="", delimiter="|", values=["1"])
        result = extract_section_mappings(fmt="javascript", js_function=js_func, resource="/data.htm")
        assert result is None

    def test_js_too_many_records_returns_none(self) -> None:
        """JS function where record count exceeds data returns None."""
        js_func = DetectedJsFunction(name="InitDsTagValue", body="", delimiter="|", values=["5", "a"])
        result = extract_section_mappings(fmt="javascript", js_function=js_func, resource="/data.htm")
        assert result is None

    def test_js_no_field_matches_returns_none(self) -> None:
        """JS function where no values map to fields returns None."""
        js_func = DetectedJsFunction(name="InitDsTagValue", body="", delimiter="|", values=["1", "hello"])
        result = extract_section_mappings(
            fmt="javascript", js_function=js_func, resource="/data.htm", direction="downstream"
        )
        assert result is None

    def test_json_non_dict_array_items_returns_none(self) -> None:
        """JSON array with non-dict items returns None."""
        result = extract_section_mappings(
            fmt="json",
            json_data={"channels": ["str1", "str2"]},
            resource="/api/data",
        )
        assert result is None

    def test_json_all_empty_keys_returns_none(self) -> None:
        """JSON items with only empty keys returns None (no mappings)."""
        result = extract_section_mappings(
            fmt="json",
            json_data={"channels": [{"": 1, "  ": 2}]},
            resource="/api/data",
        )
        assert result is None

    def test_json_no_channel_array_returns_none(self) -> None:
        """JSON with no list-of-dicts returns None."""
        result = extract_section_mappings(
            fmt="json",
            json_data={"status": "ok", "count": 5},
            resource="/api/data",
        )
        assert result is None

    def test_json_empty_data_returns_none(self) -> None:
        """Empty JSON dict returns None."""
        result = extract_section_mappings(fmt="json", json_data={}, resource="/api/data")
        assert result is None


# =====================================================================
# _find_channel_array edge cases
# =====================================================================


class TestFindChannelArray:
    """Edge cases for JSON channel array discovery."""

    def test_nested_array(self) -> None:
        """Finds array nested under a key."""
        path, arr = _find_channel_array({"data": {"channels": [{"id": 1}]}})
        assert path == "data.channels"
        assert len(arr) == 1

    def test_no_array(self) -> None:
        """Returns empty when no list-of-dicts found."""
        path, arr = _find_channel_array({"status": "ok"})
        assert path == ""
        assert arr == []

    def test_list_of_non_dicts(self) -> None:
        """List of strings is not a channel array."""
        path, arr = _find_channel_array({"items": ["a", "b"]})
        assert path == ""
        assert arr == []


# =====================================================================
# Channel detection edge cases
# =====================================================================

# fmt: off
CHANNEL_TYPE_FIXED_CASES = [
    # (direction,     expected,              desc)
    ("downstream",    {"fixed": "qam"},      "downstream fixed qam"),
    ("upstream",      {"fixed": "atdma"},    "upstream fixed atdma"),
    ("unknown",       None,                  "unknown returns None"),
]
# fmt: on


@pytest.mark.parametrize(
    "direction,expected,desc",
    CHANNEL_TYPE_FIXED_CASES,
    ids=[c[2] for c in CHANNEL_TYPE_FIXED_CASES],
)
def test_channel_type_fixed(direction: str, expected: object, desc: str) -> None:
    """Fixed channel type maps from direction."""
    assert detect_channel_type_fixed(direction) == expected


# fmt: off
MODULATION_MAP_CASES = [
    # (values,                     expected_map,                                desc)
    ({"ATDMA"},                    {"ATDMA": "atdma"},                          "ATDMA in modulation map"),
    ({"OFDMA"},                    {"OFDMA": "ofdma"},                          "OFDMA maps to ofdma"),
    ({"QAM256", "OFDM"},           {"OFDM": "ofdm", "QAM256": "qam"},          "mixed QAM and OFDM"),
    ({"Other"},                    {"Other": "ofdm"},                           "Other maps to ofdm"),
]
# fmt: on


@pytest.mark.parametrize(
    "values,expected_map,desc",
    MODULATION_MAP_CASES,
    ids=[c[2] for c in MODULATION_MAP_CASES],
)
def test_build_modulation_map(values: set[str], expected_map: dict[str, str], desc: str) -> None:
    """Modulation values map to channel types."""
    assert _build_modulation_map(values) == expected_map


# fmt: off
CHANNEL_TYPE_MAP_CASES = [
    # (values,           expected_map,                  desc)
    ({"OFDMA"},          {"OFDMA": "ofdma"},            "OFDMA in channel type map"),
    ({"ATDMA"},          {"ATDMA": "atdma"},            "ATDMA in channel type map"),
    ({"SC-QAM"},         {"SC-QAM": "qam"},             "SC-QAM maps to qam"),
    ({"OFDM"},           {"OFDM": "ofdm"},              "OFDM in channel type map"),
]
# fmt: on


@pytest.mark.parametrize(
    "values,expected_map,desc",
    CHANNEL_TYPE_MAP_CASES,
    ids=[c[2] for c in CHANNEL_TYPE_MAP_CASES],
)
def test_build_channel_type_map(values: set[str], expected_map: dict[str, str], desc: str) -> None:
    """Channel type values map to canonical types."""
    assert _build_channel_type_map(values) == expected_map


# =====================================================================
# Mapping types serialization
# =====================================================================


class TestMappingTypeSerialization:
    """Serialization branches for FieldMapping and SectionDetail."""

    def test_field_mapping_with_offset(self) -> None:
        """FieldMapping.to_dict() includes offset when set."""
        m = FieldMapping(field="lock_status", type="string", offset=0)
        d = m.to_dict()
        assert d["offset"] == 0
        assert "index" not in d

    def test_field_mapping_with_label(self) -> None:
        """FieldMapping.to_dict() includes label when set."""
        m = FieldMapping(field="power", type="float", label="Power Level")
        d = m.to_dict()
        assert d["label"] == "Power Level"
        assert "index" not in d

    def test_field_mapping_with_unit(self) -> None:
        """FieldMapping.to_dict() includes unit when set."""
        m = FieldMapping(field="frequency", type="frequency", unit="Hz", index=1)
        d = m.to_dict()
        assert d["unit"] == "Hz"
        assert d["index"] == 1

    def test_section_detail_with_row_start_and_filter(self) -> None:
        """SectionDetail.to_dict() includes row_start and filter."""
        section = SectionDetail(
            format="table",
            resource="/status.html",
            mappings=[FieldMapping(field="frequency", type="frequency", index=1)],
            row_start=2,
            filter={"lock_status": "Locked"},
        )
        d = section.to_dict()
        assert d["row_start"] == 2
        assert d["filter"] == {"lock_status": "Locked"}

    def test_section_detail_js_fields(self) -> None:
        """SectionDetail.to_dict() includes JS-specific fields."""
        section = SectionDetail(
            format="javascript",
            resource="/data.htm",
            mappings=[FieldMapping(field="frequency", type="frequency", offset=3)],
            function_name="InitDsTagValue",
            delimiter="|",
            fields_per_record=8,
            channel_count=2,
        )
        d = section.to_dict()
        assert d["function_name"] == "InitDsTagValue"
        assert d["delimiter"] == "|"
        assert d["fields_per_record"] == 8
        assert d["channel_count"] == 2

    def test_section_detail_json_fields(self) -> None:
        """SectionDetail.to_dict() includes array_path for JSON."""
        section = SectionDetail(
            format="json",
            resource="/api/data",
            mappings=[FieldMapping(field="channel_id", type="integer", key="channelId")],
            array_path="downstream.channels",
        )
        d = section.to_dict()
        assert d["array_path"] == "downstream.channels"

    def test_system_info_field_id_selector(self) -> None:
        """SystemInfoFieldDetail.to_dict() uses 'id' key for id selector."""
        f = SystemInfoFieldDetail(
            field="system_uptime",
            type="string",
            selector_type="id",
            selector_value="systemuptime",
        )
        d = f.to_dict()
        assert d["id"] == "systemuptime"
        assert "label" not in d

    def test_system_info_field_source_key(self) -> None:
        """SystemInfoFieldDetail.to_dict() uses 'source' key for JSON."""
        f = SystemInfoFieldDetail(
            field="software_version",
            type="string",
            source="firmwareVersion",
        )
        d = f.to_dict()
        assert d["source"] == "firmwareVersion"

    def test_system_info_field_pattern(self) -> None:
        """SystemInfoFieldDetail.to_dict() includes pattern when set."""
        f = SystemInfoFieldDetail(
            field="system_uptime",
            type="string",
            selector_type="label",
            selector_value="Uptime",
            pattern=r"\d+ days",
        )
        d = f.to_dict()
        assert d["pattern"] == r"\d+ days"

    def test_system_info_source_response_key(self) -> None:
        """SystemInfoSourceDetail.to_dict() includes response_key."""
        src = SystemInfoSourceDetail(
            format="json",
            resource="/api/info",
            fields=[SystemInfoFieldDetail(field="system_uptime", source="uptime")],
            response_key="systemInfo",
        )
        d = src.to_dict()
        assert d["response_key"] == "systemInfo"
