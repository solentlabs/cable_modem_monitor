"""Tests for the Universal Fallback parser."""

from __future__ import annotations

from unittest.mock import Mock, patch

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.parsers.universal.fallback import UniversalFallbackParser


class TestCanParse:
    """Test the can_parse method."""

    def test_always_returns_true_for_any_html(self):
        """Test that can_parse always returns True regardless of HTML content."""
        # Test with random HTML
        soup = BeautifulSoup("<html><body><h1>Random Page</h1></body></html>", "html.parser")
        assert UniversalFallbackParser.can_parse(soup, "http://192.168.1.1", "<html></html>") is True

    def test_returns_true_for_empty_html(self):
        """Test that can_parse returns True even for empty HTML."""
        soup = BeautifulSoup("", "html.parser")
        assert UniversalFallbackParser.can_parse(soup, "http://192.168.1.1", "") is True

    def test_returns_true_for_known_modem_html(self):
        """Test that can_parse returns True even for HTML from known modems."""
        html = "<html><title>ARRIS SB6190</title></html>"
        soup = BeautifulSoup(html, "html.parser")
        assert UniversalFallbackParser.can_parse(soup, "http://192.168.100.1", html) is True

    def test_returns_true_for_invalid_html(self):
        """Test that can_parse returns True even for malformed HTML."""
        soup = BeautifulSoup("<html><body><unclosed>", "html.parser")
        assert UniversalFallbackParser.can_parse(soup, "http://192.168.1.1", "<html><body><unclosed>") is True


class TestParse:
    """Test the parse method."""

    def test_returns_empty_channels(self):
        """Test that parse returns empty channel lists."""
        parser = UniversalFallbackParser()
        soup = BeautifulSoup("<html></html>", "html.parser")

        result = parser.parse(soup)

        assert result["downstream"] == []
        assert result["upstream"] == []

    def test_sets_fallback_mode_flag(self):
        """Test that parse sets the fallback_mode flag in system_info."""
        parser = UniversalFallbackParser()
        soup = BeautifulSoup("<html></html>", "html.parser")

        result = parser.parse(soup)

        assert result["system_info"]["fallback_mode"] is True

    def test_includes_status_message(self):
        """Test that parse includes a helpful status message."""
        parser = UniversalFallbackParser()
        soup = BeautifulSoup("<html></html>", "html.parser")

        result = parser.parse(soup)

        status_message = result["system_info"]["status_message"]
        assert "⚠️" in status_message
        assert "Connectivity monitoring" in status_message
        assert "Capture HTML" in status_message

    def test_sets_unknown_manufacturer(self):
        """Test that parse sets manufacturer to Unknown."""
        parser = UniversalFallbackParser()
        soup = BeautifulSoup("<html></html>", "html.parser")

        result = parser.parse(soup)

        assert result["system_info"]["manufacturer"] == "Unknown"


class TestModelExtraction:
    """Test the _try_extract_model_info method."""

    def test_from_title(self):
        """Test extracting modem model from HTML title tag."""
        parser = UniversalFallbackParser()
        html = "<html><head><title>NETGEAR CM600</title></head></html>"
        soup = BeautifulSoup(html, "html.parser")

        result = parser.parse(soup)

        assert result["system_info"]["model"] == "NETGEAR CM600"

    def test_from_meta_tags(self):
        """Test extracting modem model from meta tags."""
        parser = UniversalFallbackParser()
        html = '<html><head><meta name="product" content="ARRIS SB8200"/></head></html>'
        soup = BeautifulSoup(html, "html.parser")

        result = parser.parse(soup)

        assert result["system_info"]["model"] == "ARRIS SB8200"

    def test_netgear_from_body(self):
        """Test extracting NETGEAR model from HTML body text."""
        parser = UniversalFallbackParser()
        html = "<html><body>Welcome to your NETGEAR CM1000 Cable Modem</body></html>"
        soup = BeautifulSoup(html, "html.parser")

        result = parser.parse(soup)

        assert "NETGEAR CM1000" in result["system_info"]["model"]

    def test_arris_from_body(self):
        """Test extracting ARRIS model from HTML body text."""
        parser = UniversalFallbackParser()
        html = "<html><body>ARRIS SB6190 Status Page</body></html>"
        soup = BeautifulSoup(html, "html.parser")

        result = parser.parse(soup)

        assert "ARRIS SB6190" in result["system_info"]["model"]

    def test_motorola_from_body(self):
        """Test extracting Motorola model from HTML body text."""
        parser = UniversalFallbackParser()
        html = "<html><body>Motorola MB8600 Configuration</body></html>"
        soup = BeautifulSoup(html, "html.parser")

        result = parser.parse(soup)

        assert "Motorola MB8600" in result["system_info"]["model"]

    def test_returns_unknown_model_when_not_found(self):
        """Test that Unknown Model is returned when no model info found."""
        parser = UniversalFallbackParser()
        html = "<html><body>Generic Router Page</body></html>"
        soup = BeautifulSoup(html, "html.parser")

        result = parser.parse(soup)

        assert result["system_info"]["model"] == "Unknown Model"


