"""Tests for action execution — dispatch, HTTP, and HNAP executors.

Covers: single dispatch routing, HTTP pre-fetch + form-action extraction,
HNAP SOAP signing + pre-fetch + param interpolation + response validation,
connection loss handling for both transports.
"""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock, patch

import requests
from solentlabs.cable_modem_monitor_core.auth.base import AuthContext
from solentlabs.cable_modem_monitor_core.models.modem_config.actions import (
    HnapAction,
    HttpAction,
)
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import HnapAuth, NoneAuth
from solentlabs.cable_modem_monitor_core.orchestration.actions import (
    execute_action,
    execute_hnap_action,
    execute_http_action,
)

# ------------------------------------------------------------------
# Tests — execute_http_action
# ------------------------------------------------------------------


class TestExecuteHttpAction:
    """HTTP action execution and error handling."""

    def test_connection_error_treated_as_success(self) -> None:
        """ConnectionError during restart is success (modem rebooting)."""
        session = MagicMock(spec=requests.Session)
        session.request.side_effect = requests.ConnectionError("refused")
        action = HttpAction(type="http", method="POST", endpoint="/restart.htm")

        result = execute_http_action(session, "http://192.168.100.1", action)

        assert result.success is True
        session.request.assert_called_once()

    def test_timeout_treated_as_success(self) -> None:
        """Timeout during restart is success."""
        session = MagicMock(spec=requests.Session)
        session.request.side_effect = requests.Timeout("timed out")
        action = HttpAction(type="http", method="POST", endpoint="/restart.htm")

        result = execute_http_action(session, "http://192.168.100.1", action)

        assert result.success is True

    def test_successful_action_returns_status_code(self) -> None:
        """Successful action returns result with status code in details."""
        session = MagicMock(spec=requests.Session)
        resp = MagicMock()
        resp.status_code = 200
        session.request.return_value = resp
        action = HttpAction(
            type="http",
            method="GET",
            endpoint="/logout",
            headers={"X-Token": "abc"},
            params={"confirm": "yes"},
        )

        result = execute_http_action(session, "http://192.168.100.1", action, timeout=5)

        assert result.success is True
        assert result.details["status_code"] == 200
        session.request.assert_called_once_with(
            "GET",
            "http://192.168.100.1/logout",
            data={"confirm": "yes"},
            headers={"X-Token": "abc"},
            timeout=5,
        )


# ------------------------------------------------------------------
# Tests — HTTP pre-fetch and form-action extraction
# ------------------------------------------------------------------


class TestHttpPreFetch:
    """Pre-fetch URL support for HTTP actions."""

    def test_pre_fetch_executed_before_action(self) -> None:
        """pre_fetch_url is fetched before the main action request."""
        session = MagicMock(spec=requests.Session)
        pre_resp = MagicMock()
        pre_resp.status_code = 200
        pre_resp.content = b"<html>security page</html>"
        pre_resp.text = "<html>security page</html>"
        session.get.return_value = pre_resp

        action = HttpAction(
            type="http",
            method="POST",
            endpoint="/goform/restart",
            pre_fetch_url="/Security.asp",
            params={"RestartAction": "1"},
        )

        execute_http_action(session, "http://192.168.100.1", action)

        session.get.assert_called_once_with(
            "http://192.168.100.1/Security.asp",
            timeout=10,
        )
        session.request.assert_called_once()

    def test_pre_fetch_connection_error_falls_back_to_static(self) -> None:
        """If pre-fetch fails, action uses static endpoint."""
        session = MagicMock(spec=requests.Session)
        session.get.side_effect = requests.ConnectionError("refused")

        action = HttpAction(
            type="http",
            method="POST",
            endpoint="/goform/restart",
            pre_fetch_url="/Security.asp",
        )

        execute_http_action(session, "http://192.168.100.1", action)

        session.get.assert_called_once()
        session.request.assert_called_once_with(
            "POST",
            "http://192.168.100.1/goform/restart",
            data=None,
            headers=None,
            timeout=10,
        )

    def test_no_pre_fetch_skips_get(self) -> None:
        """Without pre_fetch_url, no GET request is made."""
        session = MagicMock(spec=requests.Session)
        action = HttpAction(type="http", method="POST", endpoint="/restart")

        execute_http_action(session, "http://192.168.100.1", action)

        session.get.assert_not_called()
        session.request.assert_called_once()


