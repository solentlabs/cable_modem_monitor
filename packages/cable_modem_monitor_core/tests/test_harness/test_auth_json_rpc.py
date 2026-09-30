"""Tests for JsonRpcAuthHandler — the JSON-RPC mock handler.

Drives the real ``json_rpc`` auth manager, loader and action executor
against a HARMockServer built from a synthetic capture: calls are
answered by body ``method``, the token must ride in the query, and a
request the capture cannot honestly answer fails.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
import requests
from solentlabs.cable_modem_monitor_core.auth.json_rpc import JsonRpcAuthManager
from solentlabs.cable_modem_monitor_core.fetch_list import ResourceTarget
from solentlabs.cable_modem_monitor_core.loaders.http import ResourceLoadError
from solentlabs.cable_modem_monitor_core.loaders.json_rpc import JsonRpcLoader
from solentlabs.cable_modem_monitor_core.models.modem_config import ModemConfig
from solentlabs.cable_modem_monitor_core.models.modem_config.actions import JsonRpcAction
from solentlabs.cable_modem_monitor_core.orchestration.actions.json_rpc_action import execute_json_rpc_action
from solentlabs.cable_modem_monitor_core.protocol.json_rpc import call_url, json_rpc_params
from solentlabs.cable_modem_monitor_core.test_harness.server import HARMockServer

_ENDPOINT = "/cgi-bin/router.php"
_TOKEN = "FIELD_token01"


@pytest.fixture(autouse=True)
def _allow_sockets(socket_enabled: None) -> None:
    """The mock server listens on a real socket."""


def _entry(method: str, reply: dict[str, Any], *, token: str = "", params: Any = None) -> dict[str, Any]:
    query = f"?token={token}" if token else ""
    body = {"jsonrpc": "2.0", "method": method, "params": params if params is not None else [], "id": 7}
    return {
        "request": {
            "method": "POST",
            "url": f"https://192.168.0.1{_ENDPOINT}{query}",
            "headers": [{"name": "Content-Type", "value": "application/json; charset=UTF-8"}],
            "postData": {"mimeType": "application/json", "text": json.dumps(body)},
        },
        "response": {
            "status": 200,
            "headers": [{"name": "Content-Type", "value": "application/json; charset=UTF-8"}],
            "content": {"mimeType": "application/json", "text": json.dumps(reply)},
        },
    }


_CREDS = [{"loginUserName": "FIELD_u", "loginPwd": "FIELD_p"}]
_ENTRIES = [
    # A failed login first, as the capture steps ask; the success must win.
    _entry(
        "MGMT.login", {"jsonrpc": "2.0", "error": {"code": "msgBadLoginText", "message": ""}, "id": 1}, params=_CREDS
    ),
    _entry("MGMT.login", {"jsonrpc": "2.0", "result": {"token": _TOKEN}, "id": 2}, params=_CREDS),
    _entry("CM.getDownstream", {"jsonrpc": "2.0", "result": {"dss": [{"channel": "2"}]}, "id": 3}, token=_TOKEN),
    _entry("CM.getMisc", {"jsonrpc": "2.0", "result": {"model": "T950"}, "id": 4}, token=_TOKEN),
    _entry("MGMT.reboot", {"jsonrpc": "2.0", "result": [], "id": 5}, token=_TOKEN),
]


def _config() -> ModemConfig:
    return ModemConfig.model_validate(
        {
            "manufacturer": "Solent Labs",
            "model": "T950",
            "transport": "json_rpc",
            "default_host": "192.168.0.1",
            "auth": {
                "strategy": "json_rpc",
                "endpoint": _ENDPOINT,
                "login_method": "MGMT.login",
                "username_field": "loginUserName",
                "password_field": "loginPwd",
                "token_path": "token",
                "token_param": "token",
            },
            "actions": {"restart": {"type": "json_rpc", "method": "MGMT.reboot"}},
            "status": "unsupported",
        }
    )


def _manager(config: ModemConfig) -> JsonRpcAuthManager:
    return JsonRpcAuthManager(json_rpc_params(config.auth))


def _loader(session: requests.Session, base_url: str, token: str) -> JsonRpcLoader:
    return JsonRpcLoader(
        session=session,
        base_url=base_url,
        endpoint=_ENDPOINT,
        token_prefix="token=" if token else "",
        url_token=token,
        session_expired_code="",
        timeout=5,
        model="T950",
    )


def test_login_then_data_by_method() -> None:
    """The successful login's token unlocks each captured method's result."""
    config = _config()
    with HARMockServer(_ENTRIES, modem_config=config) as server:
        session = requests.Session()
        result = _manager(config).authenticate(session, server.base_url, "admin", "pw")
        assert result.success, result.error
        assert result.auth_context.token == _TOKEN

        targets = [ResourceTarget(path=m, format="json") for m in ("CM.getDownstream", "CM.getMisc")]
        resources = _loader(session, server.base_url, _TOKEN).fetch(targets)

    assert resources == {"CM.getDownstream": {"dss": [{"channel": "2"}]}, "CM.getMisc": {"model": "T950"}}


def test_data_call_without_token_is_refused() -> None:
    """Core must send the token the way the browser did."""
    config = _config()
    with HARMockServer(_ENTRIES, modem_config=config) as server:
        session = requests.Session()
        assert _manager(config).authenticate(session, server.base_url, "admin", "pw").success
        with pytest.raises(ResourceLoadError) as info:
            _loader(session, server.base_url, "").fetch([ResourceTarget(path="CM.getMisc", format="json")])

    assert info.value.status_code == 401


def test_method_not_in_capture_is_not_found() -> None:
    """An uncaptured method never borrows another method's reply."""
    config = _config()
    with HARMockServer(_ENTRIES, modem_config=config) as server:
        session = requests.Session()
        assert _manager(config).authenticate(session, server.base_url, "admin", "pw").success
        with pytest.raises(ResourceLoadError) as info:
            _loader(session, server.base_url, _TOKEN).fetch([ResourceTarget(path="CM.getLogs", format="json")])

    assert info.value.status_code == 404


