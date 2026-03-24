"""Tests for action execution — HTTP and HNAP action dispatch.

Covers connection timeout handling, HNAP action warning, and
restart action dispatch for both HTTP and HNAP types.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import requests
from solentlabs.cable_modem_monitor_core.auth.base import AuthContext
from solentlabs.cable_modem_monitor_core.models.modem_config.actions import (
    HnapAction,
    HttpAction,
)
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import HnapAuth, NoneAuth
from solentlabs.cable_modem_monitor_core.orchestration.actions import (
    execute_hnap_action,
    execute_http_action,
    execute_restart_action,
)

# ------------------------------------------------------------------
# Tests — execute_http_action
# ------------------------------------------------------------------


class TestExecuteHttpAction:
    """HTTP action execution and error handling."""

    def test_connection_error_suppressed(self) -> None:
        """ConnectionError during restart is suppressed (modem rebooting)."""
        session = MagicMock(spec=requests.Session)
        session.request.side_effect = requests.ConnectionError("refused")
        action = HttpAction(type="http", method="POST", endpoint="/restart.htm")

        # Should not raise
        execute_http_action(session, "http://192.168.100.1", action)
        session.request.assert_called_once()

    def test_timeout_suppressed(self) -> None:
        """Timeout during restart is suppressed."""
        session = MagicMock(spec=requests.Session)
        session.request.side_effect = requests.Timeout("timed out")
        action = HttpAction(type="http", method="POST", endpoint="/restart.htm")

        execute_http_action(session, "http://192.168.100.1", action)
        session.request.assert_called_once()

    def test_successful_action(self) -> None:
        """Successful action calls session.request with correct args."""
        session = MagicMock(spec=requests.Session)
        action = HttpAction(
            type="http",
            method="GET",
            endpoint="/logout",
            headers={"X-Token": "abc"},
            params={"confirm": "yes"},
        )

        execute_http_action(session, "http://192.168.100.1", action, timeout=5)
        session.request.assert_called_once_with(
            "GET",
            "http://192.168.100.1/logout",
            data={"confirm": "yes"},
            headers={"X-Token": "abc"},
            timeout=5,
        )


# ------------------------------------------------------------------
# Tests — execute_hnap_action
# ------------------------------------------------------------------


class TestExecuteHnapAction:
    """HNAP action execution (currently unimplemented — logs warning)."""

    def test_hnap_action_logs_warning(self) -> None:
        """HNAP action execution logs warning (not yet implemented)."""
        session = MagicMock(spec=requests.Session)
        action = HnapAction(type="hnap", action_name="Logout")

        with patch("solentlabs.cable_modem_monitor_core.orchestration.actions._logger") as mock_logger:
            execute_hnap_action(session, "http://192.168.100.1", action, private_key="key")

        mock_logger.warning.assert_called_once()
        assert "Logout" in mock_logger.warning.call_args[0][1]


# ------------------------------------------------------------------
# Tests — execute_restart_action dispatch
# ------------------------------------------------------------------


class TestExecuteRestartAction:
    """Restart action dispatch for HTTP and HNAP types."""

    def test_http_restart_dispatches(self) -> None:
        """HTTP restart action dispatches to execute_http_action."""
        collector = MagicMock()
        collector._session = MagicMock(spec=requests.Session)
        collector._base_url = "http://192.168.100.1"

        modem_config = MagicMock()
        modem_config.auth = NoneAuth(strategy="none")
        modem_config.timeout = 10

        action = HttpAction(type="http", method="POST", endpoint="/restart.htm")

        with patch("solentlabs.cable_modem_monitor_core.orchestration.actions.execute_http_action") as mock_http:
            execute_restart_action(collector, modem_config, action)

        mock_http.assert_called_once_with(
            collector._session,
            collector._base_url,
            action,
            timeout=10,
        )

    def test_hnap_restart_dispatches(self) -> None:
        """HNAP restart action dispatches to execute_hnap_action."""
        collector = MagicMock()
        collector._session = MagicMock(spec=requests.Session)
        collector._base_url = "http://192.168.100.1"
        collector._auth_context = AuthContext(private_key="test_key")

        modem_config = MagicMock()
        modem_config.auth = HnapAuth(strategy="hnap", hmac_algorithm="sha256")
        modem_config.timeout = 10

        action = HnapAction(type="hnap", action_name="Reboot")

        with patch("solentlabs.cable_modem_monitor_core.orchestration.actions.execute_hnap_action") as mock_hnap:
            execute_restart_action(collector, modem_config, action)

        mock_hnap.assert_called_once()
        call_kwargs = mock_hnap.call_args
        assert call_kwargs[1]["private_key"] == "test_key"
        assert call_kwargs[1]["hmac_algorithm"] == "sha256"

    def test_hnap_restart_no_auth_context(self) -> None:
        """HNAP restart with no auth context uses empty private key."""
        collector = MagicMock()
        collector._session = MagicMock(spec=requests.Session)
        collector._base_url = "http://192.168.100.1"
        collector._auth_context = None

        modem_config = MagicMock()
        modem_config.auth = HnapAuth(strategy="hnap", hmac_algorithm="md5")
        modem_config.timeout = 10

        action = HnapAction(type="hnap", action_name="Reboot")

        with patch("solentlabs.cable_modem_monitor_core.orchestration.actions.execute_hnap_action") as mock_hnap:
            execute_restart_action(collector, modem_config, action)

        assert mock_hnap.call_args[1]["private_key"] == ""
