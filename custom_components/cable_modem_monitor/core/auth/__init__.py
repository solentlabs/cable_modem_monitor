"""Authentication module for cable modem monitor.

This module provides pluggable authentication strategies for various modem types,
as well as response-driven auth discovery for automatic strategy detection.

See README.md in this directory for detailed architecture documentation.

Usage:
    from custom_components.cable_modem_monitor.core.auth import (
        AuthFactory,
        AuthStrategyType,
        BasicAuthConfig,
        AuthDiscovery,
        DiscoveryResult,
    )

    # Discover auth strategy
    discovery = AuthDiscovery()
    result = discovery.discover(session, base_url, data_url, user, password, parser)
    if result.success:
        print(f"Detected: {result.strategy}")

    # Get a strategy by type
    strategy = AuthFactory.get_strategy(AuthStrategyType.BASIC_HTTP)

    # Use a config
    config = BasicAuthConfig()
"""

from __future__ import annotations

from .base import AuthResult, AuthStrategy
from .configs import (
    AuthConfig,
    BasicAuthConfig,
    FormAuthConfig,
    HNAPAuthConfig,
    HNAPSoapAuthConfig,
    NoAuthConfig,
    RedirectFormAuthConfig,
    UrlTokenSessionConfig,
)
from .discovery import AuthDiscovery, DiscoveredFormConfig, DiscoveryResult
from .factory import AuthFactory
from .handler import AuthHandler
from .hnap import HNAPJsonRequestBuilder, HNAPRequestBuilder
from .strategies import (
    BasicHttpAuthStrategy,
    FormPlainAuthStrategy,
    HNAPJsonAuthStrategy,
    HNAPSessionAuthStrategy,
    NoAuthStrategy,
    RedirectFormAuthStrategy,
    UrlTokenSessionStrategy,
)
from .types import AuthErrorType, AuthStrategyType
from .workflow import AUTH_TYPE_LABELS, AuthWorkflow, AuthWorkflowResult

__all__ = [
    # Base
    "AuthResult",
    "AuthStrategy",
    # Configs
    "AuthConfig",
    "BasicAuthConfig",
    "FormAuthConfig",
    "HNAPAuthConfig",
    "HNAPSoapAuthConfig",
    "NoAuthConfig",
    "RedirectFormAuthConfig",
    "UrlTokenSessionConfig",
    # Discovery
    "AuthDiscovery",
    "DiscoveredFormConfig",
    "DiscoveryResult",
    # Enums
    "AuthErrorType",
    "AuthStrategyType",
    # Factory
    "AuthFactory",
    # Handler
    "AuthHandler",
    # Workflow
    "AUTH_TYPE_LABELS",
    "AuthWorkflow",
    "AuthWorkflowResult",
    # Request Builders
    "HNAPJsonRequestBuilder",
    "HNAPRequestBuilder",
    # Strategies
    "BasicHttpAuthStrategy",
    "FormPlainAuthStrategy",
    "HNAPJsonAuthStrategy",
    "HNAPSessionAuthStrategy",
    "NoAuthStrategy",
    "RedirectFormAuthStrategy",
    "UrlTokenSessionStrategy",
]
