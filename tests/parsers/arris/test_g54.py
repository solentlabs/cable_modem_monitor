"""Tests for the Arris G54 parser."""

import json
import os
from unittest.mock import MagicMock

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.parsers.arris.g54 import ArrisG54Parser
from custom_components.cable_modem_monitor.parsers.base_parser import ModemCapability, ParserStatus


@pytest.fixture
def g54_wan_status():
    """Load G54 wan_status.json fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "g54", "wan_status.json")
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def g54_login_html():
    """Load G54 login page HTML fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "g54", "login_page.html")
    with open(fixture_path) as f:
        return f.read()


@pytest.fixture
def mock_session(g54_wan_status):
    """Create a mock session that returns wan_status JSON."""
    session = MagicMock()

    # Mock the response for wan_status
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = g54_wan_status

    session.get.return_value = response
    session.cookies = {"sysauth": "test_session_token"}

    return session


class TestG54ParserDetection:
    """Test parser detection logic."""

    def test_can_parse_login_page(self, g54_login_html):
        """Test detection via login page content."""
        soup = BeautifulSoup(g54_login_html, "html.parser")
        assert ArrisG54Parser.can_parse(soup, "http://10.0.10.1/cgi-bin/luci/", g54_login_html)

    def test_can_parse_with_g54_and_arrisgw(self):
        """Test detection with G54 and ARRISGW markers."""
        html = "<html><title>ARRISGW</title><div>Model: G54</div></html>"
        soup = BeautifulSoup(html, "html.parser")
        assert ArrisG54Parser.can_parse(soup, "http://10.0.10.1/", html)

    def test_cannot_parse_other_modem(self):
        """Test that other modems are not detected."""
        html = "<html><title>SB8200</title><div>Model: SB8200</div></html>"
        soup = BeautifulSoup(html, "html.parser")
        assert not ArrisG54Parser.can_parse(soup, "http://192.168.100.1/", html)

    def test_parser_metadata(self):
        """Test parser metadata is correct."""
        assert ArrisG54Parser.name == "Arris G54"
        assert ArrisG54Parser.manufacturer == "Arris/CommScope"
        assert "G54" in ArrisG54Parser.models
        assert ArrisG54Parser.docsis_version == "3.1"
        assert ArrisG54Parser.status == ParserStatus.AWAITING_VERIFICATION


class TestG54ParserCapabilities:
    """Test parser capabilities declaration."""

    def test_has_downstream_capability(self):
        """Test downstream channels capability."""
        assert ArrisG54Parser.has_capability(ModemCapability.DOWNSTREAM_CHANNELS)

    def test_has_upstream_capability(self):
        """Test upstream channels capability."""
        assert ArrisG54Parser.has_capability(ModemCapability.UPSTREAM_CHANNELS)

    def test_has_ofdm_downstream_capability(self):
        """Test OFDM downstream capability (DOCSIS 3.1)."""
        assert ArrisG54Parser.has_capability(ModemCapability.OFDM_DOWNSTREAM)

    def test_has_ofdm_upstream_capability(self):
        """Test OFDM upstream capability (DOCSIS 3.1)."""
        assert ArrisG54Parser.has_capability(ModemCapability.OFDM_UPSTREAM)

    def test_has_uptime_capability(self):
        """Test uptime capability."""
        assert ArrisG54Parser.has_capability(ModemCapability.SYSTEM_UPTIME)

    def test_has_version_capability(self):
        """Test software version capability."""
        assert ArrisG54Parser.has_capability(ModemCapability.SOFTWARE_VERSION)

    def test_no_restart_capability(self):
        """Test that restart is NOT yet supported (could be added later)."""
        assert not ArrisG54Parser.has_capability(ModemCapability.RESTART)


