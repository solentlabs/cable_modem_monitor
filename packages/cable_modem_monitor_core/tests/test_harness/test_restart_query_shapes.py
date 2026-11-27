"""Restart query-shape enforcement — routes builder and server rejection.

A captured restart whose URL carries a query string (a dynamic form
action like ``/goform/RouterStatus?id=NNN``) is a statement about the
request the firmware accepts. A restart sent without that parameter must
not silently match the captured answer — the login rule in
``test_login_query_shapes.py``, applied to the declared restart. Param
*names* are compared, never values: the id changes per page load.

TEST DATA TABLES
================
Shape-collection cases live in ``fixtures/restart_query_shapes_*.json``,
one file per case: ``restart_method``, ``restart_endpoint`` and
``_entries`` in, ``expected_shapes`` out (a list of param-name lists).
Adding a case = adding a file. The enforcement table below loads the
same fixtures as server scaffolding.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import requests
from solentlabs.cable_modem_monitor_core.models.modem_config import ModemConfig
from solentlabs.cable_modem_monitor_core.test_harness.endpoint_match import url_matches_endpoint
from solentlabs.cable_modem_monitor_core.test_harness.routes import build_query_shapes
from solentlabs.cable_modem_monitor_core.test_harness.server import HARMockServer

from tests._helpers import load_fixture

FIXTURES_DIR = Path(__file__).parent / "fixtures"

SHAPE_FIXTURES = sorted(FIXTURES_DIR.glob("restart_query_shapes_*.json"))


def _make_config(auth: dict[str, Any]) -> ModemConfig:
    """Validate a modem config declaring the fixtures' restart, with the given auth block."""
    from solentlabs.cable_modem_monitor_core.config_loader import validate_modem_config

    return validate_modem_config(
        {
            "manufacturer": "Solent Labs",
            "model": "T100",
            "transport": "http",
            "default_host": "192.168.100.1",
            "status": "unsupported",
            "auth": auth,
            "actions": {"restart": {"type": "http", "method": "POST", "endpoint": "/goform/RouterStatus"}},
        }
    )


class TestBuildRestartQueryShapes:
    """Shape collection from captured restart requests, one fixture per case."""

    @pytest.mark.parametrize("fixture_path", SHAPE_FIXTURES, ids=lambda p: p.stem)
    def test_shapes(self, fixture_path: Path) -> None:
        data = load_fixture(fixture_path)
        expected = frozenset(frozenset(shape) for shape in data["expected_shapes"])
        method, endpoint = data["restart_method"], data["restart_endpoint"]

        def is_restart(m: str, url: str) -> bool:
            return m == method and url_matches_endpoint(endpoint, url)

        shapes = build_query_shapes(data["_entries"], is_restart)
        assert shapes == expected


# ┌──────────────────────────────────────┬──────────────────────────────┬─────────┬────────────────────────────────┐
# │ fixture                              │ request path                 │ status  │ description                    │
# ├──────────────────────────────────────┼──────────────────────────────┼─────────┼────────────────────────────────┤
# │ restart_query_shapes_dynamic_id.json │ /goform/RouterStatus         │ 500     │ dropped id fails as dishonest  │
# │ restart_query_shapes_dynamic_id.json │ /goform/RouterStatus?id=999  │ 302     │ same names, new value matches  │
# │ restart_query_shapes_dynamic_id.json │ /goform/RouterStatus?x=1     │ 500     │ other name fails               │
# │ restart_query_shapes_bare.json       │ /goform/RouterStatus         │ 302     │ bare capture, bare restart     │
# └──────────────────────────────────────┴──────────────────────────────┴─────────┴────────────────────────────────┘
#
# fmt: off
ENFORCEMENT_CASES = [
    # (fixture,                              request_path,                  status, description)
    ("restart_query_shapes_dynamic_id.json",   "/goform/RouterStatus",        500,    "dropped id fails as dishonest"),
    ("restart_query_shapes_dynamic_id.json",   "/goform/RouterStatus?id=999", 302,    "same names, new value matches"),
    ("restart_query_shapes_dynamic_id.json",   "/goform/RouterStatus?x=1",    500,    "other name fails"),
    ("restart_query_shapes_bare.json",         "/goform/RouterStatus",        302,    "bare capture, bare restart"),
]
# fmt: on


class TestRestartQueryShapeEnforcement:
    """Server rejects restarts whose query shape the capture never recorded."""

    @pytest.mark.parametrize(
        "fixture,request_path,status,desc",
        ENFORCEMENT_CASES,
        ids=[c[3] for c in ENFORCEMENT_CASES],
    )
    def test_restart_query_shape(self, fixture: str, request_path: str, status: int, desc: str) -> None:
        entries = list(load_fixture(FIXTURES_DIR / fixture)["_entries"])
        with HARMockServer(entries, modem_config=_make_config({"strategy": "none"})) as server:
            resp = requests.post(
                f"{server.base_url}{request_path}",
                data={"buttonSelect": "2"},
                timeout=5,
                allow_redirects=False,
            )
        assert resp.status_code == status, desc
        if status == 500:
            assert "restart query params not in the capture" in resp.text

    def test_restart_sharing_the_login_endpoint_is_left_to_the_login_rule(self) -> None:
        """A restart at the login path is the login check's request, not a second check's."""
        entries = list(load_fixture(FIXTURES_DIR / "restart_query_shapes_dynamic_id.json")["_entries"])
        config = _make_config({"strategy": "form", "action": "/goform/RouterStatus", "cookie_name": "s"})
        with HARMockServer(entries, modem_config=config) as server:
            resp = requests.post(f"{server.base_url}/goform/RouterStatus", timeout=5, allow_redirects=False)
        assert "restart query params" not in resp.text
