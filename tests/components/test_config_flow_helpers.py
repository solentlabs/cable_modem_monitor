"""Tests for config_flow_helpers.py."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from custom_components.cable_modem_monitor.config_flow_helpers import (
    build_parser_dropdown,
    classify_error,
    load_parser_hints,
    validate_input,
)
from custom_components.cable_modem_monitor.core.exceptions import (
    CannotConnectError,
    InvalidAuthError,
    UnsupportedModemError,
)

# =============================================================================
# CLASSIFY ERROR TEST CASES
# =============================================================================
# Tests classify_error() which maps exceptions to user-facing error codes.
# Used by config flow to display appropriate error messages in the UI.
#
# ┌─────────────────────┬─────────────────────────────┬───────────────────┐
# │ test_id             │ error_type                  │ expected_code     │
# ├─────────────────────┼─────────────────────────────┼───────────────────┤
# │ none_error          │ None                        │ cannot_connect    │
# │ cannot_connect_no   │ CannotConnectError()        │ cannot_connect    │
# │ cannot_connect_msg  │ CannotConnectError("...")   │ network_unreachable│
# │ invalid_auth        │ InvalidAuthError("...")     │ invalid_auth      │
# │ unsupported_modem   │ UnsupportedModemError("...") │ unsupported_modem │
# │ value_error         │ ValueError("...")           │ invalid_input     │
# │ type_error          │ TypeError("...")            │ invalid_input     │
# │ runtime_error       │ RuntimeError("...")         │ unknown           │
# │ generic_exception   │ Exception("...")            │ unknown           │
# └─────────────────────┴─────────────────────────────┴───────────────────┘
#
# fmt: off
CLASSIFY_ERROR_CASES: list[tuple[str, object, str]] = [
    # (test_id,               error,                                  expected)
    ("none_error",            None,                                   "cannot_connect"),
    ("cannot_connect_no_msg", CannotConnectError(),                   "cannot_connect"),
    ("cannot_connect_msg",    CannotConnectError("Host unreachable"), "network_unreachable"),
    ("invalid_auth",          InvalidAuthError("Bad credentials"),    "invalid_auth"),
    ("unsupported_modem",     UnsupportedModemError("No parser"),     "unsupported_modem"),
    ("value_error",           ValueError("Invalid host format"),      "invalid_input"),
    ("type_error",            TypeError("Expected string"),           "invalid_input"),
    ("runtime_error",         RuntimeError("Something went wrong"),   "unknown"),
    ("generic_exception",     Exception("Generic error"),             "unknown"),
]
# fmt: on


class TestClassifyError:
    """Tests for classify_error function."""

    @pytest.mark.parametrize(
        "test_id,error,expected",
        CLASSIFY_ERROR_CASES,
        ids=[c[0] for c in CLASSIFY_ERROR_CASES],
    )
    def test_classify_error(self, test_id: str, error: Exception | None, expected: str):
        """Test classify_error returns correct error code for each error type."""
        result = classify_error(error)
        assert result == expected, f"{test_id}: expected {expected}, got {result}"


class TestBuildParserDropdown:
    """Tests for build_parser_dropdown function."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        hass = Mock()
        return hass

    @pytest.mark.asyncio
    async def test_builds_dropdown_with_auto_first(self, mock_hass):
        """Test dropdown includes 'auto' as first option."""

        # Mock get_parser_dropdown_from_index to return parser names
        async def mock_executor(func, *args):
            return ["Test Parser"]

        mock_hass.async_add_executor_job = mock_executor

        choices = await build_parser_dropdown(mock_hass)

        assert choices[0] == "auto"
        assert "Test Parser" in choices

    @pytest.mark.asyncio
    async def test_empty_parsers_returns_auto_only(self, mock_hass):
        """Test empty parser list returns just 'auto'."""

        async def mock_executor(func, *args):
            return []

        mock_hass.async_add_executor_job = mock_executor

        choices = await build_parser_dropdown(mock_hass)

        assert choices == ["auto"]


