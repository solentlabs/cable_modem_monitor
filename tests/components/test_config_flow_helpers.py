"""Tests for config_flow_helpers.py."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from custom_components.cable_modem_monitor.config_flow_helpers import (
    _build_static_config_for_auth_type,
    build_parser_dropdown,
    classify_error,
    get_auth_type_dropdown,
    get_auth_types_for_parser,
    load_parser_hints,
    needs_auth_type_selection,
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
    async def test_builds_dropdown_without_auto(self, mock_hass):
        """Test dropdown does not include 'auto' option (user must select modem)."""

        # Mock get_parser_dropdown_from_index to return parser names
        async def mock_executor(func, *args):
            return ["Test Parser", "Another Parser"]

        mock_hass.async_add_executor_job = mock_executor

        choices = await build_parser_dropdown(mock_hass)

        assert "auto" not in choices
        assert "Test Parser" in choices
        assert "Another Parser" in choices

    @pytest.mark.asyncio
    async def test_empty_parsers_returns_empty_list(self, mock_hass):
        """Test empty parser list returns empty list (no 'auto')."""

        async def mock_executor(func, *args):
            return []

        mock_hass.async_add_executor_job = mock_executor

        choices = await build_parser_dropdown(mock_hass)

        assert choices == []


# =============================================================================
# AUTH TYPE HELPERS TEST CASES
# =============================================================================
# Tests for auth type selection functions used when modems have multiple
# auth variants (e.g., SB8200 with none vs url_token, SB6190 with none vs form).
#
# ┌─────────────────────────┬────────────────────┬─────────────────────────────┐
# │ function                │ scenario           │ expected                    │
# ├─────────────────────────┼────────────────────┼─────────────────────────────┤
# │ get_auth_types_for_...  │ no parser          │ ["none"]                    │
# │ get_auth_types_for_...  │ no adapter         │ ["none"]                    │
# │ get_auth_types_for_...  │ single auth type   │ ["form"]                    │
# │ get_auth_types_for_...  │ multiple types     │ ["none", "url_token"]       │
# │ needs_auth_type_...     │ single type        │ False                       │
# │ needs_auth_type_...     │ multiple types     │ True                        │
# │ get_auth_type_dropdown  │ multiple types     │ {"none": "...", "form": ...}│
# │ _build_static_config... │ form type          │ {auth_strategy: form_plain} │
# │ _build_static_config... │ url_token type     │ {auth_strategy: url_token}  │
# └─────────────────────────┴────────────────────┴─────────────────────────────┘


class TestGetAuthTypesForParser:
    """Tests for get_auth_types_for_parser function."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        return Mock()

    @pytest.mark.asyncio
    async def test_no_parser_returns_none_list(self, mock_hass):
        """Test None parser returns ["none"]."""
        result = await get_auth_types_for_parser(mock_hass, None)
        assert result == ["none"]

    @pytest.mark.asyncio
    async def test_no_adapter_returns_none_list(self, mock_hass):
        """Test parser without adapter returns ["none"]."""
        mock_parser = Mock()
        mock_parser.__name__ = "TestParser"

        async def mock_executor(func, *args):
            return None  # No adapter found

        mock_hass.async_add_executor_job = mock_executor

        result = await get_auth_types_for_parser(mock_hass, mock_parser)
        assert result == ["none"]

    @pytest.mark.asyncio
    async def test_single_auth_type(self, mock_hass):
        """Test parser with single auth type."""
        mock_parser = Mock()
        mock_parser.__name__ = "TestParser"

        mock_adapter = Mock()
        mock_adapter.get_available_auth_types.return_value = ["form"]

        async def mock_executor(func, *args):
            return mock_adapter

        mock_hass.async_add_executor_job = mock_executor

        result = await get_auth_types_for_parser(mock_hass, mock_parser)
        assert result == ["form"]

    @pytest.mark.asyncio
    async def test_multiple_auth_types(self, mock_hass):
        """Test parser with multiple auth types (e.g., SB8200)."""
        mock_parser = Mock()
        mock_parser.__name__ = "ArrisSB8200Parser"

        mock_adapter = Mock()
        mock_adapter.get_available_auth_types.return_value = ["none", "url_token"]

        async def mock_executor(func, *args):
            return mock_adapter

        mock_hass.async_add_executor_job = mock_executor

        result = await get_auth_types_for_parser(mock_hass, mock_parser)
        assert result == ["none", "url_token"]

    @pytest.mark.asyncio
    async def test_empty_auth_types_returns_none_list(self, mock_hass):
        """Test adapter returning empty list falls back to ["none"]."""
        mock_parser = Mock()
        mock_parser.__name__ = "TestParser"

        mock_adapter = Mock()
        mock_adapter.get_available_auth_types.return_value = []

        async def mock_executor(func, *args):
            return mock_adapter

        mock_hass.async_add_executor_job = mock_executor

        result = await get_auth_types_for_parser(mock_hass, mock_parser)
        assert result == ["none"]


