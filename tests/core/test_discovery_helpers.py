"""Tests for core/discovery_helpers.py."""

from __future__ import annotations

import time
from unittest.mock import Mock, patch

import pytest
import requests

from custom_components.cable_modem_monitor.core.base_parser import ModemParser
from custom_components.cable_modem_monitor.core.discovery_helpers import (
    AuthenticationError,
    CircuitBreakerError,
    DetectionError,
    DiscoveryCircuitBreaker,
    HintMatch,
    HintMatcher,
    ModemConnectionError,
    ParserHeuristics,
    ParserNotFoundError,
    SessionExpiredError,
)

# =============================================================================
# FIXTURES - Singleton state management
# =============================================================================


@pytest.fixture(autouse=True)
def reset_hint_matcher_singleton():
    """Reset HintMatcher singleton state after each test.

    This fixture ensures tests that manipulate HintMatcher._instance or
    HintMatcher._index don't pollute other tests in the suite.
    """
    # Save original state
    original_instance = HintMatcher._instance
    original_index = HintMatcher._index

    yield

    # Restore original state after test
    HintMatcher._instance = original_instance
    HintMatcher._index = original_index


# =============================================================================
# TEST DATA TABLES
# =============================================================================

# HintMatcher.match_pre_auth() test cases
# ┌─────────────────────────────────────┬────────────────────┬─────────────────────────────────────┐
# │ content                             │ expected_matches   │ description                         │
# ├─────────────────────────────────────┼────────────────────┼─────────────────────────────────────┤
# │ "arris sb8200 login"                │ ["ArrisSB8200..."] │ matches pre_auth pattern            │
# │ "generic router page"               │ []                 │ no match                            │
# │ ""                                  │ []                 │ empty content                       │
# │ "ARRIS SB8200" (uppercase)          │ ["ArrisSB8200..."] │ case insensitive                    │
# └─────────────────────────────────────┴────────────────────┴─────────────────────────────────────┘
#
# fmt: off
MATCH_PRE_AUTH_CASES = [
    # (index_data, content, expected_parser_names, description)
    (
        {"modems": {"ArrisSB8200Parser": {
            "manufacturer": "ARRIS", "model": "SB8200", "path": "arris/sb8200",
            "detection": {"pre_auth": ["sb8200", "arris"]}
        }}},
        "Welcome to ARRIS SB8200 Login",
        ["ArrisSB8200Parser"],
        "matches pre_auth patterns",
    ),
    (
        {"modems": {"ArrisSB8200Parser": {
            "manufacturer": "ARRIS", "model": "SB8200", "path": "arris/sb8200",
            "detection": {"pre_auth": ["sb8200"]}
        }}},
        "Generic router page",
        [],
        "no match when pattern not found",
    ),
    (
        {"modems": {"ArrisSB8200Parser": {
            "manufacturer": "ARRIS", "model": "SB8200", "path": "arris/sb8200",
            "detection": {"pre_auth": ["sb8200"]}
        }}},
        "",
        [],
        "empty content returns no matches",
    ),
    (
        {"modems": {"ArrisSB8200Parser": {
            "manufacturer": "ARRIS", "model": "SB8200", "path": "arris/sb8200",
            "detection": {"pre_auth": ["sb8200"]}
        }}},
        "SB8200 UPPERCASE TEST",
        ["ArrisSB8200Parser"],
        "case insensitive matching",
    ),
    (
        {"modems": {
            "Parser1": {"manufacturer": "A", "model": "1", "detection": {"pre_auth": ["pattern1", "pattern2"]}},
            "Parser2": {"manufacturer": "B", "model": "2", "detection": {"pre_auth": ["pattern1"]}}
        }},
        "content with pattern1 and pattern2",
        ["Parser1", "Parser2"],
        "multiple matches sorted by count",
    ),
    (
        {"modems": {"NoDetectionParser": {"manufacturer": "X", "model": "Y"}}},
        "any content",
        [],
        "parser without detection section",
    ),
]
# fmt: on

