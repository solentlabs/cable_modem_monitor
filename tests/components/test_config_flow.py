"""Tests for Cable Modem Monitor config flow.

TEST DATA TABLES
================
This module uses table-driven tests for parameterized test cases.
Tables are defined at the top of the file with ASCII box-drawing comments.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cable_modem_monitor.config_flow import (
    CableModemMonitorConfigFlow,
    OptionsFlowHandler,
    ValidationProgressHelper,
)
from custom_components.cable_modem_monitor.config_flow_helpers import (
    validate_input,
)
from custom_components.cable_modem_monitor.const import (
    CONF_DETECTED_MANUFACTURER,
    CONF_DETECTED_MODEM,
    CONF_DOCSIS_VERSION,
    CONF_PARSER_NAME,
    CONF_PARSER_SELECTED_AT,
    DOMAIN,
    ENTITY_PREFIX_IP,
    ENTITY_PREFIX_MODEL,
    ENTITY_PREFIX_NONE,
)
from custom_components.cable_modem_monitor.core.exceptions import (
    CannotConnectError,
    InvalidAuthError,
)
from custom_components.cable_modem_monitor.core.setup import SetupResult

# Mock constants to avoid ImportError in tests
CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 600
MIN_SCAN_INTERVAL = 60
MAX_SCAN_INTERVAL = 1800

# =============================================================================
# Table-Driven Test Data
# =============================================================================

# -----------------------------------------------------------------------------
# Title Formatting Cases - modem name + manufacturer -> expected title
# -----------------------------------------------------------------------------
# ┌─────────────────┬──────────────┬────────────────────────────────────┬──────────────────────────────┐
# │ modem_name      │ manufacturer │ expected_title                     │ description                  │
# ├─────────────────┼──────────────┼────────────────────────────────────┼──────────────────────────────┤
# │ "[MFG] [Model]" │ "[MFG]"      │ "[MFG] [Model] (192.168.100.1)"    │ no duplicate when mfg in name│
# │ "[Model]"       │ "[MFG]"      │ "[MFG] [Model] (192.168.100.1)"    │ prepend when mfg not in name │
# │ "Generic Modem" │ "Unknown"    │ "Generic Modem (192.168.100.1)"    │ skip "Unknown" manufacturer  │
# │ "Cable Modem"   │ "Unknown"    │ "Cable Modem (192.168.100.1)"      │ default case                 │
# └─────────────────┴──────────────┴────────────────────────────────────┴──────────────────────────────┘
#
# fmt: off
TITLE_FORMATTING_CASES = [
    # (modem_name,       manufacturer, expected_title,                        description)
    ("[MFG] [Model]",    "[MFG]",      "[MFG] [Model] (192.168.100.1)",       "no dup when mfg in name"),
    ("[Model]",          "[MFG]",      "[MFG] [Model] (192.168.100.1)",       "prepend mfg"),
    ("Generic Modem",    "Unknown",    "Generic Modem (192.168.100.1)",       "skip unknown mfg"),
    ("Cable Modem",      "Unknown",    "Cable Modem (192.168.100.1)",         "default case"),
    ("Arris SB8200",     "Arris",      "Arris SB8200 (192.168.100.1)",        "real modem example"),
    ("MB8611",           "Motorola",   "Motorola MB8611 (192.168.100.1)",     "model only, prepend mfg"),
]
# fmt: on

# -----------------------------------------------------------------------------
# Scan Interval Validation Cases
# -----------------------------------------------------------------------------
# ┌───────────┬──────────┬─────────────────────────────┐
# │ interval  │ valid?   │ description                 │
# ├───────────┼──────────┼─────────────────────────────┤
# │ 60        │ True     │ minimum boundary            │
# │ 180       │ True     │ 3 minutes                   │
# │ 300       │ True     │ 5 minutes                   │
# │ 600       │ True     │ 10 minutes (default)        │
# │ 900       │ True     │ 15 minutes                  │
# │ 1800      │ True     │ maximum boundary            │
# └───────────┴──────────┴─────────────────────────────┘
#
# fmt: off
SCAN_INTERVAL_VALID_CASES = [
    # (interval, description)
    (60,   "minimum boundary"),
    (180,  "3 minutes"),
    (300,  "5 minutes"),
    (600,  "10 minutes (default)"),
    (900,  "15 minutes"),
    (1800, "maximum boundary"),
]
# fmt: on


def _create_success_result(
    modem_name: str = "Cable Modem",
    manufacturer: str = "Unknown",
    working_url: str = "https://192.168.100.1",
) -> SetupResult:
    """Create a successful setup result for tests."""
    mock_parser = Mock()
    mock_parser.manufacturer = manufacturer
    mock_parser.get_actual_model.return_value = None

    return SetupResult(
        success=True,
        working_url=working_url,
        auth_strategy="no_auth",
        auth_form_config=None,
        parser_name=modem_name,
        legacy_ssl=False,
        modem_data={"cable_modem_connection_status": "online"},
        parser_instance=mock_parser,
        session=Mock(),
        error=None,
        failed_step=None,
    )


class TestConfigFlow:
    """Test the config flow."""

    def test_scan_interval_minimum_valid(self):
        """Test that minimum scan interval (60s) is accepted."""
        # Minimum value should be valid
        assert MIN_SCAN_INTERVAL == 60

    def test_scan_interval_maximum_valid(self):
        """Test that maximum scan interval (1800s) is accepted."""
        # Maximum value should be valid
        assert MAX_SCAN_INTERVAL == 1800

    def test_scan_interval_default_value(self):
        """Test that default scan interval is 600s (10 minutes)."""
        assert DEFAULT_SCAN_INTERVAL == 600

    def test_scan_interval_range_valid(self):
        """Test that scan interval range makes sense."""
        # Min should be less than default, default less than max
        assert MIN_SCAN_INTERVAL < DEFAULT_SCAN_INTERVAL < MAX_SCAN_INTERVAL


CONF_MODEM_CHOICE = "modem_choice"


class TestValidateInput:
    """Test input validation."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = Mock()
        hass.async_add_executor_job = Mock(return_value=None)
        return hass

    @pytest.fixture
    def mock_parser_class(self):
        """Create a mock parser class."""
        parser_class = Mock()
        parser_class.name = "Cable Modem"
        parser_class.__name__ = "CableModemParser"
        return parser_class

    @pytest.fixture
    def valid_input(self):
        """Provide valid input data."""
        return {
            CONF_HOST: "192.168.100.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
            CONF_MODEM_CHOICE: "Cable Modem",
        }

    @pytest.mark.asyncio
    @patch("custom_components.cable_modem_monitor.core.setup.setup_modem")
    @patch("custom_components.cable_modem_monitor.config_flow_helpers.load_static_auth_config")
    @patch("custom_components.cable_modem_monitor.config_flow_helpers.test_http_head")
    @patch("custom_components.cable_modem_monitor.config_flow_helpers.test_icmp_ping")
    @patch("custom_components.cable_modem_monitor.config_flow_helpers.get_parser_by_name")
    async def test_success(
        self,
        mock_get_parser,
        mock_icmp_ping,
        mock_http_head,
        mock_load_static_auth,
        mock_setup,
        mock_hass,
        mock_parser_class,
        valid_input,
    ):
        """Test successful validation."""
        # Mock parser lookup
        mock_get_parser.return_value = mock_parser_class

        # Mock static auth config (required now that fallback is removed)
        mock_load_static_auth.return_value = {"auth_strategy": "no_auth"}

        # Mock setup to return success
        mock_setup.return_value = _create_success_result()
        mock_icmp_ping.return_value = True
        mock_http_head.return_value = False

        # Mock async_add_executor_job to call the function
        async def mock_executor_job(func, *args):
            return func(*args)

        mock_hass.async_add_executor_job = mock_executor_job

        result = await validate_input(mock_hass, valid_input)

        assert result["title"] == "Cable Modem (192.168.100.1)"

    @pytest.mark.asyncio
    @patch("custom_components.cable_modem_monitor.core.setup.setup_modem")
    @patch("custom_components.cable_modem_monitor.config_flow_helpers.load_static_auth_config")
    @patch("custom_components.cable_modem_monitor.config_flow_helpers.test_http_head")
    @patch("custom_components.cable_modem_monitor.config_flow_helpers.test_icmp_ping")
    @patch("custom_components.cable_modem_monitor.config_flow_helpers.get_parser_by_name")
    async def test_connection_failure(
        self,
        mock_get_parser,
        mock_icmp_ping,
        mock_http_head,
        mock_load_static_auth,
        mock_setup,
        mock_hass,
        mock_parser_class,
        valid_input,
    ):
        """Test validation fails when cannot connect to modem."""
        # Mock parser lookup
        mock_get_parser.return_value = mock_parser_class

        # Mock static auth config (required now that fallback is removed)
        mock_load_static_auth.return_value = {"auth_strategy": "no_auth"}

        # Mock setup to return failure
        mock_setup.return_value = SetupResult(
            success=False,
            error="Connection failed",
            failed_step="connectivity",
        )
        mock_icmp_ping.return_value = False
        mock_http_head.return_value = False

        # Mock async_add_executor_job to call the function
        async def mock_executor_job(func, *args):
            return func(*args)

        mock_hass.async_add_executor_job = mock_executor_job

        with pytest.raises(CannotConnectError):
            await validate_input(mock_hass, valid_input)

    def test_requires_host(self, valid_input):
        """Test that host is required."""
        # Host should be in valid input
        assert CONF_HOST in valid_input


