"""Fixture validation tests for S33.

Validates that committed fixture files are correct and that parser
configuration matches actual modem behavior observed in HAR captures.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


def _load_json_fixture(path: Path) -> dict[str, Any] | None:
    """Load a JSON fixture file."""
    if not path.exists():
        return None
    with open(path) as f:
        data: dict[str, Any] = json.load(f)
        return data


def _load_html_fixture(path: Path) -> str | None:
    """Load an HTML fixture file."""
    if not path.exists():
        return None
    for encoding in ("utf-8", "iso-8859-1", "cp1252"):
        try:
            with open(path, encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    return None


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


class TestS33FixtureValidation:
    """Validate S33 HNAP auth pattern using fixtures."""

    def test_login_page_exists(self):
        """Verify login page fixture is available."""
        login_page = FIXTURES_DIR / "Login.html"
        assert login_page.exists(), "Login.html fixture missing"

    def test_login_page_has_hnap_pattern(self):
        """Verify login page contains HNAP auth pattern."""
        html = _load_html_fixture(FIXTURES_DIR / "Login.html")
        if not html:
            pytest.skip("Login page fixture not available")

        # S33 uses HNAP/SOAP auth
        assert "HNAP" in html or "SOAPAction" in html or "Login.js" in html, "Login page should reference HNAP auth"

    def test_hnap_request_uses_empty_string(self):
        """Verify HNAP request uses empty string for action values."""
        request = _load_json_fixture(FIXTURES_DIR / "extended/hnap_data_request.json")
        if not request:
            pytest.skip("HNAP request fixture not available")

        # S33 uses "" (empty string) for action values
        actions = request.get("GetMultipleHNAPs", {})
        for action_name, action_value in actions.items():
            assert action_value == "", f"Should use empty string for {action_name}, got {action_value!r}"

    def test_hnap_login_response_has_challenge(self):
        """Verify HNAP login response contains challenge pattern."""
        response = _load_json_fixture(FIXTURES_DIR / "extended/hnap_login_response.json")
        if not response:
            pytest.skip("HNAP login response fixture not available")

        login_resp = response.get("LoginResponse", {})
        assert "LoginResult" in login_resp
        assert "Challenge" in login_resp
        assert "PublicKey" in login_resp
        assert "Cookie" in login_resp

    def test_parser_hnap_hints_complete(self):
        """Verify modem.yaml has complete hnap_hints."""
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_auth_adapter_for_parser,
        )

        adapter = get_auth_adapter_for_parser("ArrisS33HnapParser")
        assert adapter is not None, "Should have modem.yaml config"
        hints = adapter.get_hnap_hints()
        assert hints is not None, "Should have hnap_hints in modem.yaml"

        required_keys = ["endpoint", "namespace", "empty_action_value"]
        for key in required_keys:
            assert key in hints, f"Missing {key} in hnap_hints"

        assert hints["endpoint"] == "/HNAP1/"
        assert hints["empty_action_value"] == ""

    def test_hnap_response_can_be_parsed(self):
        """Verify parser can handle HNAP response format."""
        response = _load_json_fixture(FIXTURES_DIR / "extended/hnap_device_status_response.json")
        if not response:
            pytest.skip("HNAP response fixture not available")

        # Should have expected structure
        assert "GetArrisDeviceStatusResponse" in response
        status = response["GetArrisDeviceStatusResponse"]
        assert "FirmwareVersion" in status
        assert "GetArrisDeviceStatusResult" in status

    def test_empty_action_value_matches_parser(self):
        """Verify modem.yaml uses empty string for action values.

        S33 was the first to use "" and is the reference implementation.
        """
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_auth_adapter_for_parser,
        )

        adapter = get_auth_adapter_for_parser("ArrisS33HnapParser")
        assert adapter is not None, "Should have modem.yaml config"
        hints = adapter.get_hnap_hints()
        assert hints is not None, "Should have hnap_hints in modem.yaml"
        assert (
            hints["empty_action_value"] == ""
        ), f"empty_action_value should be '', got {hints['empty_action_value']!r}"