# HintMatcher.match_post_auth() test cases
# fmt: off
MATCH_POST_AUTH_CASES = [
    # (index_data, content, expected_parser_names, description)
    (
        {"modems": {"NetgearCM2000Parser": {
            "manufacturer": "Netgear", "model": "CM2000",
            "detection": {"post_auth": ["cm2000", "docsis 3.1"]}
        }}},
        "CM2000 Status Page - DOCSIS 3.1",
        ["NetgearCM2000Parser"],
        "matches post_auth patterns",
    ),
    (
        {"modems": {"NetgearCM2000Parser": {
            "manufacturer": "Netgear", "model": "CM2000",
            "detection": {"post_auth": ["cm2000"]}
        }}},
        "Some other modem page",
        [],
        "no match",
    ),
    (
        {"modems": {
            "Parser1": {"detection": {"post_auth": ["unique1"]}},
            "Parser2": {"detection": {"post_auth": ["unique2"]}}
        }},
        "page with unique1",
        ["Parser1"],
        "only matching parser returned",
    ),
]
# fmt: on

# HintMatcher.get_page_hint() test cases
# fmt: off
GET_PAGE_HINT_CASES = [
    # (index_data, parser_name, expected_hint, description)
    (
        {"modems": {"TestParser": {"detection": {"page_hint": "/status.html"}}}},
        "TestParser",
        "/status.html",
        "returns page_hint when present",
    ),
    (
        {"modems": {"TestParser": {"detection": {}}}},
        "TestParser",
        None,
        "returns None when no page_hint",
    ),
    (
        {"modems": {"OtherParser": {}}},
        "TestParser",
        None,
        "returns None for unknown parser",
    ),
    (
        {"modems": {}},
        "AnyParser",
        None,
        "returns None with empty index",
    ),
]
# fmt: on

# DiscoveryCircuitBreaker test cases
# fmt: off
CIRCUIT_BREAKER_CASES = [
    # (max_attempts, timeout, num_calls, expected_broken, description)
    (10, 60, 0,  False, "not broken initially"),
    (10, 60, 5,  False, "not broken at half attempts"),
    (10, 60, 10, True,  "broken at max attempts"),
    (10, 60, 15, True,  "stays broken after max"),
    (3,  60, 3,  True,  "custom max_attempts works"),
]
# fmt: on

# Exception test cases
# fmt: off
EXCEPTION_TROUBLESHOOTING_CASES = [
    # (exception_class, kwargs, expected_step_substring, description)
    (ParserNotFoundError, {}, "IP address", "parser not found has IP step"),
    (ParserNotFoundError, {}, "GitHub issue", "parser not found has GitHub step"),
    (AuthenticationError, {}, "username and password", "auth error has credentials step"),
    (AuthenticationError, {}, "web browser", "auth error has browser step"),
    (SessionExpiredError, {}, "temporary", "session expired mentions temporary"),
    (SessionExpiredError, {}, "polling interval", "session expired mentions polling"),
    (ModemConnectionError, {"message": "Connection failed"}, "192.168.100.1", "connection error has IP"),
    (ModemConnectionError, {"message": "Connection failed"}, "firewall", "connection error has firewall"),
    (
        CircuitBreakerError,
        {"stats": {"attempts": 5, "max_attempts": 10, "elapsed_seconds": 30.0, "timeout_seconds": 60}},
        "responsive",
        "circuit breaker has responsive step",
    ),
]
# fmt: on


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_index():
    """Create a mock modem index."""
    return {
        "modems": {
            "ArrisSB8200Parser": {
                "manufacturer": "ARRIS",
                "model": "SB8200",
                "path": "arris/sb8200",
                "detection": {
                    "pre_auth": ["sb8200", "arris surfboard"],
                    "post_auth": ["downstream bonded channels", "upstream bonded channels"],
                    "page_hint": "/cmconnectionstatus.html",
                },
            },
            "NetgearCM2000Parser": {
                "manufacturer": "Netgear",
                "model": "CM2000",
                "path": "netgear/cm2000",
                "detection": {
                    "pre_auth": ["cm2000", "netgear"],
                    "post_auth": ["ofdm downstream", "ofdma upstream"],
                },
            },
        }
    }


