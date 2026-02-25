"""Tests for ActionFactory.

The ActionFactory uses `actions.restart` as the single source of truth:
- If actions.restart exists, restart is supported
- The `type` field determines which action class to create (hnap, html_form, rest_api)
- For HNAP, `action_name` is required
- For HTML/REST, `endpoint` or `endpoint_pattern` is required
"""

from __future__ import annotations

import pytest

from custom_components.cable_modem_monitor.core.actions import ActionFactory
from custom_components.cable_modem_monitor.core.actions.base import ActionType
from custom_components.cable_modem_monitor.core.actions.hnap import HNAPRestartAction
from custom_components.cable_modem_monitor.core.actions.html import HTMLRestartAction
from custom_components.cable_modem_monitor.core.actions.rest import RESTRestartAction

# Test timeout constant - matches DEFAULT_TIMEOUT from schema
TEST_TIMEOUT = 10

# ┌────────────────────┬──────────────────────────────────┬───────────────────────┐
# │ type               │ config                           │ expected result       │
# ├────────────────────┼──────────────────────────────────┼───────────────────────┤
# │ hnap               │ action_name present              │ HNAPRestartAction     │
# │ hnap               │ action_name missing              │ HNAPRestartAction*    │
# │ html_form          │ endpoint present                 │ HTMLRestartAction     │
# │ html_form          │ endpoint_pattern present         │ HTMLRestartAction     │
# │ rest_api           │ endpoint present                 │ RESTRestartAction     │
# │ None               │ no actions.restart               │ None                  │
# └────────────────────┴──────────────────────────────────┴───────────────────────┘
# * HNAP still creates action but execute will fail - validation is runtime

# fmt: off
TEST_FACTORY_HNAP_CASES = [
    # (actions_config, auth_hnap_config, expected_type, description)
    (
        {"restart": {"type": "hnap", "action_name": "SetArrisConfig"}},
        {"endpoint": "/HNAP1/", "namespace": "http://purenetworks.com/HNAP1/", "hmac_algorithm": "md5"},
        HNAPRestartAction,
        "HNAP with action_name"
    ),
    (
        {"restart": {"type": "hnap"}},  # No action_name - action created but will fail at execute
        {"endpoint": "/HNAP1/", "namespace": "http://purenetworks.com/HNAP1/", "hmac_algorithm": "md5"},
        HNAPRestartAction,
        "HNAP without action_name (created but will fail)"
    ),
    (
        None,  # No actions config
        {"endpoint": "/HNAP1/", "namespace": "http://purenetworks.com/HNAP1/", "hmac_algorithm": "md5"},
        None,
        "HNAP paradigm but no actions.restart"
    ),
    (
        {},  # Empty actions config
        {"endpoint": "/HNAP1/", "namespace": "http://purenetworks.com/HNAP1/", "hmac_algorithm": "md5"},
        None,
        "HNAP paradigm with empty actions"
    ),
]
# fmt: on


@pytest.mark.parametrize(
    "actions_config,auth_hnap_config,expected_type,desc",
    TEST_FACTORY_HNAP_CASES,
)
def test_create_restart_action_hnap(actions_config, auth_hnap_config, expected_type, desc):
    """Test ActionFactory.create_restart_action with HNAP configurations."""
    modem_config = {
        "timeout": TEST_TIMEOUT,
        "paradigm": "hnap",
        "manufacturer": "TestMfg",
        "model": "TestModel",
        "auth": {"hnap": auth_hnap_config},
    }
    if actions_config is not None:
        modem_config["actions"] = actions_config

    result = ActionFactory.create_restart_action(modem_config)

    if expected_type is None:
        assert result is None, f"Expected None for: {desc}"
    else:
        assert isinstance(result, expected_type), f"Expected {expected_type.__name__} for: {desc}"


# fmt: off
TEST_FACTORY_HTML_CASES = [
    # (actions_config, expected_type, description)
    (
        {"restart": {"type": "html_form", "endpoint": "/goform/restart", "params": {"action": "1"}}},
        HTMLRestartAction, "HTML with endpoint"
    ),
    (
        {"restart": {"type": "html_form", "endpoint_pattern": "restart", "pre_fetch_url": "/status.htm"}},
        HTMLRestartAction, "HTML with endpoint_pattern"
    ),
    ({"restart": {"endpoint": "/goform/restart"}}, HTMLRestartAction, "HTML default type (html_form)"),
    ({}, None, "Empty actions config"),
    ({"restart": {}}, None, "Empty restart config"),
    (None, None, "No actions config"),
]
# fmt: on


@pytest.mark.parametrize(
    "actions_config,expected_type,desc",
    TEST_FACTORY_HTML_CASES,
)
def test_create_restart_action_html(actions_config, expected_type, desc):
    """Test ActionFactory.create_restart_action with HTML form configurations."""
    modem_config = {
        "timeout": TEST_TIMEOUT,
        "paradigm": "html",
        "manufacturer": "TestMfg",
        "model": "TestModel",
    }
    if actions_config is not None:
        modem_config["actions"] = actions_config

    result = ActionFactory.create_restart_action(modem_config)

    if expected_type is None:
        assert result is None, f"Expected None for: {desc}"
    else:
        assert isinstance(result, expected_type), f"Expected {expected_type.__name__} for: {desc}"


