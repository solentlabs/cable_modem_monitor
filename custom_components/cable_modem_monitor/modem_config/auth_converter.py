"""Direct conversion from modem.yaml schema to auth.configs.

This module provides direct conversion from Pydantic ModemConfig auth configuration
to typed AuthConfig dataclasses, bypassing the adapter's dict intermediary.

This is the approach:
    modem.yaml (Pydantic) → AuthConfig (dataclass) → Strategy.login()

Instead of:
    modem.yaml (Pydantic) → adapter → dict → AuthHandler → inline implementation
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.cable_modem_monitor.core.auth.configs import (
    BasicAuthConfig,
    FormAuthConfig,
    HNAPAuthConfig,
    NoAuthConfig,
    UrlTokenSessionConfig,
)
from custom_components.cable_modem_monitor.core.auth.types import AuthStrategyType, HMACAlgorithm

if TYPE_CHECKING:
    from custom_components.cable_modem_monitor.modem_config.schema import (
        FormAuthConfig as ModemFormAuthConfig,
        HnapAuthConfig as ModemHnapAuthConfig,
        ModemConfig,
        UrlTokenAuthConfig as ModemUrlTokenAuthConfig,
    )

# Type alias for return type
AuthConfigType = FormAuthConfig | HNAPAuthConfig | UrlTokenSessionConfig | BasicAuthConfig | NoAuthConfig


def modem_config_to_auth_config(config: ModemConfig) -> tuple[AuthStrategyType, AuthConfigType]:
    """Convert ModemConfig auth settings to typed AuthConfig.

    Args:
        config: ModemConfig from modem.yaml

    Returns:
        Tuple of (AuthStrategyType, AuthConfig instance)
    """
    from custom_components.cable_modem_monitor.modem_config.schema import AuthStrategy

    auth = config.auth
    strategy = auth.strategy

    if strategy == AuthStrategy.NONE:
        return AuthStrategyType.NO_AUTH, NoAuthConfig()

    if strategy == AuthStrategy.BASIC:
        return AuthStrategyType.BASIC_HTTP, BasicAuthConfig()

    if strategy == AuthStrategy.FORM and auth.form:
        return form_config_to_auth_config(auth.form)

    if strategy == AuthStrategy.HNAP and auth.hnap:
        return hnap_config_to_auth_config(auth.hnap)

    if strategy == AuthStrategy.URL_TOKEN and auth.url_token:
        return url_token_config_to_auth_config(auth.url_token)

    # Default: no auth
    return AuthStrategyType.NO_AUTH, NoAuthConfig()


def form_config_to_auth_config(form: ModemFormAuthConfig) -> tuple[AuthStrategyType, FormAuthConfig]:
    """Convert modem.yaml FormAuthConfig to auth.configs.FormAuthConfig.

    Args:
        form: FormAuthConfig from modem.yaml schema

    Returns:
        Tuple of (AuthStrategyType, FormAuthConfig)

    Note:
        As of v3.12.0, FORM_BASE64 was consolidated into FORM_PLAIN.
        Password encoding (plain vs base64) is now specified via the
        password_encoding field in FormAuthConfig, not the strategy type.
    """
    # Always use FORM_PLAIN - encoding is controlled by password_encoding field
    strategy = AuthStrategyType.FORM_PLAIN

    return strategy, FormAuthConfig(
        strategy=strategy,
        login_url=form.action,
        username_field=form.username_field,
        password_field=form.password_field,
        method=form.method,
        hidden_fields=dict(form.hidden_fields) if form.hidden_fields else None,
        password_encoding=form.password_encoding.value,
        # success_indicator from form.success if present
        success_indicator=form.success.indicator if form.success else None,
    )


def hnap_config_to_auth_config(hnap: ModemHnapAuthConfig) -> tuple[AuthStrategyType, HNAPAuthConfig]:
    """Convert modem.yaml HnapAuthConfig to auth.configs.HNAPAuthConfig.

    Args:
        hnap: HnapAuthConfig from modem.yaml schema

    Returns:
        Tuple of (AuthStrategyType, HNAPAuthConfig)
    """
    # Convert string from modem.yaml to enum
    hmac_algo = HMACAlgorithm(hnap.hmac_algorithm)

    return AuthStrategyType.HNAP_SESSION, HNAPAuthConfig(
        strategy=AuthStrategyType.HNAP_SESSION,
        endpoint=hnap.endpoint,
        namespace=hnap.namespace,
        empty_action_value=hnap.empty_action_value,
        hmac_algorithm=hmac_algo,
    )


def url_token_config_to_auth_config(
    url_token: ModemUrlTokenAuthConfig,
) -> tuple[AuthStrategyType, UrlTokenSessionConfig]:
    """Convert modem.yaml UrlTokenAuthConfig to auth.configs.UrlTokenSessionConfig.

    Args:
        url_token: UrlTokenAuthConfig from modem.yaml schema

    Returns:
        Tuple of (AuthStrategyType, UrlTokenSessionConfig)
    """
    return AuthStrategyType.URL_TOKEN_SESSION, UrlTokenSessionConfig(
        strategy=AuthStrategyType.URL_TOKEN_SESSION,
        login_page=url_token.login_page,
        login_prefix=url_token.login_prefix,
        token_prefix=url_token.token_prefix,
        session_cookie_name=url_token.session_cookie,
        success_indicator=url_token.success_indicator or "Downstream",
    )
