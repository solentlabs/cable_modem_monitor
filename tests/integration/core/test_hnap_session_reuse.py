"""E2E test for HNAP session reuse in DataOrchestrator.

Validates that the orchestrator reuses existing HNAP sessions instead of
re-authenticating on every poll. Without session reuse, HNAP modems like the
S33 receive ~1440 logins/day, which can trigger anti-brute-force reboots.

Uses MockModemServer with the S33 modem config and HNAP auth handler.
Related: Issue #117.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from custom_components.cable_modem_monitor.core.auth.workflow import (
    AUTH_TYPE_TO_STRATEGY,
)
from custom_components.cable_modem_monitor.core.data_orchestrator import (
    DataOrchestrator,
)
from custom_components.cable_modem_monitor.core.parser_registry import (
    get_parser_by_name,
)
from custom_components.cable_modem_monitor.modem_config import (
    get_auth_adapter_for_parser,
)
from tests.integration.mock_handlers.hnap import TEST_PASSWORD, TEST_USERNAME
from tests.integration.mock_modem_server import MockModemServer

MODEMS_DIR = Path(__file__).parent.parent.parent.parent / "modems"
S33_PATH = MODEMS_DIR / "arris" / "s33"
TEST_TIMEOUT = 10


def _build_orchestrator(server_url: str) -> DataOrchestrator:
    """Build a DataOrchestrator configured for S33 HNAP auth."""
    parser_class = get_parser_by_name("Arris/CommScope S33")
    parser = parser_class()
    adapter = get_auth_adapter_for_parser(parser_class.__name__)
    hnap_config = adapter.get_auth_config_for_type("hnap")

    return DataOrchestrator(
        host=server_url,
        username=TEST_USERNAME,
        password=TEST_PASSWORD,
        parser=parser,
        auth_strategy=AUTH_TYPE_TO_STRATEGY["hnap"],
        auth_hnap_config=hnap_config,
        timeout=TEST_TIMEOUT,
    )


@pytest.mark.integration
class TestHnapSessionReuse:
    """E2E tests for HNAP session reuse across poll cycles."""

    def test_second_poll_reuses_session_skips_login(self):
        """Second poll reuses existing HNAP session — login called only once.

        Without session reuse, every poll calls _login() which performs
        a full HNAP challenge-response. This test verifies that the second
        poll detects valid session credentials (uid cookie + private key)
        and skips the login entirely.
        """
        with MockModemServer.from_modem_path(S33_PATH, auth_type="hnap") as server:
            orchestrator = _build_orchestrator(server.url)

            # Track login verification calls on the mock handler
            login_count = 0
            original_verify = server.handler._handle_login_verification

            def counting_verify(*args, **kwargs):
                nonlocal login_count
                login_count += 1
                return original_verify(*args, **kwargs)

            server.handler._handle_login_verification = counting_verify

            # First poll — full HNAP login
            result1 = orchestrator.get_modem_data()
            assert result1.get("cable_modem_connection_status") != "auth_failed", "First poll auth failed"
            assert login_count == 1, f"Expected 1 login on first poll, got {login_count}"

            # Session credentials should now exist
            assert (
                orchestrator._has_valid_session()
            ), "Expected valid session after first poll (uid cookie + private key)"

            # Second poll — should reuse session
            result2 = orchestrator.get_modem_data()
            assert result2.get("cable_modem_connection_status") != "auth_failed", "Second poll auth failed"
            assert login_count == 1, f"Expected login count to stay at 1 after second poll, got {login_count}"
            assert orchestrator._session_reused is True

    def test_first_poll_does_not_set_session_reused(self):
        """First poll performs fresh login — _session_reused should be False."""
        with MockModemServer.from_modem_path(S33_PATH, auth_type="hnap") as server:
            orchestrator = _build_orchestrator(server.url)

            result = orchestrator.get_modem_data()
            assert result.get("cable_modem_connection_status") != "auth_failed"
            assert orchestrator._session_reused is False

    def test_stale_session_retry_on_expired_session(self):
        """Expired session triggers cache clear + fresh login + successful retry.

        Simulates a modem reboot or session timeout: the orchestrator still has
        uid cookie + private key (so _has_valid_session() returns True), but the
        modem no longer recognizes the session. The stale retry logic should
        detect zero channels, clear auth cache, re-login, and succeed.
        """
        with MockModemServer.from_modem_path(S33_PATH, auth_type="hnap") as server:
            orchestrator = _build_orchestrator(server.url)

            # First poll — establish session
            result1 = orchestrator.get_modem_data()
            assert result1.get("cable_modem_connection_status") != "auth_failed", "First poll failed"

            # Simulate modem expiring the session (reboot, timeout, etc.)
            server.handler.authenticated_sessions.clear()

            # Track logins for the retry
            login_count = 0
            original_verify = server.handler._handle_login_verification

            def counting_verify(*args, **kwargs):
                nonlocal login_count
                login_count += 1
                return original_verify(*args, **kwargs)

            server.handler._handle_login_verification = counting_verify

            # Second poll — session reuse attempted, fails, retries with fresh login
            orchestrator.get_modem_data()

            # Retry should have re-authenticated
            assert login_count >= 1, "Expected at least 1 fresh login during retry"

    def test_capture_mode_always_does_fresh_login(self):
        """Capture mode bypasses session reuse to ensure clean diagnostic data."""
        with MockModemServer.from_modem_path(S33_PATH, auth_type="hnap") as server:
            orchestrator = _build_orchestrator(server.url)

            # First poll — establish session
            orchestrator.get_modem_data()
            assert orchestrator._has_valid_session()

            login_count = 0
            original_verify = server.handler._handle_login_verification

            def counting_verify(*args, **kwargs):
                nonlocal login_count
                login_count += 1
                return original_verify(*args, **kwargs)

            server.handler._handle_login_verification = counting_verify

            # Enable capture mode
            orchestrator._capture_enabled = True

            # Second poll in capture mode — should do fresh login despite valid session
            orchestrator.get_modem_data(capture_raw=True)
            assert login_count == 1, f"Expected fresh login in capture mode, got {login_count} logins"
            assert orchestrator._session_reused is False