# fmt: off
TEST_FACTORY_REST_CASES = [
    # (actions_config, expected_type, description)
    ({"restart": {"type": "rest_api", "endpoint": "/api/restart"}}, RESTRestartAction, "REST with endpoint"),
    (
        {"restart": {"type": "rest_api", "endpoint_pattern": "restart", "pre_fetch_url": "/api/info"}},
        RESTRestartAction, "REST with endpoint_pattern"
    ),
    ({}, None, "Empty actions config"),
    ({"restart": {}}, None, "Empty restart config"),
    (None, None, "No actions config"),
]
# fmt: on


@pytest.mark.parametrize(
    "actions_config,expected_type,desc",
    TEST_FACTORY_REST_CASES,
)
def test_create_restart_action_rest(actions_config, expected_type, desc):
    """Test ActionFactory.create_restart_action with REST API configurations."""
    modem_config = {
        "timeout": TEST_TIMEOUT,
        "paradigm": "rest_api",
        "manufacturer": "TestMfg",
        "model": "TestModel",
    }
    if actions_config is not None:
        modem_config["actions"] = actions_config

    result = ActionFactory.create_restart_action(modem_config)

    if expected_type is None:
        assert result is None, f"Expected None for: {desc}"
    else:
        assert isinstance(result, expected_type), f"Expected {expected_type.__name__} for: {desc}"


def test_create_action_restart():
    """Test ActionFactory.create_action with RESTART action type."""
    modem_config = {
        "timeout": TEST_TIMEOUT,
        "paradigm": "hnap",
        "manufacturer": "Arris",
        "model": "S33",
        "auth": {
            "hnap": {
                "endpoint": "/HNAP1/",
                "namespace": "http://purenetworks.com/HNAP1/",
                "hmac_algorithm": "md5",
            }
        },
        "actions": {
            "restart": {
                "type": "hnap",
                "action_name": "SetArrisConfigurationInfo",
            }
        },
    }

    result = ActionFactory.create_action(ActionType.RESTART, modem_config)
    assert isinstance(result, HNAPRestartAction)


def test_supports_restart():
    """Test ActionFactory.supports() method."""
    # With actions.restart configured
    config_with_restart = {"actions": {"restart": {"type": "html_form", "endpoint": "/restart"}}}
    assert ActionFactory.supports(ActionType.RESTART, config_with_restart) is True

    # Without actions.restart
    config_without_restart = {"actions": {}}
    assert ActionFactory.supports(ActionType.RESTART, config_without_restart) is False

    # With no actions at all
    config_no_actions = {}
    assert ActionFactory.supports(ActionType.RESTART, config_no_actions) is False


class TestHNAPRestartActionInit:
    """Test HNAPRestartAction initialization."""

    def test_basic_config(self):
        """Test initialization with basic HNAP config."""
        modem_config = {
            "timeout": TEST_TIMEOUT,
            "paradigm": "hnap",
            "auth": {
                "hnap": {
                    "endpoint": "/HNAP1/",
                    "namespace": "http://purenetworks.com/HNAP1/",
                    "hmac_algorithm": "md5",
                    "empty_action_value": "",
                }
            },
            "actions": {
                "restart": {
                    "type": "hnap",
                    "action_name": "SetConfigurationInfo",
                    "params": {"Action": "reboot"},
                    "response_key": "SetConfigurationInfoResponse",
                    "result_key": "SetConfigurationInfoResult",
                    "success_value": "OK",
                }
            },
        }

        action = HNAPRestartAction(modem_config)
        assert action._action_name == "SetConfigurationInfo"
        assert action._endpoint == "/HNAP1/"
        assert action._namespace == "http://purenetworks.com/HNAP1/"
        assert action._hmac_algorithm == "md5"
        assert action._response_key == "SetConfigurationInfoResponse"
        assert action._result_key == "SetConfigurationInfoResult"

    def test_config_with_prefetch(self):
        """Test initialization with pre-fetch action config."""
        modem_config = {
            "timeout": TEST_TIMEOUT,
            "paradigm": "hnap",
            "auth": {
                "hnap": {
                    "endpoint": "/HNAP1/",
                    "namespace": "http://purenetworks.com/HNAP1/",
                    "hmac_algorithm": "md5",
                }
            },
            "actions": {
                "restart": {
                    "type": "hnap",
                    "action_name": "SetConfig",
                    "pre_fetch_action": "GetConfig",
                    "pre_fetch_response_key": "GetConfigResponse",
                    "params": {"Setting": "${value:default}"},
                    "response_key": "SetConfigResponse",
                    "result_key": "SetConfigResult",
                    "success_value": "OK",
                }
            },
        }

        action = HNAPRestartAction(modem_config)
        assert action._action_name == "SetConfig"
        assert action._pre_fetch_action == "GetConfig"
        assert action._pre_fetch_response_key == "GetConfigResponse"

    def test_fallback_to_deprecated_location(self):
        """Test that HNAP still reads from deprecated auth.hnap.actions.restart."""
        modem_config = {
            "timeout": TEST_TIMEOUT,
            "paradigm": "hnap",
            "auth": {
                "hnap": {
                    "endpoint": "/HNAP1/",
                    "namespace": "http://purenetworks.com/HNAP1/",
                    "hmac_algorithm": "md5",
                    "actions": {"restart": "LegacyRebootAction"},
                }
            },
            "actions": {
                "restart": {
                    "type": "hnap",
                    # No action_name - should fall back to auth.hnap.actions.restart
                }
            },
        }

        action = HNAPRestartAction(modem_config)
        assert action._action_name == "LegacyRebootAction"
