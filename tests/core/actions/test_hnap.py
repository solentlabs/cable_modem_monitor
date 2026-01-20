"""Tests for HNAPRestartAction."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from custom_components.cable_modem_monitor.core.actions.base import ActionResult
from custom_components.cable_modem_monitor.core.actions.hnap import HNAPRestartAction


def _make_auth_handler(builder: MagicMock) -> MagicMock:
    """Create a mock auth handler that returns the given builder."""
    auth_handler = MagicMock()
    auth_handler.get_hnap_builder.return_value = builder
    return auth_handler


class TestHNAPRestartActionExecution:
    """Test HNAPRestartAction.execute() method."""

    @pytest.fixture
    def hnap_config_with_prefetch(self):
        """HNAP config with pre-fetch action (e.g., for modems that need current state)."""
        return {
            "paradigm": "hnap",
            "capabilities": ["restart"],
            "auth": {
                "hnap": {
                    "endpoint": "/HNAP1/",
                    "namespace": "http://purenetworks.com/HNAP1/",
                    "hmac_algorithm": "md5",
                    "empty_action_value": "",
                    "actions": {"restart": "SetConfigurationInfo"},
                }
            },
            "actions": {
                "restart": {
                    "type": "hnap",
                    "pre_fetch_action": "GetConfigurationInfo",
                    "pre_fetch_response_key": "GetConfigurationInfoResponse",
                    "params": {
                        "Action": "reboot",
                        "Setting1": "${setting1:0}",
                        "Setting2": "${setting2:1}",
                    },
                    "response_key": "SetConfigurationInfoResponse",
                    "result_key": "SetConfigurationInfoResult",
                    "success_value": "OK",
                }
            },
        }

    @pytest.fixture
    def hnap_config_simple(self):
        """Simple HNAP config without pre-fetch."""
        return {
            "paradigm": "hnap",
            "capabilities": ["restart"],
            "auth": {
                "hnap": {
                    "endpoint": "/HNAP1/",
                    "namespace": "http://purenetworks.com/HNAP1/",
                    "hmac_algorithm": "md5",
                    "actions": {"restart": "SetSecuritySettings"},
                }
            },
            "actions": {
                "restart": {
                    "type": "hnap",
                    "params": {
                        "SecurityAction": "1",
                        "Placeholder": "XXX",
                    },
                    "response_key": "SetSecuritySettingsResponse",
                    "result_key": "SetSecuritySettingsResult",
                    "success_value": "OK",
                }
            },
        }

    def test_restart_with_prefetch_success(self, hnap_config_with_prefetch):
        """Test restart with pre-fetch action and successful response."""
        action = HNAPRestartAction(hnap_config_with_prefetch)

        session = MagicMock()
        builder = MagicMock()
        auth_handler = _make_auth_handler(builder)

        # Mock GetConfigurationInfo response (pre-fetch)
        prefetch_response = json.dumps(
            {
                "GetConfigurationInfoResponse": {
                    "GetConfigurationInfoResult": "OK",
                    "setting1": "1",
                    "setting2": "0",
                }
            }
        )

        # Mock SetConfigurationInfo response (restart)
        restart_response = json.dumps(
            {
                "SetConfigurationInfoResponse": {
                    "SetConfigurationInfoResult": "OK",
                }
            }
        )

        builder.call_single.side_effect = [prefetch_response, restart_response]

        result = action.execute(session, "http://192.168.100.1", auth_handler)

        assert result.success is True
        assert "accepted" in result.message.lower()
        assert builder.call_single.call_count == 2

    def test_restart_with_connection_reset(self, hnap_config_with_prefetch):
        """Test restart when connection resets (modem rebooting)."""
        action = HNAPRestartAction(hnap_config_with_prefetch)

        session = MagicMock()
        builder = MagicMock()
        auth_handler = _make_auth_handler(builder)

        # Mock pre-fetch success, then restart causes connection reset
        prefetch_response = json.dumps(
            {
                "GetConfigurationInfoResponse": {
                    "GetConfigurationInfoResult": "OK",
                    "setting1": "1",
                    "setting2": "0",
                }
            }
        )
        builder.call_single.side_effect = [prefetch_response, ConnectionResetError()]

        result = action.execute(session, "http://192.168.100.1", auth_handler)

        # Connection reset is treated as success
        assert result.success is True
        assert "connection reset" in result.message.lower()

    def test_restart_simple_success(self, hnap_config_simple):
        """Test simple restart (no pre-fetch) with successful response."""
        action = HNAPRestartAction(hnap_config_simple)

        session = MagicMock()
        builder = MagicMock()
        auth_handler = _make_auth_handler(builder)

        restart_response = json.dumps(
            {
                "SetSecuritySettingsResponse": {
                    "SetSecuritySettingsResult": "OK",
                }
            }
        )
        builder.call_single.return_value = restart_response

        result = action.execute(session, "http://192.168.100.1", auth_handler)

        assert result.success is True
        assert "accepted" in result.message.lower()

    def test_restart_failure(self, hnap_config_simple):
        """Test restart with failure response."""
        action = HNAPRestartAction(hnap_config_simple)

        session = MagicMock()
        builder = MagicMock()
        auth_handler = _make_auth_handler(builder)

        restart_response = json.dumps(
            {
                "SetSecuritySettingsResponse": {
                    "SetSecuritySettingsResult": "ERROR",
                }
            }
        )
        builder.call_single.return_value = restart_response

        result = action.execute(session, "http://192.168.100.1", auth_handler)

        assert result.success is False
        assert "error" in result.message.lower()

    def test_no_action_configured(self):
        """Test when no restart action is configured."""
        config = {
            "paradigm": "hnap",
            "capabilities": ["restart"],
            "auth": {
                "hnap": {
                    "endpoint": "/HNAP1/",
                    "namespace": "http://purenetworks.com/HNAP1/",
                    "hmac_algorithm": "md5",
                    "actions": {},  # No restart action
                }
            },
        }
        action = HNAPRestartAction(config)

        session = MagicMock()
        builder = MagicMock()
        auth_handler = _make_auth_handler(builder)

        result = action.execute(session, "http://192.168.100.1", auth_handler)

        assert result.success is False
        assert "no restart action configured" in result.message.lower()

    def test_creates_builder_when_none_provided(self, hnap_config_simple):
        """Test that action creates a builder when auth_handler returns None."""
        action = HNAPRestartAction(hnap_config_simple)

        session = MagicMock()
        # Auth handler returns None for builder (e.g., not an HNAP auth)
        auth_handler = MagicMock()
        auth_handler.get_hnap_builder.return_value = None

        with patch.object(action, "_create_builder") as mock_create:
            mock_builder = MagicMock()
            mock_create.return_value = mock_builder

            restart_response = json.dumps(
                {
                    "SetSecuritySettingsResponse": {
                        "SetSecuritySettingsResult": "OK",
                    }
                }
            )
            mock_builder.call_single.return_value = restart_response

            result = action.execute(session, "http://192.168.100.1", auth_handler)

            mock_create.assert_called_once()
            assert result.success is True

    def test_creates_builder_when_no_auth_handler(self, hnap_config_simple):
        """Test that action creates a builder when no auth_handler provided."""
        action = HNAPRestartAction(hnap_config_simple)

        session = MagicMock()

        with patch.object(action, "_create_builder") as mock_create:
            mock_builder = MagicMock()
            mock_create.return_value = mock_builder

            restart_response = json.dumps(
                {
                    "SetSecuritySettingsResponse": {
                        "SetSecuritySettingsResult": "OK",
                    }
                }
            )
            mock_builder.call_single.return_value = restart_response

            result = action.execute(session, "http://192.168.100.1", None)

            mock_create.assert_called_once()
            assert result.success is True


class TestParamInterpolation:
    """Test parameter interpolation with ${var:default} placeholders."""

    def test_interpolate_with_values(self):
        """Test interpolation when pre-fetch data has values."""
        config = {
            "paradigm": "hnap",
            "auth": {"hnap": {"actions": {"restart": "SetConfig"}}},
            "actions": {
                "restart": {
                    "params": {
                        "fixed": "value",
                        "dynamic": "${myvar:default}",
                    }
                }
            },
        }
        action = HNAPRestartAction(config)

        pre_fetch_data = {"myvar": "fetched_value"}
        result = action._interpolate_params(config["actions"]["restart"]["params"], pre_fetch_data)

        assert result["fixed"] == "value"
        assert result["dynamic"] == "fetched_value"

    def test_interpolate_with_defaults(self):
        """Test interpolation falls back to defaults when value missing."""
        config = {
            "paradigm": "hnap",
            "auth": {"hnap": {"actions": {"restart": "SetConfig"}}},
            "actions": {
                "restart": {
                    "params": {
                        "dynamic": "${missing:fallback}",
                    }
                }
            },
        }
        action = HNAPRestartAction(config)

        pre_fetch_data = {}  # No value for 'missing'
        result = action._interpolate_params(config["actions"]["restart"]["params"], pre_fetch_data)

        assert result["dynamic"] == "fallback"


class TestActionResult:
    """Test ActionResult dataclass."""

    def test_success_result(self):
        """Test creating a success result."""
        result = ActionResult(success=True, message="OK")
        assert result.success is True
        assert result.message == "OK"
        assert result.details is None

    def test_failure_result_with_details(self):
        """Test creating a failure result with details."""
        result = ActionResult(
            success=False,
            message="Failed",
            details={"error_code": 500},
        )
        assert result.success is False
        assert result.message == "Failed"
        assert result.details == {"error_code": 500}
