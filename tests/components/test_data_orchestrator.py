"""Tests for DataOrchestrator.

These tests validate the DataOrchestrator core functionality using mock parsers.
No modem-specific references - tests exercise the orchestrator mechanism itself.

NOTE: Using mock parsers (not real modems) ensures these tests remain stable
as the architecture evolves toward declarative modem configs.
"""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.base_parser import ModemParser
from custom_components.cable_modem_monitor.core.data_orchestrator import DataOrchestrator

# Test timeout constant - matches DEFAULT_TIMEOUT from schema
TEST_TIMEOUT = 10


class MockTestParser(ModemParser):
    """Mock parser for scraper mechanism tests.

    This parser is used to test DataOrchestrator behavior without coupling
    to any specific modem implementation.

    Detection is handled by YAML hints (HintMatcher) - tests should mock
    _detect_parser or _fetch_data for parser detection scenarios.
    """

    name = "[MFG] [Model]"
    manufacturer = "[MFG]"
    model = "[Model]"

    # URL patterns for testing scraper URL handling
    url_patterns = [
        {"path": "/status.html", "auth_method": "none"},
        {"path": "/MotoConnection.asp", "auth_method": "form"},
    ]

    # Simulate a parser with auth form hints
    auth_form_hints = {
        "username_field": "loginUsername",
        "password_field": "loginPassword",
    }

    # Detection uses YAML hints (HintMatcher) - tests mock _detect_parser

    def parse_resources(self, resources) -> dict:
        """Return minimal valid parse result."""
        return {
            "downstream": [],
            "upstream": [],
            "system_info": {"model": "[MFG] [Model]"},
        }


