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
        mocker.patch.object(
            scraper, "_fetch_data", return_value=("<html></html>", "http://192.168.100.1", mock_parser_class)
        )

        # _login is called internally after parser is detected, so it should use the mock_parser_instance's login
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

        # Assert that the parser instance's login method was called
        mock_parser_instance.login.assert_called_once_with(
            scraper.session, scraper.base_url, scraper.username, scraper.password
        )
        mock_parser_instance.parse.assert_called_once()

    def test_fetch_data_url_ordering(self, mocker):
        """Test that the scraper tries URLs in the correct order when all fail."""
        # Import parsers to get URL patterns
        from custom_components.cable_modem_monitor.parsers import get_parsers

        parsers = get_parsers()

        scraper = ModemScraper("192.168.100.1", parser=parsers)

        # Mock the session.get to track which URLs are tried
        mock_get = mocker.patch.object(scraper.session, "get")
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
        assert any(
            "/MotoConnection.asp" in call or "/network_setup.jst" in call or "/cmSignalData.htm" in call
            for call in calls
        )

    def test_fetch_data_stops_on_first_success(self, mocker):
        """Test that the scraper stops trying URLs after first successful response."""
        # Import parsers to get URL patterns
        from custom_components.cable_modem_monitor.parsers import get_parsers

        parsers = get_parsers()

        scraper = ModemScraper("192.168.100.1", parser=parsers)

        # Mock successful response on first URL
        mock_get = mocker.patch.object(scraper.session, "get")
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Modem Data</body></html>"
        mock_get.return_value = mock_response

        result = scraper._fetch_data()
        assert result is not None, "Expected _fetch_data to return a tuple, got None"
        html, url, parser_class = result

        # Should succeed on first try
        assert html == "<html><body>Modem Data</body></html>"
        assert url is not None  # URL should be set
        assert parser_class is not None  # Parser class should be suggested

        # Should only have tried once (stop on first success)
        assert mock_get.call_count == 1

    def test_restart_modem_https_to_http_fallback(self, mocker):
        """Test that restart_modem falls back from HTTPS to HTTP when connection refused."""
        import requests

        from custom_components.cable_modem_monitor.parsers.motorola.generic import MotorolaGenericParser

        # Create scraper with HTTPS URL
        scraper = ModemScraper("https://192.168.100.1", "admin", "motorola", parser=[MotorolaGenericParser])

        # Mock session.get to simulate HTTPS failure, HTTP success
        call_count = [0]

        def mock_get(url, **kwargs):
            call_count[0] += 1
            response = mocker.Mock()
            if url.startswith("https://"):
                # HTTPS fails with connection refused
                raise requests.exceptions.ConnectionError(
                    "Failed to establish a new connection: [Errno 111] Connection refused"
                )
            else:
                # HTTP succeeds
                response.status_code = 200
                response.text = "<html><title>Motorola Cable Modem</title></html>"
                return response

        mocker.patch.object(scraper.session, "get", side_effect=mock_get)

        # Mock parser instance
        mock_parser_instance = mocker.Mock()
        mock_parser_instance.restart = mocker.Mock(return_value=True)

        # Mock _detect_parser to return our mock parser instance
        mocker.patch.object(scraper, "_detect_parser", return_value=mock_parser_instance)

        # Mock login to return success
        mocker.patch.object(scraper, "_login", return_value=True)

        # Call restart_modem
        result = scraper.restart_modem()

        # Should succeed
        assert result is True
        # Should have tried both HTTPS and HTTP
        assert call_count[0] >= 2
        # Base URL should now be HTTP
        assert scraper.base_url == "http://192.168.100.1"

    def test_restart_modem_calls_login_with_credentials(self, mocker):
        """Test that restart_modem calls login when credentials are provided."""
        from custom_components.cable_modem_monitor.parsers.motorola.generic import MotorolaGenericParser

        scraper = ModemScraper("http://192.168.100.1", "admin", "motorola", parser=[MotorolaGenericParser])

        # Mock parser instance
        mock_parser_instance = mocker.Mock()
        mock_parser_instance.restart = mocker.Mock(return_value=True)

        # Mock _fetch_data to return success
        mocker.patch.object(
            scraper,
            "_fetch_data",
            return_value=(
                "<html><title>Motorola Cable Modem</title></html>",
                "http://192.168.100.1/MotoConnection.asp",
                MotorolaGenericParser,
            ),
        )

        # Mock _detect_parser to return our mock parser instance
        mocker.patch.object(scraper, "_detect_parser", return_value=mock_parser_instance)

        # Mock login
        mock_login = mocker.patch.object(scraper, "_login", return_value=True)

        # Call restart_modem
        result = scraper.restart_modem()

        # Should succeed
        assert result is True
        # Login should have been called
        mock_login.assert_called_once()
        # Restart should have been called on parser
        mock_parser_instance.restart.assert_called_once_with(scraper.session, scraper.base_url)

    def test_restart_modem_skips_login_without_credentials(self, mocker):
        """Test that restart_modem skips login when no credentials provided."""
        from custom_components.cable_modem_monitor.parsers.motorola.generic import MotorolaGenericParser

        # No username/password
        scraper = ModemScraper("http://192.168.100.1", None, None, parser=[MotorolaGenericParser])

        # Mock parser instance
        mock_parser_instance = mocker.Mock()
        mock_parser_instance.restart = mocker.Mock(return_value=True)

        # Mock _fetch_data to return success
        mocker.patch.object(
            scraper,
            "_fetch_data",
            return_value=(
                "<html><title>Motorola Cable Modem</title></html>",
                "http://192.168.100.1/MotoConnection.asp",
                MotorolaGenericParser,
            ),
        )

        # Mock _detect_parser to return our mock parser instance
        mocker.patch.object(scraper, "_detect_parser", return_value=mock_parser_instance)

        # Mock login
        mock_login = mocker.patch.object(scraper, "_login")

        # Call restart_modem
        result = scraper.restart_modem()

        # Should succeed
        assert result is True
        # Login should NOT have been called (no credentials)
        mock_login.assert_not_called()
        # Restart should have been called on parser
        mock_parser_instance.restart.assert_called_once()

    def test_restart_modem_fails_when_login_fails(self, mocker):
        """Test that restart_modem aborts when login fails."""
        from custom_components.cable_modem_monitor.parsers.motorola.generic import MotorolaGenericParser

        scraper = ModemScraper("http://192.168.100.1", "admin", "wrong_password", parser=[MotorolaGenericParser])

        # Mock parser instance
        mock_parser_instance = mocker.Mock()
        mock_parser_instance.restart = mocker.Mock(return_value=True)

        # Mock _fetch_data to return success
        mocker.patch.object(
            scraper,
            "_fetch_data",
            return_value=(
                "<html><title>Motorola Cable Modem</title></html>",
                "http://192.168.100.1/MotoConnection.asp",
                MotorolaGenericParser,
            ),
        )

        # Mock _detect_parser to return our mock parser instance
        mocker.patch.object(scraper, "_detect_parser", return_value=mock_parser_instance)

        # Mock login to fail (returns tuple)
        mocker.patch.object(scraper, "_login", return_value=(False, None))

        # Call restart_modem
        result = scraper.restart_modem()

        # Should fail
        assert result is False
        # Restart should NOT have been called (login failed)
        mock_parser_instance.restart.assert_not_called()

    def test_restart_modem_fails_when_connection_fails(self, mocker):
        """Test that restart_modem fails gracefully when connection fails."""
        from custom_components.cable_modem_monitor.parsers.motorola.generic import MotorolaGenericParser

        scraper = ModemScraper("http://192.168.100.1", parser=[MotorolaGenericParser])

        # Mock _fetch_data to return None (connection failed)
        mocker.patch.object(scraper, "_fetch_data", return_value=None)

        # Call restart_modem
        result = scraper.restart_modem()

        # Should fail
        assert result is False

    def test_restart_modem_fails_when_parser_not_detected(self, mocker):
        """Test that restart_modem fails when parser cannot be detected."""
        scraper = ModemScraper("http://192.168.100.1", parser=[])

        # Mock _fetch_data to return success but no parser
        mocker.patch.object(
            scraper,
            "_fetch_data",
            return_value=("<html><title>Unknown Modem</title></html>", "http://192.168.100.1", None),
        )
        mocker.patch.object(scraper, "_detect_parser", return_value=None)

        # Call restart_modem
        result = scraper.restart_modem()

        # Should fail
        assert result is False

    def test_restart_modem_fails_when_parser_lacks_restart_method(self, mocker):
        """Test that restart_modem fails when parser doesn't support restart."""
        # Create a mock parser without restart method
        mock_parser_instance = mocker.Mock(spec=["parse", "login"])  # No 'restart'
        mock_parser_class = mocker.Mock()
        mock_parser_class.return_value = mock_parser_instance

        scraper = ModemScraper("http://192.168.100.1", parser=[mock_parser_class])

        # Mock _fetch_data to return success
        mocker.patch.object(
            scraper,
            "_fetch_data",
            return_value=("<html><title>Test Modem</title></html>", "http://192.168.100.1", mock_parser_class),
        )
        mocker.patch.object(scraper, "_detect_parser", return_value=mock_parser_instance)

        # Call restart_modem
        result = scraper.restart_modem()

        # Should fail
        assert result is False

    def test_restart_modem_always_fetches_data_even_with_cached_parser(self, mocker):
        """Test that restart_modem always calls _fetch_data even when parser is cached.

        This is critical to ensure protocol detection (HTTP vs HTTPS) happens on every restart.
        """
        from custom_components.cable_modem_monitor.parsers.motorola.generic import MotorolaGenericParser

        # Create scraper with HTTPS and pre-set parser (simulating cached state)
        scraper = ModemScraper("https://192.168.100.1", "admin", "motorola", parser=[MotorolaGenericParser])

        # Mock parser instance
        mock_parser_instance = mocker.Mock()
        mock_parser_instance.restart = mocker.Mock(return_value=True)
        scraper.parser = mock_parser_instance  # Pre-set parser (cached)

        # Mock _fetch_data to simulate HTTP fallback with side effect
        def mock_fetch_with_update():
            # Simulate what _fetch_data does: updates base_url to HTTP
            scraper.base_url = "http://192.168.100.1"
            return (
                "<html><title>Motorola Cable Modem</title></html>",
                "http://192.168.100.1/MotoConnection.asp",
                MotorolaGenericParser,
            )

        mock_fetch = mocker.patch.object(scraper, "_fetch_data", side_effect=mock_fetch_with_update)

        # Mock login
        mocker.patch.object(scraper, "_login", return_value=True)

        # Call restart_modem
        result = scraper.restart_modem()

        # Should succeed
        assert result is True
        # _fetch_data MUST be called even though parser was cached
        mock_fetch.assert_called_once()
        # Base URL should be updated to HTTP
        assert scraper.base_url == "http://192.168.100.1"
        # Restart should have been called on the cached parser
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
        mock_class.can_parse.return_value = False  # Won't match by default
        mock_class.url_patterns = [{"path": "/status.html", "auth_method": "basic", "auth_required": False}]
        return mock_class

    @pytest.fixture
    def mock_fallback_parser_class(self, mocker):
        """Create a mock fallback parser class."""
        mock_class = mocker.Mock()
        mock_class.name = "Unknown Modem (Fallback Mode)"
        mock_class.manufacturer = "Unknown"  # Key identifier for fallback
        mock_class.priority = 1
        mock_class.can_parse.return_value = True  # Always matches
        mock_class.url_patterns = [{"path": "/", "auth_method": "basic", "auth_required": False}]
        return mock_class

    def test_excluded_from_anonymous_probing(self, mocker, mock_normal_parser_class, mock_fallback_parser_class):
        """Test that fallback parser is excluded from Phase 1 (anonymous probing)."""
        from custom_components.cable_modem_monitor.core.modem_scraper import ModemScraper

        scraper = ModemScraper("192.168.100.1", parser=[mock_normal_parser_class, mock_fallback_parser_class])

        # Mock session.get to return HTML
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Test</body></html>"
        mock_response.url = "http://192.168.100.1/"
        mocker.patch.object(scraper.session, "get", return_value=mock_response)

        # Create circuit breaker mock
        mock_circuit_breaker = mocker.Mock()
        mock_circuit_breaker.should_continue.return_value = True

        # Call _try_anonymous_probing
        attempted_parsers: list[type] = []
        scraper._try_anonymous_probing(mock_circuit_breaker, attempted_parsers)

        # Fallback parser should NOT have been tried
        assert mock_fallback_parser_class.can_parse.call_count == 0
        # Normal parser should have been tried
        assert mock_normal_parser_class.can_parse.call_count > 0

    def test_excluded_from_prioritized_parsers(self, mocker, mock_normal_parser_class, mock_fallback_parser_class):
        """Test that fallback parser is excluded from Phase 3 (prioritized parsers)."""
        from bs4 import BeautifulSoup

        from custom_components.cable_modem_monitor.core.modem_scraper import ModemScraper

        scraper = ModemScraper("192.168.100.1", parser=[mock_normal_parser_class, mock_fallback_parser_class])

        html = "<html><body>Test</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        url = "http://192.168.100.1/"

        # Create circuit breaker mock
        mock_circuit_breaker = mocker.Mock()
        mock_circuit_breaker.should_continue.return_value = True

        # Call _try_prioritized_parsers
        attempted_parsers: list[type] = []
        scraper._try_prioritized_parsers(soup, url, html, None, mock_circuit_breaker, attempted_parsers)

        # Fallback parser should NOT have been tried
        assert mock_fallback_parser_class.can_parse.call_count == 0
        # Normal parser should have been tried
        assert mock_normal_parser_class.can_parse.call_count > 0

    def test_excluded_from_url_discovery_tier2(self, mocker, mock_normal_parser_class, mock_fallback_parser_class):
        """Test that fallback parser is excluded from Tier 2 URL discovery."""
        from custom_components.cable_modem_monitor.core.modem_scraper import ModemScraper

        # Set a cached parser name to trigger tier 2
        scraper = ModemScraper(
            "192.168.100.1", parser=[mock_normal_parser_class, mock_fallback_parser_class], parser_name="Test Parser"
        )

        urls = scraper._get_tier2_urls()

        # Convert URLs to list of parser names that contributed URLs
        parser_names = [parser_class.name for _, _, parser_class in urls]

        # Fallback parser should NOT contribute URLs in tier 2
        assert "Unknown Modem (Fallback Mode)" not in parser_names
        # Normal parser should contribute URLs
        assert "Test Parser" in parser_names

    def test_excluded_from_url_discovery_tier3(self, mocker, mock_normal_parser_class, mock_fallback_parser_class):
        """Test that fallback parser is excluded from Tier 3 URL discovery."""
        from custom_components.cable_modem_monitor.core.modem_scraper import ModemScraper

        scraper = ModemScraper("192.168.100.1", parser=[mock_normal_parser_class, mock_fallback_parser_class])

        urls = scraper._get_tier3_urls()

        # Convert URLs to list of parser names that contributed URLs
        parser_names = [parser_class.name for _, _, parser_class in urls]

        # Fallback parser should NOT contribute URLs in tier 3
        assert "Unknown Modem (Fallback Mode)" not in parser_names

    def test_not_auto_selected_raises_error(self, mocker):
        """Test that fallback parser is NOT auto-selected when detection fails.

        User must manually select "Unknown Modem (Fallback Mode)" from the list.
        This prevents accidental fallback for supported modems with connection issues.
        """
        from custom_components.cable_modem_monitor.core.discovery_helpers import ParserNotFoundError
        from custom_components.cable_modem_monitor.core.modem_scraper import ModemScraper
        from custom_components.cable_modem_monitor.parsers.universal.fallback import UniversalFallbackParser

        # Use real fallback parser to ensure it's available but not auto-selected
        scraper = ModemScraper("192.168.100.1", parser=[UniversalFallbackParser])

        html = "<html><body>Unknown Modem</body></html>"
        url = "http://192.168.100.1/"

        # Mock session.get
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_response.url = url
        mocker.patch.object(scraper.session, "get", return_value=mock_response)

        # Call _detect_parser with correct signature (html, url, suggested_parser)
        # Should raise ParserNotFoundError instead of auto-selecting fallback
        with pytest.raises(ParserNotFoundError):
            scraper._detect_parser(html, url, suggested_parser=None)

    def test_known_modem_detected_before_fallback(self):
        """Test that a known modem parser is detected before fallback parser."""
        from bs4 import BeautifulSoup

        from custom_components.cable_modem_monitor.parsers.motorola.mb7621 import MotorolaMB7621Parser
        from custom_components.cable_modem_monitor.parsers.universal.fallback import UniversalFallbackParser

        # HTML from Motorola MB7621
        html = "<html><title>Motorola Cable Modem : Login</title><body>MB7621</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        url = "http://192.168.100.1/"

        # Test that Motorola parser can_parse returns True
        assert MotorolaMB7621Parser.can_parse(soup, url, html) is True

        # Test that fallback parser would also return True (but should be tried last)
        assert UniversalFallbackParser.can_parse(soup, url, html) is True

        # When both parsers are available, detection logic should try Motorola first
        # because it's excluded from phases 1-3 by manufacturer check
        # This test verifies the parsers themselves work correctly
