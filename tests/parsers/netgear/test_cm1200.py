"""Tests for the Netgear CM1200 parser.

Parser Status: Awaiting user verification
- 31 QAM downstream + 1 OFDM downstream = 32 total downstream channels
- 2 ATDMA upstream + 1 OFDMA upstream = 3 total upstream channels
- HTTP Basic authentication
- System uptime and current time

Fixtures available:
- DocsisStatus.htm: DOCSIS channel data (32 DS + 3 US locked)

Related: Issue #63 (Netgear CM1200 Support Request)
Contributor: @DeFlanko
"""

from __future__ import annotations

import os

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.parsers.netgear.cm1200 import NetgearCM1200Parser


@pytest.fixture
def cm1200_docsis_status_html():
    """Load CM1200 DocsisStatus.htm fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "cm1200", "DocsisStatus.htm")
    with open(fixture_path) as f:
        return f.read()


class TestCM1200Detection:
    """Tests for CM1200 modem detection."""

    def test_can_parse_from_title(self, cm1200_docsis_status_html):
        """Test detection via page title."""
        soup = BeautifulSoup(cm1200_docsis_status_html, "html.parser")
        assert NetgearCM1200Parser.can_parse(soup, "http://192.168.100.1/DocsisStatus.htm", cm1200_docsis_status_html)

    def test_can_parse_from_meta_description(self, cm1200_docsis_status_html):
        """Test detection via meta description."""
        soup = BeautifulSoup(cm1200_docsis_status_html, "html.parser")
        meta = soup.find("meta", attrs={"name": "description"})
        assert meta is not None
        assert "CM1200" in meta.get("content", "")

    def test_does_not_match_cm2000(self):
        """Test that CM1200 parser doesn't match CM2000 HTML."""
        cm2000_html = """
        <html>
        <head>
        <title>NETGEAR Modem CM2000</title>
        <META name="description" content="CM2000">
        </head>
        <body></body>
        </html>
        """
        soup = BeautifulSoup(cm2000_html, "html.parser")
        assert not NetgearCM1200Parser.can_parse(soup, "http://192.168.100.1/", cm2000_html)

    def test_does_not_match_cm600(self):
        """Test that CM1200 parser doesn't match CM600 HTML."""
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
        assert not NetgearCM1200Parser.can_parse(soup, "http://192.168.100.1/", cm600_html)


class TestCM1200Metadata:
    """Tests for CM1200 parser metadata."""

    def test_parser_name(self):
        """Test parser name is set correctly."""
        assert NetgearCM1200Parser.name == "Netgear CM1200"

    def test_parser_manufacturer(self):
        """Test manufacturer is set correctly."""
        assert NetgearCM1200Parser.manufacturer == "Netgear"

    def test_parser_models(self):
        """Test models list is set correctly."""
        assert "CM1200" in NetgearCM1200Parser.models

    def test_parser_awaiting_verification_status(self):
        """Test parser is awaiting verification."""
        from custom_components.cable_modem_monitor.parsers.base_parser import ParserStatus

        assert NetgearCM1200Parser.status == ParserStatus.AWAITING_VERIFICATION
        parser = NetgearCM1200Parser()
        assert parser.verified is False

    def test_auth_config(self):
        """Test authentication configuration is set correctly."""
        from custom_components.cable_modem_monitor.core.auth_config import AuthStrategyType

        assert NetgearCM1200Parser.auth_config.strategy == AuthStrategyType.BASIC_HTTP


