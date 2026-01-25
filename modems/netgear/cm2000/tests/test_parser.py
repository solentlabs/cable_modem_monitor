"""Tests for the Netgear CM2000 (Nighthawk) parser.

Parser Status: ✅ Verified by @m4dh4tt3r-88
- 31 downstream QAM + OFDM channels
- 4 upstream ATDMA channels + OFDMA support
- Software version from index.htm
- Restart via RouterStatus.htm

Fixtures available:
- index.htm: Login page with firmware version
- DocsisStatus.htm: DOCSIS channel data (31 DS + 4 US channels, 1 OFDM DS, 2 OFDMA US)
- RouterStatus.htm: Restart endpoint

Related: Issue #38 (Netgear CM2000 Support Request)
Contributor: @m4dh4tt3r-88
"""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.discovery_helpers import HintMatcher
from custom_components.cable_modem_monitor.modems.netgear.cm2000.parser import NetgearCM2000Parser
from tests.fixtures import fixture_exists, load_fixture


@pytest.fixture
def cm2000_index_html():
    """Load CM2000 index.htm fixture (login page)."""
    return load_fixture("netgear", "cm2000", "index.htm")


@pytest.fixture
def cm2000_docsis_status_html():
    """Load CM2000 DocsisStatus.htm fixture.

    Returns None if fixture doesn't exist yet (awaiting user submission).
    """
    try:
        return load_fixture("netgear", "cm2000", "DocsisStatus.htm")
    except FileNotFoundError:
        return None


class TestCM2000Detection:
    """Tests for CM2000 modem detection."""

    def test_detection_from_title(self, cm2000_index_html):
        """Test detection via page title using HintMatcher."""
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_login_markers(cm2000_index_html)
        assert any(m.parser_name == "NetgearCM2000Parser" for m in matches)

    def test_detection_from_meta_description(self, cm2000_index_html):
        """Test detection via meta description."""
        soup = BeautifulSoup(cm2000_index_html, "html.parser")
        # The meta description should contain CM2000
        meta = soup.find("meta", attrs={"name": "description"})
        assert meta is not None
        assert "CM2000" in meta.get("content", "")

    def test_does_not_match_cm600(self):
        """Test that CM2000 parser doesn't match CM600 HTML via HintMatcher.

        Uses match_model_strings (Phase 2) for model-specific discrimination.
        """
        # Use CM600 style HTML
        cm600_html = """
        <html>
        <head>
        <title>NETGEAR Gateway CM600</title>
        <META name="description" content="CM600">
        </head>
        <body></body>
        </html>
        """
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_model_strings(cm600_html)
        assert not any(m.parser_name == "NetgearCM2000Parser" for m in matches)

    def test_does_not_match_c3700(self):
        """Test that CM2000 parser doesn't match C3700 HTML via HintMatcher.

        Uses match_model_strings (Phase 2) for model-specific discrimination.
        """
        c3700_html = """
        <html>
        <head>
        <title>NETGEAR Gateway C3700-100NAS</title>
        <META name="description" content="C3700-100NAS">
        </head>
        <body></body>
        </html>
        """
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_model_strings(c3700_html)
        assert not any(m.parser_name == "NetgearCM2000Parser" for m in matches)