class TestFormActionExtraction:
    """Form-action keyword extraction from pre-fetch pages."""

    def test_extracts_dynamic_endpoint_from_form(self) -> None:
        """Keyword matches form action, dynamic endpoint extracted."""
        session = MagicMock(spec=requests.Session)
        pre_resp = MagicMock()
        pre_resp.status_code = 200
        pre_resp.content = b""
        pre_resp.text = '<html><form name="status" method="POST" ' 'action="/goform/RouterStatus?id=12345">'
        session.get.return_value = pre_resp

        action = HttpAction(
            type="http",
            method="POST",
            endpoint="/goform/RouterStatus",
            pre_fetch_url="/RouterStatus.htm",
            endpoint_pattern="RouterStatus",
        )

        execute_http_action(session, "http://192.168.100.1", action)

        # Main request uses extracted endpoint with session ID
        session.request.assert_called_once_with(
            "POST",
            "http://192.168.100.1/goform/RouterStatus?id=12345",
            data=None,
            headers=None,
            timeout=10,
        )

    def test_double_quotes_in_form_action(self) -> None:
        """Extraction works with double-quoted form action."""
        session = MagicMock(spec=requests.Session)
        pre_resp = MagicMock()
        pre_resp.status_code = 200
        pre_resp.content = b""
        pre_resp.text = '<form action="/goform/RouterStatus?id=99">'
        session.get.return_value = pre_resp

        action = HttpAction(
            type="http",
            method="POST",
            endpoint="/goform/RouterStatus",
            pre_fetch_url="/RouterStatus.htm",
            endpoint_pattern="RouterStatus",
        )

        execute_http_action(session, "http://192.168.100.1", action)

        session.request.assert_called_once_with(
            "POST",
            "http://192.168.100.1/goform/RouterStatus?id=99",
            data=None,
            headers=None,
            timeout=10,
        )

    def test_no_match_falls_back_to_static_endpoint(self) -> None:
        """When keyword not found in any form, static endpoint is used."""
        session = MagicMock(spec=requests.Session)
        pre_resp = MagicMock()
        pre_resp.status_code = 200
        pre_resp.content = b""
        pre_resp.text = "<html>no matching form here</html>"
        session.get.return_value = pre_resp

        action = HttpAction(
            type="http",
            method="POST",
            endpoint="/goform/RouterStatus",
            pre_fetch_url="/RouterStatus.htm",
            endpoint_pattern="RouterStatus",
        )

        execute_http_action(session, "http://192.168.100.1", action)

        # Falls back to static endpoint
        session.request.assert_called_once_with(
            "POST",
            "http://192.168.100.1/goform/RouterStatus",
            data=None,
            headers=None,
            timeout=10,
        )

    def test_no_match_no_fallback_returns_failure(self) -> None:
        """When extraction fails and no static endpoint, action fails."""
        session = MagicMock(spec=requests.Session)
        pre_resp = MagicMock()
        pre_resp.status_code = 200
        pre_resp.content = b""
        pre_resp.text = "<html>no matching form</html>"
        session.get.return_value = pre_resp

        action = HttpAction(
            type="http",
            method="POST",
            endpoint="",
            pre_fetch_url="/RouterStatus.htm",
            endpoint_pattern="RouterStatus",
        )

        result = execute_http_action(session, "http://192.168.100.1", action)

        assert result.success is False
        assert "extraction failed" in result.message.lower()
        session.request.assert_not_called()

    def test_case_insensitive_form_matching(self) -> None:
        """Form tag matching is case-insensitive."""
        session = MagicMock(spec=requests.Session)
        pre_resp = MagicMock()
        pre_resp.status_code = 200
        pre_resp.content = b""
        pre_resp.text = '<FORM ACTION="/goform/RouterStatus?id=1">'
        session.get.return_value = pre_resp

        action = HttpAction(
            type="http",
            method="POST",
            endpoint="/goform/RouterStatus",
            pre_fetch_url="/RouterStatus.htm",
            endpoint_pattern="RouterStatus",
        )

        execute_http_action(session, "http://192.168.100.1", action)

        session.request.assert_called_once_with(
            "POST",
            "http://192.168.100.1/goform/RouterStatus?id=1",
            data=None,
            headers=None,
            timeout=10,
        )