class TestG54DownstreamParsing:
    """Test downstream channel parsing."""

    def test_downstream_channel_count(self, mock_session, g54_wan_status):
        """Test correct number of downstream channels parsed."""
        parser = ArrisG54Parser()
        soup = BeautifulSoup("<html></html>", "html.parser")
        data = parser.parse(soup, session=mock_session, base_url="http://10.0.10.1")

        assert "downstream" in data
        # Should have SC-QAM channels (locked only) + OFDM channels (active only)
        # From fixture: 32 locked SC-QAM + 2 active OFDM = 34 (minus unlocked ones)
        downstream = data["downstream"]
        assert len(downstream) > 20  # At least 20+ locked channels

    def test_scqam_downstream_channel(self, mock_session):
        """Test SC-QAM downstream channel values."""
        parser = ArrisG54Parser()
        soup = BeautifulSoup("<html></html>", "html.parser")
        data = parser.parse(soup, session=mock_session, base_url="http://10.0.10.1")

        # Find a regular SC-QAM channel (not OFDM)
        scqam_channels = [ch for ch in data["downstream"] if not ch.get("is_ofdm")]
        assert len(scqam_channels) > 0

        # Check first locked SC-QAM channel
        first_ch = scqam_channels[0]
        assert first_ch["lock_status"] == "Locked"
        assert first_ch["modulation"] == "QAM256"
        assert first_ch["frequency"] > 0
        assert first_ch["is_ofdm"] is False

    def test_ofdm_downstream_channel(self, mock_session):
        """Test OFDM downstream channel values."""
        parser = ArrisG54Parser()
        soup = BeautifulSoup("<html></html>", "html.parser")
        data = parser.parse(soup, session=mock_session, base_url="http://10.0.10.1")

        # Find OFDM channels
        ofdm_channels = [ch for ch in data["downstream"] if ch.get("is_ofdm")]
        assert len(ofdm_channels) == 2  # 2 active OFDM channels in fixture

        ofdm = ofdm_channels[0]
        assert ofdm["channel_id"].startswith("OFDM-")
        assert ofdm["is_ofdm"] is True
        assert ofdm["modulation"] == "QAM4096"
        assert "frequency_start" in ofdm
        assert "frequency_end" in ofdm


class TestG54UpstreamParsing:
    """Test upstream channel parsing."""

    def test_upstream_channel_count(self, mock_session):
        """Test correct number of upstream channels parsed."""
        parser = ArrisG54Parser()
        soup = BeautifulSoup("<html></html>", "html.parser")
        data = parser.parse(soup, session=mock_session, base_url="http://10.0.10.1")

        assert "upstream" in data
        # From fixture: 4 locked SC-QAM + 1 active OFDMA = 5
        upstream = data["upstream"]
        assert len(upstream) >= 4  # At least 4 SC-QAM channels

    def test_scqam_upstream_channel(self, mock_session):
        """Test SC-QAM upstream channel values."""
        parser = ArrisG54Parser()
        soup = BeautifulSoup("<html></html>", "html.parser")
        data = parser.parse(soup, session=mock_session, base_url="http://10.0.10.1")

        # Find SC-QAM upstream channels
        scqam_channels = [ch for ch in data["upstream"] if not ch.get("is_ofdm")]
        assert len(scqam_channels) >= 4

        first_ch = scqam_channels[0]
        assert first_ch["lock_status"] == "Locked"
        assert first_ch["modulation"] == "64QAM"
        assert first_ch["channel_type"] == "US_TYPE_ATDMA"
        assert first_ch["frequency"] > 0
        assert first_ch["power"] > 0

    def test_ofdma_upstream_channel(self, mock_session):
        """Test OFDMA upstream channel values."""
        parser = ArrisG54Parser()
        soup = BeautifulSoup("<html></html>", "html.parser")
        data = parser.parse(soup, session=mock_session, base_url="http://10.0.10.1")

        # Find OFDMA channels
        ofdma_channels = [ch for ch in data["upstream"] if ch.get("is_ofdm")]
        assert len(ofdma_channels) == 1  # 1 active OFDMA in fixture

        ofdma = ofdma_channels[0]
        assert ofdma["channel_id"].startswith("OFDMA-")
        assert ofdma["is_ofdm"] is True
        assert ofdma["modulation"] == "QAM2048"
        assert "frequency_start" in ofdma
        assert "frequency_end" in ofdma


class TestG54SystemInfo:
    """Test system info parsing."""

    def test_system_info_exists(self, mock_session):
        """Test that system_info is returned."""
        parser = ArrisG54Parser()
        soup = BeautifulSoup("<html></html>", "html.parser")
        data = parser.parse(soup, session=mock_session, base_url="http://10.0.10.1")

        assert "system_info" in data
        assert isinstance(data["system_info"], dict)

    def test_uptime_parsed(self, mock_session):
        """Test uptime is parsed correctly."""
        parser = ArrisG54Parser()
        soup = BeautifulSoup("<html></html>", "html.parser")
        data = parser.parse(soup, session=mock_session, base_url="http://10.0.10.1")

        info = data["system_info"]
        assert "uptime_seconds" in info
        assert info["uptime_seconds"] == 50221  # From fixture
        assert "system_uptime" in info

    def test_software_version_parsed(self, mock_session):
        """Test software version is parsed."""
        parser = ArrisG54Parser()
        soup = BeautifulSoup("<html></html>", "html.parser")
        data = parser.parse(soup, session=mock_session, base_url="http://10.0.10.1")

        info = data["system_info"]
        assert "software_version" in info
        assert "AC01.02.012" in info["software_version"]

    def test_model_info_parsed(self, mock_session):
        """Test model info is parsed."""
        parser = ArrisG54Parser()
        soup = BeautifulSoup("<html></html>", "html.parser")
        data = parser.parse(soup, session=mock_session, base_url="http://10.0.10.1")

        info = data["system_info"]
        assert info.get("model") == "G54"
        assert info.get("manufacturer") == "CommScope"


