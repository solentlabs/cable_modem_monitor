"""Tests for fleet scanner — validates pattern extraction from the catalog.

The fleet scanner reads all parser.yaml files and builds FleetPatterns.
These tests run against the real catalog to verify extraction correctness.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from solentlabs.cable_modem_monitor_catalog import CATALOG_PATH
from solentlabs.cable_modem_monitor_catalog_tools.analysis.types import FleetPatterns
from solentlabs.cable_modem_monitor_catalog_tools.fleet_scanner import AuthAuditIssue, audit_fleet_auth, scan_fleet


@pytest.fixture(scope="module")
def fleet() -> FleetPatterns:
    """Scan the real catalog once per module."""
    return scan_fleet(CATALOG_PATH)


class TestScanFleetStructure:
    """Verify scan_fleet returns a well-formed FleetPatterns."""

    def test_returns_fleet_patterns(self, fleet: FleetPatterns) -> None:
        """scan_fleet returns a FleetPatterns instance."""
        assert isinstance(fleet, FleetPatterns)

    def test_selector_directions_non_empty(self, fleet: FleetPatterns) -> None:
        """Fleet has selector→direction mappings from parser.yaml selectors."""
        assert len(fleet.selector_directions) > 0

    def test_system_info_labels_non_empty(self, fleet: FleetPatterns) -> None:
        """Fleet has system_info label→field mappings."""
        assert len(fleet.system_info_labels) > 0

    def test_system_info_json_keys_non_empty(self, fleet: FleetPatterns) -> None:
        """Fleet has system_info JSON key→field mappings."""
        assert len(fleet.system_info_json_keys) > 0

    def test_aggregate_fields_non_empty(self, fleet: FleetPatterns) -> None:
        """Fleet has aggregate field pairs."""
        assert len(fleet.aggregate_fields) > 0

    def test_channel_type_values_non_empty(self, fleet: FleetPatterns) -> None:
        """Fleet has channel type values from parser.yaml maps."""
        assert len(fleet.channel_type_values) > 0

    def test_js_function_layouts_non_empty(self, fleet: FleetPatterns) -> None:
        """Fleet extracts JS function layouts from javascript-format sections."""
        assert len(fleet.js_function_layouts) > 0

    def test_js_function_layout_structure(self, fleet: FleetPatterns) -> None:
        """JS function layouts include known Netgear/ARRIS function names with fields."""
        assert "InitDsTableTagValue" in fleet.js_function_layouts
        layout = fleet.js_function_layouts["InitDsTableTagValue"]
        assert isinstance(layout.get("fields"), list)
        assert len(layout["fields"]) > 0
        assert all("offset" in f and "field" in f for f in layout["fields"])

    def test_hnap_response_layouts_non_empty(self, fleet: FleetPatterns) -> None:
        """Fleet extracts HNAP response key layouts from hnap-format sections."""
        assert len(fleet.hnap_response_layouts) > 0

    def test_hnap_response_layout_structure(self, fleet: FleetPatterns) -> None:
        """HNAP response layouts include known ARRIS response keys with fields."""
        assert "GetCustomerStatusDownstreamChannelInfoResponse" in fleet.hnap_response_layouts
        layout = fleet.hnap_response_layouts["GetCustomerStatusDownstreamChannelInfoResponse"]
        assert isinstance(layout.get("fields"), list)
        assert len(layout["fields"]) > 0
        assert all("index" in f and "field" in f for f in layout["fields"])

    def test_hnap_response_layout_has_channel_number(self, fleet: FleetPatterns) -> None:
        """HNAP downstream layout includes channel_number at index 0."""
        layout = fleet.hnap_response_layouts.get("GetCustomerStatusDownstreamChannelInfoResponse", {})
        fields = {f["index"]: f["field"] for f in layout.get("fields", []) if "index" in f}
        assert fields.get(0) == "channel_number"


# ┌─────────────────────────┬───────────────────┬──────────────────────────────────┐
# │ field                   │ expected key      │ value                            │
# ├─────────────────────────┼───────────────────┼──────────────────────────────────┤
# │ selector_directions     │ "downstream"      │ "downstream"                     │
# │ selector_directions     │ "upstream"        │ "upstream"                       │
# │ system_info_labels      │ "system uptime"   │ ("system_uptime", 1)             │
# │ system_info_labels      │ "hw version"      │ ("hardware_version", 1)          │
# │ system_info_json_keys   │ "uptime"          │ ("system_uptime", 1)             │
# │ system_info_json_keys   │ "firmwareversion" │ ("software_version", 1)          │
# │ aggregate_fields        │ —                 │ ("corrected", "total_corrected") │
# └─────────────────────────┴───────────────────┴──────────────────────────────────┘
#
# fmt: off
EXPECTED_SELECTORS = [
    ("downstream",              "downstream"),
    ("upstream",                "upstream"),
    ("downstream bonded channels", "downstream"),
    ("upstream bonded channels",   "upstream"),
]

EXPECTED_LABELS = [
    ("system uptime",    ("system_uptime", 1)),
    ("hw version",       ("hardware_version", 1)),
    ("software version", ("software_version", 1)),
]

EXPECTED_JSON_KEYS = [
    ("uptime",           ("system_uptime", 1)),
    ("firmwareversion",  ("software_version", 1)),
    ("hardwareversion",  ("hardware_version", 1)),
]
# fmt: on


class TestScanFleetContent:
    """Verify specific fleet patterns are extracted correctly."""

    @pytest.mark.parametrize(
        "selector,direction",
        EXPECTED_SELECTORS,
        ids=[s for s, _ in EXPECTED_SELECTORS],
    )
    def test_selector_direction(self, fleet: FleetPatterns, selector: str, direction: str) -> None:
        """Known selector text maps to correct direction."""
        assert fleet.selector_directions.get(selector) == direction

    @pytest.mark.parametrize(
        "label,expected",
        EXPECTED_LABELS,
        ids=[lbl for lbl, _ in EXPECTED_LABELS],
    )
    def test_system_info_label(self, fleet: FleetPatterns, label: str, expected: tuple[str, int]) -> None:
        """Known system_info labels map to correct fields."""
        assert fleet.system_info_labels.get(label) == expected

    @pytest.mark.parametrize(
        "key,expected",
        EXPECTED_JSON_KEYS,
        ids=[k for k, _ in EXPECTED_JSON_KEYS],
    )
    def test_system_info_json_key(self, fleet: FleetPatterns, key: str, expected: tuple[str, int]) -> None:
        """Known JSON keys map to correct fields."""
        assert fleet.system_info_json_keys.get(key) == expected

    def test_aggregate_corrected(self, fleet: FleetPatterns) -> None:
        """corrected→total_corrected aggregate pair is in the fleet."""
        assert ("corrected", "total_corrected") in fleet.aggregate_fields

    def test_aggregate_uncorrected(self, fleet: FleetPatterns) -> None:
        """uncorrected→total_uncorrected aggregate pair is in the fleet."""
        assert ("uncorrected", "total_uncorrected") in fleet.aggregate_fields

    def test_all_directions_valid(self, fleet: FleetPatterns) -> None:
        """All selector_directions values are 'downstream' or 'upstream'."""
        for direction in fleet.selector_directions.values():
            assert direction in ("downstream", "upstream")

    def test_all_labels_lowercase(self, fleet: FleetPatterns) -> None:
        """All system_info label keys are normalized to lowercase."""
        for label in fleet.system_info_labels:
            assert label == label.lower()


class TestAuditFleetAuth:
    """audit_fleet_auth catches login_page / HAR fixture mismatches."""

    def test_empty_directory_returns_no_issues(self, tmp_path: Path) -> None:
        """Empty catalog directory returns empty issue list."""
        assert audit_fleet_auth(tmp_path) == []

    def test_missing_login_page_detected(self, tmp_path: Path) -> None:
        """Modem with login_page set but no matching HAR entry is flagged."""
        import json

        modem_dir = tmp_path / "modems" / "acme" / "m1"
        test_data = modem_dir / "test_data"
        test_data.mkdir(parents=True)

        (modem_dir / "modem.yaml").write_text(
            "manufacturer: Acme\nmodel: M1\n"
            "auth:\n  strategy: form\n  action: /goform/Login\n"
            "  login_page: /Login.asp\n  username_field: u\n  password_field: p\n",
            encoding="utf-8",
        )
        (test_data / "modem.har").write_text(
            json.dumps(
                {
                    "log": {
                        "entries": [
                            {
                                "request": {"method": "POST", "url": "http://192.168.0.1/goform/Login"},
                                "response": {"status": 302, "headers": [], "content": {}},
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )

        issues = audit_fleet_auth(tmp_path)
        assert len(issues) == 1
        assert issues[0].modem == "modems/acme/m1"
        assert "no GET entry" in issues[0].issue

    def test_non_form_auth_skipped(self, tmp_path: Path) -> None:
        """Modems with non-form auth strategy produce no issues."""
        modem_dir = tmp_path / "modems" / "acme" / "m2"
        test_data = modem_dir / "test_data"
        test_data.mkdir(parents=True)

        (modem_dir / "modem.yaml").write_text(
            "manufacturer: Acme\nmodel: M2\nauth:\n  strategy: basic\n",
            encoding="utf-8",
        )
        (test_data / "modem.har").write_text('{"log": {"entries": []}}', encoding="utf-8")

        assert audit_fleet_auth(tmp_path) == []

    def test_audit_issue_fields(self, tmp_path: Path) -> None:
        """AuthAuditIssue carries modem, har, and issue fields."""
        import json

        modem_dir = tmp_path / "modems" / "acme" / "m3"
        test_data = modem_dir / "test_data"
        test_data.mkdir(parents=True)

        (modem_dir / "modem.yaml").write_text(
            "manufacturer: Acme\nmodel: M3\n"
            "auth:\n  strategy: form\n  action: /goform/Login\n"
            "  login_page: /Login.asp\n  username_field: u\n  password_field: p\n",
            encoding="utf-8",
        )
        (test_data / "modem.har").write_text(json.dumps({"log": {"entries": []}}), encoding="utf-8")

        issues = audit_fleet_auth(tmp_path)
        assert len(issues) == 1
        issue = issues[0]
        assert isinstance(issue, AuthAuditIssue)
        assert issue.har == "modem.har"
        assert issue.issue


class TestScanFleetEdgeCases:
    """Edge cases and robustness."""

    def test_empty_directory(self, tmp_path: Path) -> None:
        """scan_fleet on empty directory returns empty FleetPatterns."""
        fleet = scan_fleet(tmp_path)
        assert fleet.selector_directions == {}
        assert fleet.system_info_labels == {}
        assert fleet.delimiters == set()
        assert fleet.aggregate_fields == []

    def test_malformed_yaml(self, tmp_path: Path) -> None:
        """scan_fleet skips malformed YAML files without crashing."""
        bad_yaml = tmp_path / "modems" / "bad" / "modem" / "parser.yaml"
        bad_yaml.parent.mkdir(parents=True)
        bad_yaml.write_text("{{invalid yaml", encoding="utf-8")
        fleet = scan_fleet(tmp_path)
        assert isinstance(fleet, FleetPatterns)
