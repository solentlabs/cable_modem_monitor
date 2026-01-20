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

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.discovery_helpers import HintMatcher
from custom_components.cable_modem_monitor.modems.netgear.c7000v2.parser import NetgearC7000v2Parser
from tests.fixtures import load_fixture


@pytest.fixture
def c7000v2_index_html():
    """Load C7000v2 index.htm fixture."""
    return load_fixture("netgear", "c7000v2", "index.htm")


@pytest.fixture
def c7000v2_docsis_status_html():
    """Load C7000v2 DocsisStatus.htm fixture."""
    return load_fixture("netgear", "c7000v2", "DocsisStatus.htm")


@pytest.fixture
def c7000v2_router_status_html():
    """Load C7000v2 RouterStatus.htm fixture."""
    return load_fixture("netgear", "c7000v2", "RouterStatus.htm")


class TestDetection:
    """Test C7000v2 parser detection."""

    def test_parser_detection_from_fixture(self, c7000v2_index_html):
        """Test that the Netgear C7000v2 parser detects the modem from fixture via HintMatcher."""
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_login_markers(c7000v2_index_html)
        assert any(m.parser_name == "NetgearC7000v2Parser" for m in matches)

    def test_parser_detection_from_title(self):
        """Test C7000v2 detection from page title via HintMatcher."""
        html = """
        <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
        <html><head><title>NETGEAR Gateway C7000v2</title></head>
        <body></body></html>
        """
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_login_markers(html)
        assert any(m.parser_name == "NetgearC7000v2Parser" for m in matches)

    def test_parser_detection_from_meta(self):
        """Test C7000v2 detection from meta description via HintMatcher."""
        html = """
        <html>
        <head>
            <META content='C7000v2' name="description">
            <title>NETGEAR Gateway</title>
        </head>
        <body></body>
        </html>
        """
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_login_markers(html)
        assert any(m.parser_name == "NetgearC7000v2Parser" for m in matches)

    def test_parser_detection_from_content(self):
        """Test C7000v2 detection from page content via HintMatcher."""
        html = """
        <html>
        <head><title>NETGEAR Gateway</title></head>
        <body>
            <p>Welcome to your C7000v2 gateway</p>
        </body>
        </html>
        """
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_login_markers(html)
        assert any(m.parser_name == "NetgearC7000v2Parser" for m in matches)

    def test_c3700_ranks_higher_than_c7000v2_for_c3700_content(self):
        """Test that C3700 ranks higher than C7000v2 for C3700-specific content.

        Both parsers share the generic "NETGEAR" login_marker, so both may match.
        However, C3700 has more specific markers that give it more matches,
        causing it to rank higher in the results (sorted by match count).
        """
        html = """
        <html>
        <head><title>NETGEAR Gateway C3700</title></head>
        <body></body>
        </html>
        """
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_login_markers(html)

        # C3700 should rank first (more specific markers)
        assert len(matches) > 0
        assert matches[0].parser_name == "NetgearC3700Parser"

        # C7000v2 may still be in the list (generic "NETGEAR" marker matches)
        # but should rank lower due to fewer matches
        c7000v2_matches = [m for m in matches if m.parser_name == "NetgearC7000v2Parser"]
        if c7000v2_matches:
            c3700_matches = [m for m in matches if m.parser_name == "NetgearC3700Parser"]
            # C3700 should have more matched markers
            assert len(c3700_matches[0].matched_markers) > len(c7000v2_matches[0].matched_markers)


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
    """Test auth discovery hints and URL patterns for C7000v2 (v3.12.0+)."""

    def test_url_patterns_auth_required(self):
        """Test that protected URLs require authentication."""
        from custom_components.cable_modem_monitor.modem_config.adapter import get_url_patterns_for_parser

        url_patterns = get_url_patterns_for_parser("NetgearC7000v2Parser")
        assert url_patterns is not None, "C7000v2 should have URL patterns in modem.yaml"

        # DocsisStatus.htm should require auth
        docsis_pattern = next(p for p in url_patterns if p["path"] == "/DocsisStatus.htm")
        assert docsis_pattern["auth_required"] is True

        # Should have a public page for detection
        public_patterns = [p for p in url_patterns if not p.get("auth_required", True)]
        assert len(public_patterns) > 0, "C7000v2 should have a public page for detection"


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
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_auth_adapter_for_parser,
        )

        adapter = get_auth_adapter_for_parser("NetgearC7000v2Parser")
        assert adapter is not None
        assert adapter.get_status() == "awaiting_verification"

    def test_capabilities(self):
        """Test parser capabilities."""
        from custom_components.cable_modem_monitor.core.base_parser import ModemCapability

        parser = NetgearC7000v2Parser()
        assert ModemCapability.SCQAM_DOWNSTREAM in parser.capabilities
        assert ModemCapability.SCQAM_UPSTREAM in parser.capabilities
        assert ModemCapability.SYSTEM_UPTIME in parser.capabilities
        # Note: RESTART is now an action (check via ActionFactory.supports), not a capability


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
        from tests.fixtures import get_fixture_dir

        fixture_path = get_fixture_dir("netgear", "c7000v2")
        assert fixture_path.is_dir()

    def test_required_fixtures_exist(self):
        """Test that required fixture files exist."""
        from tests.fixtures import get_fixture_dir

        fixture_dir = get_fixture_dir("netgear", "c7000v2")
        required_files = ["index.htm", "DocsisStatus.htm", "RouterStatus.htm"]
        for filename in required_files:
            filepath = fixture_dir / filename
            assert filepath.exists(), f"Missing required fixture: {filename}"
