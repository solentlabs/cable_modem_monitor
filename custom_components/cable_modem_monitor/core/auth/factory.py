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