# ------------------------------------------------------------------
# Tests — execute_hnap_action
# ------------------------------------------------------------------


class TestExecuteHnapAction:
    """HNAP SOAP action execution."""

    def test_basic_action_sends_signed_request(self) -> None:
        """HNAP action sends HMAC-signed SOAP POST."""
        session = MagicMock(spec=requests.Session)
        resp = MagicMock()
        resp.json.return_value = {
            "SetStatusSecuritySettingsResponse": {
                "SetStatusSecuritySettingsResult": "OK",
            },
        }
        session.post.return_value = resp

        action = HnapAction(
            type="hnap",
            action_name="SetStatusSecuritySettings",
            params={"MotoStatusSecurityAction": "1"},
            response_key="SetStatusSecuritySettingsResponse",
            result_key="SetStatusSecuritySettingsResult",
            success_value="OK",
        )

        result = execute_hnap_action(
            session,
            "http://192.168.100.1",
            action,
            private_key="test_key",
        )

        assert result.success is True
        assert result.details["result"] == "OK"

        # Verify SOAP headers
        call_kwargs = session.post.call_args
        headers = call_kwargs[1]["headers"] if "headers" in call_kwargs[1] else call_kwargs[0][2]
        assert "HNAP_AUTH" in headers
        assert "SOAPAction" in headers

    def test_connection_error_treated_as_success(self) -> None:
        """Connection drop during restart = success."""
        session = MagicMock(spec=requests.Session)
        session.post.side_effect = requests.ConnectionError("reset")

        action = HnapAction(type="hnap", action_name="Reboot")

        result = execute_hnap_action(
            session,
            "http://192.168.100.1",
            action,
            private_key="key",
        )

        assert result.success is True

    def test_unexpected_result_returns_failure(self) -> None:
        """HNAP action with unexpected result value fails."""
        session = MagicMock(spec=requests.Session)
        resp = MagicMock()
        resp.json.return_value = {
            "RebootResponse": {"RebootResult": "ERROR"},
        }
        session.post.return_value = resp

        action = HnapAction(
            type="hnap",
            action_name="Reboot",
            response_key="RebootResponse",
            result_key="RebootResult",
            success_value="OK",
        )

        result = execute_hnap_action(
            session,
            "http://192.168.100.1",
            action,
            private_key="key",
        )

        assert result.success is False
        assert "ERROR" in result.message

    def test_invalid_json_response(self) -> None:
        """Non-JSON response returns failure."""
        session = MagicMock(spec=requests.Session)
        resp = MagicMock()
        resp.json.side_effect = ValueError("not json")
        resp.status_code = 500
        session.post.return_value = resp

        action = HnapAction(type="hnap", action_name="Reboot")

        result = execute_hnap_action(
            session,
            "http://192.168.100.1",
            action,
            private_key="key",
        )

        assert result.success is False