class TestLoadParserHints:
    """Tests for load_parser_hints function."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        hass = Mock()
        return hass

    @pytest.mark.asyncio
    async def test_none_parser_returns_none(self, mock_hass):
        """Test None parser returns None hints."""
        result = await load_parser_hints(mock_hass, None)
        assert result is None

    @pytest.mark.asyncio
    async def test_loads_hints_from_modem_yaml(self, mock_hass):
        """Test hints are loaded from modem.yaml adapter."""
        mock_parser = Mock()
        mock_parser.__name__ = "TestParser"
        mock_parser.name = "Test Parser"

        mock_adapter = Mock()
        mock_adapter.get_auth_form_hints.return_value = {
            "password_encoding": "base64",
            "success_redirect": "/status.html",
        }

        async def mock_executor(func, *args):
            return mock_adapter

        mock_hass.async_add_executor_job = mock_executor

        result = await load_parser_hints(mock_hass, mock_parser)

        assert result == {"password_encoding": "base64", "success_redirect": "/status.html"}

    @pytest.mark.asyncio
    async def test_falls_back_to_parser_class_hints(self, mock_hass):
        """Test falls back to parser class auth_form_hints."""
        mock_parser = Mock()
        mock_parser.__name__ = "TestParser"
        mock_parser.name = "Test Parser"
        mock_parser.auth_form_hints = {"username_field": "user", "password_field": "pass"}

        async def mock_executor(func, *args):
            return None  # No adapter found

        mock_hass.async_add_executor_job = mock_executor

        result = await load_parser_hints(mock_hass, mock_parser)

        assert result == {"username_field": "user", "password_field": "pass"}

    @pytest.mark.asyncio
    async def test_returns_none_when_no_hints_available(self, mock_hass):
        """Test returns None when neither adapter nor parser have hints."""
        mock_parser = Mock(spec=["__name__", "name"])  # No auth_form_hints attribute
        mock_parser.__name__ = "TestParser"
        mock_parser.name = "Test Parser"

        async def mock_executor(func, *args):
            return None

        mock_hass.async_add_executor_job = mock_executor

        result = await load_parser_hints(mock_hass, mock_parser)

        assert result is None

    @pytest.mark.asyncio
    async def test_handles_adapter_exception(self, mock_hass):
        """Test handles exception when loading adapter."""
        mock_parser = Mock()
        mock_parser.__name__ = "TestParser"
        mock_parser.name = "Test Parser"
        mock_parser.auth_form_hints = {"fallback": "hints"}

        async def mock_executor(func, *args):
            raise ImportError("modem_config not found")

        mock_hass.async_add_executor_job = mock_executor

        result = await load_parser_hints(mock_hass, mock_parser)

        # Should fall back to parser hints
        assert result == {"fallback": "hints"}


class TestValidateInput:
    """Tests for validate_input function."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        hass = Mock()
        return hass

    @pytest.fixture
    def mock_pipeline_result(self):
        """Create a successful pipeline result."""
        from custom_components.cable_modem_monitor.core.discovery.pipeline import (
            DiscoveryPipelineResult,
        )

        mock_parser = Mock()
        mock_parser.manufacturer = "Arris"
        mock_parser.get_actual_model.return_value = "SB8200-v2"

        return DiscoveryPipelineResult(
            success=True,
            working_url="http://192.168.100.1",
            auth_strategy="no_auth",
            auth_form_config=None,
            parser_name="Arris SB8200",
            legacy_ssl=False,
            modem_data={"downstream": [], "upstream": []},
            parser_instance=mock_parser,
            session=None,
            error=None,
            failed_step=None,
        )

    @pytest.mark.asyncio
    async def test_successful_validation(self, mock_hass, mock_pipeline_result):
        """Test successful validation returns expected data."""
        mock_parser_class = Mock()
        mock_parser_class.name = "Arris SB8200"

        async def mock_executor(func, *args):
            if func.__name__ == "get_parsers":
                return [mock_parser_class]
            elif func.__name__ == "run_discovery_pipeline":
                return mock_pipeline_result
            return None

        mock_hass.async_add_executor_job = mock_executor

        with patch(
            "custom_components.cable_modem_monitor.config_flow_helpers.test_icmp_ping",
            return_value=True,
        ):
            result = await validate_input(
                mock_hass,
                {"host": "192.168.100.1", "username": "", "password": ""},
            )

        assert result["title"] == "Arris SB8200 (192.168.100.1)"
        assert result["supports_icmp"] is True
        assert result["working_url"] == "http://192.168.100.1"
        assert result["auth_strategy"] == "no_auth"
        assert result["detection_info"]["modem_name"] == "Arris SB8200"
        assert result["detection_info"]["manufacturer"] == "Arris"
        assert result["detection_info"]["actual_model"] == "SB8200-v2"

    @pytest.mark.asyncio
    async def test_connectivity_failure_raises_cannot_connect(self, mock_hass):
        """Test connectivity failure raises CannotConnectError."""
        from custom_components.cable_modem_monitor.core.discovery.pipeline import (
            DiscoveryPipelineResult,
        )

        failed_result = DiscoveryPipelineResult(
            success=False,
            error="Connection refused",
            failed_step="connectivity",
        )

        async def mock_executor(func, *args):
            if func.__name__ == "get_parsers":
                return []
            return failed_result

        mock_hass.async_add_executor_job = mock_executor

        with pytest.raises(CannotConnectError, match="Connection refused"):
            await validate_input(
                mock_hass,
                {"host": "192.168.100.1", "username": "", "password": ""},
            )

    @pytest.mark.asyncio
    async def test_auth_failure_raises_invalid_auth(self, mock_hass):
        """Test auth failure raises InvalidAuthError."""
        from custom_components.cable_modem_monitor.core.discovery.pipeline import (
            DiscoveryPipelineResult,
        )

        failed_result = DiscoveryPipelineResult(
            success=False,
            error="Bad credentials",
            failed_step="auth",
        )

        async def mock_executor(func, *args):
            if func.__name__ == "get_parsers":
                return []
            return failed_result

        mock_hass.async_add_executor_job = mock_executor

        with pytest.raises(InvalidAuthError, match="Bad credentials"):
            await validate_input(
                mock_hass,
                {"host": "192.168.100.1", "username": "admin", "password": "wrong"},
            )

    @pytest.mark.asyncio
    async def test_parser_detection_failure_raises_unsupported(self, mock_hass):
        """Test parser detection failure raises UnsupportedModemError."""
        from custom_components.cable_modem_monitor.core.discovery.pipeline import (
            DiscoveryPipelineResult,
        )

        failed_result = DiscoveryPipelineResult(
            success=False,
            error="No parser matched",
            failed_step="parser_detection",
        )

        async def mock_executor(func, *args):
            if func.__name__ == "get_parsers":
                return []
            return failed_result

        mock_hass.async_add_executor_job = mock_executor

        with pytest.raises(UnsupportedModemError, match="No parser matched"):
            await validate_input(
                mock_hass,
                {"host": "192.168.100.1", "username": "", "password": ""},
            )

    @pytest.mark.asyncio
    async def test_generic_failure_raises_cannot_connect(self, mock_hass):
        """Test generic failure raises CannotConnectError."""
        from custom_components.cable_modem_monitor.core.discovery.pipeline import (
            DiscoveryPipelineResult,
        )

        failed_result = DiscoveryPipelineResult(
            success=False,
            error="Unknown error",
            failed_step="validation",
        )

        async def mock_executor(func, *args):
            if func.__name__ == "get_parsers":
                return []
            return failed_result

        mock_hass.async_add_executor_job = mock_executor

        with pytest.raises(CannotConnectError, match="Unknown error"):
            await validate_input(
                mock_hass,
                {"host": "192.168.100.1", "username": "", "password": ""},
            )

    @pytest.mark.asyncio
    async def test_validation_with_user_selected_parser(self, mock_hass, mock_pipeline_result):
        """Test validation with user-selected parser."""
        mock_parser_class = Mock()
        mock_parser_class.name = "Arris SB8200"
        mock_parser_class.__name__ = "ArrisSB8200Parser"

        async def mock_executor(func, *args):
            if func.__name__ == "get_parsers":
                return [mock_parser_class]
            elif func.__name__ == "get_auth_adapter_for_parser":
                return None  # No adapter, will fall back to parser hints
            elif func.__name__ == "run_discovery_pipeline":
                return mock_pipeline_result
            return None

        mock_hass.async_add_executor_job = mock_executor

        with patch(
            "custom_components.cable_modem_monitor.config_flow_helpers.test_icmp_ping",
            return_value=False,
        ):
            result = await validate_input(
                mock_hass,
                {
                    "host": "192.168.100.1",
                    "username": "",
                    "password": "",
                    "modem_choice": "Arris SB8200",
                },
            )

        assert result["supports_icmp"] is False

    @pytest.mark.asyncio
    async def test_validation_without_actual_model(self, mock_hass):
        """Test validation when parser doesn't return actual model."""
        from custom_components.cable_modem_monitor.core.discovery.pipeline import (
            DiscoveryPipelineResult,
        )

        mock_parser = Mock()
        mock_parser.manufacturer = "Netgear"
        mock_parser.get_actual_model.return_value = None

        result = DiscoveryPipelineResult(
            success=True,
            working_url="http://192.168.100.1",
            auth_strategy="basic",
            auth_form_config=None,
            parser_name="Netgear CM600",
            legacy_ssl=False,
            modem_data={},
            parser_instance=mock_parser,
            session=None,
        )

        async def mock_executor(func, *args):
            if func.__name__ == "get_parsers":
                return []
            return result

        mock_hass.async_add_executor_job = mock_executor

        with patch(
            "custom_components.cable_modem_monitor.config_flow_helpers.test_icmp_ping",
            return_value=True,
        ):
            validation_result = await validate_input(
                mock_hass,
                {"host": "192.168.100.1", "username": "admin", "password": "pass"},
            )

        assert "actual_model" not in validation_result["detection_info"]
        assert validation_result["detection_info"]["modem_name"] == "Netgear CM600"

    @pytest.mark.asyncio
    async def test_validation_stores_auth_discovery_status(self, mock_hass, mock_pipeline_result):
        """Test validation stores auth discovery status in result."""

        async def mock_executor(func, *args):
            if func.__name__ == "get_parsers":
                return []
            return mock_pipeline_result

        mock_hass.async_add_executor_job = mock_executor

        with patch(
            "custom_components.cable_modem_monitor.config_flow_helpers.test_icmp_ping",
            return_value=True,
        ):
            result = await validate_input(
                mock_hass,
                {"host": "192.168.100.1", "username": "", "password": ""},
            )

        assert result["auth_discovery_status"] == "success"
        assert result["auth_discovery_failed"] is False
        assert result["auth_discovery_error"] is None

    @pytest.mark.asyncio
    async def test_validation_with_none_parser_instance(self, mock_hass):
        """Test validation handles None parser_instance gracefully."""
        from custom_components.cable_modem_monitor.core.discovery.pipeline import (
            DiscoveryPipelineResult,
        )

        # Result with no parser_instance (edge case)
        result = DiscoveryPipelineResult(
            success=True,
            working_url="http://192.168.100.1",
            auth_strategy="no_auth",
            auth_form_config=None,
            parser_name="Unknown Modem",
            legacy_ssl=False,
            modem_data={},
            parser_instance=None,  # No parser instance
            session=None,
        )

        async def mock_executor(func, *args):
            if func.__name__ == "get_parsers":
                return []
            elif func.__name__ == "run_discovery_pipeline":
                return result
            return None

        mock_hass.async_add_executor_job = mock_executor

        with patch(
            "custom_components.cable_modem_monitor.config_flow_helpers.test_icmp_ping",
            return_value=True,
        ):
            validation_result = await validate_input(
                mock_hass,
                {"host": "192.168.100.1", "username": "", "password": ""},
            )

        # manufacturer should be None when parser_instance is None
        assert validation_result["detection_info"]["manufacturer"] is None
        assert "actual_model" not in validation_result["detection_info"]
        assert validation_result["detection_info"]["modem_name"] == "Unknown Modem"

    @pytest.mark.asyncio
    async def test_connectivity_failure_uses_default_message(self, mock_hass):
        """Test connectivity failure uses default message when error is None."""
        from custom_components.cable_modem_monitor.core.discovery.pipeline import (
            DiscoveryPipelineResult,
        )

        failed_result = DiscoveryPipelineResult(
            success=False,
            error=None,  # No specific error message
            failed_step="connectivity",
        )

        async def mock_executor(func, *args):
            if func.__name__ == "get_parsers":
                return []
            elif func.__name__ == "run_discovery_pipeline":
                return failed_result
            return None

        mock_hass.async_add_executor_job = mock_executor

        with pytest.raises(CannotConnectError, match="Cannot connect to modem"):
            await validate_input(
                mock_hass,
                {"host": "192.168.100.1", "username": "", "password": ""},
            )

    @pytest.mark.asyncio
    async def test_auth_failure_uses_default_message(self, mock_hass):
        """Test auth failure uses default message when error is None."""
        from custom_components.cable_modem_monitor.core.discovery.pipeline import (
            DiscoveryPipelineResult,
        )

        failed_result = DiscoveryPipelineResult(
            success=False,
            error=None,  # No specific error message
            failed_step="auth",
        )

        async def mock_executor(func, *args):
            if func.__name__ == "get_parsers":
                return []
            elif func.__name__ == "run_discovery_pipeline":
                return failed_result
            return None

        mock_hass.async_add_executor_job = mock_executor

        with pytest.raises(InvalidAuthError, match="Authentication failed"):
            await validate_input(
                mock_hass,
                {"host": "192.168.100.1", "username": "admin", "password": "pass"},
            )

    @pytest.mark.asyncio
    async def test_parser_detection_failure_uses_default_message(self, mock_hass):
        """Test parser detection failure uses default message when error is None."""
        from custom_components.cable_modem_monitor.core.discovery.pipeline import (
            DiscoveryPipelineResult,
        )

        failed_result = DiscoveryPipelineResult(
            success=False,
            error=None,  # No specific error message
            failed_step="parser_detection",
        )

        async def mock_executor(func, *args):
            if func.__name__ == "get_parsers":
                return []
            elif func.__name__ == "run_discovery_pipeline":
                return failed_result
            return None

        mock_hass.async_add_executor_job = mock_executor

        with pytest.raises(UnsupportedModemError, match="Could not detect modem type"):
            await validate_input(
                mock_hass,
                {"host": "192.168.100.1", "username": "", "password": ""},
            )

    @pytest.mark.asyncio
    async def test_generic_failure_uses_default_message(self, mock_hass):
        """Test generic failure uses default message when error is None."""
        from custom_components.cable_modem_monitor.core.discovery.pipeline import (
            DiscoveryPipelineResult,
        )

        failed_result = DiscoveryPipelineResult(
            success=False,
            error=None,  # No specific error message
            failed_step="validation",
        )

        async def mock_executor(func, *args):
            if func.__name__ == "get_parsers":
                return []
            elif func.__name__ == "run_discovery_pipeline":
                return failed_result
            return None

        mock_hass.async_add_executor_job = mock_executor

        with pytest.raises(CannotConnectError, match="Discovery failed"):
            await validate_input(
                mock_hass,
                {"host": "192.168.100.1", "username": "", "password": ""},
            )

    @pytest.mark.asyncio
    async def test_validation_stores_hnap_config(self, mock_hass):
        """Test validation stores auth_hnap_config from pipeline result."""
        from custom_components.cable_modem_monitor.core.discovery.pipeline import (
            DiscoveryPipelineResult,
        )

        mock_parser = Mock()
        mock_parser.manufacturer = "Arris"
        mock_parser.get_actual_model.return_value = None

        hnap_config = {
            "endpoint": "/HNAP1/",
            "namespace": "http://purenetworks.com/HNAP1/",
        }

        result = DiscoveryPipelineResult(
            success=True,
            working_url="http://192.168.100.1",
            auth_strategy="hnap_session",
            auth_form_config=None,
            auth_hnap_config=hnap_config,
            parser_name="Arris SB8200",
            legacy_ssl=False,
            modem_data={},
            parser_instance=mock_parser,
            session=None,
        )

        async def mock_executor(func, *args):
            if func.__name__ == "get_parsers":
                return []
            return result

        mock_hass.async_add_executor_job = mock_executor

        with patch(
            "custom_components.cable_modem_monitor.config_flow_helpers.test_icmp_ping",
            return_value=True,
        ):
            validation_result = await validate_input(
                mock_hass,
                {"host": "192.168.100.1", "username": "admin", "password": "pass"},
            )

        assert validation_result["auth_hnap_config"] == hnap_config
        assert validation_result["auth_strategy"] == "hnap_session"

    @pytest.mark.asyncio
    async def test_validation_stores_url_token_config(self, mock_hass):
        """Test validation stores auth_url_token_config from pipeline result."""
        from custom_components.cable_modem_monitor.core.discovery.pipeline import (
            DiscoveryPipelineResult,
        )

        mock_parser = Mock()
        mock_parser.manufacturer = "Motorola"
        mock_parser.get_actual_model.return_value = None

        url_token_config = {
            "login_prefix": "login",
            "data_page": "MotoStatusSoftware.asp",
            "token_pattern": r"currentSessionId\s*=\s*['\"]([^'\"]+)['\"]",
        }

        result = DiscoveryPipelineResult(
            success=True,
            working_url="http://192.168.100.1",
            auth_strategy="url_token_session",
            auth_form_config=None,
            auth_url_token_config=url_token_config,
            parser_name="Motorola MB8611",
            legacy_ssl=False,
            modem_data={},
            parser_instance=mock_parser,
            session=None,
        )

        async def mock_executor(func, *args):
            if func.__name__ == "get_parsers":
                return []
            return result

        mock_hass.async_add_executor_job = mock_executor

        with patch(
            "custom_components.cable_modem_monitor.config_flow_helpers.test_icmp_ping",
            return_value=True,
        ):
            validation_result = await validate_input(
                mock_hass,
                {"host": "192.168.100.1", "username": "admin", "password": "pass"},
            )

        assert validation_result["auth_url_token_config"] == url_token_config
        assert validation_result["auth_strategy"] == "url_token_session"