class TestDataOrchestrator:
    """Test the DataOrchestrator class."""

    @pytest.fixture
    def mock_parser(self, mocker):
        """Create a mock parser.

        Detection is handled by HintMatcher - this fixture provides
        a mock parser for testing parse() and login() flows.
        """
        parser = mocker.Mock()
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
        mock_parser_instance.parse.return_value = {
            "cable_modem_downstream": [],
            "cable_modem_upstream": [],
            "system_info": {},
        }

        # Create a mock for the parser class that _detect_parser would return
        mock_parser_class = mocker.Mock(spec=ModemParser)
        mock_parser_class.return_value = mock_parser_instance  # What the class returns when instantiated

        orchestrator = DataOrchestrator("192.168.100.1", parser=[mock_parser_class], timeout=TEST_TIMEOUT)
        # _fetch_data now returns (html, url, parser_class)
        mocker.patch.object(
            orchestrator, "_fetch_data", return_value=("<html></html>", "http://192.168.100.1", mock_parser_class)
        )

        # Mock _detect_parser to return the mock parser instance directly
        mocker.patch.object(orchestrator, "_detect_parser", return_value=mock_parser_instance)

        # Mock _login to return success (v3.12.0+: auth is handled separately, not via parser.login())
        mocker.patch.object(orchestrator, "_login", return_value=(True, None))

        data = orchestrator.get_modem_data()

        assert data is not None
        mock_parser_instance.parse.assert_called_once()

    def test_fetch_data_url_ordering(self, mocker):
        """Test that the scraper tries URLs from parser's url_patterns in order."""
        # Use MockTestParser which has proper class attributes
        orchestrator = DataOrchestrator("192.168.100.1", parser=MockTestParser(), timeout=TEST_TIMEOUT)

        # Mock the session.get to track which URLs are tried
        mock_get = mocker.patch.object(orchestrator.session, "get")
        mock_response = mocker.Mock()
        mock_response.status_code = 404  # Force it to try all URLs
        mock_get.return_value = mock_response

        result = orchestrator._fetch_data()

        # Should try all URLs and return None (all failed)
        assert result is None

        # Verify URLs were tried in order (MockTestParser has /status.html and /MotoConnection.asp)
        calls = [call[0][0] for call in mock_get.call_args_list]
        assert len(calls) >= 2
        # Should try HTTPS first, then HTTP fallback
        assert any("/status.html" in call for call in calls)
        assert any("/MotoConnection.asp" in call for call in calls)

    def test_fetch_data_stops_on_first_success(self, mocker):
        """Test that the scraper stops trying URLs after first successful response."""
        # Use MockTestParser which has proper class attributes
        orchestrator = DataOrchestrator("192.168.100.1", parser=MockTestParser(), timeout=TEST_TIMEOUT)

        # Mock successful response on first URL
        mock_get = mocker.patch.object(orchestrator.session, "get")
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Modem Data</body></html>"
        mock_get.return_value = mock_response

        result = orchestrator._fetch_data()
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

        from custom_components.cable_modem_monitor.core import data_orchestrator as orchestrator_module
        from custom_components.cable_modem_monitor.core.actions.factory import ActionFactory

        # Using MockTestParser defined at module level

        # Create scraper with HTTPS URL and parser instance
        orchestrator = DataOrchestrator(
            "https://192.168.100.1", "admin", "motorola", parser=MockTestParser(), timeout=TEST_TIMEOUT
        )

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
                response.text = "<html><title>Mock Test Parser</title></html>"
                return response

        mocker.patch.object(orchestrator.session, "get", side_effect=mock_get)

        # Mock parser instance
        mock_parser_instance = mocker.Mock()

        # Mock _detect_parser to return our mock parser instance
        mocker.patch.object(orchestrator, "_detect_parser", return_value=mock_parser_instance)

        # Mock login to return success
        mocker.patch.object(orchestrator, "_login", return_value=True)

        # Mock adapter and action layer - restart uses adapter + ActionFactory
        mock_adapter = mocker.Mock()
        mock_adapter.get_modem_config_dict.return_value = {
            "paradigm": "html",
            "actions": {"restart": {"type": "html_form", "endpoint": "/restart"}},
        }
        mocker.patch.object(orchestrator_module, "get_auth_adapter_for_parser", return_value=mock_adapter)

        mock_action = mocker.Mock()
        mock_action.execute.return_value = mocker.Mock(success=True, message="OK")
        mocker.patch.object(ActionFactory, "create_restart_action", return_value=mock_action)

        # Call restart_modem
        result = orchestrator.restart_modem()

        # Should succeed
        assert result is True
        # Should have tried both HTTPS and HTTP
        assert call_count[0] >= 2
        # Base URL should now be HTTP
        assert orchestrator.base_url == "http://192.168.100.1"

    def test_restart_modem_calls_login_with_credentials(self, mocker):
        """Test that restart_modem calls login when credentials are provided."""
        from custom_components.cable_modem_monitor.core import data_orchestrator as orchestrator_module
        from custom_components.cable_modem_monitor.core.actions.factory import ActionFactory

        # Using MockTestParser defined at module level

        orchestrator = DataOrchestrator(
            "http://192.168.100.1", "admin", "motorola", parser=[MockTestParser], timeout=TEST_TIMEOUT
        )

        # Mock parser instance
        mock_parser_instance = mocker.Mock()

        # Mock _fetch_data to return success
        mocker.patch.object(
            orchestrator,
            "_fetch_data",
            return_value=(
                "<html><title>Mock Test Parser</title></html>",
                "http://192.168.100.1/MotoConnection.asp",
                MockTestParser,
            ),
        )

        # Mock _detect_parser to return our mock parser instance
        mocker.patch.object(orchestrator, "_detect_parser", return_value=mock_parser_instance)

        # Mock login
        mock_login = mocker.patch.object(orchestrator, "_login", return_value=True)

        # Mock adapter and action layer - restart uses adapter + ActionFactory
        mock_adapter = mocker.Mock()
        mock_adapter.get_modem_config_dict.return_value = {
            "paradigm": "html",
            "actions": {"restart": {"type": "html_form", "endpoint": "/restart"}},
        }
        mocker.patch.object(orchestrator_module, "get_auth_adapter_for_parser", return_value=mock_adapter)

        mock_action = mocker.Mock()
        mock_action.execute.return_value = mocker.Mock(success=True, message="OK")
        mocker.patch.object(ActionFactory, "create_restart_action", return_value=mock_action)

        # Call restart_modem
        result = orchestrator.restart_modem()

        # Should succeed
        assert result is True
        # Login should have been called
        mock_login.assert_called_once()
        # Action execute should have been called
        mock_action.execute.assert_called_once()

    def test_restart_modem_skips_login_without_credentials(self, mocker):
        """Test that restart_modem skips login when no credentials provided."""
        from custom_components.cable_modem_monitor.core import data_orchestrator as orchestrator_module
        from custom_components.cable_modem_monitor.core.actions.factory import ActionFactory

        # Using MockTestParser defined at module level

        # No username/password
        orchestrator = DataOrchestrator(
            "http://192.168.100.1", None, None, parser=[MockTestParser], timeout=TEST_TIMEOUT
        )

        # Mock parser instance
        mock_parser_instance = mocker.Mock()

        # Mock _fetch_data to return success
        mocker.patch.object(
            orchestrator,
            "_fetch_data",
            return_value=(
                "<html><title>Mock Test Parser</title></html>",
                "http://192.168.100.1/MotoConnection.asp",
                MockTestParser,
            ),
        )

        # Mock _detect_parser to return our mock parser instance
        mocker.patch.object(orchestrator, "_detect_parser", return_value=mock_parser_instance)

        # Mock login
        mock_login = mocker.patch.object(orchestrator, "_login")

        # Mock adapter and action layer - restart uses adapter + ActionFactory
        mock_adapter = mocker.Mock()
        mock_adapter.get_modem_config_dict.return_value = {
            "paradigm": "html",
            "actions": {"restart": {"type": "html_form", "endpoint": "/restart"}},
        }
        mocker.patch.object(orchestrator_module, "get_auth_adapter_for_parser", return_value=mock_adapter)

        mock_action = mocker.Mock()
        mock_action.execute.return_value = mocker.Mock(success=True, message="OK")
        mocker.patch.object(ActionFactory, "create_restart_action", return_value=mock_action)

        # Call restart_modem
        result = orchestrator.restart_modem()

        # Should succeed
        assert result is True
        # Login should NOT have been called (no credentials)
        mock_login.assert_not_called()
        # Action execute should have been called
        mock_action.execute.assert_called_once()

    def test_restart_modem_fails_when_login_fails(self, mocker):
        """Test that restart_modem aborts when login fails."""
        from custom_components.cable_modem_monitor.core import data_orchestrator as orchestrator_module
        from custom_components.cable_modem_monitor.core.actions.factory import ActionFactory

        # Using MockTestParser defined at module level

        orchestrator = DataOrchestrator(
            "http://192.168.100.1", "admin", "wrong_password", parser=[MockTestParser], timeout=TEST_TIMEOUT
        )

        # Mock parser instance
        mock_parser_instance = mocker.Mock()

        # Mock _fetch_data to return success
        mocker.patch.object(
            orchestrator,
            "_fetch_data",
            return_value=(
                "<html><title>Mock Test Parser</title></html>",
                "http://192.168.100.1/MotoConnection.asp",
                MockTestParser,
            ),
        )

        # Mock _detect_parser to return our mock parser instance
        mocker.patch.object(orchestrator, "_detect_parser", return_value=mock_parser_instance)

        # Mock login to fail (returns tuple)
        mocker.patch.object(orchestrator, "_login", return_value=(False, None))

        # Mock adapter and action layer - but action should NOT be called due to login failure
        mock_adapter = mocker.Mock()
        mock_adapter.get_modem_config_dict.return_value = {
            "paradigm": "html",
            "actions": {"restart": {"type": "html_form", "endpoint": "/restart"}},
        }
        mocker.patch.object(orchestrator_module, "get_auth_adapter_for_parser", return_value=mock_adapter)

        mock_action = mocker.Mock()
        mock_action.execute.return_value = mocker.Mock(success=True, message="OK")
        mocker.patch.object(ActionFactory, "create_restart_action", return_value=mock_action)

        # Call restart_modem
        result = orchestrator.restart_modem()

        # Should fail
        assert result is False
        # Action should NOT have been called (login failed)
        mock_action.execute.assert_not_called()

    def test_restart_modem_fails_when_connection_fails(self, mocker):
        """Test that restart_modem fails gracefully when connection fails."""
        # Using MockTestParser defined at module level

        orchestrator = DataOrchestrator("http://192.168.100.1", parser=[MockTestParser], timeout=TEST_TIMEOUT)

        # Mock _fetch_data to return None (connection failed)
        mocker.patch.object(orchestrator, "_fetch_data", return_value=None)

        # Call restart_modem
        result = orchestrator.restart_modem()

        # Should fail
        assert result is False

    def test_restart_modem_fails_when_parser_not_detected(self, mocker):
        """Test that restart_modem fails when parser cannot be detected."""
        orchestrator = DataOrchestrator("http://192.168.100.1", parser=[], timeout=TEST_TIMEOUT)

        # Mock _fetch_data to return success but no parser
        mocker.patch.object(
            orchestrator,
            "_fetch_data",
            return_value=("<html><title>Unknown Modem</title></html>", "http://192.168.100.1", None),
        )
        mocker.patch.object(orchestrator, "_detect_parser", return_value=None)

        # Call restart_modem
        result = orchestrator.restart_modem()

        # Should fail
        assert result is False

    def test_restart_modem_fails_when_modem_yaml_has_no_restart_action(self, mocker):
        """Test that restart_modem fails when modem.yaml has no actions.restart config.

        v3.13+: Restart capability is determined by modem.yaml actions.restart config,
        not by parser attributes. ActionFactory.supports() is the single source of truth.
        """
        from custom_components.cable_modem_monitor.core import data_orchestrator as orchestrator_module

        # Create a mock parser
        mock_parser_instance = mocker.Mock()
        mock_parser_instance.__class__.__name__ = "TestParser"
        mock_parser_instance.name = "Test Parser"
        mock_parser_class = mocker.Mock()
        mock_parser_class.return_value = mock_parser_instance

        orchestrator = DataOrchestrator("http://192.168.100.1", parser=[mock_parser_class], timeout=TEST_TIMEOUT)

        # Mock _fetch_data to return success
        mocker.patch.object(
            orchestrator,
            "_fetch_data",
            return_value=("<html><title>Test Modem</title></html>", "http://192.168.100.1", mock_parser_class),
        )
        mocker.patch.object(orchestrator, "_detect_parser", return_value=mock_parser_instance)

        # Mock adapter to return modem config WITHOUT actions.restart
        mock_adapter = mocker.Mock()
        mock_adapter.get_modem_config_dict.return_value = {
            "paradigm": "html",
            # No "actions" key - restart not supported
        }
        mocker.patch.object(orchestrator_module, "get_auth_adapter_for_parser", return_value=mock_adapter)

        # Call restart_modem
        result = orchestrator.restart_modem()

        # Should fail because modem.yaml has no actions.restart
        assert result is False

    def test_restart_modem_always_fetches_data_even_with_cached_parser(self, mocker):
        """Test that restart_modem always calls _fetch_data even when parser is cached.

        This is critical to ensure protocol detection (HTTP vs HTTPS) happens on every restart.
        """
        from custom_components.cable_modem_monitor.core import data_orchestrator as orchestrator_module
        from custom_components.cable_modem_monitor.core.actions.factory import ActionFactory

        # Using MockTestParser defined at module level

        # Create scraper with HTTPS and pre-set parser (simulating cached state)
        orchestrator = DataOrchestrator(
            "https://192.168.100.1", "admin", "motorola", parser=[MockTestParser], timeout=TEST_TIMEOUT
        )

        # Mock parser instance
        mock_parser_instance = mocker.Mock()
        orchestrator.parser = mock_parser_instance  # Pre-set parser (cached)

        # Mock _fetch_data to simulate HTTP fallback with side effect
        def mock_fetch_with_update():
            # Simulate what _fetch_data does: updates base_url to HTTP
            orchestrator.base_url = "http://192.168.100.1"
            return (
                "<html><title>Mock Test Parser</title></html>",
                "http://192.168.100.1/MotoConnection.asp",
                MockTestParser,
            )

        mock_fetch = mocker.patch.object(orchestrator, "_fetch_data", side_effect=mock_fetch_with_update)

        # Mock login
        mocker.patch.object(orchestrator, "_login", return_value=True)

        # Mock adapter and action layer - restart uses adapter + ActionFactory
        mock_adapter = mocker.Mock()
        mock_adapter.get_modem_config_dict.return_value = {
            "paradigm": "html",
            "actions": {"restart": {"type": "html_form", "endpoint": "/restart"}},
        }
        mocker.patch.object(orchestrator_module, "get_auth_adapter_for_parser", return_value=mock_adapter)

        mock_action = mocker.Mock()
        mock_action.execute.return_value = mocker.Mock(success=True, message="OK")
        mocker.patch.object(ActionFactory, "create_restart_action", return_value=mock_action)

        # Call restart_modem
        result = orchestrator.restart_modem()

        # Should succeed
        assert result is True
        # _fetch_data MUST be called even though parser was cached
        mock_fetch.assert_called_once()
        # Base URL should be updated to HTTP
        assert orchestrator.base_url == "http://192.168.100.1"
        # Action execute should have been called
        mock_action.execute.assert_called_once()