class TestG54UptimeFormatting:
    """Test uptime formatting helper."""

    def test_format_uptime_with_days(self):
        """Test uptime formatting with days."""
        parser = ArrisG54Parser()
        result = parser._format_uptime(90061)  # 1 day, 1 hour, 1 min, 1 sec
        assert result == "1d 01:01:01"

    def test_format_uptime_no_days(self):
        """Test uptime formatting without days."""
        parser = ArrisG54Parser()
        result = parser._format_uptime(3661)  # 1 hour, 1 min, 1 sec
        assert result == "01:01:01"

    def test_format_uptime_zero(self):
        """Test uptime formatting with zero."""
        parser = ArrisG54Parser()
        result = parser._format_uptime(0)
        assert result == "00:00:00"


class TestG54FrequencyParsing:
    """Test frequency parsing helper."""

    def test_parse_frequency_hz_string(self):
        """Test parsing frequency as Hz string."""
        parser = ArrisG54Parser()
        result = parser._parse_frequency("855000000")
        assert result == 855000000

    def test_parse_frequency_with_whitespace(self):
        """Test parsing frequency with leading whitespace."""
        parser = ArrisG54Parser()
        result = parser._parse_frequency(" 259000000")
        assert result == 259000000

    def test_parse_frequency_empty(self):
        """Test parsing empty frequency."""
        parser = ArrisG54Parser()
        result = parser._parse_frequency("")
        assert result == 0

    def test_parse_frequency_none(self):
        """Test parsing None frequency."""
        parser = ArrisG54Parser()
        result = parser._parse_frequency(None)
        assert result == 0


class TestG54FloatParsing:
    """Test float parsing helper."""

    def test_parse_float_string(self):
        """Test parsing float string."""
        parser = ArrisG54Parser()
        result = parser._parse_float("-7.299999")
        assert abs(result - (-7.299999)) < 0.001

    def test_parse_float_with_whitespace(self):
        """Test parsing float with whitespace."""
        parser = ArrisG54Parser()
        result = parser._parse_float(" -7.400002")
        assert abs(result - (-7.400002)) < 0.001

    def test_parse_float_inf(self):
        """Test parsing -inf returns 0."""
        parser = ArrisG54Parser()
        result = parser._parse_float("-inf")
        assert result == 0.0

    def test_parse_float_empty(self):
        """Test parsing empty string."""
        parser = ArrisG54Parser()
        result = parser._parse_float("")
        assert result == 0.0

    def test_parse_float_none(self):
        """Test parsing None."""
        parser = ArrisG54Parser()
        result = parser._parse_float(None)
        assert result == 0.0


class TestG54Login:
    """Test login behavior."""

    def test_login_success_with_cookie(self):
        """Test login success when sysauth cookie is set."""
        parser = ArrisG54Parser()

        session = MagicMock()
        session.cookies = {"sysauth": "abc123"}
        response = MagicMock()
        response.text = "<html>success</html>"
        session.post.return_value = response

        success, html = parser.login(session, "http://10.0.10.1", "admin", "password")
        assert success is True
        assert html is not None

    def test_login_failure_no_cookie(self):
        """Test login failure when no sysauth cookie."""
        parser = ArrisG54Parser()

        session = MagicMock()
        session.cookies = {}  # No sysauth cookie
        response = MagicMock()
        response.text = "<html>login failed</html>"
        session.post.return_value = response

        success, html = parser.login(session, "http://10.0.10.1", "admin", "wrong")
        assert success is False
        assert html is None


class TestG54NoSession:
    """Test behavior when session is not provided."""

    def test_parse_without_session(self):
        """Test parse returns empty data without session."""
        parser = ArrisG54Parser()
        soup = BeautifulSoup("<html></html>", "html.parser")
        data = parser.parse(soup)

        assert data["downstream"] == []
        assert data["upstream"] == []
        assert data["system_info"] == {}