class TestCM1200Parsing:
    """Tests for CM1200 channel parsing."""

    def test_parse_empty_page_returns_empty_channels(self):
        """Test parsing empty page returns empty channel lists."""
        parser = NetgearCM1200Parser()
        empty_html = "<html><body></body></html>"
        soup = BeautifulSoup(empty_html, "html.parser")

        result = parser.parse(soup)

        assert result["downstream"] == []
        assert result["upstream"] == []
        assert isinstance(result["system_info"], dict)

    def test_parse_docsis_status(self, cm1200_docsis_status_html):
        """Test parsing actual DOCSIS status page."""
        parser = NetgearCM1200Parser()
        soup = BeautifulSoup(cm1200_docsis_status_html, "html.parser")

        result = parser.parse(soup)

        # Verify structure
        assert "downstream" in result
        assert "upstream" in result
        assert "system_info" in result

        # Verify downstream channels (31 QAM locked + 1 OFDM locked = 32 total)
        downstream = result["downstream"]
        assert len(downstream) == 32, f"Expected 32 downstream channels, got {len(downstream)}"

        # Verify downstream channel structure (common fields)
        for ch in downstream:
            assert "channel_id" in ch
            assert "frequency" in ch
            assert "power" in ch
            assert "snr" in ch
            assert "modulation" in ch
            # corrected/uncorrected only present on QAM channels
            if not ch.get("is_ofdm"):
                assert "corrected" in ch
                assert "uncorrected" in ch

        # Verify specific QAM downstream values (from fixture)
        first_ds = downstream[0]
        assert first_ds["frequency"] == 765000000
        assert first_ds["modulation"] == "QAM256"
        assert first_ds["channel_id"] == "32"

        # Verify OFDM channel exists
        ofdm_channels = [ch for ch in downstream if ch.get("is_ofdm")]
        assert len(ofdm_channels) == 1
        assert ofdm_channels[0]["modulation"] == "OFDM"

    def test_parse_upstream(self, cm1200_docsis_status_html):
        """Test parsing upstream channels."""
        parser = NetgearCM1200Parser()
        soup = BeautifulSoup(cm1200_docsis_status_html, "html.parser")

        result = parser.parse(soup)

        # Verify upstream channels (2 ATDMA locked + 1 OFDMA locked = 3 total)
        upstream = result["upstream"]
        assert len(upstream) == 3, f"Expected 3 upstream channels, got {len(upstream)}"

        # Verify upstream channel structure (common fields)
        for ch in upstream:
            assert "channel_id" in ch
            assert "frequency" in ch
            assert "power" in ch
            assert "channel_type" in ch
            # symbol_rate only present on ATDMA channels
            if not ch.get("is_ofdm"):
                assert "symbol_rate" in ch

        # Verify specific ATDMA upstream values (from fixture)
        first_us = upstream[0]
        assert first_us["frequency"] == 13200000
        assert first_us["channel_type"] == "ATDMA"
        assert first_us["symbol_rate"] == 5120

        # Verify OFDMA channel exists
        ofdma_channels = [ch for ch in upstream if ch.get("is_ofdm")]
        assert len(ofdma_channels) == 1
        assert ofdma_channels[0]["channel_type"] == "OFDMA"

    def test_parse_system_info(self, cm1200_docsis_status_html):
        """Test parsing system info."""
        parser = NetgearCM1200Parser()
        soup = BeautifulSoup(cm1200_docsis_status_html, "html.parser")

        result = parser.parse(soup)

        system_info = result["system_info"]
        assert "current_time" in system_info
        assert "system_uptime" in system_info
        assert "last_boot_time" in system_info

        # Verify values from fixture
        assert "Sun Dec 14" in system_info["current_time"]
        assert "39 days" in system_info["system_uptime"]


class TestCM1200Fixtures:
    """Tests for CM1200 fixture availability."""

    def test_docsis_status_fixture_exists(self):
        """Verify DocsisStatus.htm fixture is present."""
        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "cm1200", "DocsisStatus.htm")
        assert os.path.exists(fixture_path), "DocsisStatus.htm fixture should exist"

    def test_readme_exists(self):
        """Verify README.md is present in fixtures directory."""
        readme_path = os.path.join(os.path.dirname(__file__), "fixtures", "cm1200", "README.md")
        assert os.path.exists(readme_path), "README.md should exist"

    def test_metadata_exists(self):
        """Verify metadata.yaml is present in fixtures directory."""
        metadata_path = os.path.join(os.path.dirname(__file__), "fixtures", "cm1200", "metadata.yaml")
        assert os.path.exists(metadata_path), "metadata.yaml should exist"


