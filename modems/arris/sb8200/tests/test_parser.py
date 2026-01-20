"""Tests for the ARRIS SB8200 parser."""

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.base_parser import ModemCapability
from custom_components.cable_modem_monitor.core.discovery_helpers import HintMatcher
from custom_components.cable_modem_monitor.modems.arris.sb8200.parser import ArrisSB8200Parser
from tests.fixtures import get_fixture_path, load_fixture


@pytest.fixture
def sb8200_html():
    """Load SB8200 HTML fixture (from Tim's fallback capture)."""
    return load_fixture("arris", "sb8200", "root.html")


@pytest.fixture
def sb8200_alt_html():
    """Load SB8200 alternative HTML fixture (original)."""
    # This fixture uses Windows-1252 encoding (copyright symbol)
    path = get_fixture_path("arris", "sb8200", "cmconnectionstatus.html")
    with open(path, encoding="cp1252") as f:
        return f.read()


@pytest.fixture
def sb8200_product_info_html():
    """Load SB8200 product info page (cmswinfo.html)."""
    return load_fixture("arris", "sb8200", "cmswinfo.html")


class TestSB8200ParserDetection:
    """Test parser detection logic."""

    def test_detection_with_model_span(self, sb8200_html):
        """Test detection via model number span using HintMatcher."""
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_login_markers(sb8200_html)
        assert any(m.parser_name == "ArrisSB8200Parser" for m in matches)

    def test_detection_alt_fixture(self, sb8200_alt_html):
        """Test detection on alternative fixture using HintMatcher."""
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_login_markers(sb8200_alt_html)
        assert any(m.parser_name == "ArrisSB8200Parser" for m in matches)

    def test_parser_metadata(self):
        """Test parser metadata is correct."""
        assert ArrisSB8200Parser.name == "ARRIS SB8200"
        assert ArrisSB8200Parser.manufacturer == "ARRIS"
        assert "SB8200" in ArrisSB8200Parser.models

        # Status and docsis_version now read from modem.yaml via adapter
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_auth_adapter_for_parser,
        )

        adapter = get_auth_adapter_for_parser("ArrisSB8200Parser")
        assert adapter is not None
        assert adapter.get_docsis_version() == "3.1"
        assert adapter.get_status() == "verified"  # Verified (Issue #42)


class TestSB8200ParserCapabilities:
    """Test parser capabilities declaration."""

    def test_has_downstream_capability(self):
        """Test downstream channels capability."""
        assert ArrisSB8200Parser.has_capability(ModemCapability.SCQAM_DOWNSTREAM)

    def test_has_upstream_capability(self):
        """Test upstream channels capability."""
        assert ArrisSB8200Parser.has_capability(ModemCapability.SCQAM_UPSTREAM)

    def test_has_ofdm_downstream_capability(self):
        """Test OFDM downstream capability (DOCSIS 3.1)."""
        assert ArrisSB8200Parser.has_capability(ModemCapability.OFDM_DOWNSTREAM)

    def test_has_ofdma_upstream_capability(self):
        """Test OFDMA upstream capability (DOCSIS 3.1)."""
        assert ArrisSB8200Parser.has_capability(ModemCapability.OFDMA_UPSTREAM)

    def test_no_restart_capability(self):
        """Test that restart is NOT supported."""
        assert not ArrisSB8200Parser.has_capability(ModemCapability.RESTART)

    def test_has_uptime_capability(self):
        """Test uptime capability (from cmswinfo.html)."""
        assert ArrisSB8200Parser.has_capability(ModemCapability.SYSTEM_UPTIME)

    def test_has_version_capabilities(self):
        """Test hardware/software version capabilities."""
        assert ArrisSB8200Parser.has_capability(ModemCapability.SOFTWARE_VERSION)
        assert ArrisSB8200Parser.has_capability(ModemCapability.HARDWARE_VERSION)


