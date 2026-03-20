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
    _merge_channels,
    _stub_js_embedded,
    _stub_js_sysinfo,
    _stub_json,
    _stub_json_sysinfo,
    _stub_transposed,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "coordinator"
VALID_FIXTURES = sorted((FIXTURES_DIR / "valid").glob("*.json"))


def _build_resources(html_map: dict[str, str]) -> dict[str, BeautifulSoup]:
    """Build resource dict from a mapping of path -> HTML string."""
    return {path: BeautifulSoup(html, "html.parser") for path, html in html_map.items()}


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
    resources = _build_resources(data["_html"])
    config = ParserConfig(**data["_parser_config"])
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
        config = ParserConfig(**ds_fixture["_parser_config"])
        coordinator = ModemParserCoordinator(config, _MockPostProcessor())
        result = coordinator.parse(resources)

        assert result["downstream"][0]["custom_field"] == "enriched"
        assert result["downstream"][0]["frequency"] == 507000000

    def test_hook_replaces_output(self, ds_fixture: dict[str, Any]) -> None:
        """Hook can fully replace BaseParser extraction output."""
        resources = _build_resources(ds_fixture["_html"])
        config = ParserConfig(**ds_fixture["_parser_config"])
        coordinator = ModemParserCoordinator(config, _ReplacingPostProcessor())
        result = coordinator.parse(resources)

        assert result["downstream"] == [{"channel_id": 99, "channel_type": "qam", "custom": True}]

    def test_no_hook_for_section(self) -> None:
        """Section without a hook uses BaseParser output as-is."""
        data = _load_fixture("downstream_upstream.json")
        resources = _build_resources(data["_html"])
        config = ParserConfig(**data["_parser_config"])
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
        config = ParserConfig(**data["_parser_config"])
        coordinator = ModemParserCoordinator(config, _MockPostProcessor())
        result = coordinator.parse(resources)

        assert result["system_info"] == {"custom_key": "custom_value"}

    def test_no_post_processor(self, ds_fixture: dict[str, Any]) -> None:
        """Coordinator with no post-processor uses BaseParser output."""
        resources = _build_resources(ds_fixture["_html"])
        config = ParserConfig(**ds_fixture["_parser_config"])
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
        config = ParserConfig(**data["_parser_config"])
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
        assert result["system_info"] == {
            "software_version": "AB01.02.053",
            "system_uptime": "7 days 00:00:01",
        }

    def test_hook_on_empty_section(self) -> None:
        """Hook is still invoked when config has no mapping for a section."""
        data = _load_fixture("minimal_downstream.json")
        config = ParserConfig(**data["_parser_config"])
        coordinator = ModemParserCoordinator(config, _MockPostProcessor())
        result = coordinator.parse({})

        assert result["downstream"] == []
        # parse_system_info hook is called with empty dict — returns custom data
        assert result["system_info"] == {"custom_key": "custom_value"}


# ---------------------------------------------------------------------------
# Registry stub tests — NotImplementedError for unimplemented formats
# ---------------------------------------------------------------------------

# ┌──────────────────────────┬──────────────────────────────────────┐
# │ stub function            │ expected error fragment              │
# ├──────────────────────────┼──────────────────────────────────────┤
# │ _stub_transposed         │ "HTMLTableTransposedParser"          │
# │ _stub_js_embedded        │ "JSEmbeddedParser"                  │
# │ _stub_json               │ "JSONParser"                        │
# │ _stub_js_sysinfo         │ "JSSystemInfoParser"                │
# │ _stub_json_sysinfo       │ "JSONSystemInfoParser"              │
# └──────────────────────────┴──────────────────────────────────────┘

# fmt: off
CHANNEL_STUB_CASES = [
    ("transposed",   _stub_transposed,  "HTMLTableTransposedParser"),
    ("js_embedded",  _stub_js_embedded, "JSEmbeddedParser"),
    ("json",         _stub_json,        "JSONParser"),
]
# fmt: on


@pytest.mark.parametrize(
    "desc,stub_fn,expected_msg",
    CHANNEL_STUB_CASES,
    ids=[c[0] for c in CHANNEL_STUB_CASES],
)
def test_channel_stub_raises(
    desc: str,
    stub_fn: Any,
    expected_msg: str,
) -> None:
    """Channel parser stub raises NotImplementedError with parser name."""
    with pytest.raises(NotImplementedError, match=expected_msg):
        stub_fn(None, {})


# fmt: off
SYSINFO_STUB_CASES = [
    ("js_sysinfo",   _stub_js_sysinfo,   "JSSystemInfoParser"),
    ("json_sysinfo", _stub_json_sysinfo,  "JSONSystemInfoParser"),
]
# fmt: on


@pytest.mark.parametrize(
    "desc,stub_fn,expected_msg",
    SYSINFO_STUB_CASES,
    ids=[c[0] for c in SYSINFO_STUB_CASES],
)
def test_sysinfo_stub_raises(
    desc: str,
    stub_fn: Any,
    expected_msg: str,
) -> None:
    """System info parser stub raises NotImplementedError with parser name."""
    with pytest.raises(NotImplementedError, match=expected_msg):
        stub_fn(None, {})
