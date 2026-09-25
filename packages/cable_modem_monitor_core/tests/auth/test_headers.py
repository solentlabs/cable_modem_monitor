"""Auth manager headers() — declared header names for failure-log redaction.

Each strategy declares which header names it puts on the wire so loader
diagnostics can redact those values in failure logs without leaking
session tokens. The default ``frozenset({"cookie"})`` covers any
cookie-based session; overrides extend it with strategy-specific names
(``HNAP_AUTH``, ``Authorization``, the configured CSRF header, etc.).

The contract is load-bearing for the redaction layer — if a strategy
forgets to declare its token-bearing header, that header's value
appears verbatim in production failure logs. This table-driven test
covers every concrete ``BaseAuthManager`` subclass.
"""

from __future__ import annotations

import pytest
from solentlabs.cable_modem_monitor_core.auth.base import BaseAuthManager
from solentlabs.cable_modem_monitor_core.auth.basic import BasicAuthManager
from solentlabs.cable_modem_monitor_core.auth.form import FormAuthManager
from solentlabs.cable_modem_monitor_core.auth.form_cbn import FormCbnAuthManager
from solentlabs.cable_modem_monitor_core.auth.form_nonce import FormNonceAuthManager
from solentlabs.cable_modem_monitor_core.auth.form_pbkdf2 import FormPbkdf2AuthManager
from solentlabs.cable_modem_monitor_core.auth.form_sjcl import FormSjclAuthManager
from solentlabs.cable_modem_monitor_core.auth.hnap import HnapAuthManager
from solentlabs.cable_modem_monitor_core.auth.json_sjcl import JsonSjclAuthManager
from solentlabs.cable_modem_monitor_core.auth.none import NoneAuthManager
from solentlabs.cable_modem_monitor_core.auth.url_token import UrlTokenAuthManager
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import (
    BasicAuth,
    FormAuth,
    FormCbnAuth,
    FormNonceAuth,
    FormPbkdf2Auth,
    FormSjclAuth,
    HnapAuth,
    JsonSjclAuth,
    UrlTokenAuth,
)


def _sjcl(csrf: str) -> FormSjclAuthManager:
    return FormSjclAuthManager(
        FormSjclAuth(
            strategy="form_sjcl",
            login_endpoint="/login",
            pbkdf2_iterations=1000,
            pbkdf2_key_length=128,
            csrf_header=csrf,
        )
    )


def _pbkdf2(csrf: str) -> FormPbkdf2AuthManager:
    return FormPbkdf2AuthManager(
        FormPbkdf2Auth(
            strategy="form_pbkdf2",
            login_endpoint="/login",
            pbkdf2_iterations=1000,
            pbkdf2_key_length=128,
            csrf_header=csrf,
        )
    )


# Each row: (manager instance, expected headers, description-id)
_CASES: list[tuple[BaseAuthManager, frozenset[str], str]] = [
    (NoneAuthManager(), frozenset({"cookie"}), "none — inherits default"),
    (FormAuthManager(FormAuth(strategy="form", action="/login")), frozenset({"cookie"}), "form — inherits default"),
    (
        FormNonceAuthManager(FormNonceAuth(strategy="form_nonce", action="/login", nonce_field="nonce")),
        frozenset({"cookie"}),
        "form_nonce — inherits default",
    ),
    (
        UrlTokenAuthManager(UrlTokenAuth(strategy="url_token", login_page="/")),
        frozenset({"cookie"}),
        "url_token — token in URL, no auth header",
    ),
    (
        FormCbnAuthManager(FormCbnAuth(strategy="form_cbn")),
        frozenset({"cookie"}),
        "form_cbn — cookie-based session",
    ),
    (
        BasicAuthManager(BasicAuth(strategy="basic")),
        frozenset({"cookie", "authorization"}),
        "basic — adds Authorization",
    ),
    (
        HnapAuthManager(HnapAuth(strategy="hnap", hmac_algorithm="md5")),
        frozenset({"cookie", "hnap_auth"}),
        "hnap — adds HNAP_AUTH",
    ),
    (_sjcl("csrfNonce"), frozenset({"cookie", "csrfnonce"}), "form_sjcl — adds configured csrf_header (lowercased)"),
    (_sjcl(""), frozenset({"cookie"}), "form_sjcl — no csrf_header configured"),
    (_pbkdf2("X-CSRF-Token"), frozenset({"cookie", "x-csrf-token"}), "form_pbkdf2 — adds configured csrf_header"),
    (_pbkdf2(""), frozenset({"cookie"}), "form_pbkdf2 — no csrf_header configured"),
    (
        JsonSjclAuthManager(
            JsonSjclAuth(
                strategy="json_sjcl",
                login_page="/login.php",
                login_endpoint="/login",
                pbkdf2_iterations=1000,
                pbkdf2_key_length=128,
                aad="AAD",
                token_header="X-Session-Token",
            )
        ),
        frozenset({"cookie", "x-session-token"}),
        "json_sjcl — adds configured token_header (lowercased)",
    ),
]


@pytest.mark.parametrize(
    "manager,expected,desc",
    _CASES,
    ids=[c[2] for c in _CASES],
)
def test_auth_manager_headers(manager: BaseAuthManager, expected: frozenset[str], desc: str) -> None:
    """Each strategy declares the lowercase header names it puts on the wire."""
    assert manager.headers() == expected
