"""Mock handlers for MockModemServer.

Each handler implements a specific authentication strategy.
"""

from .base import BaseAuthHandler
from .form import FormAuthHandler
from .form_ajax import FormAjaxAuthHandler
from .form_dynamic import FormDynamicAuthHandler
from .hnap import HnapAuthHandler
from .rest_api import RestApiHandler
from .url_token import UrlTokenAuthHandler

__all__ = [
    "BaseAuthHandler",
    "FormAjaxAuthHandler",
    "FormAuthHandler",
    "FormDynamicAuthHandler",
    "HnapAuthHandler",
    "RestApiHandler",
    "UrlTokenAuthHandler",
]
