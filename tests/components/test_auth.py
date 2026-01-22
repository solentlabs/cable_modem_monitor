from __future__ import annotations

from custom_components.cable_modem_monitor.core.auth.handler import AuthHandler
from custom_components.cable_modem_monitor.core.base_parser import ModemParser
from custom_components.cable_modem_monitor.core.data_orchestrator import DataOrchestrator


class MockParserWithHints(ModemParser):
    """Mock parser WITH auth_form_hints - should use AuthHandler."""

    name = "[MFG] [Model] WithHints"
    manufacturer = "[MFG]"
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

    Authentication is handled by AuthHandler:
    - Parsers with auth_form_hints use AuthHandler for form-based auth.
    - Parsers without auth_form_hints use auth discovery to detect auth type.
    """

    def test_form_auth_uses_parser_hints(self, mocker):
        """Test form-based authentication uses parser's auth_form_hints.

        When a parser has auth_form_hints defined, the scraper creates a temporary
        AuthHandler to handle authentication.
        """
        scraper = DataOrchestrator("192.168.100.1", "admin", "password", parser=[MockParserWithHints])
        # _fetch_data now returns (html, url, parser_class)
        mocker.patch.object(
            scraper, "_fetch_data", return_value=("<html></html>", "http://192.168.100.1", MockParserWithHints)
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
