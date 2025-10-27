"""Tests for Cable Modem Monitor scraper."""
import pytest
from bs4 import BeautifulSoup
from unittest.mock import Mock

from custom_components.cable_modem_monitor.modem_scraper import ModemScraper
from custom_components.cable_modem_monitor.parsers.base_parser import ModemParser

class TestModemScraper:
    """Test the ModemScraper class."""

    @pytest.fixture
    def mock_parser(self, mocker):
        """Create a mock parser."""
        parser = mocker.Mock()
        parser.can_parse.return_value = True
        parser.parse.return_value = {
            "downstream": [],
            "upstream": [],
            "system_info": {},
        }
        return parser

    def test_scraper_with_mock_parser(self, mocker):
        """Test the scraper with a mock parser."""
        ***REMOVED*** Create a mock instance for the detected parser
        mock_parser_instance = mocker.Mock(spec=ModemParser)
        mock_parser_instance.login.return_value = True
        mock_parser_instance.parse.return_value = {
            "downstream": [],
            "upstream": [],
            "system_info": {},
        }

        ***REMOVED*** Create a mock for the parser class that _detect_parser would return
        mock_parser_class = mocker.Mock(spec=ModemParser)
        mock_parser_class.can_parse.return_value = True
        mock_parser_class.return_value = mock_parser_instance  ***REMOVED*** What the class returns when instantiated

        scraper = ModemScraper("192.168.100.1", parsers=[mock_parser_class])
        mocker.patch.object(scraper, '_fetch_data', return_value=("<html></html>", "http://192.168.100.1"))
        
        ***REMOVED*** _login is called internally after parser is detected, so it should use the mock_parser_instance's login
        mocker.patch.object(scraper, '_login', side_effect=lambda: mock_parser_instance.login(scraper.session, scraper.base_url, scraper.username, scraper.password))

        data = scraper.get_modem_data()

        assert data is not None
        mock_parser_class.can_parse.assert_called_once()
        
        ***REMOVED*** Assert that the parser instance's login method was called
        mock_parser_instance.login.assert_called_once_with(scraper.session, scraper.base_url, scraper.username, scraper.password)
        mock_parser_instance.parse.assert_called_once()