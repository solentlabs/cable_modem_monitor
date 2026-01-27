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

from ...const import DEFAULT_TIMEOUT
from .types import AuthStrategyType, HMACAlgorithm


@dataclass(kw_only=True)
class AuthConfig:
    """Base dataclass for authentication configurations.

    Subclasses define strategy-specific fields. All configs have a strategy
    field that identifies which AuthStrategy implementation to use.

    Timeout uses DEFAULT_TIMEOUT from schema. Modems override in modem.yaml if needed.
    """

    strategy: AuthStrategyType
    timeout: int = DEFAULT_TIMEOUT


@dataclass(kw_only=True)
class NoAuthConfig(AuthConfig):
    """No authentication required."""

    strategy: AuthStrategyType = AuthStrategyType.NO_AUTH


@dataclass(kw_only=True)
class BasicAuthConfig(AuthConfig):
    """HTTP Basic Authentication configuration."""

    strategy: AuthStrategyType = AuthStrategyType.BASIC_HTTP


@dataclass(kw_only=True)
class FormAuthConfig(AuthConfig):
    """Form-based authentication configuration.

    Supports two modes:
    1. Traditional: Separate username_field and password_field
    2. Combined: Single credential_field with formatted value

    For combined mode, set credential_field and credential_format.
    For traditional mode, use username_field and password_field.
    """

    strategy: AuthStrategyType = AuthStrategyType.FORM_PLAIN
    login_url: str = ""  # Form action URL (relative to base_url)
    username_field: str = "username"
    password_field: str = "password"
    method: str = "POST"  # HTTP method for form submission
    success_redirect: str | None = None  # Expected URL path after successful login (e.g., "/at_a_glance.jst")
    success_indicator: str | None = None  # Content string or min response size (legacy, prefer success_redirect)
    hidden_fields: dict[str, str] | None = None  # Additional hidden form fields

    # Password encoding (plain, base64)
    password_encoding: str = "plain"

    # Combined credential mode
    credential_field: str | None = None  # Field name for combined credentials
    credential_format: str | None = None  # Format string, e.g., "{username}:{password}"


@dataclass(kw_only=True)
class FormDynamicAuthConfig(AuthConfig):
    """Form auth with dynamic action URL extracted from login page.

    Used when the login form's action attribute contains a dynamic parameter
    that changes per page load (e.g., /goform/Login?id=XXXXXXXXXX where the
    id value is regenerated on each page load).

    The strategy fetches the login page first, parses the <form> element,
    and extracts the actual action URL before submitting credentials.

    Extends AuthConfig directly (not FormAuthConfig) to avoid dataclass
    inheritance issues with required vs optional fields.
    """

    strategy: AuthStrategyType = AuthStrategyType.FORM_DYNAMIC

    # Page containing the login form to scrape for dynamic action URL
    login_page: str = "/"

    # Fallback form action URL if extraction fails
    login_url: str = "/login"

    # CSS selector for form element (e.g., "form[name='loginform']")
    # If None, uses the first <form> element found
    form_selector: str | None = None

    # Form field configuration (same as FormAuthConfig)
    username_field: str = "username"
    password_field: str = "password"
    method: str = "POST"
    success_redirect: str | None = None  # Expected URL path after successful login
    success_indicator: str | None = None  # Content string or min response size (legacy)
    hidden_fields: dict[str, str] | None = None
    password_encoding: str = "plain"

    # Combined credential mode - unlikely for dynamic forms but included for completeness
    credential_field: str | None = None
    credential_format: str | None = None


