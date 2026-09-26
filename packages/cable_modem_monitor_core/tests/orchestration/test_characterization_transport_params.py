"""Characterization: auth-config values the HNAP and CBN transports put on the wire.

The collector's HNAP and CBN loaders and the action dispatcher's HNAP
and CBN executors read transport parameters off the auth block:
``hmac_algorithm`` for HNAP; the getter or setter endpoint and the
session cookie name for CBN. These rows pin what a real collector and
``execute_action`` send, observed on the wire, so moving those reads
into the transport modules (ARCHITECTURE_DECISIONS § Strategy
knowledge lives with the strategy) can prove nothing changed.

The premise that makes those modules a legitimate home, one strategy
per protocol-locked transport, is pinned here too.

TEST DATA TABLES
================
This module uses table-driven tests. Tables are defined at the top
of the file with ASCII box-drawing comments for readability.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from solentlabs.cable_modem_monitor_core.auth.base import AuthContext, AuthResult
from solentlabs.cable_modem_monitor_core.models.modem_config.actions import CbnAction, HnapAction
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import get_transport_strategy_sets
from solentlabs.cable_modem_monitor_core.models.parser_config import ParserConfig
from solentlabs.cable_modem_monitor_core.orchestration.actions import execute_action
from solentlabs.cable_modem_monitor_core.orchestration.collector import ModemDataCollector
from solentlabs.cable_modem_monitor_core.protocol.hnap import HNAP_NAMESPACE, hmac_hex

from tests._helpers import load_fixture

from ._characterization import RecordedRequest, RecordingServer, build_modem_config

_PARSER_FIXTURES = Path(__file__).parents[1] / "models" / "fixtures" / "parser_config" / "valid"
_HNAP_PARSER = _PARSER_FIXTURES / "hnap_downstream.json"
_CBN_PARSER = _PARSER_FIXTURES / "xml_downstream.json"

_HNAP_BODY = '{"GetMultipleHNAPsResponse": {}}'
_CBN_BODY = "<downstream_table/>"

HNAP_MD5 = {"strategy": "hnap", "hmac_algorithm": "md5"}
HNAP_SHA256 = {"strategy": "hnap", "hmac_algorithm": "sha256"}
CBN_DEFAULT = {"strategy": "form_cbn"}
CBN_CUSTOM = {
    "strategy": "form_cbn",
    "getter_endpoint": "/alt/get.xml",
    "setter_endpoint": "/alt/set.xml",
    "session_cookie_name": "tokA",
}

# Both names are always in the jar, so the posted token shows which one was read.
CBN_COOKIES = {"sessionToken": "S-default", "tokA": "S-custom"}

HNAP_RESTART = HnapAction(type="hnap", action_name="RestartDevice")
CBN_RESTART = CbnAction(type="cbn", fun=8)

# =============================================================================
# Test Data Tables
# =============================================================================

# ┌──────────────┬──────────────────┬───────────┬───────────┬──────────────────────────┐
# │ auth block   │ context          │ algorithm │ key used  │ description              │
# ├──────────────┼──────────────────┼───────────┼───────────┼──────────────────────────┤
# │ hmac md5     │ private_key K1   │ md5       │ K1        │ declared algorithm       │
# │ hmac sha256  │ private_key K1   │ sha256    │ K1        │ declared algorithm       │
# │ hmac md5     │ never            │ md5       │ ""        │ no login: empty key      │
# └──────────────┴──────────────────┴───────────┴───────────┴──────────────────────────┘
#
# fmt: off
HNAP_LOADER_CASES: list[tuple[dict[str, Any], AuthContext | None, str, str, str]] = [
    # (auth,         context,                          algorithm, key,  id)
    (HNAP_MD5,       AuthContext(private_key="K1"),    "md5",     "K1", "md5"),
    (HNAP_SHA256,    AuthContext(private_key="K1"),    "sha256",  "K1", "sha256"),
    (HNAP_SHA256,    None,                             "sha256",  "",   "sha256-never_authenticated"),
]
# fmt: on

# ┌──────────────┬───────────┬──────────────────────────┐
# │ auth block   │ algorithm │ description              │
# ├──────────────┼───────────┼──────────────────────────┤
# │ hmac md5     │ md5       │ action signs with md5    │
# │ hmac sha256  │ sha256    │ action signs with sha256 │
# └──────────────┴───────────┴──────────────────────────┘
#
# fmt: off
HNAP_ACTION_CASES: list[tuple[dict[str, Any], str, str]] = [
    # (auth,         algorithm, id)
    (HNAP_MD5,       "md5",     "md5"),
    (HNAP_SHA256,    "sha256",  "sha256"),
]
# fmt: on

# ┌──────────────┬────────────────────┬──────────────┬───────────────────────────┐
# │ auth block   │ endpoint           │ token posted │ description               │
# ├──────────────┼────────────────────┼──────────────┼───────────────────────────┤
# │ defaults     │ /xml/getter.xml    │ S-default    │ default getter + cookie   │
# │ custom       │ /alt/get.xml       │ S-custom     │ declared getter + cookie  │
# └──────────────┴────────────────────┴──────────────┴───────────────────────────┘
#
# fmt: off
CBN_LOADER_CASES: list[tuple[dict[str, Any], str, str, str]] = [
    # (auth,         endpoint,          body,                          id)
    (CBN_DEFAULT,    "/xml/getter.xml", "token=S-default&fun=10",      "defaults"),
    (CBN_CUSTOM,     "/alt/get.xml",    "token=S-custom&fun=10",       "custom"),
]
# fmt: on

# ┌──────────────┬────────────────────┬──────────────┬───────────────────────────┐
# │ auth block   │ endpoint           │ token posted │ description               │
# ├──────────────┼────────────────────┼──────────────┼───────────────────────────┤
# │ defaults     │ /xml/setter.xml    │ S-default    │ default setter + cookie   │
# │ custom       │ /alt/set.xml       │ S-custom     │ declared setter + cookie  │
# └──────────────┴────────────────────┴──────────────┴───────────────────────────┘
#
# fmt: off
CBN_ACTION_CASES: list[tuple[dict[str, Any], str, str, str]] = [
    # (auth,         endpoint,          body,                          id)
    (CBN_DEFAULT,    "/xml/setter.xml", "token=S-default&fun=8",       "defaults"),
    (CBN_CUSTOM,     "/alt/set.xml",    "token=S-custom&fun=8",        "custom"),
]
# fmt: on

# ┌───────────┬─────────────────┬──────────────────────────────────┐
# │ transport │ strategies      │ description                      │
# ├───────────┼─────────────────┼──────────────────────────────────┤
# │ hnap      │ {hnap}          │ protocol is its own strategy     │
# │ cbn       │ {form_cbn}      │ protocol is its own strategy     │
# └───────────┴─────────────────┴──────────────────────────────────┘
#
# fmt: off
PROTOCOL_LOCKED_CASES = [
    # (transport, strategies,              id)
    ("hnap",      frozenset({"hnap"}),     "hnap"),
    ("cbn",       frozenset({"form_cbn"}), "cbn"),
]
# fmt: on


def _assert_hnap_signature(request: RecordedRequest, action: str, key: str, algorithm: str) -> None:
    """Recompute HNAP_AUTH from its own timestamp; only the expected key and algorithm reproduce it."""
    digest, timestamp = request.headers["HNAP_AUTH"].split(" ")
    assert digest == hmac_hex(key=key, message=f'{timestamp}"{HNAP_NAMESPACE}{action}"', algorithm=algorithm)


def _collector(auth: dict[str, Any], parser_fixture: Path, base_url: str) -> ModemDataCollector:
    parser_config = ParserConfig.model_validate(load_fixture(parser_fixture))
    return ModemDataCollector(build_modem_config(auth), parser_config, None, base_url, "", "")


class TestHnapLoaderAlgorithm:
    """The collector's HNAP fetch signs with the auth block's algorithm and the login's key."""

    @pytest.mark.parametrize(
        "auth,context,algorithm,key,desc",
        HNAP_LOADER_CASES,
        ids=[c[4] for c in HNAP_LOADER_CASES],
    )
    def test_loader_signature(
        self,
        auth: dict[str, Any],
        context: AuthContext | None,
        algorithm: str,
        key: str,
        desc: str,
    ) -> None:
        """HNAP_AUTH on the data fetch verifies only under the recorded algorithm and key."""
        with RecordingServer("application/json", _HNAP_BODY) as server:
            collector = _collector(auth, _HNAP_PARSER, server.base_url)
            collector._auth_context = context
            collector._load_resources(AuthResult(success=True))

        (request,) = server.requests
        assert (request.method, request.path) == ("POST", "/HNAP1/"), desc
        _assert_hnap_signature(request, "GetMultipleHNAPs", key, algorithm)