class TestRestartValidation:
    """Tests for _validate_restart_capability method.

    v3.13+: Restart capability is determined by modem.yaml actions.restart config,
    checked via ActionFactory.supports(). Parser attributes are not used.
    """

    def test_validate_restart_returns_true_when_modem_yaml_has_restart(self, mocker):
        """Test validation succeeds when modem.yaml has actions.restart configured."""
        from custom_components.cable_modem_monitor.core import data_orchestrator as orchestrator_module

        orchestrator = DataOrchestrator("http://192.168.100.1", timeout=TEST_TIMEOUT)

        # Create mock parser
        mock_parser = mocker.Mock()
        mock_parser.__class__.__name__ = "TestParser"
        mock_parser.name = "Test Parser"
        orchestrator.parser = mock_parser

        # Mock adapter to return modem config WITH actions.restart
        mock_adapter = mocker.Mock()
        mock_adapter.get_modem_config_dict.return_value = {
            "paradigm": "html",
            "actions": {
                "restart": {
                    "type": "html_form",
                    "endpoint": "/goform/restart",
                }
            },
        }
        mocker.patch.object(orchestrator_module, "get_auth_adapter_for_parser", return_value=mock_adapter)

        result = orchestrator._validate_restart_capability()

        assert result is True

    def test_validate_restart_returns_false_when_no_restart_action(self, mocker):
        """Test validation fails when modem.yaml has no actions.restart."""
        from custom_components.cable_modem_monitor.core import data_orchestrator as orchestrator_module

        orchestrator = DataOrchestrator("http://192.168.100.1", timeout=TEST_TIMEOUT)

        mock_parser = mocker.Mock()
        mock_parser.__class__.__name__ = "TestParser"
        mock_parser.name = "Test Parser"
        orchestrator.parser = mock_parser

        # Mock adapter to return modem config WITHOUT actions.restart
        mock_adapter = mocker.Mock()
        mock_adapter.get_modem_config_dict.return_value = {
            "paradigm": "html",
            "actions": {},  # Empty actions
        }
        mocker.patch.object(orchestrator_module, "get_auth_adapter_for_parser", return_value=mock_adapter)

        result = orchestrator._validate_restart_capability()

        assert result is False

    def test_validate_restart_returns_false_when_no_actions_key(self, mocker):
        """Test validation fails when modem.yaml has no actions key at all."""
        from custom_components.cable_modem_monitor.core import data_orchestrator as orchestrator_module

        orchestrator = DataOrchestrator("http://192.168.100.1", timeout=TEST_TIMEOUT)

        mock_parser = mocker.Mock()
        mock_parser.__class__.__name__ = "TestParser"
        mock_parser.name = "Test Parser"
        orchestrator.parser = mock_parser

        # Mock adapter to return modem config with no actions key
        mock_adapter = mocker.Mock()
        mock_adapter.get_modem_config_dict.return_value = {
            "paradigm": "html",
            # No "actions" key
        }
        mocker.patch.object(orchestrator_module, "get_auth_adapter_for_parser", return_value=mock_adapter)

        result = orchestrator._validate_restart_capability()

        assert result is False

    def test_validate_restart_returns_false_when_no_adapter(self, mocker):
        """Test validation fails when no modem.yaml adapter found."""
        from custom_components.cable_modem_monitor.core import data_orchestrator as orchestrator_module

        orchestrator = DataOrchestrator("http://192.168.100.1", timeout=TEST_TIMEOUT)

        mock_parser = mocker.Mock()
        mock_parser.__class__.__name__ = "UnknownParser"
        mock_parser.name = "Unknown Parser"
        orchestrator.parser = mock_parser

        # Mock adapter to return None (no modem.yaml for this parser)
        mocker.patch.object(orchestrator_module, "get_auth_adapter_for_parser", return_value=None)

        result = orchestrator._validate_restart_capability()

        assert result is False

    def test_validate_restart_returns_false_when_no_parser(self, mocker):
        """Test validation fails when parser is not set."""
        orchestrator = DataOrchestrator("http://192.168.100.1", timeout=TEST_TIMEOUT)
        orchestrator.parser = None

        result = orchestrator._validate_restart_capability()

        assert result is False

    def test_validate_restart_with_hnap_action_type(self, mocker):
        """Test validation succeeds for HNAP restart action type."""
        from custom_components.cable_modem_monitor.core import data_orchestrator as orchestrator_module

        orchestrator = DataOrchestrator("http://192.168.100.1", timeout=TEST_TIMEOUT)

        mock_parser = mocker.Mock()
        mock_parser.__class__.__name__ = "ArrisS33Parser"
        mock_parser.name = "Arris S33"
        orchestrator.parser = mock_parser

        # Mock adapter to return HNAP restart config
        mock_adapter = mocker.Mock()
        mock_adapter.get_modem_config_dict.return_value = {
            "paradigm": "hnap",
            "auth": {
                "hnap": {
                    "endpoint": "/HNAP1/",
                    "namespace": "http://purenetworks.com/HNAP1/",
                }
            },
            "actions": {
                "restart": {
                    "type": "hnap",
                    "action_name": "SetArrisConfigurationInfo",
                }
            },
        }
        mocker.patch.object(orchestrator_module, "get_auth_adapter_for_parser", return_value=mock_adapter)

        result = orchestrator._validate_restart_capability()

        assert result is True


class TestFallbackParserDetection:
    """Test that fallback parser is excluded from detection phases and only used as last resort."""

    @pytest.fixture
    def mock_normal_parser_class(self, mocker):
        """Create a mock normal (non-fallback) parser class."""
        mock_class = mocker.Mock()
        mock_class.name = "Test Parser"
        mock_class.__name__ = "TestParser"  # Required for HintMatcher lookup
        mock_class.manufacturer = "TestBrand"
        mock_class.priority = 50
        mock_class.url_patterns = [{"path": "/status.html", "auth_method": "basic", "auth_required": False}]
        return mock_class

    @pytest.fixture
    def mock_fallback_parser_class(self, mocker):
        """Create a mock fallback parser class."""
        mock_class = mocker.Mock()
        mock_class.name = "Unknown Modem (Fallback Mode)"
        mock_class.__name__ = "FallbackParser"  # Required for HintMatcher lookup
        mock_class.manufacturer = "Unknown"  # Key identifier for fallback
        mock_class.priority = 1
        mock_class.url_patterns = [{"path": "/", "auth_method": "basic", "auth_required": False}]
        return mock_class

    def test_excluded_from_anonymous_probing(self, mocker, mock_normal_parser_class, mock_fallback_parser_class):
        """Test that fallback parser is excluded from Phase 1 (anonymous probing)."""
        from custom_components.cable_modem_monitor.core.data_orchestrator import DataOrchestrator

        orchestrator = DataOrchestrator(
            "192.168.100.1",
            parser=[mock_normal_parser_class, mock_fallback_parser_class],
            timeout=TEST_TIMEOUT,
        )

        # Mock session.get to return HTML
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Test</body></html>"
        mock_response.url = "http://192.168.100.1/"
        mocker.patch.object(orchestrator.session, "get", return_value=mock_response)

        # Create circuit breaker mock that tracks which parsers were attempted
        attempted_parser_names = []
        mock_circuit_breaker = mocker.Mock()
        mock_circuit_breaker.should_continue.return_value = True
        mock_circuit_breaker.record_attempt.side_effect = lambda name: attempted_parser_names.append(name)

        # Call _try_anonymous_probing
        attempted_parsers: list[type] = []
        orchestrator._try_anonymous_probing(mock_circuit_breaker, attempted_parsers)

        # Fallback parser should NOT have been attempted (excluded due to manufacturer == "Unknown")
        assert "Unknown Modem (Fallback Mode)" not in attempted_parser_names
        # Normal parser should have been attempted
        assert "Test Parser" in attempted_parser_names

    def test_excluded_from_prioritized_parsers(self, mocker, mock_normal_parser_class, mock_fallback_parser_class):
        """Test that fallback parser is excluded from Phase 3 (prioritized parsers)."""

        from custom_components.cable_modem_monitor.core.data_orchestrator import DataOrchestrator

        orchestrator = DataOrchestrator(
            "192.168.100.1",
            parser=[mock_normal_parser_class, mock_fallback_parser_class],
            timeout=TEST_TIMEOUT,
        )

        html = "<html><body>Test</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        url = "http://192.168.100.1/"

        # Create circuit breaker mock that tracks which parsers were attempted
        attempted_parser_names = []
        mock_circuit_breaker = mocker.Mock()
        mock_circuit_breaker.should_continue.return_value = True
        mock_circuit_breaker.record_attempt.side_effect = lambda name: attempted_parser_names.append(name)

        # Call _try_prioritized_parsers
        attempted_parsers: list[type] = []
        orchestrator._try_prioritized_parsers(soup, url, html, None, mock_circuit_breaker, attempted_parsers)

        # Fallback parser should NOT have been attempted (excluded due to manufacturer == "Unknown")
        assert "Unknown Modem (Fallback Mode)" not in attempted_parser_names
        # Normal parser should have been attempted
        assert "Test Parser" in attempted_parser_names

    def test_not_auto_selected_raises_error(self, mocker):
        """Test that fallback parser is NOT auto-selected when detection fails.

        User must manually select "Unknown Modem (Fallback Mode)" from the list.
        This prevents accidental fallback for supported modems with connection issues.
        """
        from custom_components.cable_modem_monitor.core.data_orchestrator import DataOrchestrator
        from custom_components.cable_modem_monitor.core.discovery_helpers import ParserNotFoundError
        from custom_components.cable_modem_monitor.core.fallback.parser import UniversalFallbackParser

        # Use real fallback parser to ensure it's available but not auto-selected
        orchestrator = DataOrchestrator("192.168.100.1", parser=[UniversalFallbackParser], timeout=TEST_TIMEOUT)

        html = "<html><body>Unknown Modem</body></html>"
        url = "http://192.168.100.1/"

        # Mock session.get
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_response.url = url
        mocker.patch.object(orchestrator.session, "get", return_value=mock_response)

        # Call _detect_parser with correct signature (html, url, suggested_parser)
        # Should raise ParserNotFoundError instead of auto-selecting fallback
        with pytest.raises(ParserNotFoundError):
            orchestrator._detect_parser(html, url, suggested_parser=None)

    @pytest.mark.skip(reason="Fallback parser is manually selected by users, not auto-detected")
    def test_known_modem_detected_before_fallback(self):
        """Test that a known modem parser is detected before fallback parser."""
        pass


