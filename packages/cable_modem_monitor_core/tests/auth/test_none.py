"""Tests for NoneAuthManager."""

from __future__ import annotations

import pytest
import requests
from solentlabs.cable_modem_monitor_core.auth.none import NoneAuthManager

# +-----------------+-----------+---------------------+
# | field           | expected  | description         |
# +-----------------+-----------+---------------------+
# | success         | True      | always succeeds     |
# | error           | ""        | no error message    |
# | auth_context    | {}        | no auth context     |
# | response        | None      | no login response   |
# | response_url    | ""        | no response URL     |
# +-----------------+-----------+---------------------+
#
# fmt: off
RESULT_FIELD_CASES = [
    ("success",      True,  "always succeeds"),
    ("error",        "",    "no error message"),
    ("auth_context", {},    "no auth context"),
    ("response",     None,  "no login response"),
    ("response_url", "",    "no response URL"),
]
# fmt: on


class TestNoneAuthManager:
    """NoneAuthManager always succeeds with no side effects."""

    @pytest.mark.parametrize(
        "field,expected,desc",
        RESULT_FIELD_CASES,
        ids=[c[2] for c in RESULT_FIELD_CASES],
    )
    def test_result_field(
        self,
        session: requests.Session,
        field: str,
        expected: object,
        desc: str,  # noqa: ARG002
    ) -> None:
        """AuthResult field has the expected default value."""
        manager = NoneAuthManager()
        result = manager.authenticate(session, "http://192.168.100.1", "", "")
        assert getattr(result, field) == expected

    def test_session_unchanged(self, session: requests.Session) -> None:
        """Session has no auth credentials added."""
        manager = NoneAuthManager()
        manager.authenticate(session, "http://192.168.100.1", "", "")
        assert session.auth is None
        assert len(session.cookies) == 0