def test_login_with_unrecorded_credential_keys_fails() -> None:
    """A credential object the capture never carried means the modem was never asked this."""
    config = _config()
    wrong = json_rpc_params(config.auth).model_copy(update={"username_field": "user"})
    with HARMockServer(_ENTRIES, modem_config=config) as server:
        result = JsonRpcAuthManager(wrong).authenticate(requests.Session(), server.base_url, "admin", "pw")

    assert not result.success
    assert "HTTP 500" in result.error


def test_restart_not_in_capture_is_refused() -> None:
    """A restart the capture never made is refused rather than synthesized."""
    config = _config()
    entries = [e for e in _ENTRIES if "MGMT.reboot" not in e["request"]["postData"]["text"]]
    with HARMockServer(entries, modem_config=config) as server:
        session = requests.Session()
        assert _manager(config).authenticate(session, server.base_url, "admin", "pw").success
        url = call_url(server.base_url, _ENDPOINT, "token=", _TOKEN)
        result = execute_json_rpc_action(session, JsonRpcAction(type="json_rpc", method="MGMT.reboot"), url=url)

        assert not result.success
        assert server.auth_handler.served_actions.get("restart") == 404


def test_restart_is_answered_and_recorded() -> None:
    """The restart call is served from the capture and recorded for the runner."""
    config = _config()
    with HARMockServer(_ENTRIES, modem_config=config) as server:
        session = requests.Session()
        assert _manager(config).authenticate(session, server.base_url, "admin", "pw").success
        url = call_url(server.base_url, _ENDPOINT, "token=", _TOKEN)
        result = execute_json_rpc_action(session, JsonRpcAction(type="json_rpc", method="MGMT.reboot"), url=url)

        assert result.success, result.message
        assert server.auth_handler.served_actions.get("restart") == 200
