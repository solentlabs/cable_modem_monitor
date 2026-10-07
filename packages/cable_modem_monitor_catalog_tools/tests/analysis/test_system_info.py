"""Tests for Phase 6: System info detection.

Label matching, multi-source detection, and format-specific
system info extraction.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.analysis.format.types import (
    DetectedJsFunction,
    DetectedLabelPair,
    PageAnalysis,
)
from solentlabs.cable_modem_monitor_catalog_tools.analysis.mapping.system_info import (
    _is_directional_js,
    _match_label,
    detect_system_info,
)
from solentlabs.cable_modem_monitor_catalog_tools.analysis.types import FleetPatterns
from tests._helpers import collect_fixtures, load_fixture

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
    ("Model",                    "label",       "model_name",        "model is the model name"),
    ("Cable Modem Status",       "label",       "docsis_status",     "cable modem status"),
    ("Network Access",           "label",       "docsis_status",     "network access"),
    ("Boot Status",              "label",       "boot_status",       "tier 2 boot status"),
    ("Serial Number",            "label",       "",                  "serial not mapped (PII)"),
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


def test_model_label_is_tier_2() -> None:
    """A Model label maps to the Tier 2 registered model_name."""
    assert _match_label("Model", "label") == ("model_name", 2)


# A page that lists Model before Hardware Version keeps each value in its
# own field; first-wins dedup used to give hardware_version the model (#221).
_MODEL = ("Model", "M-100")
_HW = ("Hardware Version", "1.0")
_BOTH = {"model_name": "Model", "hardware_version": "Hardware Version"}

# fmt: off
MODEL_BEFORE_HARDWARE_CASES = [
    # (pairs (label, value), expected {field: selector_value}, desc)
    ([_MODEL, _HW],          _BOTH,                            "model first"),
    ([_HW, _MODEL],          _BOTH,                            "hardware first"),
    ([_MODEL],               {"model_name": "Model"},          "model only"),
]
# fmt: on


@pytest.mark.parametrize(
    "pairs,expected,desc",
    MODEL_BEFORE_HARDWARE_CASES,
    ids=[c[2] for c in MODEL_BEFORE_HARDWARE_CASES],
)
def test_model_and_hardware_version_labels_stay_separate(
    pairs: list[tuple[str, str]], expected: dict[str, str], desc: str
) -> None:
    """Each label claims its own field regardless of page order."""
    page = PageAnalysis(
        resource="/info.html",
        content_type="text/html",
        label_pairs=[
            DetectedLabelPair(label=label, value=value, selector_type="label", selector_value=label, element_id="")
            for label, value in pairs
        ],
    )
    result = detect_system_info([page], [])
    assert result is not None, desc
    assert {f.field: f.selector_value for f in result.sources[0].fields} == expected, desc


_JSON_BOTH = {"model_name": "model", "hardware_version": "hardwareVersion"}

# fmt: off
JSON_MODEL_CASES = [
    # (json_data,                                   expected {field: key},     desc)
    ({"model": "M-100"},                            {"model_name": "model"},   "model key"),
    ({"model": "M-100", "hardwareVersion": "1.0"},  _JSON_BOTH,                "both keys"),
]
# fmt: on


@pytest.mark.parametrize("json_data,expected,desc", JSON_MODEL_CASES, ids=[c[2] for c in JSON_MODEL_CASES])
def test_json_model_key_maps_to_model_name(json_data: dict[str, object], expected: dict[str, str], desc: str) -> None:
    """A JSON model key maps to model_name, leaving hardware_version to its own key."""
    page = PageAnalysis(resource="/api/info", content_type="application/json", json_data=json_data)
    result = detect_system_info([page], [])
    assert result is not None, desc
    assert {f.field: f.source for f in result.sources[0].fields} == expected, desc


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
# JSON nested key emission - table-driven
# =====================================================================

# Core navigates path, then looks the key up literally inside it. A
# nested field emitted as one dotted key matches nothing and fails
# silently, which is how a whole endpoint's fields go missing.
# fmt: off
NESTED_KEY_CASES = [
    # (json_data,                                          key,          path,           desc)
    ({"softwareVersion": "1.0"},                           "softwareVersion", "",         "top level — no path"),
    ({"info": {"softwareVersion": "1.0"}},                 "softwareVersion", "info",     "one container deep"),
    ({"a": {"b": {"softwareVersion": "1.0"}}},             "softwareVersion", "a.b",      "two containers deep"),
]
# fmt: on


@pytest.mark.parametrize("json_data,key,path,desc", NESTED_KEY_CASES, ids=[c[3] for c in NESTED_KEY_CASES])
def test_nested_json_key_splits_into_key_and_path(
    json_data: dict[str, object],
    key: str,
    path: str,
    desc: str,
) -> None:
    """A nested JSON field emits key and path separately, never one dotted string."""
    page = PageAnalysis(resource="/api/info", content_type="application/json", json_data=json_data)

    result = detect_system_info([page], [])
    assert result is not None, desc

    field = result.sources[0].fields[0]
    assert field.source == key, desc
    assert field.path == path, desc

    emitted = field.to_dict()
    assert emitted.get("source") == key, desc
    assert emitted.get("path", "") == path, desc


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

    def test_js_model_label_maps_to_model_name(self) -> None:
        """A Model value in a JS function maps to model_name, not hardware_version."""
        page = PageAnalysis(
            resource="/info.html",
            content_type="text/html",
            js_functions=[
                DetectedJsFunction(
                    name="InitTagValue",
                    body="",
                    delimiter="|",
                    values=["Model", "M-100", "Hardware Version", "1.0"],
                ),
            ],
        )
        result = detect_system_info([page], [])
        assert result is not None
        assert {f.field: f.source for src in result.sources for f in src.fields} == {
            "model_name": "Model",
            "hardware_version": "Hardware Version",
        }

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


# =====================================================================
# Fleet-augmented system info detection
# =====================================================================


class TestFleetAugmentedDetection:
    """Verify fleet patterns augment system_info detection."""

    def test_fleet_label_adds_new_field(self) -> None:
        """Fleet label mapping detects a field Core's baseline misses."""
        # "board temperature" is not in Core's _LABEL_FIELD_MAP
        page = PageAnalysis(
            resource="/status.html",
            content_type="text/html",
            tables=[],
            js_functions=[],
            label_pairs=[
                DetectedLabelPair(
                    label="Board Temperature",
                    value="42C",
                    selector_type="label",
                    selector_value="Board Temperature",
                    element_id="",
                ),
            ],
            json_data=None,
        )
        # Without fleet — not detected
        result_base = detect_system_info([page], [])
        base_fields = set()
        if result_base:
            for src in result_base.sources:
                for f in src.fields:
                    base_fields.add(f.field)

        # With fleet — detected
        fleet = FleetPatterns(
            system_info_labels={"board temperature": ("board_temperature", 1)},
        )
        result_fleet = detect_system_info([page], [], fleet=fleet)
        assert result_fleet is not None
        fleet_fields = set()
        for src in result_fleet.sources:
            for f in src.fields:
                fleet_fields.add(f.field)
        assert "board_temperature" in fleet_fields
        assert "board_temperature" not in base_fields

    def test_fleet_does_not_override_baseline(self) -> None:
        """Fleet labels don't override Core's baseline mappings."""
        page = PageAnalysis(
            resource="/status.html",
            content_type="text/html",
            tables=[],
            js_functions=[],
            label_pairs=[
                DetectedLabelPair(
                    label="System Up Time",
                    value="5 days",
                    selector_type="label",
                    selector_value="System Up Time",
                    element_id="",
                ),
            ],
            json_data=None,
        )
        # Fleet tries to remap "system up time" to a different field
        fleet = FleetPatterns(
            system_info_labels={"system up time": ("wrong_field", 1)},
        )
        result = detect_system_info([page], [], fleet=fleet)
        assert result is not None
        fields = {f.field for src in result.sources for f in src.fields}
        # Baseline wins — "system_uptime", not "wrong_field"
        assert "system_uptime" in fields
        assert "wrong_field" not in fields

    def test_fleet_none_behaves_like_baseline(self) -> None:
        """fleet=None produces same result as no fleet."""
        page = PageAnalysis(
            resource="/status.html",
            content_type="text/html",
            tables=[],
            js_functions=[],
            label_pairs=[
                DetectedLabelPair(
                    label="Uptime",
                    value="3 days",
                    selector_type="label",
                    selector_value="Uptime",
                    element_id="",
                ),
            ],
            json_data=None,
        )
        result = detect_system_info([page], [], fleet=None)
        assert result is not None
        fields = {f.field for src in result.sources for f in src.fields}
        assert "system_uptime" in fields


