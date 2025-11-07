"""Authentication configuration dataclasses."""
from dataclasses import dataclass
from typing import Optional
from abc import ABC
from .authentication import AuthStrategyType


@dataclass
class AuthConfig(ABC):
    """Base class for authentication configurations."""
    strategy: AuthStrategyType


@dataclass
class NoAuthConfig(AuthConfig):
    """No authentication required."""
    strategy: AuthStrategyType = AuthStrategyType.NO_AUTH


@dataclass
class BasicAuthConfig(AuthConfig):
    """HTTP Basic Authentication configuration."""
    strategy: AuthStrategyType = AuthStrategyType.BASIC_HTTP


@dataclass
class FormAuthConfig(AuthConfig):
    """Form-based authentication configuration."""
    strategy: AuthStrategyType
    login_url: str
    username_field: str
    password_field: str
    success_indicator: Optional[str] = None  # URL fragment or min response size


@dataclass
class RedirectFormAuthConfig(AuthConfig):
    """Form auth with redirect validation configuration (e.g., XB7)."""
    strategy: AuthStrategyType = AuthStrategyType.REDIRECT_FORM
    login_url: str = "/check.jst"
    username_field: str = "username"
    password_field: str = "password"
    success_redirect_pattern: str = "/at_a_glance.jst"
    authenticated_page_url: str = "/network_setup.jst"


@dataclass
class HNAPAuthConfig(AuthConfig):
    """HNAP/SOAP session authentication configuration (e.g., MB8611)."""
    strategy: AuthStrategyType = AuthStrategyType.HNAP_SESSION
    login_url: str = "/Login.html"
    hnap_endpoint: str = "/HNAP1/"
    session_timeout_indicator: str = "UN-AUTH"
    soap_action_namespace: str = "http://purenetworks.com/HNAP1/"
