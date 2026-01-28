"""Tests for single-session modem behavior (max_concurrent=1).

Reproduces Issue #61: Netgear C7000v2 only allows one authenticated session.
The v3.13 refactor introduced a bug where setup_modem() creates two separate
sessions (connectivity check + auth check), causing auth to fail on single-session modems.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import requests

from custom_components.cable_modem_monitor.core.setup import setup_modem
from custom_components.cable_modem_monitor.modems.netgear.c7000v2.parser import (
    NetgearC7000v2Parser,
)

from .mock_handlers.form import TEST_PASSWORD, TEST_USERNAME
from .mock_modem_server import MockModemServer

# Path to C7000v2 modem fixtures
C7000V2_PATH = Path(__file__).parent.parent.parent / "modems" / "netgear" / "c7000v2"


class TestSessionLimit:
    """Test single-session modem behavior."""

    def test_single_session_allows_first_client(self):
        """First authenticated request should succeed."""
        with MockModemServer.from_modem_path(C7000V2_PATH, max_concurrent=1) as server:
            session = requests.Session()
            session.auth = (TEST_USERNAME, TEST_PASSWORD)
            session.verify = False
            session.headers["X-Mock-Client-ID"] = "client-1"

            resp = session.get(f"{server.url}/DocsisStatus.htm", timeout=5)
            assert resp.status_code == 200

    def test_single_session_blocks_second_client(self):
        """Second client should be blocked when max_concurrent=1."""
        with MockModemServer.from_modem_path(C7000V2_PATH, max_concurrent=1) as server:
            # First client authenticates
            session1 = requests.Session()
            session1.auth = (TEST_USERNAME, TEST_PASSWORD)
            session1.verify = False
            session1.headers["X-Mock-Client-ID"] = "client-1"
            resp1 = session1.get(f"{server.url}/DocsisStatus.htm", timeout=5)
            assert resp1.status_code == 200

            # Second client should be blocked
            session2 = requests.Session()
            session2.auth = (TEST_USERNAME, TEST_PASSWORD)
            session2.verify = False
            session2.headers["X-Mock-Client-ID"] = "client-2"
            resp2 = session2.get(f"{server.url}/DocsisStatus.htm", timeout=5)
            assert resp2.status_code == 503  # Service Unavailable

    def test_logout_releases_session(self):
        """Logout should allow new client to connect."""
        with MockModemServer.from_modem_path(C7000V2_PATH, max_concurrent=1) as server:
            # First client authenticates
            session1 = requests.Session()
            session1.auth = (TEST_USERNAME, TEST_PASSWORD)
            session1.verify = False
            session1.headers["X-Mock-Client-ID"] = "client-1"
            resp1 = session1.get(f"{server.url}/DocsisStatus.htm", timeout=5)
            assert resp1.status_code == 200

            # Second client is blocked
            session2 = requests.Session()
            session2.auth = (TEST_USERNAME, TEST_PASSWORD)
            session2.verify = False
            session2.headers["X-Mock-Client-ID"] = "client-2"
            resp2 = session2.get(f"{server.url}/DocsisStatus.htm", timeout=5)
            assert resp2.status_code == 503

            # Any client can trigger logout (clears all sessions)
            logout_resp = session1.get(f"{server.url}/Logout.htm", timeout=5)
            assert logout_resp.status_code == 200

            # Second client can now connect
            resp3 = session2.get(f"{server.url}/DocsisStatus.htm", timeout=5)
            assert resp3.status_code == 200

    def test_same_client_can_make_multiple_requests(self):
        """Same client should be able to make multiple requests."""
        with MockModemServer.from_modem_path(C7000V2_PATH, max_concurrent=1) as server:
            session = requests.Session()
            session.auth = (TEST_USERNAME, TEST_PASSWORD)
            session.verify = False
            session.headers["X-Mock-Client-ID"] = "client-1"

            # Multiple requests from same client should work
            for _ in range(3):
                resp = session.get(f"{server.url}/DocsisStatus.htm", timeout=5)
                assert resp.status_code == 200

    def test_unlimited_sessions_allows_multiple_clients(self):
        """With max_concurrent=0 (default), multiple clients should work."""
        with MockModemServer.from_modem_path(C7000V2_PATH, max_concurrent=0) as server:
            # Multiple clients should all succeed
            for i in range(3):
                session = requests.Session()
                session.auth = (TEST_USERNAME, TEST_PASSWORD)
                session.verify = False
                session.headers["X-Mock-Client-ID"] = f"client-{i}"
                resp = session.get(f"{server.url}/DocsisStatus.htm", timeout=5)
                assert resp.status_code == 200, f"Client {i} failed"


class TestSetupModemSessionBug:
    """Test that reproduces the setup_modem() session bug from Issue #61.

    The bug: setup_modem() calls check_connectivity() which creates Session #1,
    then creates Session #2 for auth. On single-session modems like C7000v2,
    Session #2 is blocked because Session #1 is still "active".
    """

    def test_setup_modem_works_with_ip_based_sessions(self):
        """Test that setup_modem works when sessions are tracked by IP.

        With IP-based session tracking (which Netgear may use), all requests
        from the same IP share a session slot. The connectivity check
        (unauthenticated) and auth check both come from localhost, so they
        don't conflict.

        Note: If the real C7000v2 tracks sessions differently (e.g., by
        authenticated connection), this test wouldn't reproduce the issue.
        The user's actual issue may be network-related (VPN, Docker, etc.)
        rather than a session limit bug.
        """
        with MockModemServer.from_modem_path(C7000V2_PATH, max_concurrent=1) as server:
            static_auth_config = {
                "auth_strategy": "basic_http",
                "timeout": 10,
            }
            host = server.url.replace("http://", "").replace("https://", "")

            result = setup_modem(
                host=host,
                parser_class=NetgearC7000v2Parser,
                static_auth_config=static_auth_config,
                username=TEST_USERNAME,
                password=TEST_PASSWORD,
            )

            # With IP-based tracking, this should succeed
            assert result.success is True
            assert result.working_url is not None
            assert "C7000v2" in result.parser_name
            assert len(result.modem_data["downstream"]) > 0

    @pytest.mark.skip(reason="Need to understand real Netgear session tracking first")
    def test_setup_modem_with_connection_based_sessions(self):
        """Test setup_modem if Netgear tracks sessions by TCP connection.

        If Netgear tracks sessions by TCP connection (not IP), then the
        connectivity check (which creates a new connection) and auth check
        (another new connection) would be seen as different clients.

        To test this properly, we'd need:
        1. A way to simulate connection-based session tracking in the mock
        2. Or actual testing against a real C7000v2 modem

        This test is skipped until we understand how Netgear actually
        tracks sessions.
        """
        pass  # Placeholder for future implementation
