"""Tests for ModemDataCollector edge cases.

Covers connection failures during auth, HNAP resource loading,
HNAP logout, missing parser config, auth context updates, and
URL token extraction.

These complement test_collector.py which covers signal classification
and basic session lifecycle.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests
from solentlabs.cable_modem_monitor_core.auth.base import AuthContext, AuthResult
from solentlabs.cable_modem_monitor_core.models.modem_config.actions import (
    HnapAction,
)
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import (
    BasicAuth,
    HnapAuth,
    NoneAuth,
)
from solentlabs.cable_modem_monitor_core.orchestration.collector import (
    ModemDataCollector,
)
from solentlabs.cable_modem_monitor_core.orchestration.signals import (
    CollectorSignal,
)

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_config(
    *,
    auth_type: str = "none",
    transport: str = "http",
    cookie_name: str = "",
    token_prefix: str = "",
    max_concurrent: int = 0,
    logout_action: Any = None,
    timeout: int = 10,
    hmac_algorithm: str = "md5",
) -> Any:
    """Build a minimal ModemConfig-like object for testing."""
    config = MagicMock()
    config.transport = transport
    config.timeout = timeout

    if auth_type == "none":
        config.auth = NoneAuth(strategy="none")
    elif auth_type == "basic":
        config.auth = BasicAuth(strategy="basic")
    elif auth_type == "hnap":
        config.auth = HnapAuth(strategy="hnap", hmac_algorithm=hmac_algorithm)
    else:
        config.auth = MagicMock()
        config.auth.strategy = auth_type

    if cookie_name or max_concurrent or token_prefix:
        config.session = MagicMock()
        config.session.cookie_name = cookie_name
        config.session.max_concurrent = max_concurrent
        config.session.token_prefix = token_prefix
        config.session.headers = {}
    else:
        config.session = None

    if logout_action is not None:
        config.actions = MagicMock()
        config.actions.logout = logout_action
    else:
        config.actions = None

    config.behaviors = None
    return config


# ------------------------------------------------------------------
# Tests — session headers from modem config
# ------------------------------------------------------------------


class TestSessionHeaders:
    """Collector passes session headers to auth manager."""

    def test_session_headers_applied(self) -> None:
        """Session headers from modem_config are passed to configure_session."""
        config = MagicMock()
        config.transport = "http"
        config.timeout = 10
        config.auth = NoneAuth(strategy="none")
        config.session = MagicMock()
        config.session.cookie_name = ""
        config.session.max_concurrent = 0
        config.session.token_prefix = ""
        config.session.headers = {"X-Custom": "value"}
        config.actions = None
        config.behaviors = None

        collector = ModemDataCollector(config, None, None, "http://localhost", "", "")
        # The headers should have been applied during __init__
        # Verify by checking the session has the custom header
        assert collector._session.headers.get("X-Custom") == "value"


# ------------------------------------------------------------------
# Tests — connection failure during auth
# ------------------------------------------------------------------


class TestConnectionFailureDuringAuth:
    """ConnectionError/Timeout during authenticate → CONNECTIVITY signal."""

    def test_connection_error_during_auth(self) -> None:
        """requests.ConnectionError during auth → CONNECTIVITY."""
        config = _make_config(auth_type="basic")
        collector = ModemDataCollector(config, MagicMock(), None, "http://localhost", "", "")

        with patch.object(
            collector,
            "_ensure_authenticated",
            side_effect=requests.ConnectionError("refused"),
        ):
            result = collector.execute()

        assert result.success is False
        assert result.signal == CollectorSignal.CONNECTIVITY

    def test_timeout_during_auth(self) -> None:
        """requests.Timeout during auth → CONNECTIVITY."""
        config = _make_config(auth_type="basic")
        collector = ModemDataCollector(config, MagicMock(), None, "http://localhost", "", "")

        with patch.object(
            collector,
            "_ensure_authenticated",
            side_effect=requests.Timeout("timed out"),
        ):
            result = collector.execute()

        assert result.success is False
        assert result.signal == CollectorSignal.CONNECTIVITY


# ------------------------------------------------------------------
# Tests — auth context updates
# ------------------------------------------------------------------


class TestAuthContextUpdate:
    """Auth context is stored on successful authentication."""

    def test_auth_context_saved_on_success(self) -> None:
        """Successful auth stores auth_context from result."""
        config = _make_config(auth_type="basic")
        collector = ModemDataCollector(config, MagicMock(), None, "http://localhost", "", "")

        mock_context = AuthContext(private_key="test_key")
        mock_result = AuthResult(success=True, auth_context=mock_context)

        with (
            patch.object(collector._auth_manager, "authenticate", return_value=mock_result),
            patch.object(collector, "_load_resources", return_value={}),
            patch.object(collector, "_parse", return_value={"downstream": [], "upstream": [], "system_info": {}}),
        ):
            result = collector.execute()

        assert result.success is True
        assert collector._auth_context is mock_context


# ------------------------------------------------------------------
# Tests — missing parser config
# ------------------------------------------------------------------


class TestMissingParserConfig:
    """parser_config=None raises RuntimeError in _load_resources."""

    def test_load_resources_no_parser_config(self) -> None:
        """_load_resources raises when parser_config is None."""
        config = _make_config(auth_type="none")
        collector = ModemDataCollector(config, None, None, "http://localhost", "", "")

        mock_result = AuthResult(success=True)
        with pytest.raises(RuntimeError, match="custom parser.py"):
            collector._load_resources(mock_result)

    def test_parse_no_coordinator(self) -> None:
        """_parse raises when coordinator is None (no parser_config)."""
        config = _make_config(auth_type="none")
        collector = ModemDataCollector(config, None, None, "http://localhost", "", "")

        with pytest.raises(RuntimeError, match="No parser coordinator"):
            collector._parse({})


# ------------------------------------------------------------------
# Tests — HNAP resource loading
# ------------------------------------------------------------------


class TestHnapResourceLoading:
    """HNAP transport uses HNAPLoader with correct algorithm."""

    def test_hnap_loader_created_with_md5(self) -> None:
        """HNAP loader uses md5 algorithm from config."""
        config = _make_config(auth_type="hnap", transport="hnap", hmac_algorithm="md5")
        parser_config = MagicMock()
        collector = ModemDataCollector(config, parser_config, None, "http://localhost", "", "pw")

        # Set auth context as if authenticated
        collector._auth_context = AuthContext(private_key="test_private_key")

        with patch("solentlabs.cable_modem_monitor_core.loaders.hnap.HNAPLoader") as mock_loader_cls:
            mock_loader = MagicMock()
            mock_loader.fetch.return_value = {"hnap_data": "ok"}
            mock_loader_cls.return_value = mock_loader

            result = collector._load_hnap_resources()

        mock_loader_cls.assert_called_once_with(
            session=collector._session,
            base_url="http://localhost",
            private_key="test_private_key",
            hmac_algorithm="md5",
            timeout=10,
        )
        assert result == {"hnap_data": "ok"}

    def test_hnap_loader_with_sha256(self) -> None:
        """HNAP loader uses sha256 when config specifies it."""
        config = _make_config(auth_type="hnap", transport="hnap", hmac_algorithm="sha256")
        parser_config = MagicMock()
        collector = ModemDataCollector(config, parser_config, None, "http://localhost", "", "pw")
        collector._auth_context = AuthContext(private_key="key")

        with patch("solentlabs.cable_modem_monitor_core.loaders.hnap.HNAPLoader") as mock_loader_cls:
            mock_loader_cls.return_value.fetch.return_value = {}
            collector._load_hnap_resources()

        assert mock_loader_cls.call_args[1]["hmac_algorithm"] == "sha256"

    def test_hnap_loader_no_auth_context(self) -> None:
        """HNAP loader uses empty private key when no auth context."""
        config = _make_config(auth_type="hnap", transport="hnap")
        parser_config = MagicMock()
        collector = ModemDataCollector(config, parser_config, None, "http://localhost", "", "pw")
        # auth_context is None by default

        with patch("solentlabs.cable_modem_monitor_core.loaders.hnap.HNAPLoader") as mock_loader_cls:
            mock_loader_cls.return_value.fetch.return_value = {}
            collector._load_hnap_resources()

        assert mock_loader_cls.call_args[1]["private_key"] == ""


# ------------------------------------------------------------------
# Tests — HNAP logout
# ------------------------------------------------------------------


class TestHnapLogout:
    """HNAP logout action dispatches to execute_hnap_action."""

    def test_hnap_logout_called(self) -> None:
        """HNAP logout action dispatches to execute_hnap_action."""
        logout_action = HnapAction(
            type="hnap",
            action_name="Logout",
        )
        config = _make_config(
            auth_type="hnap",
            transport="hnap",
            cookie_name="uid",
            max_concurrent=1,
            logout_action=logout_action,
        )
        collector = ModemDataCollector(config, MagicMock(), None, "http://localhost", "", "pw")
        collector._auth_context = AuthContext(private_key="test_key")

        modem_data: dict[str, Any] = {"downstream": [], "upstream": [], "system_info": {}}
        with (
            patch.object(collector, "_ensure_authenticated", return_value=MagicMock(success=True)),
            patch.object(collector, "_load_resources", return_value={}),
            patch.object(collector, "_parse", return_value=modem_data),
            patch("solentlabs.cable_modem_monitor_core.orchestration.collector.execute_hnap_action") as mock_hnap,
        ):
            result = collector.execute()

        assert result.success is True
        mock_hnap.assert_called_once()
        call_kwargs = mock_hnap.call_args
        assert call_kwargs[1]["private_key"] == "test_key"
        assert call_kwargs[1]["hmac_algorithm"] == "md5"


# ------------------------------------------------------------------
# Tests — URL token extraction
# ------------------------------------------------------------------


class TestUrlTokenExtraction:
    """URL token extraction from session cookie."""

    def test_url_token_from_cookie(self) -> None:
        """token_prefix + cookie_name → url_token extracted."""
        config = _make_config(
            auth_type="none",
            cookie_name="auth_token",
            token_prefix="?token=",
        )
        parser_config = MagicMock()
        collector = ModemDataCollector(config, parser_config, None, "http://localhost", "", "")

        # Set cookie in session
        collector._session.cookies.set("auth_token", "abc123")

        mock_result = AuthResult(success=True)
        with patch("solentlabs.cable_modem_monitor_core.orchestration.collector.HTTPResourceLoader") as mock_loader_cls:
            mock_loader = MagicMock()
            mock_loader.fetch.return_value = {}
            mock_loader_cls.return_value = mock_loader

            with patch(
                "solentlabs.cable_modem_monitor_core.orchestration.collector.collect_fetch_targets", return_value=[]
            ):
                collector._load_http_resources(mock_result)

        # Verify HTTPResourceLoader was called with url_token
        assert mock_loader_cls.call_args[1]["url_token"] == "abc123"
        assert mock_loader_cls.call_args[1]["token_prefix"] == "?token="

    def test_no_url_token_without_prefix(self) -> None:
        """No token_prefix → url_token is empty."""
        config = _make_config(
            auth_type="none",
            cookie_name="auth_token",
            token_prefix="",
        )
        parser_config = MagicMock()
        collector = ModemDataCollector(config, parser_config, None, "http://localhost", "", "")
        collector._session.cookies.set("auth_token", "abc123")

        mock_result = AuthResult(success=True)
        with patch("solentlabs.cable_modem_monitor_core.orchestration.collector.HTTPResourceLoader") as mock_loader_cls:
            mock_loader = MagicMock()
            mock_loader.fetch.return_value = {}
            mock_loader_cls.return_value = mock_loader

            with patch(
                "solentlabs.cable_modem_monitor_core.orchestration.collector.collect_fetch_targets", return_value=[]
            ):
                collector._load_http_resources(mock_result)

        assert mock_loader_cls.call_args[1]["url_token"] == ""


# ------------------------------------------------------------------
# Tests — HNAP session_is_valid
# ------------------------------------------------------------------


class TestHnapSessionValidity:
    """session_is_valid checks for HNAP transport."""

    def test_hnap_valid_with_cookie_and_key(self) -> None:
        """HNAP session valid when uid cookie and private key present."""
        config = _make_config(auth_type="hnap", transport="hnap")
        collector = ModemDataCollector(config, None, None, "http://localhost", "", "pw")
        collector._auth_context = AuthContext(private_key="some_key")
        collector._session.cookies.set("uid", "session123")
        assert collector.session_is_valid is True

    def test_hnap_invalid_without_cookie(self) -> None:
        """HNAP session invalid without uid cookie."""
        config = _make_config(auth_type="hnap", transport="hnap")
        collector = ModemDataCollector(config, None, None, "http://localhost", "", "pw")
        collector._auth_context = AuthContext(private_key="some_key")
        assert collector.session_is_valid is False

    def test_url_token_valid(self) -> None:
        """Session valid when auth context has url_token."""
        config = _make_config(auth_type="none")
        collector = ModemDataCollector(config, None, None, "http://localhost", "", "")
        collector._auth_context = AuthContext(url_token="token123")
        assert collector.session_is_valid is True
