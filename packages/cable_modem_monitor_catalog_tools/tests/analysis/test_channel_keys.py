"""Tests for fleet-learned channel JSON keys: learned meanings, and disagreements as ambiguities.

Table-driven: each case is one channel key, the meanings committed
parser.yaml files declare for it, and the field analysis maps it to
plus the candidates of the ambiguity it raises.

Per docs/ONBOARDING_SPEC.md § Ambiguities (Channel key meanings).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.analysis.ambiguity import Ambiguity
from solentlabs.cable_modem_monitor_catalog_tools.analysis.format import detect_sections
from solentlabs.cable_modem_monitor_catalog_tools.analysis.types import FleetPatterns
from solentlabs.cable_modem_monitor_catalog_tools.analyze_har import analyze_har
from tests._helpers import load_fixture, write_har

_JSON_RPC_FIXTURE = Path(__file__).parent.parent / "fixtures" / "analyze_har" / "json_rpc" / "login_and_data.json"

_TWO_MEANINGS = {"lock_status": ["vendor/a"], "status": ["vendor/b", "vendor/c"]}
_DISAGREES = FleetPatterns(channel_keys={"status": _TWO_MEANINGS})
_MER_IS_SNR = FleetPatterns(channel_keys={"mer": {"snr": ["vendor/a"]}})
_POWERLEVEL_IS_SNR = FleetPatterns(channel_keys={"powerlevel": {"snr": ["vendor/a"]}})


def _json_entry(url: str, body: str, content_type: str = "application/json") -> dict[str, Any]:
    """A minimal HAR entry serving ``body``."""
    return {
        "request": {"method": "GET", "url": f"http://192.168.100.1{url}", "headers": []},
        "response": {
            "status": 200,
            "headers": [{"name": "Content-Type", "value": content_type}],
            "content": {"size": len(body), "mimeType": content_type, "text": body},
        },
    }


def _downstream(key: str, values: list[Any]) -> list[dict[str, Any]]:
    """One JSON downstream page whose channels carry ``key``, beside the measurement that makes them channels."""
    channels = [{"channelId": i + 1, "frequency": 507000000, key: value} for i, value in enumerate(values)]
    return [_json_entry("/api/downstream", json.dumps({"channels": channels}))]


def _sections(entries: list[dict[str, Any]], fleet: FleetPatterns | None) -> tuple[dict[str, Any], list[Ambiguity]]:
    """Run section detection and return the sections plus the ambiguities it raised."""
    ambiguities: list[Ambiguity] = []
    sections = detect_sections(entries, "http", [], [], fleet=fleet, ambiguities=ambiguities)
    return sections, ambiguities


def _field_for(section: dict[str, Any], key: str) -> str:
    """The field a section maps ``key`` to."""
    return str(next(m["field"] for m in section["mappings"] if m.get("key") == key))


# =============================================================================
# Key resolution test data
# =============================================================================
#
# ┌────────────┬─────────────────────┬────────┬─────────────────────┬────────────────────────┐
# │ key        │ fleet declares      │ field  │ candidates          │ description            │
# ├────────────┼─────────────────────┼────────┼─────────────────────┼────────────────────────┤
# │ powerLevel │ powerlevel → snr    │ power  │ none                │ registry applies first │
# │ mer        │ mer → snr           │ snr    │ none                │ one meaning is learned │
# │ status     │ lock_status, status │ status │ lock_status, status │ disagreement is judged │
# │ zeta       │ mer only            │ zeta   │ none                │ unseen keeps Tier 3    │
# │ mer        │ (no fleet)          │ mer    │ none                │ no fleet, no learning  │
# └────────────┴─────────────────────┴────────┴─────────────────────┴────────────────────────┘
#
# fmt: off
CASES: list[tuple[str, FleetPatterns | None, str, list[str], str]] = [
    # (key,         fleet,              field,    candidates,                id)
    ("powerLevel",  _POWERLEVEL_IS_SNR, "power",  [],                        "registry-first"),
    ("mer",         _MER_IS_SNR,        "snr",    [],                        "one-meaning-learned"),
    ("status",      _DISAGREES,         "status", ["lock_status", "status"], "disagreement-ambiguity"),
    ("zeta",        _MER_IS_SNR,        "zeta",   [],                        "unseen-tier-3"),
    ("mer",         None,               "mer",    [],                        "no-fleet"),
]
# fmt: on


@pytest.mark.parametrize(
    "key,fleet,field,candidates",
    [c[:4] for c in CASES],
    ids=[c[4] for c in CASES],
)
def test_channel_key_resolution(key: str, fleet: FleetPatterns | None, field: str, candidates: list[str]) -> None:
    """The registry maps first, then one fleet meaning; a disagreement keeps Tier 3 and raises an ambiguity."""
    sections, ambiguities = _sections(_downstream(key, [1.5, 2.5]), fleet)
    assert _field_for(sections["downstream"], key) == field
    assert [[c.value for c in a.candidates] for a in ambiguities] == ([candidates] if candidates else [])


def test_ambiguity_addresses_section_and_key() -> None:
    """The path names the section and the wire key; the ambiguity does not block generation."""
    _, ambiguities = _sections(_downstream("Status", ["Locked", "Locked"]), _DISAGREES)
    assert [(a.field, a.blocking, a.resolution) for a in ambiguities] == [("parser.downstream.Status", False, None)]


def test_candidate_evidence_cites_declaring_entries_and_capture() -> None:
    """Each candidate cites the entries that declare it and the capture's values; the fleet never corroborates."""
    _, ambiguities = _sections(_downstream("status", ["Locked", "Locked", "Not Locked"]), _DISAGREES)
    capture = ("/api/downstream", '"status": Locked, Not Locked')
    declares_status = [(f"vendor/{m}/parser.yaml", "status → status") for m in ("b", "c")]
    assert [
        (c.value, [(e.source, e.snippet) for e in c.evidence], c.corroborated_by) for c in ambiguities[0].candidates
    ] == [
        ("lock_status", [("vendor/a/parser.yaml", "status → lock_status"), capture], []),
        ("status", [*declares_status, capture], []),
    ]


def test_javascript_json_section_is_addressed_by_direction() -> None:
    """A JS-embedded JSON array is addressed by the direction its variable names."""
    body = '<script>json_dsData = [{"ChannelID":"1","Frequency":"507 MHz","status":"Locked"}];</script>'
    _, ambiguities = _sections([_json_entry("/php/data.php", body, "text/html")], _DISAGREES)
    assert [a.field for a in ambiguities] == ["parser.downstream.status"]


def test_http_analysis_reports_key_ambiguities(tmp_path: Path) -> None:
    """analyze_har carries a key ambiguity from an HTTP capture into its output."""
    har = write_har(tmp_path, {"log": {"entries": _downstream("status", ["Locked"])}})
    result = analyze_har(har, fleet=_DISAGREES)
    assert [a["field"] for a in result.to_dict()["ambiguities"]] == ["parser.downstream.status"]


def test_json_rpc_analysis_reports_key_ambiguities(tmp_path: Path) -> None:
    """A JSON-RPC capture's key ambiguity sits beside its auth and restart ambiguities."""
    data = load_fixture(_JSON_RPC_FIXTURE)
    fleet = FleetPatterns(channel_keys={"channel": {"channel_id": ["vendor/a"], "channel_number": ["vendor/b"]}})
    result = analyze_har(write_har(tmp_path, data["_har"]), fleet=fleet)
    assert "parser.downstream.channel" in [a.field for a in result.ambiguities]
