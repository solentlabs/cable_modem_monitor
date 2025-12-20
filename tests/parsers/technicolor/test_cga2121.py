"""Tests for the Technicolor CGA2121 parser."""

from __future__ import annotations

import os
from unittest.mock import Mock

import pytest
import requests
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.parsers.technicolor.cga2121 import (
    TechnicolorCGA2121Parser,
)


@pytest.fixture
def st_docsis_html():
    """Load st_docsis.html fixture."""
    path = os.path.join(os.path.dirname(__file__), "fixtures", "cga2121", "st_docsis.html")
    with open(path, encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def logon_html():
    """Load logon.html fixture from extended folder."""
    path = os.path.join(os.path.dirname(__file__), "fixtures", "cga2121", "extended", "logon.html")
    with open(path, encoding="utf-8") as f:
        return f.read()


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
        """Test DOCSIS version."""
        assert parser.docsis_version == "3.0"

    def test_fixtures_path(self, parser):
        """Test fixtures path exists."""
        assert parser.fixtures_path is not None
        assert "cga2121" in parser.fixtures_path


class TestDetection:
    """Test modem detection."""

    def test_can_parse_by_model_name(self, st_docsis_html):
        """Test detection by CGA2121 model name in HTML."""
        soup = BeautifulSoup(st_docsis_html, "html.parser")
        result = TechnicolorCGA2121Parser.can_parse(soup, "http://192.168.100.1/st_docsis.html", st_docsis_html)
        assert result is True

    def test_can_parse_by_url_and_branding(self, st_docsis_html):
        """Test detection by URL pattern and Technicolor branding."""
        # Remove CGA2121 from HTML but keep Technicolor
        modified_html = st_docsis_html.replace("CGA2121", "GATEWAY")
        soup = BeautifulSoup(modified_html, "html.parser")
        result = TechnicolorCGA2121Parser.can_parse(soup, "http://192.168.100.1/st_docsis.html", modified_html)
        assert result is True

    def test_does_not_match_other_modem(self):
        """Test that parser doesn't match other modems."""
        html = "<html><title>Other Modem</title><body>Some content</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        result = TechnicolorCGA2121Parser.can_parse(soup, "http://192.168.100.1/status.html", html)
        assert result is False


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


class TestLogin:
    """Test login functionality."""

    def test_login_no_credentials_returns_false(self, parser):
        """Test login without credentials returns False."""
        session = Mock()
        success, html = parser.login(session, "http://192.168.100.1", None, None)
        assert success is False
        assert html is None

    def test_login_empty_credentials_returns_false(self, parser):
        """Test login with empty credentials returns False."""
        session = Mock()
        success, html = parser.login(session, "http://192.168.100.1", "", "")
        assert success is False
        assert html is None

    def test_login_success(self, parser, st_docsis_html):
        """Test successful login flow."""
        session = Mock()

        # Mock the POST response (login)
        login_response = Mock()
        login_response.status_code = 200
        login_response.url = "http://192.168.100.1/basicUX.html"
        login_response.history = [Mock(status_code=302)]  # Simulate redirect

        # Mock the GET response (status page)
        status_response = Mock()
        status_response.status_code = 200
        status_response.text = st_docsis_html
        status_response.url = "http://192.168.100.1/st_docsis.html"

        # Mock session cookies (CGA2121 uses 'sec' cookie)
        session.cookies.get_dict.return_value = {"sec": "1486188572"}
        session.post.return_value = login_response
        session.get.return_value = status_response

        success, html = parser.login(session, "http://192.168.100.1", "admin", "password")

        assert success is True
        assert html == st_docsis_html
        session.post.assert_called_once()
        session.get.assert_called_once()

    def test_login_redirects_to_login_page(self, parser):
        """Test login failure when redirected back to login page."""
        session = Mock()

        # Mock redirect back to login page (wrong credentials)
        login_response = Mock()
        login_response.status_code = 200
        login_response.url = "http://192.168.100.1/logon.html"
        login_response.text = "<html>Login failed</html>"
        login_response.history = []

        session.cookies.get_dict.return_value = {}
        session.post.return_value = login_response

        success, html = parser.login(session, "http://192.168.100.1", "admin", "wrong")

        assert success is False
        assert html is None

    def test_login_post_fails(self, parser):
        """Test login when POST request fails."""
        session = Mock()

        login_response = Mock()
        login_response.status_code = 401
        login_response.url = "http://192.168.100.1/goform/logon"
        login_response.text = "Unauthorized"
        login_response.history = []

        session.cookies.get_dict.return_value = {}
        session.post.return_value = login_response

        success, html = parser.login(session, "http://192.168.100.1", "admin", "password")

        assert success is False
        assert html is None

    def test_login_timeout(self, parser):
        """Test login timeout handling."""
        session = Mock()
        session.post.side_effect = requests.exceptions.Timeout("Connection timed out")

        success, html = parser.login(session, "http://192.168.100.1", "admin", "password")

        assert success is False
        assert html is None

    def test_login_connection_error(self, parser):
        """Test login connection error handling."""
        session = Mock()
        session.post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        success, html = parser.login(session, "http://192.168.100.1", "admin", "password")

        assert success is False
        assert html is None

    def test_login_security_redirect_check(self, parser):
        """Test that redirect to different host is rejected."""
        session = Mock()

        # Mock redirect to different host (security violation)
        login_response = Mock()
        login_response.status_code = 200
        login_response.url = "http://malicious.com/steal"
        login_response.history = [Mock(status_code=302)]

        session.cookies.get_dict.return_value = {"sec": "fake"}
        session.post.return_value = login_response

        success, html = parser.login(session, "http://192.168.100.1", "admin", "password")

        assert success is False
        assert html is None


class TestFixtures:
    """Test fixture file existence."""

    def test_fixture_file_exists(self):
        """Test that required fixture files exist."""
        fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures", "cga2121")
        assert os.path.exists(fixtures_dir)
        assert os.path.exists(os.path.join(fixtures_dir, "st_docsis.html"))
        assert os.path.exists(os.path.join(fixtures_dir, "metadata.yaml"))
        assert os.path.exists(os.path.join(fixtures_dir, "README.md"))

    def test_extended_fixture_exists(self):
        """Test that extended fixture files exist."""
        extended_dir = os.path.join(os.path.dirname(__file__), "fixtures", "cga2121", "extended")
        assert os.path.exists(extended_dir)
        assert os.path.exists(os.path.join(extended_dir, "logon.html"))
