"""Client-side auth managers for modem web interfaces.

Factory-driven: ``create_auth_manager(config)`` selects the right
strategy from modem.yaml. Each manager authenticates on a
``requests.Session`` that the resource loader then uses.

See MODEM_YAML_SPEC.md Auth section.
"""

from __future__ import annotations

from .base import AuthContext, AuthResult, BaseAuthManager
from .basic import BasicAuthManager
from .factory import create_auth_manager
from .form import FormAuthManager
from .form_nonce import FormNonceAuthManager
from .form_pbkdf2 import FormPbkdf2AuthManager
from .hnap import HnapAuthManager
from .none import NoneAuthManager
from .url_token import UrlTokenAuthManager

__all__ = [
    "AuthContext",
    "AuthResult",
    "BaseAuthManager",
    "BasicAuthManager",
    "FormAuthManager",
    "FormNonceAuthManager",
    "FormPbkdf2AuthManager",
    "HnapAuthManager",
    "NoneAuthManager",
    "UrlTokenAuthManager",
    "create_auth_manager",
]