# =====================================================================
# Fleet-learned JSON keys: the captured value must fit a declared type
# =====================================================================

_DECLARES = {"vendor/a", "vendor/b"}

# ┌───────────┬──────────────────┬──────────┬─────────┬─────────────────────────────────┐
# │ key       │ declared type(s) │ captured │ mapped  │ description                     │
# ├───────────┼──────────────────┼──────────┼─────────┼─────────────────────────────────┤
# │ cmStatus  │ string           │ "OPER"   │ yes     │ text fits string                │
# │ cmStatus  │ string           │ 7        │ no      │ a number does not fit string    │
# │ cmCount   │ integer          │ "12"     │ yes     │ numeric text fits integer       │
# │ cmCount   │ integer          │ "twelve" │ no      │ other text does not             │
# │ cmUp      │ uptime           │ 360      │ yes     │ any value fits other types      │
# │ cmStatus  │ string, integer  │ 7        │ yes     │ fitting any declared type does  │
# └───────────┴──────────────────┴──────────┴─────────┴─────────────────────────────────┘
#
# fmt: off
SHAPE_CASES: list[tuple[str, str, list[str], object, bool, str]] = [
    # (key,       field,            types,                 captured,  mapped, id)
    ("cmStatus", "docsis_status",   ["string"],            "OPER",    True,   "text-fits-string"),
    ("cmStatus", "docsis_status",   ["string"],            7,         False,  "number-misfits-string"),
    ("cmCount",  "channel_count",   ["integer"],           "12",      True,   "numeric-text-fits-integer"),
    ("cmCount",  "channel_count",   ["integer"],           "twelve",  False,  "text-misfits-integer"),
    ("cmUp",     "system_uptime",   ["uptime"],            360,       True,   "any-fits-other-types"),
    ("cmStatus", "docsis_status",   ["string", "integer"], 7,         True,   "fits-one-of-several"),
]
# fmt: on


