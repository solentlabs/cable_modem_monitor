"""Runtime authentication handler for polling.

This module applies stored authentication strategies during polling.
Unlike AuthDiscovery (which discovers strategies), AuthHandler applies
a known strategy to authenticate a session.

All authentication types are handled directly by AuthHandler - parsers
do not implement login() methods.

Usage:
    from custom_components.cable_modem_monitor.core.auth.handler import AuthHandler
    from custom_components.cable_modem_monitor.core.auth.types import AuthStrategyType

    handler = AuthHandler(
        strategy=AuthStrategyType.FORM_PLAIN,
        form_config=stored_form_config,
    )

    success, html = handler.authenticate(
        session=session,
        base_url="http://192.168.100.1",
        username="admin",
        password="password",
    )
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .base import AuthResult
from .types import AuthStrategyType, HMACAlgorithm

if TYPE_CHECKING:
    import requests

    from .hnap import HNAPJsonRequestBuilder

_LOGGER = logging.getLogger(__name__)

# Default HNAP configuration (works for most HNAP modems)
DEFAULT_HNAP_CONFIG = {
    "endpoint": "/HNAP1/",
    "namespace": "http://purenetworks.com/HNAP1/",
    "empty_action_value": "",  # Both S33 and MB8611 use "" (verified from HAR captures)
}

# Default URL token configuration
DEFAULT_URL_TOKEN_CONFIG = {
    "login_page": "/cmconnectionstatus.html",
    "login_prefix": "login_",
    "session_cookie_name": "credential",
    "data_page": "/cmconnectionstatus.html",
    "token_prefix": "ct_",
    "success_indicator": "Downstream",
}


class AuthHandler:
    """Applies stored authentication strategy during polling.

    This is the runtime counterpart to AuthDiscovery. While AuthDiscovery
    inspects responses to determine the auth strategy, AuthHandler applies
    a known strategy to authenticate a session.

    Supported strategies (all handled directly, no parser delegation):
    - NO_AUTH: No authentication needed
    - BASIC_HTTP: HTTP Basic Authentication
    - FORM_PLAIN: Form-based login (encoding controlled by password_encoding)
    - HNAP_SESSION: HNAP/SOAP authentication
    - URL_TOKEN_SESSION: URL-based token auth
    """

    def __init__(
        self,
        strategy: AuthStrategyType | str | None = None,
        form_config: dict[str, Any] | None = None,
        hnap_config: dict[str, Any] | None = None,
        url_token_config: dict[str, Any] | None = None,
        fallback_strategies: list[dict[str, Any]] | None = None,
    ):
        """Initialize auth handler.

        Args:
            strategy: The auth strategy to use (AuthStrategyType or string value)
            form_config: Form configuration for form-based auth (required for FORM_*)
            hnap_config: HNAP configuration (endpoint, namespace, empty_action_value)
            url_token_config: URL token configuration (login_page, etc.)
            fallback_strategies: Ordered list of alternate strategies to try if primary fails.
                Each entry is a dict with 'strategy' key and optional config keys.
                Used for try-until-success pattern (e.g., modems with firmware variations).
        """
        # Normalize strategy to AuthStrategyType
        if isinstance(strategy, str):
            strategy_lower = strategy.lower()
            # Map legacy strategy names to current enum values
            # Added in v3.12.0: form_base64 was consolidated into form_plain
            # (encoding now specified via password_encoding field)
            # TODO(v3.14+): Remove this mapping once users have had time to update
            legacy_mapping = {
                "form_base64": "form_plain",
            }
            if strategy_lower in legacy_mapping:
                strategy_lower = legacy_mapping[strategy_lower]
                _LOGGER.debug("Mapped legacy auth strategy '%s' to '%s'", strategy, strategy_lower)
            try:
                # Handle case-insensitive matching (config may store uppercase)
                self.strategy = AuthStrategyType(strategy_lower)
            except ValueError:
                _LOGGER.warning("Unknown auth strategy string: %s, defaulting to UNKNOWN", strategy)
                self.strategy = AuthStrategyType.UNKNOWN
        elif strategy is None:
            self.strategy = AuthStrategyType.UNKNOWN
        else:
            self.strategy = strategy

        self.form_config = form_config or {}
        self.hnap_config = {**DEFAULT_HNAP_CONFIG, **(hnap_config or {})}
        self.url_token_config = {**DEFAULT_URL_TOKEN_CONFIG, **(url_token_config or {})}

        # Fallback strategies for try-until-success
        self._fallback_strategies = fallback_strategies or []

        # HNAP builder instance (created on first auth, reused for data fetches)
        self._hnap_builder: HNAPJsonRequestBuilder | None = None

        # Session token from URL token auth (Issue #81)
        # This is the token from the response body that must be used for subsequent
        # page fetches. It's different from the cookie value on some firmware.
        self._session_token: str | None = None

    @classmethod
    def from_modem_config(cls, config: Any, auth_type: str | None = None) -> AuthHandler:
        """Create AuthHandler from a modem.yaml config.

        Uses auth.types{} as the source of truth. Creates AuthHandler with
        the appropriate strategy and config based on the selected auth type.

        Args:
            config: ModemConfig from modem.yaml
            auth_type: Specific auth type to use, or None for default

        Returns:
            AuthHandler configured from modem.yaml
        """
        from custom_components.cable_modem_monitor.modem_config import ModemConfigAuthAdapter

        adapter = ModemConfigAuthAdapter(config)

        # Get static auth config for the specified (or default) auth type
        static_config = adapter.get_static_auth_config(auth_type)

        # Map strategy string to AuthStrategyType
        strategy_str = static_config.get("auth_strategy", "no_auth")
        strategy = cls._strategy_from_string(strategy_str)

        _LOGGER.debug(
            "Created AuthHandler from modem.yaml (strategy=%s, auth_type=%s)",
            strategy.value,
            auth_type or adapter.get_default_auth_type(),
        )

        return cls(
            strategy=strategy,
            form_config=static_config.get("auth_form_config"),
            hnap_config=static_config.get("auth_hnap_config"),
            url_token_config=static_config.get("auth_url_token_config"),
        )

    @staticmethod
    def _strategy_from_string(strategy_str: str) -> AuthStrategyType:
        """Convert strategy string to AuthStrategyType.

        Args:
            strategy_str: Strategy string (e.g., "form_plain", "hnap_session")

        Returns:
            AuthStrategyType enum value
        """
        try:
            return AuthStrategyType(strategy_str.lower())
        except ValueError:
            _LOGGER.warning("Unknown auth strategy: %s, defaulting to NO_AUTH", strategy_str)
            return AuthStrategyType.NO_AUTH

    @classmethod
    def from_parser(cls, parser_class_name: str) -> AuthHandler | None:
        """Create AuthHandler from modem.yaml looked up by parser class name.

        This is a convenience method for Phase 7 migration - allows creating
        AuthHandler directly from a parser without accessing parser attributes.

        Args:
            parser_class_name: The parser class name (e.g., "ArrisS33HnapParser")

        Returns:
            AuthHandler if modem.yaml found, None otherwise
        """
        try:
            from custom_components.cable_modem_monitor.modem_config import (
                get_modem_config_for_parser,
            )

            config = get_modem_config_for_parser(parser_class_name)
            if config:
                return cls.from_modem_config(config)
        except Exception as e:
            _LOGGER.debug("Failed to create AuthHandler from modem.yaml: %s", e)

        return None

    def authenticate(
        self,
        session: requests.Session,
        base_url: str,
        username: str | None,
        password: str | None,
        verbose: bool = False,
    ) -> AuthResult:
        """Authenticate the session using the stored strategy.

        Supports try-until-success pattern: if primary strategy fails
        and fallback strategies are configured, tries each in order until one succeeds.

        Args:
            session: requests.Session to authenticate
            base_url: Modem base URL
            username: Username for authentication
            password: Password for authentication
            verbose: If True, log at INFO level (for config_flow discovery).
                     If False, log at DEBUG level (for routine polling).

        Returns:
            AuthResult with success status, error type, and response data.
            The error_type field enables callers to provide specific user feedback.
        """
        # Try primary strategy
        result = self._do_authenticate(
            self.strategy,
            self.form_config,
            self.hnap_config,
            self.url_token_config,
            session,
            base_url,
            username,
            password,
            verbose,
        )

        if result.success:
            # Store session token for subsequent page fetches (Issue #81)
            if result.session_token:
                self._session_token = result.session_token
                _LOGGER.debug("Stored session token from auth (%d chars)", len(result.session_token))
            return result

        # Try fallback strategies if primary failed
        if self._fallback_strategies:
            _LOGGER.debug(
                "Primary auth strategy %s failed, trying %d fallback strategies",
                self.strategy.value,
                len(self._fallback_strategies),
            )

            for i, fallback in enumerate(self._fallback_strategies):
                fallback_strategy_str = fallback.get("strategy", "no_auth")
                try:
                    fallback_strategy = AuthStrategyType(fallback_strategy_str)
                except ValueError:
                    _LOGGER.warning("Unknown fallback strategy: %s", fallback_strategy_str)
                    continue

                _LOGGER.debug(
                    "Trying fallback strategy %d/%d: %s",
                    i + 1,
                    len(self._fallback_strategies),
                    fallback_strategy.value,
                )

                fallback_result = self._do_authenticate(
                    fallback_strategy,
                    fallback.get("form_config", {}),
                    fallback.get("hnap_config", {}),
                    fallback.get("url_token_config", {}),
                    session,
                    base_url,
                    username,
                    password,
                    verbose,
                )

                if fallback_result.success:
                    _LOGGER.info(
                        "Fallback auth strategy succeeded: %s (was: %s)",
                        fallback_strategy.value,
                        self.strategy.value,
                    )
                    # Update primary strategy for future calls
                    self.strategy = fallback_strategy
                    self.form_config = fallback.get("form_config", {})
                    self.hnap_config = {**DEFAULT_HNAP_CONFIG, **fallback.get("hnap_config", {})}
                    self.url_token_config = {
                        **DEFAULT_URL_TOKEN_CONFIG,
                        **fallback.get("url_token_config", {}),
                    }
                    # Store session token from fallback (Issue #81)
                    if fallback_result.session_token:
                        self._session_token = fallback_result.session_token
                    return fallback_result

            _LOGGER.warning("All auth strategies failed (primary + %d fallbacks)", len(self._fallback_strategies))

        return result

    def _do_authenticate(
        self,
        strategy: AuthStrategyType,
        form_config: dict[str, Any],
        hnap_config: dict[str, Any],
        url_token_config: dict[str, Any],
        session: requests.Session,
        base_url: str,
        username: str | None,
        password: str | None,
        verbose: bool = False,
    ) -> AuthResult:
        """Execute a single authentication strategy via delegation.

        Delegates to strategy classes via AuthFactory, converting dict configs
        to typed AuthConfig objects.

        Args:
            strategy: The auth strategy to use
            form_config: Form configuration for form-based auth
            hnap_config: HNAP configuration
            url_token_config: URL token configuration
            session: requests.Session to authenticate
            base_url: Modem base URL
            username: Username for authentication
            password: Password for authentication
            verbose: If True, log at INFO level

        Returns:
            AuthResult with success status
        """
        _LOGGER.debug("Authenticating with strategy: %s", strategy.value)

        # Get strategy instance from factory
        from .factory import AuthFactory

        try:
            strategy_instance = AuthFactory.get_strategy(strategy)
        except ValueError:
            _LOGGER.warning("Unknown auth strategy: %s - attempting without auth", strategy.value)
            return AuthResult.ok()

        # Convert dict config to typed AuthConfig
        config = self._create_typed_config(strategy, form_config, hnap_config, url_token_config)

        # Delegate to strategy
        result = strategy_instance.login(session, base_url, username, password, config, verbose)

        # For HNAP JSON strategy, store the builder for later use
        if strategy == AuthStrategyType.HNAP_SESSION and result.success:
            from .strategies.hnap_json import HNAPJsonAuthStrategy

            if isinstance(strategy_instance, HNAPJsonAuthStrategy):
                self._hnap_builder = strategy_instance.builder

        return result

    def _create_typed_config(
        self,
        strategy: AuthStrategyType,
        form_config: dict[str, Any],
        hnap_config: dict[str, Any],
        url_token_config: dict[str, Any],
    ):
        """Create typed AuthConfig from dict configs.

        Args:
            strategy: The auth strategy type
            form_config: Form configuration dict
            hnap_config: HNAP configuration dict
            url_token_config: URL token configuration dict

        Returns:
            Typed AuthConfig object appropriate for the strategy
        """
        from .configs import (
            BasicAuthConfig,
            FormAjaxAuthConfig,
            FormAuthConfig,
            FormDynamicAuthConfig,
            HNAPAuthConfig,
            NoAuthConfig,
            UrlTokenSessionConfig,
        )

        if strategy == AuthStrategyType.NO_AUTH:
            return NoAuthConfig()

        if strategy == AuthStrategyType.BASIC_HTTP:
            return BasicAuthConfig()

        if strategy == AuthStrategyType.FORM_PLAIN:
            return FormAuthConfig(
                strategy=strategy,
                login_url=form_config.get("action", ""),
                username_field=form_config.get("username_field", "username"),
                password_field=form_config.get("password_field", "password"),
                method=form_config.get("method", "POST"),
                success_indicator=form_config.get("success_indicator"),
                hidden_fields=form_config.get("hidden_fields"),
                password_encoding=form_config.get("password_encoding", "plain"),
                credential_field=form_config.get("credential_field"),
                credential_format=form_config.get("credential_format"),
            )

        if strategy == AuthStrategyType.FORM_DYNAMIC:
            return FormDynamicAuthConfig(
                strategy=strategy,
                login_page=form_config.get("login_page", "/"),
                login_url=form_config.get("action", ""),
                form_selector=form_config.get("form_selector"),
                username_field=form_config.get("username_field", "username"),
                password_field=form_config.get("password_field", "password"),
                method=form_config.get("method", "POST"),
                success_indicator=form_config.get("success_indicator"),
                hidden_fields=form_config.get("hidden_fields"),
                password_encoding=form_config.get("password_encoding", "plain"),
            )

        if strategy == AuthStrategyType.FORM_AJAX:
            return FormAjaxAuthConfig(
                strategy=strategy,
                endpoint=form_config.get("endpoint", "/cgi-bin/adv_pwd_cgi"),
                nonce_field=form_config.get("nonce_field", "ar_nonce"),
                nonce_length=form_config.get("nonce_length", 8),
                arguments_field=form_config.get("arguments_field", "arguments"),
                credential_format=form_config.get("credential_format", "username={username}:password={password}"),
                success_prefix=form_config.get("success_prefix", "Url:"),
                error_prefix=form_config.get("error_prefix", "Error:"),
            )

        if strategy == AuthStrategyType.HNAP_SESSION:
            merged = {**DEFAULT_HNAP_CONFIG, **hnap_config}
            # Convert string to enum if needed
            hmac_algo = merged.get("hmac_algorithm")
            if isinstance(hmac_algo, str):
                hmac_algo = HMACAlgorithm(hmac_algo)
            return HNAPAuthConfig(
                strategy=strategy,
                endpoint=merged.get("endpoint", "/HNAP1/"),
                namespace=merged.get("namespace", "http://purenetworks.com/HNAP1/"),
                empty_action_value=merged.get("empty_action_value", ""),
                hmac_algorithm=hmac_algo,
            )

        if strategy == AuthStrategyType.URL_TOKEN_SESSION:
            merged = {**DEFAULT_URL_TOKEN_CONFIG, **url_token_config}
            return UrlTokenSessionConfig(
                strategy=strategy,
                login_page=merged.get("login_page", "/cmconnectionstatus.html"),
                data_page=merged.get("data_page", "/cmconnectionstatus.html"),
                login_prefix=merged.get("login_prefix", "login_"),
                token_prefix=merged.get("token_prefix", "ct_"),
                session_cookie_name=merged.get("session_cookie_name", "credential"),
                success_indicator=merged.get("success_indicator", "Downstream"),
            )

        # Default: return NoAuthConfig for unknown strategies
        return NoAuthConfig()

    def get_hnap_builder(self) -> HNAPJsonRequestBuilder | None:
        """Get the HNAP builder for data fetches after authentication.

        Returns the HNAPJsonRequestBuilder instance if HNAP auth was used,
        or None otherwise. The scraper can use this for HNAP data fetches.
        """
        return self._hnap_builder

    def get_session_token(self) -> str | None:
        """Get the session token for subsequent page fetches.

        For URL token auth, returns the token from the login response body.
        This token must be used for ?ct_<token> in subsequent requests.
        Note: This may differ from the cookie value on some firmware.

        Returns:
            Session token string, or None if not URL token auth or auth not done.
        """
        return self._session_token
