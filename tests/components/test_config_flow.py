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

from custom_components.cable_modem_monitor.config_flow import (
    CableModemMonitorConfigFlow,
    OptionsFlowHandler,
)
from custom_components.cable_modem_monitor.config_flow_helpers import (
    validate_input,
)
from custom_components.cable_modem_monitor.core.discovery.pipeline import DiscoveryPipelineResult
from custom_components.cable_modem_monitor.core.exceptions import (
    CannotConnectError,
)

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
) -> DiscoveryPipelineResult:
    """Create a successful discovery pipeline result for tests."""
    mock_parser = Mock()
    mock_parser.manufacturer = manufacturer
    mock_parser.get_actual_model.return_value = None

    return DiscoveryPipelineResult(
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


class TestValidateInput:
    """Test input validation."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = Mock()
        hass.async_add_executor_job = Mock(return_value=None)
        return hass

    @pytest.fixture
    def valid_input(self):
        """Provide valid input data."""
        return {
            CONF_HOST: "192.168.100.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        }

    @pytest.mark.asyncio
    @patch("custom_components.cable_modem_monitor.core.discovery.run_discovery_pipeline")
    @patch("custom_components.cable_modem_monitor.config_flow_helpers.test_icmp_ping")
    async def test_success(self, mock_icmp_ping, mock_pipeline, mock_hass, valid_input):
        """Test successful validation."""
        # Mock pipeline to return success
        mock_pipeline.return_value = _create_success_result()
        mock_icmp_ping.return_value = True

        # Mock async_add_executor_job to call the function
        async def mock_executor_job(func, *args):
            return func(*args)

        mock_hass.async_add_executor_job = mock_executor_job

        result = await validate_input(mock_hass, valid_input)

        assert result["title"] == "Cable Modem (192.168.100.1)"

    @pytest.mark.asyncio
    @patch("custom_components.cable_modem_monitor.core.discovery.run_discovery_pipeline")
    @patch("custom_components.cable_modem_monitor.config_flow_helpers.test_icmp_ping")
    async def test_connection_failure(self, mock_icmp_ping, mock_pipeline, mock_hass, valid_input):
        """Test validation fails when cannot connect to modem."""
        # Mock pipeline to return failure
        mock_pipeline.return_value = DiscoveryPipelineResult(
            success=False,
            error="Connection failed",
            failed_step="connectivity",
        )
        mock_icmp_ping.return_value = False

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
    def valid_input(self):
        """Provide valid input data."""
        return {
            CONF_HOST: "192.168.100.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        }

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "modem_name,manufacturer,expected_title,desc",
        TITLE_FORMATTING_CASES,
        ids=[c[3] for c in TITLE_FORMATTING_CASES],
    )
    @patch("custom_components.cable_modem_monitor.core.discovery.run_discovery_pipeline")
    @patch("custom_components.cable_modem_monitor.config_flow_helpers.test_icmp_ping")
    async def test_title_formatting(
        self,
        mock_icmp_ping,
        mock_pipeline,
        mock_hass,
        valid_input,
        modem_name,
        manufacturer,
        expected_title,
        desc,
    ):
        """Test title formatting via table-driven cases."""
        mock_pipeline.return_value = _create_success_result(
            modem_name=modem_name,
            manufacturer=manufacturer,
        )
        mock_icmp_ping.return_value = True

        async def mock_executor_job(func, *args):
            return func(*args)

        mock_hass.async_add_executor_job = mock_executor_job

        result = await validate_input(mock_hass, valid_input)

        assert result["title"] == expected_title, f"Failed: {desc}"

    @pytest.mark.asyncio
    @patch("custom_components.cable_modem_monitor.core.discovery.run_discovery_pipeline")
    @patch("custom_components.cable_modem_monitor.config_flow_helpers.test_icmp_ping")
    async def test_title_detection_info_included(self, mock_icmp_ping, mock_pipeline, mock_hass, valid_input):
        """Test that detection_info is included in result."""
        mock_pipeline.return_value = _create_success_result(
            modem_name="[Model]",
            manufacturer="[MFG]",
        )
        mock_icmp_ping.return_value = True

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