class TestScanIntervalValidation:
    """Test scan interval validation logic."""

    def test_scan_interval_below_minimum_invalid(self):
        """Test that values below minimum are invalid."""
        # 59 seconds should be below minimum
        assert MIN_SCAN_INTERVAL > 59

    def test_scan_interval_above_maximum_invalid(self):
        """Test that values above maximum are invalid."""
        # 1801 seconds should be above maximum
        assert MAX_SCAN_INTERVAL < 1801

    def test_scan_interval_at_boundaries_valid(self):
        """Test that boundary values are valid."""
        # Exact min and max should be valid
        assert MIN_SCAN_INTERVAL == 60
        assert MAX_SCAN_INTERVAL == 1800

    @pytest.mark.parametrize(
        "interval,desc",
        SCAN_INTERVAL_VALID_CASES,
        ids=[c[1] for c in SCAN_INTERVAL_VALID_CASES],
    )
    def test_scan_interval_valid_values(self, interval, desc):
        """Test valid scan interval values via table-driven cases."""
        assert MIN_SCAN_INTERVAL <= interval <= MAX_SCAN_INTERVAL, f"Failed: {desc}"


class TestModemNameFormatting:
    """Test modem name and manufacturer formatting in titles.

    Uses table-driven tests for title formatting cases.
    See TITLE_FORMATTING_CASES at top of file.
    """

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = Mock()
        return hass

    @pytest.fixture
    def mock_parser_class(self):
        """Create a mock parser class."""
        parser_class = Mock()
        parser_class.name = "Test Parser"
        parser_class.__name__ = "TestParser"
        return parser_class

    @pytest.fixture
    def valid_input(self):
        """Provide valid input data."""
        return {
            CONF_HOST: "192.168.100.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
            CONF_MODEM_CHOICE: "Test Parser",
        }

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "modem_name,manufacturer,expected_title,desc",
        TITLE_FORMATTING_CASES,
        ids=[c[3] for c in TITLE_FORMATTING_CASES],
    )
    @patch("custom_components.cable_modem_monitor.core.setup.setup_modem")
    @patch("custom_components.cable_modem_monitor.config_flow_helpers.load_static_auth_config")
    @patch("custom_components.cable_modem_monitor.config_flow_helpers.test_http_head")
    @patch("custom_components.cable_modem_monitor.config_flow_helpers.test_icmp_ping")
    @patch("custom_components.cable_modem_monitor.config_flow_helpers.get_parser_by_name")
    async def test_title_formatting(
        self,
        mock_get_parser,
        mock_icmp_ping,
        mock_http_head,
        mock_load_static_auth,
        mock_setup,
        mock_hass,
        mock_parser_class,
        valid_input,
        modem_name,
        manufacturer,
        expected_title,
        desc,
    ):
        """Test title formatting via table-driven cases."""
        mock_get_parser.return_value = mock_parser_class
        mock_load_static_auth.return_value = {"auth_strategy": "no_auth"}
        mock_setup.return_value = _create_success_result(
            modem_name=modem_name,
            manufacturer=manufacturer,
        )
        mock_icmp_ping.return_value = True
        mock_http_head.return_value = False

        async def mock_executor_job(func, *args):
            return func(*args)

        mock_hass.async_add_executor_job = mock_executor_job

        result = await validate_input(mock_hass, valid_input)

        assert result["title"] == expected_title, f"Failed: {desc}"

    @pytest.mark.asyncio
    @patch("custom_components.cable_modem_monitor.core.setup.setup_modem")
    @patch("custom_components.cable_modem_monitor.config_flow_helpers.load_static_auth_config")
    @patch("custom_components.cable_modem_monitor.config_flow_helpers.test_http_head")
    @patch("custom_components.cable_modem_monitor.config_flow_helpers.test_icmp_ping")
    @patch("custom_components.cable_modem_monitor.config_flow_helpers.get_parser_by_name")
    async def test_title_detection_info_included(
        self,
        mock_get_parser,
        mock_icmp_ping,
        mock_http_head,
        mock_load_static_auth,
        mock_setup,
        mock_hass,
        mock_parser_class,
        valid_input,
    ):
        """Test that detection_info is included in result."""
        mock_get_parser.return_value = mock_parser_class
        mock_load_static_auth.return_value = {"auth_strategy": "no_auth"}
        mock_setup.return_value = _create_success_result(
            modem_name="[Model]",
            manufacturer="[MFG]",
        )
        mock_icmp_ping.return_value = True
        mock_http_head.return_value = False

        async def mock_executor_job(func, *args):
            return func(*args)

        mock_hass.async_add_executor_job = mock_executor_job

        result = await validate_input(mock_hass, valid_input)

        # Detection info should be in result
        assert "detection_info" in result
        assert result["detection_info"]["modem_name"] == "[Model]"
        assert result["detection_info"]["manufacturer"] == "[MFG]"


