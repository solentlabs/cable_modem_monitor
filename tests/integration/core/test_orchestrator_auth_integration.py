"""Integration tests for orchestrator auth strategy usage.

These tests verify that the orchestrator correctly uses stored auth strategies
during polling (Step 5 of Auth Strategy Discovery).
"""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.cable_modem_monitor.core.auth.handler import AuthHandler
from custom_components.cable_modem_monitor.core.auth.types import AuthStrategyType
from custom_components.cable_modem_monitor.core.data_orchestrator import DataOrchestrator

# Test timeout constant - matches DEFAULT_TIMEOUT from schema
TEST_TIMEOUT = 10


class TestScraperAuthStrategyUsage:
    """Test that scraper uses stored auth strategy during polling."""

    def test_scraper_accepts_auth_strategy_param(self):
        """Scraper accepts auth_strategy parameter."""
        orchestrator = DataOrchestrator(
            host="http://192.168.100.1",
            username="admin",
            password="pw",
            auth_strategy="basic_http",
            timeout=TEST_TIMEOUT,
        )

        assert orchestrator._auth_strategy == "basic_http"
        assert orchestrator._auth_handler is not None
        assert orchestrator._auth_handler.strategy == AuthStrategyType.BASIC_HTTP

    def test_scraper_accepts_form_config_param(self):
        """Scraper accepts auth_form_config parameter."""
        form_config = {
            "action": "/login",
            "method": "POST",
            "username_field": "user",
            "password_field": "pass",
            "hidden_fields": {"csrf": "token123"},
        }
        orchestrator = DataOrchestrator(
            host="http://192.168.100.1",
            username="admin",
            password="pw",
            auth_strategy="form_plain",
            auth_form_config=form_config,
            timeout=TEST_TIMEOUT,
        )

        assert orchestrator._auth_handler.form_config == form_config

    def test_scraper_no_auth_strategy_assumes_no_auth_required(self):
        """Without auth_strategy or hints, scraper assumes no auth required.

        v3.12.0: Legacy parser.login() fallback removed. When no auth strategy
        is stored and no hints exist, assume the modem doesn't require auth
        (e.g., public status pages). parser.login() is NOT called.
        """
        mock_parser = MagicMock()
        mock_parser.login.return_value = (True, "<html>data</html>")
        # No hints available
        mock_parser.hnap_hints = None
        mock_parser.js_auth_hints = None
        mock_parser.auth_form_hints = None

        orchestrator = DataOrchestrator(
            host="http://192.168.100.1",
            username="admin",
            password="pw",
            parser=mock_parser,
            auth_strategy=None,  # No stored strategy
            timeout=TEST_TIMEOUT,
        )

        success, html = orchestrator._login()

        # v3.12: No longer calls parser.login() - assumes no auth required
        mock_parser.login.assert_not_called()
        assert success is True


class TestScraperBasicAuthStrategy:
    """Test scraper with BASIC_HTTP strategy."""

    def test_basic_auth_sets_session_credentials(self, basic_auth_server):
        """Basic auth strategy sets session.auth."""
        orchestrator = DataOrchestrator(
            host=basic_auth_server.url,
            username="admin",
            password="pw",
            auth_strategy="basic_http",
            timeout=TEST_TIMEOUT,
        )

        success, html = orchestrator._login()

        assert success is True
        assert orchestrator.session.auth == ("admin", "pw")


class TestScraperFormAuthStrategy:
    """Test scraper with FORM_PLAIN strategy."""

    def test_form_auth_uses_stored_config(self, form_auth_server):
        """Form auth strategy uses stored form config."""
        form_config = {
            "action": "/login",
            "method": "POST",
            "username_field": "username",
            "password_field": "password",
            "hidden_fields": {"csrf_token": "test_token"},
        }

        orchestrator = DataOrchestrator(
            host=form_auth_server.url,
            username="admin",
            password="pw",
            auth_strategy="form_plain",
            auth_form_config=form_config,
            timeout=TEST_TIMEOUT,
        )

        success, html = orchestrator._login()

        # Should succeed with form auth
        assert success is True


class TestScraperNoAuthStrategy:
    """Test scraper with NO_AUTH strategy."""

    def test_no_auth_strategy_succeeds(self, http_server):
        """NO_AUTH strategy succeeds without any auth action."""
        orchestrator = DataOrchestrator(
            host=http_server.url,
            username=None,
            password=None,
            auth_strategy="no_auth",
            timeout=TEST_TIMEOUT,
        )

        success, html = orchestrator._login()

        assert success is True


class TestScraperHNAPStrategy:
    """Test scraper with HNAP_SESSION strategy (v3.12.0+).

    HNAP is now handled directly by AuthHandler, not delegated to parser.
    """

    def test_hnap_strategy_uses_auth_handler(self):
        """HNAP strategy uses AuthHandler directly (not parser.login())."""
        mock_parser = MagicMock()
        # _json_builder will be set by AuthHandler if HNAP auth succeeds

        orchestrator = DataOrchestrator(
            host="http://192.168.100.1",
            username="admin",
            password="pw",
            parser=mock_parser,
            auth_strategy="hnap_session",
            timeout=TEST_TIMEOUT,
        )

        # Auth handler should be configured for HNAP
        assert orchestrator._auth_handler is not None
        assert orchestrator._auth_handler.strategy == AuthStrategyType.HNAP_SESSION
        # Parser.login() should NOT be called (auth handled by AuthHandler)