class TestSB8200DownstreamParsing:
    """Test downstream channel parsing."""

    def test_downstream_channel_count(self, sb8200_html):
        """Test correct number of downstream channels parsed."""
        parser = ArrisSB8200Parser()
        soup = BeautifulSoup(sb8200_html, "html.parser")
        data = parser.parse(soup)

        assert "downstream" in data
        # SB8200 has 32 downstream channels (31 QAM256 + 1 OFDM)
        assert len(data["downstream"]) == 32

    def test_first_downstream_channel(self, sb8200_html):
        """Test first downstream channel values."""
        parser = ArrisSB8200Parser()
        soup = BeautifulSoup(sb8200_html, "html.parser")
        data = parser.parse(soup)

        # First channel in Tim's capture is channel 19
        first_ds = data["downstream"][0]
        assert first_ds["channel_id"] == "19"
        assert first_ds["frequency"] == 435000000  # 435 MHz
        assert first_ds["modulation"] == "QAM256"
        assert first_ds["channel_type"] == "qam"  # Derived from modulation
        assert first_ds["power"] == 5.5
        assert first_ds["snr"] == 43.3
        assert first_ds["corrected"] == 158
        assert first_ds["uncorrected"] == 604

    def test_ofdm_downstream_channel(self, sb8200_html):
        """Test OFDM downstream channel (channel 33)."""
        parser = ArrisSB8200Parser()
        soup = BeautifulSoup(sb8200_html, "html.parser")
        data = parser.parse(soup)

        # Find the OFDM channel (modulation "Other")
        ofdm_channels = [ch for ch in data["downstream"] if ch.get("modulation") == "Other"]
        assert len(ofdm_channels) == 1

        ofdm = ofdm_channels[0]
        assert ofdm["channel_id"] == "33"
        assert ofdm["frequency"] == 524000000  # 524 MHz
        assert ofdm.get("is_ofdm") is True
        assert ofdm["channel_type"] == "ofdm"  # Derived from modulation="Other" (issue #87)
        assert ofdm["power"] == 6.3
        assert ofdm["snr"] == 41.8


class TestSB8200UpstreamParsing:
    """Test upstream channel parsing."""

    def test_upstream_channel_count(self, sb8200_html):
        """Test correct number of upstream channels parsed."""
        parser = ArrisSB8200Parser()
        soup = BeautifulSoup(sb8200_html, "html.parser")
        data = parser.parse(soup)

        assert "upstream" in data
        # SB8200 has 3 upstream channels (2 SC-QAM + 1 OFDM)
        assert len(data["upstream"]) == 3

    def test_first_upstream_channel(self, sb8200_html):
        """Test first upstream channel values."""
        parser = ArrisSB8200Parser()
        soup = BeautifulSoup(sb8200_html, "html.parser")
        data = parser.parse(soup)

        first_us = data["upstream"][0]
        assert first_us["channel_id"] == "4"
        assert first_us["channel_type"] == "SC-QAM Upstream"
        assert first_us["frequency"] == 37000000  # 37 MHz
        assert first_us["width"] == 6400000  # 6.4 MHz
        assert first_us["power"] == 42.0

    def test_ofdm_upstream_channel(self, sb8200_html):
        """Test OFDM upstream channel."""
        parser = ArrisSB8200Parser()
        soup = BeautifulSoup(sb8200_html, "html.parser")
        data = parser.parse(soup)

        # Find the OFDM upstream channel
        ofdm_channels = [ch for ch in data["upstream"] if "OFDM" in ch.get("channel_type", "")]
        assert len(ofdm_channels) == 1

        ofdm = ofdm_channels[0]
        assert ofdm["channel_id"] == "1"
        assert ofdm["channel_type"] == "OFDM Upstream"
        assert ofdm["frequency"] == 6025000  # 6.025 MHz
        assert ofdm["width"] == 17200000  # 17.2 MHz
        assert ofdm.get("is_ofdm") is True


class TestSB8200SystemInfo:
    """Test system info parsing."""

    def test_system_info_exists(self, sb8200_html):
        """Test that system_info is returned."""
        parser = ArrisSB8200Parser()
        soup = BeautifulSoup(sb8200_html, "html.parser")
        data = parser.parse(soup)

        assert "system_info" in data
        assert isinstance(data["system_info"], dict)

    def test_current_time_parsed(self, sb8200_html):
        """Test current time is parsed from systime element."""
        parser = ArrisSB8200Parser()
        soup = BeautifulSoup(sb8200_html, "html.parser")
        data = parser.parse(soup)

        # Check that current_time was parsed (may contain IPv6 placeholder)
        if "current_time" in data["system_info"]:
            assert "2025" in data["system_info"]["current_time"]


class TestSB8200AlternativeFixture:
    """Test parsing with alternative fixture."""

    def test_downstream_parsing_alt(self, sb8200_alt_html):
        """Test downstream parsing with alternative fixture."""
        parser = ArrisSB8200Parser()
        soup = BeautifulSoup(sb8200_alt_html, "html.parser")
        data = parser.parse(soup)

        assert "downstream" in data
        assert len(data["downstream"]) == 32

    def test_upstream_parsing_alt(self, sb8200_alt_html):
        """Test upstream parsing with alternative fixture."""
        parser = ArrisSB8200Parser()
        soup = BeautifulSoup(sb8200_alt_html, "html.parser")
        data = parser.parse(soup)

        assert "upstream" in data
        assert len(data["upstream"]) == 3