@dataclass(kw_only=True)
class FormAjaxAuthConfig(AuthConfig):
    """AJAX-based form auth with client-generated nonce.

    Auth flow:
    1. POST to endpoint with:
       - arguments: base64(urlencode("username={user}:password={pass}"))
       - ar_nonce: random digits (client-generated)
    2. Response is plain text:
       - "Url:/path" = success, redirect to path
       - "Error:message" = failure
    """

    strategy: AuthStrategyType = AuthStrategyType.FORM_AJAX
    endpoint: str = "/cgi-bin/adv_pwd_cgi"  # AJAX endpoint for credentials
    nonce_field: str = "ar_nonce"  # Field name for client-generated nonce
    nonce_length: int = 8  # Length of random nonce
    arguments_field: str = "arguments"  # Field name for encoded credentials
    credential_format: str = "username={username}:password={password}"
    success_prefix: str = "Url:"  # Response prefix indicating success
    error_prefix: str = "Error:"  # Response prefix indicating failure


@dataclass(kw_only=True)
class RedirectFormAuthConfig(AuthConfig):
    """Form auth with redirect validation configuration (e.g., XB7)."""

    strategy: AuthStrategyType = AuthStrategyType.REDIRECT_FORM
    login_url: str = "/check.jst"
    username_field: str = "username"
    password_field: str = "password"
    success_redirect_pattern: str = "/at_a_glance.jst"
    authenticated_page_url: str = "/network_setup.jst"


@dataclass(kw_only=True)
class HNAPAuthConfig(AuthConfig):
    """HNAP JSON authentication configuration.

    Uses HMAC challenge-response authentication protocol.
    The HNAPJsonRequestBuilder is used internally for the authentication flow.
    """

    strategy: AuthStrategyType = AuthStrategyType.HNAP_SESSION
    endpoint: str = "/HNAP1/"
    namespace: str = "http://purenetworks.com/HNAP1/"
    # Some firmware variants expect "" for empty action, others expect {}.
    # Default to "" as it works with most modems observed in HAR captures.
    empty_action_value: str | dict = ""
    # HMAC algorithm - required, specified in each modem's modem.yaml
    # None sentinel triggers validation error if not overridden
    hmac_algorithm: HMACAlgorithm | None = None

    def __post_init__(self) -> None:
        """Validate required fields."""
        if self.hmac_algorithm is None:
            raise ValueError("hmac_algorithm is required for HNAPAuthConfig")


@dataclass(kw_only=True)
class HNAPSoapAuthConfig(AuthConfig):
    """HNAP XML/SOAP session authentication configuration (legacy modems).

    Uses simple XML/SOAP envelope for authentication.
    """

    strategy: AuthStrategyType = AuthStrategyType.HNAP_SOAP
    login_url: str = "/Login.html"
    hnap_endpoint: str = "/HNAP1/"
    session_timeout_indicator: str = "UN-AUTH"
    soap_action_namespace: str = "http://purenetworks.com/HNAP1/"


@dataclass(kw_only=True)
class UrlTokenSessionConfig(AuthConfig):
    """URL-based token auth with session cookie.

    Auth flow:
    1. Login: GET {base_url}{login_page}?{login_prefix}{base64(user:pass)}
       with Authorization: Basic {base64(user:pass)} header
       (optionally with X-Requested-With: XMLHttpRequest if ajax_login=True)
    2. Response sets {session_cookie_name} cookie
    3. Subsequent requests: GET {url}?{token_prefix}{session_cookie_value}
       (Authorization header included only if auth_header_data=True)

    Behavioral attributes (configured via modem.yaml):
        ajax_login: If True, add X-Requested-With: XMLHttpRequest to login request.
            Some modems (jQuery-based auth) require this header. Default: False.
        auth_header_data: If True, include Authorization header on data requests.
            Most modems only need the session cookie. Default: True (backwards compat).
    """

    strategy: AuthStrategyType = AuthStrategyType.URL_TOKEN_SESSION
    login_page: str = "/cmconnectionstatus.html"
    data_page: str = "/cmconnectionstatus.html"
    login_prefix: str = "login_"
    token_prefix: str = "ct_"
    session_cookie_name: str = "sessionId"
    success_indicator: str = "Downstream Bonded Channels"
    # Behavioral attributes - control header behavior based on modem requirements
    ajax_login: bool = False  # Add X-Requested-With: XMLHttpRequest to login
    auth_header_data: bool = True  # Include Authorization header on data requests
