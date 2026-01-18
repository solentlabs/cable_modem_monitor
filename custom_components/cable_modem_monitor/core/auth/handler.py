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

# Default URL token configuration (SB8200)
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
    - URL_TOKEN_SESSION: URL-based token auth (SB8200)
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
                Used for try-until-success pattern (e.g., SB6190 with firmware variations).
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

    @classmethod
    def from_modem_config(cls, config: Any) -> AuthHandler:
        """Create AuthHandler from a modem.yaml config.

        This is the Phase 7 integration point - creates AuthHandler directly
        from modem.yaml configuration instead of parser class attributes.

        Supports auth.strategies[] for try-until-success pattern.
        When strategies[] is defined, tries each in order until one succeeds.

        Args:
            config: ModemConfig from modem.yaml

        Returns:
            AuthHandler configured from modem.yaml
        """
        from custom_components.cable_modem_monitor.modem_config import (
            AuthStrategy,
            ModemConfigAuthAdapter,
        )

        adapter = ModemConfigAuthAdapter(config)

        # Map modem.yaml AuthStrategy to AuthStrategyType
        strategy_map = {
            AuthStrategy.NONE: AuthStrategyType.NO_AUTH,
            AuthStrategy.BASIC: AuthStrategyType.BASIC_HTTP,
            AuthStrategy.FORM: AuthStrategyType.FORM_PLAIN,  # Refined below
            AuthStrategy.HNAP: AuthStrategyType.HNAP_SESSION,
            AuthStrategy.URL_TOKEN: AuthStrategyType.URL_TOKEN_SESSION,
            AuthStrategy.REST_API: AuthStrategyType.NO_AUTH,  # REST API = no auth
        }

        # Check for auth.strategies[] (v3.12+ try-until-success pattern)
        if config.auth.strategies:
            return cls._from_strategies_list(config.auth.strategies, strategy_map)

        # Fall back to primary auth.strategy
        strategy = strategy_map.get(config.auth.strategy, AuthStrategyType.UNKNOWN)

        return cls(
            strategy=strategy,
            form_config=adapter.get_form_config() if config.auth.form else None,
            hnap_config=adapter.get_hnap_config() if config.auth.hnap else None,
            url_token_config=adapter.get_url_token_config() if config.auth.url_token else None,
        )

    @classmethod
    def _from_strategies_list(cls, strategies: list, strategy_map: dict) -> AuthHandler:
        """Create AuthHandler from auth.strategies[] list.

        Args:
            strategies: List of AuthStrategyEntry from modem.yaml
            strategy_map: Mapping from AuthStrategy enum to AuthStrategyType

        Returns:
            AuthHandler with primary strategy and fallbacks configured
        """
        if not strategies:
            return cls(strategy=AuthStrategyType.NO_AUTH)

        # Extract primary strategy configs
        primary = strategies[0]
        primary_strategy, primary_configs = cls._extract_strategy_config(primary, strategy_map)

        # Build fallback strategies (remaining entries)
        fallback_strategies = [cls._build_fallback_entry(entry, strategy_map) for entry in strategies[1:]]

        _LOGGER.debug(
            "Created AuthHandler with %d strategies (primary: %s, fallbacks: %d)",
            len(strategies),
            primary_strategy.value,
            len(fallback_strategies),
        )

        return cls(
            strategy=primary_strategy,
            form_config=primary_configs.get("form_config"),
            hnap_config=primary_configs.get("hnap_config"),
            url_token_config=primary_configs.get("url_token_config"),
            fallback_strategies=fallback_strategies,
        )

    @staticmethod
    def _extract_strategy_config(entry: Any, strategy_map: dict) -> tuple[AuthStrategyType, dict[str, Any]]:
        """Extract strategy type and configs from a strategy entry.

        Returns:
            Tuple of (AuthStrategyType, dict of config dicts)
        """
        from custom_components.cable_modem_monitor.modem_config.schema import AuthStrategy

        strategy = strategy_map.get(entry.strategy, AuthStrategyType.UNKNOWN)
        configs: dict[str, Any] = {}

        # Extract form config
        if entry.strategy == AuthStrategy.FORM and entry.form:
            configs["form_config"] = {
                "action": entry.form.action,
                "method": entry.form.method,
                "username_field": entry.form.username_field,
                "password_field": entry.form.password_field,
                "hidden_fields": dict(entry.form.hidden_fields) if entry.form.hidden_fields else {},
                "password_encoding": entry.form.password_encoding.value if entry.form.password_encoding else "plain",
            }

        # Extract HNAP config
        if entry.strategy == AuthStrategy.HNAP and entry.hnap:
            configs["hnap_config"] = {
                "endpoint": entry.hnap.endpoint,
                "namespace": entry.hnap.namespace,
                "empty_action_value": entry.hnap.empty_action_value,
            }

        # Extract URL token config
        if entry.strategy == AuthStrategy.URL_TOKEN and entry.url_token:
            configs["url_token_config"] = {
                "login_page": entry.url_token.login_page,
                "login_prefix": entry.url_token.login_prefix,
                "session_cookie_name": entry.url_token.session_cookie,
                "token_prefix": entry.url_token.token_prefix,
                "success_indicator": entry.url_token.success_indicator,
            }

        return strategy, configs

    @classmethod
    def _build_fallback_entry(cls, entry: Any, strategy_map: dict) -> dict[str, Any]:
        """Build a fallback strategy dict from a strategy entry."""
        strategy, configs = cls._extract_strategy_config(entry, strategy_map)
        fallback: dict[str, Any] = {"strategy": strategy.value}
        fallback.update(configs)
        return fallback

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
            FormAuthConfig,
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
