"""Auth manager factory.

Selects the correct auth manager class from modem config.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .base import BaseAuthManager
from .basic import BasicAuthManager
from .form import FormAuthManager
from .form_nonce import FormNonceAuthManager
from .form_pbkdf2 import FormPbkdf2AuthManager
from .hnap import HnapAuthManager
from .none import NoneAuthManager
from .url_token import UrlTokenAuthManager

if TYPE_CHECKING:
    from ..models.modem_config import ModemConfig

_logger = logging.getLogger(__name__)


def create_auth_manager(config: ModemConfig) -> BaseAuthManager:
    """Create the appropriate auth manager from modem config.

    Uses the ``auth.strategy`` discriminator to select the manager
    class. Session config is passed to strategies that need it
    (form, url_token, form_pbkdf2).

    Args:
        config: Validated ``ModemConfig`` instance.

    Returns:
        Auth manager ready for ``authenticate()``.
    """
    from ..models.modem_config.auth import (
        BasicAuth,
        FormAuth,
        FormNonceAuth,
        FormPbkdf2Auth,
        HnapAuth,
        NoneAuth,
        UrlTokenAuth,
    )

    auth = config.auth

    if auth is None or isinstance(auth, NoneAuth):
        return NoneAuthManager()

    if isinstance(auth, BasicAuth):
        return BasicAuthManager(auth)

    if isinstance(auth, FormAuth):
        return FormAuthManager(auth, config.session)

    if isinstance(auth, FormNonceAuth):
        return FormNonceAuthManager(auth)

    if isinstance(auth, UrlTokenAuth):
        return UrlTokenAuthManager(auth, config.session)

    if isinstance(auth, HnapAuth):
        return HnapAuthManager(auth)

    if isinstance(auth, FormPbkdf2Auth):
        return FormPbkdf2AuthManager(auth, config.session)

    _logger.warning(
        "Unknown auth strategy type: %s, using NoneAuthManager",
        type(auth).__name__,
    )
    return NoneAuthManager()
