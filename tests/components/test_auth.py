from __future__ import annotations

from custom_components.cable_modem_monitor.core.modem_scraper import ModemScraper
from custom_components.cable_modem_monitor.parsers.motorola.mb7621 import MotorolaMB7621Parser
from custom_components.cable_modem_monitor.parsers.technicolor.tc4400 import TechnicolorTC4400Parser


class TestAuth:
    """Test the authentication system."""

    def test_form_auth(self, mocker):
        """Test form-based authentication."""
        scraper = ModemScraper("192.168.100.1", "admin", "password", parser=[MotorolaMB7621Parser])
        ***REMOVED*** _fetch_data now returns (html, url, parser_class)
        mocker.patch.object(
            scraper, "_fetch_data", return_value=("<html></html>", "http://192.168.100.1", MotorolaMB7621Parser)
        )
        mocker.patch.object(scraper, "_detect_parser", return_value=MotorolaMB7621Parser())
        mock_login = mocker.patch.object(MotorolaMB7621Parser, "login", return_value=True)
        scraper.get_modem_data()

        mock_login.assert_called_once()

    def test_basic_auth(self, mocker):
        """Test basic HTTP authentication."""
        scraper = ModemScraper("192.168.100.1", "admin", "password", parser=[TechnicolorTC4400Parser])
        ***REMOVED*** _fetch_data now returns (html, url, parser_class)
        mocker.patch.object(
            scraper, "_fetch_data", return_value=("<html></html>", "http://192.168.100.1", TechnicolorTC4400Parser)
        )
        mocker.patch.object(scraper, "_detect_parser", return_value=TechnicolorTC4400Parser())
        mock_login = mocker.patch.object(TechnicolorTC4400Parser, "login", return_value=True)
        scraper.get_modem_data()

        mock_login.assert_called_once()
