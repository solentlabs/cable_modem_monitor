"""Tests for create_auth_manager factory."""

from __future__ import annotations

import json
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
from solentlabs.cable_modem_monitor_core.models.modem_config import ModemConfig

FIXTURES_DIR = Path(__file__).parent.parent / "models" / "fixtures" / "modem_config" / "valid"


# ┌─────────────────────┬──────────────────────────┐
# │ Fixture             │ Expected manager type    │
# ├─────────────────────┼──────────────────────────┤
# │ auth_none.json      │ NoneAuthManager          │
# │ auth_basic.json     │ BasicAuthManager         │
# │ auth_form.json      │ FormAuthManager          │
# │ auth_form_nonce.json│ FormNonceAuthManager     │
# │ auth_url_token.json │ UrlTokenAuthManager      │
# │ auth_hnap.json      │ HnapAuthManager          │
# │ auth_form_pbkdf2.json│ FormPbkdf2AuthManager   │
# └─────────────────────┴──────────────────────────┘
#
# fmt: off
FACTORY_CASES = [
    ("auth_none.json",       NoneAuthManager),
    ("auth_basic.json",      BasicAuthManager),
    ("auth_form.json",       FormAuthManager),
    ("auth_form_nonce.json", FormNonceAuthManager),
    ("auth_url_token.json",  UrlTokenAuthManager),
    ("auth_hnap.json",       HnapAuthManager),
    ("auth_form_pbkdf2.json", FormPbkdf2AuthManager),
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
    data = json.loads(fixture_path.read_text())
    config = ModemConfig(**data)
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
    config = ModemConfig(**data)
    manager = create_auth_manager(config)
    assert isinstance(manager, NoneAuthManager)