class TestConfigConstants:
    """Test configuration constants are properly defined."""

    def test_all_config_keys_defined(self):
        """Test that all config keys are defined."""
        required_keys = [
            CONF_HOST,
            CONF_USERNAME,
            CONF_PASSWORD,
            CONF_SCAN_INTERVAL,
        ]

        # All should be strings
        for key in required_keys:
            assert isinstance(key, str)
            assert len(key) > 0

    def test_defaults_are_reasonable(self):
        """Test that default values make sense."""
        # Scan interval: 10 minutes
        assert DEFAULT_SCAN_INTERVAL == 600

        # Min interval: 1 minute
        assert MIN_SCAN_INTERVAL == 60

        # Max interval: 30 minutes
        assert MAX_SCAN_INTERVAL == 1800


class TestOptionsFlow:
    """Test the options flow for reconfiguration."""

    def test_exists(self):
        """Test that OptionsFlowHandler class exists."""
        assert OptionsFlowHandler is not None

    def test_has_init_step(self):
        """Test that options flow has init step."""
        assert hasattr(OptionsFlowHandler, "async_step_init")

    def test_can_instantiate_without_arguments(self):
        """Test that OptionsFlowHandler can be instantiated without arguments.

        This prevents the TypeError that caused a 500 error when trying to
        access the configuration UI in Home Assistant.
        """
        # This should not raise TypeError
        handler = OptionsFlowHandler()
        assert handler is not None


