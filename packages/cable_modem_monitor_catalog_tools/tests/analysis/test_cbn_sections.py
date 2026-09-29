"""Tests for CBN sections: each getter answer is an XML page keyed by fun, read by the JSON rules.

Per docs/ONBOARDING_SPEC.md § Format-specific mapping (`xml` format).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from solentlabs.cable_modem_monitor_catalog_tools.analysis.format import detect_sections
from solentlabs.cable_modem_monitor_catalog_tools.analysis.types import FleetPatterns
from solentlabs.cable_modem_monitor_catalog_tools.analyze_har import analyze_har
from solentlabs.cable_modem_monitor_catalog_tools.generate_config import generate_config
from solentlabs.cable_modem_monitor_catalog_tools.generate_golden_file import generate_golden_file
from tests._helpers import load_fixture, write_har

_HOST = "http://192.168.100.1"


def _call(fun: str, body: str, path: str = "/xml/getter.xml", extra: str = "") -> dict[str, Any]:
    """A CBN call and its answer."""
    return {
        "request": {
            "method": "POST",
            "url": f"{_HOST}{path}",
            "headers": [],
            "postData": {"mimeType": "application/x-www-form-urlencoded", "text": f"token=T&fun={fun}{extra}"},
        },
        "response": {
            "status": 200,
            "headers": [{"name": "Content-Type", "value": "text/xml"}],
            "content": {"size": len(body), "mimeType": "text/xml", "text": body},
        },
    }


_DOWNSTREAM = (
    '<?xml version="1.0" encoding="utf-8"?><downstream_table><ds_num>2</ds_num>'
    "<downstream><freq>507000000</freq><pow>7</pow><snr>36</snr><chid>1</chid></downstream>"
    "<downstream><freq>513000000</freq><pow>8</pow><snr>37</snr><chid>2</chid></downstream>"
    "</downstream_table>"
)
_UPSTREAM = "<upstream_table><upstream><usid>3</usid><freq>36000000</freq><power>44</power></upstream></upstream_table>"
_SYSTEM = (
    "<cm_system_info><cm_hardware_version>5.01</cm_hardware_version>"
    "<cm_system_uptime>9</cm_system_uptime></cm_system_info>"
)
_FLEET = FleetPatterns(
    channel_keys={"pow": {"power": ["vendor/a"]}, "chid": {"channel_id": ["vendor/a"]}},
    system_info_json_keys={"cm_hardware_version": ("hardware_version", 1)},
)
_METADATA = load_fixture(Path(__file__).parent.parent / "fixtures" / "generate_config" / "valid" / "json_format.json")[
    "_metadata"
]

_ENTRIES = [
    _call("15", "successful;SID=1", path="/xml/setter.xml", extra="&Username=NULL&Password=ENC"),
    _call("10", _DOWNSTREAM),
    _call("11", _UPSTREAM),
    _call("2", _SYSTEM),
]


def _sections() -> dict[str, Any]:
    return detect_sections(_ENTRIES, "cbn", [], [], fleet=_FLEET)


def test_channel_table_is_an_xml_section() -> None:
    """The repeated children of a table are one channel array, addressed root.child, keyed by fun."""
    downstream = _sections()["downstream"]
    assert (downstream["format"], downstream["resource"], downstream["array_path"]) == (
        "xml",
        "10",
        "downstream_table.downstream",
    )
    assert [(m["key"], m["field"]) for m in downstream["mappings"]] == [
        ("freq", "frequency"),
        ("pow", "power"),
        ("snr", "snr"),
        ("chid", "channel_id"),
    ]


def test_single_child_is_still_a_table() -> None:
    """A table with one child element is a channel array too."""
    upstream = _sections()["upstream"]
    assert (upstream["resource"], upstream["array_path"]) == ("11", "upstream_table.upstream")


def test_scalars_feed_xml_system_info() -> None:
    """A table's scalar children are system_info candidates, named by root element."""
    sources = _sections()["system_info"]["sources"]
    assert [(s["format"], s["resource"]) for s in sources] == [("xml", "2")]


def test_generated_parser_reads_the_capture(tmp_path: Path) -> None:
    """analyze -> generate -> golden: the xml parser.yaml extracts every channel from the capture."""
    har = write_har(tmp_path, {"log": {"entries": _ENTRIES}})
    analysis = analyze_har(har, fleet=_FLEET).to_dict()
    config = generate_config(analysis, _METADATA, fleet=_FLEET)
    assert config.parser_yaml is not None
    assert config.validation.valid, config.validation.errors
    table = yaml.safe_load(config.parser_yaml)["downstream"]["tables"][0]
    assert (table["resource"], table["root_element"], table["child_element"]) == (
        "10",
        "downstream_table",
        "downstream",
    )
    golden = generate_golden_file(str(har), config.parser_yaml, transport="cbn").golden_file
    assert [c["channel_id"] for c in golden["downstream"]] == [1, 2]
    assert [c["power"] for c in golden["upstream"]] == [44.0]
    assert golden["system_info"]["hardware_version"] == "5.01"
