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
        Used by: MB7621, CM2000, C3700, C7000v2, CGA2121, XB7

    HNAPSessionAuthStrategy
        HNAP/SOAP protocol authentication (XML format).
        Used by: Arris S33

    HNAPJsonAuthStrategy
        HNAP protocol with JSON format responses.
        Used by: Motorola MB8611

    UrlTokenSessionStrategy
        URL-based token authentication (tokens in URL path).
        Used by: Arris SB8200 (HTTPS mode)

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
from .form_plain import FormPlainAuthStrategy
from .hnap_json import HNAPJsonAuthStrategy
from .hnap_session import HNAPSessionAuthStrategy
from .no_auth import NoAuthStrategy
from .redirect_form import RedirectFormAuthStrategy
from .url_token_session import UrlTokenSessionStrategy

__all__ = [
    "BasicHttpAuthStrategy",
    "FormPlainAuthStrategy",
    "HNAPJsonAuthStrategy",
    "HNAPSessionAuthStrategy",
    "NoAuthStrategy",
    "RedirectFormAuthStrategy",
    "UrlTokenSessionStrategy",
]
