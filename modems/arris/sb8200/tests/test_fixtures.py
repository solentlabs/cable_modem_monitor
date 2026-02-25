"""Fixture validation tests for SB8200.

Validates that committed fixture files are correct and that parser
configuration matches actual modem behavior observed in HAR captures.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.discovery_helpers import HintMatcher


def _load_html_fixture(path: Path) -> str | None:
    """Load an HTML fixture file."""
    if not path.exists():
        return None
    for encoding in ("utf-8", "iso-8859-1", "cp1252"):
        try:
            with open(path, encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    return None


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


class TestSB8200FixtureValidation:
    """Validate SB8200 URL token auth pattern using fixtures."""

    def test_login_page_exists(self):
        """Verify login page fixture is available."""
        login_page = FIXTURES_DIR / "extended/login_page.html"
        assert login_page.exists(), "login_page.html fixture missing"

    def test_login_page_has_javascript_auth(self):
        """Verify login page contains JavaScript-based auth pattern."""
        html = _load_html_fixture(FIXTURES_DIR / "extended/login_page.html")
        if not html:
            pytest.skip("Login page fixture not available")

        # SB8200 uses JavaScript for URL token auth
        assert "login_" in html.lower() or "credential" in html.lower(), "Login page should reference URL token auth"

    def test_parser_js_auth_hints_complete(self):
        """Verify modem.yaml has complete js_auth_hints."""
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_auth_adapter_for_parser,
        )

        adapter = get_auth_adapter_for_parser("ArrisSB8200Parser")
        assert adapter is not None, "Should have modem.yaml config"
        hints = adapter.get_js_auth_hints()
        assert hints is not None, "Should have js_auth_hints in modem.yaml"

        required_keys = [
            "pattern",
            "login_page",
            "login_prefix",
            "session_cookie_name",
            "data_page",
            "token_prefix",
        ]
        for key in required_keys:
            assert key in hints, f"Missing {key} in js_auth_hints"

        assert hints["pattern"] == "url_token_session"
        assert hints["login_prefix"] == "login_"
        assert hints["token_prefix"] == "ct_"

    def test_data_page_can_be_parsed(self):
        """Verify parser can parse data page from fixture using HintMatcher."""
        html = _load_html_fixture(FIXTURES_DIR / "cmconnectionstatus.html")
        if not html:
            pytest.skip("Data page fixture not available")

        from modems.arris.sb8200.parser import (
            ArrisSB8200Parser,
        )

        soup = BeautifulSoup(html, "html.parser")
        parser = ArrisSB8200Parser()

        # Should detect as SB8200 via HintMatcher
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_login_markers(html)
        assert any(m.parser_name == "ArrisSB8200Parser" for m in matches)

        # Should parse channel data
        result = parser.parse(soup)
        assert "downstream" in result
        assert len(result["downstream"]) > 0
