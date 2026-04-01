"""Auth handler factory — dispatches on modem.yaml ``auth.strategy``.

Contains the ``create_auth_handler`` public function and private
helpers for constructing specific handler types from config.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, NamedTuple

from .base import AuthHandler
from .basic import BasicAuthHandler
from .form import FormAuthHandler
from .pbkdf2 import FormPbkdf2AuthHandler
from .sjcl import FormSjclAuthHandler

if TYPE_CHECKING:
    from ...models.modem_config import ModemConfig

_logger = logging.getLogger(__name__)


class _ActionConfig(NamedTuple):
    """Shared action fields extracted from modem config.

    Simple data carrier for the cookie name, logout path, restart
    path, and restart method that both form-based factory functions
    need.
    """

    cookie_name: str
    logout_path: str
    restart_path: str
    restart_method: str


def _extract_action_config(modem_config: ModemConfig) -> _ActionConfig:
    """Extract shared action fields from modem config.

    Reads session cookie name and action endpoints (logout, restart)
    from the config. Used by both ``_create_form_auth_handler`` and
    ``_create_form_sjcl_auth_handler`` to avoid duplicating the same
    extraction logic.
    """
    from ...models.modem_config.actions import HttpAction

    cookie_name = getattr(modem_config.auth, "cookie_name", "")
    logout_path = ""
    restart_path = ""
    restart_method = "POST"
    if modem_config.actions:
        if modem_config.actions.logout and isinstance(modem_config.actions.logout, HttpAction):
            logout_path = modem_config.actions.logout.endpoint
        if modem_config.actions.restart and isinstance(modem_config.actions.restart, HttpAction):
            restart_path = modem_config.actions.restart.endpoint
            restart_method = modem_config.actions.restart.method
    return _ActionConfig(
        cookie_name=cookie_name,
        logout_path=logout_path,
        restart_path=restart_path,
        restart_method=restart_method,
    )


def _create_form_auth_handler(modem_config: ModemConfig) -> FormAuthHandler:
    """Build a FormAuthHandler from modem config.

    Extracts login path, session cookie, logout endpoint, and restart
    endpoint from the config. Called by ``create_auth_handler`` for
    form-based auth strategies.
    """
    auth = modem_config.auth
    login_path = getattr(auth, "action", "") or getattr(auth, "login_endpoint", "")
    action_cfg = _extract_action_config(modem_config)
    return FormAuthHandler(
        login_path=login_path,
        cookie_name=action_cfg.cookie_name,
        logout_path=action_cfg.logout_path,
        restart_path=action_cfg.restart_path,
        restart_method=action_cfg.restart_method,
    )


def _create_form_sjcl_auth_handler(modem_config: ModemConfig) -> FormSjclAuthHandler:
    """Build a FormSjclAuthHandler from modem config.

    Extracts SJCL crypto parameters, login endpoints, session cookie,
    and action endpoints from the config.
    """
    from ...models.modem_config.auth import FormSjclAuth

    auth = modem_config.auth
    assert isinstance(auth, FormSjclAuth)

    action_cfg = _extract_action_config(modem_config)
    return FormSjclAuthHandler(
        login_page_path=auth.login_page,
        login_endpoint=auth.login_endpoint,
        pbkdf2_iterations=auth.pbkdf2_iterations,
        pbkdf2_key_length=auth.pbkdf2_key_length,
        ccm_tag_length=auth.ccm_tag_length,
        decrypt_aad=auth.decrypt_aad,
        csrf_header=auth.csrf_header,
        cookie_name=action_cfg.cookie_name,
        logout_path=action_cfg.logout_path,
        restart_path=action_cfg.restart_path,
        restart_method=action_cfg.restart_method,
    )


def _create_form_pbkdf2_auth_handler(modem_config: ModemConfig) -> FormPbkdf2AuthHandler:
    """Build a FormPbkdf2AuthHandler from modem config.

    Extracts PBKDF2 parameters, salt trigger, login endpoint, CSRF
    config, session cookie, and action endpoints from the config.
    """
    from ...models.modem_config.auth import FormPbkdf2Auth

    auth = modem_config.auth
    assert isinstance(auth, FormPbkdf2Auth)

    action_cfg = _extract_action_config(modem_config)
    return FormPbkdf2AuthHandler(
        login_endpoint=auth.login_endpoint,
        salt_trigger=auth.salt_trigger,
        pbkdf2_iterations=auth.pbkdf2_iterations,
        pbkdf2_key_length=auth.pbkdf2_key_length,
        double_hash=auth.double_hash,
        csrf_init_endpoint=auth.csrf_init_endpoint,
        csrf_header=auth.csrf_header,
        cookie_name=action_cfg.cookie_name,
        logout_path=action_cfg.logout_path,
        restart_path=action_cfg.restart_path,
        restart_method=action_cfg.restart_method,
    )


def create_auth_handler(
    modem_config: ModemConfig | None,
    har_entries: list[dict[str, Any]] | None = None,
) -> AuthHandler:
    """Create the appropriate auth handler from modem config.

    Args:
        modem_config: Validated ``ModemConfig`` instance (or None for no auth).
            Uses ``auth.strategy`` to select the handler and
            ``auth.cookie_name`` for session tracking.
        har_entries: HAR ``log.entries`` list. Required for HNAP auth
            to build the merged data response. Ignored for other
            strategies.

    Returns:
        Auth handler instance.
    """
    from ...models.modem_config.auth import (
        BasicAuth,
        FormAuth,
        FormNonceAuth,
        FormPbkdf2Auth,
        FormSjclAuth,
        HnapAuth,
        NoneAuth,
        UrlTokenAuth,
    )

    if modem_config is None or modem_config.auth is None:
        return AuthHandler()

    auth = modem_config.auth

    if isinstance(auth, NoneAuth):
        return AuthHandler()

    if isinstance(auth, BasicAuth):
        return BasicAuthHandler()

    if isinstance(auth, FormAuth | FormNonceAuth):
        return _create_form_auth_handler(modem_config)

    if isinstance(auth, FormPbkdf2Auth):
        return _create_form_pbkdf2_auth_handler(modem_config)

    if isinstance(auth, FormSjclAuth):
        return _create_form_sjcl_auth_handler(modem_config)

    if isinstance(auth, UrlTokenAuth):
        # URL token auth GETs the login page with credentials in the URL.
        # The HAR route table already contains the login page response
        # (with success indicator text and Set-Cookie header), so no
        # auth gating is needed — all requests pass through.
        return AuthHandler()

    if isinstance(auth, HnapAuth):
        from .hnap import HnapAuthHandler

        return HnapAuthHandler(
            hmac_algorithm=auth.hmac_algorithm,
            har_entries=har_entries or [],
        )

    _logger.warning("Unsupported auth strategy '%s' in mock server, using no-auth", type(auth).__name__)
    return AuthHandler()
