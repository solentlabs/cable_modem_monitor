"""Integration tests for restart after session logout.

Issue #61: Restart button stopped working after v3.12.0 added logout support.

Root cause: Config entries from pre-v3.12 don't have auth_strategy stored.
When _login() is called, it skips authentication because _auth_strategy is None.
After _perform_logout() invalidates the server session, restart fails because
the session isn't re-authenticated.

Resolution: Users with pre-v3.12 config entries need to re-add their integration
to trigger auth discovery and store the auth_strategy.

These tests verify the expected behavior without referencing specific modems.
"""

from __future__ import annotations

from unittest.mock import patch

import requests

from custom_components.cable_modem_monitor.core.actions.html import HTMLRestartAction
from custom_components.cable_modem_monitor.core.data_orchestrator import DataOrchestrator


class TestHTMLRestartActionEndpointExtraction:
    """Test HTMLRestartAction endpoint extraction behavior."""

    def test_returns_static_endpoint_when_configured(self):
        """Verify static endpoint is returned directly."""
        modem_config = {
            "model": "TestModem",
            "manufacturer": "TestMfg",
            "paradigm": "html",
            "actions": {
                "restart": {
                    "endpoint": "/goform/restart",
                    "params": {"action": "reboot"},
                }
            },
        }

        action = HTMLRestartAction(modem_config)
        session = requests.Session()

        endpoint = action._resolve_endpoint(session, "http://192.168.100.1")

        assert endpoint == "/goform/restart"

    def test_returns_empty_when_prefetch_fails_401(self):
        """Verify empty endpoint when pre-fetch returns 401 (session expired)."""
        modem_config = {
            "model": "TestModem",
            "manufacturer": "TestMfg",
            "paradigm": "html",
            "actions": {
                "restart": {
                    "pre_fetch_url": "/protected/status.htm",
                    "endpoint_pattern": "restart",
                    "params": {"action": "reboot"},
                }
            },
        }

        action = HTMLRestartAction(modem_config)
        session = requests.Session()

        # Mock server returning 401 (session expired/logged out)
        with patch.object(session, "get") as mock_get:
            mock_response = requests.Response()
            mock_response.status_code = 401
            mock_response._content = b"Unauthorized"
            mock_get.return_value = mock_response

            endpoint = action._resolve_endpoint(session, "http://192.168.100.1")

            assert endpoint == "", "Should return empty when pre-fetch fails"

    def test_extracts_endpoint_from_form_when_authenticated(self):
        """Verify endpoint extraction from form action when authenticated."""
        modem_config = {
            "model": "TestModem",
            "manufacturer": "TestMfg",
            "paradigm": "html",
            "actions": {
                "restart": {
                    "pre_fetch_url": "/status.htm",
                    "endpoint_pattern": "restart",
                    "params": {"action": "reboot"},
                }
            },
        }

        action = HTMLRestartAction(modem_config)
        session = requests.Session()

        # Mock server returning HTML with form containing restart action
        html_with_form = b"""
        <html>
        <form action="/goform/restart?session=abc123" method="POST">
            <input type="submit" value="Restart">
        </form>
        </html>
        """

        with patch.object(session, "get") as mock_get:
            mock_response = requests.Response()
            mock_response.status_code = 200
            mock_response._content = html_with_form
            mock_get.return_value = mock_response

            endpoint = action._resolve_endpoint(session, "http://192.168.100.1")

            assert endpoint == "/goform/restart?session=abc123"


class TestLoginBehaviorWithoutStoredStrategy:
    """Test _login() behavior when auth_strategy is not stored."""

    def test_login_skipped_when_no_stored_strategy(self):
        """Verify _login() skips auth when _auth_strategy is None.

        Config entries from pre-v3.12 don't have auth_strategy stored.
        _login() assumes no auth is required and returns success.
        Users need to re-add their integration to fix this.
        """
        orchestrator = DataOrchestrator(
            host="http://192.168.100.1",
            username="admin",
            password="password",
            auth_strategy=None,  # Not stored (pre-v3.12 entry)
        )

        success, html = orchestrator._login()

        # With no stored strategy, login is skipped
        assert success is True, "_login returns True when no strategy stored"
        assert html is None, "No HTML returned when auth skipped"

    def test_login_skipped_without_credentials(self):
        """Verify _login() skips when no credentials provided."""
        orchestrator = DataOrchestrator(
            host="http://192.168.100.1",
            username=None,
            password=None,
        )

        success, html = orchestrator._login()

        assert success is True
        assert html is None


