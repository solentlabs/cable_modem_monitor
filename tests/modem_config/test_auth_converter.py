"""Tests for modem_config.auth_converter module.

TEST DATA TABLES
================
This module uses table-driven tests for auth strategy conversion.
Tables are defined at the top of the file with ASCII box-drawing comments.
"""

from __future__ import annotations

import pytest

from custom_components.cable_modem_monitor.core.auth.configs import (
    BasicAuthConfig,
    FormAuthConfig,
    HNAPAuthConfig,
    NoAuthConfig,
    UrlTokenSessionConfig,
)
from custom_components.cable_modem_monitor.core.auth.types import AuthStrategyType
from custom_components.cable_modem_monitor.modem_config.auth_converter import (
    form_config_to_auth_config,
    hnap_config_to_auth_config,
    modem_config_to_auth_config,
    url_token_config_to_auth_config,
)
from custom_components.cable_modem_monitor.modem_config.schema import (
    AuthConfig,
    AuthStrategy,
    FormAuthConfig as SchemaFormAuthConfig,
    FormSuccessConfig,
    HnapAuthConfig as SchemaHnapAuthConfig,
    ModemConfig,
    PasswordEncoding,
    UrlTokenAuthConfig as SchemaUrlTokenAuthConfig,
)

# =============================================================================
# Test Data Tables
# =============================================================================

# -----------------------------------------------------------------------------
# Form Auth Conversion Cases
# -----------------------------------------------------------------------------
# ┌──────────────────┬──────────────────┬────────────────────────────────────┐
# │ password_encoding│ expected_strategy│ description                        │
# ├──────────────────┼──────────────────┼────────────────────────────────────┤
# │ plain            │ FORM_PLAIN       │ plain text password                │
# │ base64           │ FORM_PLAIN       │ base64 encoded (same strategy)     │
# └──────────────────┴──────────────────┴────────────────────────────────────┘
#
# fmt: off
FORM_AUTH_CASES = [
    # (password_encoding, expected_strategy, description)
    (PasswordEncoding.PLAIN,  AuthStrategyType.FORM_PLAIN, "plain text password"),
    (PasswordEncoding.BASE64, AuthStrategyType.FORM_PLAIN, "base64 encoded - same strategy"),
]
# fmt: on


class TestModemConfigToAuthConfig:
    """Test modem_config_to_auth_config conversion."""

    def test_none_strategy_returns_no_auth(self):
        """Test that NONE strategy returns NoAuthConfig."""
        config = ModemConfig(
            manufacturer="Test",
            model="TestModem",
            auth=AuthConfig(strategy=AuthStrategy.NONE),
        )

        strategy_type, auth_config = modem_config_to_auth_config(config)

        assert strategy_type == AuthStrategyType.NO_AUTH
        assert isinstance(auth_config, NoAuthConfig)

    def test_basic_strategy_returns_basic_auth(self):
        """Test that BASIC strategy returns BasicAuthConfig."""
        config = ModemConfig(
            manufacturer="Test",
            model="TestModem",
            auth=AuthConfig(strategy=AuthStrategy.BASIC),
        )

        strategy_type, auth_config = modem_config_to_auth_config(config)

        assert strategy_type == AuthStrategyType.BASIC_HTTP
        assert isinstance(auth_config, BasicAuthConfig)

    def test_form_strategy_returns_form_auth(self):
        """Test that FORM strategy returns FormAuthConfig."""
        config = ModemConfig(
            manufacturer="Test",
            model="TestModem",
            auth=AuthConfig(
                strategy=AuthStrategy.FORM,
                form=SchemaFormAuthConfig(
                    action="/login",
                    username_field="user",
                    password_field="pass",
                ),
            ),
        )

        strategy_type, auth_config = modem_config_to_auth_config(config)

        assert strategy_type == AuthStrategyType.FORM_PLAIN
        assert isinstance(auth_config, FormAuthConfig)

    def test_hnap_strategy_returns_hnap_auth(self):
        """Test that HNAP strategy returns HNAPAuthConfig."""
        config = ModemConfig(
            manufacturer="Test",
            model="TestModem",
            auth=AuthConfig(
                strategy=AuthStrategy.HNAP,
                hnap=SchemaHnapAuthConfig(),
            ),
        )

        strategy_type, auth_config = modem_config_to_auth_config(config)

        assert strategy_type == AuthStrategyType.HNAP_SESSION
        assert isinstance(auth_config, HNAPAuthConfig)

    def test_url_token_strategy_returns_url_token_auth(self):
        """Test that URL_TOKEN strategy returns UrlTokenSessionConfig."""
        config = ModemConfig(
            manufacturer="Test",
            model="TestModem",
            auth=AuthConfig(
                strategy=AuthStrategy.URL_TOKEN,
                url_token=SchemaUrlTokenAuthConfig(
                    login_page="/login.html",
                    session_cookie="sessionId",
                ),
            ),
        )

        strategy_type, auth_config = modem_config_to_auth_config(config)

        assert strategy_type == AuthStrategyType.URL_TOKEN_SESSION
        assert isinstance(auth_config, UrlTokenSessionConfig)

    def test_missing_form_config_returns_no_auth(self):
        """Test that FORM strategy without form config returns NoAuthConfig."""
        config = ModemConfig(
            manufacturer="Test",
            model="TestModem",
            auth=AuthConfig(strategy=AuthStrategy.FORM, form=None),
        )

        strategy_type, auth_config = modem_config_to_auth_config(config)

        assert strategy_type == AuthStrategyType.NO_AUTH
        assert isinstance(auth_config, NoAuthConfig)


