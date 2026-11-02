"""Tests for the Cable Modem card's websocket command and registration.

Covers card/commands.py and card/__init__.py. The layout itself is tested
with the builders in test_services.py; here only the transport is checked.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol
from homeassistant.exceptions import ServiceValidationError

from custom_components.cable_modem_monitor.card import CARD_MODULE, CARD_URL_BASE, async_register_card
from custom_components.cable_modem_monitor.card.commands import (
    CARD_CONFIG_COMMAND,
    ERR_CARD_UNAVAILABLE,
    ws_card_config,
)
from custom_components.cable_modem_monitor.const import VERSION
from custom_components.cable_modem_monitor.services import SERVICE_GENERATE_DASHBOARD_CARD_SCHEMA

_BUILD = "custom_components.cable_modem_monitor.card.commands.build_card_config"
_WATCH = "custom_components.cable_modem_monitor.card.commands.card_watch_entities"
_FRONTEND = Path(__file__).parents[2] / "custom_components" / "cable_modem_monitor" / "card" / "frontend"
_CARD = {"type": "vertical-stack", "cards": []}

# ┌────────────────────────────────┬────────────────────────────────────────┬───────────────────────────────┐
# │ message options                │ expected to builder                    │ description                   │
# ├────────────────────────────────┼────────────────────────────────────────┼───────────────────────────────┤
# │ omitted                        │ every generator default                │ defaults come from the schema │
# │ {"graph_hours": 48}            │ graph_hours 48, other defaults         │ explicit option kept          │
# │ {"include_errors": False}      │ include_errors False                   │ toggle passes through         │
# └────────────────────────────────┴────────────────────────────────────────┴───────────────────────────────┘
# fmt: off
OPTIONS_CASES: list[tuple[dict[str, Any] | None, dict[str, Any], str]] = [
    (None,                         {"graph_hours": 24, "include_errors": True},  "defaults_applied"),
    ({"graph_hours": 48},          {"graph_hours": 48, "include_errors": True},  "explicit_hours_kept"),
    ({"include_errors": False},    {"graph_hours": 24, "include_errors": False}, "toggle_passes_through"),
]
# fmt: on


@pytest.mark.parametrize("options,expected,desc", OPTIONS_CASES, ids=[c[2] for c in OPTIONS_CASES])
def test_card_config_passes_validated_options(
    options: dict[str, Any] | None, expected: dict[str, Any], desc: str
) -> None:
    """The message schema applies the generator's defaults before the builder runs."""
    msg: dict[str, Any] = {"id": 7, "type": CARD_CONFIG_COMMAND}
    if options is not None:
        msg["options"] = options
    validated = ws_card_config._ws_schema(msg)  # type: ignore[attr-defined]  # rationale: the decorator stores the schema here; HA validates with it before dispatch
    connection = MagicMock()
    with patch(_BUILD, return_value=_CARD) as build, patch(_WATCH, return_value=["sensor.ds", "sensor.us"]):
        ws_card_config(MagicMock(), connection, validated)
    passed = build.call_args.args[1]
    assert {key: passed[key] for key in expected} == expected, desc
    connection.send_result.assert_called_once_with(7, {"card": _CARD, "watch": ["sensor.ds", "sensor.us"]})
    connection.send_error.assert_not_called()


def test_card_config_unavailable_modem_sends_error() -> None:
    """No modem, or one with no data, reaches the card as an error with the reason."""
    connection = MagicMock()
    with patch(_BUILD, side_effect=ServiceValidationError("No modem data available")):
        ws_card_config(MagicMock(), connection, {"id": 3, "options": {}})
    connection.send_error.assert_called_once_with(3, ERR_CARD_UNAVAILABLE, "No modem data available")
    connection.send_result.assert_not_called()


def test_card_config_rejects_invalid_options() -> None:
    """An out-of-range option fails the message schema, as it fails the action's."""
    with pytest.raises(vol.Invalid):
        ws_card_config._ws_schema(  # type: ignore[attr-defined]  # rationale: schema stored by the decorator
            {"id": 1, "type": CARD_CONFIG_COMMAND, "options": {"graph_hours": 999}}
        )


