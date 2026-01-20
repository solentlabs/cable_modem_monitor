"""Fixture validation tests for MB8611.

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


class TestMB8611FixtureValidation:
    """Validate MB8611 HNAP auth pattern using fixtures."""

    def test_login_page_exists(self):
        """Verify login page fixture is available."""
        login_page = FIXTURES_DIR / "Login.html"
        assert login_page.exists(), "Login.html fixture missing"

    def test_login_page_has_hnap_pattern(self):
        """Verify login page contains HNAP auth pattern."""
        html = _load_html_fixture(FIXTURES_DIR / "Login.html")
        if not html:
            pytest.skip("Login page fixture not available")

        # MB8611 uses HNAP/SOAP auth
        assert "HNAP" in html or "SOAPAction" in html or "Login" in html, "Login page should reference HNAP auth"

    def test_hnap_request_uses_empty_string(self):
        """Verify HNAP request uses empty string for action values.

        Both S33 and MB8611 use "" (empty string) for action values.
        Verified from real HAR captures (fixtures extracted and committed).
        """
        request = _load_json_fixture(FIXTURES_DIR / "extended/hnap_data_request.json")
        if not request:
            pytest.skip("HNAP request fixture not available")

        # MB8611 uses "" (empty string) for action values, same as S33
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

        adapter = get_auth_adapter_for_parser("MotorolaMB8611HnapParser")
        assert adapter is not None, "Should have modem.yaml config"
        hints = adapter.get_hnap_hints()
        assert hints is not None, "Should have hnap_hints in modem.yaml"

        required_keys = ["endpoint", "namespace", "empty_action_value"]
        for key in required_keys:
            assert key in hints, f"Missing {key} in hnap_hints"

        assert hints["endpoint"] == "/HNAP1/"
        assert hints["empty_action_value"] == ""  # Same as S33, verified from HAR

    def test_hnap_response_can_be_parsed(self):
        """Verify parser can handle HNAP response format."""
        response = _load_json_fixture(FIXTURES_DIR / "hnap_full_status.json")
        if not response:
            pytest.skip("HNAP response fixture not available")

        # Should have expected structure
        assert "GetMultipleHNAPsResponse" in response
        multi_resp = response["GetMultipleHNAPsResponse"]
        assert "GetMotoStatusConnectionInfoResponse" in multi_resp
        assert "GetMultipleHNAPsResult" in multi_resp

    def test_empty_action_value_matches_fixture(self):
        """Verify modem.yaml empty_action_value matches real HAR-derived fixture.

        This test prevents regression of the {} vs "" bug.
        Fixture extracted from real HAR capture and committed to fixtures/extended/.
        """
        # Load the committed fixture (extracted from real HAR)
        fixture = _load_json_fixture(FIXTURES_DIR / "extended/hnap_data_request.json")
        assert fixture is not None, "HNAP request fixture should exist"

        # Verify fixture shows empty strings, not empty dicts
        actions = fixture.get("GetMultipleHNAPs", {})
        assert len(actions) > 0, "Fixture should have action entries"
        for action_name, action_value in actions.items():
            assert action_value == "", f"Fixture shows {action_name} should use empty string, " f"got {action_value!r}"

        # Verify modem.yaml matches fixture
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_auth_adapter_for_parser,
        )

        adapter = get_auth_adapter_for_parser("MotorolaMB8611HnapParser")
        assert adapter is not None, "Should have modem.yaml config"
        hints = adapter.get_hnap_hints()
        assert hints is not None, "Should have hnap_hints in modem.yaml"
        assert hints["empty_action_value"] == "", (
            f"modem.yaml empty_action_value should be '' to match fixture, " f"got {hints['empty_action_value']!r}"
        )
