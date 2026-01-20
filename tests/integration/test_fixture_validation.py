"""Fixture-Based Validation Tests for Auth Strategy Discovery.

These tests validate auth strategies using committed fixture files:
1. HNAP request/response format validation
2. Login page detection patterns
3. Parser hint consistency
4. Auth strategy matching

Unlike HAR files (which are gitignored), these fixtures are committed
to the repo and always available for testing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.auth import AuthStrategyType
from custom_components.cable_modem_monitor.core.discovery_helpers import HintMatcher

# Path to fixture directories (now in modems/)
MODEMS_DIR = Path(__file__).parent.parent.parent / "modems"
S33_FIXTURES = MODEMS_DIR / "arris/s33/fixtures"
MB8611_FIXTURES = MODEMS_DIR / "motorola/mb8611/fixtures"
SB8200_FIXTURES = MODEMS_DIR / "arris/sb8200/fixtures"


def load_json_fixture(path: Path) -> dict[str, Any] | None:
    """Load a JSON fixture file."""
    if not path.exists():
        return None
    with open(path) as f:
        data: dict[str, Any] = json.load(f)
        return data


def load_html_fixture(path: Path) -> str | None:
    """Load an HTML fixture file."""
    if not path.exists():
        return None
    # Try UTF-8 first, fall back to ISO-8859-1 for legacy fixtures
    for encoding in ("utf-8", "iso-8859-1", "cp1252"):
        try:
            with open(path, encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    return None


class TestSB8200AuthValidation:
    """Validate SB8200 URL token auth pattern using fixtures."""

    def test_login_page_exists(self):
        """Verify login page fixture is available."""
        login_page = SB8200_FIXTURES / "extended/login_page.html"
        assert login_page.exists(), "SB8200 login_page.html fixture missing"

    def test_login_page_has_javascript_auth(self):
        """Verify login page contains JavaScript-based auth pattern."""
        html = load_html_fixture(SB8200_FIXTURES / "extended/login_page.html")
        if not html:
            pytest.skip("SB8200 login page fixture not available")

        # SB8200 uses JavaScript for URL token auth
        assert "login_" in html.lower() or "credential" in html.lower(), "Login page should reference URL token auth"

    def test_parser_js_auth_hints_complete(self):
        """Verify SB8200 modem.yaml has complete js_auth_hints (v3.12.0+)."""
        from custom_components.cable_modem_monitor.modem_config.adapter import get_auth_adapter_for_parser

        adapter = get_auth_adapter_for_parser("ArrisSB8200Parser")
        assert adapter is not None, "SB8200 should have modem.yaml config"
        hints = adapter.get_js_auth_hints()
        assert hints is not None, "SB8200 should have js_auth_hints in modem.yaml"

        required_keys = [
            "pattern",
            "login_page",
            "login_prefix",
            "session_cookie_name",
            "data_page",
            "token_prefix",
        ]
        for key in required_keys:
            assert key in hints, f"Missing {key} in SB8200 js_auth_hints"

        assert hints["pattern"] == "url_token_session"
        assert hints["login_prefix"] == "login_"
        assert hints["token_prefix"] == "ct_"

    def test_data_page_can_be_parsed(self):
        """Verify parser can parse data page from fixture."""
        html = load_html_fixture(SB8200_FIXTURES / "cmconnectionstatus.html")
        if not html:
            pytest.skip("SB8200 data page fixture not available")

        from custom_components.cable_modem_monitor.modems.arris.sb8200.parser import ArrisSB8200Parser

        soup = BeautifulSoup(html, "html.parser")
        parser = ArrisSB8200Parser()

        # Should detect as SB8200 via HintMatcher
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_model_strings(html)
        assert any(m.parser_name == "ArrisSB8200Parser" for m in matches)

        # Should parse channel data
        result = parser.parse(soup)
        assert "downstream" in result
        assert len(result["downstream"]) > 0


class TestS33AuthValidation:
    """Validate S33 HNAP auth pattern using fixtures."""

    def test_login_page_exists(self):
        """Verify login page fixture is available."""
        login_page = S33_FIXTURES / "Login.html"
        assert login_page.exists(), "S33 Login.html fixture missing"

    def test_login_page_has_hnap_pattern(self):
        """Verify login page contains HNAP auth pattern."""
        html = load_html_fixture(S33_FIXTURES / "Login.html")
        if not html:
            pytest.skip("S33 login page fixture not available")

        # S33 uses HNAP/SOAP auth
        assert "HNAP" in html or "SOAPAction" in html or "Login.js" in html, "Login page should reference HNAP auth"

    def test_hnap_request_uses_empty_string(self):
        """Verify S33 HNAP request uses empty string for action values."""
        request = load_json_fixture(S33_FIXTURES / "extended/hnap_data_request.json")
        if not request:
            pytest.skip("S33 HNAP request fixture not available")

        # S33 uses "" (empty string) for action values
        actions = request.get("GetMultipleHNAPs", {})
        for action_name, action_value in actions.items():
            assert action_value == "", f"S33 should use empty string for {action_name}, got {action_value!r}"

    def test_hnap_login_response_has_challenge(self):
        """Verify HNAP login response contains challenge pattern."""
        response = load_json_fixture(S33_FIXTURES / "extended/hnap_login_response.json")
        if not response:
            pytest.skip("S33 HNAP login response fixture not available")

        login_resp = response.get("LoginResponse", {})
        assert "LoginResult" in login_resp
        assert "Challenge" in login_resp
        assert "PublicKey" in login_resp
        assert "Cookie" in login_resp

    def test_parser_hnap_hints_complete(self):
        """Verify S33 modem.yaml has complete hnap_hints (v3.12.0+)."""
        from custom_components.cable_modem_monitor.modem_config.adapter import get_auth_adapter_for_parser

        adapter = get_auth_adapter_for_parser("ArrisS33HnapParser")
        assert adapter is not None, "S33 should have modem.yaml config"
        hints = adapter.get_hnap_hints()
        assert hints is not None, "S33 should have hnap_hints in modem.yaml"

        required_keys = ["endpoint", "namespace", "empty_action_value"]
        for key in required_keys:
            assert key in hints, f"Missing {key} in S33 hnap_hints"

        assert hints["endpoint"] == "/HNAP1/"
        assert hints["empty_action_value"] == ""  # S33-specific

    def test_hnap_response_can_be_parsed(self):
        """Verify parser can handle HNAP response format."""
        response = load_json_fixture(S33_FIXTURES / "extended/hnap_device_status_response.json")
        if not response:
            pytest.skip("S33 HNAP response fixture not available")

        # Should have expected structure
        assert "GetArrisDeviceStatusResponse" in response
        status = response["GetArrisDeviceStatusResponse"]
        assert "FirmwareVersion" in status
        assert "GetArrisDeviceStatusResult" in status


class TestMB8611AuthValidation:
    """Validate MB8611 HNAP auth pattern using fixtures."""

    def test_login_page_exists(self):
        """Verify login page fixture is available."""
        login_page = MB8611_FIXTURES / "Login.html"
        assert login_page.exists(), "MB8611 Login.html fixture missing"

    def test_login_page_has_hnap_pattern(self):
        """Verify login page contains HNAP auth pattern."""
        html = load_html_fixture(MB8611_FIXTURES / "Login.html")
        if not html:
            pytest.skip("MB8611 login page fixture not available")

        # MB8611 uses HNAP/SOAP auth
        assert "HNAP" in html or "SOAPAction" in html or "Login" in html, "Login page should reference HNAP auth"

    def test_hnap_request_uses_empty_string(self):
        """Verify MB8611 HNAP request uses empty string for action values.

        Both S33 and MB8611 use "" (empty string) for action values.
        Verified from real HAR captures (fixtures extracted and committed).
        """
        request = load_json_fixture(MB8611_FIXTURES / "extended/hnap_data_request.json")
        if not request:
            pytest.skip("MB8611 HNAP request fixture not available")

        # MB8611 uses "" (empty string) for action values, same as S33
        actions = request.get("GetMultipleHNAPs", {})
        for action_name, action_value in actions.items():
            assert action_value == "", f"MB8611 should use empty string for {action_name}, got {action_value!r}"

    def test_hnap_login_response_has_challenge(self):
        """Verify HNAP login response contains challenge pattern."""
        response = load_json_fixture(MB8611_FIXTURES / "extended/hnap_login_response.json")
        if not response:
            pytest.skip("MB8611 HNAP login response fixture not available")

        login_resp = response.get("LoginResponse", {})
        assert "LoginResult" in login_resp
        assert "Challenge" in login_resp
        assert "PublicKey" in login_resp
        assert "Cookie" in login_resp

    def test_parser_hnap_hints_complete(self):
        """Verify MB8611 modem.yaml has complete hnap_hints (v3.12.0+)."""
        from custom_components.cable_modem_monitor.modem_config.adapter import get_auth_adapter_for_parser

        adapter = get_auth_adapter_for_parser("MotorolaMB8611HnapParser")
        assert adapter is not None, "MB8611 should have modem.yaml config"
        hints = adapter.get_hnap_hints()
        assert hints is not None, "MB8611 should have hnap_hints in modem.yaml"

        required_keys = ["endpoint", "namespace", "empty_action_value"]
        for key in required_keys:
            assert key in hints, f"Missing {key} in MB8611 hnap_hints"

        assert hints["endpoint"] == "/HNAP1/"
        assert hints["empty_action_value"] == ""  # Same as S33, verified from HAR

    def test_hnap_response_can_be_parsed(self):
        """Verify parser can handle HNAP response format."""
        response = load_json_fixture(MB8611_FIXTURES / "hnap_full_status.json")
        if not response:
            pytest.skip("MB8611 HNAP response fixture not available")

        # Should have expected structure
        assert "GetMultipleHNAPsResponse" in response
        multi_resp = response["GetMultipleHNAPsResponse"]
        assert "GetMotoStatusConnectionInfoResponse" in multi_resp
        assert "GetMultipleHNAPsResult" in multi_resp


class TestS33VsMB8611Similarities:
    """Validate S33 and MB8611 HNAP share the same empty_action_value."""

    def test_empty_action_value_same(self):
        """Verify both S33 and MB8611 use '' for action values (v3.12.0+).

        Both modems use empty string "" for HNAP action values.
        Verified from real HAR captures (fixtures extracted and committed).
        See: https://github.com/solentlabs/cable_modem_monitor/issues/32 (S33)
        """
        from custom_components.cable_modem_monitor.modem_config.adapter import get_auth_adapter_for_parser

        s33_adapter = get_auth_adapter_for_parser("ArrisS33HnapParser")
        mb8611_adapter = get_auth_adapter_for_parser("MotorolaMB8611HnapParser")

        assert s33_adapter is not None
        assert mb8611_adapter is not None

        s33_hints = s33_adapter.get_hnap_hints()
        mb8611_hints = mb8611_adapter.get_hnap_hints()

        assert s33_hints is not None
        assert mb8611_hints is not None

        # Both use "" (empty string) - verified from HAR captures
        assert s33_hints["empty_action_value"] == ""
        assert mb8611_hints["empty_action_value"] == ""

    def test_request_fixtures_match_parser_hints(self):
        """Verify request fixtures match parser empty_action_value hints."""
        # S33 fixture
        s33_request = load_json_fixture(S33_FIXTURES / "extended/hnap_data_request.json")
        if s33_request:
            actions = s33_request.get("GetMultipleHNAPs", {})
            for value in actions.values():
                assert value == "", "S33 fixture should use empty string"

        # MB8611 fixture - also uses empty string (verified from HAR)
        mb8611_request = load_json_fixture(MB8611_FIXTURES / "extended/hnap_data_request.json")
        if mb8611_request:
            actions = mb8611_request.get("GetMultipleHNAPs", {})
            for value in actions.values():
                assert value == "", "MB8611 fixture should use empty string"

    def test_action_names_differ(self):
        """Verify S33 uses GetCustomer* while MB8611 uses GetMoto* actions."""
        s33_request = load_json_fixture(S33_FIXTURES / "extended/hnap_data_request.json")
        mb8611_request = load_json_fixture(MB8611_FIXTURES / "extended/hnap_data_request.json")

        if s33_request:
            actions = s33_request.get("GetMultipleHNAPs", {})
            assert any(
                "Customer" in k or "Arris" in k for k in actions
            ), "S33 should use GetCustomer* or GetArris* action names"

        if mb8611_request:
            actions = mb8611_request.get("GetMultipleHNAPs", {})
            assert any("Moto" in k for k in actions), "MB8611 should use GetMoto* action names"


class TestAuthStrategyConstants:
    """Validate auth strategy constants match expected values."""

    def test_all_strategies_defined(self):
        """Verify all auth strategies are defined."""
        expected = [
            "NO_AUTH",
            "BASIC_HTTP",
            "FORM_PLAIN",
            "HNAP_SESSION",
            "URL_TOKEN_SESSION",
            "UNKNOWN",
        ]

        for name in expected:
            assert hasattr(AuthStrategyType, name), f"Missing {name} strategy"

    def test_strategy_string_values(self):
        """Verify strategy string values for storage."""
        assert AuthStrategyType.NO_AUTH.value == "no_auth"
        assert AuthStrategyType.BASIC_HTTP.value == "basic_http"
        assert AuthStrategyType.FORM_PLAIN.value == "form_plain"
        assert AuthStrategyType.HNAP_SESSION.value == "hnap_session"
        assert AuthStrategyType.URL_TOKEN_SESSION.value == "url_token_session"
        assert AuthStrategyType.UNKNOWN.value == "unknown"

    def test_strategy_from_string(self):
        """Verify strategies can be created from string values."""
        assert AuthStrategyType("no_auth") == AuthStrategyType.NO_AUTH
        assert AuthStrategyType("basic_http") == AuthStrategyType.BASIC_HTTP
        assert AuthStrategyType("hnap_session") == AuthStrategyType.HNAP_SESSION
        assert AuthStrategyType("url_token_session") == AuthStrategyType.URL_TOKEN_SESSION


class TestParserHintsConsistency:
    """Validate modem.yaml auth hints are consistent across parsers (v3.12.0+)."""

    def test_s33_hnap_hints_complete(self):
        """Verify S33 modem.yaml has complete HNAP hints."""
        from custom_components.cable_modem_monitor.modem_config.adapter import get_auth_adapter_for_parser

        adapter = get_auth_adapter_for_parser("ArrisS33HnapParser")
        assert adapter is not None, "S33 should have modem.yaml config"
        hints = adapter.get_hnap_hints()
        assert hints is not None, "S33 should have hnap_hints in modem.yaml"

        required_keys = ["endpoint", "namespace", "empty_action_value"]
        for key in required_keys:
            assert key in hints, f"Missing {key} in S33 hnap_hints"

    def test_mb8611_hnap_hints_complete(self):
        """Verify MB8611 modem.yaml has complete HNAP hints."""
        from custom_components.cable_modem_monitor.modem_config.adapter import get_auth_adapter_for_parser

        adapter = get_auth_adapter_for_parser("MotorolaMB8611HnapParser")
        assert adapter is not None, "MB8611 should have modem.yaml config"
        hints = adapter.get_hnap_hints()
        assert hints is not None, "MB8611 should have hnap_hints in modem.yaml"

        required_keys = ["endpoint", "namespace", "empty_action_value"]
        for key in required_keys:
            assert key in hints, f"Missing {key} in MB8611 hnap_hints"

    def test_sb8200_js_auth_hints_complete(self):
        """Verify SB8200 modem.yaml has complete JS auth hints."""
        from custom_components.cable_modem_monitor.modem_config.adapter import get_auth_adapter_for_parser

        adapter = get_auth_adapter_for_parser("ArrisSB8200Parser")
        assert adapter is not None, "SB8200 should have modem.yaml config"
        hints = adapter.get_js_auth_hints()
        assert hints is not None, "SB8200 should have js_auth_hints in modem.yaml"

        required_keys = [
            "pattern",
            "login_page",
            "login_prefix",
            "session_cookie_name",
            "data_page",
            "token_prefix",
        ]
        for key in required_keys:
            assert key in hints, f"Missing {key} in SB8200 js_auth_hints"


class TestRealHARValidation:
    """Validate parser hints against real HAR-derived fixtures.

    These tests prevent regression by validating that parser configurations
    match actual observed modem behavior from HAR captures.

    Fixtures are sanitized extracts from real HAR files, committed to the repo.
    """

    def test_mb8611_empty_action_value_matches_fixture(self):
        """Verify MB8611 modem.yaml empty_action_value matches real HAR-derived fixture (v3.12.0+).

        This test prevents regression of the {} vs "" bug.
        Fixture extracted from real HAR capture and committed to fixtures/extended/.
        """
        # Load the committed fixture (extracted from real HAR)
        fixture = load_json_fixture(MB8611_FIXTURES / "extended/hnap_data_request.json")
        assert fixture is not None, "MB8611 HNAP request fixture should exist"

        # Verify fixture shows empty strings, not empty dicts
        actions = fixture.get("GetMultipleHNAPs", {})
        assert len(actions) > 0, "Fixture should have action entries"
        for action_name, action_value in actions.items():
            assert action_value == "", f"Fixture shows {action_name} should use empty string, got {action_value!r}"

        # Verify modem.yaml matches fixture
        from custom_components.cable_modem_monitor.modem_config.adapter import get_auth_adapter_for_parser

        adapter = get_auth_adapter_for_parser("MotorolaMB8611HnapParser")
        assert adapter is not None, "MB8611 should have modem.yaml config"
        hints = adapter.get_hnap_hints()
        assert hints is not None, "MB8611 should have hnap_hints in modem.yaml"
        assert hints["empty_action_value"] == "", (
            f"MB8611 modem.yaml empty_action_value should be '' to match fixture, "
            f"got {hints['empty_action_value']!r}"
        )

    def test_s33_empty_action_value_matches_parser(self):
        """Verify S33 modem.yaml uses empty string for action values (v3.12.0+).

        S33 was the first to use "" and is the reference implementation.
        """
        from custom_components.cable_modem_monitor.modem_config.adapter import get_auth_adapter_for_parser

        adapter = get_auth_adapter_for_parser("ArrisS33HnapParser")
        assert adapter is not None, "S33 should have modem.yaml config"
        hints = adapter.get_hnap_hints()
        assert hints is not None, "S33 should have hnap_hints in modem.yaml"
        assert (
            hints["empty_action_value"] == ""
        ), f"S33 modem.yaml empty_action_value should be '', got {hints['empty_action_value']!r}"

    def test_default_hnap_config_uses_empty_string(self):
        """Verify DEFAULT_HNAP_CONFIG uses empty string for action values.

        The default should match the observed behavior from real HAR captures.
        """
        from custom_components.cable_modem_monitor.core.auth.handler import DEFAULT_HNAP_CONFIG

        assert DEFAULT_HNAP_CONFIG["empty_action_value"] == "", (
            f"DEFAULT_HNAP_CONFIG empty_action_value should be '', "
            f"got {DEFAULT_HNAP_CONFIG['empty_action_value']!r}"
        )
