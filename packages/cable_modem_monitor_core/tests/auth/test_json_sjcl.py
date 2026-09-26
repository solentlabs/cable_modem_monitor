"""Tests for the json_sjcl auth strategy (SJCL-encrypted JSON login).

Covers: the login flow table (success, HTTP refusals, missing page
variables, missing token header, the busy branch), the exact encrypted
request (compact plaintext, lowercased user, two-key body), the shared
envelope used by encrypted actions, and the session-key hygiene rules.

TEST DATA TABLES
================
Tables sit above the class that consumes them, with ASCII
box-drawing comments for readability.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests
from requests.structures import CaseInsensitiveDict
from solentlabs.cable_modem_monitor_core.auth.json_sjcl import JsonSjclAuthManager, encrypt_payload
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import JsonSjclAuth
from solentlabs.cable_modem_monitor_core.protocol import sjcl
from solentlabs.cable_modem_monitor_core.protocol.sjcl import SjclSession

_IP = "http://192.168.100.1"
_SALT = "1122334455667788"
_IV = "aabbccddeeff0011"
_AAD = "AAD"
_TOKEN_HEADER = "X-Session-Token"
_PASSWORD = "pw"
_KEY = sjcl.derive_key(_PASSWORD, _SALT, 1000, 128)
_BUSY = {"session_overtake": True}


def _config(**fields: Any) -> JsonSjclAuth:
    return JsonSjclAuth.model_validate(
        {
            "strategy": "json_sjcl",
            "login_page": "/login.php",
            "login_endpoint": "/actionHandler/login.php",
            "pbkdf2_iterations": 1000,
            "pbkdf2_key_length": 128,
            "aad": _AAD,
            "token_header": _TOKEN_HEADER,
            **fields,
        }
    )


def _page(salt: str = _SALT, iv: str = _IV) -> str:
    """Login page carrying the firmware's double-quoted sjclEncryptObj assignments."""
    # Data pages ship the same assignments empty; the first non-empty one wins.
    return (
        "<script>function addUserInfoToEncryptObj(user, password) {\n"
        f'  sjclEncryptObj.salt = "{salt}";\n'
        f'  sjclEncryptObj.iv = "{iv}";\n'
        "}</script>"
    )


def _encrypted(payload: dict[str, Any], key: bytes = _KEY) -> dict[str, str]:
    """Encrypted response body the firmware sends: {"EncryptedData": <hex>}."""
    return {"EncryptedData": sjcl.encrypt(key, _IV, json.dumps(payload), _AAD, 16)}


def _response(
    status_code: int,
    *,
    text: str = "",
    json_body: object | None = None,
    headers: dict[str, str] | None = None,
) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.headers = CaseInsensitiveDict(headers or {})
    if json_body is not None:
        resp.json.return_value = json_body
    else:
        resp.json.side_effect = ValueError("not json")
    return resp


def _session(page: MagicMock, login: MagicMock) -> MagicMock:
    session = MagicMock(spec=requests.Session)
    session.headers = {}
    session.get.return_value = page
    session.put.return_value = login
    session.post.return_value = login
    return session


_OK_PAGE = _response(200, text=_page())
_TOKEN = {_TOKEN_HEADER: "tok"}


