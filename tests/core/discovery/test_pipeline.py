"""Tests for the discovery pipeline module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from custom_components.cable_modem_monitor.core.discovery.pipeline import (
    AuthResult,
    ConnectivityResult,
    DiscoveryPipelineResult,
    ParserResult,
    ValidationResult,
    _get_parser_class_by_name,
    check_connectivity,
    detect_parser,
    discover_auth,
    run_discovery_pipeline,
    validate_parse,
)

# =============================================================================
# HELPER FUNCTIONS - Reduce mock setup boilerplate
# =============================================================================


def _create_mock_session():
    """Create a mock requests.Session with standard setup."""
    mock_session = MagicMock()
    mock_session.verify = False
    return mock_session


def _create_mock_auth_discovery_result(
    success: bool = True,
    strategy: str = "form_plain",
    response_html: str = "<html>Auth page</html>",
    form_config: dict | None = None,
    hnap_config: dict | None = None,
    url_token_config: dict | None = None,
    error_message: str | None = None,
):
    """Create a mock AuthDiscovery result with configurable fields."""
    mock_result = MagicMock()
    mock_result.success = success
    mock_result.strategy = MagicMock(value=strategy) if strategy else None
    mock_result.response_html = response_html
    mock_result.form_config = form_config
    mock_result.hnap_config = hnap_config
    mock_result.url_token_config = url_token_config
    mock_result.error_message = error_message
    return mock_result


def _create_mock_hint_matcher(
    login_matches: list[tuple[str, list[str]]] | None = None,
    model_matches: list[tuple[str, list[str]]] | None = None,
):
    """Create a mock HintMatcher with configurable matches.

    Args:
        login_matches: List of (parser_name, matched_markers) tuples for login_markers
        model_matches: List of (parser_name, matched_markers) tuples for model_strings
    """
    mock_hint_matcher = MagicMock()

    if login_matches:
        mock_login_results = []
        for parser_name, markers in login_matches:
            match = MagicMock()
            match.parser_name = parser_name
            match.matched_markers = markers
            mock_login_results.append(match)
        mock_hint_matcher.match_login_markers.return_value = mock_login_results
    else:
        mock_hint_matcher.match_login_markers.return_value = []

    if model_matches:
        mock_model_results = []
        for parser_name, markers in model_matches:
            match = MagicMock()
            match.parser_name = parser_name
            match.matched_markers = markers
            mock_model_results.append(match)
        mock_hint_matcher.match_model_strings.return_value = mock_model_results
    else:
        mock_hint_matcher.match_model_strings.return_value = []

    return mock_hint_matcher


# =============================================================================
# TABLE-DRIVEN TEST DATA
# =============================================================================

# Auth discovery test cases - each tuple:
# (strategy, success, form_config, hnap_config, url_token_config, error_msg, description)
AUTH_DISCOVERY_CASES = [
    ("form_plain", True, None, None, None, None, "basic form auth"),
    (
        "form_plain",
        True,
        {"action": "/login", "username_field": "user", "password_field": "pass"},
        None,
        None,
        None,
        "form auth with config",
    ),
    (
        "hnap_session",
        True,
        None,
        {"endpoint": "/HNAP1/", "namespace": "http://example.com"},
        {"login_page": "/login.html", "token_prefix": "s="},
        None,
        "HNAP with v3.12 configs",
    ),
    (None, False, None, None, None, "Invalid credentials", "auth discovery fails"),
]

# Parser detection test cases - each tuple:
# (login_matches, model_matches, parser_found, exp_success, exp_method, description)
PARSER_DETECTION_CASES = [
    ([("MotorolaMB7621Parser", ["moto.css"])], [], True, True, "login_markers", "login_markers"),
    ([], [("NetgearCM600Parser", ["CM600"])], True, True, "model_strings", "model_strings"),
    ([], [], False, False, None, "no parser matched"),
    ([("NonExistentParser", ["pattern"])], [], False, False, None, "parser not found"),
]


class TestConnectivityResult:
    """Test ConnectivityResult dataclass."""

    def test_default_values(self):
        """Test default values."""
        result = ConnectivityResult(success=True)
        assert result.success is True
        assert result.working_url is None
        assert result.protocol is None
        assert result.legacy_ssl is False
        assert result.error is None

    def test_with_all_values(self):
        """Test with all values set."""
        result = ConnectivityResult(
            success=True,
            working_url="http://192.168.100.1",
            protocol="http",
            legacy_ssl=False,
        )
        assert result.success is True
        assert result.working_url == "http://192.168.100.1"
        assert result.protocol == "http"


class TestAuthResult:
    """Test AuthResult dataclass."""

    def test_default_values(self):
        """Test default values."""
        result = AuthResult(success=True)
        assert result.success is True
        assert result.strategy is None
        assert result.session is None
        assert result.html is None
        assert result.form_config is None
        assert result.hnap_config is None
        assert result.url_token_config is None
        assert result.error is None

    def test_with_all_auth_configs(self):
        """Test with all v3.12 auth config fields set."""
        result = AuthResult(
            success=True,
            strategy="hnap_session",
            form_config={"action": "/login"},
            hnap_config={"endpoint": "/HNAP1/", "namespace": "http://example.com"},
            url_token_config={"login_page": "/login.html", "token_prefix": "session="},
        )
        assert result.form_config == {"action": "/login"}
        assert result.hnap_config == {"endpoint": "/HNAP1/", "namespace": "http://example.com"}
        assert result.url_token_config == {"login_page": "/login.html", "token_prefix": "session="}


class TestParserResult:
    """Test ParserResult dataclass."""

    def test_default_values(self):
        """Test default values."""
        result = ParserResult(success=True)
        assert result.success is True
        assert result.parser_class is None
        assert result.parser_name is None
        assert result.detection_method is None
        assert result.confidence == 0.0
        assert result.error is None


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_default_values(self):
        """Test default values."""
        result = ValidationResult(success=True)
        assert result.success is True
        assert result.modem_data is None
        assert result.parser_instance is None
        assert result.error is None


class TestDiscoveryPipelineResult:
    """Test DiscoveryPipelineResult dataclass."""

    def test_default_values(self):
        """Test default values."""
        result = DiscoveryPipelineResult(success=True)
        assert result.success is True
        assert result.working_url is None
        assert result.auth_strategy is None
        assert result.auth_form_config is None
        assert result.auth_hnap_config is None
        assert result.auth_url_token_config is None
        assert result.parser_name is None
        assert result.legacy_ssl is False
        assert result.modem_data == {}
        assert result.parser_instance is None
        assert result.session is None
        assert result.error is None
        assert result.failed_step is None

    def test_with_all_auth_configs(self):
        """Test with all v3.12 auth config fields set."""
        result = DiscoveryPipelineResult(
            success=True,
            working_url="http://192.168.100.1",
            auth_strategy="hnap_session",
            auth_form_config={"action": "/login"},
            auth_hnap_config={"endpoint": "/HNAP1/"},
            auth_url_token_config={"login_page": "/login.html"},
            parser_name="TestParser",
        )
        assert result.auth_form_config == {"action": "/login"}
        assert result.auth_hnap_config == {"endpoint": "/HNAP1/"}
        assert result.auth_url_token_config == {"login_page": "/login.html"}


class TestCheckConnectivity:
    """Test check_connectivity function."""

    @patch("custom_components.cable_modem_monitor.core.discovery.steps.requests.Session")
    def test_http_success(self, mock_session_class):
        """Test successful HTTP connection."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.head.return_value = mock_response

        result = check_connectivity("192.168.100.1")

        assert result.success is True
        assert result.working_url == "https://192.168.100.1"
        assert result.protocol == "https"
        assert result.legacy_ssl is False

    @patch("custom_components.cable_modem_monitor.core.discovery.steps.requests.Session")
    def test_https_fails_http_succeeds(self, mock_session_class):
        """Test HTTPS fails but HTTP succeeds."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # First call (HTTPS HEAD) fails
        # Second call (HTTPS GET) fails
        # Third call (HTTP HEAD) succeeds
        mock_session.head.side_effect = [
            requests.exceptions.ConnectionError("HTTPS failed"),
            MagicMock(status_code=200),
        ]
        mock_session.get.side_effect = requests.exceptions.ConnectionError("HTTPS GET failed")

        result = check_connectivity("192.168.100.1")

        assert result.success is True
        assert result.working_url == "http://192.168.100.1"
        assert result.protocol == "http"

    @patch("custom_components.cable_modem_monitor.core.discovery.steps.requests.Session")
    def test_head_fails_get_succeeds(self, mock_session_class):
        """Test HEAD fails but GET succeeds."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.head.side_effect = requests.RequestException("HEAD not supported")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.get.return_value = mock_response

        result = check_connectivity("192.168.100.1")

        assert result.success is True
        assert result.protocol == "https"

    @patch("custom_components.cable_modem_monitor.core.discovery.steps.requests.Session")
    def test_all_connections_fail(self, mock_session_class):
        """Test all connection attempts fail."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.head.side_effect = requests.exceptions.ConnectionError("Failed")
        mock_session.get.side_effect = requests.exceptions.ConnectionError("Failed")

        result = check_connectivity("192.168.100.1")

        assert result.success is False
        assert "Could not connect" in result.error

    @patch("custom_components.cable_modem_monitor.core.discovery.steps.requests.Session")
    def test_timeout(self, mock_session_class):
        """Test connection timeout."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.head.side_effect = requests.exceptions.Timeout("Timeout")
        mock_session.get.side_effect = requests.exceptions.Timeout("Timeout")

        result = check_connectivity("192.168.100.1")

        assert result.success is False

    @patch("custom_components.cable_modem_monitor.core.discovery.steps.requests.Session")
    def test_ssl_error_with_legacy_fallback(self, mock_session_class):
        """Test SSL error triggers legacy SSL fallback."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # First HTTPS attempt fails with SSL error
        mock_session.head.side_effect = requests.exceptions.SSLError("SSL failed")
        mock_session.get.side_effect = requests.exceptions.SSLError("SSL failed")

        # Mock the legacy SSL adapter import and success
        with patch(
            "custom_components.cable_modem_monitor.core.discovery.steps.requests.Session"
        ) as mock_legacy_session_class:
            mock_legacy_session = MagicMock()
            mock_legacy_session_class.return_value = mock_legacy_session
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_legacy_session.get.return_value = mock_response

            result = check_connectivity("192.168.100.1")
            # Will try legacy SSL and succeed
            assert result.success is True

    @patch("custom_components.cable_modem_monitor.core.discovery.steps.requests.Session")
    def test_url_with_protocol_prefix(self, mock_session_class):
        """Test URL that already has protocol prefix."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.head.return_value = mock_response

        result = check_connectivity("http://192.168.100.1")

        assert result.success is True
        assert result.working_url == "http://192.168.100.1"
        assert result.protocol == "http"

    @patch("custom_components.cable_modem_monitor.core.discovery.steps.requests.Session")
    def test_unexpected_exception(self, mock_session_class):
        """Test unexpected exception is handled."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.head.side_effect = RuntimeError("Unexpected error")
        mock_session.get.side_effect = RuntimeError("Unexpected error")

        result = check_connectivity("192.168.100.1")

        assert result.success is False

    @patch("custom_components.cable_modem_monitor.core.ssl_adapter.LegacySSLAdapter")
    @patch("custom_components.cable_modem_monitor.core.discovery.steps.requests.Session")
    def test_legacy_ssl_success(self, mock_session_class, mock_adapter_class):
        """Test legacy SSL fallback succeeds when regular SSL fails."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # First HTTPS attempt fails with SSL error, HEAD then GET
        mock_session.head.side_effect = requests.exceptions.SSLError("SSL handshake failed")
        # GET also fails for regular session
        call_count = [0]

        def get_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First GET (HTTPS with regular session) fails
                raise requests.exceptions.SSLError("SSL failed")
            # Subsequent calls succeed (legacy SSL session)
            mock_response = MagicMock()
            mock_response.status_code = 200
            return mock_response

        mock_session.get.side_effect = get_side_effect

        result = check_connectivity("192.168.100.1")

        assert result.success is True
        assert result.legacy_ssl is True
        assert result.protocol == "https"

    @patch("custom_components.cable_modem_monitor.core.ssl_adapter.LegacySSLAdapter")
    @patch("custom_components.cable_modem_monitor.core.discovery.steps.requests.Session")
    def test_legacy_ssl_also_fails(self, mock_session_class, mock_adapter_class):
        """Test legacy SSL fallback also fails."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # All SSL attempts fail
        mock_session.head.side_effect = requests.exceptions.SSLError("SSL failed")
        mock_session.get.side_effect = requests.exceptions.SSLError("SSL failed")

        result = check_connectivity("192.168.100.1")

        # Should fail after trying both HTTPS (with legacy fallback) and HTTP
        assert result.success is False


class TestDiscoverAuth:
    """Test discover_auth function."""

    # -------------------------------------------------------------------------
    # No-credentials path tests (special case - doesn't use AuthDiscovery)
    # -------------------------------------------------------------------------

    @patch("custom_components.cable_modem_monitor.core.discovery.steps.requests.Session")
    def test_no_credentials(self, mock_session_class):
        """Test auth discovery without credentials."""
        mock_session = _create_mock_session()
        mock_session_class.return_value = mock_session
        mock_response = MagicMock()
        mock_response.text = "<html><body>Modem page</body></html>"
        mock_session.get.return_value = mock_response

        result = discover_auth("http://192.168.100.1", None, None)

        assert result.success is True
        assert result.strategy == "no_auth"
        assert result.html == "<html><body>Modem page</body></html>"

    @patch("custom_components.cable_modem_monitor.core.discovery.steps.requests.Session")
    def test_no_credentials_connection_fails(self, mock_session_class):
        """Test auth discovery without credentials when connection fails."""
        mock_session = _create_mock_session()
        mock_session_class.return_value = mock_session
        mock_session.get.side_effect = requests.exceptions.ConnectionError("Failed")

        result = discover_auth("http://192.168.100.1", None, None)

        assert result.success is False
        assert "Connection failed" in result.error

    # -------------------------------------------------------------------------
    # Table-driven tests for credentials-based auth discovery
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize(
        "strategy,exp_success,form_config,hnap_config,url_token_config,error_msg,desc",
        AUTH_DISCOVERY_CASES,
    )
    @patch("custom_components.cable_modem_monitor.core.auth.discovery.AuthDiscovery")
    @patch("custom_components.cable_modem_monitor.core.discovery.steps.requests.Session")
    def test_auth_discovery_strategies(
        self,
        mock_session_class,
        mock_auth_discovery_class,
        strategy,
        exp_success,
        form_config,
        hnap_config,
        url_token_config,
        error_msg,
        desc,
    ):
        """Table-driven test for auth discovery with credentials."""
        # Setup mocks using helpers
        mock_session = _create_mock_session()
        mock_session_class.return_value = mock_session

        mock_discovery = MagicMock()
        mock_auth_discovery_class.return_value = mock_discovery

        # Create form_config mock if dict provided (need MagicMock for attribute access)
        mock_form_config = None
        if form_config:
            mock_form_config = MagicMock()
            mock_form_config.action = form_config.get("action", "/login")
            mock_form_config.method = form_config.get("method", "POST")
            mock_form_config.username_field = form_config.get("username_field", "user")
            mock_form_config.password_field = form_config.get("password_field", "pass")
            mock_form_config.hidden_fields = form_config.get("hidden_fields", {})
            mock_form_config.password_encoding = form_config.get("password_encoding", "plain")

        mock_result = _create_mock_auth_discovery_result(
            success=exp_success,
            strategy=strategy,
            form_config=mock_form_config,
            hnap_config=hnap_config,
            url_token_config=url_token_config,
            error_message=error_msg,
        )
        mock_discovery.discover.return_value = mock_result

        # Execute
        result = discover_auth("http://192.168.100.1", "admin", "password")

        # Assert
        assert result.success is exp_success, desc
        if exp_success:
            assert result.strategy == strategy, desc
            if form_config:
                assert result.form_config is not None, desc
                assert result.form_config["action"] == form_config["action"], desc
            if hnap_config:
                assert result.hnap_config == hnap_config, desc
            if url_token_config:
                assert result.url_token_config == url_token_config, desc
        else:
            assert error_msg in result.error, desc

    # -------------------------------------------------------------------------
    # Edge case tests (exception handling, SSL, hints)
    # -------------------------------------------------------------------------

    @patch("custom_components.cable_modem_monitor.core.auth.discovery.AuthDiscovery")
    @patch("custom_components.cable_modem_monitor.core.discovery.steps.requests.Session")
    def test_auth_discovery_exception(self, mock_session_class, mock_auth_discovery_class):
        """Test auth discovery handles exception."""
        mock_session = _create_mock_session()
        mock_session_class.return_value = mock_session

        mock_discovery = MagicMock()
        mock_auth_discovery_class.return_value = mock_discovery
        mock_discovery.discover.side_effect = RuntimeError("Discovery crashed")

        result = discover_auth("http://192.168.100.1", "admin", "password")

        assert result.success is False
        assert "Discovery crashed" in result.error

    @patch("custom_components.cable_modem_monitor.core.ssl_adapter.LegacySSLAdapter")
    @patch("custom_components.cable_modem_monitor.core.discovery.steps.requests.Session")
    def test_legacy_ssl_mounts_adapter(self, mock_session_class, mock_adapter_class):
        """Test legacy SSL mounts the adapter."""
        mock_session = _create_mock_session()
        mock_session_class.return_value = mock_session
        mock_response = MagicMock()
        mock_response.text = "<html>Page</html>"
        mock_session.get.return_value = mock_response

        result = discover_auth("https://192.168.100.1", None, None, legacy_ssl=True)

        mock_session.mount.assert_called_once()
        assert result.success is True

    @patch("custom_components.cable_modem_monitor.core.auth.discovery.AuthDiscovery")
    @patch("custom_components.cable_modem_monitor.core.discovery.steps.requests.Session")
    def test_parser_hints_passed_to_discovery(self, mock_session_class, mock_auth_discovery_class):
        """Test parser hints are passed to auth discovery."""
        mock_session = _create_mock_session()
        mock_session_class.return_value = mock_session

        mock_discovery = MagicMock()
        mock_auth_discovery_class.return_value = mock_discovery

        mock_result = _create_mock_auth_discovery_result()
        mock_discovery.discover.return_value = mock_result

        hints = {"success_redirect": "/status.html", "username_field": "user"}
        result = discover_auth("http://192.168.100.1", "admin", "password", parser_hints=hints)

        assert result.success is True
        # Verify hints were passed
        call_kwargs = mock_discovery.discover.call_args.kwargs
        assert call_kwargs["verification_url"] == "/status.html"
        assert call_kwargs["hints"] == hints


class TestDetectParser:
    """Test detect_parser function."""

    # -------------------------------------------------------------------------
    # Invalid HTML tests
    # -------------------------------------------------------------------------

    def test_no_html_provided(self):
        """Test detection fails with no HTML."""
        result = detect_parser("")
        assert result.success is False
        assert "No HTML provided" in result.error

    def test_no_html_none(self):
        """Test detection fails with None HTML."""
        result = detect_parser(None)
        assert result.success is False

    # -------------------------------------------------------------------------
    # Table-driven tests for parser detection scenarios
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize(
        "login_matches,model_matches,parser_found,exp_success,exp_method,desc",
        PARSER_DETECTION_CASES,
    )
    def test_parser_detection_scenarios(
        self,
        login_matches,
        model_matches,
        parser_found,
        exp_success,
        exp_method,
        desc,
    ):
        """Table-driven test for parser detection scenarios."""
        mock_hint_matcher = _create_mock_hint_matcher(
            login_matches=login_matches,
            model_matches=model_matches,
        )

        with patch(
            "custom_components.cable_modem_monitor.core.discovery.steps._get_parser_class_by_name"
        ) as mock_get_parser:
            if parser_found:
                mock_parser = MagicMock()
                # Use first parser name from either login or model matches
                if login_matches:
                    mock_parser.name = login_matches[0][0].replace("Parser", " ").strip()
                elif model_matches:
                    mock_parser.name = model_matches[0][0].replace("Parser", " ").strip()
                mock_get_parser.return_value = mock_parser
            else:
                mock_get_parser.return_value = None

            result = detect_parser("<html>test</html>", hint_matcher=mock_hint_matcher)

            assert result.success is exp_success, desc
            if exp_success:
                assert result.detection_method == exp_method, desc
                assert result.confidence > 0, desc

    # -------------------------------------------------------------------------
    # Edge case tests (disambiguation, provided parsers, default hint matcher)
    # -------------------------------------------------------------------------

    def test_disambiguation_with_model_strings(self):
        """Test disambiguation when multiple login_markers match."""
        # Two parsers match login_markers
        mock_hint_matcher = _create_mock_hint_matcher(
            login_matches=[
                ("ArrisSB6190Parser", ["ARRIS"]),
                ("ArrisSB8200Parser", ["ARRIS"]),
            ],
            model_matches=[("ArrisSB8200Parser", ["SB8200"])],
        )

        with patch(
            "custom_components.cable_modem_monitor.core.discovery.steps._get_parser_class_by_name"
        ) as mock_get_parser:
            mock_parser = MagicMock()
            mock_parser.name = "ARRIS SB8200"
            mock_get_parser.return_value = mock_parser

            result = detect_parser("<html>ARRIS SB8200</html>", hint_matcher=mock_hint_matcher)

            assert result.success is True
            assert result.parser_name == "ARRIS SB8200"

    def test_uses_provided_parsers_list(self):
        """Test detection can use provided parsers list."""
        mock_hint_matcher = _create_mock_hint_matcher(
            login_matches=[("TestParser", ["test"])],
        )

        mock_parser_class = MagicMock()
        mock_parser_class.__name__ = "TestParser"
        mock_parser_class.name = "Test Parser"

        with patch(
            "custom_components.cable_modem_monitor.core.discovery.steps._get_parser_class_by_name"
        ) as mock_get_parser:
            mock_get_parser.return_value = mock_parser_class

            result = detect_parser("<html>test</html>", hint_matcher=mock_hint_matcher, parsers=[mock_parser_class])

            assert result.success is True

    def test_uses_default_hint_matcher(self):
        """Test detection uses HintMatcher.get_instance() when no hint_matcher provided."""
        # Use HTML that matches a real modem (Motorola MB7621)
        html = """
        <html>
        <head><link rel="stylesheet" href="moto.css"></head>
        <body>
            <form action="/goform/login">
                <input name="loginUsername">
                <input name="loginPassword">
            </form>
        </body>
        </html>
        """
        # Call without hint_matcher - should use HintMatcher.get_instance()
        result = detect_parser(html)

        # May or may not match depending on index.yaml contents
        # Just verify no exception and result is returned
        assert result is not None
        assert isinstance(result, ParserResult)


class TestGetParserClassByName:
    """Test _get_parser_class_by_name function."""

    def test_direct_load_from_index(self):
        """Test direct load using index.yaml finds a real parser."""
        # Test with a real parser that exists in the codebase
        result = _get_parser_class_by_name("MotorolaMB7621Parser")

        # Should find the actual parser class
        assert result is not None
        assert result.__name__ == "MotorolaMB7621Parser"

    def test_fallback_to_parsers_list(self):
        """Test fallback to provided parsers list."""
        mock_index = {"modems": {}}

        with patch("custom_components.cable_modem_monitor.core.parser_discovery._load_modem_index") as mock_load:
            mock_load.return_value = mock_index

            mock_parser_class = MagicMock()
            mock_parser_class.__name__ = "TestParser"

            result = _get_parser_class_by_name("TestParser", parsers=[mock_parser_class])

            assert result is mock_parser_class

    def test_parser_not_found(self):
        """Test returns None when parser not found."""
        mock_index = {"modems": {}}

        with patch("custom_components.cable_modem_monitor.core.parser_discovery._load_modem_index") as mock_load:
            mock_load.return_value = mock_index

            result = _get_parser_class_by_name("NonExistentParser")

            assert result is None

    def test_import_error_handled(self):
        """Test import error is handled gracefully."""
        mock_index = {
            "modems": {
                "BrokenParser": {
                    "path": "broken/parser",
                    "name": "Broken Parser",
                }
            }
        }

        with patch("custom_components.cable_modem_monitor.core.parser_discovery._load_modem_index") as mock_load:
            mock_load.return_value = mock_index

            with patch("importlib.import_module") as mock_import:
                mock_import.side_effect = ImportError("Module not found")

                result = _get_parser_class_by_name("BrokenParser")

                assert result is None


class TestValidateParse:
    """Test validate_parse function."""

    def test_no_html_provided(self):
        """Test validation fails with no HTML."""
        mock_parser_class = MagicMock()
        mock_session = MagicMock()

        result = validate_parse("", mock_parser_class, mock_session, "http://192.168.100.1")

        assert result.success is False
        assert "No HTML provided" in result.error

    @patch(
        "custom_components.cable_modem_monitor.modem_config.adapter.get_auth_adapter_for_parser",
        return_value=None,
    )
    def test_successful_parse(self, mock_adapter):
        """Test successful validation parse."""
        mock_parser_class = MagicMock()
        mock_parser_class.__name__ = "TestParser"
        mock_parser_instance = MagicMock()
        mock_parser_class.return_value = mock_parser_instance
        mock_parser_instance.parse_resources.return_value = {
            "downstream": [{"channel_id": 1, "power": 2.0}],
            "upstream": [{"channel_id": 1, "power": 40.0}],
            "system_info": {"uptime": "1 day"},
        }

        mock_session = MagicMock()

        result = validate_parse("<html><table></table></html>", mock_parser_class, mock_session, "http://192.168.100.1")

        assert result.success is True
        assert result.modem_data is not None
        assert len(result.modem_data["downstream"]) == 1
        assert result.parser_instance is mock_parser_instance

    @patch(
        "custom_components.cable_modem_monitor.modem_config.adapter.get_auth_adapter_for_parser",
        return_value=None,
    )
    def test_parser_returns_none(self, mock_adapter):
        """Test validation fails when parser returns None."""
        mock_parser_class = MagicMock()
        mock_parser_class.__name__ = "TestParser"
        mock_parser_instance = MagicMock()
        mock_parser_class.return_value = mock_parser_instance
        mock_parser_instance.parse_resources.return_value = None

        mock_session = MagicMock()

        result = validate_parse("<html></html>", mock_parser_class, mock_session, "http://192.168.100.1")

        assert result.success is False
        assert "Parser returned None" in result.error

    @patch(
        "custom_components.cable_modem_monitor.modem_config.adapter.get_auth_adapter_for_parser",
        return_value=None,
    )
    def test_parser_returns_empty_data(self, mock_adapter):
        """Test validation succeeds even with empty data (no signal)."""
        mock_parser_class = MagicMock()
        mock_parser_class.__name__ = "TestParser"
        mock_parser_instance = MagicMock()
        mock_parser_class.return_value = mock_parser_instance
        mock_parser_instance.parse_resources.return_value = {
            "downstream": [],
            "upstream": [],
            "system_info": {},
        }

        mock_session = MagicMock()

        result = validate_parse("<html></html>", mock_parser_class, mock_session, "http://192.168.100.1")

        # Empty data is still considered success (modem may have no signal)
        assert result.success is True

    @patch(
        "custom_components.cable_modem_monitor.modem_config.adapter.get_auth_adapter_for_parser",
        return_value=None,
    )
    def test_parser_exception(self, mock_adapter):
        """Test validation handles parser exception."""
        mock_parser_class = MagicMock()
        mock_parser_class.__name__ = "TestParser"
        mock_parser_instance = MagicMock()
        mock_parser_class.return_value = mock_parser_instance
        mock_parser_instance.parse_resources.side_effect = ValueError("Parse error")

        mock_session = MagicMock()

        result = validate_parse("<html></html>", mock_parser_class, mock_session, "http://192.168.100.1")

        assert result.success is False
        assert "Parse error" in result.error

    @patch("custom_components.cable_modem_monitor.core.loaders.ResourceLoaderFactory.create")
    @patch("custom_components.cable_modem_monitor.modem_config.adapter.get_auth_adapter_for_parser")
    def test_uses_resource_loader_when_adapter_available(self, mock_get_adapter, mock_loader_factory):
        """Test that ResourceLoader is used when modem.yaml adapter is available."""
        # Mock adapter
        mock_adapter = MagicMock()
        mock_adapter.get_modem_config_dict.return_value = {"pages": {"data": {"/page.html": "/page.html"}}}
        mock_adapter.get_url_token_config_for_loader.return_value = None
        mock_get_adapter.return_value = mock_adapter

        # Mock loader
        mock_loader = MagicMock()
        mock_loader.fetch.return_value = {"/page.html": MagicMock()}
        mock_loader_factory.return_value = mock_loader

        # Mock parser
        mock_parser_class = MagicMock()
        mock_parser_class.__name__ = "TestParser"
        mock_parser_instance = MagicMock()
        mock_parser_class.return_value = mock_parser_instance
        mock_parser_instance.parse_resources.return_value = {
            "downstream": [{"channel_id": 1}],
            "upstream": [],
            "system_info": {},
        }

        mock_session = MagicMock()

        result = validate_parse("<html></html>", mock_parser_class, mock_session, "http://192.168.100.1")

        # Verify loader was created and used
        mock_loader_factory.assert_called_once()
        mock_loader.fetch.assert_called_once()
        mock_parser_instance.parse_resources.assert_called_once()
        assert result.success is True


class TestRunDiscoveryPipeline:
    """Test run_discovery_pipeline orchestrator."""

    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.validate_parse")
    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.detect_parser")
    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.discover_auth")
    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.check_connectivity")
    def test_successful_pipeline(self, mock_connectivity, mock_auth, mock_detect, mock_validate):
        """Test successful full pipeline run."""
        # Step 1: Connectivity succeeds
        mock_connectivity.return_value = ConnectivityResult(
            success=True,
            working_url="http://192.168.100.1",
            protocol="http",
            legacy_ssl=False,
        )

        # Step 2: Auth succeeds
        mock_session = MagicMock()
        mock_auth.return_value = AuthResult(
            success=True,
            strategy="no_auth",
            session=mock_session,
            html="<html>Modem page</html>",
        )

        # Step 3: Parser detection succeeds
        mock_parser_class = MagicMock()
        mock_parser_class.name = "Motorola MB7621"
        mock_detect.return_value = ParserResult(
            success=True,
            parser_class=mock_parser_class,
            parser_name="Motorola MB7621",
            detection_method="login_markers",
            confidence=0.9,
        )

        # Step 4: Validation succeeds
        mock_parser_instance = MagicMock()
        mock_validate.return_value = ValidationResult(
            success=True,
            modem_data={"downstream": [], "upstream": []},
            parser_instance=mock_parser_instance,
        )

        result = run_discovery_pipeline("192.168.100.1")

        assert result.success is True
        assert result.working_url == "http://192.168.100.1"
        assert result.auth_strategy == "no_auth"
        assert result.parser_name == "Motorola MB7621"
        assert result.error is None
        assert result.failed_step is None

    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.check_connectivity")
    def test_connectivity_failure(self, mock_connectivity):
        """Test pipeline fails at connectivity step."""
        mock_connectivity.return_value = ConnectivityResult(
            success=False,
            error="Could not connect",
        )

        result = run_discovery_pipeline("192.168.100.1")

        assert result.success is False
        assert result.failed_step == "connectivity"
        assert "Could not connect" in result.error

    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.discover_auth")
    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.check_connectivity")
    def test_auth_failure(self, mock_connectivity, mock_auth):
        """Test pipeline fails at auth step."""
        mock_connectivity.return_value = ConnectivityResult(
            success=True,
            working_url="http://192.168.100.1",
            protocol="http",
        )
        mock_auth.return_value = AuthResult(
            success=False,
            error="Invalid credentials",
        )

        result = run_discovery_pipeline("192.168.100.1", "admin", "wrongpass")

        assert result.success is False
        assert result.failed_step == "auth"
        assert result.working_url == "http://192.168.100.1"

    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.detect_parser")
    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.discover_auth")
    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.check_connectivity")
    def test_parser_detection_failure(self, mock_connectivity, mock_auth, mock_detect):
        """Test pipeline fails at parser detection step."""
        mock_connectivity.return_value = ConnectivityResult(
            success=True,
            working_url="http://192.168.100.1",
            protocol="http",
        )
        mock_session = MagicMock()
        mock_auth.return_value = AuthResult(
            success=True,
            strategy="no_auth",
            session=mock_session,
            html="<html>Unknown modem</html>",
        )
        mock_detect.return_value = ParserResult(
            success=False,
            error="No parser matched",
        )

        result = run_discovery_pipeline("192.168.100.1")

        assert result.success is False
        assert result.failed_step == "parser_detection"
        assert result.session is mock_session

    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.validate_parse")
    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.detect_parser")
    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.discover_auth")
    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.check_connectivity")
    def test_validation_failure(self, mock_connectivity, mock_auth, mock_detect, mock_validate):
        """Test pipeline fails at validation step."""
        mock_connectivity.return_value = ConnectivityResult(
            success=True,
            working_url="http://192.168.100.1",
            protocol="http",
        )
        mock_session = MagicMock()
        mock_auth.return_value = AuthResult(
            success=True,
            strategy="no_auth",
            session=mock_session,
            html="<html>Modem page</html>",
        )
        mock_parser_class = MagicMock()
        mock_parser_class.name = "Test Parser"
        mock_detect.return_value = ParserResult(
            success=True,
            parser_class=mock_parser_class,
            parser_name="Test Parser",
            detection_method="login_markers",
            confidence=0.9,
        )
        mock_validate.return_value = ValidationResult(
            success=False,
            error="Parse failed",
        )

        result = run_discovery_pipeline("192.168.100.1")

        assert result.success is False
        assert result.failed_step == "validation"
        assert result.parser_name == "Test Parser"

    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.validate_parse")
    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.discover_auth")
    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.check_connectivity")
    def test_user_selected_parser(self, mock_connectivity, mock_auth, mock_validate):
        """Test pipeline with user-selected parser skips detection."""
        mock_connectivity.return_value = ConnectivityResult(
            success=True,
            working_url="http://192.168.100.1",
            protocol="http",
        )
        mock_session = MagicMock()
        mock_auth.return_value = AuthResult(
            success=True,
            strategy="no_auth",
            session=mock_session,
            html="<html>Modem page</html>",
        )

        mock_selected_parser = MagicMock()
        mock_selected_parser.name = "User Selected Parser"

        mock_parser_instance = MagicMock()
        mock_validate.return_value = ValidationResult(
            success=True,
            modem_data={"downstream": [], "upstream": []},
            parser_instance=mock_parser_instance,
        )

        result = run_discovery_pipeline("192.168.100.1", selected_parser=mock_selected_parser)

        assert result.success is True
        assert result.parser_name == "User Selected Parser"

    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.validate_parse")
    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.detect_parser")
    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.discover_auth")
    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.check_connectivity")
    def test_parser_hints_passed_through(self, mock_connectivity, mock_auth, mock_detect, mock_validate):
        """Test parser hints are passed through the pipeline."""
        mock_connectivity.return_value = ConnectivityResult(
            success=True,
            working_url="http://192.168.100.1",
            protocol="http",
        )
        mock_session = MagicMock()
        mock_auth.return_value = AuthResult(
            success=True,
            strategy="form_plain",
            session=mock_session,
            html="<html>Modem page</html>",
            form_config={"action": "/login"},
        )
        mock_parser_class = MagicMock()
        mock_parser_class.name = "Test Parser"
        mock_detect.return_value = ParserResult(
            success=True,
            parser_class=mock_parser_class,
            parser_name="Test Parser",
            detection_method="login_markers",
            confidence=0.9,
        )
        mock_validate.return_value = ValidationResult(
            success=True,
            modem_data={"downstream": [], "upstream": []},
            parser_instance=MagicMock(),
        )

        hints = {"username_field": "user", "password_field": "pass"}
        result = run_discovery_pipeline("192.168.100.1", "admin", "pass", parser_hints=hints)

        # Verify hints were passed to discover_auth
        mock_auth.assert_called_once()
        call_kwargs = mock_auth.call_args.kwargs
        assert call_kwargs["parser_hints"] == hints

        assert result.success is True
        assert result.auth_form_config == {"action": "/login"}

    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.validate_parse")
    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.discover_auth")
    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.check_connectivity")
    def test_hnap_with_selected_parser_validates(self, mock_connectivity, mock_auth, mock_validate):
        """Test HNAP modem with selected parser validates via HNAP builder.

        HNAP modems return html=None (data via SOAP API, not HTML pages).
        When user selects parser, validation uses hnap_builder for API calls.
        Regression test for issue #102.
        """
        mock_connectivity.return_value = ConnectivityResult(
            success=True,
            working_url="https://192.168.100.1",
            protocol="https",
            legacy_ssl=False,
        )

        # HNAP auth returns authenticated builder but NO HTML
        mock_session = MagicMock()
        mock_hnap_builder = MagicMock()
        mock_auth.return_value = AuthResult(
            success=True,
            strategy="hnap_session",
            session=mock_session,
            html=None,  # CRITICAL: Real HNAP returns None
            hnap_config={"endpoint": "/HNAP1/", "namespace": "http://purenetworks.com/HNAP1/", "hmac_algorithm": "md5"},
            hnap_builder=mock_hnap_builder,
        )

        # User selected MB8611 (required for HNAP - no HTML for auto-detect)
        mock_selected_parser = MagicMock()
        mock_selected_parser.name = "Motorola MB8611"

        mock_validate.return_value = ValidationResult(
            success=True,
            modem_data={"downstream": [{"channel": 1}], "upstream": []},
            parser_instance=MagicMock(),
        )

        result = run_discovery_pipeline(
            "192.168.100.1",
            username="admin",
            password="password",
            selected_parser=mock_selected_parser,
        )

        # Pipeline should succeed
        assert result.success is True
        assert result.auth_strategy == "hnap_session"
        assert result.parser_name == "Motorola MB8611"
        assert result.hnap_builder is mock_hnap_builder
        assert result.modem_data == {"downstream": [{"channel": 1}], "upstream": []}

        # Verify builder was passed to validate_parse
        mock_validate.assert_called_once()
        call_kwargs = mock_validate.call_args.kwargs
        assert call_kwargs["hnap_builder"] is mock_hnap_builder
        assert call_kwargs["html"] is None

    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.discover_auth")
    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.check_connectivity")
    def test_hnap_without_selected_parser_fails_gracefully(self, mock_connectivity, mock_auth):
        """Test HNAP without selected parser fails with helpful error.

        HNAP modems return html=None, so auto-detection (Step 3) cannot work.
        The pipeline should return a clear error message, not crash.
        Regression test for issue #102.
        """
        mock_connectivity.return_value = ConnectivityResult(
            success=True,
            working_url="https://192.168.100.1",
            protocol="https",
            legacy_ssl=False,
        )

        # HNAP auth succeeds but returns NO HTML
        mock_session = MagicMock()
        mock_hnap_builder = MagicMock()
        mock_auth.return_value = AuthResult(
            success=True,
            strategy="hnap_session",
            session=mock_session,
            html=None,  # No HTML - can't auto-detect
            hnap_config={"endpoint": "/HNAP1/", "namespace": "http://purenetworks.com/HNAP1/", "hmac_algorithm": "md5"},
            hnap_builder=mock_hnap_builder,
        )

        # NO selected_parser - user wants auto-detect (which can't work for HNAP)
        result = run_discovery_pipeline(
            "192.168.100.1",
            username="admin",
            password="password",
            # selected_parser NOT provided - auto-detect mode
        )

        # Should fail gracefully with helpful error, not crash
        assert result.success is False
        assert result.failed_step == "parser_detection"
        assert "HNAP" in result.error
        assert "select" in result.error.lower()
        # Builder should still be in result for potential retry
        assert result.hnap_builder is mock_hnap_builder


# =============================================================================
# CREATE AUTHENTICATED SESSION TESTS - For static auth config architecture
# =============================================================================


class TestCreateAuthenticatedSession:
    """Test create_authenticated_session function.

    This function uses static auth config from modem.yaml instead of
    dynamic auth discovery, enabling faster and more reliable setup
    for known modems.
    """

    @patch("custom_components.cable_modem_monitor.core.discovery.steps.requests.Session")
    def test_no_credentials_no_auth(self, mock_session_class):
        """Test no credentials returns no_auth success."""
        from custom_components.cable_modem_monitor.core.discovery.steps import (
            create_authenticated_session,
        )

        mock_session = _create_mock_session()
        mock_session_class.return_value = mock_session
        mock_response = MagicMock()
        mock_response.text = "<html>Modem page</html>"
        mock_session.get.return_value = mock_response

        static_config = {"auth_strategy": "no_auth"}
        result = create_authenticated_session(
            "http://192.168.100.1",
            None,  # No username
            None,  # No password
            False,  # No legacy SSL
            static_config,
        )

        assert result.success is True
        assert result.strategy == "no_auth"
        assert result.html == "<html>Modem page</html>"

    @patch("custom_components.cable_modem_monitor.core.discovery.steps.requests.Session")
    def test_no_auth_strategy(self, mock_session_class):
        """Test no_auth strategy fetches page without auth."""
        from custom_components.cable_modem_monitor.core.discovery.steps import (
            create_authenticated_session,
        )

        mock_session = _create_mock_session()
        mock_session_class.return_value = mock_session
        mock_response = MagicMock()
        mock_response.text = "<html>No auth page</html>"
        mock_session.get.return_value = mock_response

        static_config = {
            "auth_strategy": "no_auth",
            "auth_form_config": None,
            "auth_hnap_config": None,
            "auth_url_token_config": None,
        }
        result = create_authenticated_session(
            "http://192.168.100.1",
            "admin",  # Credentials provided but no_auth strategy
            "password",
            False,
            static_config,
        )

        assert result.success is True
        assert result.strategy == "no_auth"

    @patch("custom_components.cable_modem_monitor.core.auth.handler.AuthHandler.authenticate")
    @patch("custom_components.cable_modem_monitor.core.discovery.steps.requests.Session")
    def test_form_auth_with_static_config(self, mock_session_class, mock_authenticate):
        """Test form auth using static config from modem.yaml."""
        from custom_components.cable_modem_monitor.core.auth.base import AuthResult as BaseAuthResult
        from custom_components.cable_modem_monitor.core.discovery.steps import (
            create_authenticated_session,
        )

        mock_session = _create_mock_session()
        mock_session_class.return_value = mock_session

        mock_authenticate.return_value = BaseAuthResult(
            success=True,
            response_html="<html>Authenticated page</html>",
        )

        static_config = {
            "auth_strategy": "form_plain",
            "auth_form_config": {
                "action": "/goform/login",
                "username_field": "user",
                "password_field": "pass",
                "password_encoding": "base64",
            },
            "auth_hnap_config": None,
            "auth_url_token_config": None,
        }

        result = create_authenticated_session(
            "http://192.168.100.1",
            "admin",
            "password",
            False,
            static_config,
        )

        assert result.success is True
        assert result.strategy == "form_plain"
        assert result.form_config == static_config["auth_form_config"]

    @patch("custom_components.cable_modem_monitor.core.auth.handler.AuthHandler.authenticate")
    @patch("custom_components.cable_modem_monitor.core.discovery.steps.requests.Session")
    def test_hnap_auth_with_static_config(self, mock_session_class, mock_authenticate):
        """Test HNAP auth using static config from modem.yaml."""
        from custom_components.cable_modem_monitor.core.auth.base import AuthResult as BaseAuthResult
        from custom_components.cable_modem_monitor.core.discovery.steps import (
            create_authenticated_session,
        )

        mock_session = _create_mock_session()
        mock_session_class.return_value = mock_session

        mock_authenticate.return_value = BaseAuthResult(
            success=True,
            response_html=None,  # HNAP returns no HTML
        )

        static_config = {
            "auth_strategy": "hnap_session",
            "auth_form_config": None,
            "auth_hnap_config": {
                "endpoint": "/HNAP1/",
                "namespace": "http://purenetworks.com/HNAP1/",
                "hmac_algorithm": "md5",
            },
            "auth_url_token_config": None,
        }

        result = create_authenticated_session(
            "https://192.168.100.1",
            "admin",
            "password",
            False,
            static_config,
        )

        assert result.success is True
        assert result.strategy == "hnap_session"
        assert result.hnap_config == static_config["auth_hnap_config"]

    @patch("custom_components.cable_modem_monitor.core.auth.handler.AuthHandler.authenticate")
    @patch("custom_components.cable_modem_monitor.core.discovery.steps.requests.Session")
    def test_url_token_auth_with_static_config(self, mock_session_class, mock_authenticate):
        """Test URL token auth using static config from modem.yaml."""
        from custom_components.cable_modem_monitor.core.auth.base import AuthResult as BaseAuthResult
        from custom_components.cable_modem_monitor.core.discovery.steps import (
            create_authenticated_session,
        )

        mock_session = _create_mock_session()
        mock_session_class.return_value = mock_session

        mock_authenticate.return_value = BaseAuthResult(
            success=True,
            response_html="<html>Token auth page</html>",
        )

        static_config = {
            "auth_strategy": "url_token_session",
            "auth_form_config": None,
            "auth_hnap_config": None,
            "auth_url_token_config": {
                "login_page": "/cmconnectionstatus.html",
                "data_page": "/cmconnectionstatus.html",
                "login_prefix": "login_",
                "token_prefix": "ct_",
            },
        }

        result = create_authenticated_session(
            "https://192.168.100.1",
            "admin",
            "password",
            False,
            static_config,
        )

        assert result.success is True
        assert result.strategy == "url_token_session"
        assert result.url_token_config == static_config["auth_url_token_config"]

    @patch("custom_components.cable_modem_monitor.core.auth.handler.AuthHandler.authenticate")
    @patch("custom_components.cable_modem_monitor.core.discovery.steps.requests.Session")
    def test_auth_failure_returns_error(self, mock_session_class, mock_authenticate):
        """Test authentication failure returns error."""
        from custom_components.cable_modem_monitor.core.auth.base import AuthResult as BaseAuthResult
        from custom_components.cable_modem_monitor.core.discovery.steps import (
            create_authenticated_session,
        )

        mock_session = _create_mock_session()
        mock_session_class.return_value = mock_session

        mock_authenticate.return_value = BaseAuthResult(
            success=False,
            error_message="Invalid credentials",
        )

        static_config = {
            "auth_strategy": "form_plain",
            "auth_form_config": {"action": "/login"},
        }

        result = create_authenticated_session(
            "http://192.168.100.1",
            "admin",
            "wrongpass",
            False,
            static_config,
        )

        assert result.success is False
        assert "Invalid credentials" in result.error

    @patch("custom_components.cable_modem_monitor.core.ssl_adapter.LegacySSLAdapter")
    @patch("custom_components.cable_modem_monitor.core.discovery.steps.requests.Session")
    def test_legacy_ssl_mounts_adapter(self, mock_session_class, mock_adapter_class):
        """Test legacy SSL mounts the adapter."""
        from custom_components.cable_modem_monitor.core.discovery.steps import (
            create_authenticated_session,
        )

        mock_session = _create_mock_session()
        mock_session_class.return_value = mock_session
        mock_response = MagicMock()
        mock_response.text = "<html>Page</html>"
        mock_session.get.return_value = mock_response

        static_config = {"auth_strategy": "no_auth"}
        result = create_authenticated_session(
            "https://192.168.100.1",
            None,
            None,
            True,  # legacy_ssl=True
            static_config,
        )

        mock_session.mount.assert_called_once()
        assert result.success is True

    @patch("custom_components.cable_modem_monitor.core.discovery.steps.requests.Session")
    def test_connection_failure(self, mock_session_class):
        """Test connection failure returns error."""
        from custom_components.cable_modem_monitor.core.discovery.steps import (
            create_authenticated_session,
        )

        mock_session = _create_mock_session()
        mock_session_class.return_value = mock_session
        mock_session.get.side_effect = requests.exceptions.ConnectionError("Failed")

        static_config = {"auth_strategy": "no_auth"}
        result = create_authenticated_session(
            "http://192.168.100.1",
            None,
            None,
            False,
            static_config,
        )

        assert result.success is False
        assert "Connection failed" in result.error

    @patch("custom_components.cable_modem_monitor.core.auth.handler.AuthHandler.authenticate")
    @patch("custom_components.cable_modem_monitor.core.discovery.steps.requests.Session")
    def test_fetches_page_when_auth_response_has_no_html(self, mock_session_class, mock_authenticate):
        """Test that page is fetched after auth when auth response has no HTML.

        For form auth, the form submission response may not contain the actual
        modem data. In this case, we fetch the working_url to get page content.
        """
        from custom_components.cable_modem_monitor.core.auth.base import AuthResult as BaseAuthResult
        from custom_components.cable_modem_monitor.core.discovery.steps import (
            create_authenticated_session,
        )

        mock_session = _create_mock_session()
        mock_session_class.return_value = mock_session

        # Auth succeeds but returns no HTML (form submission response)
        mock_authenticate.return_value = BaseAuthResult(
            success=True,
            response_html=None,  # No HTML from auth - this is the key
        )

        # GET should be called to fetch the page after auth
        mock_response = MagicMock()
        mock_response.text = "<html>Modem status page after login</html>"
        mock_session.get.return_value = mock_response

        static_config = {
            "auth_strategy": "form_plain",
            "auth_form_config": {"action": "/login"},
        }

        result = create_authenticated_session(
            "http://192.168.100.1",
            "admin",
            "password",
            False,
            static_config,
        )

        assert result.success is True
        assert result.html == "<html>Modem status page after login</html>"
        # Verify GET was called to fetch the page
        mock_session.get.assert_called_once_with("http://192.168.100.1", timeout=10)


# =============================================================================
# PIPELINE WITH STATIC AUTH CONFIG TESTS
# =============================================================================


class TestRunDiscoveryPipelineWithStaticConfig:
    """Test run_discovery_pipeline with static_auth_config parameter.

    These tests verify the "modem.yaml as source of truth" architecture
    where known modems skip dynamic auth discovery.
    """

    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.validate_parse")
    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.create_authenticated_session")
    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.discover_auth")
    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.check_connectivity")
    def test_uses_static_config_when_provided(
        self, mock_connectivity, mock_discover_auth, mock_create_session, mock_validate
    ):
        """Test pipeline uses static config and skips discover_auth."""
        mock_connectivity.return_value = ConnectivityResult(
            success=True,
            working_url="http://192.168.100.1",
            protocol="http",
            legacy_ssl=False,
        )

        # Static auth config provided
        mock_session = MagicMock()
        mock_create_session.return_value = AuthResult(
            success=True,
            strategy="form_plain",
            session=mock_session,
            html="<html>Authenticated</html>",
            form_config={"action": "/login"},
        )

        mock_selected_parser = MagicMock()
        mock_selected_parser.name = "Motorola MB7621"

        mock_validate.return_value = ValidationResult(
            success=True,
            modem_data={"downstream": [], "upstream": []},
            parser_instance=MagicMock(),
        )

        static_config = {
            "auth_strategy": "form_plain",
            "auth_form_config": {"action": "/login"},
        }

        result = run_discovery_pipeline(
            "192.168.100.1",
            username="admin",
            password="password",
            selected_parser=mock_selected_parser,
            static_auth_config=static_config,
        )

        # verify create_authenticated_session was called instead of discover_auth
        mock_create_session.assert_called_once()
        mock_discover_auth.assert_not_called()
        assert result.success is True
        assert result.auth_strategy == "form_plain"

    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.validate_parse")
    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.create_authenticated_session")
    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.discover_auth")
    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.check_connectivity")
    def test_uses_discover_auth_when_no_static_config(
        self, mock_connectivity, mock_discover_auth, mock_create_session, mock_validate
    ):
        """Test pipeline uses discover_auth when no static config provided."""
        mock_connectivity.return_value = ConnectivityResult(
            success=True,
            working_url="http://192.168.100.1",
            protocol="http",
            legacy_ssl=False,
        )

        # No static auth config - should use discover_auth
        mock_session = MagicMock()
        mock_discover_auth.return_value = AuthResult(
            success=True,
            strategy="no_auth",
            session=mock_session,
            html="<html>Discovered</html>",
        )

        mock_selected_parser = MagicMock()
        mock_selected_parser.name = "Fallback Parser"

        mock_validate.return_value = ValidationResult(
            success=True,
            modem_data={"downstream": [], "upstream": []},
            parser_instance=MagicMock(),
        )

        result = run_discovery_pipeline(
            "192.168.100.1",
            username="admin",
            password="password",
            selected_parser=mock_selected_parser,
            static_auth_config=None,  # No static config
        )

        # Verify discover_auth was called instead of create_authenticated_session
        mock_discover_auth.assert_called_once()
        mock_create_session.assert_not_called()
        assert result.success is True

    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.create_authenticated_session")
    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.check_connectivity")
    def test_static_auth_failure_returns_auth_error(self, mock_connectivity, mock_create_session):
        """Test static auth failure returns proper error with failed_step."""
        mock_connectivity.return_value = ConnectivityResult(
            success=True,
            working_url="http://192.168.100.1",
            protocol="http",
            legacy_ssl=False,
        )

        mock_create_session.return_value = AuthResult(
            success=False,
            error="Invalid credentials",
        )

        static_config = {"auth_strategy": "form_plain"}

        result = run_discovery_pipeline(
            "192.168.100.1",
            username="admin",
            password="wrongpass",
            static_auth_config=static_config,
        )

        assert result.success is False
        assert result.failed_step == "auth"
        assert "Invalid credentials" in result.error

    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.validate_parse")
    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.create_authenticated_session")
    @patch("custom_components.cable_modem_monitor.core.discovery.pipeline.check_connectivity")
    def test_static_config_hnap_success(self, mock_connectivity, mock_create_session, mock_validate):
        """Test HNAP auth with static config succeeds."""
        mock_connectivity.return_value = ConnectivityResult(
            success=True,
            working_url="https://192.168.100.1",
            protocol="https",
            legacy_ssl=False,
        )

        mock_session = MagicMock()
        mock_hnap_builder = MagicMock()
        mock_create_session.return_value = AuthResult(
            success=True,
            strategy="hnap_session",
            session=mock_session,
            html=None,  # HNAP returns no HTML
            hnap_config={"endpoint": "/HNAP1/", "hmac_algorithm": "md5"},
            hnap_builder=mock_hnap_builder,
        )

        mock_selected_parser = MagicMock()
        mock_selected_parser.name = "Arris S33"

        mock_validate.return_value = ValidationResult(
            success=True,
            modem_data={"downstream": [{"channel": 1}], "upstream": []},
            parser_instance=MagicMock(),
        )

        static_config = {
            "auth_strategy": "hnap_session",
            "auth_hnap_config": {"endpoint": "/HNAP1/", "hmac_algorithm": "md5"},
        }

        result = run_discovery_pipeline(
            "192.168.100.1",
            username="admin",
            password="password",
            selected_parser=mock_selected_parser,
            static_auth_config=static_config,
        )

        assert result.success is True
        assert result.auth_strategy == "hnap_session"
        assert result.hnap_builder is mock_hnap_builder