class TestHnapActionAlgorithm:
    """``execute_action`` signs an HNAP action with the auth block's algorithm."""

    @pytest.mark.parametrize(
        "auth,algorithm,desc",
        HNAP_ACTION_CASES,
        ids=[c[2] for c in HNAP_ACTION_CASES],
    )
    def test_action_signature(self, auth: dict[str, Any], algorithm: str, desc: str) -> None:
        """HNAP_AUTH on the action verifies only under the recorded algorithm."""
        with RecordingServer("application/json", "{}") as server:
            collector = _collector(auth, _HNAP_PARSER, server.base_url)
            collector._auth_context = AuthContext(private_key="K1")
            execute_action(collector, build_modem_config(auth), HNAP_RESTART)

        (request,) = server.requests
        assert (request.method, request.path) == ("POST", "/HNAP1/"), desc
        _assert_hnap_signature(request, "RestartDevice", "K1", algorithm)


class TestCbnLoaderParams:
    """The collector's CBN fetch uses the auth block's getter endpoint and session cookie."""

    @pytest.mark.parametrize(
        "auth,endpoint,body,desc",
        CBN_LOADER_CASES,
        ids=[c[3] for c in CBN_LOADER_CASES],
    )
    def test_loader_request(self, auth: dict[str, Any], endpoint: str, body: str, desc: str) -> None:
        """The data fetch posts the named cookie's token to the named getter."""
        with RecordingServer("text/xml", _CBN_BODY) as server:
            collector = _collector(auth, _CBN_PARSER, server.base_url)
            collector._auth_context = AuthContext()
            for name, value in CBN_COOKIES.items():
                collector.session.cookies.set(name, value)
            collector._load_resources(AuthResult(success=True))

        assert [(r.method, r.path, r.body) for r in server.requests] == [("POST", endpoint, body)], desc


