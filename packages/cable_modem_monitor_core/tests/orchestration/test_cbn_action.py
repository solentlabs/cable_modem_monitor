"""Tests for CBN action executor.

Table-driven for multiple scenarios.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import requests
from requests.cookies import RequestsCookieJar
from solentlabs.cable_modem_monitor_core.models.modem_config.actions import CbnAction
from solentlabs.cable_modem_monitor_core.orchestration.actions.cbn_action import (
    execute_cbn_action,
)


def _make_session(token: str = "tok") -> MagicMock:
    """Create a mock session with sessionToken cookie."""
    session = MagicMock(spec=requests.Session)
    session.cookies = RequestsCookieJar()
    session.cookies.set("sessionToken", token)
    return session


def _mock_response(status_code: int = 200) -> MagicMock:
    """Build a mock response."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 400
    return resp


# ---------------------------------------------------------------------------
# Table-driven action scenarios
# ---------------------------------------------------------------------------

# ┌─────────────────────────┬─────┬────────────────────────────┬─────────┐
# │ scenario                │ fun │ post behavior              │ success │
# ├─────────────────────────┼─────┼────────────────────────────┼─────────┤
# │ logout success          │ 16  │ HTTP 200                   │ True    │
# │ restart + connection    │ 8   │ ConnectionError            │ True    │
# │ restart + timeout       │ 8   │ Timeout                    │ False   │
# │ server error            │ 16  │ HTTP 500                   │ False   │
# └─────────────────────────┴─────┴────────────────────────────┴─────────┘

# fmt: off
ACTION_CASES = [
    # (desc, fun, post_side_effect_or_response, expected_success, error_substr)
    ("logout_success",     16, _mock_response(200),                   True,  ""),
    ("restart_conn_lost",  8,  requests.ConnectionError("rebooting"), True,  "connection lost"),
    ("restart_timeout",    8,  requests.Timeout("timed out"),         False, "failed"),
    ("server_error",       16, _mock_response(500),                   False, "500"),
]
# fmt: on


@pytest.mark.parametrize(
    "desc,fun,post_effect,expected_success,error_substr",
    ACTION_CASES,
    ids=[c[0] for c in ACTION_CASES],
)
def test_action_scenario(
    desc: str,
    fun: int,
    post_effect: object,
    expected_success: bool,
    error_substr: str,
) -> None:
    """CBN action produces expected result."""
    session = _make_session()
    action = CbnAction(type="cbn", fun=fun)

    if isinstance(post_effect, Exception):
        session.post.side_effect = post_effect
    else:
        session.post.return_value = post_effect

    result = execute_cbn_action(
        session,
        "http://192.168.0.1",
        action,
        setter_endpoint="/xml/setter.xml",
        session_cookie_name="sessionToken",
        timeout=10,
        model="T100",
    )

    assert result.success is expected_success
    if error_substr:
        assert error_substr in result.message.lower()


# ---------------------------------------------------------------------------
# Token in POST body
# ---------------------------------------------------------------------------


class TestPostBody:
    """Token must be first parameter in POST body."""

    def test_token_first_param(self) -> None:
        """POST body starts with token=."""
        session = _make_session(token="my_token")
        session.post.return_value = _mock_response()

        action = CbnAction(type="cbn", fun=16)
        execute_cbn_action(
            session,
            "http://192.168.0.1",
            action,
            setter_endpoint="/xml/setter.xml",
            session_cookie_name="sessionToken",
        )

        data = session.post.call_args.kwargs.get("data", "")
        assert data.startswith("token=my_token")
        assert "fun=16" in data

    def test_fun_in_details(self) -> None:
        """Result details include the fun parameter."""
        session = _make_session()
        session.post.return_value = _mock_response()

        action = CbnAction(type="cbn", fun=8)
        result = execute_cbn_action(
            session,
            "http://192.168.0.1",
            action,
            setter_endpoint="/xml/setter.xml",
            session_cookie_name="sessionToken",
        )

        assert result.details["fun"] == 8
