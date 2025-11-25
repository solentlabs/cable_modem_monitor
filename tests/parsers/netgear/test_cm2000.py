"""Tests for the Netgear CM2000 (Nighthawk) parser.

NOTE: Parser verification pending DocsisStatus.htm HTML capture.
The CM2000 uses /DocsisStatus.htm for DOCSIS channel data, which requires
authentication to access.

Current fixtures available:
- index.htm: Login page (unauthenticated)

Missing fixture needed for parser verification:
- DocsisStatus.htm: DOCSIS channel data (downstream/upstream)

Related: Issue ***REMOVED***38 (Netgear CM2000 Support Request)
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
        ***REMOVED*** The meta description should contain CM2000
        meta = soup.find("meta", attrs={"name": "description"})
        assert meta is not None
        assert "CM2000" in meta.get("content", "")

    def test_does_not_match_cm600(self):
        """Test that CM2000 parser doesn't match CM600 HTML."""
        ***REMOVED*** Use CM600 style HTML
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
        """Test parser is marked as verified."""
        ***REMOVED*** Verified via GitHub issue ***REMOVED***38 by @m4dh4tt3r-88
        assert NetgearCM2000Parser.verified is True

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

        ***REMOVED*** Login page shouldn't have channel data
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

        ***REMOVED*** Once we have the fixture, we can add specific assertions
        ***REMOVED*** For now, just verify the structure
        assert "downstream" in result
        assert "upstream" in result
        assert "system_info" in result

        ***REMOVED*** Add specific assertions based on actual fixture data
        ***REMOVED*** downstream = result["downstream"]
        ***REMOVED*** assert len(downstream) > 0
        ***REMOVED*** assert all("channel_id" in ch for ch in downstream)
        ***REMOVED*** assert all("frequency" in ch for ch in downstream)


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

    def test_docsis_status_fixture_needed(self):
        """Document that DocsisStatus.htm is still needed."""
        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "cm2000", "DocsisStatus.htm")
        if not os.path.exists(fixture_path):
            pytest.skip("DocsisStatus.htm fixture needed - see GitHub Issue ***REMOVED***38 for details")