@pytest.fixture
def hint_matcher(mock_index):
    """Create HintMatcher with mocked index."""
    # Reset singleton state
    HintMatcher._instance = None
    HintMatcher._index = None

    with patch.object(HintMatcher, "_load_index"):
        matcher = HintMatcher()
        HintMatcher._index = mock_index
        return matcher


@pytest.fixture
def mock_parser_class():
    """Create a mock parser class."""

    class MockParser(ModemParser):
        name = "Mock Parser"
        manufacturer = "MockCorp"
        models = ["MOCK100"]

        def parse_resources(self, resources):
            return {"downstream": [], "upstream": [], "system_info": {}}

        def parse(self, soup, session=None, base_url=None):
            return {}

    return MockParser


# =============================================================================
# HINT MATCHER TESTS
# =============================================================================


class TestHintMatch:
    """Tests for HintMatch dataclass."""

    def test_hint_match_creation(self):
        """Test creating a HintMatch."""
        match = HintMatch(
            parser_name="TestParser",
            manufacturer="TestCorp",
            model="T100",
            path="test/t100",
            matched_markers=["pattern1", "pattern2"],
        )

        assert match.parser_name == "TestParser"
        assert match.manufacturer == "TestCorp"
        assert match.model == "T100"
        assert match.path == "test/t100"
        assert match.matched_markers == ["pattern1", "pattern2"]


class TestHintMatcherMatchPreAuth:
    """Tests for HintMatcher.match_pre_auth method."""

    @pytest.mark.parametrize("index_data,content,expected_names,desc", MATCH_PRE_AUTH_CASES)
    def test_match_pre_auth(self, index_data, content, expected_names, desc):
        """Test match_pre_auth with various inputs."""
        # Reset singleton
        HintMatcher._instance = None
        HintMatcher._index = None

        with patch.object(HintMatcher, "_load_index"):
            matcher = HintMatcher()
            HintMatcher._index = index_data

        matches = matcher.match_pre_auth(content)
        matched_names = [m.parser_name for m in matches]

        # Check expected parsers are in results (order may vary for equal counts)
        for name in expected_names:
            assert name in matched_names, f"Failed for: {desc}"
        assert len(matches) == len(expected_names), f"Failed for: {desc}"

    def test_match_pre_auth_returns_empty_when_no_index(self):
        """Test match_pre_auth returns empty list when index is None."""
        HintMatcher._instance = None
        HintMatcher._index = None

        with patch.object(HintMatcher, "_load_index"):
            matcher = HintMatcher()
            HintMatcher._index = None

        matches = matcher.match_pre_auth("any content")
        assert matches == []

    def test_match_login_markers_alias(self, hint_matcher):
        """Test backwards compatibility alias."""
        # match_login_markers should be same as match_pre_auth
        assert hint_matcher.match_login_markers == hint_matcher.match_pre_auth


class TestHintMatcherMatchPostAuth:
    """Tests for HintMatcher.match_post_auth method."""

    @pytest.mark.parametrize("index_data,content,expected_names,desc", MATCH_POST_AUTH_CASES)
    def test_match_post_auth(self, index_data, content, expected_names, desc):
        """Test match_post_auth with various inputs."""
        HintMatcher._instance = None
        HintMatcher._index = None

        with patch.object(HintMatcher, "_load_index"):
            matcher = HintMatcher()
            HintMatcher._index = index_data

        matches = matcher.match_post_auth(content)
        matched_names = [m.parser_name for m in matches]

        for name in expected_names:
            assert name in matched_names, f"Failed for: {desc}"
        assert len(matches) == len(expected_names), f"Failed for: {desc}"

    def test_match_post_auth_returns_empty_when_no_index(self):
        """Test match_post_auth returns empty when index is None."""
        HintMatcher._instance = None
        HintMatcher._index = None

        with patch.object(HintMatcher, "_load_index"):
            matcher = HintMatcher()
            HintMatcher._index = None

        matches = matcher.match_post_auth("any content")
        assert matches == []

    def test_match_model_strings_alias(self, hint_matcher):
        """Test backwards compatibility alias."""
        assert hint_matcher.match_model_strings == hint_matcher.match_post_auth