class TestCM1200Login:
    """Tests for CM1200 login/authentication."""

    def test_login_no_credentials_returns_success(self):
        """Test login returns success when no credentials provided."""
        parser = NetgearCM1200Parser()

        # Mock session (not used when no credentials)
        class MockSession:
            pass

        result = parser.login(MockSession(), "http://192.168.100.1", "", "")
        assert result == (True, None)

    def test_login_no_username_returns_success(self):
        """Test login returns success when username is empty."""
        parser = NetgearCM1200Parser()

        class MockSession:
            pass

        result = parser.login(MockSession(), "http://192.168.100.1", "", "password")
        assert result == (True, None)

    def test_login_no_password_returns_success(self):
        """Test login returns success when password is empty."""
        parser = NetgearCM1200Parser()

        class MockSession:
            pass

        result = parser.login(MockSession(), "http://192.168.100.1", "admin", "")
        assert result == (True, None)

    def test_login_success_with_channel_data(self, cm1200_docsis_status_html):
        """Test successful login when channel data is returned."""
        parser = NetgearCM1200Parser()

        class MockResponse:
            status_code = 200
            text = cm1200_docsis_status_html

        class MockSession:
            auth = None

            def get(self, url, timeout=None):
                return MockResponse()

        session = MockSession()
        result = parser.login(session, "http://192.168.100.1", "admin", "password")

        assert result[0] is True
        assert result[1] == cm1200_docsis_status_html
        assert session.auth == ("admin", "password")

    def test_login_401_unauthorized(self):
        """Test login fails on 401 response."""
        parser = NetgearCM1200Parser()

        class MockResponse:
            status_code = 401
            text = "Unauthorized"

        class MockSession:
            auth = None

            def get(self, url, timeout=None):
                return MockResponse()

        session = MockSession()
        result = parser.login(session, "http://192.168.100.1", "admin", "wrongpassword")

        assert result == (False, None)

    def test_login_unexpected_status_code(self):
        """Test login fails on unexpected status code."""
        parser = NetgearCM1200Parser()

        class MockResponse:
            status_code = 500
            text = "Internal Server Error"

        class MockSession:
            auth = None

            def get(self, url, timeout=None):
                return MockResponse()

        result = parser.login(MockSession(), "http://192.168.100.1", "admin", "password")
        assert result == (False, None)

    def test_login_exception_handling(self):
        """Test login handles exceptions gracefully."""
        parser = NetgearCM1200Parser()

        class MockSession:
            auth = None

            def get(self, url, timeout=None):
                raise ConnectionError("Network unreachable")

        result = parser.login(MockSession(), "http://192.168.100.1", "admin", "password")
        assert result == (False, None)


class TestCM1200BootTimeCalculation:
    """Tests for boot time calculation from uptime string."""

    def test_calculate_boot_time_days_and_time(self):
        """Test boot time calculation with days and HH:MM:SS."""
        parser = NetgearCM1200Parser()
        result = parser._calculate_boot_time("39 days 15:47:33")

        assert result is not None
        # Result should be an ISO format datetime string
        assert "T" in result

    def test_calculate_boot_time_single_day(self):
        """Test boot time calculation with single day."""
        parser = NetgearCM1200Parser()
        result = parser._calculate_boot_time("1 day 02:30:00")

        assert result is not None
        assert "T" in result

    def test_calculate_boot_time_hours_only(self):
        """Test boot time calculation with only hours:minutes:seconds."""
        parser = NetgearCM1200Parser()
        result = parser._calculate_boot_time("12:30:45")

        assert result is not None
        assert "T" in result

    def test_calculate_boot_time_zero_returns_none(self):
        """Test boot time calculation returns None for zero uptime."""
        parser = NetgearCM1200Parser()
        result = parser._calculate_boot_time("invalid string with no time")

        assert result is None

    def test_calculate_boot_time_empty_string(self):
        """Test boot time calculation handles empty string."""
        parser = NetgearCM1200Parser()
        result = parser._calculate_boot_time("")

        assert result is None


