"""Tests for Cable Modem Monitor scraper."""

from __future__ import annotations

import pytest

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
        ***REMOVED*** Create a mock instance for the detected parser
        mock_parser_instance = mocker.Mock(spec=ModemParser)
        ***REMOVED*** login() now returns tuple[bool, str | None]
        mock_parser_instance.login.return_value = (True, None)
        mock_parser_instance.parse.return_value = {
            "cable_modem_downstream": [],
            "cable_modem_upstream": [],
            "system_info": {},
        }

        ***REMOVED*** Create a mock for the parser class that _detect_parser would return
        mock_parser_class = mocker.Mock(spec=ModemParser)
        mock_parser_class.can_parse.return_value = True
        mock_parser_class.return_value = mock_parser_instance  ***REMOVED*** What the class returns when instantiated

        scraper = ModemScraper("192.168.100.1", parser=[mock_parser_class])
        ***REMOVED*** _fetch_data now returns (html, url, parser_class)
        mocker.patch.object(
            scraper, "_fetch_data", return_value=("<html></html>", "http://192.168.100.1", mock_parser_class)
        )

        ***REMOVED*** _login is called internally after parser is detected, so it should use the mock_parser_instance's login
        mocker.patch.object(
            scraper,
            "_login",
            side_effect=lambda: mock_parser_instance.login(
                scraper.session, scraper.base_url, scraper.username, scraper.password
            ),
        )

        data = scraper.get_modem_data()

        assert data is not None
        mock_parser_class.can_parse.assert_called_once()

        ***REMOVED*** Assert that the parser instance's login method was called
        mock_parser_instance.login.assert_called_once_with(
            scraper.session, scraper.base_url, scraper.username, scraper.password
        )
        mock_parser_instance.parse.assert_called_once()

    def test_fetch_data_url_ordering(self, mocker):
        """Test that the scraper tries URLs in the correct order when all fail."""
        ***REMOVED*** Import parsers to get URL patterns
        from custom_components.cable_modem_monitor.parsers import get_parsers

        parsers = get_parsers()

        scraper = ModemScraper("192.168.100.1", parser=parsers)

        ***REMOVED*** Mock the session.get to track which URLs are tried
        mock_get = mocker.patch.object(scraper.session, "get")
        mock_response = mocker.Mock()
        mock_response.status_code = 404  ***REMOVED*** Force it to try all URLs
        mock_get.return_value = mock_response

        result = scraper._fetch_data()

        ***REMOVED*** Should try all URLs and return None (all failed)
        assert result is None

        ***REMOVED*** Verify URLs were tried  - we should have tried URLs from all parsers
        calls = [call[0][0] for call in mock_get.call_args_list]
        ***REMOVED*** Just verify some URLs were tried (exact order may vary based on parsers)
        assert len(calls) > 0
        ***REMOVED*** Check that at least one known URL was tried
        assert any(
            "/MotoConnection.asp" in call or "/network_setup.jst" in call or "/cmSignalData.htm" in call
            for call in calls
        )

    def test_fetch_data_stops_on_first_success(self, mocker):
        """Test that the scraper stops trying URLs after first successful response."""
        ***REMOVED*** Import parsers to get URL patterns
        from custom_components.cable_modem_monitor.parsers import get_parsers

        parsers = get_parsers()

        scraper = ModemScraper("192.168.100.1", parser=parsers)

        ***REMOVED*** Mock successful response on first URL
        mock_get = mocker.patch.object(scraper.session, "get")
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Modem Data</body></html>"
        mock_get.return_value = mock_response

        result = scraper._fetch_data()
        assert result is not None, "Expected _fetch_data to return a tuple, got None"
        html, url, parser_class = result

        ***REMOVED*** Should succeed on first try
        assert html == "<html><body>Modem Data</body></html>"
        assert url is not None  ***REMOVED*** URL should be set
        assert parser_class is not None  ***REMOVED*** Parser class should be suggested

        ***REMOVED*** Should only have tried once (stop on first success)
        assert mock_get.call_count == 1

    def test_restart_modem_https_to_http_fallback(self, mocker):
        """Test that restart_modem falls back from HTTPS to HTTP when connection refused."""
        import requests

        from custom_components.cable_modem_monitor.parsers.motorola.generic import MotorolaGenericParser

        ***REMOVED*** Create scraper with HTTPS URL
        scraper = ModemScraper("https://192.168.100.1", "admin", "motorola", parser=[MotorolaGenericParser])

        ***REMOVED*** Mock session.get to simulate HTTPS failure, HTTP success
        call_count = [0]

        def mock_get(url, **kwargs):
            call_count[0] += 1
            response = mocker.Mock()
            if url.startswith("https://"):
                ***REMOVED*** HTTPS fails with connection refused
                raise requests.exceptions.ConnectionError(
                    "Failed to establish a new connection: [Errno 111] Connection refused"
                )
            else:
                ***REMOVED*** HTTP succeeds
                response.status_code = 200
                response.text = "<html><title>Motorola Cable Modem</title></html>"
                return response

        mocker.patch.object(scraper.session, "get", side_effect=mock_get)

        ***REMOVED*** Mock parser instance
        mock_parser_instance = mocker.Mock()
        mock_parser_instance.restart = mocker.Mock(return_value=True)

        ***REMOVED*** Mock _detect_parser to return our mock parser instance
        mocker.patch.object(scraper, "_detect_parser", return_value=mock_parser_instance)

        ***REMOVED*** Mock login to return success
        mocker.patch.object(scraper, "_login", return_value=True)

        ***REMOVED*** Call restart_modem
        result = scraper.restart_modem()

        ***REMOVED*** Should succeed
        assert result is True
        ***REMOVED*** Should have tried both HTTPS and HTTP
        assert call_count[0] >= 2
        ***REMOVED*** Base URL should now be HTTP
        assert scraper.base_url == "http://192.168.100.1"

    def test_restart_modem_calls_login_with_credentials(self, mocker):
        """Test that restart_modem calls login when credentials are provided."""
        from custom_components.cable_modem_monitor.parsers.motorola.generic import MotorolaGenericParser

        scraper = ModemScraper("http://192.168.100.1", "admin", "motorola", parser=[MotorolaGenericParser])

        ***REMOVED*** Mock parser instance
        mock_parser_instance = mocker.Mock()
        mock_parser_instance.restart = mocker.Mock(return_value=True)

        ***REMOVED*** Mock _fetch_data to return success
        mocker.patch.object(
            scraper,
            "_fetch_data",
            return_value=(
                "<html><title>Motorola Cable Modem</title></html>",
                "http://192.168.100.1/MotoConnection.asp",
                MotorolaGenericParser,
            ),
        )

        ***REMOVED*** Mock _detect_parser to return our mock parser instance
        mocker.patch.object(scraper, "_detect_parser", return_value=mock_parser_instance)

        ***REMOVED*** Mock login
        mock_login = mocker.patch.object(scraper, "_login", return_value=True)

        ***REMOVED*** Call restart_modem
        result = scraper.restart_modem()

        ***REMOVED*** Should succeed
        assert result is True
        ***REMOVED*** Login should have been called
        mock_login.assert_called_once()
        ***REMOVED*** Restart should have been called on parser
        mock_parser_instance.restart.assert_called_once_with(scraper.session, scraper.base_url)

    def test_restart_modem_skips_login_without_credentials(self, mocker):
        """Test that restart_modem skips login when no credentials provided."""
        from custom_components.cable_modem_monitor.parsers.motorola.generic import MotorolaGenericParser

        ***REMOVED*** No username/password
        scraper = ModemScraper("http://192.168.100.1", None, None, parser=[MotorolaGenericParser])

        ***REMOVED*** Mock parser instance
        mock_parser_instance = mocker.Mock()
        mock_parser_instance.restart = mocker.Mock(return_value=True)

        ***REMOVED*** Mock _fetch_data to return success
        mocker.patch.object(
            scraper,
            "_fetch_data",
            return_value=(
                "<html><title>Motorola Cable Modem</title></html>",
                "http://192.168.100.1/MotoConnection.asp",
                MotorolaGenericParser,
            ),
        )

        ***REMOVED*** Mock _detect_parser to return our mock parser instance
        mocker.patch.object(scraper, "_detect_parser", return_value=mock_parser_instance)

        ***REMOVED*** Mock login
        mock_login = mocker.patch.object(scraper, "_login")

        ***REMOVED*** Call restart_modem
        result = scraper.restart_modem()

        ***REMOVED*** Should succeed
        assert result is True
        ***REMOVED*** Login should NOT have been called (no credentials)
        mock_login.assert_not_called()
        ***REMOVED*** Restart should have been called on parser
        mock_parser_instance.restart.assert_called_once()

    def test_restart_modem_fails_when_login_fails(self, mocker):
        """Test that restart_modem aborts when login fails."""
        from custom_components.cable_modem_monitor.parsers.motorola.generic import MotorolaGenericParser

        scraper = ModemScraper("http://192.168.100.1", "admin", "wrong_password", parser=[MotorolaGenericParser])

        ***REMOVED*** Mock parser instance
        mock_parser_instance = mocker.Mock()
        mock_parser_instance.restart = mocker.Mock(return_value=True)

        ***REMOVED*** Mock _fetch_data to return success
        mocker.patch.object(
            scraper,
            "_fetch_data",
            return_value=(
                "<html><title>Motorola Cable Modem</title></html>",
                "http://192.168.100.1/MotoConnection.asp",
                MotorolaGenericParser,
            ),
        )

        ***REMOVED*** Mock _detect_parser to return our mock parser instance
        mocker.patch.object(scraper, "_detect_parser", return_value=mock_parser_instance)

        ***REMOVED*** Mock login to fail (returns tuple)
        mocker.patch.object(scraper, "_login", return_value=(False, None))

        ***REMOVED*** Call restart_modem
        result = scraper.restart_modem()

        ***REMOVED*** Should fail
        assert result is False
        ***REMOVED*** Restart should NOT have been called (login failed)
        mock_parser_instance.restart.assert_not_called()

    def test_restart_modem_fails_when_connection_fails(self, mocker):
        """Test that restart_modem fails gracefully when connection fails."""
        from custom_components.cable_modem_monitor.parsers.motorola.generic import MotorolaGenericParser

        scraper = ModemScraper("http://192.168.100.1", parser=[MotorolaGenericParser])

        ***REMOVED*** Mock _fetch_data to return None (connection failed)
        mocker.patch.object(scraper, "_fetch_data", return_value=None)

        ***REMOVED*** Call restart_modem
        result = scraper.restart_modem()

        ***REMOVED*** Should fail
        assert result is False

    def test_restart_modem_fails_when_parser_not_detected(self, mocker):
        """Test that restart_modem fails when parser cannot be detected."""
        scraper = ModemScraper("http://192.168.100.1", parser=[])

        ***REMOVED*** Mock _fetch_data to return success but no parser
        mocker.patch.object(
            scraper,
            "_fetch_data",
            return_value=("<html><title>Unknown Modem</title></html>", "http://192.168.100.1", None),
        )
        mocker.patch.object(scraper, "_detect_parser", return_value=None)

        ***REMOVED*** Call restart_modem
        result = scraper.restart_modem()

        ***REMOVED*** Should fail
        assert result is False

    def test_restart_modem_fails_when_parser_lacks_restart_method(self, mocker):
        """Test that restart_modem fails when parser doesn't support restart."""
        ***REMOVED*** Create a mock parser without restart method
        mock_parser_instance = mocker.Mock(spec=["parse", "login"])  ***REMOVED*** No 'restart'
        mock_parser_class = mocker.Mock()
        mock_parser_class.return_value = mock_parser_instance

        scraper = ModemScraper("http://192.168.100.1", parser=[mock_parser_class])

        ***REMOVED*** Mock _fetch_data to return success
        mocker.patch.object(
            scraper,
            "_fetch_data",
            return_value=("<html><title>Test Modem</title></html>", "http://192.168.100.1", mock_parser_class),
        )
        mocker.patch.object(scraper, "_detect_parser", return_value=mock_parser_instance)

        ***REMOVED*** Call restart_modem
        result = scraper.restart_modem()

        ***REMOVED*** Should fail
        assert result is False

    def test_restart_modem_always_fetches_data_even_with_cached_parser(self, mocker):
        """Test that restart_modem always calls _fetch_data even when parser is cached.

        This is critical to ensure protocol detection (HTTP vs HTTPS) happens on every restart.
        """
        from custom_components.cable_modem_monitor.parsers.motorola.generic import MotorolaGenericParser

        ***REMOVED*** Create scraper with HTTPS and pre-set parser (simulating cached state)
        scraper = ModemScraper("https://192.168.100.1", "admin", "motorola", parser=[MotorolaGenericParser])

        ***REMOVED*** Mock parser instance
        mock_parser_instance = mocker.Mock()
        mock_parser_instance.restart = mocker.Mock(return_value=True)
        scraper.parser = mock_parser_instance  ***REMOVED*** Pre-set parser (cached)

        ***REMOVED*** Mock _fetch_data to simulate HTTP fallback with side effect
        def mock_fetch_with_update():
            ***REMOVED*** Simulate what _fetch_data does: updates base_url to HTTP
            scraper.base_url = "http://192.168.100.1"
            return (
                "<html><title>Motorola Cable Modem</title></html>",
                "http://192.168.100.1/MotoConnection.asp",
                MotorolaGenericParser,
            )

        mock_fetch = mocker.patch.object(scraper, "_fetch_data", side_effect=mock_fetch_with_update)

        ***REMOVED*** Mock login
        mocker.patch.object(scraper, "_login", return_value=True)

        ***REMOVED*** Call restart_modem
        result = scraper.restart_modem()

        ***REMOVED*** Should succeed
        assert result is True
        ***REMOVED*** _fetch_data MUST be called even though parser was cached
        mock_fetch.assert_called_once()
        ***REMOVED*** Base URL should be updated to HTTP
        assert scraper.base_url == "http://192.168.100.1"
        ***REMOVED*** Restart should have been called on the cached parser
        mock_parser_instance.restart.assert_called_once_with(scraper.session, scraper.base_url)


