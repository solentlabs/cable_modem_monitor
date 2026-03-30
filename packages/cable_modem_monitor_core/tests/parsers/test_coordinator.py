"""Tests for ModemParserCoordinator.

- Extraction: fixture-driven (JSON files in fixtures/coordinator/valid/)
- merge_by: table-driven (inline data tables)
- Post-processor hooks: behavioral (inline, using shared fixture for HTML/config)
- Edge cases: behavioral (inline)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from bs4 import BeautifulSoup
from solentlabs.cable_modem_monitor_core.models.parser_config import ParserConfig
from solentlabs.cable_modem_monitor_core.parsers.coordinator import (
    ModemParserCoordinator,
)
from solentlabs.cable_modem_monitor_core.parsers.registries import (
    _merge_channels,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "coordinator"
VALID_FIXTURES = sorted((FIXTURES_DIR / "valid").glob("*.json"))


def _build_resources(html_map: dict[str, str]) -> dict[str, BeautifulSoup]:
    """Build resource dict from a mapping of path -> HTML string."""
    return {path: BeautifulSoup(html, "html.parser") for path, html in html_map.items()}


def _build_json_resources(json_map: dict[str, Any]) -> dict[str, Any]:
    """Build resource dict from a mapping of path -> JSON data."""
    return dict(json_map)


def _load_fixture(name: str) -> dict[str, Any]:
    """Load a named fixture from the coordinator fixtures directory."""
    return dict(json.loads((FIXTURES_DIR / "valid" / name).read_text()))


# ---------------------------------------------------------------------------
# Fixture-driven extraction tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_path",
    VALID_FIXTURES,
    ids=[f.stem for f in VALID_FIXTURES],
)
def test_extraction(fixture_path: Path) -> None:
    """Coordinator produces expected ModemData from fixture."""
    data = json.loads(fixture_path.read_text())

    # Fixtures use either _html (HTML resources) or _json (JSON resources)
    if "_html" in data:
        resources: dict[str, Any] = _build_resources(data["_html"])
    elif "_json" in data:
        resources = _build_json_resources(data["_json"])
    else:
        resources = {}

    config = ParserConfig.model_validate(data["_parser_config"])
    coordinator = ModemParserCoordinator(config)

    result = coordinator.parse(resources)
    expected = data["_expected"]

    assert result == expected, (
        f"Mismatch for {fixture_path.stem}:\n" f"  actual:   {result}\n" f"  expected: {expected}"
    )


# ---------------------------------------------------------------------------
# merge_by — table-driven
# ---------------------------------------------------------------------------

MERGE_CASES = [
    (
        "basic merge",
        [{"channel_id": 1, "frequency": 507}],
        [{"channel_id": 1, "corrected": 100}],
        ["channel_id"],
        [{"channel_id": 1, "frequency": 507, "corrected": 100}],
    ),
    (
        "primary wins",
        [{"channel_id": 1, "power": 3.2}],
        [{"channel_id": 1, "power": 999.0, "snr": 38.5}],
        ["channel_id"],
        [{"channel_id": 1, "power": 3.2, "snr": 38.5}],
    ),
    (
        "no match",
        [{"channel_id": 1, "frequency": 507}],
        [{"channel_id": 99, "corrected": 100}],
        ["channel_id"],
        [{"channel_id": 1, "frequency": 507}],
    ),
    (
        "composite key",
        [
            {"channel_type": "qam", "channel_id": 1, "power": 3.2},
            {"channel_type": "ofdm", "channel_id": 1, "power": 5.0},
        ],
        [
            {"channel_type": "qam", "channel_id": 1, "snr": 38.5},
            {"channel_type": "ofdm", "channel_id": 1, "snr": 42.0},
        ],
        ["channel_type", "channel_id"],
        [
            {"channel_type": "qam", "channel_id": 1, "power": 3.2, "snr": 38.5},
            {"channel_type": "ofdm", "channel_id": 1, "power": 5.0, "snr": 42.0},
        ],
    ),
    (
        "empty companion",
        [{"channel_id": 1, "frequency": 507}],
        [],
        ["channel_id"],
        [{"channel_id": 1, "frequency": 507}],
    ),
    (
        "empty primary",
        [],
        [{"channel_id": 1, "corrected": 100}],
        ["channel_id"],
        [],
    ),
]


@pytest.mark.parametrize("desc,primary,companion,merge_by,expected", MERGE_CASES)
def test_merge_channels(
    desc: str,
    primary: list[dict[str, Any]],
    companion: list[dict[str, Any]],
    merge_by: list[str],
    expected: list[dict[str, Any]],
) -> None:
    """merge_by: {desc}."""
    _merge_channels(primary, companion, merge_by)
    assert primary == expected


# ---------------------------------------------------------------------------
# Post-processor hook tests (behavioral, using shared fixture)
# ---------------------------------------------------------------------------


class _MockPostProcessor:
    """Test post-processor with hooks for downstream and system_info."""

    def parse_downstream(self, channels: list[dict[str, Any]], resources: dict[str, Any]) -> list[dict[str, Any]]:
        """Add a custom field to each channel."""
        for ch in channels:
            ch["custom_field"] = "enriched"
        return channels

    def parse_system_info(self, system_info: dict[str, str], resources: dict[str, Any]) -> dict[str, str]:
        """Replace system_info entirely."""
        return {"custom_key": "custom_value"}


class _ReplacingPostProcessor:
    """Post-processor that replaces downstream with custom extraction."""

    def parse_downstream(self, channels: list[dict[str, Any]], resources: dict[str, Any]) -> list[dict[str, Any]]:
        """Ignore BaseParser output and return custom data."""
        return [{"channel_id": 99, "channel_type": "qam", "custom": True}]


class TestPostProcessorHooks:
    """Tests for parser.py post-processing hook invocation."""

    @pytest.fixture()
    def ds_fixture(self) -> dict[str, Any]:
        """Load the shared downstream fixture for hook tests."""
        return _load_fixture("hook_enriches.json")

    def test_hook_enriches_channels(self, ds_fixture: dict[str, Any]) -> None:
        """Hook adds fields to BaseParser extraction output."""
        resources = _build_resources(ds_fixture["_html"])
        config = ParserConfig.model_validate(ds_fixture["_parser_config"])
        coordinator = ModemParserCoordinator(config, _MockPostProcessor())
        result = coordinator.parse(resources)

        assert result["downstream"][0]["custom_field"] == "enriched"
        assert result["downstream"][0]["frequency"] == 507000000

    def test_hook_replaces_output(self, ds_fixture: dict[str, Any]) -> None:
        """Hook can fully replace BaseParser extraction output."""
        resources = _build_resources(ds_fixture["_html"])
        config = ParserConfig.model_validate(ds_fixture["_parser_config"])
        coordinator = ModemParserCoordinator(config, _ReplacingPostProcessor())
        result = coordinator.parse(resources)

        assert result["downstream"] == [{"channel_id": 99, "channel_type": "qam", "custom": True}]

    def test_no_hook_for_section(self) -> None:
        """Section without a hook uses BaseParser output as-is."""
        data = _load_fixture("downstream_upstream.json")
        resources = _build_resources(data["_html"])
        config = ParserConfig.model_validate(data["_parser_config"])
        # _MockPostProcessor has parse_downstream but NOT parse_upstream
        coordinator = ModemParserCoordinator(config, _MockPostProcessor())
        result = coordinator.parse(resources)

        # upstream used as-is, no "custom_field" added
        assert result["upstream"][0]["frequency"] == 37700000
        assert "custom_field" not in result["upstream"][0]
        # downstream got the hook
        assert result["downstream"][0]["custom_field"] == "enriched"

    def test_system_info_hook(self) -> None:
        """system_info hook replaces extracted system_info."""
        data = _load_fixture("with_system_info.json")
        resources = _build_resources(data["_html"])
        config = ParserConfig.model_validate(data["_parser_config"])
        coordinator = ModemParserCoordinator(config, _MockPostProcessor())
        result = coordinator.parse(resources)

        # Hook replaced the extracted system_info; enrichment adds channel counts
        assert result["system_info"]["custom_key"] == "custom_value"
        assert result["system_info"]["downstream_channel_count"] == 1
        assert result["system_info"]["upstream_channel_count"] == 0

    def test_no_post_processor(self, ds_fixture: dict[str, Any]) -> None:
        """Coordinator with no post-processor uses BaseParser output."""
        resources = _build_resources(ds_fixture["_html"])
        config = ParserConfig.model_validate(ds_fixture["_parser_config"])
        coordinator = ModemParserCoordinator(config)
        result = coordinator.parse(resources)

        assert result["downstream"][0]["frequency"] == 507000000
        assert "custom_field" not in result["downstream"][0]


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and empty inputs."""

    def test_empty_resources(self) -> None:
        """Missing resource returns empty channels."""
        data = _load_fixture("minimal_downstream.json")
        config = ParserConfig.model_validate(data["_parser_config"])
        coordinator = ModemParserCoordinator(config)
        result = coordinator.parse({})

        assert result["downstream"] == []
        assert result["upstream"] == []

    def test_no_channel_sections(self) -> None:
        """Config with only system_info produces empty channel lists."""
        data = _load_fixture("with_system_info.json")
        config = ParserConfig(system_info=data["_parser_config"]["system_info"])
        resources = _build_resources(data["_html"])
        coordinator = ModemParserCoordinator(config)
        result = coordinator.parse(resources)

        assert result["downstream"] == []
        assert result["upstream"] == []
        assert result["system_info"]["software_version"] == "AB01.02.053"
        assert result["system_info"]["system_uptime"] == "7 days 00:00:01"
        assert result["system_info"]["downstream_channel_count"] == 0
        assert result["system_info"]["upstream_channel_count"] == 0

    def test_hook_on_empty_section(self) -> None:
        """Hook is still invoked when config has no mapping for a section."""
        data = _load_fixture("minimal_downstream.json")
        config = ParserConfig.model_validate(data["_parser_config"])
        coordinator = ModemParserCoordinator(config, _MockPostProcessor())
        result = coordinator.parse({})

        assert result["downstream"] == []
        # parse_system_info hook is called with empty dict — returns custom data
        # Channel counts are added by enrichment after hooks
        assert result["system_info"]["custom_key"] == "custom_value"
        assert result["system_info"]["downstream_channel_count"] == 0
        assert result["system_info"]["upstream_channel_count"] == 0