class TestCM2000Metadata:
    """Tests for CM2000 parser metadata."""

    def test_parser_name(self):
        """Test parser name is set correctly."""
        assert NetgearCM2000Parser.name == "Netgear CM2000"

    def test_parser_manufacturer(self):
        """Test manufacturer is set correctly."""
        assert NetgearCM2000Parser.manufacturer == "Netgear"

    def test_parser_models(self):
        """Test models list is set correctly."""
        assert "CM2000" in NetgearCM2000Parser.models

    def test_parser_verified_status(self):
        """Test parser verified status - confirmed working in v3.8.1."""
        # Status now read from modem.yaml via adapter
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_auth_adapter_for_parser,
        )

        # Issue #38: confirmed working by user
        adapter = get_auth_adapter_for_parser("NetgearCM2000Parser")
        assert adapter is not None
        assert adapter.get_status() == "verified"

    def test_has_auth_form_hints(self):
        """Test modem.yaml has auth_form_hints for non-standard form fields (v3.12.0+)."""
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_auth_adapter_for_parser,
        )

        adapter = get_auth_adapter_for_parser("NetgearCM2000Parser")
        assert adapter is not None
        hints = adapter.get_auth_form_hints()
        assert hints.get("username_field") == "loginName"
        assert hints.get("password_field") == "loginPassword"

    def test_uses_form_dynamic_auth_type(self):
        """Test CM2000 uses form_dynamic auth for dynamic login URL extraction.

        Issue #38: CM2000 login form has a dynamic action URL that changes per
        page load (e.g., /goform/Login?id=XXXXXXXXXX). The form_dynamic strategy
        fetches the login page first and extracts the actual action URL.
        """
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_auth_adapter_for_parser,
        )

        adapter = get_auth_adapter_for_parser("NetgearCM2000Parser")
        assert adapter is not None

        # Verify form_dynamic is the auth type
        auth_types = adapter.get_available_auth_types()
        assert "form_dynamic" in auth_types

        # Get the form_dynamic config
        config = adapter.get_auth_config_for_type("form_dynamic")
        assert config is not None

        # form_dynamic-specific fields
        assert config.get("login_page") == "/"
        assert config.get("form_selector") == "form[name='loginform']"

        # Standard form fields (inherited from FormAuthConfig)
        assert config.get("username_field") == "loginName"
        assert config.get("password_field") == "loginPassword"
        assert config.get("action") == "/goform/Login"


class TestCM2000Parsing:
    """Tests for CM2000 channel parsing.

    These tests will be expanded once DocsisStatus.htm fixture is available.
    """

    def test_parse_empty_page_returns_empty_channels(self):
        """Test parsing empty/login page returns empty channel lists."""
        parser = NetgearCM2000Parser()
        empty_html = "<html><body></body></html>"
        soup = BeautifulSoup(empty_html, "html.parser")

        result = parser.parse(soup)

        assert result["downstream"] == []
        assert result["upstream"] == []
        assert isinstance(result["system_info"], dict)

    def test_parse_login_page_returns_empty_channels(self, cm2000_index_html):
        """Test parsing login page returns empty channel lists."""
        parser = NetgearCM2000Parser()
        soup = BeautifulSoup(cm2000_index_html, "html.parser")

        result = parser.parse(soup)

        # Login page shouldn't have channel data
        assert result["downstream"] == []
        assert result["upstream"] == []

    @pytest.mark.skipif(
        not fixture_exists("netgear", "cm2000", "DocsisStatus.htm"),
        reason="DocsisStatus.htm fixture not yet available - awaiting user submission",
    )
    def test_parse_docsis_status(self, cm2000_docsis_status_html):
        """Test parsing actual DOCSIS status page.

        This test will be enabled once we receive the authenticated
        DocsisStatus.htm from the user.
        """
        parser = NetgearCM2000Parser()
        soup = BeautifulSoup(cm2000_docsis_status_html, "html.parser")

        result = parser.parse(soup)

        # Once we have the fixture, we can add specific assertions
        # For now, just verify the structure
        assert "downstream" in result
        assert "upstream" in result
        assert "system_info" in result

        # Add specific assertions based on actual fixture data
        # downstream = result["downstream"]
        # assert len(downstream) > 0
        # assert all("channel_id" in ch for ch in downstream)
        # assert all("frequency" in ch for ch in downstream)


class TestCM2000Fixtures:
    """Tests for CM2000 fixture availability."""

    def test_index_fixture_exists(self):
        """Verify index.htm fixture is present."""
        assert fixture_exists("netgear", "cm2000", "index.htm"), "index.htm fixture should exist"

    def test_docsis_status_fixture_exists(self):
        """Verify DocsisStatus.htm fixture is present."""
        assert fixture_exists("netgear", "cm2000", "DocsisStatus.htm"), "DocsisStatus.htm fixture should exist"

    def test_router_status_fixture_exists(self):
        """Verify RouterStatus.htm fixture is present (for restart)."""
        assert fixture_exists("netgear", "cm2000", "RouterStatus.htm"), "RouterStatus.htm fixture should exist"


class TestCM2000SoftwareVersion:
    """Tests for software version extraction from index.htm."""

    def test_parse_software_version_from_index(self, cm2000_index_html):
        """Test that software version is extracted from index.htm InitTagValue."""
        parser = NetgearCM2000Parser()
        soup = BeautifulSoup(cm2000_index_html, "html.parser")

        version = parser._parse_software_version_from_index(soup)

        # index.htm contains: var tagValueList = 'V8.01.02|0|0|0|0|retail|...'
        assert version == "V8.01.02"

    def test_parse_software_version_empty_page(self):
        """Test parsing empty page returns None."""
        parser = NetgearCM2000Parser()
        soup = BeautifulSoup("<html><body></body></html>", "html.parser")

        version = parser._parse_software_version_from_index(soup)

        assert version is None