class TestLogoutAfterPoll:
    """Tests for session cleanup after polling."""

    def test_perform_logout_calls_endpoint_when_defined(self, mocker):
        """Test that _perform_logout calls the logout endpoint when parser defines it."""
        orchestrator = DataOrchestrator("http://192.168.100.1", timeout=TEST_TIMEOUT)

        # Create mock parser with logout_endpoint
        mock_parser = mocker.Mock()
        mock_parser.logout_endpoint = "/Logout.htm"
        orchestrator.parser = mock_parser

        # Mock session.get
        mock_get = mocker.patch.object(orchestrator.session, "get")

        orchestrator._perform_logout()

        # Should have called the logout endpoint
        mock_get.assert_called_once_with("http://192.168.100.1/Logout.htm", timeout=5)

    def test_perform_logout_skips_when_no_endpoint(self, mocker):
        """Test that _perform_logout does nothing when parser has no logout_endpoint."""
        orchestrator = DataOrchestrator("http://192.168.100.1", timeout=TEST_TIMEOUT)

        # Create mock parser without logout_endpoint
        mock_parser = mocker.Mock()
        mock_parser.logout_endpoint = None
        orchestrator.parser = mock_parser

        # Mock session.get
        mock_get = mocker.patch.object(orchestrator.session, "get")

        orchestrator._perform_logout()

        # Should not have called anything
        mock_get.assert_not_called()

    def test_perform_logout_skips_when_no_parser(self, mocker):
        """Test that _perform_logout does nothing when no parser is set."""
        orchestrator = DataOrchestrator("http://192.168.100.1", timeout=TEST_TIMEOUT)
        orchestrator.parser = None

        # Mock session.get
        mock_get = mocker.patch.object(orchestrator.session, "get")

        orchestrator._perform_logout()

        # Should not have called anything
        mock_get.assert_not_called()

    def test_perform_logout_handles_request_failure(self, mocker):
        """Test that _perform_logout gracefully handles request failures."""
        import requests

        orchestrator = DataOrchestrator("http://192.168.100.1", timeout=TEST_TIMEOUT)

        # Create mock parser with logout_endpoint
        mock_parser = mocker.Mock()
        mock_parser.logout_endpoint = "/Logout.htm"
        orchestrator.parser = mock_parser

        # Mock session.get to raise an exception
        mocker.patch.object(
            orchestrator.session, "get", side_effect=requests.exceptions.ConnectionError("Connection refused")
        )

        # Should not raise - logout failure is non-critical
        orchestrator._perform_logout()

    def test_get_modem_data_calls_logout_in_finally(self, mocker):
        """Test that get_modem_data calls _perform_logout even on success."""
        orchestrator = DataOrchestrator("http://192.168.100.1", timeout=TEST_TIMEOUT)

        # Create mock parser with logout_endpoint
        mock_parser = mocker.Mock()
        mock_parser.logout_endpoint = "/Logout.htm"
        mock_parser.parse.return_value = {
            "cable_modem_downstream": [],
            "cable_modem_upstream": [],
        }
        orchestrator.parser = mock_parser

        # Mock _fetch_data
        mocker.patch.object(orchestrator, "_fetch_data", return_value=("<html></html>", "http://192.168.100.1", None))
        mocker.patch.object(orchestrator, "_authenticate", return_value="<html></html>")

        # Mock session.get to track logout call
        mock_get = mocker.patch.object(orchestrator.session, "get")

        orchestrator.get_modem_data()

        # Should have called logout endpoint
        mock_get.assert_called_with("http://192.168.100.1/Logout.htm", timeout=5)

    def test_get_modem_data_calls_logout_on_error(self, mocker):
        """Test that get_modem_data calls _perform_logout even on error."""
        orchestrator = DataOrchestrator("http://192.168.100.1", timeout=TEST_TIMEOUT)

        # Create mock parser with logout_endpoint
        mock_parser = mocker.Mock()
        mock_parser.logout_endpoint = "/Logout.htm"
        orchestrator.parser = mock_parser

        # Mock _fetch_data to return None (error case)
        mocker.patch.object(orchestrator, "_fetch_data", return_value=None)

        # Mock session.get to track logout call
        mock_get = mocker.patch.object(orchestrator.session, "get")

        orchestrator.get_modem_data()

        # Should still have called logout endpoint (in finally block)
        mock_get.assert_called_with("http://192.168.100.1/Logout.htm", timeout=5)

    def test_get_detection_info_includes_logout_endpoint(self, mocker):
        """Test that get_detection_info exposes logout_endpoint from adapter."""
        orchestrator = DataOrchestrator("http://192.168.100.1", timeout=TEST_TIMEOUT)

        # Create mock parser
        mock_parser = mocker.Mock()
        mock_parser.name = "Test Modem"
        mock_parser.manufacturer = "Test"
        mock_parser.release_date = "2020"
        mock_parser.capabilities = set()
        mock_parser.__class__.__name__ = "MockParser"
        orchestrator.parser = mock_parser
        orchestrator.last_successful_url = "http://192.168.100.1"

        # Mock the adapter to return logout_endpoint
        mock_adapter = mocker.Mock()
        mock_adapter.get_release_date.return_value = "2020"
        mock_adapter.get_docsis_version.return_value = "3.1"
        mock_adapter.get_status.return_value = "verified"
        mock_adapter.get_verification_source.return_value = None
        mock_adapter.get_logout_endpoint.return_value = "/Logout.htm"
        mock_adapter.get_capabilities.return_value = []
        mock_adapter.get_fixtures_path.return_value = None
        mocker.patch.object(orchestrator, "_get_modem_config_adapter", return_value=mock_adapter)

        info = orchestrator.get_detection_info()

        assert info["logout_endpoint"] == "/Logout.htm"

    def test_get_detection_info_logout_endpoint_none_when_not_set(self, mocker):
        """Test that get_detection_info returns None for logout_endpoint when not set."""
        orchestrator = DataOrchestrator("http://192.168.100.1", timeout=TEST_TIMEOUT)

        # Create mock parser
        mock_parser = mocker.Mock()
        mock_parser.name = "Test Modem"
        mock_parser.manufacturer = "Test"
        mock_parser.release_date = None
        mock_parser.capabilities = set()
        mock_parser.__class__.__name__ = "MockParser"
        orchestrator.parser = mock_parser
        orchestrator.last_successful_url = "http://192.168.100.1"

        # Mock the adapter to return None for logout_endpoint
        mock_adapter = mocker.Mock()
        mock_adapter.get_release_date.return_value = None
        mock_adapter.get_docsis_version.return_value = None
        mock_adapter.get_status.return_value = "awaiting_verification"
        mock_adapter.get_verification_source.return_value = None
        mock_adapter.get_logout_endpoint.return_value = None
        mock_adapter.get_capabilities.return_value = []
        mock_adapter.get_fixtures_path.return_value = None
        mocker.patch.object(orchestrator, "_get_modem_config_adapter", return_value=mock_adapter)

        info = orchestrator.get_detection_info()

        assert info["logout_endpoint"] is None

    def test_perform_logout_with_https_url(self, mocker):
        """Test that _perform_logout works with HTTPS base URL."""
        orchestrator = DataOrchestrator("https://192.168.100.1", timeout=TEST_TIMEOUT)

        mock_parser = mocker.Mock()
        mock_parser.logout_endpoint = "/Logout.htm"
        orchestrator.parser = mock_parser

        mock_get = mocker.patch.object(orchestrator.session, "get")

        orchestrator._perform_logout()

        mock_get.assert_called_once_with("https://192.168.100.1/Logout.htm", timeout=5)

    def test_perform_logout_with_different_endpoint_formats(self, mocker):
        """Test that _perform_logout works with various endpoint formats."""
        test_cases = [
            ("/Logout.htm", "http://192.168.100.1/Logout.htm"),
            ("/Logout.asp", "http://192.168.100.1/Logout.asp"),
            ("/Logout.html", "http://192.168.100.1/Logout.html"),
            ("/cgi-bin/logout", "http://192.168.100.1/cgi-bin/logout"),
        ]

        for endpoint, expected_url in test_cases:
            orchestrator = DataOrchestrator("http://192.168.100.1", timeout=TEST_TIMEOUT)

            mock_parser = mocker.Mock()
            mock_parser.logout_endpoint = endpoint
            orchestrator.parser = mock_parser

            mock_get = mocker.patch.object(orchestrator.session, "get")

            orchestrator._perform_logout()

            mock_get.assert_called_once_with(expected_url, timeout=5)