async def test_async_register_card_serves_and_loads_the_module() -> None:
    """Registration wires the command, the static path, and the versioned JS URL."""
    hass = _hass_with_components({"frontend", "http"})
    with (
        patch("custom_components.cable_modem_monitor.card.websocket_api.async_register_command") as register,
        patch("custom_components.cable_modem_monitor.card.add_extra_js_url") as add_url,
    ):
        await async_register_card(hass)
    register.assert_called_once_with(hass, ws_card_config)
    (config,) = hass.http.async_register_static_paths.call_args.args[0]
    assert config.url_path == CARD_URL_BASE
    assert Path(config.path) == _FRONTEND
    assert (_FRONTEND / CARD_MODULE).is_file()
    add_url.assert_called_once_with(hass, f"{CARD_URL_BASE}/{CARD_MODULE}?v={VERSION}")


# ┌──────────────────────┬───────────────────────┬──────────────────────────────────────┐
# │ components loaded    │ registers the card    │ description                          │
# ├──────────────────────┼───────────────────────┼──────────────────────────────────────┤
# │ frontend + http      │ yes                   │ normal install                       │
# │ http only            │ no                    │ no frontend: nothing to load into    │
# │ frontend only        │ no                    │ no http: nothing to serve from       │
# │ neither              │ no                    │ headless install                     │
# └──────────────────────┴───────────────────────┴──────────────────────────────────────┘
# fmt: off
COMPONENT_CASES: list[tuple[set[str], bool, str]] = [
    ({"frontend", "http"}, True,  "normal_install"),
    ({"http"},             False, "no_frontend"),
    ({"frontend"},         False, "no_http"),
    (set(),                False, "headless"),
]
# fmt: on


def _hass_with_components(components: set[str]) -> MagicMock:
    """A hass double with *components* loaded and an awaitable static-path hook."""
    hass = MagicMock()
    hass.config.components = components
    hass.http.async_register_static_paths = AsyncMock()
    return hass


@pytest.mark.parametrize("components,registers,desc", COMPONENT_CASES, ids=[c[2] for c in COMPONENT_CASES])
async def test_async_register_card_skips_without_frontend_or_http(
    components: set[str], registers: bool, desc: str
) -> None:
    """The card registers only where it can be served and loaded; it never raises."""
    hass = _hass_with_components(components)
    with (
        patch("custom_components.cable_modem_monitor.card.websocket_api.async_register_command") as register,
        patch("custom_components.cable_modem_monitor.card.add_extra_js_url") as add_url,
    ):
        await async_register_card(hass)
    assert register.called is registers, desc
    assert add_url.called is registers, desc


async def test_async_register_card_failure_never_propagates(caplog: pytest.LogCaptureFixture) -> None:
    """A registration failure is logged; the integration still loads."""
    hass = _hass_with_components({"frontend", "http"})
    hass.http.async_register_static_paths = AsyncMock(side_effect=RuntimeError("path exists"))
    with patch("custom_components.cable_modem_monitor.card.websocket_api.async_register_command"):
        await async_register_card(hass)
    assert "monitoring is unaffected" in caplog.text


def test_editor_fields_match_the_generator_schema() -> None:
    """Every form field is a generator option, with the generator's default."""
    source = (_FRONTEND / CARD_MODULE).read_text()
    fields = {name: default for name, default in re.findall(r'\{ name: "(\w+)"(?:, default: (\w+))?', source)}
    schema_keys = {str(key): key for key in SERVICE_GENERATE_DASHBOARD_CARD_SCHEMA.schema}
    assert len(fields) == 12, "expected the 12 editor fields"
    assert set(fields) <= set(schema_keys)
    literals = {"true": True, "false": False, "24": 24}
    for name, default in fields.items():
        if default:
            assert literals[default] == schema_keys[name].default(), name
        else:
            assert name == "device_id", f"{name} has no default in the form"
