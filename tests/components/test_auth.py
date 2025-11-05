import pytest
from unittest.mock import Mock

from custom_components.cable_modem_monitor.core.modem_scraper import ModemScraper
from custom_components.cable_modem_monitor.parsers.motorola.generic import MotorolaGenericParser
from custom_components.cable_modem_monitor.parsers.technicolor.tc4400 import TechnicolorTC4400Parser

class TestAuth:
    """Test the authentication system."""

    def test_form_auth(self, mocker):
        """Test form-based authentication."""
        scraper = ModemScraper("192.168.100.1", "admin", "password", parser=[MotorolaGenericParser])
        # _fetch_data now returns (html, url, parser_class)
        mocker.patch.object(scraper, '_fetch_data', return_value=("<html></html>", "http://192.168.100.1", MotorolaGenericParser))
        mocker.patch.object(scraper, '_detect_parser', return_value=MotorolaGenericParser())
        mock_login = mocker.patch.object(MotorolaGenericParser, 'login', return_value=True)
        scraper.get_modem_data()

        mock_login.assert_called_once()

    def test_basic_auth(self, mocker):
        """Test basic HTTP authentication."""
        from custom_components.cable_modem_monitor.parsers.technicolor.tc4400 import TechnicolorTC4400Parser
        scraper = ModemScraper("192.168.100.1", "admin", "password", parser=[TechnicolorTC4400Parser])
        # _fetch_data now returns (html, url, parser_class)
        mocker.patch.object(scraper, '_fetch_data', return_value=("<html></html>", "http://192.168.100.1", TechnicolorTC4400Parser))
        mocker.patch.object(scraper, '_detect_parser', return_value=TechnicolorTC4400Parser())
        mock_login = mocker.patch.object(TechnicolorTC4400Parser, 'login', return_value=True)
        scraper.get_modem_data()

        mock_login.assert_called_once()