class TestSB8200ProductInfoParsing:
    """Test product info parsing from cmswinfo.html."""

    def test_parse_uptime(self, sb8200_product_info_html):
        """Test uptime parsing from product info page."""
        parser = ArrisSB8200Parser()
        soup = BeautifulSoup(sb8200_product_info_html, "html.parser")
        info = parser._parse_product_info(soup)

        assert "system_uptime" in info
        # Stored as raw string for display (matches other parsers)
        assert info["system_uptime"] == "8 days 01h:16m:13s.00"

    def test_parse_hardware_version(self, sb8200_product_info_html):
        """Test hardware version parsing."""
        parser = ArrisSB8200Parser()
        soup = BeautifulSoup(sb8200_product_info_html, "html.parser")
        info = parser._parse_product_info(soup)

        assert "hardware_version" in info
        assert info["hardware_version"] == "6"

    def test_parse_software_version(self, sb8200_product_info_html):
        """Test software version parsing."""
        parser = ArrisSB8200Parser()
        soup = BeautifulSoup(sb8200_product_info_html, "html.parser")
        info = parser._parse_product_info(soup)

        assert "software_version" in info
        assert "AB01.01.009" in info["software_version"]

    def test_parse_docsis_version(self, sb8200_product_info_html):
        """Test DOCSIS version parsing."""
        parser = ArrisSB8200Parser()
        soup = BeautifulSoup(sb8200_product_info_html, "html.parser")
        info = parser._parse_product_info(soup)

        assert "docsis_version" in info
        assert info["docsis_version"] == "Docsis 3.1"


class TestSB8200UptimeParsing:
    """Test uptime string parsing."""

    def test_parse_uptime_with_days(self):
        """Test parsing uptime with days."""
        parser = ArrisSB8200Parser()
        result = parser._parse_uptime("8 days 01h:16m:13s.00")
        assert result == 695773  # 8*86400 + 1*3600 + 16*60 + 13

    def test_parse_uptime_one_day(self):
        """Test parsing uptime with singular 'day'."""
        parser = ArrisSB8200Parser()
        result = parser._parse_uptime("1 day 00h:00m:00s.00")
        assert result == 86400

    def test_parse_uptime_no_days(self):
        """Test parsing uptime without days prefix."""
        parser = ArrisSB8200Parser()
        result = parser._parse_uptime("12h:30m:45s")
        assert result == 45045  # 12*3600 + 30*60 + 45

    def test_parse_uptime_invalid(self):
        """Test parsing invalid uptime returns None."""
        parser = ArrisSB8200Parser()
        result = parser._parse_uptime("invalid format")
        assert result is None

    def test_parse_uptime_empty(self):
        """Test parsing empty string returns None."""
        parser = ArrisSB8200Parser()
        result = parser._parse_uptime("")
        assert result is None


class TestSB8200AuthHints:
    """Test URL token session hints from modem.yaml (v3.12.0+)."""

    def test_js_auth_hints_pattern(self):
        """Test that modem.yaml specifies URL token session pattern."""
        from custom_components.cable_modem_monitor.modem_config.adapter import get_auth_adapter_for_parser

        adapter = get_auth_adapter_for_parser("ArrisSB8200Parser")
        assert adapter is not None
        hints = adapter.get_js_auth_hints()
        assert hints is not None
        assert hints["pattern"] == "url_token_session"

    def test_js_auth_hints_defaults(self):
        """Test modem.yaml has correct defaults for SB8200."""
        from custom_components.cable_modem_monitor.modem_config.adapter import get_auth_adapter_for_parser

        adapter = get_auth_adapter_for_parser("ArrisSB8200Parser")
        assert adapter is not None
        hints = adapter.get_js_auth_hints()
        assert hints is not None
        assert hints["login_page"] == "/cmconnectionstatus.html"
        assert hints["data_page"] == "/cmconnectionstatus.html"
        assert hints["login_prefix"] == "login_"
        assert hints["token_prefix"] == "ct_"
        assert hints["session_cookie_name"] == "sessionId"
        assert hints["success_indicator"] == "Downstream Bonded Channels"


