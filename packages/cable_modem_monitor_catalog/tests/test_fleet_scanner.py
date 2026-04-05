"""Tests for fleet scanner — validates pattern extraction from the catalog.

The fleet scanner reads all parser.yaml files and builds FleetPatterns.
These tests run against the real catalog to verify extraction correctness.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from solentlabs.cable_modem_monitor_catalog import CATALOG_PATH
from solentlabs.cable_modem_monitor_catalog.fleet_scanner import scan_fleet
from solentlabs.cable_modem_monitor_core.mcp.analysis.types import FleetPatterns


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