# =============================================================================
# Login flow
# =============================================================================
#
# ┌───────────────────────────┬──────┬───────────────────────┬──────────┬───────┬──────┬────────────┐
# │ case                      │ page │ login body            │ token hdr│ busy  │ ok   │ attached   │
# ├───────────────────────────┼──────┼───────────────────────┼──────────┼───────┼──────┼────────────┤
# │ success                   │ ok   │ {}                    │ yes      │ -     │ yes  │ none       │
# │ login 471                 │ ok   │ "Parameter decr..."   │ no       │ -     │ no   │ login      │
# │ login 503                 │ ok   │ (none)                │ no       │ -     │ no   │ login      │
# │ page 503                  │ 503  │ -                     │ -        │ -     │ no   │ page       │
# │ page missing salt         │ salt=│ -                     │ -        │ -     │ no   │ page       │
# │ page missing iv           │ iv=  │ -                     │ -        │ -     │ no   │ page       │
# │ page iv wrong length      │ 2B iv│ -                     │ -        │ -     │ no   │ page       │
# │ page salt odd hex         │ abc  │ -                     │ -        │ -     │ no   │ page       │
# │ missing token header      │ ok   │ {}                    │ no       │ -     │ no   │ login      │
# │ busy declared, matching   │ ok   │ enc(overtake)         │ no       │ decl  │ busy │ login      │
# │ busy, body undecryptable  │ ok   │ enc under other key   │ yes      │ decl  │ yes  │ none       │
# │ busy, no EncryptedData    │ ok   │ {"ok": true}          │ yes      │ decl  │ yes  │ none       │
# │ busy, not matching        │ ok   │ enc({"x":1})          │ yes      │ decl  │ yes  │ none       │
# │ busy, body not JSON       │ ok   │ (not JSON)            │ yes      │ decl  │ yes  │ none       │
# │ busy undeclared           │ ok   │ enc(overtake)         │ yes      │ -     │ yes  │ none       │
# └───────────────────────────┴──────┴───────────────────────┴──────────┴───────┴──────┴────────────┘
#
# fmt: off
_BUSY_FIELDS: dict[str, Any] = {"login_busy": _BUSY}
_OTHER_KEY = sjcl.derive_key("other", _SALT, 1000, 128)
FLOW_CASES: list[tuple[str, MagicMock, MagicMock, dict[str, Any], bool, bool, str, str]] = [
    # (case, page, login, fields, success, busy, error fragment, attached: page|login|none)
    ("success",
     _OK_PAGE, _response(200, json_body={}, headers=_TOKEN), {}, True, False, "", "none"),
    ("login 471",
     _OK_PAGE, _response(471, json_body="Parameter decryption failed"), {}, False, False, "471", "login"),
    ("login 503",
     _OK_PAGE, _response(503), {}, False, False, "503", "login"),
    ("page 503",
     _response(503), _response(200), {}, False, False, "503", "page"),
    ("page missing salt",
     _response(200, text=_page(salt="")), _response(200), {}, False, False, "salt", "page"),
    ("page missing iv",
     _response(200, text=_page(iv="")), _response(200), {}, False, False, "iv", "page"),
    ("page iv wrong length",
     _response(200, text=_page(iv="aabb")), _response(200), {}, False, False, "bytes", "page"),
    ("page salt odd hex",
     _response(200, text=_page(salt="abc")), _response(200), {}, False, False, "salt", "page"),
    ("missing token header",
     _OK_PAGE, _response(200, json_body={}), {}, False, False, _TOKEN_HEADER, "login"),
    ("busy declared, matching",
     _OK_PAGE, _response(200, json_body=_encrypted(_BUSY)), _BUSY_FIELDS, False, True, "busy", "login"),
    ("busy declared, body undecryptable",
     _OK_PAGE, _response(200, json_body=_encrypted(_BUSY, _OTHER_KEY), headers=_TOKEN), _BUSY_FIELDS,
     True, False, "", "none"),
    ("busy declared, not matching",
     _OK_PAGE, _response(200, json_body=_encrypted({"x": 1}), headers=_TOKEN), _BUSY_FIELDS,
     True, False, "", "none"),
    ("busy declared, no EncryptedData",
     _OK_PAGE, _response(200, json_body={"ok": True}, headers=_TOKEN), _BUSY_FIELDS, True, False, "", "none"),
    ("busy declared, body not JSON",
     _OK_PAGE, _response(200, headers=_TOKEN), _BUSY_FIELDS, True, False, "", "none"),
    ("busy undeclared",
     _OK_PAGE, _response(200, json_body=_encrypted(_BUSY), headers=_TOKEN), {}, True, False, "", "none"),
]
# fmt: on


class TestJsonSjclLoginFlow:
    """One row per outcome of the six-step login."""

    @pytest.mark.parametrize(
        "case,page,login,fields,success,busy,fragment,attached",
        FLOW_CASES,
        ids=[c[0] for c in FLOW_CASES],
    )
    def test_login_flow(
        self,
        case: str,
        page: MagicMock,
        login: MagicMock,
        fields: dict[str, Any],
        success: bool,
        busy: bool,
        fragment: str,
        attached: str,
    ) -> None:
        """Each outcome reports its verdict, its busy flag and the response it rests on."""
        session = _session(page, login)
        manager = JsonSjclAuthManager(_config(**fields))

        result = manager.authenticate(session, _IP, "admin", _PASSWORD)

        assert result.success is success, case
        assert result.busy is busy, case
        assert fragment in result.error, case
        expected_response = {"page": page, "login": login, "none": None}[attached]
        assert result.response is expected_response, case
        if success:
            assert session.headers == {_TOKEN_HEADER: "tok"}
            assert manager.encode_action_body({}) is not None
        else:
            assert session.headers == {}
            assert manager.encode_action_body({}) is None

    def test_page_failure_sends_no_login(self) -> None:
        """A login page without salt and IV never reaches the login endpoint."""
        session = _session(_response(200, text="<html></html>"), _response(200))

        JsonSjclAuthManager(_config()).authenticate(session, _IP, "admin", _PASSWORD)

        session.put.assert_not_called()


# =============================================================================
# The request on the wire
# =============================================================================


