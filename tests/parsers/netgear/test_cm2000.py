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

import os

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.parsers.netgear.cm2000 import NetgearCM2000Parser


@pytest.fixture
def cm2000_index_html():
    """Load CM2000 index.htm fixture (login page)."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "cm2000", "index.htm")
    with open(fixture_path) as f:
        return f.read()


@pytest.fixture
def cm2000_docsis_status_html():
    """Load CM2000 DocsisStatus.htm fixture.

    Returns None if fixture doesn't exist yet (awaiting user submission).
    """
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "cm2000", "DocsisStatus.htm")
    if os.path.exists(fixture_path):
        with open(fixture_path) as f:
            return f.read()
    return None


class TestCM2000Detection:
    """Tests for CM2000 modem detection."""

    def test_can_parse_from_title(self, cm2000_index_html):
        """Test detection via page title."""
        soup = BeautifulSoup(cm2000_index_html, "html.parser")
        assert NetgearCM2000Parser.can_parse(soup, "http://192.168.100.1/", cm2000_index_html)

    def test_can_parse_from_meta_description(self, cm2000_index_html):
        """Test detection via meta description."""
        soup = BeautifulSoup(cm2000_index_html, "html.parser")
        # The meta description should contain CM2000
        meta = soup.find("meta", attrs={"name": "description"})
        assert meta is not None
        assert "CM2000" in meta.get("content", "")

    def test_does_not_match_cm600(self):
        """Test that CM2000 parser doesn't match CM600 HTML."""
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
        soup = BeautifulSoup(cm600_html, "html.parser")
        assert not NetgearCM2000Parser.can_parse(soup, "http://192.168.100.1/", cm600_html)

    def test_does_not_match_c3700(self):
        """Test that CM2000 parser doesn't match C3700 HTML."""
        c3700_html = """
        <html>
        <head>
        <title>NETGEAR Gateway C3700-100NAS</title>
        <META name="description" content="C3700-100NAS">
        </head>
        <body></body>
        </html>
        """
        soup = BeautifulSoup(c3700_html, "html.parser")
        assert not NetgearCM2000Parser.can_parse(soup, "http://192.168.100.1/", c3700_html)


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
        """Test parser verified status - pending user confirmation of v3.8.1 fixes."""
        from custom_components.cable_modem_monitor.parsers.base_parser import ParserStatus

        # Issue #38: awaiting confirmation of software version and restart
        assert NetgearCM2000Parser.status == ParserStatus.AWAITING_VERIFICATION
        # Also test the verified property via an instance
        parser = NetgearCM2000Parser()
        assert parser.verified is False

    def test_auth_config(self):
        """Test authentication configuration is set correctly."""
        from custom_components.cable_modem_monitor.core.authentication import AuthStrategyType

        assert NetgearCM2000Parser.auth_config.strategy == AuthStrategyType.FORM_PLAIN
        assert NetgearCM2000Parser.auth_config.login_url == "/goform/Login"
        assert NetgearCM2000Parser.auth_config.username_field == "loginName"
        assert NetgearCM2000Parser.auth_config.password_field == "loginPassword"


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
        not os.path.exists(os.path.join(os.path.dirname(__file__), "fixtures", "cm2000", "DocsisStatus.htm")),
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


