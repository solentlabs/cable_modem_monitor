"""Unit tests for connectivity check SSL fallback behavior.

These tests verify that check_connectivity properly falls back
to legacy SSL when modern SSL fails with handshake errors.

Issue #81: The connectivity check was failing for legacy SSL modems because
it used plain requests without LegacySSLAdapter fallback.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import requests

# Patch requests in steps.py where check_connectivity is defined
STEPS_MODULE = "custom_components.cable_modem_monitor.core.discovery.steps"


def create_mock_session(head_side_effect=None, get_side_effect=None, response_status=200):
    """Create a mock session with configurable head/get behavior."""
    mock_session = MagicMock()
    mock_session.verify = False

    mock_response = MagicMock()
    mock_response.status_code = response_status

    if head_side_effect:
        mock_session.head.side_effect = head_side_effect
    else:
        mock_session.head.return_value = mock_response

    if get_side_effect:
        mock_session.get.side_effect = get_side_effect
    else:
        mock_session.get.return_value = mock_response

    return mock_session


class TestConnectivityCheckSSLFallback:
    """Tests for SSL fallback in connectivity check.

    Expected behavior:
    1. Try HTTPS with plain requests
    2. SSL handshake fails
    3. Try HTTPS with LegacySSLAdapter
    4. If that works, return success with legacy_ssl=True
    """

    def test_connectivity_check_should_fallback_on_ssl_handshake_error(self):
        """Verify connectivity check tries legacy SSL when modern fails."""
        from custom_components.cable_modem_monitor.core.discovery.pipeline import check_connectivity

        # Create an SSL handshake error
        ssl_error = requests.exceptions.SSLError(
            "HTTPSConnectionPool(host='192.168.100.1', port=443): "
            "Max retries exceeded with url: / "
            "(Caused by SSLError(SSLError(1, '[SSL: SSLV3_ALERT_HANDSHAKE_FAILURE] "
            "ssl/tls alert handshake failure (_ssl.c:1032)')))"
        )

        # First session fails with SSL error
        mock_failing_session = create_mock_session(head_side_effect=ssl_error, get_side_effect=ssl_error)

        # Legacy SSL session succeeds
        mock_legacy_session = create_mock_session(response_status=200)

        call_count = 0

        def mock_session_factory():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_failing_session  # First attempt - regular session fails
            return mock_legacy_session  # Second attempt - legacy SSL session succeeds

        with patch(f"{STEPS_MODULE}.requests.Session", side_effect=mock_session_factory):
            result = check_connectivity("https://192.168.100.1")

            # Should succeed with legacy SSL
            assert result.success is True, f"Should succeed with legacy SSL fallback. Error: {result.error}"
            assert result.error is None
            assert result.legacy_ssl is True, "Should indicate legacy SSL was needed"

    def test_connectivity_check_returns_false_for_non_ssl_errors(self):
        """Verify non-SSL errors still return failure (no false positives)."""
        from custom_components.cable_modem_monitor.core.discovery.pipeline import check_connectivity

        # Connection refused - not an SSL issue
        connection_error = requests.exceptions.ConnectionError("Connection refused")

        mock_session = create_mock_session(head_side_effect=connection_error, get_side_effect=connection_error)

        with patch(f"{STEPS_MODULE}.requests.Session", return_value=mock_session):
            result = check_connectivity("https://192.168.100.1")

            # This should correctly return False - connection is actually refused
            assert result.success is False
            assert result.error is not None
            assert result.legacy_ssl is False

    def test_modern_ssl_success_returns_legacy_false(self):
        """Verify successful modern SSL connection returns legacy_ssl=False."""
        from custom_components.cable_modem_monitor.core.discovery.pipeline import check_connectivity

        mock_session = create_mock_session(response_status=200)

        with patch(f"{STEPS_MODULE}.requests.Session", return_value=mock_session):
            result = check_connectivity("https://192.168.100.1")

            assert result.success is True
            assert result.error is None
            assert result.legacy_ssl is False, "Modern SSL should not set legacy_ssl=True"


class TestConnectivityCheckHTTPRedirectToHTTPS:
    """Tests for HTTP requests that redirect to HTTPS with legacy SSL.

    Some modems redirect HTTP to HTTPS. When this happens:
    1. requests.get("http://...") follows redirect to https://...
    2. HTTPS connection fails with SSL handshake error
    3. Connectivity check moves on to try HTTPS directly, which triggers legacy SSL
    """

    def test_https_only_with_ssl_error_falls_back_to_legacy(self):
        """Verify HTTPS-only URL that gets SSL error tries legacy SSL.

        When explicit HTTPS URL fails with SSL error, legacy SSL fallback should be tried.
        """
        from custom_components.cable_modem_monitor.core.discovery.pipeline import check_connectivity

        # SSL error that happens with modern SSL
        ssl_error = requests.exceptions.SSLError(
            "HTTPSConnectionPool(host='192.168.100.1', port=443): "
            "Max retries exceeded with url: / "
            "(Caused by SSLError(SSLError(1, '[SSL: SSLV3_ALERT_HANDSHAKE_FAILURE] "
            "ssl/tls alert handshake failure (_ssl.c:1032)')))"
        )

        # First session (modern SSL) fails with SSL error
        mock_failing_session = create_mock_session(head_side_effect=ssl_error, get_side_effect=ssl_error)

        # Legacy SSL session succeeds
        mock_legacy_session = create_mock_session(response_status=200)

        call_count = 0

        def mock_session_factory():
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # Modern SSL fails
                return mock_failing_session
            return mock_legacy_session  # Legacy SSL succeeds

        with patch(f"{STEPS_MODULE}.requests.Session", side_effect=mock_session_factory):
            # Use explicit HTTPS URL to ensure we don't fall back to HTTP
            result = check_connectivity("https://192.168.100.1")

            # Should succeed via legacy SSL
            assert result.success is True, f"Should succeed with legacy SSL fallback. Error: {result.error}"
            assert result.error is None
            assert result.legacy_ssl is True
            assert result.working_url is not None and "https" in result.working_url


class TestConnectivityCheckLogging:
    """Tests for connectivity check logging behavior.

    Verify that log levels are appropriate:
    - INFO: High-level flow (what we're doing, success)
    - DEBUG: Attempt details (fallback attempts, individual failures)
    - ERROR: Only when ALL attempts fail
    - WARNING: Should NOT be used for expected fallback behavior
    """

    def test_successful_connection_logs_at_info_not_warning(self, caplog):
        """Verify successful connection logs at INFO level, not WARNING."""
        from custom_components.cable_modem_monitor.core.discovery.pipeline import check_connectivity

        mock_session = create_mock_session(response_status=200)

        with (
            patch(f"{STEPS_MODULE}.requests.Session", return_value=mock_session),
            caplog.at_level(logging.DEBUG),
        ):
            result = check_connectivity("192.168.100.1")

        assert result.success is True

        # Should NOT have WARNING for successful connection
        warning_messages = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert not any(
            "Connected" in r.message for r in warning_messages
        ), "Success should not be logged at WARNING level"

    def test_fallback_attempts_log_at_info_not_warning(self, caplog):
        """Verify fallback attempts (HTTPS fail, HTTP succeed) log at DEBUG/INFO (not WARNING)."""
        from custom_components.cable_modem_monitor.core.discovery.pipeline import check_connectivity

        # HTTPS fails with connection refused (common for HTTP-only modems)
        connection_error = requests.exceptions.ConnectionError("Connection refused")

        mock_failing_session = create_mock_session(head_side_effect=connection_error, get_side_effect=connection_error)
        mock_success_session = create_mock_session(response_status=200)

        call_count = 0

        def mock_session_factory():
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # HTTPS fails
                return mock_failing_session
            return mock_success_session  # HTTP succeeds

        with (
            patch(f"{STEPS_MODULE}.requests.Session", side_effect=mock_session_factory),
            caplog.at_level(logging.DEBUG),
        ):
            result = check_connectivity("192.168.100.1")

        assert result.success is True

        # HTTPS failure should be logged at DEBUG, not WARNING
        warning_messages = [r for r in caplog.records if r.levelno == logging.WARNING]
        https_warnings = [r for r in warning_messages if "HTTPS" in r.message and "error" in r.message.lower()]
        assert (
            len(https_warnings) == 0
        ), f"HTTPS connection errors should be DEBUG, not WARNING. Found: {[r.message for r in https_warnings]}"

    def test_get_fallback_logs_at_info_not_warning(self, caplog):
        """Verify HEAD->GET fallback logs at DEBUG (not WARNING), success at INFO."""
        from custom_components.cable_modem_monitor.core.discovery.pipeline import check_connectivity

        # HEAD fails with connection reset (some modems reject HEAD)
        connection_reset = requests.RequestException("Connection reset by peer")

        mock_session = MagicMock()
        mock_session.verify = False

        mock_response = MagicMock()
        mock_response.status_code = 200

        # HEAD fails, GET succeeds
        mock_session.head.side_effect = connection_reset
        mock_session.get.return_value = mock_response

        with (
            patch(f"{STEPS_MODULE}.requests.Session", return_value=mock_session),
            caplog.at_level(logging.DEBUG),
        ):
            result = check_connectivity("http://192.168.100.1")

        assert result.success is True

        # Fallback retry should NOT be at WARNING
        warning_messages = [r for r in caplog.records if r.levelno == logging.WARNING]
        retry_warnings = [r for r in warning_messages if "fallback" in r.message.lower() or "Retrying" in r.message]
        assert (
            len(retry_warnings) == 0
        ), f"Fallback attempts should not be WARNING. Found: {[r.message for r in retry_warnings]}"

    def test_complete_failure_returns_error_result(self, caplog):
        """Verify complete failure returns correct error result.

        Note: check_connectivity logs failures at DEBUG level. ERROR logging
        happens in the pipeline orchestrator, not here.
        """
        from custom_components.cable_modem_monitor.core.discovery.pipeline import check_connectivity

        # All attempts fail
        connection_error = requests.exceptions.ConnectionError("Connection refused")

        mock_session = create_mock_session(head_side_effect=connection_error, get_side_effect=connection_error)

        with (
            patch(f"{STEPS_MODULE}.requests.Session", return_value=mock_session),
            caplog.at_level(logging.DEBUG),
        ):
            result = check_connectivity("192.168.100.1")

        assert result.success is False
        assert result.error is not None
        assert "192.168.100.1" in result.error

        # Failure details should be logged at DEBUG level
        debug_messages = [r for r in caplog.records if r.levelno == logging.DEBUG]
        assert len(debug_messages) > 0, "Connection attempts should be logged at DEBUG level"

    def test_legacy_ssl_success_logs_at_info(self, caplog):
        """Verify legacy SSL success logs appropriately."""
        from custom_components.cable_modem_monitor.core.discovery.pipeline import check_connectivity

        # SSL handshake error triggers legacy SSL fallback
        ssl_error = requests.exceptions.SSLError("ssl/tls alert handshake failure")

        # First session fails with SSL error
        mock_failing_session = create_mock_session(head_side_effect=ssl_error, get_side_effect=ssl_error)

        # Legacy SSL session succeeds
        mock_legacy_session = create_mock_session(response_status=200)

        call_count = 0

        def mock_session_factory():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_failing_session
            return mock_legacy_session

        with (
            patch(f"{STEPS_MODULE}.requests.Session", side_effect=mock_session_factory),
            caplog.at_level(logging.DEBUG),
        ):
            result = check_connectivity("https://192.168.100.1")

        assert result.success is True
        assert result.legacy_ssl is True

        # Legacy SSL attempt should NOT be at WARNING
        warning_messages = [r for r in caplog.records if r.levelno == logging.WARNING]
        legacy_warnings = [r for r in warning_messages if "legacy" in r.message.lower()]
        assert (
            len(legacy_warnings) == 0
        ), f"Legacy SSL attempts should not be WARNING. Found: {[r.message for r in legacy_warnings]}"
