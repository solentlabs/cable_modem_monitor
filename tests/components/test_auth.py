from __future__ import annotations

from custom_components.cable_modem_monitor.core.auth.handler import AuthHandler
from custom_components.cable_modem_monitor.core.base_parser import ModemParser
from custom_components.cable_modem_monitor.core.fallback import FallbackOrchestrator


class MockParserWithHints(ModemParser):
    """Mock parser WITH auth_form_hints - should use AuthHandler."""

    name = "[MFG] [Model] WithHints"
    manufacturer = "Unknown"  # Mark as fallback parser for FallbackOrchestrator
    auth_form_hints = {"username_field": "user", "password_field": "pass"}

    # Detection uses YAML hints (HintMatcher)

    def parse_resources(self, resources):
        return {"downstream": [], "upstream": [], "system_info": {}}

    def parse(self, soup, session=None, base_url=None):
        return {"downstream": [], "upstream": []}


class MockParserWithoutHints(ModemParser):
    """Mock parser WITHOUT auth_form_hints - uses auth discovery."""

    name = "[MFG] [Model] NoHints"
    manufacturer = "[MFG]"
    # No auth_form_hints defined - auth discovery will probe for auth type

    # Detection uses YAML hints (HintMatcher)

    def parse_resources(self, resources):
        return {"downstream": [], "upstream": [], "system_info": {}}

    def parse(self, soup, session=None, base_url=None):
        return {"downstream": [], "upstream": []}


class TestAuth:
    """Test the authentication system.

    Authentication architecture:
    - DataOrchestrator: For known modem.yaml parsers, uses stored auth strategy only
    - FallbackOrchestrator: For unknown modems, adds parser hints discovery
    """

    def test_form_auth_uses_parser_hints(self, mocker):
        """Test FallbackOrchestrator uses parser's auth_form_hints.

        When a fallback parser has auth_form_hints defined, FallbackOrchestrator
        creates a temporary AuthHandler to handle authentication.
        """
        # Use FallbackOrchestrator for parser hints behavior
        scraper = FallbackOrchestrator("192.168.100.1", "admin", "password", parser=[MockParserWithHints])
        # _fetch_data now returns (html, url, parser_class)
        mocker.patch.object(
            scraper,
            "_fetch_data",
            return_value=("<html></html>", "http://192.168.100.1", MockParserWithHints),
        )
        mocker.patch.object(scraper, "_detect_parser", return_value=MockParserWithHints())

        # Mock AuthHandler.authenticate to verify it's called
        mock_auth = mocker.patch.object(AuthHandler, "authenticate", return_value=(True, None))

        scraper.get_modem_data()

        # AuthHandler.authenticate should be called (via the temp handler created for hints)
        mock_auth.assert_called_once()

    def test_parser_does_not_have_login_method(self):
        """Test that parsers don't have a login() method.

        Auth is handled by AuthHandler via auth discovery.
        """
        assert not hasattr(MockParserWithoutHints, "login")
        assert not hasattr(ModemParser, "login")

    def test_parser_without_hints_can_be_instantiated(self):
        """Test that parsers without auth_form_hints can still be used.

        Even without hints, parsers work - auth discovery determines auth type.
        """
        parser = MockParserWithoutHints()
        result = parser.parse(None)

        # Parser should return valid structure
        assert "downstream" in result
        assert "upstream" in result