class TestLogin:
    """Test the login method."""

    def test_returns_true_without_credentials(self):
        """Test that login succeeds when no credentials are provided."""
        parser = UniversalFallbackParser()
        session = Mock()

        success, html = parser.login(session, "http://192.168.1.1", None, None)

        assert success is True
        assert html is None

    def test_returns_true_with_empty_credentials(self):
        """Test that login succeeds with empty username/password."""
        parser = UniversalFallbackParser()
        session = Mock()

        success, html = parser.login(session, "http://192.168.1.1", "", "")

        assert success is True
        assert html is None

    @patch("custom_components.cable_modem_monitor.core.authentication.AuthFactory")
    def test_attempts_basic_auth_with_credentials(self, mock_auth_factory):
        """Test that login attempts HTTP Basic Auth when credentials provided."""
        parser = UniversalFallbackParser()
        session = Mock()

        # Mock successful authentication
        mock_strategy = Mock()
        mock_strategy.login.return_value = (True, "<html>authenticated</html>")
        mock_auth_factory.get_strategy.return_value = mock_strategy

        success, html = parser.login(session, "http://192.168.1.1", "admin", "password")

        # Should attempt authentication
        mock_auth_factory.get_strategy.assert_called_once()
        mock_strategy.login.assert_called_once_with(
            session, "http://192.168.1.1", "admin", "password", parser.auth_config
        )
        assert success is True
        assert html == "<html>authenticated</html>"

    @patch("custom_components.cable_modem_monitor.core.authentication.AuthFactory")
    def test_returns_true_even_when_auth_fails(self, mock_auth_factory):
        """Test that login returns True even if authentication fails."""
        parser = UniversalFallbackParser()
        session = Mock()

        # Mock failed authentication
        mock_strategy = Mock()
        mock_strategy.login.return_value = (False, None)
        mock_auth_factory.get_strategy.return_value = mock_strategy

        success, html = parser.login(session, "http://192.168.1.1", "admin", "wrong")

        # Should still return True to allow installation
        assert success is True
        assert html is None

    @patch("custom_components.cable_modem_monitor.core.authentication.AuthFactory")
    def test_returns_true_when_auth_raises_exception(self, mock_auth_factory):
        """Test that login returns True even if authentication raises exception."""
        parser = UniversalFallbackParser()
        session = Mock()

        # Mock exception during authentication
        mock_auth_factory.get_strategy.side_effect = Exception("Auth error")

        success, html = parser.login(session, "http://192.168.1.1", "admin", "password")

        # Should still return True to allow installation
        assert success is True
        assert html is None


class TestParserConfiguration:
    """Test parser configuration and properties."""

    def test_has_correct_name(self):
        """Test that parser has the correct name."""
        assert UniversalFallbackParser.name == "Unknown Modem (Fallback Mode)"

    def test_has_lowest_priority(self):
        """Test that parser has priority 1 (lowest)."""
        assert UniversalFallbackParser.priority == 1

    def test_has_unknown_manufacturer(self):
        """Test that parser has Unknown manufacturer."""
        assert UniversalFallbackParser.manufacturer == "Unknown"

    def test_has_url_patterns(self):
        """Test that parser has URL patterns defined."""
        assert len(UniversalFallbackParser.url_patterns) > 0

    def test_url_patterns_include_root(self):
        """Test that URL patterns include root path."""
        paths = [p["path"] for p in UniversalFallbackParser.url_patterns]
        assert "/" in paths

    def test_url_patterns_include_common_pages(self):
        """Test that URL patterns include common status pages."""
        paths = [p["path"] for p in UniversalFallbackParser.url_patterns]
        assert any("status" in p.lower() for p in paths if isinstance(p, str))

    def test_uses_basic_auth_config(self):
        """Test that parser uses BasicAuthConfig."""
        from custom_components.cable_modem_monitor.core.authentication import AuthStrategyType

        assert UniversalFallbackParser.auth_config.strategy == AuthStrategyType.BASIC_HTTP