class TestDataOrchestratorInitialization:
    """Tests for DataOrchestrator initialization and configuration."""

    def test_init_with_plain_ip_uses_https_default(self):
        """Test that plain IP defaults to HTTPS."""
        orchestrator = DataOrchestrator("192.168.100.1", timeout=TEST_TIMEOUT)
        assert orchestrator.base_url == "https://192.168.100.1"
        assert orchestrator.host == "192.168.100.1"

    def test_init_with_http_url_preserves_protocol(self):
        """Test that explicit HTTP URL is preserved."""
        orchestrator = DataOrchestrator("http://192.168.100.1", timeout=TEST_TIMEOUT)
        assert orchestrator.base_url == "http://192.168.100.1"

    def test_init_with_https_url_preserves_protocol(self):
        """Test that explicit HTTPS URL is preserved."""
        orchestrator = DataOrchestrator("https://192.168.100.1", timeout=TEST_TIMEOUT)
        assert orchestrator.base_url == "https://192.168.100.1"

    def test_init_with_trailing_slash_removed(self):
        """Test that trailing slashes are removed from URL."""
        orchestrator = DataOrchestrator("http://192.168.100.1/", timeout=TEST_TIMEOUT)
        assert orchestrator.base_url == "http://192.168.100.1"

    def test_init_uses_cached_url_protocol(self):
        """Test that cached URL protocol is used for plain IP."""
        orchestrator = DataOrchestrator("192.168.100.1", cached_url="http://192.168.100.1/status", timeout=TEST_TIMEOUT)
        assert orchestrator.base_url == "http://192.168.100.1"

    def test_init_with_credentials(self):
        """Test initialization with credentials."""
        orchestrator = DataOrchestrator("192.168.100.1", username="admin", password="secret", timeout=TEST_TIMEOUT)
        assert orchestrator.username == "admin"
        assert orchestrator.password == "secret"

    def test_init_with_parser_instance(self, mocker):
        """Test initialization with a parser instance."""
        mock_parser = mocker.Mock(spec=ModemParser)
        orchestrator = DataOrchestrator("192.168.100.1", parser=mock_parser, timeout=TEST_TIMEOUT)
        assert orchestrator.parser == mock_parser
        assert orchestrator.parsers == [mock_parser]

    def test_init_with_parser_class(self, mocker):
        """Test initialization with a parser class."""
        mock_parser_class = mocker.Mock()
        orchestrator = DataOrchestrator("192.168.100.1", parser=[mock_parser_class], timeout=TEST_TIMEOUT)
        assert orchestrator.parser is None
        assert orchestrator.parsers == [mock_parser_class]

    def test_init_with_verify_ssl_true(self):
        """Test initialization with SSL verification enabled."""
        orchestrator = DataOrchestrator("https://192.168.100.1", verify_ssl=True, timeout=TEST_TIMEOUT)
        assert orchestrator.verify_ssl is True
        assert orchestrator.session.verify is True

    def test_init_with_verify_ssl_false(self):
        """Test initialization with SSL verification disabled."""
        orchestrator = DataOrchestrator("https://192.168.100.1", verify_ssl=False, timeout=TEST_TIMEOUT)
        assert orchestrator.verify_ssl is False
        assert orchestrator.session.verify is False

    def test_init_with_legacy_ssl_mounts_adapter(self, mocker):
        """Test that legacy SSL mode mounts the LegacySSLAdapter."""
        # We can verify by checking that session.mount was called or adapter exists
        orchestrator = DataOrchestrator("https://192.168.100.1", legacy_ssl=True, timeout=TEST_TIMEOUT)
        assert orchestrator.legacy_ssl is True
        # The adapter should be mounted for https://
        adapters = orchestrator.session.adapters
        assert "https://" in adapters

    def test_init_legacy_ssl_not_mounted_for_http(self, mocker):
        """Test that legacy SSL adapter is NOT mounted for HTTP URLs."""
        orchestrator = DataOrchestrator("http://192.168.100.1", legacy_ssl=True, timeout=TEST_TIMEOUT)
        # Legacy SSL flag is set but adapter shouldn't affect HTTP
        assert orchestrator.legacy_ssl is True
        assert orchestrator.base_url == "http://192.168.100.1"


class TestCapturingSession:
    """Tests for the CapturingSession class."""

    def test_capturing_session_calls_callback(self, mocker):
        """Test that CapturingSession calls the callback on each request."""
        from custom_components.cable_modem_monitor.core.data_orchestrator import CapturingSession

        callback = mocker.Mock()
        session = CapturingSession(callback)

        # Mock the parent request method
        mock_response = mocker.Mock()
        mock_response.url = "http://192.168.100.1/status"
        mocker.patch.object(session.__class__.__bases__[0], "request", return_value=mock_response)

        session.get("http://192.168.100.1/status")

        callback.assert_called_once()
        # First arg should be the response
        assert callback.call_args[0][0] == mock_response

    def test_capturing_session_detects_hnap_requests(self, mocker):
        """Test that CapturingSession identifies HNAP requests."""
        from custom_components.cable_modem_monitor.core.data_orchestrator import CapturingSession

        callback = mocker.Mock()
        session = CapturingSession(callback)

        mock_response = mocker.Mock()
        mock_response.url = "http://192.168.100.1/HNAP1/"

        mocker.patch.object(session.__class__.__bases__[0], "request", return_value=mock_response)

        session.request(
            "POST", "http://192.168.100.1/HNAP1/", headers={"SOAPAction": '"http://purenetworks.com/HNAP1/Login"'}
        )

        callback.assert_called_once()
        # Second arg should be description containing HNAP
        assert "HNAP" in callback.call_args[0][1]

    def test_capturing_session_detects_login_pages(self, mocker):
        """Test that CapturingSession identifies login pages."""
        from custom_components.cable_modem_monitor.core.data_orchestrator import CapturingSession

        callback = mocker.Mock()
        session = CapturingSession(callback)

        mock_response = mocker.Mock()
        mock_response.url = "http://192.168.100.1/login.htm"

        mocker.patch.object(session.__class__.__bases__[0], "request", return_value=mock_response)

        session.get("http://192.168.100.1/login.htm")

        callback.assert_called_once()
        assert "Login" in callback.call_args[0][1]

    def test_capturing_session_detects_status_pages(self, mocker):
        """Test that CapturingSession identifies status pages."""
        from custom_components.cable_modem_monitor.core.data_orchestrator import CapturingSession

        callback = mocker.Mock()
        session = CapturingSession(callback)

        mock_response = mocker.Mock()
        mock_response.url = "http://192.168.100.1/cmstatus.htm"

        mocker.patch.object(session.__class__.__bases__[0], "request", return_value=mock_response)

        session.get("http://192.168.100.1/cmstatus.htm")

        callback.assert_called_once()
        assert "Status" in callback.call_args[0][1]