class TestFormConfigToAuthConfig:
    """Test form_config_to_auth_config conversion."""

    @pytest.mark.parametrize(
        "encoding,expected_strategy,desc",
        FORM_AUTH_CASES,
        ids=[c[2] for c in FORM_AUTH_CASES],
    )
    def test_encoding_to_strategy(self, encoding, expected_strategy, desc):
        """Test password encoding maps to correct strategy via table-driven cases."""
        form = SchemaFormAuthConfig(
            action="/login",
            username_field="user",
            password_field="pass",
            password_encoding=encoding,
        )

        strategy_type, auth_config = form_config_to_auth_config(form)

        assert strategy_type == expected_strategy, f"Failed: {desc}"
        assert auth_config.password_encoding == encoding.value

    def test_form_fields_copied_correctly(self):
        """Test that form fields are copied to auth config."""
        form = SchemaFormAuthConfig(
            action="/goform/login",
            method="POST",
            username_field="loginUsername",
            password_field="loginPassword",
            hidden_fields={"csrf": "token123"},
            password_encoding=PasswordEncoding.BASE64,
            success=FormSuccessConfig(indicator="Welcome"),
        )

        _, auth_config = form_config_to_auth_config(form)

        assert auth_config.login_url == "/goform/login"
        assert auth_config.method == "POST"
        assert auth_config.username_field == "loginUsername"
        assert auth_config.password_field == "loginPassword"
        assert auth_config.hidden_fields == {"csrf": "token123"}
        assert auth_config.password_encoding == "base64"
        assert auth_config.success_indicator == "Welcome"

    def test_no_success_config(self):
        """Test that missing success config results in None indicator."""
        form = SchemaFormAuthConfig(
            action="/login",
            username_field="user",
            password_field="pass",
            success=None,
        )

        _, auth_config = form_config_to_auth_config(form)

        assert auth_config.success_indicator is None


class TestHnapConfigToAuthConfig:
    """Test hnap_config_to_auth_config conversion."""

    def test_hnap_defaults(self):
        """Test HNAP config with default values."""
        hnap = SchemaHnapAuthConfig()

        strategy_type, auth_config = hnap_config_to_auth_config(hnap)

        assert strategy_type == AuthStrategyType.HNAP_SESSION
        assert auth_config.endpoint == "/HNAP1/"
        assert auth_config.namespace == "http://purenetworks.com/HNAP1/"
        assert auth_config.empty_action_value == ""

    def test_hnap_custom_values(self):
        """Test HNAP config with custom values."""
        hnap = SchemaHnapAuthConfig(
            endpoint="/custom/hnap",
            namespace="http://custom.namespace/",
            empty_action_value="empty",
        )

        _, auth_config = hnap_config_to_auth_config(hnap)

        assert auth_config.endpoint == "/custom/hnap"
        assert auth_config.namespace == "http://custom.namespace/"
        assert auth_config.empty_action_value == "empty"


class TestUrlTokenConfigToAuthConfig:
    """Test url_token_config_to_auth_config conversion."""

    def test_url_token_basic(self):
        """Test URL token config with required fields."""
        url_token = SchemaUrlTokenAuthConfig(
            login_page="/cmconnectionstatus.html",
            session_cookie="credential",
        )

        strategy_type, auth_config = url_token_config_to_auth_config(url_token)

        assert strategy_type == AuthStrategyType.URL_TOKEN_SESSION
        assert auth_config.login_page == "/cmconnectionstatus.html"
        assert auth_config.session_cookie_name == "credential"

    def test_url_token_with_prefixes(self):
        """Test URL token config with custom prefixes."""
        url_token = SchemaUrlTokenAuthConfig(
            login_page="/login.html",
            login_prefix="auth_",
            token_prefix="session_",
            session_cookie="sid",
        )

        _, auth_config = url_token_config_to_auth_config(url_token)

        assert auth_config.login_prefix == "auth_"
        assert auth_config.token_prefix == "session_"

    def test_url_token_success_indicator_default(self):
        """Test URL token config uses default success indicator."""
        url_token = SchemaUrlTokenAuthConfig(
            login_page="/login.html",
            session_cookie="sid",
            success_indicator=None,
        )

        _, auth_config = url_token_config_to_auth_config(url_token)

        assert auth_config.success_indicator == "Downstream"

    def test_url_token_custom_success_indicator(self):
        """Test URL token config with custom success indicator."""
        url_token = SchemaUrlTokenAuthConfig(
            login_page="/login.html",
            session_cookie="sid",
            success_indicator="Channel Status",
        )

        _, auth_config = url_token_config_to_auth_config(url_token)

        assert auth_config.success_indicator == "Channel Status"