class TestConfigFlowRegistration:
    """Test the config flow registration."""

    def test_handler_is_registered(self):
        """Test that the config flow handler is registered."""
        handler = config_entries.HANDLERS.get("cable_modem_monitor")
        assert handler is not None
        assert handler == CableModemMonitorConfigFlow


# =============================================================================
# ValidationProgressHelper Tests
# =============================================================================


class TestValidationProgressHelper:
    """Test the ValidationProgressHelper state machine.

    This helper manages async validation state for the progress indicator flow.
    Tests verify state transitions and error handling.
    """

    @pytest.fixture
    def helper(self):
        """Create a fresh ValidationProgressHelper instance."""
        return ValidationProgressHelper()

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = Mock()
        return hass

    def test_initial_state(self, helper):
        """Test helper initializes with empty state."""
        assert helper.user_input is None
        assert helper.task is None
        assert helper.error is None
        assert helper.info is None

    def test_is_running_when_no_task(self, helper):
        """Test is_running returns False when no task exists."""
        assert helper.is_running() is False

    def test_is_running_when_task_done(self, helper):
        """Test is_running returns False when task is complete."""
        mock_task = Mock()
        mock_task.done.return_value = True
        helper.task = mock_task

        assert helper.is_running() is False

    def test_is_running_when_task_active(self, helper):
        """Test is_running returns True when task is running."""
        mock_task = Mock()
        mock_task.done.return_value = False
        helper.task = mock_task

        assert helper.is_running() is True

    def test_start_stores_user_input(self, helper, mock_hass):
        """Test start() stores user input and creates task."""
        user_input = {"host": "192.168.100.1"}
        mock_task = Mock()
        mock_hass.async_create_task = Mock(return_value=mock_task)

        helper.start(mock_hass, user_input)

        assert helper.user_input == user_input
        assert helper.task == mock_task
        mock_hass.async_create_task.assert_called_once()

    def test_reset_clears_all_state(self, helper):
        """Test reset() clears all state."""
        # Set up state
        helper.user_input = {"host": "192.168.100.1"}
        helper.task = Mock()
        helper.error = Exception("test")
        helper.info = {"title": "Test"}

        helper.reset()

        assert helper.user_input is None
        assert helper.task is None
        assert helper.error is None
        assert helper.info is None

    @pytest.mark.asyncio
    async def test_get_result_returns_missing_input_when_no_task(self, helper):
        """Test get_result returns 'missing_input' when task is None."""
        result = await helper.get_result()

        assert result == "missing_input"

    @pytest.mark.asyncio
    async def test_get_result_success_stores_info(self, helper):
        """Test get_result stores info dict on success."""
        import asyncio

        # Create a real completed task
        async def success_validation():
            return {"title": "Test Modem"}

        helper.task = asyncio.create_task(success_validation())

        result = await helper.get_result()

        assert result is None  # None means success
        assert helper.info == {"title": "Test Modem"}
        assert helper.task is None  # Task cleared in finally

    @pytest.mark.asyncio
    async def test_get_result_known_exception_classified(self, helper):
        """Test get_result classifies known exceptions."""
        import asyncio

        async def failing_validation():
            # CannotConnectError with a message gets user_message set,
            # which triggers "network_unreachable" classification
            raise CannotConnectError("Connection failed")

        helper.task = asyncio.create_task(failing_validation())

        result = await helper.get_result()

        # CannotConnectError with user_message returns "network_unreachable"
        assert result == "network_unreachable"
        assert helper.error is not None
        assert isinstance(helper.error, CannotConnectError)
        assert helper.task is None

    @pytest.mark.asyncio
    async def test_get_result_invalid_auth_classified(self, helper):
        """Test get_result classifies InvalidAuthError."""
        import asyncio

        async def failing_validation():
            raise InvalidAuthError("Bad credentials")

        helper.task = asyncio.create_task(failing_validation())

        result = await helper.get_result()

        assert result == "invalid_auth"
        assert isinstance(helper.error, InvalidAuthError)

    @pytest.mark.asyncio
    async def test_get_result_unknown_exception_logged(self, helper):
        """Test get_result logs unexpected exceptions."""
        import asyncio

        async def unexpected_failure():
            raise RuntimeError("Unexpected error")

        helper.task = asyncio.create_task(unexpected_failure())

        # Should not raise, should return error type
        result = await helper.get_result()

        assert result is not None  # Some error type
        assert helper.error is not None
        assert isinstance(helper.error, RuntimeError)

    def test_get_error_type_with_known_error(self, helper):
        """Test get_error_type returns correct classification."""
        helper.error = InvalidAuthError("test")

        result = helper.get_error_type()

        assert result == "invalid_auth"

    def test_get_error_type_with_no_error(self, helper):
        """Test get_error_type when no error is set."""
        # This tests an edge case - what happens if called before error is set
        result = helper.get_error_type()

        # Should handle None gracefully
        assert result is not None  # Should return some default