class TestCbnActionParams:
    """``execute_action`` sends a CBN action to the auth block's setter with its session cookie."""

    @pytest.mark.parametrize(
        "auth,endpoint,body,desc",
        CBN_ACTION_CASES,
        ids=[c[3] for c in CBN_ACTION_CASES],
    )
    def test_action_request(self, auth: dict[str, Any], endpoint: str, body: str, desc: str) -> None:
        """The action posts the named cookie's token to the named setter."""
        with RecordingServer("text/xml", "") as server:
            collector = _collector(auth, _CBN_PARSER, server.base_url)
            for name, value in CBN_COOKIES.items():
                collector.session.cookies.set(name, value)
            execute_action(collector, build_modem_config(auth), CBN_RESTART)

        assert [(r.method, r.path, r.body) for r in server.requests] == [("POST", endpoint, body)], desc


class TestProtocolLockedTransports:
    """Each protocol-locked transport admits exactly one auth strategy."""

    @pytest.mark.parametrize(
        "transport,strategies,desc",
        PROTOCOL_LOCKED_CASES,
        ids=[c[2] for c in PROTOCOL_LOCKED_CASES],
    )
    def test_single_strategy(self, transport: str, strategies: frozenset[str], desc: str) -> None:
        """The transport's strategy set is exactly the protocol's own strategy."""
        assert get_transport_strategy_sets()[transport] == strategies, desc