class TestHintMatcherGetPageHint:
    """Tests for HintMatcher.get_page_hint method."""

    @pytest.mark.parametrize("index_data,parser_name,expected,desc", GET_PAGE_HINT_CASES)
    def test_get_page_hint(self, index_data, parser_name, expected, desc):
        """Test get_page_hint with various inputs."""
        HintMatcher._instance = None
        HintMatcher._index = None

        with patch.object(HintMatcher, "_load_index"):
            matcher = HintMatcher()
            HintMatcher._index = index_data

        result = matcher.get_page_hint(parser_name)
        assert result == expected, f"Failed for: {desc}"

    def test_get_page_hint_returns_none_when_no_index(self):
        """Test get_page_hint returns None when index is None."""
        HintMatcher._instance = None
        HintMatcher._index = None

        with patch.object(HintMatcher, "_load_index"):
            matcher = HintMatcher()
            HintMatcher._index = None

        result = matcher.get_page_hint("AnyParser")
        assert result is None


class TestHintMatcherGetAllModems:
    """Tests for HintMatcher.get_all_modems method."""

    def test_get_all_modems(self, hint_matcher, mock_index):
        """Test get_all_modems returns all entries."""
        modems = hint_matcher.get_all_modems()

        assert len(modems) == 2
        parser_names = [m["parser_name"] for m in modems]
        assert "ArrisSB8200Parser" in parser_names
        assert "NetgearCM2000Parser" in parser_names

    def test_get_all_modems_returns_empty_when_no_index(self):
        """Test get_all_modems returns empty when index is None."""
        HintMatcher._instance = None
        HintMatcher._index = None

        with patch.object(HintMatcher, "_load_index"):
            matcher = HintMatcher()
            HintMatcher._index = None

        modems = matcher.get_all_modems()
        assert modems == []


class TestHintMatcherSingleton:
    """Tests for HintMatcher singleton pattern."""

    def test_get_instance_returns_singleton(self):
        """Test get_instance returns same instance."""
        HintMatcher._instance = None
        HintMatcher._index = {"modems": {}}

        with patch.object(HintMatcher, "_load_index"):
            instance1 = HintMatcher.get_instance()
            instance2 = HintMatcher.get_instance()

        assert instance1 is instance2

    def test_load_index_handles_file_not_found(self):
        """Test _load_index handles missing file gracefully."""
        HintMatcher._instance = None
        HintMatcher._index = None

        with patch("builtins.open", side_effect=FileNotFoundError()):
            HintMatcher()

        assert HintMatcher._index == {"modems": {}}

    def test_load_index_handles_yaml_error(self):
        """Test _load_index handles YAML parse errors."""
        HintMatcher._instance = None
        HintMatcher._index = None

        with patch("builtins.open", side_effect=Exception("YAML error")):
            HintMatcher()

        assert HintMatcher._index == {"modems": {}}


# =============================================================================
# PARSER HEURISTICS TESTS
# =============================================================================