class TestHnapPreFetch:
    """HNAP pre-fetch action for parameter interpolation."""

    def test_pre_fetch_values_interpolated(self) -> None:
        """Pre-fetch response values replace ${var:default} placeholders."""
        session = MagicMock(spec=requests.Session)

        # Pre-fetch response
        pre_resp = MagicMock()
        pre_resp.json.return_value = {
            "GetArrisConfigurationInfoResponse": {
                "ethSWEthEEE": "1",
                "LedStatus": "0",
            },
        }

        # Main action response
        main_resp = MagicMock()
        main_resp.json.return_value = {
            "SetArrisConfigurationInfoResponse": {
                "SetArrisConfigurationInfoResult": "OK",
            },
        }

        session.post.side_effect = [pre_resp, main_resp]

        action = HnapAction(
            type="hnap",
            action_name="SetArrisConfigurationInfo",
            pre_fetch_action="GetArrisConfigurationInfo",
            params={
                "Action": "reboot",
                "SetEEEEnable": "${ethSWEthEEE:0}",
                "LED_Status": "${LedStatus:1}",
            },
            response_key="SetArrisConfigurationInfoResponse",
            result_key="SetArrisConfigurationInfoResult",
            success_value="OK",
        )

        result = execute_hnap_action(
            session,
            "http://192.168.100.1",
            action,
            private_key="test_key",
        )

        assert result.success is True

        # Verify main action params have interpolated values
        main_call = session.post.call_args_list[1]
        body = json.loads(main_call[1]["data"])
        params = body["SetArrisConfigurationInfo"]
        assert params["SetEEEEnable"] == "1"
        assert params["LED_Status"] == "0"
        assert params["Action"] == "reboot"

    def test_pre_fetch_failure_uses_defaults(self) -> None:
        """When pre-fetch fails, ${var:default} uses default values."""
        session = MagicMock(spec=requests.Session)

        # Pre-fetch fails
        session.post.side_effect = [
            requests.ConnectionError("refused"),
            # Main action also fails (modem rebooting)
            requests.ConnectionError("reset"),
        ]

        action = HnapAction(
            type="hnap",
            action_name="SetArrisConfigurationInfo",
            pre_fetch_action="GetArrisConfigurationInfo",
            params={
                "Action": "reboot",
                "SetEEEEnable": "${ethSWEthEEE:0}",
                "LED_Status": "${LedStatus:1}",
            },
        )

        result = execute_hnap_action(
            session,
            "http://192.168.100.1",
            action,
            private_key="key",
        )

        # Action still attempted — pre-fetch failure is not fatal
        assert result.success is True
        assert session.post.call_count == 2


# ------------------------------------------------------------------
# Tests — execute_action dispatch
# ------------------------------------------------------------------


class TestExecuteAction:
    """Single dispatch routing for HTTP and HNAP actions."""

    def test_http_action_dispatches(self) -> None:
        """HTTP action routes to execute_http_action."""
        collector = MagicMock()
        collector._session = MagicMock(spec=requests.Session)
        collector._base_url = "http://192.168.100.1"

        modem_config = MagicMock()
        modem_config.auth = NoneAuth(strategy="none")
        modem_config.timeout = 10

        action = HttpAction(type="http", method="POST", endpoint="/restart.htm")

        with patch("solentlabs.cable_modem_monitor_core.orchestration.actions.execute_http_action") as mock_http:
            mock_http.return_value = MagicMock(success=True)
            execute_action(collector, modem_config, action)

        mock_http.assert_called_once_with(
            collector._session,
            collector._base_url,
            action,
            timeout=10,
            log_level=logging.INFO,
            model=modem_config.model,
        )

    def test_hnap_action_dispatches(self) -> None:
        """HNAP action routes to execute_hnap_action with credentials."""
        collector = MagicMock()
        collector._session = MagicMock(spec=requests.Session)
        collector._base_url = "http://192.168.100.1"
        collector._auth_context = AuthContext(private_key="test_key")

        modem_config = MagicMock()
        modem_config.auth = HnapAuth(strategy="hnap", hmac_algorithm="sha256")
        modem_config.timeout = 10

        action = HnapAction(type="hnap", action_name="Reboot")

        with patch("solentlabs.cable_modem_monitor_core.orchestration.actions.execute_hnap_action") as mock_hnap:
            mock_hnap.return_value = MagicMock(success=True)
            execute_action(collector, modem_config, action)

        mock_hnap.assert_called_once()
        call_kwargs = mock_hnap.call_args
        assert call_kwargs[1]["private_key"] == "test_key"
        assert call_kwargs[1]["hmac_algorithm"] == "sha256"

    def test_hnap_no_auth_context_uses_empty_key(self) -> None:
        """HNAP dispatch with no auth context uses empty private key."""
        collector = MagicMock()
        collector._session = MagicMock(spec=requests.Session)
        collector._base_url = "http://192.168.100.1"
        collector._auth_context = None

        modem_config = MagicMock()
        modem_config.auth = HnapAuth(strategy="hnap", hmac_algorithm="md5")
        modem_config.timeout = 10

        action = HnapAction(type="hnap", action_name="Reboot")

        with patch("solentlabs.cable_modem_monitor_core.orchestration.actions.execute_hnap_action") as mock_hnap:
            mock_hnap.return_value = MagicMock(success=True)
            execute_action(collector, modem_config, action)

        assert mock_hnap.call_args[1]["private_key"] == ""