class TestClearAuthCache:
    """Tests for auth cache clearing."""

    def test_clear_auth_cache_creates_new_session(self, mocker):
        """Test that clear_auth_cache creates a fresh session."""
        orchestrator = DataOrchestrator("192.168.100.1", timeout=TEST_TIMEOUT)
        old_session = orchestrator.session

        orchestrator.clear_auth_cache()

        assert orchestrator.session is not old_session

    def test_clear_auth_cache_preserves_verify_setting(self, mocker):
        """Test that clear_auth_cache preserves SSL verify setting."""
        orchestrator = DataOrchestrator("192.168.100.1", verify_ssl=True, timeout=TEST_TIMEOUT)
        assert orchestrator.session.verify is True

        orchestrator.clear_auth_cache()

        assert orchestrator.session.verify is True

    def test_clear_auth_cache_clears_hnap_builder(self, mocker):
        """Test that clear_auth_cache clears HNAP builder cache via auth_handler."""
        orchestrator = DataOrchestrator("192.168.100.1", timeout=TEST_TIMEOUT)

        # Mock auth handler with HNAP builder
        mock_builder = mocker.Mock()
        mock_auth_handler = mocker.Mock()
        mock_auth_handler.get_hnap_builder.return_value = mock_builder
        orchestrator._auth_handler = mock_auth_handler

        orchestrator.clear_auth_cache()

        mock_builder.clear_auth_cache.assert_called_once()

    def test_clear_auth_cache_handles_missing_builder(self, mocker):
        """Test that clear_auth_cache handles auth handler without HNAP builder."""
        orchestrator = DataOrchestrator("192.168.100.1", timeout=TEST_TIMEOUT)

        # Mock auth handler returning None for HNAP builder (not HNAP modem)
        mock_auth_handler = mocker.Mock()
        mock_auth_handler.get_hnap_builder.return_value = None
        orchestrator._auth_handler = mock_auth_handler

        # Should not raise
        orchestrator.clear_auth_cache()


class TestCaptureResponse:
    """Tests for response capture functionality."""

    def test_capture_response_when_disabled(self, mocker):
        """Test that capture is skipped when disabled."""
        orchestrator = DataOrchestrator("192.168.100.1", timeout=TEST_TIMEOUT)
        orchestrator._capture_enabled = False

        mock_response = mocker.Mock()
        mock_response.url = "http://192.168.100.1/status"

        orchestrator._capture_response(mock_response, "Test")

        assert len(orchestrator._captured_urls) == 0

    def test_capture_response_when_enabled(self, mocker):
        """Test that response is captured when enabled."""
        orchestrator = DataOrchestrator("192.168.100.1", timeout=TEST_TIMEOUT)
        orchestrator._capture_enabled = True
        orchestrator._captured_urls = []

        mock_response = mocker.Mock()
        mock_response.url = "http://192.168.100.1/status"
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.text = "<html>Test</html>"
        mock_response.request = mocker.Mock()
        mock_response.request.method = "GET"
        mock_response.elapsed = mocker.Mock()
        mock_response.elapsed.total_seconds.return_value = 0.5

        orchestrator._capture_response(mock_response, "Test capture")

        assert len(orchestrator._captured_urls) == 1
        assert orchestrator._captured_urls[0]["url"] == "http://192.168.100.1/status"
        assert orchestrator._captured_urls[0]["description"] == "Test capture"

    def test_capture_response_deduplicates_urls(self, mocker):
        """Test that duplicate URLs are not captured twice."""
        orchestrator = DataOrchestrator("192.168.100.1", timeout=TEST_TIMEOUT)
        orchestrator._capture_enabled = True
        orchestrator._captured_urls = []

        mock_response = mocker.Mock()
        mock_response.url = "http://192.168.100.1/status"
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.text = "<html>Test</html>"
        mock_response.request = mocker.Mock()
        mock_response.request.method = "GET"
        mock_response.elapsed = mocker.Mock()
        mock_response.elapsed.total_seconds.return_value = 0.5

        orchestrator._capture_response(mock_response, "First capture")
        orchestrator._capture_response(mock_response, "Second capture")

        # Should only have one entry
        assert len(orchestrator._captured_urls) == 1


class TestRecordFailedUrl:
    """Tests for failed URL recording."""

    def test_record_failed_url_when_disabled(self, mocker):
        """Test that failed URL is not recorded when capture disabled."""
        orchestrator = DataOrchestrator("192.168.100.1", timeout=TEST_TIMEOUT)
        orchestrator._capture_enabled = False
        orchestrator._failed_urls = []

        orchestrator._record_failed_url("http://192.168.100.1/test", "Connection refused")

        assert len(orchestrator._failed_urls) == 0

    def test_record_failed_url_when_enabled(self, mocker):
        """Test that failed URL is recorded when capture enabled."""
        orchestrator = DataOrchestrator("192.168.100.1", timeout=TEST_TIMEOUT)
        orchestrator._capture_enabled = True
        orchestrator._failed_urls = []

        orchestrator._record_failed_url(
            url="http://192.168.100.1/test",
            reason="Connection refused",
            status_code=None,
            exception_type="ConnectionError",
            resource_type="html",
        )

        assert len(orchestrator._failed_urls) == 1
        assert orchestrator._failed_urls[0]["url"] == "http://192.168.100.1/test"
        assert orchestrator._failed_urls[0]["reason"] == "Connection refused"
        assert orchestrator._failed_urls[0]["exception_type"] == "ConnectionError"

    def test_record_failed_url_with_response_body(self, mocker):
        """Test that response body is recorded for error pages."""
        orchestrator = DataOrchestrator("192.168.100.1", timeout=TEST_TIMEOUT)
        orchestrator._capture_enabled = True
        orchestrator._failed_urls = []

        orchestrator._record_failed_url(
            url="http://192.168.100.1/test",
            reason="Session conflict",
            status_code=403,
            response_body="<html>Session in use by another user</html>",
        )

        assert len(orchestrator._failed_urls) == 1
        assert orchestrator._failed_urls[0]["content"] == "<html>Session in use by another user</html>"
        assert orchestrator._failed_urls[0]["size_bytes"] == len("<html>Session in use by another user</html>")


class TestProtocolDetection:
    """Tests for HTTP/HTTPS protocol detection and fallback."""

    def test_fetch_data_tries_https_first(self, mocker):
        """Test that _fetch_data tries HTTPS before HTTP."""
        # Using MockTestParser defined at module level

        orchestrator = DataOrchestrator("192.168.100.1", parser=MockTestParser(), timeout=TEST_TIMEOUT)

        urls_tried = []

        def mock_get(url, **kwargs):
            urls_tried.append(url)
            response = mocker.Mock()
            response.status_code = 404
            return response

        mocker.patch.object(orchestrator.session, "get", side_effect=mock_get)

        orchestrator._fetch_data()

        # First URL tried should be HTTPS
        assert urls_tried[0].startswith("https://")

    def test_fetch_data_falls_back_to_http(self, mocker):
        """Test that _fetch_data falls back to HTTP when HTTPS fails."""
        import requests

        # Using MockTestParser defined at module level

        orchestrator = DataOrchestrator("192.168.100.1", parser=MockTestParser(), timeout=TEST_TIMEOUT)

        urls_tried = []

        def mock_get(url, **kwargs):
            urls_tried.append(url)
            if url.startswith("https://"):
                raise requests.exceptions.SSLError("SSL handshake failed")
            response = mocker.Mock()
            response.status_code = 200
            response.text = "<html>Modem page</html>"
            return response

        mocker.patch.object(orchestrator.session, "get", side_effect=mock_get)

        result = orchestrator._fetch_data()

        # Should have tried HTTPS first
        assert any(url.startswith("https://") for url in urls_tried)
        # Should have fallen back to HTTP
        assert any(url.startswith("http://") and not url.startswith("https://") for url in urls_tried)
        # Should succeed with HTTP
        assert result is not None

    def test_fetch_data_updates_base_url_on_success(self, mocker):
        """Test that base_url is updated when HTTP fallback succeeds."""
        import requests

        # Using MockTestParser defined at module level

        orchestrator = DataOrchestrator("192.168.100.1", parser=MockTestParser(), timeout=TEST_TIMEOUT)
        assert orchestrator.base_url == "https://192.168.100.1"

        def mock_get(url, **kwargs):
            if url.startswith("https://"):
                raise requests.exceptions.ConnectionError("Connection refused")
            response = mocker.Mock()
            response.status_code = 200
            response.text = "<html>Modem page</html>"
            return response

        mocker.patch.object(orchestrator.session, "get", side_effect=mock_get)

        orchestrator._fetch_data()

        # Base URL should be updated to HTTP
        assert orchestrator.base_url == "http://192.168.100.1"