class TestNeedsAuthTypeSelection:
    """Tests for needs_auth_type_selection function."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        return Mock()

    @pytest.mark.asyncio
    async def test_single_type_no_selection_needed(self, mock_hass):
        """Test single auth type does not need selection."""
        mock_parser = Mock()
        mock_parser.__name__ = "MotorplaMB7621Parser"

        mock_adapter = Mock()
        mock_adapter.get_available_auth_types.return_value = ["form"]

        async def mock_executor(func, *args):
            return mock_adapter

        mock_hass.async_add_executor_job = mock_executor

        result = await needs_auth_type_selection(mock_hass, mock_parser)
        assert result is False

    @pytest.mark.asyncio
    async def test_multiple_types_needs_selection(self, mock_hass):
        """Test multiple auth types requires selection."""
        mock_parser = Mock()
        mock_parser.__name__ = "ArrisSB8200Parser"

        mock_adapter = Mock()
        mock_adapter.get_available_auth_types.return_value = ["none", "url_token"]

        async def mock_executor(func, *args):
            return mock_adapter

        mock_hass.async_add_executor_job = mock_executor

        result = await needs_auth_type_selection(mock_hass, mock_parser)
        assert result is True

    @pytest.mark.asyncio
    async def test_no_parser_no_selection_needed(self, mock_hass):
        """Test None parser does not need selection."""
        result = await needs_auth_type_selection(mock_hass, None)
        assert result is False


class TestGetAuthTypeDropdown:
    """Tests for get_auth_type_dropdown function."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        return Mock()

    @pytest.mark.asyncio
    async def test_builds_dropdown_with_labels(self, mock_hass):
        """Test dropdown includes human-readable labels."""
        mock_parser = Mock()
        mock_parser.__name__ = "ArrisSB8200Parser"

        mock_adapter = Mock()
        mock_adapter.get_available_auth_types.return_value = ["none", "url_token"]

        async def mock_executor(func, *args):
            return mock_adapter

        mock_hass.async_add_executor_job = mock_executor

        result = await get_auth_type_dropdown(mock_hass, mock_parser)

        assert "none" in result
        assert "url_token" in result
        # Labels should be human-readable strings
        assert isinstance(result["none"], str)
        assert isinstance(result["url_token"], str)

    @pytest.mark.asyncio
    async def test_no_parser_returns_none_dropdown(self, mock_hass):
        """Test None parser returns dropdown with just 'none'."""
        result = await get_auth_type_dropdown(mock_hass, None)
        assert "none" in result
        assert len(result) == 1