class TestLoginBehaviorWithStoredStrategy:
    """Test _login() behavior when auth_strategy IS stored (v3.12+ entries)."""

    def test_login_uses_auth_handler_when_strategy_stored(self, mocker):
        """Verify _login() uses AuthHandler when auth_strategy is stored."""
        from custom_components.cable_modem_monitor.core.auth.types import AuthStrategyType

        orchestrator = DataOrchestrator(
            host="http://192.168.100.1",
            username="admin",
            password="password",
            auth_strategy=AuthStrategyType.BASIC_HTTP,
        )

        # Mock auth handler to track if authenticate is called
        mock_result = mocker.Mock()
        mock_result.success = True
        mock_result.response_html = None
        orchestrator._auth_handler.authenticate = mocker.Mock(return_value=mock_result)

        success, html = orchestrator._login()

        assert success is True
        orchestrator._auth_handler.authenticate.assert_called_once()


class TestRestartFlowWithStoredStrategy:
    """Test restart flow when auth_strategy IS stored (expected case)."""

    def test_restart_calls_login_before_action(self, mocker):
        """Verify restart_modem() calls _login() before executing action."""
        from custom_components.cable_modem_monitor.core.auth.types import AuthStrategyType

        orchestrator = DataOrchestrator(
            host="http://192.168.100.1",
            username="admin",
            password="password",
            auth_strategy=AuthStrategyType.BASIC_HTTP,
        )

        # Mock parser
        mock_parser = mocker.Mock()
        mock_parser.name = "TestParser"
        mock_parser.__class__.__name__ = "TestParser"
        orchestrator.parser = mock_parser

        # Mock _fetch_data (called in _prepare_for_restart)
        mocker.patch.object(
            orchestrator,
            "_fetch_data",
            return_value=("<html>test</html>", "http://192.168.100.1", mock_parser.__class__),
        )
        mocker.patch.object(orchestrator, "_detect_parser", return_value=mock_parser)

        # Track _login calls
        mock_login = mocker.patch.object(orchestrator, "_login", return_value=(True, None))

        # Mock adapter - patch where it's imported in data_orchestrator
        mock_adapter = mocker.Mock()
        mock_adapter.get_modem_config_dict.return_value = {
            "paradigm": "html",
            "actions": {"restart": {"endpoint": "/restart", "params": {"go": "1"}}},
        }
        mocker.patch(
            "custom_components.cable_modem_monitor.core.data_orchestrator.get_auth_adapter_for_parser",
            return_value=mock_adapter,
        )

        mock_action = mocker.Mock()
        mock_action.execute.return_value = mocker.Mock(success=True, message="OK")
        mocker.patch(
            "custom_components.cable_modem_monitor.core.actions.factory.ActionFactory.create_restart_action",
            return_value=mock_action,
        )
        mocker.patch(
            "custom_components.cable_modem_monitor.core.actions.factory.ActionFactory.supports",
            return_value=True,
        )

        # Execute restart
        result = orchestrator.restart_modem()

        # Verify _login was called
        assert mock_login.called, "_login should be called before restart"
        assert result is True


class TestPerformLogout:
    """Test _perform_logout() behavior."""

    def test_logout_calls_endpoint_when_configured(self, mocker):
        """Verify logout endpoint is called when configured in modem.yaml."""
        orchestrator = DataOrchestrator(
            host="http://192.168.100.1",
            username="admin",
            password="password",
        )

        # Mock parser (also clear logout_endpoint attribute to avoid fallback)
        mock_parser = mocker.Mock()
        mock_parser.__class__.__name__ = "TestParser"
        mock_parser.logout_endpoint = None  # Ensure no fallback
        orchestrator.parser = mock_parser

        # Mock adapter with logout endpoint - patch at source module
        # (the import inside _perform_logout uses this path)
        mock_adapter = mocker.Mock()
        mock_adapter.get_logout_endpoint.return_value = "/Logout.htm"
        mocker.patch(
            "custom_components.cable_modem_monitor.modem_config.adapter.get_auth_adapter_for_parser",
            return_value=mock_adapter,
        )

        # Mock session.get
        mock_get = mocker.patch.object(orchestrator.session, "get")

        # Call logout
        orchestrator._perform_logout()

        # Verify logout endpoint was called
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "/Logout.htm" in call_args[0][0]

    def test_logout_skipped_when_no_endpoint(self, mocker):
        """Verify logout is skipped when no endpoint configured."""
        orchestrator = DataOrchestrator(
            host="http://192.168.100.1",
            username="admin",
            password="password",
        )

        # Mock parser (also clear logout_endpoint attribute to avoid fallback)
        mock_parser = mocker.Mock()
        mock_parser.__class__.__name__ = "TestParser"
        mock_parser.logout_endpoint = None  # Ensure no fallback
        orchestrator.parser = mock_parser

        # Mock adapter without logout endpoint - patch at source module
        mock_adapter = mocker.Mock()
        mock_adapter.get_logout_endpoint.return_value = None
        mocker.patch(
            "custom_components.cable_modem_monitor.modem_config.adapter.get_auth_adapter_for_parser",
            return_value=mock_adapter,
        )

        # Mock session.get
        mock_get = mocker.patch.object(orchestrator.session, "get")

        # Call logout
        orchestrator._perform_logout()

        # Verify no request was made
        mock_get.assert_not_called()
