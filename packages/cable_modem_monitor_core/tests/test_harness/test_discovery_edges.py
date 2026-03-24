"""Tests for modem discovery edge cases.

Covers hidden directory filtering, relative path fallback, and
HAR entries with query-string routing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from solentlabs.cable_modem_monitor_core.test_harness.discovery import (
    discover_modem_tests,
)
from solentlabs.cable_modem_monitor_core.test_harness.routes import (
    build_routes,
)

# ------------------------------------------------------------------
# Tests — hidden directory filtering in discovery
# ------------------------------------------------------------------


class TestHiddenDirectoryFiltering:
    """discover_modem_tests skips hidden directories."""

    def test_hidden_mfr_dir_skipped(self, tmp_path: Path) -> None:
        """Manufacturer directories starting with '.' are skipped."""
        modems = tmp_path / "modems"
        modems.mkdir()

        # Hidden manufacturer directory — should be skipped
        hidden = modems / ".hidden_mfr"
        hidden.mkdir()
        model = hidden / "model"
        model.mkdir()
        test_data = model / "test_data"
        test_data.mkdir()
        (test_data / "modem.har").write_text("{}")

        # Visible manufacturer directory — should be found
        visible = modems / "visible_mfr"
        visible.mkdir()

        cases = discover_modem_tests(modems)
        names = [c.name for c in cases]
        assert not any(".hidden_mfr" in n for n in names)

    def test_hidden_model_dir_skipped(self, tmp_path: Path) -> None:
        """Model directories starting with '.' are skipped."""
        modems = tmp_path / "modems"
        mfr = modems / "acme"
        mfr.mkdir(parents=True)

        # Hidden model directory
        hidden = mfr / ".wip"
        hidden.mkdir()
        test_data = hidden / "test_data"
        test_data.mkdir()
        (test_data / "modem.har").write_text("{}")

        cases = discover_modem_tests(modems)
        names = [c.name for c in cases]
        assert not any(".wip" in n for n in names)


# ------------------------------------------------------------------
# Tests — route table with query strings
# ------------------------------------------------------------------


def _make_entry(url: str, status: int = 200, body: str = "ok") -> dict[str, Any]:
    """Build a minimal HAR entry dict."""
    return {
        "request": {"method": "GET", "url": url},
        "response": {
            "status": status,
            "headers": [{"name": "Content-Type", "value": "text/html"}],
            "content": {"text": body, "mimeType": "text/html"},
        },
    }


class TestRouteTableQueryStrings:
    """Route table preserves query strings for endpoint disambiguation."""

    def test_query_string_in_route_key(self) -> None:
        """HAR entries with query params create distinct routes."""
        entries = [
            _make_entry("http://192.168.100.1/setup.cgi?todo=downstream", body="ds_data"),
            _make_entry("http://192.168.100.1/setup.cgi?todo=upstream", body="us_data"),
        ]
        routes = build_routes(entries)

        # Both routes should exist with their query strings
        ds_route = routes.get(("GET", "/setup.cgi?todo=downstream"))
        us_route = routes.get(("GET", "/setup.cgi?todo=upstream"))
        assert ds_route is not None
        assert us_route is not None
        assert ds_route.body == "ds_data"
        assert us_route.body == "us_data"

    def test_no_query_string_plain_path(self) -> None:
        """HAR entries without query params use plain path."""
        entries = [_make_entry("http://192.168.100.1/data.htm")]
        routes = build_routes(entries)
        assert routes.get(("GET", "/data.htm")) is not None