def _fleet_for(key: str, field: str, types: list[str]) -> FleetPatterns:
    """A fleet that learned ``key`` as ``field``, declared with each of ``types``."""
    normalized = key.lower()
    return FleetPatterns(
        system_info_json_keys={normalized: (field, 1)},
        system_info_json_key_types={normalized: {t: sorted(_DECLARES) for t in types}},
    )


@pytest.mark.parametrize(
    "key,field,types,captured,mapped",
    [c[:5] for c in SHAPE_CASES],
    ids=[c[5] for c in SHAPE_CASES],
)
def test_fleet_key_maps_only_a_fitting_value(
    key: str, field: str, types: list[str], captured: object, mapped: bool
) -> None:
    """A learned key maps when its value fits a declared type; a misfit is left unmapped and warned."""
    page = PageAnalysis(resource="/api/info", content_type="application/json", json_data={"cm": {key: captured}})
    warnings: list[str] = []
    result = detect_system_info([page], warnings, fleet=_fleet_for(key, field, types))
    fields = [f.field for s in (result.sources if result else []) for f in s.fields]
    assert (field in fields) is mapped
    assert any(key in w and "not mapped" in w for w in warnings) is not mapped


def test_misfit_warning_names_the_evidence() -> None:
    """The warning cites the key, where it sits, the declaring entries, the declared type and the value."""
    page = PageAnalysis(resource="/api/info", content_type="application/json", json_data={"cm": {"cmStatus": 7}})
    warnings: list[str] = []
    detect_system_info([page], warnings, fleet=_fleet_for("cmStatus", "docsis_status", ["string"]))
    assert [w for w in warnings if "not mapped" in w] == [
        "WARNING: JSON key 'cm.cmStatus' on /api/info is docsis_status in vendor/a, vendor/b as string, "
        "but the capture holds 7; not mapped. Review which key carries docsis_status."
    ]


def test_misfit_leaves_the_field_for_another_key() -> None:
    """A later key that fits still claims the field."""
    page = PageAnalysis(
        resource="/api/info",
        content_type="application/json",
        json_data={"cmStatus": 7, "networkAccess": "Permitted"},
    )
    result = detect_system_info([page], [], fleet=_fleet_for("cmStatus", "docsis_status", ["string"]))
    assert result is not None
    assert [(f.field, f.source) for f in result.sources[0].fields] == [("docsis_status", "networkAccess")]


def test_baseline_key_is_not_shape_checked() -> None:
    """Only fleet-learned keys are checked; the baseline map applies as before."""
    page = PageAnalysis(resource="/api/info", content_type="application/json", json_data={"uptime": "3 days"})
    fleet = FleetPatterns(system_info_json_key_types={"uptime": {"integer": ["vendor/a"]}})
    result = detect_system_info([page], [], fleet=fleet)
    assert result is not None
    assert [f.field for f in result.sources[0].fields] == ["system_uptime"]