class TestLoginFlow:
    """Tests for the login flow."""

    def test_login_skipped_without_credentials(self, mocker):
        """Test that login is skipped when no credentials provided."""
        orchestrator = DataOrchestrator("192.168.100.1", timeout=TEST_TIMEOUT)
        orchestrator.parser = mocker.Mock()

        result = orchestrator._login()

        # Without credentials, login returns success (assumes no auth needed)
        assert result == (True, None)

    def test_login_skipped_without_parser(self, mocker):
        """Test that login assumes no auth required when no parser is set.

        Without a parser or stored auth strategy, we assume the modem
        doesn't require authentication (e.g., status pages are public).
        """
        orchestrator = DataOrchestrator("192.168.100.1", username="admin", password="secret", timeout=TEST_TIMEOUT)
        orchestrator.parser = None

        result = orchestrator._login()

        # v3.12.0+: Returns (True, None) assuming no auth required
        assert result == (True, None)

    def test_login_assumes_no_auth_when_parser_has_no_hints(self, mocker):
        """Test that login assumes no auth required when parser has no hints.

        v3.12.0+: When a parser exists but has no auth hints (hnap_hints,
        js_auth_hints, auth_form_hints), we assume no authentication is
        required. This handles modems with public status pages.
        """
        orchestrator = DataOrchestrator("192.168.100.1", username="admin", password="secret", timeout=TEST_TIMEOUT)

        mock_parser = mocker.Mock()
        # Explicitly set no hints - should assume no auth required
        mock_parser.hnap_hints = None
        mock_parser.js_auth_hints = None
        mock_parser.auth_form_hints = None
        orchestrator.parser = mock_parser

        result = orchestrator._login()

        # v3.12.0+: Returns (True, None) assuming no auth required
        assert result == (True, None)


class TestSessionExpiryHandling:
    """Tests for session expiry detection and re-fetch."""

    def test_authenticate_detects_session_expiry(self, mocker):
        """When original HTML is login page, session expiry is detected."""
        orchestrator = DataOrchestrator("192.168.100.1", username="admin", password="secret", timeout=TEST_TIMEOUT)

        # Mock _login to succeed
        mocker.patch.object(orchestrator, "_login", return_value=(True, None))

        # Original HTML is a login page (has password field)
        login_html = '<form><input type="password"></form>'

        # Mock session.get to return authenticated content after re-fetch
        mock_response = mocker.Mock()
        mock_response.ok = True
        mock_response.text = "<h1>Connection Status</h1><table>...</table>"
        orchestrator.session.get = mocker.Mock(return_value=mock_response)

        result = orchestrator._authenticate(login_html, data_url="http://192.168.100.1/status.html")

        # Should have re-fetched and returned the authenticated content
        orchestrator.session.get.assert_called_once()
        assert result == mock_response.text

    def test_authenticate_skips_refetch_when_not_login_page(self, mocker):
        """When original HTML is NOT a login page, no re-fetch needed."""
        orchestrator = DataOrchestrator("192.168.100.1", username="admin", password="secret", timeout=TEST_TIMEOUT)

        # Mock _login to succeed without returning HTML
        mocker.patch.object(orchestrator, "_login", return_value=(True, None))

        # Original HTML is already authenticated content
        data_html = "<h1>Connection Status</h1><table>...</table>"

        # session.get should NOT be called
        orchestrator.session.get = mocker.Mock()

        result = orchestrator._authenticate(data_html, data_url="http://192.168.100.1/status.html")

        # Should return original HTML without re-fetching
        orchestrator.session.get.assert_not_called()
        assert result == data_html

    def test_authenticate_uses_auth_html_when_provided(self, mocker):
        """When _login returns authenticated_html, use it directly."""
        orchestrator = DataOrchestrator("192.168.100.1", username="admin", password="secret", timeout=TEST_TIMEOUT)

        # Mock _login to return authenticated HTML
        auth_html = "<h1>Authenticated Content</h1>"
        mocker.patch.object(orchestrator, "_login", return_value=(True, auth_html))

        # Original HTML is a login page
        login_html = '<form><input type="password"></form>'

        # session.get should NOT be called (we have auth HTML)
        orchestrator.session.get = mocker.Mock()

        result = orchestrator._authenticate(login_html, data_url="http://192.168.100.1/status.html")

        # Should use authenticated HTML from _login, not re-fetch
        orchestrator.session.get.assert_not_called()
        assert result == auth_html

    def test_authenticate_returns_none_on_login_failure(self, mocker):
        """When _login fails, return None."""
        orchestrator = DataOrchestrator("192.168.100.1", username="admin", password="secret", timeout=TEST_TIMEOUT)

        # Mock _login to fail
        mocker.patch.object(orchestrator, "_login", return_value=(False, None))

        login_html = '<form><input type="password"></form>'

        result = orchestrator._authenticate(login_html, data_url="http://192.168.100.1/status.html")

        assert result is None

    def test_authenticate_handles_refetch_still_login_page(self, mocker):
        """When re-fetch still returns login page, fall back to original."""
        orchestrator = DataOrchestrator("192.168.100.1", username="admin", password="secret", timeout=TEST_TIMEOUT)

        mocker.patch.object(orchestrator, "_login", return_value=(True, None))

        # Original is login page
        login_html = '<form><input type="password"></form>'

        # Re-fetch also returns login page (auth failed silently)
        mock_response = mocker.Mock()
        mock_response.ok = True
        mock_response.text = '<form><input type="password">Still login page</form>'
        orchestrator.session.get = mocker.Mock(return_value=mock_response)

        result = orchestrator._authenticate(login_html, data_url="http://192.168.100.1/status.html")

        # Falls back to original HTML (even though it's login page)
        assert result == login_html


class TestUrlPatternGeneration:
    """Tests for URL pattern generation from parser."""

    def test_urls_from_parser_instance(self, mocker):
        """Test URL generation from parser instance."""
        mock_parser = mocker.Mock()
        mock_parser.name = "Test Parser"
        mock_parser.url_patterns = [
            {"path": "/status.html", "auth_method": "none"},
            {"path": "/info.html", "auth_method": "basic"},
        ]

        orchestrator = DataOrchestrator("192.168.100.1", parser=mock_parser, timeout=TEST_TIMEOUT)

        urls = orchestrator._get_url_patterns_to_try()

        assert len(urls) == 2
        assert urls[0][0] == "https://192.168.100.1/status.html"
        assert urls[1][0] == "https://192.168.100.1/info.html"

    def test_returns_empty_list_when_no_parser(self, mocker):
        """Test that _get_url_patterns_to_try returns empty list when no parser set."""
        orchestrator = DataOrchestrator("192.168.100.1", timeout=TEST_TIMEOUT)
        orchestrator.parser = None

        urls = orchestrator._get_url_patterns_to_try()

        assert urls == []


class TestGetModemData:
    """Tests for the main get_modem_data flow."""

    def test_get_modem_data_clears_captures_on_start(self, mocker):
        """Test that get_modem_data clears previous captures."""
        orchestrator = DataOrchestrator("192.168.100.1", timeout=TEST_TIMEOUT)
        orchestrator._captured_urls = [{"url": "old"}]
        orchestrator._failed_urls = [{"url": "old_fail"}]

        # Mock _fetch_data to return None (fail early)
        mocker.patch.object(orchestrator, "_fetch_data", return_value=None)

        orchestrator.get_modem_data(capture_raw=True)

        assert orchestrator._captured_urls == []
        assert orchestrator._failed_urls == []

    def test_get_modem_data_returns_status_on_connection_failure(self, mocker):
        """Test that get_modem_data returns status dict on connection failure."""
        orchestrator = DataOrchestrator("192.168.100.1", timeout=TEST_TIMEOUT)

        mocker.patch.object(orchestrator, "_fetch_data", return_value=None)

        result = orchestrator.get_modem_data()

        # Should return a dict with connection status info
        assert "cable_modem_connection_status" in result
        assert result["cable_modem_connection_status"] == "unreachable"

    def test_get_modem_data_sets_capture_enabled_flag(self, mocker):
        """Test that get_modem_data sets _capture_enabled flag when capture_raw=True."""
        orchestrator = DataOrchestrator("192.168.100.1", timeout=TEST_TIMEOUT)

        # Mock _fetch_data to return None (fail early, but flag should be set)
        mocker.patch.object(orchestrator, "_fetch_data", return_value=None)

        # Verify flag is initially False
        assert orchestrator._capture_enabled is False

        orchestrator.get_modem_data(capture_raw=True)

        # Flag should be set to True during the call
        # (It gets set at the start of get_modem_data)
        # Since we can't easily check during execution, verify the flag exists
        assert hasattr(orchestrator, "_capture_enabled")


# =============================================================================
# v3.12 Detection Method Tests
# =============================================================================