class TestParserHeuristicsGetLikelyParsers:
    """Tests for ParserHeuristics.get_likely_parsers method."""

    def test_returns_likely_parsers_first(self, mock_parser_class):
        """Test likely parsers are returned before unlikely ones."""

        class ArrisParser(ModemParser):
            name = "ARRIS SB8200"
            manufacturer = "ARRIS"
            models = ["SB8200"]

            def parse(self, soup, session=None, base_url=None):
                return {}

        class NetgearParser(ModemParser):
            name = "Netgear CM2000"
            manufacturer = "Netgear"
            models = ["CM2000"]

            def parse(self, soup, session=None, base_url=None):
                return {}

        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><title>ARRIS</title><body>ARRIS SB8200</body></html>"
        mock_session.get.return_value = mock_response

        parsers = [NetgearParser, ArrisParser]
        result = ParserHeuristics.get_likely_parsers("http://192.168.100.1", parsers, mock_session, verify_ssl=False)

        # ARRIS should be first (likely), Netgear second (unlikely)
        assert result[0] == ArrisParser

    def test_returns_all_parsers_on_non_200_response(self, mock_parser_class):
        """Test returns all parsers when root page returns non-200."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 401
        mock_session.get.return_value = mock_response

        parsers = [mock_parser_class]
        result = ParserHeuristics.get_likely_parsers("http://192.168.100.1", parsers, mock_session)

        assert result == parsers

    def test_returns_all_parsers_on_request_exception(self, mock_parser_class):
        """Test returns all parsers when request fails."""
        mock_session = Mock()
        mock_session.get.side_effect = requests.RequestException("Connection failed")

        parsers = [mock_parser_class]
        result = ParserHeuristics.get_likely_parsers("http://192.168.100.1", parsers, mock_session)

        assert result == parsers

    def test_matches_model_numbers(self):
        """Test matching by model number in HTML."""

        class TestParser(ModemParser):
            name = "Test"
            manufacturer = "Unknown"
            models = ["XYZ-9000"]

            def parse(self, soup, session=None, base_url=None):
                return {}

        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Model: XYZ-9000</body></html>"
        mock_session.get.return_value = mock_response

        result = ParserHeuristics.get_likely_parsers("http://192.168.100.1", [TestParser], mock_session)

        assert TestParser in result


class TestParserHeuristicsCheckAnonymousAccess:
    """Tests for ParserHeuristics.check_anonymous_access method."""

    def test_returns_html_for_public_url(self):
        """Test returns HTML when public URL accessible."""

        class ParserWithPublicUrl(ModemParser):
            name = "Test"
            manufacturer = "Test"
            models = []

            def parse(self, soup, session=None, base_url=None):
                return {}

        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html>Public page</html>"
        mock_session.get.return_value = mock_response

        with patch(
            "custom_components.cable_modem_monitor.core.discovery_helpers.get_url_patterns_for_parser",
            return_value=[{"path": "/public.html", "auth_required": False}],
        ):
            result = ParserHeuristics.check_anonymous_access("http://192.168.100.1", ParserWithPublicUrl, mock_session)

        assert result is not None
        assert result[0] == "<html>Public page</html>"
        assert result[1] == "http://192.168.100.1/public.html"

    def test_returns_none_when_no_url_patterns(self, mock_parser_class):
        """Test returns None when parser has no URL patterns."""
        mock_session = Mock()

        with patch(
            "custom_components.cable_modem_monitor.core.discovery_helpers.get_url_patterns_for_parser",
            return_value=None,
        ):
            result = ParserHeuristics.check_anonymous_access("http://192.168.100.1", mock_parser_class, mock_session)

        assert result is None

    def test_returns_none_when_all_urls_require_auth(self, mock_parser_class):
        """Test returns None when all URLs require auth."""
        mock_session = Mock()

        with patch(
            "custom_components.cable_modem_monitor.core.discovery_helpers.get_url_patterns_for_parser",
            return_value=[{"path": "/protected.html", "auth_required": True}],
        ):
            result = ParserHeuristics.check_anonymous_access("http://192.168.100.1", mock_parser_class, mock_session)

        assert result is None

    def test_handles_request_exception(self, mock_parser_class):
        """Test handles request exceptions gracefully."""
        mock_session = Mock()
        mock_session.get.side_effect = requests.RequestException("Timeout")

        with patch(
            "custom_components.cable_modem_monitor.core.discovery_helpers.get_url_patterns_for_parser",
            return_value=[{"path": "/public.html", "auth_required": False}],
        ):
            result = ParserHeuristics.check_anonymous_access("http://192.168.100.1", mock_parser_class, mock_session)

        assert result is None


class TestParserHeuristicsCheckAuthenticatedAccess:
    """Tests for ParserHeuristics.check_authenticated_access method."""

    def test_returns_html_for_protected_url(self, mock_parser_class):
        """Test returns HTML when protected URL accessible with session."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html>Protected page</html>"
        mock_session.get.return_value = mock_response

        with patch(
            "custom_components.cable_modem_monitor.core.discovery_helpers.get_url_patterns_for_parser",
            return_value=[{"path": "/status.html", "auth_required": True}],
        ):
            result = ParserHeuristics.check_authenticated_access(
                "http://192.168.100.1", mock_parser_class, mock_session
            )

        assert result is not None
        assert result[0] == "<html>Protected page</html>"

    def test_skips_static_assets(self, mock_parser_class):
        """Test skips CSS, JS, and image files."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html>Page</html>"
        mock_session.get.return_value = mock_response

        with patch(
            "custom_components.cable_modem_monitor.core.discovery_helpers.get_url_patterns_for_parser",
            return_value=[
                {"path": "/style.css", "auth_required": True},
                {"path": "/script.js", "auth_required": True},
                {"path": "/logo.png", "auth_required": True},
                {"path": "/status.html", "auth_required": True},
            ],
        ):
            ParserHeuristics.check_authenticated_access("http://192.168.100.1", mock_parser_class, mock_session)

        # Should only try status.html, not static assets
        assert mock_session.get.call_count == 1
        call_url = mock_session.get.call_args[0][0]
        assert call_url.endswith("/status.html")

    def test_returns_none_when_no_url_patterns(self, mock_parser_class):
        """Test returns None when no URL patterns."""
        mock_session = Mock()

        with patch(
            "custom_components.cable_modem_monitor.core.discovery_helpers.get_url_patterns_for_parser",
            return_value=None,
        ):
            result = ParserHeuristics.check_authenticated_access(
                "http://192.168.100.1", mock_parser_class, mock_session
            )

        assert result is None


# =============================================================================
# DISCOVERY CIRCUIT BREAKER TESTS
# =============================================================================


class TestDiscoveryCircuitBreaker:
    """Tests for DiscoveryCircuitBreaker class."""

    @pytest.mark.parametrize("max_attempts,timeout,num_calls,expected_broken,desc", CIRCUIT_BREAKER_CASES)
    def test_circuit_breaker_attempts(self, max_attempts, timeout, num_calls, expected_broken, desc):
        """Test circuit breaker breaks at max attempts."""
        breaker = DiscoveryCircuitBreaker(max_attempts=max_attempts, timeout_seconds=timeout)

        for i in range(num_calls):
            breaker.should_continue()
            breaker.record_attempt(f"parser_{i}")

        # Call should_continue one more time to check state
        breaker.should_continue()
        assert breaker.is_broken() == expected_broken, f"Failed for: {desc}"

    def test_initial_state(self):
        """Test circuit breaker initial state."""
        breaker = DiscoveryCircuitBreaker()

        assert breaker.attempts == 0
        assert breaker.start_time == 0.0
        assert not breaker.is_broken()

    def test_should_continue_starts_timer_once(self):
        """Test should_continue only starts timer on first call."""
        breaker = DiscoveryCircuitBreaker()

        breaker.should_continue()
        first_start = breaker.start_time

        time.sleep(0.01)
        breaker.should_continue()
        second_start = breaker.start_time

        # Timer should not reset
        assert first_start == second_start

    def test_timeout_breaks_circuit(self):
        """Test circuit breaks on timeout."""
        breaker = DiscoveryCircuitBreaker(max_attempts=100, timeout_seconds=0)

        # First call starts timer
        breaker.should_continue()
        # Second call should detect timeout (0 seconds)
        time.sleep(0.01)
        result = breaker.should_continue()

        assert result is False
        assert breaker.is_broken()

    def test_record_attempt_increments_counter(self):
        """Test record_attempt increments attempt counter."""
        breaker = DiscoveryCircuitBreaker()

        breaker.record_attempt("parser1")
        assert breaker.attempts == 1

        breaker.record_attempt("parser2")
        assert breaker.attempts == 2

    def test_get_stats(self):
        """Test get_stats returns correct information."""
        breaker = DiscoveryCircuitBreaker(max_attempts=5, timeout_seconds=30)
        breaker.should_continue()
        breaker.record_attempt("test")

        stats = breaker.get_stats()

        assert stats["attempts"] == 1
        assert stats["max_attempts"] == 5
        assert stats["timeout_seconds"] == 30
        assert stats["is_broken"] is False
        assert "elapsed_seconds" in stats

    def test_stays_broken_after_breaking(self):
        """Test circuit stays broken once broken."""
        breaker = DiscoveryCircuitBreaker(max_attempts=1)

        breaker.should_continue()
        breaker.record_attempt()
        breaker.should_continue()  # This breaks the circuit

        # Multiple calls should all return False
        assert breaker.should_continue() is False
        assert breaker.should_continue() is False
        assert breaker.is_broken()


# =============================================================================
# EXCEPTION TESTS
# =============================================================================


class TestDetectionError:
    """Tests for DetectionError base class."""

    def test_creation_with_message(self):
        """Test creating DetectionError with message."""
        error = DetectionError("Test error")

        assert str(error) == "Test error"
        assert error.diagnostics == {}

    def test_creation_with_diagnostics(self):
        """Test creating DetectionError with diagnostics."""
        diag = {"key": "value", "count": 42}
        error = DetectionError("Test error", diagnostics=diag)

        assert error.diagnostics == diag

    def test_get_user_message(self):
        """Test get_user_message returns string representation."""
        error = DetectionError("User-friendly message")
        assert error.get_user_message() == "User-friendly message"

    def test_get_troubleshooting_steps_default(self):
        """Test base class returns empty troubleshooting steps."""
        error = DetectionError("Error")
        assert error.get_troubleshooting_steps() == []


class TestParserNotFoundError:
    """Tests for ParserNotFoundError exception."""

    def test_exception_creation_default(self):
        """Test creating ParserNotFoundError with defaults."""
        error = ParserNotFoundError()

        assert str(error) == "Could not detect modem type. No parser matched."
        assert isinstance(error, Exception)
        assert error.modem_info == {}
        assert error.attempted_parsers == []

    def test_exception_with_modem_info(self):
        """Test creating ParserNotFoundError with modem info."""
        modem_info = {"title": "Acme Router-1000", "model": "Router-1000"}
        error = ParserNotFoundError(modem_info=modem_info)

        assert str(error) == "Could not detect modem type. No parser matched."
        assert error.modem_info == modem_info
        assert error.modem_info["title"] == "Acme Router-1000"

    def test_exception_with_attempted_parsers(self):
        """Test exception with list of attempted parsers."""
        attempted = ["AcmeRouter2000", "AcmeRouter1000", "GenericParser"]
        error = ParserNotFoundError(attempted_parsers=attempted)

        assert str(error) == "Could not detect modem type. No parser matched."
        assert error.attempted_parsers == attempted
        assert len(error.attempted_parsers) == 3

    def test_exception_can_be_raised(self):
        """Test that exception can be raised and caught."""
        with pytest.raises(ParserNotFoundError) as exc_info:
            raise ParserNotFoundError()

        error_msg = str(exc_info.value)
        assert "Could not detect modem type" in error_msg
        assert "No parser matched" in error_msg

    def test_get_user_message(self):
        """Test user-friendly error message generation."""
        modem_info = {"title": "Acme Gateway-3000"}
        attempted = ["AcmeGateway2000", "GenericParser"]
        error = ParserNotFoundError(modem_info=modem_info, attempted_parsers=attempted)

        user_message = error.get_user_message()

        assert "Acme Gateway-3000" in user_message
        assert "Tried 2 parsers" in user_message
        assert "not be supported" in user_message

    def test_get_troubleshooting_steps(self):
        """Test troubleshooting steps are provided."""
        error = ParserNotFoundError()
        steps = error.get_troubleshooting_steps()

        assert isinstance(steps, list)
        assert len(steps) > 0
        assert any("IP address" in step for step in steps)
        assert any("GitHub issue" in step for step in steps)

    def test_exception_with_full_context(self):
        """Test exception with complete context information."""
        modem_info = {
            "title": "Acme Modem-9000",
            "manufacturer": "Acme",
            "model": "Modem-9000",
        }
        attempted = ["AcmeModem8000", "AcmeModem7000", "GenericAcme"]

        error = ParserNotFoundError(modem_info=modem_info, attempted_parsers=attempted)

        assert error.modem_info["manufacturer"] == "Acme"
        assert error.modem_info["model"] == "Modem-9000"
        assert "AcmeModem8000" in error.attempted_parsers

        user_msg = error.get_user_message()
        assert "Modem-9000" in user_msg
        assert "3 parsers" in user_msg


class TestAuthenticationError:
    """Tests for AuthenticationError exception."""

    def test_default_message(self):
        """Test default error message."""
        error = AuthenticationError()
        assert str(error) == "Authentication failed"

    def test_custom_message(self):
        """Test custom error message."""
        error = AuthenticationError("Invalid credentials for admin user")
        assert str(error) == "Invalid credentials for admin user"

    def test_troubleshooting_steps(self):
        """Test troubleshooting steps."""
        error = AuthenticationError()
        steps = error.get_troubleshooting_steps()

        assert len(steps) > 0
        assert any("username and password" in step for step in steps)
        assert any("web browser" in step for step in steps)


class TestSessionExpiredError:
    """Tests for SessionExpiredError exception."""

    def test_default_message(self):
        """Test default error message."""
        error = SessionExpiredError()
        assert "Session expired" in str(error)

    def test_message_with_indicator(self):
        """Test message includes indicator."""
        error = SessionExpiredError(indicator="UN-AUTH")
        assert "UN-AUTH" in str(error)

    def test_troubleshooting_steps(self):
        """Test troubleshooting steps."""
        error = SessionExpiredError()
        steps = error.get_troubleshooting_steps()

        assert len(steps) > 0
        assert any("temporary" in step for step in steps)
        assert any("polling interval" in step for step in steps)


class TestModemConnectionError:
    """Tests for ModemConnectionError exception."""

    def test_creation(self):
        """Test creating ModemConnectionError."""
        error = ModemConnectionError("Cannot connect to 192.168.100.1")
        assert str(error) == "Cannot connect to 192.168.100.1"

    def test_troubleshooting_steps(self):
        """Test troubleshooting steps include common IPs."""
        error = ModemConnectionError("Connection failed")
        steps = error.get_troubleshooting_steps()

        assert len(steps) > 0
        assert any("192.168.100.1" in step for step in steps)
        assert any("firewall" in step for step in steps)


class TestCircuitBreakerError:
    """Tests for CircuitBreakerError exception."""

    def test_creation_with_stats(self):
        """Test creating with stats dict."""
        stats = {
            "attempts": 10,
            "max_attempts": 10,
            "elapsed_seconds": 45.5,
            "timeout_seconds": 60,
            "is_broken": True,
        }
        error = CircuitBreakerError(stats)

        assert "10" in str(error)
        assert "45.5" in str(error)
        assert error.stats == stats

    def test_get_user_message(self):
        """Test user-friendly message."""
        stats = {
            "attempts": 5,
            "max_attempts": 10,
            "elapsed_seconds": 30.0,
            "timeout_seconds": 60,
        }
        error = CircuitBreakerError(stats)
        msg = error.get_user_message()

        assert "5/10" in msg
        assert "30.0" in msg
        assert "60" in msg

    def test_troubleshooting_steps(self):
        """Test troubleshooting steps."""
        stats = {"attempts": 1, "max_attempts": 1, "elapsed_seconds": 1, "timeout_seconds": 1}
        error = CircuitBreakerError(stats)
        steps = error.get_troubleshooting_steps()

        assert len(steps) > 0
        assert any("responsive" in step for step in steps)
        assert any("manually selecting" in step for step in steps)


class TestExceptionTroubleshootingSteps:
    """Parameterized tests for exception troubleshooting steps."""

    @pytest.mark.parametrize("exc_class,kwargs,expected_substring,desc", EXCEPTION_TROUBLESHOOTING_CASES)
    def test_troubleshooting_contains_expected_step(self, exc_class, kwargs, expected_substring, desc):
        """Test each exception has expected troubleshooting content."""
        error = exc_class(**kwargs)
        steps = error.get_troubleshooting_steps()

        found = any(expected_substring in step for step in steps)
        assert found, f"Failed for: {desc} - expected '{expected_substring}' in steps: {steps}"