class TestSB8200ParseResources:
    """Test new parse_resources() method (v3.12.0+ fetcher architecture)."""

    def test_parse_resources_with_main_and_info_pages(self, sb8200_html, sb8200_product_info_html):
        """Test parse_resources with both main and product info pages."""
        parser = ArrisSB8200Parser()

        # Build resources dict as fetcher would
        resources = {
            "/cmconnectionstatus.html": BeautifulSoup(sb8200_html, "html.parser"),
            "/cmswinfo.html": BeautifulSoup(sb8200_product_info_html, "html.parser"),
        }

        data = parser.parse_resources(resources)

        # Should have all data
        assert len(data["downstream"]) == 32
        assert len(data["upstream"]) == 3
        assert "system_uptime" in data["system_info"]
        assert "hardware_version" in data["system_info"]
        assert "software_version" in data["system_info"]

    def test_parse_resources_with_only_main_page(self, sb8200_html):
        """Test parse_resources with only main page (info page not fetched)."""
        parser = ArrisSB8200Parser()

        resources = {
            "/": BeautifulSoup(sb8200_html, "html.parser"),
        }

        data = parser.parse_resources(resources)

        # Should still have channel data
        assert len(data["downstream"]) == 32
        assert len(data["upstream"]) == 3
        # Product info should be absent
        assert "system_uptime" not in data["system_info"]

    def test_parse_resources_empty_resources(self):
        """Test parse_resources with empty resources dict."""
        parser = ArrisSB8200Parser()

        data = parser.parse_resources({})

        assert data["downstream"] == []
        assert data["upstream"] == []
        assert data["system_info"] == {}


class TestSB8200VariantTracking:
    """Test auth variant tracking for diagnostics."""

    def test_variant_constants_defined(self):
        """Test that all variant constants are defined."""
        assert ArrisSB8200Parser.VARIANT_HTTP_NO_AUTH == "http_no_auth"
        assert ArrisSB8200Parser.VARIANT_HTTPS_TOKEN_SESSION == "https_token_session"
        assert ArrisSB8200Parser.VARIANT_HTTPS_NO_AUTH_FALLBACK == "https_no_auth_fallback"


class TestSB8200AuthVariantInDiagnostics:
    """Test auth variant appears in parsed output."""

    def test_auth_variant_in_system_info(self, sb8200_html):
        """Test that auth variant is included in system_info."""
        parser = ArrisSB8200Parser()
        # Set variant as if login was called
        parser._auth_variant = ArrisSB8200Parser.VARIANT_HTTP_NO_AUTH

        soup = BeautifulSoup(sb8200_html, "html.parser")
        data = parser.parse(soup)

        assert "auth_variant" in data["system_info"]
        assert data["system_info"]["auth_variant"] == "http_no_auth"

    def test_no_auth_variant_when_not_set(self, sb8200_html):
        """Test that auth_variant is not in system_info if not set."""
        parser = ArrisSB8200Parser()
        # Don't set _auth_variant

        soup = BeautifulSoup(sb8200_html, "html.parser")
        data = parser.parse(soup)

        # Should not be present if not set
        assert parser._auth_variant is None
        assert "auth_variant" not in data["system_info"]


class TestSB8200LegacyParsePath:
    """Test legacy parse() path (deprecated, for backward compatibility)."""

    def test_parse_without_session_works(self, sb8200_html):
        """Test that parse() without session still works for basic parsing."""
        parser = ArrisSB8200Parser()
        soup = BeautifulSoup(sb8200_html, "html.parser")

        data = parser.parse(soup)

        # Should parse channel data from main page
        assert len(data["downstream"]) == 32
        assert len(data["upstream"]) == 3

    def test_parse_with_session_fetches_additional_pages(self, sb8200_html, sb8200_product_info_html):
        """Test that legacy parse() with session fetches cmswinfo.html."""
        from unittest.mock import MagicMock

        parser = ArrisSB8200Parser()
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = sb8200_product_info_html
        mock_session.get.return_value = mock_response

        soup = BeautifulSoup(sb8200_html, "html.parser")
        data = parser.parse(soup, session=mock_session, base_url="https://192.168.100.1")

        # Should have fetched cmswinfo.html
        mock_session.get.assert_called_once()
        # Should have product info
        assert "system_uptime" in data["system_info"]

    def test_parse_handles_fetch_failure(self, sb8200_html):
        """Test that parse() continues gracefully if cmswinfo.html fetch fails."""
        from unittest.mock import MagicMock

        parser = ArrisSB8200Parser()
        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Connection refused")

        soup = BeautifulSoup(sb8200_html, "html.parser")
        data = parser.parse(soup, session=mock_session, base_url="https://192.168.100.1")

        # Parse should still succeed with channel data
        assert len(data["downstream"]) == 32
        # Product info should be absent
        assert "system_uptime" not in data.get("system_info", {})


# Note: Integration tests for auth are in tests/integration/test_sb8200_auth.py
# Note: URL token handling is now done by HTMLFetcher (v3.12.0+)
# The parse() method no longer builds authenticated URLs directly - that's handled by the fetcher