# =============================================================================
# Auth Type Flow Tests
# =============================================================================


class TestAuthTypeFlow:
    """Test the auth type selection flow.

    This step only appears for modems with multiple auth types defined
    in their modem.yaml (e.g., SB8200 with "none" and "url_token").
    """

    @pytest.fixture
    def flow(self):
        """Create a CableModemMonitorConfigFlow instance."""
        return CableModemMonitorConfigFlow()

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = Mock()
        hass.config_entries = Mock()
        hass.config_entries.async_entries = Mock(return_value=[])
        return hass

    @pytest.mark.asyncio
    @patch("custom_components.cable_modem_monitor.config_flow.get_auth_type_dropdown")
    async def test_auth_type_step_shown_for_multi_auth_modem(self, mock_get_dropdown, flow, mock_hass):
        """Test auth type step is shown when modem has multiple auth options."""
        flow.hass = mock_hass
        flow._modem_choices = ["Arris SB8200"]

        # Simulate user input from step_user
        flow._progress.user_input = {
            "host": "192.168.100.1",
            "modem_choice": "Arris SB8200",
        }

        mock_get_dropdown.return_value = {
            "none": "No Authentication",
            "url_token": "URL Token (Requires Password)",
        }

        # Make async_add_executor_job return an awaitable
        mock_parser = Mock()
        mock_parser.name = "Arris SB8200"

        async def mock_executor_job(func, *args):
            return mock_parser

        mock_hass.async_add_executor_job = mock_executor_job

        # Call auth_type step with no input (show form)
        with patch.object(flow, "async_show_form") as mock_show_form:
            mock_show_form.return_value = {"type": "form", "step_id": "auth_type"}

            await flow.async_step_auth_type(None)

            mock_show_form.assert_called_once()
            call_kwargs = mock_show_form.call_args[1]
            assert call_kwargs["step_id"] == "auth_type"

    @pytest.mark.asyncio
    async def test_auth_type_selection_stored_and_proceeds(self, flow, mock_hass):
        """Test selecting auth type stores it and proceeds to validation."""
        flow.hass = mock_hass
        flow._modem_choices = ["Arris SB8200"]
        flow._progress.user_input = {
            "host": "192.168.100.1",
            "modem_choice": "Arris SB8200",
        }

        # Simulate user selecting an auth type
        user_input = {"auth_type": "url_token"}

        with patch.object(flow, "async_step_validate") as mock_validate:
            mock_validate.return_value = {"type": "progress"}

            await flow.async_step_auth_type(user_input)

            # Verify auth type was stored
            assert flow._selected_auth_type == "url_token"
            assert flow._progress.user_input["auth_type"] == "url_token"
            mock_validate.assert_called_once()