class TestScraperURLTokenStrategy:
    """Test scraper with URL_TOKEN_SESSION strategy (v3.12.0+).

    URL token auth is now handled directly by AuthHandler.
    """

    def test_url_token_strategy_uses_auth_handler(self):
        """URL token strategy uses AuthHandler directly."""
        mock_parser = MagicMock()

        orchestrator = DataOrchestrator(
            host="http://192.168.100.1",
            username="admin",
            password="pw",
            parser=mock_parser,
            auth_strategy="url_token_session",
            timeout=TEST_TIMEOUT,
        )

        # Auth handler should be configured for URL token
        assert orchestrator._auth_handler is not None
        assert orchestrator._auth_handler.strategy == AuthStrategyType.URL_TOKEN_SESSION
        # Parser.login() should NOT be called (auth handled by AuthHandler)


class TestScraperLegacyEntryHandling:
    """Test handling of legacy config entries without auth_strategy."""

    def test_legacy_entry_without_strategy_assumes_no_auth(self):
        """Config entry without auth_strategy assumes no auth required.

        v3.12.0: Legacy parser.login() fallback removed. When no auth strategy
        is stored and no hints exist, assume no auth required.
        """
        mock_parser = MagicMock()
        mock_parser.login.return_value = (True, "<html>data</html>")
        # No hints available
        mock_parser.hnap_hints = None
        mock_parser.js_auth_hints = None
        mock_parser.auth_form_hints = None

        # Legacy entry: no auth_strategy or auth_form_config
        orchestrator = DataOrchestrator(
            host="http://192.168.100.1",
            username="admin",
            password="pw",
            parser=mock_parser,
            auth_strategy=None,
            auth_form_config=None,
            timeout=TEST_TIMEOUT,
        )

        success, html = orchestrator._login()

        # v3.12: No longer calls parser.login() - assumes no auth required
        mock_parser.login.assert_not_called()
        assert success is True

    def test_legacy_entry_no_parser_no_strategy_assumes_no_auth(self):
        """Legacy entry without parser or strategy assumes no auth required.

        v3.12.0: When no auth is configured (no strategy, no parser hints),
        assume the modem doesn't require authentication. This supports
        modems with public status pages.
        """
        orchestrator = DataOrchestrator(
            host="http://192.168.100.1",
            username="admin",
            password="pw",
            parser=None,
            auth_strategy=None,
            timeout=TEST_TIMEOUT,
        )

        success, html = orchestrator._login()

        # v3.12: Assumes no auth required
        assert success is True


class TestScraperAuthHandlerIntegration:
    """Test AuthHandler integration with DataOrchestrator."""

    def test_form_auth_without_config_fails_gracefully(self):
        """Form auth without config returns failure."""
        mock_parser = MagicMock()

        # Create scraper with form auth but no form config
        orchestrator = DataOrchestrator(
            host="http://192.168.100.1",
            username="admin",
            password="pw",
            parser=mock_parser,
            auth_strategy="form_plain",
            auth_form_config=None,  # Missing config will cause warning
            timeout=TEST_TIMEOUT,
        )

        success, html = orchestrator._login()

        # Form auth without config should fail (no form_config)
        assert success is False

    def test_auth_handler_initialized_correctly(self):
        """Auth handler is initialized with correct strategy."""
        orchestrator = DataOrchestrator(
            host="http://192.168.100.1",
            username="admin",
            password="pw",
            auth_strategy="basic_http",
            timeout=TEST_TIMEOUT,
        )

        assert isinstance(orchestrator._auth_handler, AuthHandler)
        assert orchestrator._auth_handler.strategy == AuthStrategyType.BASIC_HTTP

    def test_auth_handler_initialized_with_unknown_strategy(self):
        """Unknown strategy string handled gracefully."""
        orchestrator = DataOrchestrator(
            host="http://192.168.100.1",
            username="admin",
            password="pw",
            auth_strategy="not_a_real_strategy",
            timeout=TEST_TIMEOUT,
        )

        # Should default to UNKNOWN
        assert orchestrator._auth_handler.strategy == AuthStrategyType.UNKNOWN


class TestScraperNoCredentials:
    """Test scraper behavior when no credentials provided."""

    def test_no_credentials_skips_login(self):
        """Without credentials, _login() returns success immediately."""
        orchestrator = DataOrchestrator(
            host="http://192.168.100.1",
            username=None,
            password=None,
            auth_strategy="basic_http",  # Strategy exists but no creds
            timeout=TEST_TIMEOUT,
        )

        success, html = orchestrator._login()

        # Should return True immediately (skip login)
        assert success is True
        assert html is None

    def test_empty_credentials_skips_login(self):
        """Empty string credentials skip login."""
        orchestrator = DataOrchestrator(
            host="http://192.168.100.1",
            username="",
            password="",
            auth_strategy="basic_http",
            timeout=TEST_TIMEOUT,
        )

        success, html = orchestrator._login()

        # Should return True immediately (skip login)
        assert success is True
        assert html is None