class TestCM2000Login:
    """Tests for CM2000 login functionality."""

    def test_login_extracts_dynamic_form_id(self, requests_mock, cm2000_index_html):
        """Test that login extracts the dynamic form ID from login page."""
        import re

        parser = NetgearCM2000Parser()
        import requests

        session = requests.Session()
        session.verify = False
        base_url = "https://192.168.100.1"

        # Mock the login page with dynamic form ID
        requests_mock.get(f"{base_url}/", text=cm2000_index_html)

        # Mock the login POST using a regex pattern to match any /goform/Login URL
        requests_mock.register_uri(
            "POST",
            re.compile(r".*/goform/Login.*"),
            text="<html><body>Logged in</body></html>",
        )

        # Mock DocsisStatus.htm with channel data to verify success
        docsis_html = """
        <html><script>
        function InitDsTableTagValue() { var tagValueList = '1|1|Locked|QAM256|1|500000000 Hz|5.0|40.0|0|0|'; }
        function InitUsTableTagValue() { var tagValueList = '1|1|Locked|ATDMA|1|5120 Ksym/sec|20000000 Hz|38.0 dBmV|'; }
        </script></html>
        """
        requests_mock.get(f"{base_url}/DocsisStatus.htm", text=docsis_html)

        success, html = parser.login(session, base_url, "admin", "password123")

        assert success is True
        # Verify the login POST was made (check request history)
        assert any("/goform/Login" in str(req.url) for req in requests_mock.request_history if req.method == "POST")

    def test_login_fails_when_redirected_to_login(self, requests_mock, cm2000_index_html):
        """Test that login fails if DocsisStatus.htm redirects to login page."""
        import re

        parser = NetgearCM2000Parser()
        import requests

        session = requests.Session()
        session.verify = False
        base_url = "https://192.168.100.1"

        # Mock the login page
        requests_mock.get(f"{base_url}/", text=cm2000_index_html)
        requests_mock.register_uri(
            "POST",
            re.compile(r".*/goform/Login.*"),
            text="<html><body>Logged in</body></html>",
        )

        # Mock DocsisStatus.htm returning login redirect (auth failed)
        login_redirect_html = """
        <html><script>
        function redirect(){top.location.href="/Login.htm";}
        </script><body onLoad="redirect()"></body></html>
        """
        requests_mock.get(f"{base_url}/DocsisStatus.htm", text=login_redirect_html)

        success, html = parser.login(session, base_url, "admin", "wrongpassword")

        assert success is False

    def test_login_skipped_without_credentials(self):
        """Test that login is skipped when no credentials provided."""
        parser = NetgearCM2000Parser()
        import requests

        session = requests.Session()
        base_url = "https://192.168.100.1"

        # Should return (True, None) when no credentials
        success, html = parser.login(session, base_url, None, None)
        assert success is True

        success, html = parser.login(session, base_url, "", "")
        assert success is True


class TestCM2000Fixtures:
    """Tests for CM2000 fixture availability."""

    def test_index_fixture_exists(self):
        """Verify index.htm fixture is present."""
        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "cm2000", "index.htm")
        assert os.path.exists(fixture_path), "index.htm fixture should exist"

    def test_readme_exists(self):
        """Verify README.md is present in fixtures directory."""
        readme_path = os.path.join(os.path.dirname(__file__), "fixtures", "cm2000", "README.md")
        assert os.path.exists(readme_path), "README.md should exist"

    def test_docsis_status_fixture_exists(self):
        """Verify DocsisStatus.htm fixture is present."""
        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "cm2000", "DocsisStatus.htm")
        assert os.path.exists(fixture_path), "DocsisStatus.htm fixture should exist"

    def test_router_status_fixture_exists(self):
        """Verify RouterStatus.htm fixture is present (for restart)."""
        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "cm2000", "RouterStatus.htm")
        assert os.path.exists(fixture_path), "RouterStatus.htm fixture should exist"


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


class TestCM2000Restart:
    """Tests for CM2000 restart functionality."""

    def test_restart_capability_declared(self):
        """Test that RESTART capability is declared."""
        from custom_components.cable_modem_monitor.parsers.base_parser import ModemCapability

        assert ModemCapability.RESTART in NetgearCM2000Parser.capabilities

    def test_restart_extracts_form_action(self, requests_mock):
        """Test that restart extracts dynamic form action from RouterStatus.htm."""
        import re

        parser = NetgearCM2000Parser()
        import requests

        session = requests.Session()
        session.verify = False
        base_url = "https://192.168.100.1"

        # Load actual RouterStatus.htm fixture
        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "cm2000", "RouterStatus.htm")
        with open(fixture_path) as f:
            router_status_html = f.read()

        # Mock RouterStatus.htm
        requests_mock.get(f"{base_url}/RouterStatus.htm", text=router_status_html)

        # Mock the goform POST endpoint
        requests_mock.register_uri(
            "POST",
            re.compile(r".*/goform/RouterStatus.*"),
            text="<html><body>Rebooting...</body></html>",
        )

        result = parser.restart(session, base_url)

        assert result is True
        # Verify POST was made with buttonSelect=2
        post_requests = [r for r in requests_mock.request_history if r.method == "POST"]
        assert len(post_requests) == 1
        assert "buttonSelect=2" in post_requests[0].text


class TestCM2000OFDMParsing:
    """Tests for OFDM/OFDMA channel parsing (DOCSIS 3.1)."""

    def test_ofdm_capability_declared(self):
        """Test that OFDM capabilities are declared."""
        from custom_components.cable_modem_monitor.parsers.base_parser import ModemCapability

        assert ModemCapability.OFDM_DOWNSTREAM in NetgearCM2000Parser.capabilities
        assert ModemCapability.OFDM_UPSTREAM in NetgearCM2000Parser.capabilities

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