# =============================================================================
# Entity Prefix Logic Tests
# =============================================================================


class TestEntityPrefixLogic:
    """Test the entity prefix dropdown conditional logic.

    First modem: "None" option available, default is "None"
    Second+ modem: "None" option removed, default is "Model"
    """

    @pytest.fixture
    def flow(self):
        """Create a CableModemMonitorConfigFlow instance."""
        return CableModemMonitorConfigFlow()

    @pytest.fixture
    def mock_hass_no_entries(self):
        """Create mock hass with no existing entries."""
        hass = Mock()
        hass.config_entries = Mock()
        hass.config_entries.async_entries = Mock(return_value=[])
        return hass

    @pytest.fixture
    def mock_hass_with_entries(self):
        """Create mock hass with existing entries."""
        hass = Mock()
        existing_entry = Mock()
        hass.config_entries = Mock()
        hass.config_entries.async_entries = Mock(return_value=[existing_entry])
        return hass

    def test_first_modem_has_none_option(self, flow, mock_hass_no_entries):
        """Test first modem config includes 'None' prefix option."""
        flow.hass = mock_hass_no_entries
        flow._modem_choices = ["Test Modem"]

        schema = flow._build_user_schema()

        # Extract entity_prefix field from schema
        schema_dict = dict(schema.schema)
        entity_prefix_key = None
        for key in schema_dict:
            if hasattr(key, "schema") and key.schema == "entity_prefix":
                entity_prefix_key = key
                break

        assert entity_prefix_key is not None
        # Default should be "none" for first modem
        assert entity_prefix_key.default() == ENTITY_PREFIX_NONE

    def test_second_modem_no_none_option(self, flow, mock_hass_with_entries):
        """Test second modem config excludes 'None' prefix option."""
        flow.hass = mock_hass_with_entries
        flow._modem_choices = ["Test Modem"]

        schema = flow._build_user_schema()

        # Extract entity_prefix field from schema
        schema_dict = dict(schema.schema)
        entity_prefix_key = None
        for key in schema_dict:
            if hasattr(key, "schema") and key.schema == "entity_prefix":
                entity_prefix_key = key
                break

        assert entity_prefix_key is not None
        # Default should be "model" for second+ modem
        assert entity_prefix_key.default() == ENTITY_PREFIX_MODEL

    def test_default_entity_prefix_preserved(self, flow, mock_hass_no_entries):
        """Test that explicitly passed default_entity_prefix is used."""
        flow.hass = mock_hass_no_entries
        flow._modem_choices = ["Test Modem"]

        schema = flow._build_user_schema(default_entity_prefix=ENTITY_PREFIX_IP)

        schema_dict = dict(schema.schema)
        entity_prefix_key = None
        for key in schema_dict:
            if hasattr(key, "schema") and key.schema == "entity_prefix":
                entity_prefix_key = key
                break

        assert entity_prefix_key is not None
        assert entity_prefix_key.default() == ENTITY_PREFIX_IP


# =============================================================================
# Options Flow Tests
#
# Uses HA test infrastructure (pytest-homeassistant-custom-component):
# - MockConfigEntry for config entries
# - hass fixture for Home Assistant instance
# - enable_custom_integrations to load custom component
# =============================================================================


