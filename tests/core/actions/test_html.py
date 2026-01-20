"""Tests for HTMLRestartAction."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.cable_modem_monitor.core.actions.html import HTMLRestartAction


class TestHTMLRestartActionInit:
    """Test HTMLRestartAction initialization."""

    def test_static_endpoint_config(self):
        """Test initialization with static endpoint."""
        modem_config = {
            "paradigm": "html",
            "capabilities": ["restart"],
            "model": "TestModem",
            "actions": {
                "restart": {
                    "endpoint": "/goform/restart",
                    "params": {"action": "reboot"},
                }
            },
        }

        action = HTMLRestartAction(modem_config)
        assert action._endpoint == "/goform/restart"
        assert action._endpoint_pattern == ""
        assert action._params == {"action": "reboot"}

    def test_dynamic_endpoint_config(self):
        """Test initialization with dynamic endpoint pattern."""
        modem_config = {
            "paradigm": "html",
            "capabilities": ["restart"],
            "model": "TestModem",
            "actions": {
                "restart": {
                    "pre_fetch_url": "/RouterStatus.htm",
                    "endpoint_pattern": "RouterStatus",
                    "params": {"buttonSelect": "2"},
                }
            },
        }

        action = HTMLRestartAction(modem_config)
        assert action._endpoint == ""
        assert action._endpoint_pattern == "RouterStatus"
        assert action._pre_fetch_url == "/RouterStatus.htm"
        assert action._params == {"buttonSelect": "2"}


class TestHTMLRestartActionExecution:
    """Test HTMLRestartAction execution."""

    def test_static_endpoint_success(self):
        """Test successful restart with static endpoint."""
        modem_config = {
            "paradigm": "html",
            "model": "TestModem",
            "actions": {
                "restart": {
                    "endpoint": "/goform/restart",
                    "params": {"action": "reboot"},
                }
            },
        }

        action = HTMLRestartAction(modem_config)

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_session.post.return_value = mock_response

        result = action.execute(mock_session, "http://192.168.100.1")

        assert result.success is True
        mock_session.post.assert_called_once_with(
            "http://192.168.100.1/goform/restart",
            data={"action": "reboot"},
            timeout=10,
        )

    def test_dynamic_endpoint_success(self):
        """Test successful restart with dynamic endpoint extraction."""
        modem_config = {
            "paradigm": "html",
            "model": "CM2000",
            "actions": {
                "restart": {
                    "pre_fetch_url": "/RouterStatus.htm",
                    "endpoint_pattern": "RouterStatus",
                    "params": {"buttonSelect": "2"},
                }
            },
        }

        action = HTMLRestartAction(modem_config)

        # Mock the pre-fetch response with form containing dynamic ID
        mock_session = MagicMock()
        mock_prefetch_response = MagicMock()
        mock_prefetch_response.ok = True
        mock_prefetch_response.text = """
            <html>
            <form action='/goform/RouterStatus?id=239640653' method="post">
                <input type="submit" value="Restart">
            </form>
            </html>
        """

        mock_post_response = MagicMock()
        mock_post_response.status_code = 200
        mock_post_response.text = "OK"

        mock_session.get.return_value = mock_prefetch_response
        mock_session.post.return_value = mock_post_response

        result = action.execute(mock_session, "http://192.168.100.1")

        assert result.success is True
        # Verify the dynamic URL was extracted and used
        mock_session.post.assert_called_once_with(
            "http://192.168.100.1/goform/RouterStatus?id=239640653",
            data={"buttonSelect": "2"},
            timeout=10,
        )

    def test_dynamic_endpoint_extraction_failure(self):
        """Test failure when form action cannot be extracted."""
        modem_config = {
            "paradigm": "html",
            "model": "CM2000",
            "actions": {
                "restart": {
                    "pre_fetch_url": "/RouterStatus.htm",
                    "endpoint_pattern": "RouterStatus",
                    "params": {"buttonSelect": "2"},
                }
            },
        }

        action = HTMLRestartAction(modem_config)

        mock_session = MagicMock()
        mock_prefetch_response = MagicMock()
        mock_prefetch_response.ok = True
        mock_prefetch_response.text = "<html><body>No form here</body></html>"

        mock_session.get.return_value = mock_prefetch_response

        result = action.execute(mock_session, "http://192.168.100.1")

        assert result.success is False
        assert "No restart endpoint" in result.message

    def test_no_endpoint_configured(self):
        """Test failure when no endpoint is configured."""
        modem_config = {
            "paradigm": "html",
            "model": "TestModem",
            "actions": {
                "restart": {
                    "params": {"action": "reboot"},
                }
            },
        }

        action = HTMLRestartAction(modem_config)
        mock_session = MagicMock()

        result = action.execute(mock_session, "http://192.168.100.1")

        assert result.success is False
        assert "No restart endpoint" in result.message

    def test_no_params_configured(self):
        """Test failure when no params are configured."""
        modem_config = {
            "paradigm": "html",
            "model": "TestModem",
            "actions": {
                "restart": {
                    "endpoint": "/goform/restart",
                }
            },
        }

        action = HTMLRestartAction(modem_config)
        mock_session = MagicMock()

        result = action.execute(mock_session, "http://192.168.100.1")

        assert result.success is False
        assert "No restart params" in result.message

    def test_connection_drop_is_success(self):
        """Test that connection drop during restart is treated as success."""
        from requests.exceptions import ConnectionError

        modem_config = {
            "paradigm": "html",
            "model": "TestModem",
            "actions": {
                "restart": {
                    "endpoint": "/goform/restart",
                    "params": {"action": "reboot"},
                }
            },
        }

        action = HTMLRestartAction(modem_config)

        mock_session = MagicMock()
        mock_session.post.side_effect = ConnectionError("Connection reset")

        result = action.execute(mock_session, "http://192.168.100.1")

        assert result.success is True
        assert "connection dropped" in result.message.lower()


class TestDynamicEndpointExtraction:
    """Test form action extraction patterns."""

    # fmt: off
    FORM_HTML_CASES = [
        # (html, pattern, expected_action, description)
        ('<form action="/goform/Status?id=1">', "Status", "/goform/Status?id=1", "double quotes"),
        ("<form action='/goform/Status?id=2'>", "Status", "/goform/Status?id=2", "single quotes"),
        ('<FORM ACTION="/goform/Status?id=3">', "Status", "/goform/Status?id=3", "uppercase"),
        ('<form method="post" action="/goform/Status?id=4">', "Status", "/goform/Status?id=4", "action 2nd"),
        ('<form action="/x"><form action="/goform/Status?id=5">', "Status", "/goform/Status?id=5", "multi form"),
    ]
    # fmt: on

    @pytest.mark.parametrize("html,pattern,expected,desc", FORM_HTML_CASES)
    def test_extract_form_action(self, html, pattern, expected, desc):
        """Test form action extraction with various HTML patterns."""
        modem_config = {
            "paradigm": "html",
            "model": "TestModem",
            "actions": {
                "restart": {
                    "pre_fetch_url": "/RouterStatus.htm",
                    "endpoint_pattern": pattern,
                    "params": {"buttonSelect": "2"},
                }
            },
        }

        action = HTMLRestartAction(modem_config)

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.text = html
        mock_session.get.return_value = mock_response

        extracted = action._extract_endpoint_from_form(mock_session, "http://192.168.100.1")

        assert extracted == expected, f"Failed for: {desc}"