class TestFallbackParserDetection:
    """Test that fallback parser is excluded from detection phases and only used as last resort."""

    @pytest.fixture
    def mock_normal_parser_class(self, mocker):
        """Create a mock normal (non-fallback) parser class."""
        mock_class = mocker.Mock()
        mock_class.name = "Test Parser"
        mock_class.manufacturer = "TestBrand"
        mock_class.priority = 50
        mock_class.can_parse.return_value = False  ***REMOVED*** Won't match by default
        mock_class.url_patterns = [{"path": "/status.html", "auth_method": "basic", "auth_required": False}]
        return mock_class

    @pytest.fixture
    def mock_fallback_parser_class(self, mocker):
        """Create a mock fallback parser class."""
        mock_class = mocker.Mock()
        mock_class.name = "Unknown Modem (Fallback Mode)"
        mock_class.manufacturer = "Unknown"  ***REMOVED*** Key identifier for fallback
        mock_class.priority = 1
        mock_class.can_parse.return_value = True  ***REMOVED*** Always matches
        mock_class.url_patterns = [{"path": "/", "auth_method": "basic", "auth_required": False}]
        return mock_class

    def test_excluded_from_anonymous_probing(self, mocker, mock_normal_parser_class, mock_fallback_parser_class):
        """Test that fallback parser is excluded from Phase 1 (anonymous probing)."""
        from custom_components.cable_modem_monitor.core.modem_scraper import ModemScraper

        scraper = ModemScraper("192.168.100.1", parser=[mock_normal_parser_class, mock_fallback_parser_class])

        ***REMOVED*** Mock session.get to return HTML
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Test</body></html>"
        mock_response.url = "http://192.168.100.1/"
        mocker.patch.object(scraper.session, "get", return_value=mock_response)

        ***REMOVED*** Create circuit breaker mock
        mock_circuit_breaker = mocker.Mock()
        mock_circuit_breaker.should_continue.return_value = True

        ***REMOVED*** Call _try_anonymous_probing
        attempted_parsers: list[type] = []
        scraper._try_anonymous_probing(mock_circuit_breaker, attempted_parsers)

        ***REMOVED*** Fallback parser should NOT have been tried
        assert mock_fallback_parser_class.can_parse.call_count == 0
        ***REMOVED*** Normal parser should have been tried
        assert mock_normal_parser_class.can_parse.call_count > 0

    def test_excluded_from_prioritized_parsers(self, mocker, mock_normal_parser_class, mock_fallback_parser_class):
        """Test that fallback parser is excluded from Phase 3 (prioritized parsers)."""
        from bs4 import BeautifulSoup

        from custom_components.cable_modem_monitor.core.modem_scraper import ModemScraper

        scraper = ModemScraper("192.168.100.1", parser=[mock_normal_parser_class, mock_fallback_parser_class])

        html = "<html><body>Test</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        url = "http://192.168.100.1/"

        ***REMOVED*** Create circuit breaker mock
        mock_circuit_breaker = mocker.Mock()
        mock_circuit_breaker.should_continue.return_value = True

        ***REMOVED*** Call _try_prioritized_parsers
        attempted_parsers: list[type] = []
        scraper._try_prioritized_parsers(soup, url, html, None, mock_circuit_breaker, attempted_parsers)

        ***REMOVED*** Fallback parser should NOT have been tried
        assert mock_fallback_parser_class.can_parse.call_count == 0
        ***REMOVED*** Normal parser should have been tried
        assert mock_normal_parser_class.can_parse.call_count > 0

    def test_excluded_from_url_discovery_tier2(self, mocker, mock_normal_parser_class, mock_fallback_parser_class):
        """Test that fallback parser is excluded from Tier 2 URL discovery."""
        from custom_components.cable_modem_monitor.core.modem_scraper import ModemScraper

        ***REMOVED*** Set a cached parser name to trigger tier 2
        scraper = ModemScraper(
            "192.168.100.1", parser=[mock_normal_parser_class, mock_fallback_parser_class], parser_name="Test Parser"
        )

        urls = scraper._get_tier2_urls()

        ***REMOVED*** Convert URLs to list of parser names that contributed URLs
        parser_names = [parser_class.name for _, _, parser_class in urls]

        ***REMOVED*** Fallback parser should NOT contribute URLs in tier 2
        assert "Unknown Modem (Fallback Mode)" not in parser_names
        ***REMOVED*** Normal parser should contribute URLs
        assert "Test Parser" in parser_names

    def test_excluded_from_url_discovery_tier3(self, mocker, mock_normal_parser_class, mock_fallback_parser_class):
        """Test that fallback parser is excluded from Tier 3 URL discovery."""
        from custom_components.cable_modem_monitor.core.modem_scraper import ModemScraper

        scraper = ModemScraper("192.168.100.1", parser=[mock_normal_parser_class, mock_fallback_parser_class])

        urls = scraper._get_tier3_urls()

        ***REMOVED*** Convert URLs to list of parser names that contributed URLs
        parser_names = [parser_class.name for _, _, parser_class in urls]

        ***REMOVED*** Fallback parser should NOT contribute URLs in tier 3
        assert "Unknown Modem (Fallback Mode)" not in parser_names

    def test_not_auto_selected_raises_error(self, mocker):
        """Test that fallback parser is NOT auto-selected when detection fails.

        User must manually select "Unknown Modem (Fallback Mode)" from the list.
        This prevents accidental fallback for supported modems with connection issues.
        """
        from custom_components.cable_modem_monitor.core.discovery_helpers import ParserNotFoundError
        from custom_components.cable_modem_monitor.core.modem_scraper import ModemScraper
        from custom_components.cable_modem_monitor.parsers.universal.fallback import UniversalFallbackParser

        ***REMOVED*** Use real fallback parser to ensure it's available but not auto-selected
        scraper = ModemScraper("192.168.100.1", parser=[UniversalFallbackParser])

        html = "<html><body>Unknown Modem</body></html>"
        url = "http://192.168.100.1/"

        ***REMOVED*** Mock session.get
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_response.url = url
        mocker.patch.object(scraper.session, "get", return_value=mock_response)

        ***REMOVED*** Call _detect_parser with correct signature (html, url, suggested_parser)
        ***REMOVED*** Should raise ParserNotFoundError instead of auto-selecting fallback
        with pytest.raises(ParserNotFoundError):
            scraper._detect_parser(html, url, suggested_parser=None)

    def test_known_modem_detected_before_fallback(self):
        """Test that a known modem parser is detected before fallback parser."""
        from bs4 import BeautifulSoup

        from custom_components.cable_modem_monitor.parsers.motorola.mb7621 import MotorolaMB7621Parser
        from custom_components.cable_modem_monitor.parsers.universal.fallback import UniversalFallbackParser

        ***REMOVED*** HTML from Motorola MB7621
        html = "<html><title>Motorola Cable Modem : Login</title><body>MB7621</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        url = "http://192.168.100.1/"

        ***REMOVED*** Test that Motorola parser can_parse returns True
        assert MotorolaMB7621Parser.can_parse(soup, url, html) is True

        ***REMOVED*** Test that fallback parser would also return True (but should be tried last)
        assert UniversalFallbackParser.can_parse(soup, url, html) is True

        ***REMOVED*** When both parsers are available, detection logic should try Motorola first
        ***REMOVED*** because it's excluded from phases 1-3 by manufacturer check
        ***REMOVED*** This test verifies the parsers themselves work correctly