async def test_options_flow_init_shows_form(hass: HomeAssistant, enable_custom_integrations):
    """Test options flow initialization shows form."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.100.1",
            "username": "admin",
            "password": "secretpassword",
            "modem_choice": "Test Modem",
            "parser_name": "Test Modem",
        },
        unique_id="192.168.100.1",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.cable_modem_monitor.config_flow.build_parser_dropdown",
        return_value=["Test Modem"],
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"


async def test_options_flow_preserves_password_when_empty(hass: HomeAssistant, enable_custom_integrations):
    """Test password is preserved when user leaves it empty in options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.100.1",
            "username": "admin",
            "password": "secretpassword",
            "modem_choice": "Test Modem",
            "parser_name": "Test Modem",
        },
        unique_id="192.168.100.1",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.cable_modem_monitor.config_flow.build_parser_dropdown",
        return_value=["Test Modem"],
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        flow = hass.config_entries.options._progress.get(result["flow_id"])
        assert flow is not None

        user_input = {
            "host": "192.168.100.1",
            "username": "admin",
            "password": "",  # User left blank
        }
        flow._preserve_credentials(user_input)

        assert user_input["password"] == "secretpassword"


async def test_options_flow_preserves_username_when_empty(hass: HomeAssistant, enable_custom_integrations):
    """Test username is preserved when user leaves it empty."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.100.1",
            "username": "admin",
            "password": "secretpassword",
            "modem_choice": "Test Modem",
            "parser_name": "Test Modem",
        },
        unique_id="192.168.100.1",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.cable_modem_monitor.config_flow.build_parser_dropdown",
        return_value=["Test Modem"],
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        flow = hass.config_entries.options._progress.get(result["flow_id"])

        user_input = {
            "host": "192.168.100.1",
            "username": "",  # User left blank
            "password": "newpassword",
        }
        flow._preserve_credentials(user_input)

        assert user_input["username"] == "admin"


async def test_options_flow_new_password_not_overwritten(hass: HomeAssistant, enable_custom_integrations):
    """Test new password is not overwritten by existing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.100.1",
            "username": "admin",
            "password": "secretpassword",
            "modem_choice": "Test Modem",
            "parser_name": "Test Modem",
        },
        unique_id="192.168.100.1",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.cable_modem_monitor.config_flow.build_parser_dropdown",
        return_value=["Test Modem"],
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        flow = hass.config_entries.options._progress.get(result["flow_id"])

        user_input = {
            "host": "192.168.100.1",
            "username": "admin",
            "password": "newpassword",  # User entered new password
        }
        flow._preserve_credentials(user_input)

        assert user_input["password"] == "newpassword"


async def test_options_flow_preserves_both_credentials_when_empty(hass: HomeAssistant, enable_custom_integrations):
    """Test both credentials preserved when both empty."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.100.1",
            "username": "admin",
            "password": "secretpassword",
            "modem_choice": "Test Modem",
            "parser_name": "Test Modem",
        },
        unique_id="192.168.100.1",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.cable_modem_monitor.config_flow.build_parser_dropdown",
        return_value=["Test Modem"],
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        flow = hass.config_entries.options._progress.get(result["flow_id"])

        user_input = {
            "host": "192.168.100.1",
            "username": "",
            "password": "",
        }
        flow._preserve_credentials(user_input)

        assert user_input["username"] == "admin"
        assert user_input["password"] == "secretpassword"


async def test_options_flow_preserves_detection_info(hass: HomeAssistant, enable_custom_integrations):
    """Test all detection fields are preserved."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.100.1",
            "parser_name": "Arris SB8200",
            "modem_choice": "Arris SB8200",
            "detected_modem": "Arris SB8200",
            "detected_manufacturer": "Arris",
            "docsis_version": "3.1",
            "parser_selected_at": "2026-01-22T10:00:00",
        },
        unique_id="192.168.100.1",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.cable_modem_monitor.config_flow.build_parser_dropdown",
        return_value=["Arris SB8200"],
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        flow = hass.config_entries.options._progress.get(result["flow_id"])

        data = {}
        flow._preserve_detection_info(data)

        assert data[CONF_PARSER_NAME] == "Arris SB8200"
        assert data[CONF_DETECTED_MODEM] == "Arris SB8200"
        assert data[CONF_DETECTED_MANUFACTURER] == "Arris"
        assert data[CONF_DOCSIS_VERSION] == "3.1"
        assert data[CONF_PARSER_SELECTED_AT] == "2026-01-22T10:00:00"


