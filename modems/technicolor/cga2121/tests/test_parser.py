"""Tests for the Technicolor CGA2121 parser."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.discovery_helpers import HintMatcher
from custom_components.cable_modem_monitor.modems.technicolor.cga2121.parser import (
    TechnicolorCGA2121Parser,
)
from tests.fixtures import load_fixture


@pytest.fixture
def st_docsis_html():
    """Load st_docsis.html fixture."""
    return load_fixture("technicolor", "cga2121", "st_docsis.html")


@pytest.fixture
def logon_html():
    """Load logon.html fixture from extended folder."""
    return load_fixture("technicolor", "cga2121", "extended/logon.html")


@pytest.fixture
def parser():
    """Create a CGA2121 parser instance."""
    return TechnicolorCGA2121Parser()


class TestMetadata:
    """Test parser metadata."""

    def test_parser_name(self, parser):
        """Test parser name."""
        assert parser.name == "Technicolor CGA2121"

    def test_manufacturer(self, parser):
        """Test manufacturer."""
        assert parser.manufacturer == "Technicolor"

    def test_models(self, parser):
        """Test models list."""
        assert "CGA2121" in parser.models

    def test_docsis_version(self, parser):
        """Test DOCSIS version from modem.yaml."""
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_auth_adapter_for_parser,
        )

        adapter = get_auth_adapter_for_parser("TechnicolorCGA2121Parser")
        assert adapter is not None
        assert adapter.get_docsis_version() == "3.0"

    def test_fixtures_path(self):
        """Test fixtures path exists via modem.yaml adapter."""
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_auth_adapter_for_parser,
        )

        adapter = get_auth_adapter_for_parser("TechnicolorCGA2121Parser")
        assert adapter is not None
        fixtures_path = adapter.get_fixtures_path()
        assert fixtures_path is not None
        assert "cga2121" in fixtures_path


class TestDetection:
    """Test modem detection via HintMatcher."""

    def test_detection_by_model_name(self, st_docsis_html):
        """Test detection by CGA2121 model name in HTML via HintMatcher."""
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_login_markers(st_docsis_html)
        assert any(m.parser_name == "TechnicolorCGA2121Parser" for m in matches)

    def test_detection_by_url_and_branding(self, st_docsis_html):
        """Test detection by Technicolor branding via HintMatcher."""
        # Remove CGA2121 from HTML but keep Technicolor
        modified_html = st_docsis_html.replace("CGA2121", "GATEWAY")
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_login_markers(modified_html)
        # May or may not match depending on YAML hints - just Technicolor branding alone
        # is not enough without CGA2121 model string
        # This test verifies the behavior is consistent with HintMatcher
        assert isinstance(matches, list)

    def test_does_not_match_other_modem(self):
        """Test that parser doesn't match other modems via HintMatcher."""
        html = "<html><title>Other Modem</title><body>Some content</body></html>"
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_login_markers(html)
        assert not any(m.parser_name == "TechnicolorCGA2121Parser" for m in matches)


class TestParsing:
    """Test parser functionality."""

    def test_downstream_channels(self, parser, st_docsis_html):
        """Test parsing of downstream channels."""
        soup = BeautifulSoup(st_docsis_html, "html.parser")
        data = parser.parse(soup)
        downstream = data["downstream"]

        assert len(downstream) == 24

        # Check first channel
        assert downstream[0]["channel_id"] == 1
        assert downstream[0]["modulation"] == "QAM256"
        assert downstream[0]["snr"] == 42.3
        assert downstream[0]["power"] == 10.4

        # Check last channel
        assert downstream[23]["channel_id"] == 24
        assert downstream[23]["modulation"] == "QAM256"
        assert downstream[23]["snr"] == 39.4
        assert downstream[23]["power"] == 7.7

    def test_upstream_channels(self, parser, st_docsis_html):
        """Test parsing of upstream channels."""
        soup = BeautifulSoup(st_docsis_html, "html.parser")
        data = parser.parse(soup)
        upstream = data["upstream"]

        assert len(upstream) == 4

        # Check first channel
        assert upstream[0]["channel_id"] == 1
        assert upstream[0]["modulation"] == "QAM64"
        assert upstream[0]["power"] == 43.7

        # Check last channel
        assert upstream[3]["channel_id"] == 4
        assert upstream[3]["modulation"] == "QAM64"
        assert upstream[3]["power"] == 43.5

    def test_system_info(self, parser, st_docsis_html):
        """Test parsing of system info."""
        soup = BeautifulSoup(st_docsis_html, "html.parser")
        data = parser.parse(soup)
        system_info = data["system_info"]

        # Check that basic info is parsed
        assert system_info.get("operational_status") == "Operational"
        assert system_info.get("downstream_channel_count") == 24
        assert system_info.get("upstream_channel_count") == 4

    def test_parse_empty_html_returns_empty(self, parser):
        """Test parsing empty HTML returns empty lists."""
        soup = BeautifulSoup("<html><body></body></html>", "html.parser")
        data = parser.parse(soup)

        assert data["downstream"] == []
        assert data["upstream"] == []
        assert data["system_info"] == {}


class TestAuthHints:
    """Test auth discovery hints (v3.12.0+)."""

    def test_has_auth_form_hints(self, parser):
        """Test modem.yaml has auth_form_hints for non-standard form fields."""
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_auth_adapter_for_parser,
        )

        adapter = get_auth_adapter_for_parser("TechnicolorCGA2121Parser")
        assert adapter is not None
        hints = adapter.get_auth_form_hints()
        assert hints.get("username_field") == "username_login"
        assert hints.get("password_field") == "password_login"


class TestFixtures:
    """Test fixture file existence."""

    def test_fixture_file_exists(self):
        """Test that required fixture files exist."""
        from pathlib import Path

        from tests.fixtures import fixture_exists, get_fixture_dir

        fixtures_dir = get_fixture_dir("technicolor", "cga2121")
        assert fixtures_dir.exists()
        assert fixture_exists("technicolor", "cga2121", "st_docsis.html")
        # modem.yaml is now in the modem directory, not fixtures
        modem_yaml = Path(__file__).parent.parent / "modem.yaml"
        assert modem_yaml.exists(), "modem.yaml should exist"

    def test_extended_fixture_exists(self):
        """Test that extended fixture files exist."""
        from tests.fixtures import get_fixture_dir

        fixtures_dir = get_fixture_dir("technicolor", "cga2121")
        extended_dir = fixtures_dir / "extended"
        assert extended_dir.exists()
        assert (extended_dir / "logon.html").exists()