# Note: TestCM2000Restart class removed - restart functionality moved to action layer
# See tests/core/actions/test_html.py for HTML restart action tests


class TestCM2000OFDMParsing:
    """Tests for OFDM/OFDMA channel parsing (DOCSIS 3.1)."""

    def test_ofdm_capability_declared(self):
        """Test that OFDM capabilities are declared."""
        from custom_components.cable_modem_monitor.core.base_parser import ModemCapability

        assert ModemCapability.OFDM_DOWNSTREAM in NetgearCM2000Parser.capabilities
        assert ModemCapability.OFDMA_UPSTREAM in NetgearCM2000Parser.capabilities

    def test_parse_ofdm_downstream_from_fixture(self, cm2000_docsis_status_html):
        """Test parsing OFDM downstream channels from fixture.

        The fixture contains:
        InitDsOfdmTableTagValue with 2 channels, 1 locked at 762MHz
        """
        if cm2000_docsis_status_html is None:
            pytest.skip("DocsisStatus.htm fixture not available")

        parser = NetgearCM2000Parser()
        soup = BeautifulSoup(cm2000_docsis_status_html, "html.parser")

        # Test the OFDM parsing directly
        ofdm_channels = parser._parse_ofdm_downstream(soup)

        # Fixture has 1 locked OFDM channel (channel 33 at 762MHz)
        assert len(ofdm_channels) == 1
        channel = ofdm_channels[0]
        assert channel["frequency"] == 762000000
        assert channel["modulation"] == "OFDM"
        assert channel["is_ofdm"] is True
        assert channel["channel_id"] == "33"
        assert channel["power"] == 11.18
        assert channel["snr"] == 40.8

    def test_parse_ofdma_upstream_from_fixture(self, cm2000_docsis_status_html):
        """Test parsing OFDMA upstream channels from fixture.

        The fixture contains:
        InitUsOfdmaTableTagValue with 2 channels, both Not Locked
        """
        if cm2000_docsis_status_html is None:
            pytest.skip("DocsisStatus.htm fixture not available")

        parser = NetgearCM2000Parser()
        soup = BeautifulSoup(cm2000_docsis_status_html, "html.parser")

        # Test the OFDMA parsing directly
        ofdma_channels = parser._parse_ofdma_upstream(soup)

        # Fixture has 0 locked OFDMA channels (both are "Not Locked")
        assert len(ofdma_channels) == 0

    def test_full_parse_includes_ofdm(self, cm2000_docsis_status_html):
        """Test that full parse() includes OFDM channels in results."""
        if cm2000_docsis_status_html is None:
            pytest.skip("DocsisStatus.htm fixture not available")

        parser = NetgearCM2000Parser()
        soup = BeautifulSoup(cm2000_docsis_status_html, "html.parser")

        result = parser.parse(soup)

        # Should have 31 QAM + 1 OFDM = 32 downstream channels
        downstream = result["downstream"]
        assert len(downstream) == 32

        # Find the OFDM channel
        ofdm_channels = [ch for ch in downstream if ch.get("is_ofdm") is True]
        assert len(ofdm_channels) == 1
        assert ofdm_channels[0]["modulation"] == "OFDM"

    def test_extract_tagvaluelist_helper(self, cm2000_docsis_status_html):
        """Test the _extract_tagvaluelist helper function."""
        if cm2000_docsis_status_html is None:
            pytest.skip("DocsisStatus.htm fixture not available")

        parser = NetgearCM2000Parser()
        soup = BeautifulSoup(cm2000_docsis_status_html, "html.parser")

        # Test extracting OFDM downstream tagValueList
        values = parser._extract_tagvaluelist(soup, "InitDsOfdmTableTagValue")
        assert values is not None
        assert values[0] == "2"  # Channel count

        # Test extracting OFDMA upstream tagValueList
        values = parser._extract_tagvaluelist(soup, "InitUsOfdmaTableTagValue")
        assert values is not None
        assert values[0] == "2"  # Channel count

        # Test non-existent function returns None
        values = parser._extract_tagvaluelist(soup, "NonExistentFunction")
        assert values is None