class TestCM1200EdgeCases:
    """Tests for edge cases and error handling."""

    def test_parse_malformed_downstream_js(self):
        """Test parsing handles malformed downstream JavaScript."""
        parser = NetgearCM1200Parser()
        html = """
        <html>
        <head><title>NETGEAR Modem CM1200</title></head>
        <body>
        <script>
        function InitDsTableTagValue() {
            var tagValueList = 'not|enough|values';
            return tagValueList.split("|");
        }
        </script>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = parser.parse_downstream(soup)

        assert result == []

    def test_parse_malformed_upstream_js(self):
        """Test parsing handles malformed upstream JavaScript."""
        parser = NetgearCM1200Parser()
        html = """
        <html>
        <head><title>NETGEAR Modem CM1200</title></head>
        <body>
        <script>
        function InitUsTableTagValue() {
            var tagValueList = 'bad|data';
            return tagValueList.split("|");
        }
        </script>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = parser.parse_upstream(soup)

        assert result == []

    def test_parse_skips_unlocked_channels(self):
        """Test parsing skips channels that are not locked."""
        parser = NetgearCM1200Parser()
        html = """
        <html>
        <head><title>NETGEAR Modem CM1200</title></head>
        <body>
        <script>
        function InitDsTableTagValue() {
            var tagValueList = '2|1|Not Locked|QAM256|1|0 Hz|0|0|0|0|2|Locked|QAM256|2|579000000 Hz|8.7|44|100|50|';
            return tagValueList.split("|");
        }
        </script>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = parser.parse_downstream(soup)

        # Only the locked channel should be parsed
        assert len(result) == 1
        assert result[0]["frequency"] == 579000000

    def test_parse_with_session_fetches_docsis_status(self, cm1200_docsis_status_html):
        """Test parse() fetches DocsisStatus.htm when session provided."""
        parser = NetgearCM1200Parser()

        class MockResponse:
            status_code = 200
            text = cm1200_docsis_status_html

        class MockSession:
            def get(self, url, timeout=None):
                return MockResponse()

        # Start with empty soup
        empty_soup = BeautifulSoup("<html></html>", "html.parser")

        result = parser.parse(empty_soup, session=MockSession(), base_url="http://192.168.100.1")

        # Should have parsed channels from fetched page (31 QAM + 1 OFDM, 2 ATDMA + 1 OFDMA)
        assert len(result["downstream"]) == 32
        assert len(result["upstream"]) == 3

    def test_parse_with_session_handles_fetch_failure(self):
        """Test parse() handles DocsisStatus.htm fetch failure."""
        parser = NetgearCM1200Parser()

        class MockResponse:
            status_code = 404
            text = "Not Found"

        class MockSession:
            def get(self, url, timeout=None):
                return MockResponse()

        empty_soup = BeautifulSoup("<html></html>", "html.parser")
        result = parser.parse(empty_soup, session=MockSession(), base_url="http://192.168.100.1")

        # Should fall back to empty results from provided soup
        assert result["downstream"] == []
        assert result["upstream"] == []

    def test_parse_with_session_handles_exception(self):
        """Test parse() handles session exception gracefully."""
        parser = NetgearCM1200Parser()

        class MockSession:
            def get(self, url, timeout=None):
                raise ConnectionError("Network error")

        empty_soup = BeautifulSoup("<html></html>", "html.parser")
        result = parser.parse(empty_soup, session=MockSession(), base_url="http://192.168.100.1")

        # Should fall back to empty results
        assert result["downstream"] == []
        assert result["upstream"] == []

    def test_can_parse_returns_false_for_no_indicators(self):
        """Test can_parse returns False when no CM1200 indicators present."""
        html = "<html><head><title>Some Other Page</title></head></html>"
        soup = BeautifulSoup(html, "html.parser")

        assert NetgearCM1200Parser.can_parse(soup, "http://192.168.100.1/", html) is False

    def test_can_parse_meta_content_not_string(self):
        """Test can_parse handles meta content that is not a string."""
        html = """
        <html>
        <head>
        <title>Some Page</title>
        <meta name="description" content="">
        </head>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        # Manually set content to a list (edge case)
        meta = soup.find("meta", attrs={"name": "description"})
        meta["content"] = ["not", "a", "string"]

        assert NetgearCM1200Parser.can_parse(soup, "http://192.168.100.1/", html) is False


class TestCM1200Capabilities:
    """Tests for CM1200 declared capabilities."""

    def test_downstream_capability(self):
        """Test that DOWNSTREAM_CHANNELS capability is declared."""
        from custom_components.cable_modem_monitor.parsers.base_parser import ModemCapability

        assert ModemCapability.DOWNSTREAM_CHANNELS in NetgearCM1200Parser.capabilities

    def test_upstream_capability(self):
        """Test that UPSTREAM_CHANNELS capability is declared."""
        from custom_components.cable_modem_monitor.parsers.base_parser import ModemCapability

        assert ModemCapability.UPSTREAM_CHANNELS in NetgearCM1200Parser.capabilities

    def test_uptime_capability(self):
        """Test that SYSTEM_UPTIME capability is declared."""
        from custom_components.cable_modem_monitor.parsers.base_parser import ModemCapability

        assert ModemCapability.SYSTEM_UPTIME in NetgearCM1200Parser.capabilities

    def test_no_restart_capability(self):
        """Test that RESTART capability is NOT declared (not in capture)."""
        from custom_components.cable_modem_monitor.parsers.base_parser import ModemCapability

        assert ModemCapability.RESTART not in NetgearCM1200Parser.capabilities

    def test_ofdm_capability(self):
        """Test that OFDM capabilities are declared."""
        from custom_components.cable_modem_monitor.parsers.base_parser import ModemCapability

        assert ModemCapability.OFDM_DOWNSTREAM in NetgearCM1200Parser.capabilities
        assert ModemCapability.OFDM_UPSTREAM in NetgearCM1200Parser.capabilities
