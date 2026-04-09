"""Tests for JSVarsParser — system_info from JS variable assignments."""

from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup
from solentlabs.cable_modem_monitor_core.models.parser_config.system_info import (
    JSVarsFieldMapping,
    JSVarsSystemInfoSource,
)
from solentlabs.cable_modem_monitor_core.parsers.formats.js_vars import JSVarsParser


def _make_source(
    resource: str = "/status.html",
    fields: list[dict[str, Any]] | None = None,
) -> JSVarsSystemInfoSource:
    """Build a minimal JSVarsSystemInfoSource config."""
    if fields is None:
        fields = [
            {"source": "js_FWVersion", "field": "software_version", "type": "string"},
            {"source": "js_HWType", "field": "hardware_version", "type": "string"},
        ]
    return JSVarsSystemInfoSource(
        format="javascript_vars",
        resource=resource,
        fields=[JSVarsFieldMapping(**f) for f in fields],
    )


def _make_soup(html: str) -> BeautifulSoup:
    """Build a BeautifulSoup from HTML string."""
    return BeautifulSoup(html, "html.parser")


class TestBasicExtraction:
    """Test basic field extraction from JS variable assignments."""

    def test_extracts_var_assignments(self) -> None:
        """Extract values from var x = 'value' assignments."""
        source = _make_source()
        parser = JSVarsParser(source)
        html = "<html><script>var js_FWVersion = '1.2.3'; var js_HWType = 'Rev-A';</script></html>"
        resources = {"/status.html": _make_soup(html)}

        result = parser.parse(resources)

        assert result == {
            "software_version": "1.2.3",
            "hardware_version": "Rev-A",
        }

    def test_extracts_without_var_keyword(self) -> None:
        """Extract values from x = 'value' (no var keyword)."""
        source = _make_source()
        parser = JSVarsParser(source)
        html = "<html><script>js_FWVersion = '4.5.6';</script></html>"
        resources = {"/status.html": _make_soup(html)}

        result = parser.parse(resources)

        assert result == {"software_version": "4.5.6"}

    def test_skips_unmapped_variables(self) -> None:
        """Variables not in the field list are ignored."""
        source = _make_source()
        parser = JSVarsParser(source)
        html = "<html><script>var js_FWVersion = '1.0'; var js_Other = 'ignored';</script></html>"
        resources = {"/status.html": _make_soup(html)}

        result = parser.parse(resources)

        assert result == {"software_version": "1.0"}


class TestMapApplied:
    """Test that map entries on fields normalize values."""

    def test_map_normalizes_value(self) -> None:
        """Map on a field definition transforms the extracted value."""
        source = _make_source(
            fields=[
                {
                    "source": "js_isCmOperational",
                    "field": "docsis_status",
                    "type": "string",
                    "map": {"online": "Operational"},
                },
            ],
        )
        parser = JSVarsParser(source)
        html = "<html><script>var js_isCmOperational = 'online';</script></html>"
        resources = {"/status.html": _make_soup(html)}

        result = parser.parse(resources)

        assert result == {"docsis_status": "Operational"}

    def test_unmapped_value_passes_through(self) -> None:
        """Values not in the map pass through unchanged."""
        source = _make_source(
            fields=[
                {
                    "source": "js_isCmOperational",
                    "field": "docsis_status",
                    "type": "string",
                    "map": {"online": "Operational"},
                },
            ],
        )
        parser = JSVarsParser(source)
        html = "<html><script>var js_isCmOperational = 'offline';</script></html>"
        resources = {"/status.html": _make_soup(html)}

        result = parser.parse(resources)

        assert result == {"docsis_status": "offline"}


class TestMissingData:
    """Test handling of missing resources."""

    def test_missing_resource(self) -> None:
        """Missing resource returns empty dict."""
        source = _make_source()
        parser = JSVarsParser(source)

        assert parser.parse({}) == {}

    def test_no_scripts(self) -> None:
        """Page with no script tags returns empty dict."""
        source = _make_source()
        parser = JSVarsParser(source)
        resources = {"/status.html": _make_soup("<html><body>No scripts</body></html>")}

        assert parser.parse(resources) == {}
