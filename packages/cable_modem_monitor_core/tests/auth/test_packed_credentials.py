"""Tests for packed_credential_fields."""

from __future__ import annotations

import pytest
from solentlabs.cable_modem_monitor_core.auth.packed_credentials import packed_credential_fields

_PACKED = (
    '<form action="basic_pwd_cgi"><input id="user"><input id="pwd" type="password">'
    '<input name="arguments" value="" type="hidden"><input name="ar_nonce" value="" type="hidden"></form>'
)

# ┌──────────────────────────────────┬────────────┬──────────────────────────┐
# │ login page                       │ nonce      │ candidates               │
# ├──────────────────────────────────┼────────────┼──────────────────────────┤
# │ packed form, nonce known         │ ar_nonce   │ arguments                │
# │ packed form, nonce unknown       │ ""         │ arguments, ar_nonce      │
# │ named username input             │ ar_nonce   │ none (plain)             │
# │ hidden field with a value        │ ar_nonce   │ none                     │
# │ no form                          │ ar_nonce   │ none                     │
# │ empty page                       │ ar_nonce   │ none                     │
# └──────────────────────────────────┴────────────┴──────────────────────────┘
CASES = [
    pytest.param(_PACKED, "ar_nonce", ["arguments"], id="packed_nonce_known"),
    pytest.param(_PACKED, "", ["arguments", "ar_nonce"], id="packed_nonce_unknown"),
    pytest.param(
        '<form><input name="username"><input name="arguments" value="" type="hidden"></form>',
        "ar_nonce",
        [],
        id="named_username_is_plain",
    ),
    pytest.param(
        '<form><input name="webToken" value="abc123" type="hidden"></form>',
        "ar_nonce",
        [],
        id="filled_hidden_field",
    ),
    pytest.param("<html><body>Login</body></html>", "ar_nonce", [], id="no_form"),
    pytest.param("", "ar_nonce", [], id="empty_page"),
]


@pytest.mark.parametrize("html,nonce_field,expected", CASES)
def test_packed_credential_fields(html: str, nonce_field: str, expected: list[str]) -> None:
    """Empty hidden fields of a form with no named username input, nonce excluded."""
    assert packed_credential_fields(html, "username", nonce_field) == expected
