"""Tests for create_auth_manager factory."""

from __future__ import annotations

from pathlib import Path

import pytest
from solentlabs.cable_modem_monitor_core.auth import (
    BasicAuthManager,
    FormAuthManager,
    FormNonceAuthManager,
    FormPbkdf2AuthManager,
    HnapAuthManager,
    NoneAuthManager,
    UrlTokenAuthManager,
    create_auth_manager,
)
from solentlabs.cable_modem_monitor_core.auth.form_sjcl import FormSjclAuthManager
from solentlabs.cable_modem_monitor_core.auth.json_sjcl import JsonSjclAuthManager
from solentlabs.cable_modem_monitor_core.models.modem_config import ModemConfig

from tests._helpers import load_fixture

FIXTURES_DIR = Path(__file__).parent.parent / "models" / "fixtures" / "modem_config" / "valid"


# ┌──────────────────────┬──────────────────────────┐
# │ Fixture              │ Expected manager type    │
# ├──────────────────────┼──────────────────────────┤
# │ auth_none.json       │ NoneAuthManager          │
# │ auth_basic.json      │ BasicAuthManager         │
# │ auth_form.json       │ FormAuthManager          │
# │ auth_form_nonce.json │ FormNonceAuthManager     │
# │ auth_url_token.json  │ UrlTokenAuthManager      │
# │ auth_hnap.json       │ HnapAuthManager          │
# │ auth_form_pbkdf2.json│ FormPbkdf2AuthManager    │
# │ auth_form_sjcl.json  │ FormSjclAuthManager      │
# │ auth_json_sjcl.json  │ JsonSjclAuthManager      │
# └──────────────────────┴──────────────────────────┘
#
# fmt: off
FACTORY_CASES = [
    ("auth_none.json",        NoneAuthManager),
    ("auth_basic.json",       BasicAuthManager),
    ("auth_form.json",        FormAuthManager),
    ("auth_form_nonce.json",  FormNonceAuthManager),
    ("auth_url_token.json",   UrlTokenAuthManager),
    ("auth_hnap.json",        HnapAuthManager),
    ("auth_form_pbkdf2.json", FormPbkdf2AuthManager),
    ("auth_form_sjcl.json",   FormSjclAuthManager),
    ("auth_json_sjcl.json",   JsonSjclAuthManager),
]
# fmt: on


@pytest.mark.parametrize(
    "fixture_name,expected_type",
    FACTORY_CASES,
    ids=[c[0].removesuffix(".json") for c in FACTORY_CASES],
)
def test_factory_selects_correct_manager(
    fixture_name: str,
    expected_type: type,
) -> None:
    """Factory returns the correct manager type for each auth strategy."""
    fixture_path = FIXTURES_DIR / fixture_name
    data = load_fixture(fixture_path)
    config = ModemConfig.model_validate(data)
    manager = create_auth_manager(config)
    assert isinstance(manager, expected_type)


def test_factory_none_auth_when_auth_missing() -> None:
    """Factory returns NoneAuthManager when auth is None."""
    data = {
        "manufacturer": "Acme",
        "model": "T100",
        "transport": "http",
        "default_host": "192.168.100.1",
        "status": "unsupported",
    }
    config = ModemConfig.model_validate(data)
    manager = create_auth_manager(config)
    assert isinstance(manager, NoneAuthManager)


def test_factory_hands_session_query_params_to_the_manager() -> None:
    """The login requests of strategies that use them carry the session's query params (TG3442DE ``_n``)."""
    data = load_fixture(FIXTURES_DIR / "auth_form_sjcl.json")
    data["session"] = {**data.get("session", {}), "query_params": {"_n": "12345"}}
    manager = create_auth_manager(ModemConfig.model_validate(data))
    assert manager.login_query_params == {"_n": "12345"}


def test_factory_leaves_login_query_params_empty_without_session_params() -> None:
    """No session query params, no login query params."""
    manager = create_auth_manager(ModemConfig.model_validate(load_fixture(FIXTURES_DIR / "auth_form_sjcl.json")))
    assert manager.login_query_params == {}
