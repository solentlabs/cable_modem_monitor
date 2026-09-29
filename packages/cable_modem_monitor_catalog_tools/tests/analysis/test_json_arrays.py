"""Tests for JSON channel array detection: every channel array, its direction and channel type.

A list of objects is a channel array when a key maps to a measurement
(frequency, power, snr); every other list is skipped with a warning.
Several ``json`` arrays for a direction come out in ``arrays`` form.

Per docs/ONBOARDING_SPEC.md § Format-specific mapping (`json` format).
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.analysis.ambiguity import Ambiguity
from solentlabs.cable_modem_monitor_catalog_tools.analysis.format import detect_sections
from solentlabs.cable_modem_monitor_catalog_tools.analysis.format.dispatcher import _direction_from_array_path
from solentlabs.cable_modem_monitor_catalog_tools.analysis.types import FleetPatterns


def _entry(url: str, body: str, content_type: str = "application/json") -> dict[str, Any]:
    """A minimal HAR entry serving ``body``."""
    return {
        "request": {"method": "GET", "url": f"http://192.168.100.1{url}", "headers": []},
        "response": {
            "status": 200,
            "headers": [{"name": "Content-Type", "value": content_type}],
            "content": {"size": len(body), "mimeType": content_type, "text": body},
        },
    }


# A status response shaped like a DOCSIS 3.1 gateway's: an address list
# first, four channel arrays, and a codeword companion with no measurement.
_STATUS = {
    "wan6": [{"linklocal": "fe80::1"}],
    "docsis": {
        "ofdmachannel": {"ofdmachannel": [{"ofdmaID": 41, "powerLevel": 40.1}]},
        "dschannel": {"dschannel": [{"channelID": 1, "frequency": 507000000, "powerLevel": 3.2}]},
        "errcodeword": {"errcodeword": [{"ChannelID": 1, "correctableCodewords": 5}]},
        "uschannel": {"uschannel": [{"channelID": 2, "frequency": 36000000, "powerLevel": 44.0}]},
        "ofdmchannel": {"ofdmchannel": [{"ofdmID": 33, "powerLevel": 1.5}]},
    },
}


def _sections(entries: list[dict[str, Any]], fleet: FleetPatterns | None = None) -> tuple[dict[str, Any], list[str]]:
    """Run section detection; return the sections and the warnings."""
    warnings: list[str] = []
    return detect_sections(entries, "http", warnings, [], fleet=fleet), warnings


def _arrays(section: dict[str, Any]) -> list[tuple[str, Any]]:
    """Each array's path and channel type."""
    return [(a["array_path"], a.get("channel_type")) for a in section["arrays"]]


