"""Authentication configuration dataclasses."""
from dataclasses import dataclass
from typing import Optional
from abc import ABC
from enum import Enum


class AuthStrategyType(Enum):
    """Enumeration of supported authentication strategies."""

    NO_AUTH = "no_auth"
    """No authentication required."""

    BASIC_HTTP = "basic_http"
    """HTTP Basic Authentication (RFC 7617)."""

    FORM_PLAIN = "form_plain"
    """Form-based auth with plain password."""

    FORM_BASE64 = "form_base64"
    """Form-based auth with base64-encoded password."""

    FORM_PLAIN_AND_BASE64 = "form_plain_and_base64"
    """Form-based auth with fallback."""

    REDIRECT_FORM = "redirect_form"
    """Form-based auth with redirect validation."""

    HNAP_SESSION = "hnap_session"
    """HNAP/SOAP session-based authentication."""


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
