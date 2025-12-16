"""Tests for the Netgear C7000v2 parser.

NOTE: The C7000v2 (Nighthawk AC1900) is a combo modem/router using .htm extensions.

Model: C7000v2
Firmware: V1.03.08
Hardware: 2.01

Captured fixtures (from Issue #61 - @Anthranilic):
- index.htm, DocsisStatus.htm, RouterStatus.htm (core)
- DashBoard.htm, eventLog.htm, DocsisOffline.htm (extended)
"""

from __future__ import annotations

import os

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.parsers.netgear.c7000v2 import NetgearC7000v2Parser


@pytest.fixture
def c7000v2_index_html():
    """Load C7000v2 index.htm fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "c7000v2", "index.htm")
    with open(fixture_path) as f:
        return f.read()


@pytest.fixture
def c7000v2_docsis_status_html():
    """Load C7000v2 DocsisStatus.htm fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "c7000v2", "DocsisStatus.htm")
    with open(fixture_path) as f:
        return f.read()


@pytest.fixture
def c7000v2_router_status_html():
    """Load C7000v2 RouterStatus.htm fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "c7000v2", "RouterStatus.htm")
    with open(fixture_path) as f:
        return f.read()


class TestDetection:
    """Test C7000v2 parser detection."""

    def test_parser_detection_from_fixture(self, c7000v2_index_html):
        """Test that the Netgear C7000v2 parser detects the modem from fixture."""
        soup = BeautifulSoup(c7000v2_index_html, "html.parser")
        assert NetgearC7000v2Parser.can_parse(soup, "http://192.168.100.1/index.htm", c7000v2_index_html)

    def test_parser_detection_from_title(self):
        """Test C7000v2 detection from page title."""
        html = """
        <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
        <html><head><title>NETGEAR Gateway C7000v2</title></head>
        <body></body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        assert NetgearC7000v2Parser.can_parse(soup, "http://192.168.100.1/", html)

    def test_parser_detection_from_meta(self):
        """Test C7000v2 detection from meta description."""
        html = """
        <html>
        <head>
            <META content='C7000v2' name="description">
            <title>NETGEAR Gateway</title>
        </head>
        <body></body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        assert NetgearC7000v2Parser.can_parse(soup, "http://192.168.100.1/", html)

    def test_parser_detection_from_content(self):
        """Test C7000v2 detection from page content."""
        html = """
        <html>
        <head><title>NETGEAR Gateway</title></head>
        <body>
            <p>Welcome to your C7000v2 gateway</p>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        assert NetgearC7000v2Parser.can_parse(soup, "http://192.168.100.1/", html)

    def test_parser_does_not_match_c3700(self):
        """Test that C7000v2 parser doesn't match C3700."""
        html = """
        <html>
        <head><title>NETGEAR Gateway C3700</title></head>
        <body></body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        assert not NetgearC7000v2Parser.can_parse(soup, "http://192.168.100.1/", html)


class TestParsing:
    """Test C7000v2 channel data parsing."""

    def test_parsing_downstream(self, c7000v2_docsis_status_html):
        """Test parsing of Netgear C7000v2 downstream data."""
        parser = NetgearC7000v2Parser()
        soup = BeautifulSoup(c7000v2_docsis_status_html, "html.parser")
        data = parser.parse(soup)

        # Verify downstream channels were parsed
        assert "downstream" in data
        assert len(data["downstream"]) > 0

        # Check first downstream channel structure
        first_ds = data["downstream"][0]
        assert "channel_id" in first_ds
        assert "frequency" in first_ds
        assert "power" in first_ds
        assert "snr" in first_ds
        assert "modulation" in first_ds
        assert "corrected" in first_ds
        assert "uncorrected" in first_ds

    def test_parsing_upstream(self, c7000v2_docsis_status_html):
        """Test parsing of Netgear C7000v2 upstream data."""
        parser = NetgearC7000v2Parser()
        soup = BeautifulSoup(c7000v2_docsis_status_html, "html.parser")
        data = parser.parse(soup)

        # Verify upstream channels were parsed
        assert "upstream" in data
        assert len(data["upstream"]) > 0

        # Check first upstream channel structure
        first_us = data["upstream"][0]
        assert "channel_id" in first_us
        assert "frequency" in first_us
        assert "power" in first_us
        assert "channel_type" in first_us

    def test_parse_system_info(self, c7000v2_router_status_html):
        """Test parsing of system info from RouterStatus.htm."""
        parser = NetgearC7000v2Parser()
        soup = BeautifulSoup(c7000v2_router_status_html, "html.parser")
        system_info = parser.parse_system_info(soup)

        # Verify system info was parsed
        assert "hardware_version" in system_info
        assert "software_version" in system_info

    def test_multi_page_parsing_with_session(
        self, c7000v2_index_html, c7000v2_docsis_status_html, c7000v2_router_status_html
    ):
        """Test that parser fetches DocsisStatus.htm and RouterStatus.htm."""
        from unittest.mock import Mock

        parser = NetgearC7000v2Parser()
        mock_session = Mock()

        def mock_get(url, timeout=10):
            mock_response = Mock()
            mock_response.status_code = 200
            if "DocsisStatus.htm" in url:
                mock_response.text = c7000v2_docsis_status_html
            elif "RouterStatus.htm" in url:
                mock_response.text = c7000v2_router_status_html
            else:
                mock_response.text = c7000v2_index_html
            return mock_response

        mock_session.get.side_effect = mock_get

        index_soup = BeautifulSoup(c7000v2_index_html, "html.parser")
        data = parser.parse(index_soup, session=mock_session, base_url="http://192.168.100.1")

        # Verify channel data was parsed
        assert len(data["downstream"]) > 0
        assert len(data["upstream"]) > 0


class TestAuthentication:
    """Test HTTP Basic Authentication for C7000v2."""

    def test_has_basic_auth_config(self):
        """Test that parser has HTTP Basic Auth configuration."""
        from custom_components.cable_modem_monitor.core.auth_config import BasicAuthConfig
        from custom_components.cable_modem_monitor.core.authentication import AuthStrategyType

        parser = NetgearC7000v2Parser()

        assert parser.auth_config is not None
        assert isinstance(parser.auth_config, BasicAuthConfig)
        assert parser.auth_config.strategy == AuthStrategyType.BASIC_HTTP

    def test_url_patterns_auth_required(self):
        """Test that protected URLs require authentication."""
        parser = NetgearC7000v2Parser()

        # DocsisStatus.htm should require auth
        docsis_pattern = next(p for p in parser.url_patterns if p["path"] == "/DocsisStatus.htm")
        assert docsis_pattern["auth_required"] is True

        # Index page should NOT require auth
        index_pattern = next(p for p in parser.url_patterns if p["path"] == "/")
        assert index_pattern["auth_required"] is False


class TestMetadata:
    """Test parser metadata."""

    def test_name(self):
        """Test parser name."""
        parser = NetgearC7000v2Parser()
        assert parser.name == "Netgear C7000v2"

    def test_manufacturer(self):
        """Test parser manufacturer."""
        parser = NetgearC7000v2Parser()
        assert parser.manufacturer == "Netgear"

    def test_models(self):
        """Test parser supported models."""
        parser = NetgearC7000v2Parser()
        assert "C7000v2" in parser.models
        assert "C7000-100NAS" in parser.models

    def test_status_awaiting_verification(self):
        """Test parser status is awaiting verification."""
        from custom_components.cable_modem_monitor.parsers.base_parser import ParserStatus

        parser = NetgearC7000v2Parser()
        assert parser.status == ParserStatus.AWAITING_VERIFICATION

    def test_capabilities(self):
        """Test parser capabilities."""
        from custom_components.cable_modem_monitor.parsers.base_parser import ModemCapability

        parser = NetgearC7000v2Parser()
        assert ModemCapability.DOWNSTREAM_CHANNELS in parser.capabilities
        assert ModemCapability.UPSTREAM_CHANNELS in parser.capabilities
        assert ModemCapability.SYSTEM_UPTIME in parser.capabilities
        assert ModemCapability.RESTART in parser.capabilities


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_downstream_data(self):
        """Test parsing when no downstream channels are present."""
        parser = NetgearC7000v2Parser()
        html = "<html><head><title>C7000v2</title></head><body></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        data = parser.parse(soup)

        assert data["downstream"] == []
        assert data["upstream"] == []
        assert data["system_info"] == {}

    def test_graceful_handling_on_fetch_error(self, c7000v2_index_html):
        """Test that parser gracefully handles errors when fetching pages."""
        from unittest.mock import Mock

        parser = NetgearC7000v2Parser()
        mock_session = Mock()
        mock_session.get.side_effect = Exception("Connection error")

        index_soup = BeautifulSoup(c7000v2_index_html, "html.parser")
        data = parser.parse(index_soup, session=mock_session, base_url="http://192.168.100.1")

        # Should return empty data structures without crashing
        assert data["downstream"] == []
        assert data["upstream"] == []


class TestFixtures:
    """Test that required fixtures exist."""

    def test_fixtures_directory_exists(self):
        """Test that the C7000v2 fixtures directory exists."""
        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "c7000v2")
        assert os.path.isdir(fixture_path)

    def test_required_fixtures_exist(self):
        """Test that required fixture files exist."""
        fixture_base = os.path.join(os.path.dirname(__file__), "fixtures", "c7000v2")

        required_files = ["index.htm", "DocsisStatus.htm", "RouterStatus.htm"]
        for filename in required_files:
            filepath = os.path.join(fixture_base, filename)
            assert os.path.exists(filepath), f"Missing required fixture: {filename}"