# ---------------------------------------------------------------------------
# Derived field enrichment — channel counts + aggregate sums
# ---------------------------------------------------------------------------

# ┌──────────────────────────────┬────────────────────────────────┬──────────────┐
# │ scenario                     │ expected                       │ description  │
# ├──────────────────────────────┼────────────────────────────────┼──────────────┤
# │ 3 DS, 2 US, no native count │ ds=3, us=2                     │ computed     │
# │ 3 DS, native ds_count=99    │ ds=99 (native wins)            │ setdefault   │
# │ no channels                  │ ds=0, us=0                     │ empty        │
# │ aggregate sum (2 channels)   │ total_corrected=300            │ scoped sum   │
# │ aggregate + native sysinfo   │ native value preserved         │ native wins  │
# │ type-qualified scope         │ only matching channels summed  │ qam filter   │
# │ missing field on channels    │ field not in system_info       │ skip missing │
# └──────────────────────────────┴────────────────────────────────┴──────────────┘
#
# fmt: off
_ENRICHMENT_CASES: list[tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]] = [
    # (description, parser_config_dict, parse_result_pre_enrichment, expected_system_info)
    # Note: parse_result_pre_enrichment simulates what extraction produces
    # before enrichment; tests verify the enrichment layer via parse().
]
# fmt: on


