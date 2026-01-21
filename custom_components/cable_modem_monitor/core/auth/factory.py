"""Factory for creating authentication strategy instances."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .types import AuthStrategyType

if TYPE_CHECKING:
    from .base import AuthStrategy


class AuthFactory:
    """Factory for creating authentication strategy instances."""

    @classmethod
    def get_strategy(cls, strategy_type: AuthStrategyType) -> AuthStrategy:
        """Get authentication strategy instance by type.

        Args:
            strategy_type: AuthStrategyType enum value

        Returns:
            AuthStrategy instance

        Raises:
            ValueError: If strategy type is not supported
        """
        # Lazy imports to avoid circular dependencies
        from .strategies.basic_http import BasicHttpAuthStrategy
        from .strategies.form_plain import FormPlainAuthStrategy
        from .strategies.hnap_json import HNAPJsonAuthStrategy
        from .strategies.hnap_session import HNAPSessionAuthStrategy
        from .strategies.no_auth import NoAuthStrategy
        from .strategies.redirect_form import RedirectFormAuthStrategy
        from .strategies.url_token_session import UrlTokenSessionStrategy

        _strategies = {
            AuthStrategyType.NO_AUTH: NoAuthStrategy,
            AuthStrategyType.BASIC_HTTP: BasicHttpAuthStrategy,
            AuthStrategyType.FORM_PLAIN: FormPlainAuthStrategy,
            AuthStrategyType.REDIRECT_FORM: RedirectFormAuthStrategy,
            AuthStrategyType.HNAP_SESSION: HNAPJsonAuthStrategy,  # Default to JSON HNAP
            AuthStrategyType.HNAP_SOAP: HNAPSessionAuthStrategy,  # Legacy XML/SOAP HNAP
            AuthStrategyType.URL_TOKEN_SESSION: UrlTokenSessionStrategy,
        }

        if strategy_type not in _strategies:
            raise ValueError(f"Unsupported authentication strategy: {strategy_type}")

        strategy_class = _strategies[strategy_type]
        return strategy_class()  # type: ignore[abstract]

    @classmethod
    def get_strategy_by_name(cls, name: str) -> AuthStrategy:
        """Get authentication strategy by string name (backward compatibility).

        Args:
            name: Strategy name (e.g., "basic_http", "form_plain")

        Returns:
            AuthStrategy instance
        """
        try:
            strategy_type = AuthStrategyType(name)
            return cls.get_strategy(strategy_type)
        except ValueError:
            raise ValueError(f"Unknown authentication strategy name: {name}")

    @classmethod
    def create_from_modem_config(
        cls,
        auth_type: str,
        config: dict | None = None,
    ) -> AuthStrategy:
        """Create configured auth strategy from modem.yaml type and config.

        Maps user-facing auth types (from modem.yaml) to internal strategy types:
          "none"      -> AuthStrategyType.NO_AUTH
          "form"      -> AuthStrategyType.FORM_PLAIN
          "url_token" -> AuthStrategyType.URL_TOKEN_SESSION
          "hnap"      -> AuthStrategyType.HNAP_SESSION
          "basic"     -> AuthStrategyType.BASIC_HTTP

        Args:
            auth_type: User-facing auth type from modem.yaml (e.g., "form", "hnap")
            config: Configuration dict for the auth type (optional)

        Returns:
            Configured AuthStrategy instance

        Raises:
            ValueError: If auth_type is not supported
        """
        type_mapping = {
            "none": AuthStrategyType.NO_AUTH,
            "form": AuthStrategyType.FORM_PLAIN,
            "url_token": AuthStrategyType.URL_TOKEN_SESSION,
            "hnap": AuthStrategyType.HNAP_SESSION,
            "basic": AuthStrategyType.BASIC_HTTP,
        }

        strategy_type = type_mapping.get(auth_type)
        if strategy_type is None:
            raise ValueError(f"Unknown auth type: {auth_type}")

        return cls.get_strategy(strategy_type)