class TestEveryChannelArray:
    """One response with several channel arrays yields both directions in arrays form."""

    def test_downstream_arrays(self) -> None:
        """SC-QAM and OFDM arrays, in response order, typed by path."""
        sections, _ = _sections([_entry("/cgi-bin/status", json.dumps(_STATUS))])
        assert _arrays(sections["downstream"]) == [
            ("docsis.dschannel.dschannel", {"fixed": "qam"}),
            ("docsis.ofdmchannel.ofdmchannel", {"fixed": "ofdm"}),
        ]

    def test_upstream_arrays(self) -> None:
        """OFDMA is upstream; the SC-QAM upstream array takes the direction's default type."""
        sections, _ = _sections([_entry("/cgi-bin/status", json.dumps(_STATUS))])
        assert _arrays(sections["upstream"]) == [
            ("docsis.ofdmachannel.ofdmachannel", {"fixed": "ofdma"}),
            ("docsis.uschannel.uschannel", {"fixed": "atdma"}),
        ]

    def test_each_array_carries_its_mappings(self) -> None:
        """Mappings are per array, not merged across the section."""
        sections, _ = _sections([_entry("/cgi-bin/status", json.dumps(_STATUS))])
        keys = [[m["key"] for m in a["mappings"]] for a in sections["downstream"]["arrays"]]
        assert keys == [["channelID", "frequency", "powerLevel"], ["ofdmID", "powerLevel"]]

    def test_skipped_arrays_are_warned(self) -> None:
        """Lists with no measurement key are named, so a missed channel array shows at review."""
        _, warnings = _sections([_entry("/cgi-bin/status", json.dumps(_STATUS))])
        skipped = [w for w in warnings if "no channel measurement" in w]
        assert len(skipped) == 2
        assert "wan6" in skipped[0] and "docsis.errcodeword.errcodeword" in skipped[1]

    def test_one_array_stays_flat(self) -> None:
        """A single channel array keeps the flat form."""
        body = json.dumps({"channels": [{"channelId": 1, "frequency": 507000000}]})
        sections, _ = _sections([_entry("/api/downstream", body)])
        assert sections["downstream"]["array_path"] == "channels"
        assert "arrays" not in sections["downstream"]

    def test_no_channel_array_no_section(self) -> None:
        """A response whose only list has no measurement yields no section, only a warning."""
        sections, warnings = _sections([_entry("/api/downstream", json.dumps({"log": [{"message": "x"}]}))])
        assert "downstream" not in sections
        assert any("log" in w and "no channel measurement" in w for w in warnings)

    def test_fleet_measurement_key_selects_array(self) -> None:
        """A measurement key only the fleet maps still makes a channel array."""
        body = json.dumps({"rows": [{"num": 1, "FreqD": 507000000}]})
        fleet = FleetPatterns(channel_keys={"freqd": {"frequency": ["vendor/a"]}})
        without, _ = _sections([_entry("/api/downstream", body)])
        learned, _ = _sections([_entry("/api/downstream", body)], fleet)
        assert "downstream" not in without
        assert learned["downstream"]["array_path"] == "rows"

    def test_key_ambiguity_raised_once_per_section(self) -> None:
        """A contested key in two arrays of one section is one ambiguity, citing both captures."""
        status = {
            "dschannel": [{"channelID": 1, "frequency": 1, "status": "Locked"}],
            "ofdmchannel": [{"ofdmID": 33, "powerLevel": 1.5, "status": "1"}],
        }
        fleet = FleetPatterns(channel_keys={"status": {"lock_status": ["vendor/a"], "status": ["vendor/b"]}})
        ambiguities: list[Ambiguity] = []
        detect_sections(
            [_entry("/cgi-bin/status", json.dumps(status))], "http", [], [], fleet=fleet, ambiguities=ambiguities
        )
        assert [a.field for a in ambiguities] == ["parser.downstream.status"]
        captured = [e.snippet for e in ambiguities[0].candidates[0].evidence if e.source == "/cgi-bin/status"]
        assert captured == ['"status": Locked', '"status": 1']


class TestJavascriptJsonList:
    """A JS variable holding the channel list itself has no path to read."""

    def test_list_variable_stays_flat(self) -> None:
        body = '<script>json_dsData = [{"ChannelID":"1","Frequency":"507 MHz"}];</script>'
        sections, _ = _sections([_entry("/php/status.php", body, "text/html")])
        assert "arrays" not in sections["downstream"]
        assert "array_path" not in sections["downstream"]


# =============================================================================
# Direction from an array's path
# =============================================================================
#
# ┌──────────────────────────────┬────────────┬──────────────────────────────┐
# │ path                         │ direction  │ description                  │
# ├──────────────────────────────┼────────────┼──────────────────────────────┤
# │ docsis.dschannel.dschannel   │ downstream │ ds prefix                    │
# │ docsis.ofdmachannel.ofdmach… │ upstream   │ ofdma before ofdm            │
# │ ofdm                         │ downstream │ ofdm is downstream           │
# │ uss                          │ upstream   │ us prefix                    │
# │ data.ofdma_upstream          │ upstream   │ leaf segment decides         │
# │ upstream.channels            │ upstream   │ parent segment when leaf is  │
# │                              │            │ silent                       │
# │ nodes                        │ unknown    │ no DOCSIS term               │
# │ user.list                    │ unknown    │ English word, not a prefix   │
# └──────────────────────────────┴────────────┴──────────────────────────────┘
#
# fmt: off
PATH_CASES: list[tuple[str, str, str]] = [
    ("docsis.dschannel.dschannel",       "downstream", "ds-prefix"),
    ("docsis.ofdmachannel.ofdmachannel", "upstream",   "ofdma-before-ofdm"),
    ("ofdm",                             "downstream", "ofdm"),
    ("uss",                              "upstream",   "us-prefix"),
    ("data.ofdma_upstream",              "upstream",   "leaf-decides"),
    ("upstream.channels",                "upstream",   "parent-segment"),
    ("nodes",                            "unknown",    "no-term"),
    ("user.list",                        "unknown",    "english-word"),
]
# fmt: on


@pytest.mark.parametrize("path,direction", [c[:2] for c in PATH_CASES], ids=[c[2] for c in PATH_CASES])
def test_direction_from_array_path(path: str, direction: str) -> None:
    """DOCSIS terms in the path decide direction, leaf segment first."""
    assert _direction_from_array_path(path) == direction
