"""Tests for the Universal Fallback parser."""

from __future__ import annotations

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.parsers.universal.fallback import UniversalFallbackParser

# Detection is handled by YAML hints (HintMatcher).
# The fallback parser is manually selected by users when auto-detection fails.


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
        html = '<html><head><meta name="product" content="ACME Modem-5000"/></head></html>'
        soup = BeautifulSoup(html, "html.parser")

        result = parser.parse(soup)

        assert result["system_info"]["model"] == "ACME Modem-5000"

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

    def test_has_auth_hint(self):
        """Test that parser has auth_hint suggesting basic auth."""
        assert UniversalFallbackParser.auth_hint == "basic"
