"""Tests for the config flow — wizard steps, options flow, reauth, helpers.

Mocks: load_modem_catalog, load_variant_list, validate_connection.
The config flow is tested through HA's flow machinery.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cable_modem_monitor.config_flow import (
    _build_prefix_options,
    _duration_to_seconds,
    _seconds_to_duration,
    _ValidationProgress,
)
from custom_components.cable_modem_monitor.const import DOMAIN

from .conftest import (
    FAKE_CATALOG,
    MOCK_ENTRY_DATA,
    MOCK_MULTI_VARIANTS,
    MOCK_SINGLE_VARIANT,
    MOCK_SUMMARIES,
    MOCK_VALIDATION_RESULT,
)

_PATCH_CATALOG_PATH = "custom_components.cable_modem_monitor.config_flow.CATALOG_PATH"

# All tests need the integration to be loadable
pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


# -----------------------------------------------------------------------
# Duration helpers — pure functions
# -----------------------------------------------------------------------

# ┌──────────┬───────────────────────────────────┬──────────────────┐
# │ seconds  │ expected dict                      │ description      │
# ├──────────┼───────────────────────────────────┼──────────────────┤
# │ 600      │ {hours: 0, minutes: 10, seconds: 0} │ 10 minutes     │
# │ 3661     │ {hours: 1, minutes: 1, seconds: 1}  │ mixed          │
# │ 0        │ {hours: 0, minutes: 0, seconds: 0}  │ zero           │
# │ 30       │ {hours: 0, minutes: 0, seconds: 30}│ seconds only    │
# └──────────┴───────────────────────────────────┴──────────────────┘
#
# fmt: off
DURATION_CASES = [
    (600,  {"hours": 0, "minutes": 10, "seconds": 0},  "10_minutes"),
    (3661, {"hours": 1, "minutes": 1,  "seconds": 1},  "mixed"),
    (0,    {"hours": 0, "minutes": 0,  "seconds": 0},  "zero"),
    (30,   {"hours": 0, "minutes": 0,  "seconds": 30}, "seconds_only"),
]
# fmt: on


@pytest.mark.parametrize("seconds,expected,desc", DURATION_CASES, ids=[c[2] for c in DURATION_CASES])
def test_seconds_to_duration(seconds, expected, desc):
    """_seconds_to_duration converts correctly."""
    assert _seconds_to_duration(seconds) == expected


# fmt: off
SECONDS_CASES = [
    ({"hours": 1, "minutes": 2, "seconds": 3}, 3723, "dict_full"),
    ({"minutes": 5},                            300,  "dict_partial"),
    (42,                                        42,   "raw_int"),
]
# fmt: on


@pytest.mark.parametrize("duration,expected,desc", SECONDS_CASES, ids=[c[2] for c in SECONDS_CASES])
def test_duration_to_seconds(duration, expected, desc):
    """_duration_to_seconds handles both dict and raw int."""
    assert _duration_to_seconds(duration) == expected


# -----------------------------------------------------------------------
# _build_prefix_options
# -----------------------------------------------------------------------


def test_prefix_options_first_entry():
    """First entry gets Default option."""
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = []
    options = _build_prefix_options(hass)
    values = [o["value"] for o in options]
    assert "none" in values  # "Default" option


def test_prefix_options_none_in_use():
    """When 'none' prefix already used, Default is removed."""
    hass = MagicMock()
    existing = MagicMock()
    existing.data = {"entity_prefix": "none"}
    hass.config_entries.async_entries.return_value = [existing]
    options = _build_prefix_options(hass)
    values = [o["value"] for o in options]
    assert "none" not in values
    assert "model" in values
    assert "ip" in values


# -----------------------------------------------------------------------
# _ValidationProgress
# -----------------------------------------------------------------------


def test_validation_progress_lifecycle():
    """Progress tracks task state and collects results."""
    progress = _ValidationProgress()
    assert not progress.is_running()
    assert progress.result is None
    assert progress.error is None

    progress.reset()
    assert progress.task is None
    assert progress.error_key == "unknown"


async def test_validation_progress_collect_no_task():
    """Collect returns False when no task was started."""
    progress = _ValidationProgress()
    assert await progress.collect() is False


async def test_validation_progress_runtime_error():
    """RuntimeError extracts error key from colon-delimited message."""
    progress = _ValidationProgress()

    async def _raise():
        raise RuntimeError("error_type:modem_locked:Too many attempts")

    loop = asyncio.get_event_loop()
    progress.task = loop.create_task(_raise())
    await asyncio.sleep(0)  # let task complete

    assert await progress.collect() is False
    assert progress.error_key == "modem_locked"
    assert progress.task is None


async def test_validation_progress_unexpected_error():
    """Generic exceptions default to 'unknown' error key."""
    progress = _ValidationProgress()

    async def _raise():
        raise ValueError("something unexpected")

    loop = asyncio.get_event_loop()
    progress.task = loop.create_task(_raise())
    await asyncio.sleep(0)

    assert await progress.collect() is False
    assert progress.error_key == "unknown"
    assert isinstance(progress.error, ValueError)


# -----------------------------------------------------------------------
# Config flow — Step 1a: Manufacturer selection
# -----------------------------------------------------------------------


async def test_step_user_shows_form(hass: HomeAssistant):
    """Step 1a shows manufacturer dropdown."""
    with patch(
        "custom_components.cable_modem_monitor.config_flow.load_modem_catalog",
        return_value=MOCK_SUMMARIES,
    ):
        result: Any = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_step_user_selects_manufacturer(hass: HomeAssistant):
    """Selecting a manufacturer advances to model step."""
    with patch(
        "custom_components.cable_modem_monitor.config_flow.load_modem_catalog",
        return_value=MOCK_SUMMARIES,
    ):
        result: Any = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"manufacturer": "Solent Labs"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "model"


# -----------------------------------------------------------------------
# Config flow — Step 1b: Model selection
# -----------------------------------------------------------------------


async def test_step_model_selects_model_single_variant(hass: HomeAssistant):
    """Selecting a single-variant modem skips variant step."""
    with (
        patch(
            "custom_components.cable_modem_monitor.config_flow.load_modem_catalog",
            return_value=MOCK_SUMMARIES,
        ),
        patch(
            "custom_components.cable_modem_monitor.config_flow.load_variant_list",
            return_value=MOCK_SINGLE_VARIANT,
        ),
        patch(_PATCH_CATALOG_PATH, FAKE_CATALOG),
    ):
        # Step 1a — init flow
        result: Any = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        # Step 1a — select "All" manufacturers
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"manufacturer": "__all__"},
        )
        # Step 1b — select model (single variant → skip variant step)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"model": "Solent Labs/TPS-2000", "entity_prefix": "none"},
        )

    # Single-variant modem skips step 2, goes straight to connection
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connection"


# -----------------------------------------------------------------------
# Config flow — Step 2: Variant selection (multi-variant)
# -----------------------------------------------------------------------


async def test_step_variant_shown_for_multi_variant(hass: HomeAssistant):
    """Variant step shown when modem has multiple variants."""
    with (
        patch(
            "custom_components.cable_modem_monitor.config_flow.load_modem_catalog",
            return_value=MOCK_SUMMARIES,
        ),
        patch(
            "custom_components.cable_modem_monitor.config_flow.load_variant_list",
            return_value=MOCK_MULTI_VARIANTS,
        ),
        patch(_PATCH_CATALOG_PATH, FAKE_CATALOG),
    ):
        # Step 1a → Step 1b
        result: Any = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"manufacturer": "__all__"},
        )
        # Step 1b — select multi-variant modem (TPS-3000 has basic + form_nonce)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"model": "Solent Labs/TPS-3000", "entity_prefix": "none"},
        )

    # Multi-variant modem shows step 2
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "variant"


async def test_step_variant_advances_to_connection(hass: HomeAssistant):
    """Selecting a variant advances to connection step."""
    with (
        patch(
            "custom_components.cable_modem_monitor.config_flow.load_modem_catalog",
            return_value=MOCK_SUMMARIES,
        ),
        patch(
            "custom_components.cable_modem_monitor.config_flow.load_variant_list",
            return_value=MOCK_MULTI_VARIANTS,
        ),
        patch(_PATCH_CATALOG_PATH, FAKE_CATALOG),
    ):
        # Steps 1a → 1b → variant form
        result: Any = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"manufacturer": "__all__"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"model": "Solent Labs/TPS-3000", "entity_prefix": "none"},
        )
        # Step 2 — select variant
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"variant": "v2"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connection"


# -----------------------------------------------------------------------
# Config flow — Step 3: Connection details
# -----------------------------------------------------------------------


async def test_step_connection_shows_form(hass: HomeAssistant):
    """Connection step shows host and credential fields."""
    with (
        patch(
            "custom_components.cable_modem_monitor.config_flow.load_modem_catalog",
            return_value=MOCK_SUMMARIES,
        ),
        patch(
            "custom_components.cable_modem_monitor.config_flow.load_variant_list",
            return_value=MOCK_SINGLE_VARIANT,
        ),
        patch(_PATCH_CATALOG_PATH, FAKE_CATALOG),
    ):
        # Steps 1a → 1b → connection form (single variant, skips step 2)
        result: Any = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"manufacturer": "__all__"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"model": "Solent Labs/TPS-2000", "entity_prefix": "none"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connection"


# -----------------------------------------------------------------------
# Config flow — Step 4: Validation + entry creation
# -----------------------------------------------------------------------


async def test_full_flow_creates_entry(hass: HomeAssistant):
    """Complete flow through validation creates config entry."""
    with (
        patch(
            "custom_components.cable_modem_monitor.config_flow.load_modem_catalog",
            return_value=MOCK_SUMMARIES,
        ),
        patch(
            "custom_components.cable_modem_monitor.config_flow.load_variant_list",
            return_value=MOCK_SINGLE_VARIANT,
        ),
        patch(
            "custom_components.cable_modem_monitor.config_flow.validate_connection",
            return_value=MOCK_VALIDATION_RESULT,
        ),
        patch(
            "custom_components.cable_modem_monitor.async_setup_entry",
            return_value=True,
        ),
        patch(_PATCH_CATALOG_PATH, FAKE_CATALOG),
    ):
        # Step 1a → Step 1b → Step 3 (single variant, skip step 2)
        result: Any = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"manufacturer": "__all__"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"model": "Solent Labs/TPS-2000", "entity_prefix": "none"},
        )
        # Step 3 → connection details (triggers step 4 validation)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"host": "192.168.100.1"},
        )

        # Step 4 — drive through progress spinner states.
        # Mock validate_connection resolves instantly, so HA may skip
        # the spinner or condense the steps.
        while result["type"] in (FlowResultType.SHOW_PROGRESS, FlowResultType.SHOW_PROGRESS_DONE):
            result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Successful validation creates config entry
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Solent Labs TPS-2000 (192.168.100.1)"
    assert result["data"]["protocol"] == "http"
    assert result["data"]["manufacturer"] == "Solent Labs"


# -----------------------------------------------------------------------
# Config flow — Validation errors
# -----------------------------------------------------------------------


async def test_validation_connection_error_shows_form(hass: HomeAssistant):
    """Connection error during validation returns to connection form."""
    with (
        patch(
            "custom_components.cable_modem_monitor.config_flow.load_modem_catalog",
            return_value=MOCK_SUMMARIES,
        ),
        patch(
            "custom_components.cable_modem_monitor.config_flow.load_variant_list",
            return_value=MOCK_SINGLE_VARIANT,
        ),
        patch(
            "custom_components.cable_modem_monitor.config_flow.validate_connection",
            side_effect=ConnectionError("Modem unreachable"),
        ),
        patch(_PATCH_CATALOG_PATH, FAKE_CATALOG),
    ):
        # Steps 1a → 1b → 3 → 4 (validation raises ConnectionError)
        result: Any = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"manufacturer": "__all__"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"model": "Solent Labs/TPS-2000", "entity_prefix": "none"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"host": "192.168.100.1"},
        )

        # Drive through progress states after validation failure
        while result["type"] in (FlowResultType.SHOW_PROGRESS, FlowResultType.SHOW_PROGRESS_DONE):
            result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Connection error returns to step 3 with error banner
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connection"
    assert "base" in result.get("errors", {})


async def test_validation_auth_error(hass: HomeAssistant):
    """Auth error during validation shows error on connection form."""
    with (
        patch(
            "custom_components.cable_modem_monitor.config_flow.load_modem_catalog",
            return_value=MOCK_SUMMARIES,
        ),
        patch(
            "custom_components.cable_modem_monitor.config_flow.load_variant_list",
            return_value=MOCK_SINGLE_VARIANT,
        ),
        patch(
            "custom_components.cable_modem_monitor.config_flow.validate_connection",
            side_effect=PermissionError("auth_error:invalid_auth:Bad password"),
        ),
        patch(_PATCH_CATALOG_PATH, FAKE_CATALOG),
    ):
        # Steps 1a → 1b → 3 → 4 (validation raises PermissionError)
        result: Any = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"manufacturer": "__all__"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"model": "Solent Labs/TPS-2000", "entity_prefix": "none"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"host": "192.168.100.1"},
        )

        # Drive through progress states after auth failure
        while result["type"] in (FlowResultType.SHOW_PROGRESS, FlowResultType.SHOW_PROGRESS_DONE):
            result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Auth error returns to step 3 with specific error key
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connection"
    assert result["errors"]["base"] == "invalid_auth"


# -----------------------------------------------------------------------
# Options flow
# -----------------------------------------------------------------------


def _options_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a MockConfigEntry for options flow tests."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data=MOCK_ENTRY_DATA,
        options={},
    )
    entry.add_to_hass(hass)
    return entry


async def test_options_step_init_shows_form(hass: HomeAssistant):
    """Options init step shows form with current values."""
    entry = _options_entry(hass)

    with patch("custom_components.cable_modem_monitor.async_setup_entry", return_value=True):
        await hass.config_entries.async_setup(entry.entry_id)

    result: Any = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"


async def test_options_full_flow_success(hass: HomeAssistant):
    """Complete options flow validates and creates entry."""
    entry = _options_entry(hass)

    with (
        patch("custom_components.cable_modem_monitor.async_setup_entry", return_value=True),
        patch(
            "custom_components.cable_modem_monitor.config_flow.load_modem_catalog",
            return_value=MOCK_SUMMARIES,
        ),
        patch(
            "custom_components.cable_modem_monitor.config_flow.validate_connection",
            return_value=MOCK_VALIDATION_RESULT,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)

        result: Any = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "host": "192.168.100.1",
                "username": "admin",
                "password": "newpass",
                "scan_interval": {"hours": 0, "minutes": 5, "seconds": 0},
                "health_check_interval": {"hours": 0, "minutes": 1, "seconds": 0},
            },
        )

        # Drive through progress spinner
        while result["type"] in (FlowResultType.SHOW_PROGRESS, FlowResultType.SHOW_PROGRESS_DONE):
            result = await hass.config_entries.options.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["scan_interval"] == 300
    assert result["data"]["health_check_interval"] == 60


async def test_options_flow_validation_failure(hass: HomeAssistant):
    """Validation error in options flow shows error form."""
    entry = _options_entry(hass)

    with (
        patch("custom_components.cable_modem_monitor.async_setup_entry", return_value=True),
        patch(
            "custom_components.cable_modem_monitor.config_flow.load_modem_catalog",
            return_value=MOCK_SUMMARIES,
        ),
        patch(
            "custom_components.cable_modem_monitor.config_flow.validate_connection",
            side_effect=ConnectionError("Modem unreachable"),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)

        result: Any = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "host": "192.168.100.1",
                "username": "admin",
                "password": "pass",
                "scan_interval": {"hours": 0, "minutes": 10, "seconds": 0},
                "health_check_interval": {"hours": 0, "minutes": 0, "seconds": 30},
            },
        )

        while result["type"] in (FlowResultType.SHOW_PROGRESS, FlowResultType.SHOW_PROGRESS_DONE):
            result = await hass.config_entries.options.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"]["base"] == "network_unreachable"


async def test_options_password_preserved(hass: HomeAssistant):
    """Blank password in options preserves existing password from entry data."""
    entry = _options_entry(hass)

    with (
        patch("custom_components.cable_modem_monitor.async_setup_entry", return_value=True),
        patch(
            "custom_components.cable_modem_monitor.config_flow.load_modem_catalog",
            return_value=MOCK_SUMMARIES,
        ),
        patch(
            "custom_components.cable_modem_monitor.config_flow.validate_connection",
            return_value=MOCK_VALIDATION_RESULT,
        ) as mock_validate,
    ):
        await hass.config_entries.async_setup(entry.entry_id)

        result: Any = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "host": "192.168.100.1",
                "username": "admin",
                "password": "",  # blank — should preserve "password" from entry
                "scan_interval": {"hours": 0, "minutes": 10, "seconds": 0},
                "health_check_interval": {"hours": 0, "minutes": 0, "seconds": 30},
            },
        )

        while result["type"] in (FlowResultType.SHOW_PROGRESS, FlowResultType.SHOW_PROGRESS_DONE):
            result = await hass.config_entries.options.async_configure(result["flow_id"])

    # Validate was called with the original password, not blank
    call_kwargs = mock_validate.call_args
    assert call_kwargs.kwargs["password"] == "password"
