"""Every site that reads an exception as CONNECTIVITY agrees on which ones are.

The rule (RESOURCE_LOADING_SPEC § Error Signals, ORCHESTRATION_SPEC
CollectorSignal.CONNECTIVITY): a requests ``ConnectionError`` or
``Timeout`` means the modem never answered. Auth strategies re-raise it,
loaders let it escape, the collector maps it to CONNECTIVITY, and the
HTTP, HNAP and JSON-RPC actions read it as the reboot dropping the
connection (the CBN action catches only ``ConnectionError``). The predicate
(``connectivity.is_connectivity_error``) and each site are driven with
the same truth table, so a site that drifts from it fails. Auth
strategies are driven in ``auth/test_auth_failure_modes.py``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests
from requests.cookies import RequestsCookieJar
from solentlabs.cable_modem_monitor_core.auth.setup import detect_setup_params
from solentlabs.cable_modem_monitor_core.connectivity import is_connectivity_error
from solentlabs.cable_modem_monitor_core.fetch_list import ResourceTarget
from solentlabs.cable_modem_monitor_core.loaders.cbn import CBNLoader
from solentlabs.cable_modem_monitor_core.loaders.hnap import HNAPLoadError
from solentlabs.cable_modem_monitor_core.loaders.http import ResourceLoadError
from solentlabs.cable_modem_monitor_core.loaders.json_rpc import JsonRpcLoader
from solentlabs.cable_modem_monitor_core.models.modem_config import ModemConfig
from solentlabs.cable_modem_monitor_core.models.modem_config.actions import (
    HnapAction,
    HttpAction,
    JsonRpcAction,
)
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import NoneAuth
from solentlabs.cable_modem_monitor_core.orchestration.actions.hnap_action import execute_hnap_action
from solentlabs.cable_modem_monitor_core.orchestration.actions.http_action import execute_http_action
from solentlabs.cable_modem_monitor_core.orchestration.actions.json_rpc_action import execute_json_rpc_action
from solentlabs.cable_modem_monitor_core.orchestration.collector import ModemDataCollector
from solentlabs.cable_modem_monitor_core.orchestration.signals import CollectorSignal
from solentlabs.cable_modem_monitor_core.parsers.diagnostics import ParseDiagnostics

from tests._helpers import REQUESTS_CONNECTIVITY_CASES, requests_case_id

_IDS = [requests_case_id(c) for c in REQUESTS_CONNECTIVITY_CASES]

# A wrapped cause can be anything the loader caught, so the collector's
# classifiers also see exceptions from outside requests. The builtin
# ConnectionError and TimeoutError share a name with the requests types
# but not the class, and are not the rule.
# fmt: off
CAUSE_CASES: list[tuple[BaseException | None, bool]] = [
    *REQUESTS_CONNECTIVITY_CASES,
    (ValueError("malformed"),       False),
    (ConnectionError("builtin"),    False),
    (TimeoutError("builtin"),       False),
    (None,                          False),
]
# fmt: on
_CAUSE_IDS = [*_IDS, "ValueError", "builtin-ConnectionError", "builtin-TimeoutError", "no-cause"]


@pytest.mark.parametrize("exc,connectivity", CAUSE_CASES, ids=_CAUSE_IDS)
def test_predicate(exc: BaseException | None, connectivity: bool) -> None:
    """The shared predicate is the truth table every site below follows."""
    assert is_connectivity_error(exc) is connectivity


def _collector(transport: str = "http") -> ModemDataCollector:
    """Build a collector over a mock config; only the fields execute() reads are real."""
    config = MagicMock()
    config.transport = transport
    config.timeout = 10
    config.auth = NoneAuth(strategy="none")
    config.session.headers = {}
    config.session.query_params = {}
    config.session.post_login_endpoints = []
    config.actions = None
    return ModemDataCollector(config, MagicMock(), None, "http://localhost", "", "")


def _execute(collector: ModemDataCollector, *, auth: Any = None, load: Any = None) -> Any:
    """Run one collection with the auth or load phase raising the given exception."""
    auth_patch = (
        patch.object(collector, "authenticate", side_effect=auth)
        if auth is not None
        else patch.object(collector, "authenticate", return_value=MagicMock(success=True))
    )
    parsed = ({"downstream": [], "upstream": [], "system_info": {}}, ParseDiagnostics())
    with (
        auth_patch,
        patch.object(collector, "_load_resources", side_effect=load),
        patch.object(collector, "_parse", return_value=parsed),
    ):
        return collector.execute()


# ---------------------------------------------------------------------------
# Collector: wrapped causes (HTTP and HNAP classifiers)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cause,connectivity", CAUSE_CASES, ids=_CAUSE_IDS)
def test_http_wrapped_cause(cause: BaseException | None, connectivity: bool) -> None:
    """A status-less ResourceLoadError is CONNECTIVITY exactly when its cause is."""
    err = ResourceLoadError("Failed to fetch /d.htm", path="/d.htm")
    err.__cause__ = cause
    result = _execute(_collector(), load=err)
    assert (result.signal == CollectorSignal.CONNECTIVITY) is connectivity


@pytest.mark.parametrize("cause,connectivity", CAUSE_CASES, ids=_CAUSE_IDS)
def test_hnap_wrapped_cause(cause: BaseException | None, connectivity: bool) -> None:
    """A status-less HNAPLoadError is CONNECTIVITY exactly when its cause is."""
    err = HNAPLoadError("HNAP request failed")
    err.__cause__ = cause
    result = _execute(_collector("hnap"), load=err)
    assert (result.signal == CollectorSignal.CONNECTIVITY) is connectivity


# ---------------------------------------------------------------------------
# Collector: raw exceptions escaping auth or load
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("phase", ["auth", "load"])
@pytest.mark.parametrize("exc,connectivity", REQUESTS_CONNECTIVITY_CASES, ids=_IDS)
def test_collector_raw_exception(phase: str, exc: requests.RequestException, connectivity: bool) -> None:
    """A raw connectivity exception becomes CONNECTIVITY; any other one is not caught there."""
    kwargs = {phase: exc}
    if connectivity:
        assert _execute(_collector(), **kwargs).signal == CollectorSignal.CONNECTIVITY
    else:
        with pytest.raises(type(exc)):
            _execute(_collector(), **kwargs)


# ---------------------------------------------------------------------------
# Loaders: connectivity escapes raw, everything else becomes ResourceLoadError
# ---------------------------------------------------------------------------


def _cbn_fetch(session: MagicMock) -> Any:
    jar = RequestsCookieJar()
    jar.set("sessionToken", "tok")
    session.cookies = jar
    loader = CBNLoader(
        session=session,
        base_url="http://192.168.0.1",
        getter_endpoint="/xml/getter.xml",
        session_cookie_name="sessionToken",
        timeout=10,
        model="T100",
    )
    return loader.fetch([ResourceTarget(path="10", format="xml")])


def _json_rpc_fetch(session: MagicMock) -> Any:
    loader = JsonRpcLoader(
        session=session,
        base_url="http://192.168.0.1",
        endpoint="/rpc",
        token_prefix="token=",
        url_token="tok",
        session_expired_code="expired",
        timeout=7,
        model="T950",
    )
    return loader.fetch([ResourceTarget(path="CM.x", format="json")])


@pytest.mark.parametrize("fetch", [_cbn_fetch, _json_rpc_fetch], ids=["cbn", "json_rpc"])
@pytest.mark.parametrize("exc,connectivity", REQUESTS_CONNECTIVITY_CASES, ids=_IDS)
def test_loader_classification(fetch: Any, exc: requests.RequestException, connectivity: bool) -> None:
    """Connectivity escapes as itself; any other request error is a ResourceLoadError."""
    session = MagicMock(spec=requests.Session)
    session.post.side_effect = exc
    expected: type[Exception] = type(exc) if connectivity else ResourceLoadError
    with pytest.raises(expected) as info:
        fetch(session)
    assert isinstance(info.value, ResourceLoadError) is not connectivity


# ---------------------------------------------------------------------------
# Actions: a lost connection is the reboot; anything else is not
# ---------------------------------------------------------------------------


def _ok_response() -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.ok = True
    resp.status_code = 200
    return resp


def _http_main(exc: requests.RequestException) -> Any:
    session = MagicMock(spec=requests.Session)
    session.request.side_effect = exc
    return execute_http_action(session, "http://192.168.0.1", HttpAction(type="http", method="POST", endpoint="/r"))


def _http_pre_fetch(exc: requests.RequestException) -> Any:
    # A lost pre-fetch falls back to the static endpoint, which answers.
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = exc
    session.request.return_value = _ok_response()
    action = HttpAction(type="http", method="POST", endpoint="/r", pre_fetch_url="/p", endpoint_pattern="x")
    return execute_http_action(session, "http://192.168.0.1", action)


def _hnap(exc: requests.RequestException) -> Any:
    session = MagicMock(spec=requests.Session)
    session.post.side_effect = exc
    return execute_hnap_action(session, "http://192.168.0.1", HnapAction(type="hnap", action_name="Reboot"), "key")


def _json_rpc(exc: requests.RequestException) -> Any:
    session = MagicMock(spec=requests.Session)
    session.post.side_effect = exc
    return execute_json_rpc_action(session, JsonRpcAction(type="json_rpc", method="MGMT.reboot"), url="http://x/rpc")


# (run, what a non-connectivity exception does)
# fmt: off
ACTION_SITES = [
    (_http_main,      "raises"),
    (_http_pre_fetch, "raises"),
    (_hnap,           "raises"),
    (_json_rpc,       "fails"),
]
# fmt: on


@pytest.mark.parametrize("run,otherwise", ACTION_SITES, ids=["http", "http-pre-fetch", "hnap", "json_rpc"])
@pytest.mark.parametrize("exc,connectivity", REQUESTS_CONNECTIVITY_CASES, ids=_IDS)
def test_action_classification(run: Any, otherwise: str, exc: requests.RequestException, connectivity: bool) -> None:
    """Connectivity reads as a sent action; anything else raises or fails, per site."""
    if connectivity:
        assert run(exc).success is True
    elif otherwise == "raises":
        with pytest.raises(type(exc)):
            run(exc)
    else:
        assert run(exc).success is False


# ---------------------------------------------------------------------------
# Setup: an unreachable login page stops validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("exc,connectivity", REQUESTS_CONNECTIVITY_CASES, ids=_IDS)
def test_setup_page_fetch(exc: requests.RequestException, connectivity: bool) -> None:
    """Connectivity surfaces as the builtin ConnectionError; anything else detects on an empty page."""
    config = ModemConfig.model_validate(
        {
            "manufacturer": "Solent Labs",
            "model": "T100",
            "transport": "http",
            "default_host": "192.168.100.1",
            "status": "unsupported",
            "auth": {"strategy": "form_nonce", "action": "/login", "nonce_field": "ar_nonce"},
        }
    )
    session = MagicMock()
    session.get.side_effect = exc
    with patch("solentlabs.cable_modem_monitor_core.connectivity.create_session", return_value=session):
        if connectivity:
            with pytest.raises(ConnectionError):
                detect_setup_params(config, "http://192.168.100.1")
        else:
            assert isinstance(detect_setup_params(config, "http://192.168.100.1"), dict)