class TestDerivedFieldEnrichment:
    """Channel counts and aggregate sums added to system_info by coordinator."""

    def test_channel_counts_computed(self) -> None:
        """Channel counts added to system_info from parsed channels."""
        config = ParserConfig(
            downstream=_table_section("/status.html"),
        )
        resources = _build_resources(
            {
                "/status.html": _make_table_html("Downstream", [["1", "507"], ["2", "513"], ["3", "519"]]),
            }
        )
        coordinator = ModemParserCoordinator(config)
        result = coordinator.parse(resources)

        assert result["system_info"]["downstream_channel_count"] == 3
        assert result["system_info"]["upstream_channel_count"] == 0

    def test_native_channel_count_wins(self) -> None:
        """Native channel count from system_info takes precedence."""
        config = ParserConfig(
            downstream=_table_section("/status.html"),
            system_info=_sysinfo_section(
                "/info.html",
                [
                    {"label": "DS Channels", "field": "downstream_channel_count", "type": "integer"},
                ],
            ),
        )
        resources = _build_resources(
            {
                "/status.html": _make_table_html("Downstream", [["1", "507"]]),
                "/info.html": _make_field_html({"DS Channels": "99"}),
            }
        )
        coordinator = ModemParserCoordinator(config)
        result = coordinator.parse(resources)

        # Native value ("99") wins over computed (1)
        # html_fields parser returns the raw string; type conversion
        # happens downstream. The setdefault precedence rule still applies.
        assert result["system_info"]["downstream_channel_count"] == "99"

    def test_aggregate_sum(self) -> None:
        """Aggregate sum computed from channel data."""
        from solentlabs.cable_modem_monitor_core.models.parser_config.config import (
            AggregateField,
        )

        config = ParserConfig(
            downstream=_table_section(
                "/status.html",
                columns=[
                    {"index": 0, "field": "channel_id", "type": "integer"},
                    {"index": 1, "field": "corrected", "type": "integer"},
                ],
            ),
            aggregate={
                "total_corrected": AggregateField(sum="corrected", channels="downstream"),
            },
        )
        resources = _build_resources(
            {
                "/status.html": _make_table_html("Downstream", [["1", "100"], ["2", "200"]]),
            }
        )
        coordinator = ModemParserCoordinator(config)
        result = coordinator.parse(resources)

        assert result["system_info"]["total_corrected"] == 300

    def test_aggregate_native_wins(self) -> None:
        """Native system_info value takes precedence over aggregate."""
        from solentlabs.cable_modem_monitor_core.models.parser_config.config import (
            AggregateField,
        )

        config = ParserConfig(
            downstream=_table_section(
                "/status.html",
                columns=[
                    {"index": 0, "field": "channel_id", "type": "integer"},
                    {"index": 1, "field": "corrected", "type": "integer"},
                ],
            ),
            system_info=_sysinfo_section(
                "/info.html",
                [
                    {"label": "Total Corrected", "field": "total_corrected", "type": "integer"},
                ],
            ),
            aggregate={
                "total_corrected": AggregateField(sum="corrected", channels="downstream"),
            },
        )
        resources = _build_resources(
            {
                "/status.html": _make_table_html("Downstream", [["1", "100"], ["2", "200"]]),
                "/info.html": _make_field_html({"Total Corrected": "999"}),
            }
        )
        coordinator = ModemParserCoordinator(config)
        result = coordinator.parse(resources)

        # Native value ("999") wins over computed (300)
        # html_fields returns raw string; the precedence rule still applies
        assert result["system_info"]["total_corrected"] == "999"

    def test_aggregate_type_qualified_scope(self) -> None:
        """Type-qualified scope filters channels by channel_type."""
        from solentlabs.cable_modem_monitor_core.models.parser_config.config import (
            AggregateField,
        )

        config = ParserConfig(
            downstream=_table_section(
                "/status.html",
                columns=[
                    {"index": 0, "field": "channel_id", "type": "integer"},
                    {"index": 1, "field": "corrected", "type": "integer"},
                ],
                channel_type="qam",
            ),
            aggregate={
                "total_corrected": AggregateField(sum="corrected", channels="downstream.qam"),
            },
        )
        resources = _build_resources(
            {
                "/status.html": _make_table_html("Downstream", [["1", "100"], ["2", "200"]]),
            }
        )
        coordinator = ModemParserCoordinator(config)
        result = coordinator.parse(resources)

        assert result["system_info"]["total_corrected"] == 300

    def test_aggregate_missing_field_skipped(self) -> None:
        """Aggregate for a field not present on channels is not added."""
        from solentlabs.cable_modem_monitor_core.models.parser_config.config import (
            AggregateField,
        )

        config = ParserConfig(
            downstream=_table_section("/status.html"),
            aggregate={
                "total_corrected": AggregateField(sum="corrected", channels="downstream"),
            },
        )
        resources = _build_resources(
            {
                "/status.html": _make_table_html("Downstream", [["1", "507"], ["2", "513"]]),
            }
        )
        coordinator = ModemParserCoordinator(config)
        result = coordinator.parse(resources)

        # Channels don't have "corrected" field → no aggregate
        assert "total_corrected" not in result["system_info"]

    def test_no_aggregate_config(self) -> None:
        """No aggregate section → only channel counts in system_info."""
        config = ParserConfig(
            downstream=_table_section("/status.html"),
        )
        resources = _build_resources(
            {
                "/status.html": _make_table_html("Downstream", [["1", "507"]]),
            }
        )
        coordinator = ModemParserCoordinator(config)
        result = coordinator.parse(resources)

        assert result["system_info"]["downstream_channel_count"] == 1
        assert result["system_info"]["upstream_channel_count"] == 0
        # No aggregate fields
        assert len(result["system_info"]) == 2