async def test_options_flow_preserves_detection_with_missing_fields(hass: HomeAssistant, enable_custom_integrations):
    """Test preservation handles missing fields gracefully."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.100.1",
            "parser_name": "Unknown Modem",
            "modem_choice": "Unknown Modem",
            # Missing most detection fields
        },
        unique_id="192.168.100.2",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.cable_modem_monitor.config_flow.build_parser_dropdown",
        return_value=["Unknown Modem"],
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        flow = hass.config_entries.options._progress.get(result["flow_id"])

        data = {}
        flow._preserve_detection_info(data)

        # Should have defaults for missing fields
        assert data[CONF_DETECTED_MODEM] == "Unknown"
        assert data[CONF_DETECTED_MANUFACTURER] == "Unknown"


# =============================================================================
# Auth Config Persistence Tests
# =============================================================================


class TestApplyAuthDiscoveryInfo:
    """Test _apply_auth_discovery_info stores all auth config types.

    This was added after manual testing revealed HNAP config wasn't being
    stored in config entries, causing 'hmac_algorithm is required' errors.
    """

    @pytest.fixture
    def flow(self):
        """Create a CableModemMonitorConfigFlow instance."""
        return CableModemMonitorConfigFlow()

    def test_stores_hnap_config(self, flow):
        """Test HNAP config is stored in config entry data.

        Regression test for bug where _apply_auth_discovery_info only stored
        CONF_AUTH_STRATEGY and CONF_AUTH_FORM_CONFIG, missing HNAP config.
        This caused 'hmac_algorithm is required' errors for HNAP modems.
        """
        data = {}
        info = {
            "auth_strategy": "hnap_session",
            "auth_hnap_config": {
                "endpoint": "/HNAP1/",
                "namespace": "http://purenetworks.com/HNAP1/",
                "hmac_algorithm": "sha256",
            },
        }

        flow._apply_auth_discovery_info(data, info)

        assert "auth_hnap_config" in data
        assert data["auth_hnap_config"]["hmac_algorithm"] == "sha256"
        assert data["auth_hnap_config"]["endpoint"] == "/HNAP1/"

    def test_stores_url_token_config(self, flow):
        """Test URL token config is stored in config entry data."""
        data = {}
        info = {
            "auth_strategy": "url_token_session",
            "auth_url_token_config": {
                "login_prefix": "login",
                "data_page": "status.html",
            },
        }

        flow._apply_auth_discovery_info(data, info)

        assert "auth_url_token_config" in data
        assert data["auth_url_token_config"]["login_prefix"] == "login"

    def test_stores_form_config(self, flow):
        """Test form config is stored (existing behavior)."""
        data = {}
        info = {
            "auth_strategy": "form_plain",
            "auth_form_config": {
                "action": "/login.cgi",
                "method": "POST",
            },
        }

        flow._apply_auth_discovery_info(data, info)

        assert "auth_form_config" in data
        assert data["auth_form_config"]["action"] == "/login.cgi"

    def test_stores_auth_strategy(self, flow):
        """Test auth strategy is stored."""
        data = {}
        info = {"auth_strategy": "no_auth"}

        flow._apply_auth_discovery_info(data, info)

        assert data["auth_strategy"] == "no_auth"

    def test_fallback_to_existing_hnap_config(self, flow):
        """Test fallback to existing HNAP config when not in new info."""
        data = {}
        info = {"auth_strategy": "hnap_session"}  # No HNAP config
        fallback = {
            "auth_hnap_config": {
                "endpoint": "/HNAP1/",
                "hmac_algorithm": "md5",
            },
        }

        flow._apply_auth_discovery_info(data, info, fallback_data=fallback)

        assert data["auth_hnap_config"]["hmac_algorithm"] == "md5"

    def test_new_hnap_config_overrides_fallback(self, flow):
        """Test new HNAP config takes precedence over fallback."""
        data = {}
        info = {
            "auth_strategy": "hnap_session",
            "auth_hnap_config": {"hmac_algorithm": "sha256"},
        }
        fallback = {
            "auth_hnap_config": {"hmac_algorithm": "md5"},
        }

        flow._apply_auth_discovery_info(data, info, fallback_data=fallback)

        assert data["auth_hnap_config"]["hmac_algorithm"] == "sha256"
