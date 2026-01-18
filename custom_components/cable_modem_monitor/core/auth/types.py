"""Authentication strategy type enumeration."""

from __future__ import annotations

from enum import Enum


class HMACAlgorithm(str, Enum):
    """HMAC algorithm for HNAP authentication.

    Different modem firmwares use different HMAC algorithms for
    challenge-response authentication. The specific algorithm is
    declared in each modem's modem.yaml configuration.
    """

    MD5 = "md5"
    """HMAC-MD5: Most common algorithm for HNAP modems."""

    SHA256 = "sha256"
    """HMAC-SHA256: Used by newer firmware variants."""


class AuthErrorType(Enum):
    """Classification of authentication errors.

    Used to provide specific feedback to users about why auth failed.
    """

    NONE = "none"
    """No error - authentication succeeded."""

    MISSING_CREDENTIALS = "missing_credentials"
    """Username or password not provided."""

    INVALID_CREDENTIALS = "invalid_credentials"
    """Credentials rejected by modem (wrong username/password)."""

    SESSION_EXPIRED = "session_expired"
    """Session timed out mid-request (need to re-authenticate)."""

    CONNECTION_FAILED = "connection_failed"
    """Could not connect to modem (network issue)."""

    STRATEGY_NOT_CONFIGURED = "strategy_not_configured"
    """Auth strategy requires config that wasn't provided (e.g., form_config)."""

    UNKNOWN_ERROR = "unknown_error"
    """Unexpected error during authentication."""


class AuthStrategyType(Enum):
    """Enumeration of supported authentication strategies."""

    NO_AUTH = "no_auth"
    """No authentication required."""

    BASIC_HTTP = "basic_http"
    """HTTP Basic Authentication (RFC 7617)."""

    FORM_PLAIN = "form_plain"
    """Form-based auth. Encoding controlled by FormAuthConfig.password_encoding."""

    REDIRECT_FORM = "redirect_form"
    """Form-based auth with redirect validation."""

    HNAP_SESSION = "hnap_session"
    """HNAP JSON authentication with HMAC challenge-response."""

    HNAP_SOAP = "hnap_soap"
    """HNAP XML/SOAP authentication (legacy/older firmwares)."""

    URL_TOKEN_SESSION = "url_token_session"
    """URL-based token auth with session cookie (e.g., ARRIS SB8200 HTTPS variant)."""

    UNKNOWN = "unknown"
    """Unrecognized auth pattern - captured for debugging and future implementation."""