class TestJsonSjclLoginRequest:
    """The login request is the firmware's exact envelope."""

    def _sent(self, username: str = "Admin", **fields: Any) -> tuple[MagicMock, Any]:
        """Log in and return the session with the login call it made."""
        session = _session(_OK_PAGE, _response(200, json_body={}, headers=_TOKEN))
        JsonSjclAuthManager(_config(**fields)).authenticate(session, _IP, username, _PASSWORD)
        sender = session.put if fields.get("method", "PUT") == "PUT" else session.post
        return session, sender.call_args

    def test_body_is_encrypted_data_and_lowercased_user(self) -> None:
        """The JSON body carries exactly EncryptedData and the lowercased user."""
        _, call = self._sent()

        body = call.kwargs["json"]
        assert set(body) == {"EncryptedData", "user"}
        assert body["user"] == "admin"

    def test_plaintext_is_compact_json_with_lowercased_username(self) -> None:
        """EncryptedData decrypts to the compact JSON the page's JSON.stringify builds."""
        _, call = self._sent()

        plaintext = sjcl.decrypt(_KEY, _IV, call.kwargs["json"]["EncryptedData"], _AAD, 16)
        assert plaintext == b'{"username":"admin","password":"pw"}'

    @pytest.mark.parametrize("method", ["PUT", "POST"])
    def test_method_and_endpoint(self, method: str) -> None:
        """The declared method reaches the login endpoint; the page is fetched first."""
        session, call = self._sent(method=method)

        assert call.args[0] == f"{_IP}/actionHandler/login.php"
        session.get.assert_called_once()
        assert session.get.call_args.args[0] == f"{_IP}/login.php"

    def test_default_method_is_put(self) -> None:
        """PUT is the default, the verb the firmware's login uses."""
        assert _config().method == "PUT"


# =============================================================================
# Shared envelope, session state and hygiene
# =============================================================================


class TestEncryptPayload:
    """encrypt_payload is the one envelope for login and actions."""

    def test_round_trip(self) -> None:
        """The envelope decrypts back to the compact JSON of the input under the session."""
        session = SjclSession(key=_KEY, iv_hex=_IV, user="admin", aad=_AAD, tag_length=16)

        envelope = encrypt_payload(session, {"action": "restart", "module": "gateway"})

        assert set(envelope) == {"EncryptedData", "user"}
        assert envelope["user"] == "admin"
        plaintext = sjcl.decrypt(_KEY, _IV, envelope["EncryptedData"], _AAD, 16)
        assert plaintext == b'{"action":"restart","module":"gateway"}'


class TestJsonSjclSessionState:
    """The login hands the action layer an encoder, never the key itself."""

    def test_success_supplies_the_session_encoder(self) -> None:
        """encode_action_body wraps a body under the login's key, IV, user and AAD."""
        session = _session(_OK_PAGE, _response(200, json_body={}, headers=_TOKEN))
        manager = JsonSjclAuthManager(_config())

        manager.authenticate(session, _IP, "Admin", _PASSWORD)

        envelope = manager.encode_action_body({"action": "restart", "module": "gateway"})
        assert envelope is not None
        assert set(envelope) == {"EncryptedData", "user"}
        assert envelope["user"] == "admin"
        plaintext = sjcl.decrypt(_KEY, _IV, envelope["EncryptedData"], _AAD, 16)
        assert plaintext == b'{"action":"restart","module":"gateway"}'

    def test_failed_relogin_drops_the_encoder(self) -> None:
        """A login that fails after one succeeded leaves nothing to encode with, never the old key."""
        manager = JsonSjclAuthManager(_config())
        manager.authenticate(_session(_OK_PAGE, _response(200, json_body={}, headers=_TOKEN)), _IP, "admin", _PASSWORD)
        assert manager.encode_action_body({}) is not None

        manager.authenticate(_session(_OK_PAGE, _response(503)), _IP, "admin", _PASSWORD)

        assert manager.encode_action_body({}) is None

    def test_success_exposes_token_for_action_placeholders(self) -> None:
        """AuthContext.token carries the header token, so actions can name {auth:token} as with bearer."""
        session = _session(_OK_PAGE, _response(200, json_body={}, headers=_TOKEN))

        result = JsonSjclAuthManager(_config()).authenticate(session, _IP, "admin", _PASSWORD)

        assert result.auth_context.token == "tok"

    def test_key_not_in_repr(self) -> None:
        """Neither the login's context, the manager, its encoder nor its session state prints the key."""
        session = _session(_OK_PAGE, _response(200, json_body={}, headers=_TOKEN))
        manager = JsonSjclAuthManager(_config())

        result = manager.authenticate(session, _IP, "admin", _PASSWORD)

        state = SjclSession(key=_KEY, iv_hex=_IV, user="admin", aad=_AAD, tag_length=16)
        for text in (repr(result.auth_context), repr(manager), repr(manager.encode_action_body), repr(state)):
            assert _KEY.hex() not in text
            assert repr(_KEY) not in text

    def test_success_does_not_advertise_reuse(self) -> None:
        """The login response is not a data page, so response/response_url stay unset."""
        session = _session(_OK_PAGE, _response(200, json_body={}, headers=_TOKEN))

        result = JsonSjclAuthManager(_config()).authenticate(session, _IP, "admin", _PASSWORD)

        assert result.success is True
        assert result.response is None
        assert result.response_url == ""

    def test_missing_cryptography_fails_before_any_request(self) -> None:
        """Without the [sjcl] extra the login fails naming it, and nothing is sent."""
        session = _session(_OK_PAGE, _response(200))

        with patch.object(sjcl, "ensure_available", side_effect=ImportError("no cryptography")):
            result = JsonSjclAuthManager(_config()).authenticate(session, _IP, "admin", _PASSWORD)

        assert result.success is False
        assert "[sjcl]" in result.error
        assert "json_sjcl" in result.error
        session.get.assert_not_called()
        session.put.assert_not_called()
