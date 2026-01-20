"""Authentication configuration dataclasses.

Each auth strategy has a corresponding config dataclass that holds the
parameters needed for that strategy. These configs are:

1. Discovered during setup (by AuthDiscovery)
2. Stored in the config entry
3. Used by AuthHandler at runtime

See README.md in this directory for architecture details.
"""

from __future__ import annotations

from dataclasses import dataclass

from .types import AuthStrategyType


@dataclass
class AuthConfig:
    """Base dataclass for authentication configurations.

    Subclasses define strategy-specific fields. All configs have a strategy
    field that identifies which AuthStrategy implementation to use.
    """

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
    """Form-based authentication configuration.

    Supports two modes:
    1. Traditional: Separate username_field and password_field
    2. Combined: Single credential_field with formatted value (e.g., SB6190)

    For combined mode, set credential_field and credential_format.
    For traditional mode, use username_field and password_field.
    """

    strategy: AuthStrategyType
    login_url: str  # Form action URL (relative to base_url)
    username_field: str = "username"
    password_field: str = "password"
    method: str = "POST"  # HTTP method for form submission
    success_indicator: str | None = None  # URL fragment or min response size
    hidden_fields: dict[str, str] | None = None  # Additional hidden form fields

    # Password encoding (plain, base64)
    password_encoding: str = "plain"

    # Combined credential mode (SB6190-style)
    credential_field: str | None = None  # Field name for combined credentials
    credential_format: str | None = None  # Format string, e.g., "{username}:{password}"


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
    """HNAP JSON authentication configuration (MB8611, S33).

    Uses HMAC-MD5 challenge-response authentication protocol.
    The HNAPJsonRequestBuilder is used internally for the authentication flow.
    """

    strategy: AuthStrategyType = AuthStrategyType.HNAP_SESSION
    endpoint: str = "/HNAP1/"
    namespace: str = "http://purenetworks.com/HNAP1/"
    # Modem firmware bug: S33 expects "" for empty action, MB8611 expects {}.
    # Both should accept {} per HNAP spec, but S33 firmware rejects it.
    empty_action_value: str | dict = ""


@dataclass
class HNAPSoapAuthConfig(AuthConfig):
    """HNAP XML/SOAP session authentication configuration (legacy modems).

    Uses simple XML/SOAP envelope for authentication.
    """

    strategy: AuthStrategyType = AuthStrategyType.HNAP_SOAP
    login_url: str = "/Login.html"
    hnap_endpoint: str = "/HNAP1/"
    session_timeout_indicator: str = "UN-AUTH"
    soap_action_namespace: str = "http://purenetworks.com/HNAP1/"


@dataclass
class UrlTokenSessionConfig(AuthConfig):
    """URL-based token auth with session cookie (e.g., ARRIS SB8200 HTTPS).

    Auth flow:
    1. Login: GET {base_url}{login_page}?{login_prefix}{base64(user:pass)}
       with Authorization: Basic {base64(user:pass)} header
    2. Response sets {session_cookie_name} cookie
    3. Subsequent requests: GET {url}?{token_prefix}{session_cookie_value}
    """

    strategy: AuthStrategyType = AuthStrategyType.URL_TOKEN_SESSION
    login_page: str = "/cmconnectionstatus.html"
    data_page: str = "/cmconnectionstatus.html"
    login_prefix: str = "login_"
    token_prefix: str = "ct_"
    session_cookie_name: str = "sessionId"
    success_indicator: str = "Downstream Bonded Channels"
