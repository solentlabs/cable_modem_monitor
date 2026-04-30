"""Unit tests for generate_config.system_info transformations.

Pure-function tests covering each branch of transform_system_info
and its private helpers (_transform_hnap_system_info,
_transform_json_system_info). The wider generate_config pipeline
is exercised by test_generate_config.py via fixtures; this file
isolates the transformation logic for direct branch coverage.
"""

from __future__ import annotations

from solentlabs.cable_modem_monitor_catalog_tools.generate_config.system_info import (
    _transform_hnap_system_info,
    _transform_json_system_info,
    transform_system_info,
)

# -----------------------------------------------------------------------
# transform_system_info — top-level dispatcher
# -----------------------------------------------------------------------


def test_dispatch_hnap_source() -> None:
    """HNAP source format routes to HNAP transformer."""
    result = transform_system_info(
        {
            "sources": [
                {
                    "format": "hnap",
                    "response_key": "GetMyStatusResponse",
                    "fields": {"HwVersion": "hardware_version"},
                }
            ]
        }
    )
    assert len(result["sources"]) == 1
    assert result["sources"][0]["format"] == "hnap"
    assert result["sources"][0]["fields"] == [{"source": "HwVersion", "field": "hardware_version", "type": "string"}]


def test_dispatch_json_source() -> None:
    """JSON source format routes to JSON transformer."""
    result = transform_system_info(
        {
            "sources": [
                {
                    "format": "json",
                    "resource": "/api/info",
                    "fields": [{"source": "fw", "field": "firmware", "type": "string"}],
                }
            ]
        }
    )
    assert len(result["sources"]) == 1
    assert result["sources"][0]["format"] == "json"
    assert result["sources"][0]["resource"] == "/api/info"


def test_dispatch_html_fields_passes_through() -> None:
    """html_fields and other unrecognized formats pass through unchanged."""
    source = {
        "format": "html_fields",
        "resource": "/status.html",
        "fields": [{"selector": "td", "field": "model", "type": "string"}],
    }
    result = transform_system_info({"sources": [source]})
    assert result["sources"][0] is source


def test_dispatch_javascript_passes_through() -> None:
    """javascript format also flows through the else branch unchanged."""
    source = {"format": "javascript", "resource": "/info.js"}
    result = transform_system_info({"sources": [source]})
    assert result["sources"][0] is source


def test_dispatch_no_sources_returns_empty_sources() -> None:
    """Missing 'sources' key produces an empty list."""
    result = transform_system_info({})
    assert result == {"sources": []}


# -----------------------------------------------------------------------
# _transform_hnap_system_info
# -----------------------------------------------------------------------


def test_hnap_transforms_dict_fields_into_list() -> None:
    """HNAP fields dict {hnap_key: canonical} → list of {source, field, type}."""
    result = _transform_hnap_system_info(
        {
            "format": "hnap",
            "response_key": "GetMyStatusResponse",
            "fields": {
                "HwVersion": "hardware_version",
                "ModelName": "model",
            },
        }
    )
    assert result["format"] == "hnap"
    assert result["response_key"] == "GetMyStatusResponse"
    expected_fields = [
        {"source": "HwVersion", "field": "hardware_version", "type": "string"},
        {"source": "ModelName", "field": "model", "type": "string"},
    ]
    # Order may vary in older Python but 3.7+ preserves dict insertion order
    assert sorted(result["fields"], key=lambda f: f["source"]) == sorted(expected_fields, key=lambda f: f["source"])


def test_hnap_passes_through_already_listy_fields() -> None:
    """If fields is already a list (analysis already normalized), pass through."""
    fields_list = [{"source": "HwVersion", "field": "hardware_version", "type": "string"}]
    result = _transform_hnap_system_info(
        {
            "format": "hnap",
            "response_key": "X",
            "fields": fields_list,
        }
    )
    assert result["fields"] is fields_list


def test_hnap_missing_response_key_defaults_to_empty() -> None:
    """A source without response_key gets an empty string default."""
    result = _transform_hnap_system_info({"format": "hnap", "fields": {}})
    assert result["response_key"] == ""
    assert result["fields"] == []


# -----------------------------------------------------------------------
# _transform_json_system_info
# -----------------------------------------------------------------------


def test_json_basic_transformation() -> None:
    """Basic fields list with key/field/type passes through."""
    result = _transform_json_system_info(
        {
            "format": "json",
            "resource": "/api/info",
            "fields": [
                {"key": "hwVersion", "field": "hardware_version", "type": "string"},
                {"key": "swVersion", "field": "software_version", "type": "string"},
            ],
        }
    )
    assert result["format"] == "json"
    assert result["resource"] == "/api/info"
    assert len(result["fields"]) == 2
    assert result["fields"][0]["key"] == "hwVersion"
    assert result["fields"][0]["field"] == "hardware_version"


def test_json_source_key_normalized_to_key() -> None:
    """Fields using analysis 'source' key are renamed to 'key' for the model."""
    result = _transform_json_system_info(
        {
            "format": "json",
            "resource": "/api/info",
            "fields": [
                {"source": "fw", "field": "firmware", "type": "string"},
            ],
        }
    )
    assert result["fields"][0]["key"] == "fw"
    assert "source" not in result["fields"][0]


def test_json_path_field_preserved() -> None:
    """JSONPath path values flow through into the transformed field."""
    result = _transform_json_system_info(
        {
            "format": "json",
            "resource": "/api/info",
            "fields": [
                {"key": "x", "field": "model", "type": "string", "path": "$.device.model"},
            ],
        }
    )
    assert result["fields"][0]["path"] == "$.device.model"


def test_json_encoding_propagated_when_set() -> None:
    """Source-level 'encoding' (e.g., base64) is forwarded into the transformed source."""
    result = _transform_json_system_info(
        {
            "format": "json",
            "resource": "/api/info",
            "encoding": "base64",
            "fields": [],
        }
    )
    assert result["encoding"] == "base64"


def test_json_encoding_omitted_when_absent() -> None:
    """No encoding key in source → no encoding key in result."""
    result = _transform_json_system_info({"format": "json", "resource": "/api/info", "fields": []})
    assert "encoding" not in result
