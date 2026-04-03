"""Tests for fetch list derivation from parser.yaml."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from solentlabs.cable_modem_monitor_core.loaders.fetch_list import (
    ResourceTarget,
    collect_fetch_targets,
)
from solentlabs.cable_modem_monitor_core.models.parser_config import ParserConfig

FIXTURES_DIR = Path(__file__).parent.parent / "models" / "fixtures" / "parser_config" / "valid"
LOCAL_FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestCollectFetchTargets:
    """Fetch list derivation from ParserConfig."""

    def test_table_single_resource(self) -> None:
        """Single table section produces one resource target."""
        data = json.loads((FIXTURES_DIR / "table_single.json").read_text())
        config = ParserConfig.model_validate(data)
        targets = collect_fetch_targets(config)

        assert len(targets) == 1
        assert targets[0].path == data["downstream"]["resource"]
        assert targets[0].format == "table"

    def test_downstream_and_upstream_same_resource(self) -> None:
        """Duplicate paths are deduplicated."""
        data = json.loads((FIXTURES_DIR / "upstream_table.json").read_text())
        config = ParserConfig.model_validate(data)
        targets = collect_fetch_targets(config)

        paths = [t.path for t in targets]
        # Should have unique paths only
        assert len(paths) == len(set(paths))

    def test_system_info_resources_collected(self) -> None:
        """System info sources add to the fetch list."""
        data = json.loads((FIXTURES_DIR / "system_info_html_fields.json").read_text())
        config = ParserConfig.model_validate(data)
        targets = collect_fetch_targets(config)

        formats = {t.format for t in targets}
        assert "html_fields" in formats

    def test_hnap_sections_skipped(self) -> None:
        """HNAP sections are excluded from HTTP fetch list."""
        data = json.loads((FIXTURES_DIR / "hnap_downstream.json").read_text())
        config = ParserConfig.model_validate(data)
        targets = collect_fetch_targets(config)

        # HNAP sections have no resource paths -- skip entirely
        assert len(targets) == 0

    def test_javascript_format(self) -> None:
        """JavaScript sections produce resource targets."""
        data = json.loads((FIXTURES_DIR / "javascript_single_function.json").read_text())
        config = ParserConfig.model_validate(data)
        targets = collect_fetch_targets(config)

        assert len(targets) >= 1
        formats = {t.format for t in targets}
        assert "javascript" in formats

    def test_json_format(self) -> None:
        """JSON sections produce resource targets."""
        data = json.loads((FIXTURES_DIR / "json_downstream.json").read_text())
        config = ParserConfig.model_validate(data)
        targets = collect_fetch_targets(config)

        assert len(targets) >= 1
        formats = {t.format for t in targets}
        assert "json" in formats

    def test_mixed_formats_deduplicated(self) -> None:
        """Multiple sections with same path keep first format."""
        data = json.loads((LOCAL_FIXTURES_DIR / "parser_config_shared_resource.json").read_text())
        config = ParserConfig.model_validate(data)
        targets = collect_fetch_targets(config)

        # Same resource path -- deduplicated to one target
        assert len(targets) == 1
        assert targets[0].path == "/status.html"
        assert targets[0].format == "table"

    def test_empty_config(self) -> None:
        """Config with no sections produces empty fetch list."""
        # system_info only, with HNAP source
        data = json.loads((FIXTURES_DIR / "system_info_hnap.json").read_text())
        config = ParserConfig.model_validate(data)
        targets = collect_fetch_targets(config)

        # HNAP system info has no resource path
        assert len(targets) == 0

    def test_xml_multi_table_resources(self) -> None:
        """XML tables[] produces one target per unique resource."""
        data = json.loads((FIXTURES_DIR / "xml_multi_table.json").read_text())
        config = ParserConfig.model_validate(data)
        targets = collect_fetch_targets(config)

        paths = sorted(t.path for t in targets)
        assert paths == ["10", "9"]
        assert all(t.format == "xml" for t in targets)

    def test_xml_single_table_resource(self) -> None:
        """XML section with one table produces one target."""
        data = json.loads((FIXTURES_DIR / "xml_downstream.json").read_text())
        config = ParserConfig.model_validate(data)
        targets = collect_fetch_targets(config)

        assert len(targets) == 1
        assert targets[0].path == "10"
        assert targets[0].format == "xml"

    def test_resource_target_is_frozen(self) -> None:
        """ResourceTarget is immutable."""
        target = ResourceTarget(path="/test.html", format="table")
        with pytest.raises(AttributeError):
            target.path = "/other.html"  # type: ignore[misc]
