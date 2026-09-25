"""Tests for HAR mock server: json_sjcl (SJCL-encrypted JSON login) integration.

Runs the real ``JsonSjclAuthManager`` and HTTP action executor against
``HARMockServer`` over real HTTP. The handler decrypts the login body
under the key it derives from its own test password, so a login is
accepted only when Core encrypted exactly the firmware's plaintext.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

import pytest
import requests
from solentlabs.cable_modem_monitor_core.auth.json_sjcl import JsonSjclAuthManager, encrypt_payload
from solentlabs.cable_modem_monitor_core.models.modem_config.actions import HttpAction
from solentlabs.cable_modem_monitor_core.orchestration.actions import execute_http_action
from solentlabs.cable_modem_monitor_core.protocol import sjcl
from solentlabs.cable_modem_monitor_core.test_harness.auth import create_auth_handler
from solentlabs.cable_modem_monitor_core.test_harness.auth.json_sjcl import JsonSjclAuthHandler
from solentlabs.cable_modem_monitor_core.test_harness.server import HARMockServer

from tests._helpers import load_fixture

FIXTURES_DIR = Path(__file__).parent / "fixtures"

_PASSWORD = JsonSjclAuthHandler._TEST_PASSWORD
_RESTART = "/actionHandler/restart.php"


def _entries(name: str) -> list[dict[str, Any]]:
    return list(load_fixture(FIXTURES_DIR / name)["_entries"])


def _config(restart: dict[str, Any] | None = None) -> Any:
    from solentlabs.cable_modem_monitor_core.config_loader import validate_modem_config

    data: dict[str, Any] = {
        "manufacturer": "Solent Labs",
        "model": "T100",
        "transport": "http",
        "default_host": "192.168.100.1",
        "status": "unsupported",
        "auth": {
            "strategy": "json_sjcl",
            "login_page": "/login.php",
            "login_endpoint": "/actionHandler/login.php",
            "pbkdf2_iterations": 1000,
            "pbkdf2_key_length": 128,
            "aad": "AAD",
            "token_header": "X-Session-Token",
            "cookie_name": "PHPSESSID",
        },
    }
    if restart is not None:
        data["actions"] = {"restart": restart}
    return validate_modem_config(data)


_ENCRYPTED_RESTART: dict[str, Any] = {
    "type": "http",
    "method": "PUT",
    "endpoint": _RESTART,
    "json_body": {"action": "restart", "module": "gateway"},
    "body_encoding": "session",
}

# ┌──────────────────────────────┬──────────────┬──────────┬──────────┬───────────────┐
# │ fixture                      │ data page    │ user     │ password │ login status  │
# ├──────────────────────────────┼──────────────┼──────────┼──────────┼───────────────┤
# │ captured login page          │ /status.php  │ Admin    │ pw       │ accepted      │
# │ captured login page          │ /status.php  │ admin    │ wrong    │ 471           │
# │ no page in capture           │ /status.html │ ADMIN    │ pw       │ accepted      │
# │ no page in capture           │ /status.html │ admin    │ wrong    │ 471           │
# └──────────────────────────────┴──────────────┴──────────┴──────────┴───────────────┘
#
# fmt: off
LOGIN_CASES = [
    ("har_entries_json_sjcl.json", "/status.php",  "Admin", _PASSWORD, True,  "captured page, mixed-case user"),
    ("har_entries_json_sjcl.json", "/status.php",  "admin", "wrong",   False, "captured page, wrong password"),
    ("har_entries_no_auth.json",   "/status.html", "ADMIN", _PASSWORD, True,  "synthesized page"),
    ("har_entries_no_auth.json",   "/status.html", "admin", "wrong",   False, "synthesized page, wrong password"),
]
# fmt: on


# ┌──────────────────────────────┬────────────┬─────────────┬────────┬───────────────────────────────┐
# │ fixture                      │ encoding   │ session key │ status │ why                           │
# ├──────────────────────────────┼────────────┼─────────────┼────────┼───────────────────────────────┤
# │ captured restart (200)       │ session    │ login's     │ 200    │ captured answer served        │
# │ no restart in capture        │ session    │ login's     │ 200    │ synthesized answer            │
# │ captured restart (200)       │ session    │ other       │ 400    │ refusal beats the capture     │
# │ no restart in capture        │ plain      │ -           │ 400    │ plaintext is not the envelope │
# └──────────────────────────────┴────────────┴─────────────┴────────┴───────────────────────────────┘
#
# A plaintext body against the captured restart never reaches dispatch:
# the server fails keys the capture never recorded (ARCHITECTURE § A
# request the harness cannot honestly answer fails).
#
# fmt: off
RESTART_CASES = [
    ("har_entries_json_sjcl.json", "session", "login", 200, "encrypted, captured"),
    ("har_entries_no_auth.json",   "session", "login", 200, "encrypted, synthesized"),
    ("har_entries_json_sjcl.json", "session", "other", 400, "wrong key, captured 200 does not rescue"),
    ("har_entries_no_auth.json",   "plain",   "login", 400, "plaintext rejected"),
]
# fmt: on


class TestJsonSjclMockServer:
    """The real manager logs in only with the credential the handler can decrypt."""

    def test_factory_dispatches_json_sjcl(self) -> None:
        """A json_sjcl config gets the json_sjcl handler."""
        assert isinstance(create_auth_handler(_config()), JsonSjclAuthHandler)

    def test_page_without_assignments_refuses_every_login(self) -> None:
        """A captured page with no salt or IV leaves nothing to decrypt with, so the login answers 471."""
        handler = JsonSjclAuthHandler(
            "/login.php",
            "/actionHandler/login.php",
            method="PUT",
            pbkdf2_iterations=1000,
            pbkdf2_key_length=128,
            ccm_tag_length=16,
            aad="AAD",
            token_header="X-Session-Token",
            login_page_html="<html></html>",
        )

        response = handler.handle_login("PUT", "/actionHandler/login.php", b'{"EncryptedData":"00","user":"admin"}', {})

        assert response is not None
        assert response.status == 471
        assert handler.handle_login("GET", "/status.php", b"", {}) is None

    def test_restart_from_another_user_refused(self) -> None:
        """An envelope that decrypts but names another user is not the session's, so the restart is refused."""
        handler = create_auth_handler(_config(restart=_ENCRYPTED_RESTART))
        assert isinstance(handler, JsonSjclAuthHandler)
        key = sjcl.derive_key(_PASSWORD, JsonSjclAuthHandler._TEST_SALT, 1000, 128)
        encrypted = sjcl.encrypt(key, JsonSjclAuthHandler._TEST_IV_HEX, "{}", "AAD", 16)

        response = handler.handle_restart(body=json.dumps({"EncryptedData": encrypted, "user": "other"}).encode())

        assert response.status == 400

    def test_data_pages_require_login(self) -> None:
        """Data pages are challenged before any login."""
        with HARMockServer(_entries("har_entries_json_sjcl.json"), modem_config=_config()) as server:
            assert requests.get(f"{server.base_url}/status.php").status_code == 401

    @pytest.mark.parametrize(
        "fixture,data_page,username,password,accepted,desc",
        LOGIN_CASES,
        ids=[c[5] for c in LOGIN_CASES],
    )
    def test_login(self, fixture: str, data_page: str, username: str, password: str, accepted: bool, desc: str) -> None:
        """A correct credential is accepted and opens data pages; a wrong one answers 471."""
        config = _config()
        with HARMockServer(_entries(fixture), modem_config=config) as server:
            session = requests.Session()

            result = JsonSjclAuthManager(config.auth).authenticate(session, server.base_url, username, password)

            assert result.success is accepted, desc
            if accepted:
                assert session.headers["X-Session-Token"] == JsonSjclAuthHandler._TEST_TOKEN
                assert "PHPSESSID" in session.cookies
                assert session.get(f"{server.base_url}{data_page}").status_code == 200
            else:
                assert result.response is not None
                assert result.response.status_code == 471
                assert result.response.json() == "Parameter decryption failed"
                assert session.get(f"{server.base_url}{data_page}").status_code == 401

    @pytest.mark.parametrize(
        "fixture,encoding,session_key,status,desc",
        RESTART_CASES,
        ids=[c[4] for c in RESTART_CASES],
    )
    def test_restart(self, fixture: str, encoding: str, session_key: str, status: int, desc: str) -> None:
        """Only a restart encrypted under the login's session key is accepted; a capture cannot rescue one."""
        config = _config(restart=_ENCRYPTED_RESTART)
        with HARMockServer(_entries(fixture), modem_config=config) as server:
            session = requests.Session()
            manager = JsonSjclAuthManager(config.auth)
            login = manager.authenticate(session, server.base_url, "admin", _PASSWORD)
            assert login.success is True
            encode_body: Callable[[dict[str, Any]], dict[str, Any] | None] = manager.encode_action_body
            if session_key == "other":
                # Encrypted, but under a key the login never derived.
                other = sjcl.SjclSession(
                    key=bytes(16), iv_hex="aabbccddeeff0011", user="admin", aad="AAD", tag_length=16
                )
                encode_body = partial(encrypt_payload, other)

            result = execute_http_action(
                session,
                server.base_url,
                HttpAction.model_validate({**_ENCRYPTED_RESTART, "body_encoding": encoding}),
                auth_context=login.auth_context,
                encode_body=encode_body,
            )

            assert result.success is (status == 200), desc
            assert server.auth_handler.served_actions == {"restart": status}, desc