# ---------------------------------------------------------------------------
# Test helpers for enrichment tests
# ---------------------------------------------------------------------------


def _table_section(
    resource: str,
    columns: list[dict[str, Any]] | None = None,
    channel_type: str | None = None,
) -> Any:
    """Build a minimal table section config dict."""
    if columns is None:
        columns = [
            {"index": 0, "field": "channel_id", "type": "integer"},
            {"index": 1, "field": "frequency", "type": "integer"},
        ]
    table: dict[str, Any] = {
        "selector": {"type": "header_text", "match": "Downstream"},
        "columns": columns,
    }
    if channel_type:
        table["channel_type"] = {"fixed": channel_type}
    return {
        "format": "table",
        "resource": resource,
        "tables": [table],
    }


def _sysinfo_section(resource: str, fields: list[dict[str, Any]]) -> Any:
    """Build a minimal html_fields system_info section config dict."""
    return {
        "sources": [
            {
                "format": "html_fields",
                "resource": resource,
                "fields": fields,
            }
        ],
    }


def _make_table_html(header: str, rows: list[list[str]]) -> str:
    """Build minimal HTML with a header and data rows."""
    row_html = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return (
        f"<table><tr><th colspan='99'>{header}</th></tr>" f"<tr><th>Col A</th><th>Col B</th></tr>" f"{row_html}</table>"
    )


def _make_field_html(fields: dict[str, str]) -> str:
    """Build minimal HTML with label/value table for html_fields parser."""
    rows = "".join(f"<tr><td>{label}</td><td>{value}</td></tr>" for label, value in fields.items())
    return f"<table>{rows}</table>"
