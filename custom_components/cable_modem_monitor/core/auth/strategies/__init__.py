"""Authentication strategy implementations.

This package provides concrete implementations of the AuthStrategy ABC,
each handling a specific authentication mechanism used by cable modems.

Available Strategies:
    NoAuthStrategy
        For modems with no authentication (all pages public).
        Used by: Older firmware versions, basic modems

    BasicHttpAuthStrategy
        HTTP Basic Auth (401 challenge with WWW-Authenticate header).
        Used by: Some enterprise/commercial modems

    FormPlainAuthStrategy
        HTML form-based login with plain or base64-encoded credentials.
        Used by: Most traditional modem web interfaces

    FormDynamicAuthStrategy
        Form auth where action URL is extracted from the login page.
        Used when form action contains dynamic parameters (e.g., session IDs).

    HNAPSessionAuthStrategy
        HNAP/SOAP protocol authentication (XML format).
        Used by: Some ARRIS modems with HNAP

    HNAPJsonAuthStrategy
        HNAP protocol with JSON format responses.
        Used by: HNAP modems with JSON responses

    UrlTokenSessionStrategy
        URL-based token authentication (tokens in URL path).
        Used by: HTTPS modems with URL token auth

    RedirectFormAuthStrategy
        Form auth with redirect-based session establishment.
        Used by: Some Netgear modems

Strategy Selection:
    AuthDiscovery.discover() detects the appropriate strategy by:
    1. Checking HTTP response codes (401 → Basic)
    2. Inspecting HTML for form elements (→ FormPlain)
    3. Checking for HNAP endpoints (→ HNAP)
    4. Reading modem.yaml hints

Usage:
    Strategies are typically instantiated via AuthFactory, not directly:

    from custom_components.cable_modem_monitor.core.auth import (
        AuthFactory, AuthStrategyType
    )
    strategy = AuthFactory.create(AuthStrategyType.FORM_PLAIN)
"""

from __future__ import annotations

from .basic_http import BasicHttpAuthStrategy
from .form_ajax import FormAjaxAuthStrategy
from .form_dynamic import FormDynamicAuthStrategy
from .form_plain import FormPlainAuthStrategy
from .hnap_json import HNAPJsonAuthStrategy
from .hnap_session import HNAPSessionAuthStrategy
from .no_auth import NoAuthStrategy
from .redirect_form import RedirectFormAuthStrategy
from .url_token_session import UrlTokenSessionStrategy

__all__ = [
    "BasicHttpAuthStrategy",
    "FormAjaxAuthStrategy",
    "FormDynamicAuthStrategy",
    "FormPlainAuthStrategy",
    "HNAPJsonAuthStrategy",
    "HNAPSessionAuthStrategy",
    "NoAuthStrategy",
    "RedirectFormAuthStrategy",
    "UrlTokenSessionStrategy",
]
