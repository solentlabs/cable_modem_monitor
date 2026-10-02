"""Tests for Phase 4: Action detection - dispatch and serialization.

Transport-specific tests are in test_actions_http.py and
test_actions_hnap.py. This file tests the dispatcher and shared types.
"""

from __future__ import annotations

from solentlabs.cable_modem_monitor_catalog_tools.analysis import (
    ActionDetail,
    ActionsDetail,
)


class TestActionsSerialization:
    """ActionsDetail and ActionDetail serialization."""

    def test_to_dict_no_actions(self) -> None:
        """No actions serializes as both null."""
        detail = ActionsDetail()
        assert detail.to_dict() == {"logout": None, "restart": None}

    def test_to_dict_with_logout(self) -> None:
        """Logout action serializes correctly."""
        detail = ActionsDetail(logout=ActionDetail(type="http", method="GET", endpoint="/logout.asp"))
        d = detail.to_dict()
        assert d["logout"]["type"] == "http"
        assert d["logout"]["method"] == "GET"
        assert d["logout"]["endpoint"] == "/logout.asp"
        assert d["restart"] is None

    def test_to_dict_excludes_empty_params(self) -> None:
        """Empty params excluded from serialization."""
        detail = ActionDetail(type="http", method="GET", endpoint="/logout.asp")
        d = detail.to_dict()
        assert "params" not in d

    def test_to_dict_includes_params(self) -> None:
        """Non-empty params included in serialization."""
        detail = ActionDetail(type="http", method="POST", endpoint="/reboot", params={"action": "1"})
        d = detail.to_dict()
        assert d["params"] == {"action": "1"}

    def test_to_dict_json_body(self) -> None:
        """json_body serializes when observed and is omitted otherwise."""
        body = {"reboot": {"enable": True}}
        assert ActionDetail(type="http", method="POST", endpoint="/r", json_body=body).to_dict()["json_body"] == body
        assert "json_body" not in ActionDetail(type="http", method="POST", endpoint="/r").to_dict()

    def test_to_dict_body_state(self) -> None:
        """A body state and its evidence serialize when set and are omitted otherwise."""
        evidence = {"keys": ["EncryptedData", "user"], "sanitized": ["user"]}
        encoded = ActionDetail(type="http", method="PUT", endpoint="/r", body="encoded", body_evidence=evidence)
        assert encoded.to_dict()["body"] == "encoded"
        assert encoded.to_dict()["body_evidence"] == evidence
        plain = ActionDetail(type="http", method="PUT", endpoint="/r").to_dict()
        assert "body" not in plain
        assert "body_evidence" not in plain

    def test_to_dict_includes_action_name(self) -> None:
        """Non-empty action_name included in serialization."""
        detail = ActionDetail(
            type="hnap",
            method="POST",
            endpoint="/HNAP1/",
            action_name="SetDeviceReboot",
        )
        d = detail.to_dict()
        assert d["action_name"] == "SetDeviceReboot"

    def test_to_dict_excludes_empty_action_name(self) -> None:
        """Empty action_name excluded from serialization."""
        detail = ActionDetail(type="http", method="GET", endpoint="/logout.asp")
        d = detail.to_dict()
        assert "action_name" not in d
