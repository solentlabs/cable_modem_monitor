"""Restart retries once when the modem refuses the reused monitoring session.

ORCHESTRATION_SPEC § Restart Action ("A refused reused session retries
once"), UC-21a. Two layers:

- executors mark a refusal from the firmware's own verdict (HNAP
  ``UN-AUTH``, HTTP 401 or 403) and nothing else;
- ``run_restart`` clears the session, logs in fresh and sends the action
  once more, only for a refusal on the reused monitoring session.

TEST DATA TABLES
================
``HTTP_CASES``: response status in, ``session_refused`` out.
``HNAP_CASES``: ``<Action>Result`` in, ``session_refused`` out.
``RETRY_CASES``: executor results and session state in, restart outcome out.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest
import requests
from solentlabs.cable_modem_monitor_core.models.modem_config.actions import HttpAction
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import NoneAuth
from solentlabs.cable_modem_monitor_core.orchestration.actions.base import ActionResult
from solentlabs.cable_modem_monitor_core.orchestration.actions.hnap_action import _validate_response
from solentlabs.cable_modem_monitor_core.orchestration.actions.http_action import execute_http_action
from solentlabs.cable_modem_monitor_core.orchestration.recovery import Recovery
from solentlabs.cable_modem_monitor_core.orchestration.restart import run_restart

_REFUSED = ActionResult(success=False, message="refused", session_refused=True)
_FAILED = ActionResult(success=False, message="HTTP 500")
_OK = ActionResult(success=True, message="sent")

# fmt: off
HTTP_CASES = [
    # (id, status, session_refused)
    ("401 is a refusal", 401, True),
    ("403 is a refusal", 403, True),
    ("404 is a wrong endpoint, not a session", 404, False),
    ("500 is the modem failing", 500, False),
    ("200 is accepted", 200, False),
    ("302 is accepted", 302, False),
]

HNAP_CASES = [
    # (id, <Action>Result, session_refused)
    ("UN-AUTH is a refusal", "UN-AUTH", True),
    ("another result is a failure, not a refusal", "ERROR", False),
    ("OK is accepted", "OK", False),
]

RETRY_CASES = [
    # (id, executor results in order, session reused, action_auth, fresh login ok,
    #  sends, authenticates, clears, success)
    ("refused then accepted",            [_REFUSED, _OK],      True,  False, True,  2, 2, 2, True),
    ("refused twice stops after one retry", [_REFUSED, _REFUSED], True, False, True, 2, 2, 1, False),
    ("refusal on a session just created", [_REFUSED],           False, False, True,  1, 1, 0, False),
    ("failure that is not a refusal",    [_FAILED],            True,  False, True,  1, 1, 0, False),
    ("accepted is never retried",        [_OK],                True,  False, True,  1, 1, 1, True),
    ("action_auth never retries",        [_REFUSED],           True,  True,  True,  1, 0, 0, False),
    ("fresh login fails on the retry",   [_REFUSED],           True,  False, False, 1, 2, 1, False),
]
# fmt: on


def _action(method: str = "POST") -> MagicMock:
    action = MagicMock()
    action.method = method
    action.endpoint = "/restart.htm"
    action.endpoint_pattern = ""
    action.pre_fetch_url = ""
    action.params = {"restart": "1"}
    action.json_body = None
    action.headers = None
    return action


@pytest.mark.parametrize(("case_id", "status", "refused"), HTTP_CASES, ids=[c[0] for c in HTTP_CASES])
def test_http_executor_marks_a_refusal(case_id: str, status: int, refused: bool) -> None:
    session = MagicMock()
    response = MagicMock()
    response.status_code = status
    response.ok = status < 400
    session.request.return_value = response
    result = execute_http_action(session, "http://192.168.100.1", _action(), model="T100")
    assert result.session_refused is refused


def test_http_connection_drop_is_not_a_refusal() -> None:
    """A lost connection is the reboot starting: success, never a refusal."""
    session = MagicMock()
    session.request.side_effect = requests.exceptions.ConnectionError("reset")
    result = execute_http_action(session, "http://192.168.100.1", _action(), model="T100")
    assert result.success is True
    assert result.session_refused is False


@pytest.mark.parametrize(("case_id", "result", "refused"), HNAP_CASES, ids=[c[0] for c in HNAP_CASES])
def test_hnap_executor_marks_a_refusal(case_id: str, result: str, refused: bool) -> None:
    action = MagicMock()
    action.action_name = "SetStatusSecuritySettings"
    action.response_key = "SetStatusSecuritySettingsResponse"
    action.result_key = "SetStatusSecuritySettingsResult"
    action.success_value = "OK"
    data = {"SetStatusSecuritySettingsResponse": {"SetStatusSecuritySettingsResult": result}}
    assert _validate_response(data, action, model="MB8611").session_refused is refused


def _config(*, action_auth: bool) -> MagicMock:
    config = MagicMock()
    config.model = "T100"
    config.timeout = 10
    config.actions.logout = None
    config.actions.restart = HttpAction(
        type="http",
        method="POST",
        endpoint="/restart.htm",
        params={"restart": "1"},
        action_auth=NoneAuth(strategy="none") if action_auth else None,
    )
    return config


def _collector(*, reused: bool, fresh_login_ok: bool) -> MagicMock:
    collector = MagicMock()
    collector.session_reused = reused
    collector.session_age_seconds = 4000.0
    first = MagicMock(success=True, error="")
    second = MagicMock(success=fresh_login_ok, error="" if fresh_login_ok else "login refused")
    collector.authenticate.side_effect = [first, second]
    return collector


@pytest.mark.parametrize(
    ("case_id", "results", "reused", "action_auth", "login_ok", "sends", "logins", "clears", "success"),
    RETRY_CASES,
    ids=[c[0] for c in RETRY_CASES],
)
def test_restart_retries_only_a_refused_reused_session(
    case_id: str,
    results: list[ActionResult],
    reused: bool,
    action_auth: bool,
    login_ok: bool,
    sends: int,
    logins: int,
    clears: int,
    success: bool,
) -> None:
    config = _config(action_auth=action_auth)
    collector = _collector(reused=reused, fresh_login_ok=login_ok)
    recovery = Recovery(modem_config=config)
    with patch(
        "solentlabs.cable_modem_monitor_core.orchestration.restart.execute_action",
        side_effect=list(results),
    ) as execute:
        result = run_restart(collector, config, recovery)
    assert execute.call_count == sends
    assert collector.authenticate.call_count == logins
    assert collector.clear_session.call_count == clears
    assert result.success is success
    assert recovery.active is success
    if not success:
        assert result.error == "command_failed"


def test_retry_is_logged_with_the_session_age(caplog: pytest.LogCaptureFixture) -> None:
    config = _config(action_auth=False)
    collector = _collector(reused=True, fresh_login_ok=True)
    with (
        patch(
            "solentlabs.cable_modem_monitor_core.orchestration.restart.execute_action",
            side_effect=[_REFUSED, _OK],
        ),
        caplog.at_level(logging.INFO),
    ):
        run_restart(collector, config, Recovery(modem_config=config))
    assert "Restart refused on a reused session [T100]" in caplog.text
    assert "session age 4000s" in caplog.text
    assert "retry once" in caplog.text


def test_second_refusal_is_logged_as_a_failed_command(caplog: pytest.LogCaptureFixture) -> None:
    config = _config(action_auth=False)
    collector = _collector(reused=True, fresh_login_ok=True)
    collector.session_age_seconds = 0.0
    with (
        patch(
            "solentlabs.cable_modem_monitor_core.orchestration.restart.execute_action",
            side_effect=[_REFUSED, _REFUSED],
        ),
        caplog.at_level(logging.INFO),
    ):
        run_restart(collector, config, Recovery(modem_config=config))
    assert "Restart command failed [T100] — refused" in caplog.text
