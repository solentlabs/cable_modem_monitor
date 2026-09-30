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


class TestConfirmedConfigValues:
    """Only confirmed entries teach: their auth and action values corroborate ambiguity candidates."""

    @staticmethod
    def _write(root: Path, rel: str, text: str) -> None:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_confirmed_values_indexed_by_path(self, tmp_path: Path) -> None:
        """A confirmed entry's auth and action scalars are indexed; an unconfirmed entry's are not."""
        self._write(
            tmp_path,
            "vendor/m1/modem.yaml",
            "status: confirmed\nauth:\n  strategy: json_rpc\n  lockout_code: codeLocked\n"
            "actions:\n  restart:\n    type: json_rpc\n    method: SYS.reboot\n",
        )
        self._write(
            tmp_path,
            "vendor/m1/modem-alt.yaml",
            "status: confirmed\nauth:\n  lockout_code: codeLocked\n",
        )
        self._write(
            tmp_path,
            "vendor/m2/modem.yaml",
            "status: awaiting_verification\nauth:\n  lockout_code: codeOther\n",
        )
        values = scan_fleet(tmp_path).confirmed_config_values
        assert values["auth.lockout_code"] == {"codeLocked": ["vendor/m1", "vendor/m1/modem-alt"]}
        assert values["actions.restart.method"] == {"SYS.reboot": ["vendor/m1"]}
        assert "codeOther" not in values.get("auth.lockout_code", {})


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


class TestExcludeOneModem:
    """The intake score grades each HAR against a fleet that excludes its own committed config."""

    @staticmethod
    def _write(root: Path, rel: str, text: str) -> None:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _catalog(self, root: Path) -> None:
        for model, key, code, pwd in (("m1", "k1", "c1", "pw1"), ("m2", "k2", "c2", "pw2")):
            self._write(
                root,
                f"vendor/{model}/parser.yaml",
                f"system_info:\n  sources:\n    - format: json\n      resource: /a\n      fields:\n"
                f"        - key: {key}\n          field: software_version\n          type: string\n",
            )
            self._write(
                root,
                f"vendor/{model}/modem.yaml",
                f"status: confirmed\nauth:\n  strategy: json_rpc\n  password_field: {pwd}\n  lockout_code: {code}\n",
            )

    def test_whole_fleet_learns_both(self, tmp_path: Path) -> None:
        """Without exclusion every committed entry teaches."""
        self._catalog(tmp_path)
        fleet = scan_fleet(tmp_path)
        assert set(fleet.system_info_json_keys) == {"k1", "k2"}
        assert fleet.password_field_names == frozenset({"pw1", "pw2"})
        assert set(fleet.confirmed_config_values["auth.lockout_code"]) == {"c1", "c2"}

    def test_excluded_modem_teaches_nothing(self, tmp_path: Path) -> None:
        """The excluded directory's parser patterns, password field and confirmed values are all absent."""
        self._catalog(tmp_path)
        fleet = scan_fleet(tmp_path, exclude=tmp_path / "vendor" / "m1")
        assert set(fleet.system_info_json_keys) == {"k2"}
        assert fleet.password_field_names == frozenset({"pw2"})
        assert set(fleet.confirmed_config_values["auth.lockout_code"]) == {"c2"}


class TestChannelJsonKeys:
    """Channel JSON keys are learned from every committed parser.yaml, with the entries that declare each meaning."""

    @staticmethod
    def _write(root: Path, rel: str, text: str) -> None:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _catalog(self, root: Path) -> None:
        # m1 nests two json arrays that both declare "status"; m2 is javascript_json, whose list is mappings.
        self._write(
            root,
            "vendor/m1/parser.yaml",
            "downstream:\n  format: json\n  resource: /a\n  arrays:\n"
            "    - array_path: dss\n      fields:\n        - {key: Status, field: lock_status, type: lock_status}\n"
            "    - array_path: ofdm\n      fields:\n        - {key: status, field: lock_status, type: lock_status}\n",
        )
        self._write(
            root,
            "vendor/m2/parser.yaml",
            "upstream:\n  format: javascript_json\n  resource: /b\n  variable: json_usData\n"
            "  mappings:\n    - {key: status, field: status, type: string}\n"
            "    - {key: mer, field: snr, type: float}\n",
        )

    def test_meanings_indexed_with_declaring_entries(self, tmp_path: Path) -> None:
        """Keys are lowercased; an entry is listed once per meaning however many arrays declare it."""
        self._catalog(tmp_path)
        assert scan_fleet(tmp_path).channel_keys == {
            "status": {"lock_status": ["vendor/m1"], "status": ["vendor/m2"]},
            "mer": {"snr": ["vendor/m2"]},
        }

    def test_excluded_modem_teaches_no_keys(self, tmp_path: Path) -> None:
        """The modem under test does not teach its own key vocabulary."""
        self._catalog(tmp_path)
        assert scan_fleet(tmp_path, exclude=tmp_path / "vendor" / "m2").channel_keys == {
            "status": {"lock_status": ["vendor/m1"]},
        }


class TestSystemInfoJsonKeyTypes:
    """Each learned system_info JSON key records the types the fleet declares for it, and who declares them."""

    @staticmethod
    def _write(root: Path, rel: str, text: str) -> None:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _catalog(self, root: Path) -> None:
        for model, key, declared in (
            ("m1", "CMStatus", "string"),
            ("m2", "cmstatus", "string"),
            ("m3", "cmStatus", "integer"),
        ):
            self._write(
                root,
                f"vendor/{model}/parser.yaml",
                f"system_info:\n  sources:\n    - format: json\n      resource: /a\n      fields:\n"
                f"        - key: {key}\n          field: docsis_status\n          type: {declared}\n",
            )

    def test_types_indexed_with_declaring_entries(self, tmp_path: Path) -> None:
        """Keys are lowercased; each declared type lists its entries."""
        self._catalog(tmp_path)
        assert scan_fleet(tmp_path).system_info_json_key_types == {
            "cmstatus": {"string": ["vendor/m1", "vendor/m2"], "integer": ["vendor/m3"]},
        }

    def test_excluded_modem_declares_nothing(self, tmp_path: Path) -> None:
        self._catalog(tmp_path)
        types = scan_fleet(tmp_path, exclude=tmp_path / "vendor" / "m3").system_info_json_key_types
        assert types == {"cmstatus": {"string": ["vendor/m1", "vendor/m2"]}}


class TestXmlVocabulary:
    """XML column and system_info sources teach the same key vocabulary as JSON keys."""

    def test_xml_sources_learned(self, tmp_path: Path) -> None:
        path = tmp_path / "vendor" / "m1" / "parser.yaml"
        path.parent.mkdir(parents=True)
        path.write_text(
            "downstream:\n  format: xml\n  tables:\n    - resource: '10'\n      root_element: downstream_table\n"
            "      child_element: downstream\n      columns:\n        - {source: pow, field: power, type: float}\n"
            "system_info:\n  sources:\n    - format: xml\n      resource: '1'\n      root_element: GlobalSettings\n"
            "      fields:\n        - {source: SwVersion, field: software_version, type: string}\n",
            encoding="utf-8",
        )
        fleet = scan_fleet(tmp_path)
        assert fleet.channel_keys == {"pow": {"power": ["vendor/m1"]}}
        assert fleet.system_info_json_keys["swversion"] == ("software_version", 1)
        assert fleet.system_info_json_key_types["swversion"] == {"string": ["vendor/m1"]}
