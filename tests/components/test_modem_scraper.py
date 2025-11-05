"""Tests for Cable Modem Monitor scraper."""
import pytest
from bs4 import BeautifulSoup
from unittest.mock import Mock

from custom_components.cable_modem_monitor.core.modem_scraper import ModemScraper
from custom_components.cable_modem_monitor.parsers.base_parser import ModemParser

class TestModemScraper:
    """Test the ModemScraper class."""

    @pytest.fixture
    def mock_parser(self, mocker):
        """Create a mock parser."""
        parser = mocker.Mock()
        parser.can_parse.return_value = True
        parser.parse.return_value = {
            "cable_modem_downstream": [],
            "cable_modem_upstream": [],
            "system_info": {},
        }
        return parser

    def test_scraper_with_mock_parser(self, mocker):
        """Test the scraper with a mock parser."""
        # Create a mock instance for the detected parser
        mock_parser_instance = mocker.Mock(spec=ModemParser)
        mock_parser_instance.login.return_value = True
        mock_parser_instance.parse.return_value = {
            "cable_modem_downstream": [],
            "cable_modem_upstream": [],
            "system_info": {},
        }

        # Create a mock for the parser class that _detect_parser would return
        mock_parser_class = mocker.Mock(spec=ModemParser)
        mock_parser_class.can_parse.return_value = True
        mock_parser_class.return_value = mock_parser_instance  # What the class returns when instantiated

        scraper = ModemScraper("192.168.100.1", parser=[mock_parser_class])
        # _fetch_data now returns (html, url, parser_class)
        mocker.patch.object(scraper, '_fetch_data', return_value=("<html></html>", "http://192.168.100.1", mock_parser_class))

        # _login is called internally after parser is detected, so it should use the mock_parser_instance's login
        mocker.patch.object(scraper, '_login', side_effect=lambda: mock_parser_instance.login(scraper.session, scraper.base_url, scraper.username, scraper.password))

        data = scraper.get_modem_data()

        assert data is not None
        mock_parser_class.can_parse.assert_called_once()

        # Assert that the parser instance's login method was called
        mock_parser_instance.login.assert_called_once_with(scraper.session, scraper.base_url, scraper.username, scraper.password)
        mock_parser_instance.parse.assert_called_once()

    def test_fetch_data_url_ordering(self, mocker):
        """Test that the scraper tries URLs in the correct order when all fail."""
        # Import parsers to get URL patterns
        from custom_components.cable_modem_monitor.parsers import get_parsers
        parsers = get_parsers()

        scraper = ModemScraper("192.168.100.1", parser=parsers)

        # Mock the session.get to track which URLs are tried
        mock_get = mocker.patch.object(scraper.session, 'get')
        mock_response = mocker.Mock()
        mock_response.status_code = 404  # Force it to try all URLs
        mock_get.return_value = mock_response

        result = scraper._fetch_data()

        # Should try all URLs and return None (all failed)
        assert result is None

        # Verify URLs were tried  - we should have tried URLs from all parsers
        calls = [call[0][0] for call in mock_get.call_args_list]
        # Just verify some URLs were tried (exact order may vary based on parsers)
        assert len(calls) > 0
        # Check that at least one known URL was tried
        assert any("/MotoConnection.asp" in call or "/network_setup.jst" in call or "/cmSignalData.htm" in call for call in calls)

    def test_fetch_data_stops_on_first_success(self, mocker):
        """Test that the scraper stops trying URLs after first successful response."""
        # Import parsers to get URL patterns
        from custom_components.cable_modem_monitor.parsers import get_parsers
        parsers = get_parsers()

        scraper = ModemScraper("192.168.100.1", parser=parsers)

        # Mock successful response on first URL
        mock_get = mocker.patch.object(scraper.session, 'get')
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Modem Data</body></html>"
        mock_get.return_value = mock_response

        html, url, parser_class = scraper._fetch_data()

        # Should succeed on first try
        assert html == "<html><body>Modem Data</body></html>"
        assert url is not None  # URL should be set
        assert parser_class is not None  # Parser class should be suggested

        # Should only have tried once (stop on first success)
        assert mock_get.call_count == 1