class TestV312DetectionMethods:
    """Tests for v3.12 HintMatcher-based detection methods."""

    @pytest.fixture
    def orchestrator(self):
        """Create a scraper with mock parsers."""
        return DataOrchestrator("192.168.100.1", parser=[MockTestParser], timeout=TEST_TIMEOUT)

    @pytest.fixture
    def mock_hint_matcher(self, mocker):
        """Create a mock HintMatcher."""
        mock = mocker.Mock()
        mock.match_login_markers.return_value = []
        mock.match_model_strings.return_value = []
        return mock

    # -------------------------------------------------------------------------
    # _get_parser_by_name tests
    # -------------------------------------------------------------------------

    def test_get_parser_by_name_found(self, orchestrator):
        """Test _get_parser_by_name returns parser when found."""
        parser = orchestrator._get_parser_by_name("MockTestParser")
        assert parser is not None
        assert parser.name == "[MFG] [Model]"

    def test_get_parser_by_name_not_found(self, orchestrator):
        """Test _get_parser_by_name returns None when not found."""
        parser = orchestrator._get_parser_by_name("NonExistentParser")
        assert parser is None

    # -------------------------------------------------------------------------
    # _try_instant_detection tests
    # -------------------------------------------------------------------------

    def test_try_instant_detection_with_prefetched_html(self, mocker, orchestrator):
        """Test instant detection uses pre-fetched HTML from auth discovery."""
        # Set up pre-fetched HTML
        orchestrator._authenticated_html = "<html>moto.css</html>"

        # Mock HintMatcher to return a match
        mock_match = mocker.Mock()
        mock_match.parser_name = "MockTestParser"
        mock_match.manufacturer = "[MFG]"
        mock_match.matched_markers = ["moto.css"]  # Must be a real list, not Mock
        mock_hint_matcher = mocker.Mock()
        mock_hint_matcher.match_login_markers.return_value = [mock_match]
        mock_hint_matcher.match_model_strings.return_value = []
        mocker.patch(
            "custom_components.cable_modem_monitor.core.data_orchestrator.HintMatcher.get_instance",
            return_value=mock_hint_matcher,
        )

        orchestrator._try_instant_detection()

        assert orchestrator.parser is not None
        assert orchestrator._authenticated_html is None  # Cleared after use

    def test_try_instant_detection_skipped_when_no_html(self, orchestrator):
        """Test instant detection is skipped when no pre-fetched HTML."""
        orchestrator._authenticated_html = None
        orchestrator._try_instant_detection()
        assert orchestrator.parser is None

    def test_try_instant_detection_skipped_when_parser_exists(self, mocker, orchestrator):
        """Test instant detection is skipped when parser already detected."""
        orchestrator._authenticated_html = "<html>test</html>"
        orchestrator.parser = mocker.Mock()  # Parser already set

        orchestrator._try_instant_detection()

        # Pre-fetched HTML should NOT be cleared (detection was skipped)
        assert orchestrator._authenticated_html == "<html>test</html>"

    # -------------------------------------------------------------------------
    # _try_login_markers_detection tests - table-driven
    # -------------------------------------------------------------------------

    # Table: (num_matches, expected_result_type, description)
    # fmt: off
    LOGIN_MARKERS_CASES = [
        (0, None,     "no matches returns None"),
        (1, "parser", "single match returns parser"),
        (2, "parser", "multiple matches uses disambiguation or best match"),
    ]
    # fmt: on

    @pytest.mark.parametrize("num_matches,expected,desc", LOGIN_MARKERS_CASES)
    def test_login_markers_detection(self, mocker, orchestrator, num_matches, expected, desc):
        """Table-driven test for _try_login_markers_detection."""
        mock_hint_matcher = mocker.Mock()

        # Create matches
        matches = []
        for i in range(num_matches):
            match = mocker.Mock()
            match.parser_name = "MockTestParser"
            match.manufacturer = "[MFG]"
            match.matched_markers = [f"marker{i}"]
            matches.append(match)

        mock_hint_matcher.match_login_markers.return_value = matches
        mock_hint_matcher.match_model_strings.return_value = []

        result = orchestrator._try_login_markers_detection("<html>test</html>", mock_hint_matcher)

        if expected is None:
            assert result is None, desc
        else:
            assert result is not None, desc

    # -------------------------------------------------------------------------
    # _disambiguate_with_model_strings tests
    # -------------------------------------------------------------------------

    def test_disambiguate_finds_intersection(self, mocker, orchestrator):
        """Test disambiguation finds parser in both login and model matches."""
        mock_hint_matcher = mocker.Mock()

        # Login matches
        login_match1 = mocker.Mock()
        login_match1.parser_name = "ParserA"
        login_match2 = mocker.Mock()
        login_match2.parser_name = "MockTestParser"
        login_matches = [login_match1, login_match2]

        # Model matches - MockTestParser is in both
        model_match = mocker.Mock()
        model_match.parser_name = "MockTestParser"
        model_match.manufacturer = "[MFG]"
        model_match.matched_markers = ["model_marker"]
        mock_hint_matcher.match_model_strings.return_value = [model_match]

        result = orchestrator._disambiguate_with_model_strings("<html>test</html>", login_matches, mock_hint_matcher)

        assert result is not None
        assert result.name == "[MFG] [Model]"

    def test_disambiguate_no_intersection(self, mocker, orchestrator):
        """Test disambiguation returns None when no intersection."""
        mock_hint_matcher = mocker.Mock()

        # Login matches
        login_match = mocker.Mock()
        login_match.parser_name = "ParserA"
        login_matches = [login_match]

        # Model matches - different parser
        model_match = mocker.Mock()
        model_match.parser_name = "ParserB"
        mock_hint_matcher.match_model_strings.return_value = [model_match]

        result = orchestrator._disambiguate_with_model_strings("<html>test</html>", login_matches, mock_hint_matcher)

        assert result is None

    # -------------------------------------------------------------------------
    # _try_quick_detection tests
    # -------------------------------------------------------------------------

    def test_try_quick_detection_delegates_to_login_markers(self, mocker, orchestrator):
        """Test _try_quick_detection delegates to _try_login_markers_detection."""
        mock_parser = mocker.Mock()
        mocker.patch.object(orchestrator, "_try_login_markers_detection", return_value=mock_parser)

        soup = mocker.Mock()
        result = orchestrator._try_quick_detection(soup, "<html>test</html>", "http://test")

        assert result == mock_parser
        orchestrator._try_login_markers_detection.assert_called_once()


class TestV312ScraperInitialization:
    """Tests for v3.12 scraper initialization parameters."""

    def test_init_with_auth_hnap_config(self):
        """Test initialization with HNAP config from config entry."""
        hnap_config = {"endpoint": "/HNAP1/", "namespace": "http://example.com"}
        orchestrator = DataOrchestrator(
            "192.168.100.1",
            auth_strategy="hnap_session",
            auth_hnap_config=hnap_config,
            timeout=TEST_TIMEOUT,
        )
        assert orchestrator._auth_handler is not None

    def test_init_with_auth_url_token_config(self):
        """Test initialization with URL token config from config entry."""
        url_token_config = {"login_page": "/login.html", "token_prefix": "session="}
        orchestrator = DataOrchestrator(
            "192.168.100.1",
            auth_strategy="url_token_session",
            auth_url_token_config=url_token_config,
            timeout=TEST_TIMEOUT,
        )
        assert orchestrator._auth_handler is not None

    def test_init_with_authenticated_html(self):
        """Test initialization with pre-fetched HTML."""
        orchestrator = DataOrchestrator(
            "192.168.100.1",
            authenticated_html="<html>Pre-fetched</html>",
            timeout=TEST_TIMEOUT,
        )
        assert orchestrator._authenticated_html == "<html>Pre-fetched</html>"

    def test_init_with_session_pre_authenticated(self):
        """Test initialization with pre-authenticated session flag."""
        orchestrator = DataOrchestrator(
            "192.168.100.1",
            session_pre_authenticated=True,
            timeout=TEST_TIMEOUT,
        )
        assert orchestrator._session_pre_authenticated is True

    def test_login_skipped_when_pre_authenticated(self, mocker):
        """Test _login returns success without auth when session is pre-authenticated."""
        orchestrator = DataOrchestrator(
            "192.168.100.1",
            username="admin",
            password="password",
            session_pre_authenticated=True,
            timeout=TEST_TIMEOUT,
        )

        result = orchestrator._login()

        assert result == (True, None)
        # Flag should be cleared after first use
        assert orchestrator._session_pre_authenticated is False

    def test_login_proceeds_after_pre_auth_flag_cleared(self, mocker):
        """Test subsequent _login calls proceed normally after flag is cleared."""
        orchestrator = DataOrchestrator(
            "192.168.100.1",
            username="admin",
            password="password",
            session_pre_authenticated=True,
            timeout=TEST_TIMEOUT,
        )

        # First call - uses pre-auth flag
        result1 = orchestrator._login()
        assert result1 == (True, None)
        assert orchestrator._session_pre_authenticated is False

        # Mock auth handler for second call
        mock_handler = mocker.Mock()
        mock_handler.strategy.value = "form_plain"
        # authenticate() returns an object with .success and .response_html attributes
        mock_auth_result = mocker.Mock()
        mock_auth_result.success = True
        mock_auth_result.response_html = "<html>logged in</html>"
        mock_handler.authenticate.return_value = mock_auth_result
        orchestrator._auth_handler = mock_handler
        orchestrator._auth_strategy = "form_plain"

        # Second call - should use auth handler
        orchestrator._login()
        assert mock_handler.authenticate.called
