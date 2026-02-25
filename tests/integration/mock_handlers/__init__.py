"""Mock handlers for MockModemServer.

Each handler implements a specific authentication strategy.
"""

from .base import BaseAuthHandler
from .form import FormAuthHandler
from .form_ajax import FormAjaxAuthHandler
from .form_dynamic import FormDynamicAuthHandler
from .form_nonce import FormNonceAuthHandler
from .hnap import HnapAuthHandler
from .rest_api import RestApiHandler
from .url_token import UrlTokenAuthHandler

__all__ = [
    "BaseAuthHandler",
    "FormAjaxAuthHandler",
    "FormAuthHandler",
    "FormDynamicAuthHandler",
    "FormNonceAuthHandler",
    "HnapAuthHandler",
    "RestApiHandler",
    "UrlTokenAuthHandler",
]