class TestBuildStaticConfigForAuthType:
    """Tests for _build_static_config_for_auth_type function."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        return Mock()

    @pytest.mark.asyncio
    async def test_no_parser_returns_none(self, mock_hass):
        """Test None parser returns None."""
        result = await _build_static_config_for_auth_type(mock_hass, None, "form")
        assert result is None

    @pytest.mark.asyncio
    async def test_no_adapter_returns_none(self, mock_hass):
        """Test parser without adapter returns None."""
        mock_parser = Mock()
        mock_parser.__name__ = "TestParser"

        async def mock_executor(func, *args):
            return None

        mock_hass.async_add_executor_job = mock_executor

        result = await _build_static_config_for_auth_type(mock_hass, mock_parser, "form")
        assert result is None

    @pytest.mark.asyncio
    async def test_form_auth_type_builds_config(self, mock_hass):
        """Test form auth type builds correct config structure."""
        mock_parser = Mock()
        mock_parser.__name__ = "ArrisSB6190Parser"
        mock_parser.name = "ARRIS SB6190"

        mock_adapter = Mock()
        mock_adapter.get_auth_config_for_type.return_value = {
            "action": "/cgi-bin/login",
            "method": "POST",
        }

        async def mock_executor(func, *args):
            return mock_adapter

        mock_hass.async_add_executor_job = mock_executor

        result = await _build_static_config_for_auth_type(mock_hass, mock_parser, "form")

        assert result is not None
        assert result["auth_strategy"] == "form_plain"
        assert result["auth_form_config"] == {"action": "/cgi-bin/login", "method": "POST"}
        assert result["auth_hnap_config"] is None
        assert result["auth_url_token_config"] is None

    @pytest.mark.asyncio
    async def test_url_token_auth_type_builds_config(self, mock_hass):
        """Test url_token auth type builds correct config structure."""
        mock_parser = Mock()
        mock_parser.__name__ = "ArrisSB8200Parser"
        mock_parser.name = "ARRIS SB8200"

        mock_adapter = Mock()
        mock_adapter.get_auth_config_for_type.return_value = {
            "login_page": "/cmconnectionstatus.html",
            "token_prefix": "ct_",
        }

        async def mock_executor(func, *args):
            return mock_adapter

        mock_hass.async_add_executor_job = mock_executor

        result = await _build_static_config_for_auth_type(mock_hass, mock_parser, "url_token")

        assert result is not None
        assert result["auth_strategy"] == "url_token_session"
        assert result["auth_url_token_config"] == {
            "login_page": "/cmconnectionstatus.html",
            "token_prefix": "ct_",
        }
        assert result["auth_form_config"] is None
        assert result["auth_hnap_config"] is None

    @pytest.mark.asyncio
    async def test_none_auth_type_builds_config(self, mock_hass):
        """Test none auth type builds correct config structure."""
        mock_parser = Mock()
        mock_parser.__name__ = "ArrisSB6190Parser"
        mock_parser.name = "ARRIS SB6190"

        mock_adapter = Mock()
        mock_adapter.get_auth_config_for_type.return_value = {}

        async def mock_executor(func, *args):
            return mock_adapter

        mock_hass.async_add_executor_job = mock_executor

        result = await _build_static_config_for_auth_type(mock_hass, mock_parser, "none")

        assert result is not None
        assert result["auth_strategy"] == "no_auth"
        assert result["auth_form_config"] is None
        assert result["auth_hnap_config"] is None
        assert result["auth_url_token_config"] is None

    @pytest.mark.asyncio
    async def test_hnap_auth_type_builds_config(self, mock_hass):
        """Test hnap auth type builds correct config structure."""
        mock_parser = Mock()
        mock_parser.__name__ = "MotorolaMB8611Parser"
        mock_parser.name = "Motorola MB8611"

        mock_adapter = Mock()
        mock_adapter.get_auth_config_for_type.return_value = {
            "endpoint": "/HNAP1/",
            "namespace": "http://purenetworks.com/HNAP1/",
        }

        async def mock_executor(func, *args):
            return mock_adapter

        mock_hass.async_add_executor_job = mock_executor

        result = await _build_static_config_for_auth_type(mock_hass, mock_parser, "hnap")

        assert result is not None
        assert result["auth_strategy"] == "hnap_session"
        assert result["auth_hnap_config"] == {
            "endpoint": "/HNAP1/",
            "namespace": "http://purenetworks.com/HNAP1/",
        }
        assert result["auth_form_config"] is None
        assert result["auth_url_token_config"] is None

    @pytest.mark.asyncio
    async def test_form_ajax_auth_type_builds_config(self, mock_hass):
        """Test form_ajax auth type builds correct config structure.

        Regression test for issue #93 and #83: SB6190 with firmware 9.1.103+
        requires AJAX-based login. The config must include auth_form_ajax_config
        for AuthWorkflow.authenticate_with_static_config() to work.
        """
        mock_parser = Mock()
        mock_parser.__name__ = "ArrisSB6190Parser"
        mock_parser.name = "ARRIS SB6190"

        mock_adapter = Mock()
        mock_adapter.get_auth_config_for_type.return_value = {
            "endpoint": "/cgi-bin/adv_pwd_cgi",
            "nonce_field": "ar_nonce",
            "nonce_length": 8,
            "arguments_field": "arguments",
            "credential_format": "username={username}:password={password}",
            "success_prefix": "Url:",
            "error_prefix": "Error:",
        }

        async def mock_executor(func, *args):
            return mock_adapter

        mock_hass.async_add_executor_job = mock_executor

        result = await _build_static_config_for_auth_type(mock_hass, mock_parser, "form_ajax")

        assert result is not None
        assert result["auth_strategy"] == "form_ajax"
        # This is the key assertion - auth_form_ajax_config must be populated
        assert result["auth_form_ajax_config"] == {
            "endpoint": "/cgi-bin/adv_pwd_cgi",
            "nonce_field": "ar_nonce",
            "nonce_length": 8,
            "arguments_field": "arguments",
            "credential_format": "username={username}:password={password}",
            "success_prefix": "Url:",
            "error_prefix": "Error:",
        }
        assert result["auth_form_config"] is None
        assert result["auth_hnap_config"] is None
        assert result["auth_url_token_config"] is None


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
    def mock_parser_class(self):
        """Create a mock parser class."""
        parser_class = Mock()
        parser_class.name = "Arris SB8200"
        parser_class.__name__ = "ArrisSB8200Parser"
        return parser_class

    @pytest.fixture
    def mock_adapter(self):
        """Create a mock modem adapter that returns static auth config."""
        adapter = Mock()
        adapter.get_static_auth_config.return_value = {
            "auth_strategy": "no_auth",
            "auth_form_config": None,
            "auth_hnap_config": None,
            "auth_url_token_config": None,
        }
        return adapter

    @pytest.fixture
    def mock_setup_result(self):
        """Create a successful setup result."""
        from custom_components.cable_modem_monitor.core.setup import SetupResult

        mock_parser = Mock()
        mock_parser.manufacturer = "Arris"
        mock_parser.get_actual_model.return_value = "SB8200-v2"

        return SetupResult(
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
    async def test_missing_modem_choice_raises_value_error(self, mock_hass):
        """Test validation fails when modem_choice is missing."""
        with pytest.raises(ValueError, match="Modem selection is required"):
            await validate_input(
                mock_hass,
                {"host": "192.168.100.1", "username": "", "password": ""},
            )

    @pytest.mark.asyncio
    async def test_nonexistent_parser_raises_unsupported(self, mock_hass):
        """Test validation fails when selected parser doesn't exist."""

        async def mock_executor(func, *args):
            if func.__name__ == "get_parser_by_name":
                return None  # Parser not found
            return None

        mock_hass.async_add_executor_job = mock_executor

        with pytest.raises(UnsupportedModemError, match="Parser 'NonExistent Parser' not found"):
            await validate_input(
                mock_hass,
                {
                    "host": "192.168.100.1",
                    "username": "",
                    "password": "",
                    "modem_choice": "NonExistent Parser",
                },
            )

    @pytest.mark.asyncio
    async def test_successful_validation(self, mock_hass, mock_parser_class, mock_adapter, mock_setup_result):
        """Test successful validation returns expected data."""

        async def mock_executor(func, *args):
            func_name = getattr(func, "__name__", None)
            if func_name == "get_parser_by_name":
                return mock_parser_class
            elif func_name == "get_auth_adapter_for_parser":
                return mock_adapter
            elif func_name == "setup_modem":
                return mock_setup_result
            # Handle bound methods from mock adapter (e.g., adapter.get_static_auth_config)
            elif callable(func):
                return func()
            return None

        mock_hass.async_add_executor_job = mock_executor

        with patch(
            "custom_components.cable_modem_monitor.config_flow_helpers.test_icmp_ping",
            return_value=True,
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

        assert result["title"] == "Arris SB8200 (192.168.100.1)"
        assert result["supports_icmp"] is True
        assert result["working_url"] == "http://192.168.100.1"
        assert result["auth_strategy"] == "no_auth"
        assert result["detection_info"]["modem_name"] == "Arris SB8200"
        assert result["detection_info"]["manufacturer"] == "Arris"
        assert result["detection_info"]["actual_model"] == "SB8200-v2"

    @pytest.mark.asyncio
    async def test_connectivity_failure_raises_cannot_connect(self, mock_hass, mock_parser_class, mock_adapter):
        """Test connectivity failure raises CannotConnectError."""
        from custom_components.cable_modem_monitor.core.setup import SetupResult

        failed_result = SetupResult(
            success=False,
            error="Connection refused",
            failed_step="connectivity",
        )

        async def mock_executor(func, *args):
            func_name = getattr(func, "__name__", None)
            if func_name == "get_parser_by_name":
                return mock_parser_class
            elif func_name == "get_auth_adapter_for_parser":
                return mock_adapter
            elif func_name == "setup_modem":
                return failed_result
            elif callable(func):
                return func()
            return None

        mock_hass.async_add_executor_job = mock_executor

        with pytest.raises(CannotConnectError, match="Connection refused"):
            await validate_input(
                mock_hass,
                {
                    "host": "192.168.100.1",
                    "username": "",
                    "password": "",
                    "modem_choice": "Arris SB8200",
                },
            )

    @pytest.mark.asyncio
    async def test_auth_failure_raises_invalid_auth(self, mock_hass, mock_parser_class, mock_adapter):
        """Test auth failure raises InvalidAuthError."""
        from custom_components.cable_modem_monitor.core.setup import SetupResult

        failed_result = SetupResult(
            success=False,
            error="Bad credentials",
            failed_step="auth",
        )

        async def mock_executor(func, *args):
            func_name = getattr(func, "__name__", None)
            if func_name == "get_parser_by_name":
                return mock_parser_class
            elif func_name == "get_auth_adapter_for_parser":
                return mock_adapter
            elif func_name == "setup_modem":
                return failed_result
            elif callable(func):
                return func()
            return None

        mock_hass.async_add_executor_job = mock_executor

        with pytest.raises(InvalidAuthError, match="Bad credentials"):
            await validate_input(
                mock_hass,
                {
                    "host": "192.168.100.1",
                    "username": "admin",
                    "password": "wrong",
                    "modem_choice": "Arris SB8200",
                },
            )

    @pytest.mark.asyncio
    async def test_parser_detection_failure_raises_unsupported(self, mock_hass, mock_parser_class, mock_adapter):
        """Test parser detection failure raises UnsupportedModemError."""
        from custom_components.cable_modem_monitor.core.setup import SetupResult

        failed_result = SetupResult(
            success=False,
            error="No parser matched",
            failed_step="parser_detection",
        )

        async def mock_executor(func, *args):
            func_name = getattr(func, "__name__", None)
            if func_name == "get_parser_by_name":
                return mock_parser_class
            elif func_name == "get_auth_adapter_for_parser":
                return mock_adapter
            elif func_name == "setup_modem":
                return failed_result
            elif callable(func):
                return func()
            return None

        mock_hass.async_add_executor_job = mock_executor

        with pytest.raises(UnsupportedModemError, match="No parser matched"):
            await validate_input(
                mock_hass,
                {
                    "host": "192.168.100.1",
                    "username": "",
                    "password": "",
                    "modem_choice": "Arris SB8200",
                },
            )

    @pytest.mark.asyncio
    async def test_generic_failure_raises_cannot_connect(self, mock_hass, mock_parser_class, mock_adapter):
        """Test generic failure raises CannotConnectError."""
        from custom_components.cable_modem_monitor.core.setup import SetupResult

        failed_result = SetupResult(
            success=False,
            error="Unknown error",
            failed_step="validation",
        )

        async def mock_executor(func, *args):
            func_name = getattr(func, "__name__", None)
            if func_name == "get_parser_by_name":
                return mock_parser_class
            elif func_name == "get_auth_adapter_for_parser":
                return mock_adapter
            elif func_name == "setup_modem":
                return failed_result
            elif callable(func):
                return func()
            return None

        mock_hass.async_add_executor_job = mock_executor

        with pytest.raises(CannotConnectError, match="Unknown error"):
            await validate_input(
                mock_hass,
                {
                    "host": "192.168.100.1",
                    "username": "",
                    "password": "",
                    "modem_choice": "Arris SB8200",
                },
            )

    @pytest.mark.asyncio
    async def test_validation_with_user_selected_parser(
        self,
        mock_hass,
        mock_parser_class,
        mock_adapter,
        mock_setup_result,
    ):
        """Test validation with user-selected parser."""

        async def mock_executor(func, *args):
            func_name = getattr(func, "__name__", None)
            if func_name == "get_parser_by_name":
                return mock_parser_class
            elif func_name == "get_auth_adapter_for_parser":
                return mock_adapter
            elif func_name == "setup_modem":
                return mock_setup_result
            elif callable(func):
                return func()
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
    async def test_validation_without_actual_model(self, mock_hass, mock_parser_class, mock_adapter):
        """Test validation when parser doesn't return actual model."""
        from custom_components.cable_modem_monitor.core.setup import SetupResult

        mock_parser = Mock()
        mock_parser.manufacturer = "Netgear"
        mock_parser.get_actual_model.return_value = None

        result = SetupResult(
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
            func_name = getattr(func, "__name__", None)
            if func_name == "get_parser_by_name":
                return mock_parser_class
            elif func_name == "get_auth_adapter_for_parser":
                return mock_adapter
            elif func_name == "setup_modem":
                return result
            elif callable(func):
                return func()
            return None

        mock_hass.async_add_executor_job = mock_executor

        with patch(
            "custom_components.cable_modem_monitor.config_flow_helpers.test_icmp_ping",
            return_value=True,
        ):
            validation_result = await validate_input(
                mock_hass,
                {
                    "host": "192.168.100.1",
                    "username": "admin",
                    "password": "pass",
                    "modem_choice": "Netgear CM600",
                },
            )

        assert "actual_model" not in validation_result["detection_info"]
        assert validation_result["detection_info"]["modem_name"] == "Netgear CM600"

    @pytest.mark.asyncio
    async def test_validation_stores_auth_discovery_status(
        self,
        mock_hass,
        mock_parser_class,
        mock_adapter,
        mock_setup_result,
    ):
        """Test validation stores auth discovery status in result."""

        async def mock_executor(func, *args):
            func_name = getattr(func, "__name__", None)
            if func_name == "get_parser_by_name":
                return mock_parser_class
            elif func_name == "get_auth_adapter_for_parser":
                return mock_adapter
            elif func_name == "setup_modem":
                return mock_setup_result
            elif callable(func):
                return func()
            return None

        mock_hass.async_add_executor_job = mock_executor

        with patch(
            "custom_components.cable_modem_monitor.config_flow_helpers.test_icmp_ping",
            return_value=True,
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

        assert result["auth_discovery_status"] == "success"
        assert result["auth_discovery_failed"] is False
        assert result["auth_discovery_error"] is None

    @pytest.mark.asyncio
    async def test_validation_with_none_parser_instance(self, mock_hass, mock_parser_class, mock_adapter):
        """Test validation handles None parser_instance gracefully."""
        from custom_components.cable_modem_monitor.core.setup import SetupResult

        # Result with no parser_instance (edge case)
        result = SetupResult(
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
            func_name = getattr(func, "__name__", None)
            if func_name == "get_parser_by_name":
                return mock_parser_class
            elif func_name == "get_auth_adapter_for_parser":
                return mock_adapter
            elif func_name == "setup_modem":
                return result
            elif callable(func):
                return func()
            return None

        mock_hass.async_add_executor_job = mock_executor

        with patch(
            "custom_components.cable_modem_monitor.config_flow_helpers.test_icmp_ping",
            return_value=True,
        ):
            validation_result = await validate_input(
                mock_hass,
                {
                    "host": "192.168.100.1",
                    "username": "",
                    "password": "",
                    "modem_choice": "Unknown Modem",
                },
            )

        # manufacturer should be None when parser_instance is None
        assert validation_result["detection_info"]["manufacturer"] is None
        assert "actual_model" not in validation_result["detection_info"]
        assert validation_result["detection_info"]["modem_name"] == "Unknown Modem"

    @pytest.mark.asyncio
    async def test_connectivity_failure_uses_default_message(self, mock_hass, mock_parser_class, mock_adapter):
        """Test connectivity failure uses default message when error is None."""
        from custom_components.cable_modem_monitor.core.setup import SetupResult

        failed_result = SetupResult(
            success=False,
            error=None,  # No specific error message
            failed_step="connectivity",
        )

        async def mock_executor(func, *args):
            func_name = getattr(func, "__name__", None)
            if func_name == "get_parser_by_name":
                return mock_parser_class
            elif func_name == "get_auth_adapter_for_parser":
                return mock_adapter
            elif func_name == "setup_modem":
                return failed_result
            elif callable(func):
                return func()
            return None

        mock_hass.async_add_executor_job = mock_executor

        with pytest.raises(CannotConnectError, match="Cannot connect to modem"):
            await validate_input(
                mock_hass,
                {
                    "host": "192.168.100.1",
                    "username": "",
                    "password": "",
                    "modem_choice": "Arris SB8200",
                },
            )

    @pytest.mark.asyncio
    async def test_auth_failure_uses_default_message(self, mock_hass, mock_parser_class, mock_adapter):
        """Test auth failure uses default message when error is None."""
        from custom_components.cable_modem_monitor.core.setup import SetupResult

        failed_result = SetupResult(
            success=False,
            error=None,  # No specific error message
            failed_step="auth",
        )

        async def mock_executor(func, *args):
            func_name = getattr(func, "__name__", None)
            if func_name == "get_parser_by_name":
                return mock_parser_class
            elif func_name == "get_auth_adapter_for_parser":
                return mock_adapter
            elif func_name == "setup_modem":
                return failed_result
            elif callable(func):
                return func()
            return None

        mock_hass.async_add_executor_job = mock_executor

        with pytest.raises(InvalidAuthError, match="Authentication failed"):
            await validate_input(
                mock_hass,
                {
                    "host": "192.168.100.1",
                    "username": "admin",
                    "password": "pass",
                    "modem_choice": "Arris SB8200",
                },
            )

    @pytest.mark.asyncio
    async def test_parser_detection_failure_uses_default_message(self, mock_hass, mock_parser_class, mock_adapter):
        """Test parser detection failure uses default message when error is None."""
        from custom_components.cable_modem_monitor.core.setup import SetupResult

        failed_result = SetupResult(
            success=False,
            error=None,  # No specific error message
            failed_step="parser_detection",
        )

        async def mock_executor(func, *args):
            func_name = getattr(func, "__name__", None)
            if func_name == "get_parser_by_name":
                return mock_parser_class
            elif func_name == "get_auth_adapter_for_parser":
                return mock_adapter
            elif func_name == "setup_modem":
                return failed_result
            elif callable(func):
                return func()
            return None

        mock_hass.async_add_executor_job = mock_executor

        with pytest.raises(UnsupportedModemError, match="Could not detect modem type"):
            await validate_input(
                mock_hass,
                {
                    "host": "192.168.100.1",
                    "username": "",
                    "password": "",
                    "modem_choice": "Arris SB8200",
                },
            )

    @pytest.mark.asyncio
    async def test_generic_failure_uses_default_message(self, mock_hass, mock_parser_class, mock_adapter):
        """Test generic failure uses default message when error is None."""
        from custom_components.cable_modem_monitor.core.setup import SetupResult

        failed_result = SetupResult(
            success=False,
            error=None,  # No specific error message
            failed_step="validation",
        )

        async def mock_executor(func, *args):
            func_name = getattr(func, "__name__", None)
            if func_name == "get_parser_by_name":
                return mock_parser_class
            elif func_name == "get_auth_adapter_for_parser":
                return mock_adapter
            elif func_name == "setup_modem":
                return failed_result
            elif callable(func):
                return func()
            return None

        mock_hass.async_add_executor_job = mock_executor

        with pytest.raises(CannotConnectError, match="Setup failed"):
            await validate_input(
                mock_hass,
                {
                    "host": "192.168.100.1",
                    "username": "",
                    "password": "",
                    "modem_choice": "Arris SB8200",
                },
            )

    @pytest.mark.asyncio
    async def test_validation_stores_hnap_config(self, mock_hass, mock_parser_class, mock_adapter):
        """Test validation stores auth_hnap_config from setup result."""
        from custom_components.cable_modem_monitor.core.setup import SetupResult

        mock_parser = Mock()
        mock_parser.manufacturer = "Arris"
        mock_parser.get_actual_model.return_value = None

        hnap_config = {
            "endpoint": "/HNAP1/",
            "namespace": "http://purenetworks.com/HNAP1/",
        }

        result = SetupResult(
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
            func_name = getattr(func, "__name__", None)
            if func_name == "get_parser_by_name":
                return mock_parser_class
            elif func_name == "get_auth_adapter_for_parser":
                return mock_adapter
            elif func_name == "setup_modem":
                return result
            elif callable(func):
                return func()
            return None

        mock_hass.async_add_executor_job = mock_executor

        with patch(
            "custom_components.cable_modem_monitor.config_flow_helpers.test_icmp_ping",
            return_value=True,
        ):
            validation_result = await validate_input(
                mock_hass,
                {
                    "host": "192.168.100.1",
                    "username": "admin",
                    "password": "pass",
                    "modem_choice": "Arris SB8200",
                },
            )

        assert validation_result["auth_hnap_config"] == hnap_config
        assert validation_result["auth_strategy"] == "hnap_session"

    @pytest.mark.asyncio
    async def test_validation_stores_url_token_config(self, mock_hass, mock_parser_class, mock_adapter):
        """Test validation stores auth_url_token_config from setup result."""
        from custom_components.cable_modem_monitor.core.setup import SetupResult

        mock_parser = Mock()
        mock_parser.manufacturer = "Motorola"
        mock_parser.get_actual_model.return_value = None

        url_token_config = {
            "login_prefix": "login",
            "data_page": "MotoStatusSoftware.asp",
            "token_pattern": r"currentSessionId\s*=\s*['\"]([^'\"]+)['\"]",
        }

        result = SetupResult(
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
            func_name = getattr(func, "__name__", None)
            if func_name == "get_parser_by_name":
                return mock_parser_class
            elif func_name == "get_auth_adapter_for_parser":
                return mock_adapter
            elif func_name == "setup_modem":
                return result
            elif callable(func):
                return func()
            return None

        mock_hass.async_add_executor_job = mock_executor

        with patch(
            "custom_components.cable_modem_monitor.config_flow_helpers.test_icmp_ping",
            return_value=True,
        ):
            validation_result = await validate_input(
                mock_hass,
                {
                    "host": "192.168.100.1",
                    "username": "admin",
                    "password": "pass",
                    "modem_choice": "Motorola MB8611",
                },
            )

        assert validation_result["auth_url_token_config"] == url_token_config
        assert validation_result["auth_strategy"] == "url_token_session"
