"""Tests for connectivity — protocol detection and health probes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import requests

# Alias to avoid pytest collecting these as test functions
from solentlabs.cable_modem_monitor_core.connectivity import (
    ConnectivityResult,
    LegacySSLAdapter,
    create_session,
    detect_protocol,
    test_http_head as probe_http_head,
    test_icmp as probe_icmp,
)

# =====================================================================
# detect_protocol()
# =====================================================================

# ┌──────────────────────┬──────────────┬───────────┬────────────────────┐
# │ scenario             │ http resp    │ https     │ expected           │
# ├──────────────────────┼──────────────┼───────────┼────────────────────┤
# │ http_works           │ 200          │ —         │ http, no legacy    │
# │ http_401             │ 401          │ —         │ http, no legacy    │
# │ https_only           │ ConnErr      │ 200       │ https, no legacy   │
# │ https_legacy         │ ConnErr      │ SSLError  │ https, legacy=True │
# │ all_fail             │ ConnErr      │ ConnErr   │ success=False      │
# │ explicit_https       │ —            │ 200       │ https, no legacy   │
# └──────────────────────┴──────────────┴───────────┴────────────────────┘


class TestDetectProtocol:
    """Protocol detection with mocked network I/O."""

    def _mock_session(self, head_effect: object = None, get_effect: object = None) -> MagicMock:
        """Create a mock session with configurable head/get behavior."""
        session = MagicMock()
        session.verify = False

        if head_effect is not None:
            if isinstance(head_effect, Exception):
                session.head.side_effect = head_effect
            else:
                resp = MagicMock()
                resp.status_code = head_effect
                session.head.return_value = resp

        if get_effect is not None:
            if isinstance(get_effect, Exception):
                session.get.side_effect = get_effect
            else:
                resp = MagicMock()
                resp.status_code = get_effect
                session.get.return_value = resp

        return session

    @patch("solentlabs.cable_modem_monitor_core.connectivity.create_session")
    def test_http_works(self, mock_create: MagicMock) -> None:
        """HTTP 200 response detected as http protocol."""
        mock_create.return_value = self._mock_session(head_effect=200)

        result = detect_protocol("192.168.100.1")

        assert result.success is True
        assert result.protocol == "http"
        assert result.legacy_ssl is False
        assert result.working_url == "http://192.168.100.1"

    @patch("solentlabs.cable_modem_monitor_core.connectivity.create_session")
    def test_http_401_is_reachable(self, mock_create: MagicMock) -> None:
        """HTTP 401 counts as reachable (auth required, but modem is up)."""
        mock_create.return_value = self._mock_session(head_effect=401)

        result = detect_protocol("192.168.100.1")

        assert result.success is True
        assert result.protocol == "http"

    @patch("solentlabs.cable_modem_monitor_core.connectivity.create_session")
    def test_https_fallback(self, mock_create: MagicMock) -> None:
        """When HTTP fails, HTTPS fallback works."""
        http_session = self._mock_session(
            head_effect=requests.exceptions.ConnectionError(),
            get_effect=requests.exceptions.ConnectionError(),
        )
        https_session = self._mock_session(head_effect=200)
        mock_create.side_effect = [http_session, https_session]

        result = detect_protocol("192.168.100.1")

        assert result.success is True
        assert result.protocol == "https"
        assert result.legacy_ssl is False

    @patch("solentlabs.cable_modem_monitor_core.connectivity.create_session")
    def test_https_legacy_ssl(self, mock_create: MagicMock) -> None:
        """Legacy SSL fallback when HTTPS with modern ciphers fails."""
        http_session = self._mock_session(
            head_effect=requests.exceptions.ConnectionError(),
            get_effect=requests.exceptions.ConnectionError(),
        )
        https_session = self._mock_session(
            head_effect=requests.exceptions.SSLError("handshake failure"),
        )
        legacy_session = self._mock_session(get_effect=200)
        mock_create.side_effect = [http_session, https_session, legacy_session]

        result = detect_protocol("192.168.100.1")

        assert result.success is True
        assert result.protocol == "https"
        assert result.legacy_ssl is True

    @patch("solentlabs.cable_modem_monitor_core.connectivity.create_session")
    def test_all_fail(self, mock_create: MagicMock) -> None:
        """All protocols fail returns success=False."""
        fail_session = self._mock_session(
            head_effect=requests.exceptions.ConnectionError(),
            get_effect=requests.exceptions.ConnectionError(),
        )
        mock_create.return_value = fail_session

        result = detect_protocol("192.168.100.1")

        assert result.success is False
        assert result.error is not None
        assert "192.168.100.1" in result.error

    @patch("solentlabs.cable_modem_monitor_core.connectivity.create_session")
    def test_explicit_protocol_skips_detection(self, mock_create: MagicMock) -> None:
        """User-specified protocol prefix — only that protocol is tried."""
        mock_create.return_value = self._mock_session(head_effect=200)

        result = detect_protocol("https://192.168.100.1")

        assert result.success is True
        assert result.protocol == "https"
        # Only one session created (not two for http + https)
        assert mock_create.call_count == 1


# =====================================================================
# probe_icmp()
# =====================================================================


class TestIcmp:
    """ICMP ping probe."""

    @patch("solentlabs.cable_modem_monitor_core.connectivity.subprocess.run")
    def test_ping_success(self, mock_run: MagicMock) -> None:
        """Successful ping returns True."""
        mock_run.return_value = MagicMock(returncode=0)
        assert probe_icmp("192.168.100.1") is True

    @patch("solentlabs.cable_modem_monitor_core.connectivity.subprocess.run")
    def test_ping_blocked(self, mock_run: MagicMock) -> None:
        """Blocked/timeout ping returns False."""
        mock_run.return_value = MagicMock(returncode=1)
        assert probe_icmp("192.168.100.1") is False

    @patch("solentlabs.cable_modem_monitor_core.connectivity.subprocess.run")
    def test_ping_exception(self, mock_run: MagicMock) -> None:
        """Exception during ping returns False."""
        mock_run.side_effect = FileNotFoundError("ping not found")
        assert probe_icmp("192.168.100.1") is False


# =====================================================================
# probe_http_head()
# =====================================================================


class TestHttpHead:
    """HTTP HEAD probe."""

    @patch("solentlabs.cable_modem_monitor_core.connectivity.create_session")
    def test_head_success(self, mock_create: MagicMock) -> None:
        """HEAD 200 returns True."""
        session = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        session.head.return_value = resp
        mock_create.return_value = session

        assert probe_http_head("http://192.168.100.1") is True

    @patch("solentlabs.cable_modem_monitor_core.connectivity.create_session")
    def test_head_403_is_ok(self, mock_create: MagicMock) -> None:
        """HEAD 403 is still considered supported (status < 500)."""
        session = MagicMock()
        resp = MagicMock()
        resp.status_code = 403
        session.head.return_value = resp
        mock_create.return_value = session

        assert probe_http_head("http://192.168.100.1") is True

    @patch("solentlabs.cable_modem_monitor_core.connectivity.create_session")
    def test_head_500_fails(self, mock_create: MagicMock) -> None:
        """HEAD 500 returns False (server error = HEAD not supported)."""
        session = MagicMock()
        resp = MagicMock()
        resp.status_code = 500
        session.head.return_value = resp
        mock_create.return_value = session

        assert probe_http_head("http://192.168.100.1") is False

    @patch("solentlabs.cable_modem_monitor_core.connectivity.create_session")
    def test_head_connection_error(self, mock_create: MagicMock) -> None:
        """Connection error returns False."""
        session = MagicMock()
        session.head.side_effect = requests.exceptions.ConnectionError()
        mock_create.return_value = session

        assert probe_http_head("http://192.168.100.1") is False


# =====================================================================
# create_session() and LegacySSLAdapter
# =====================================================================


class TestCreateSession:
    """Session factory."""

    def test_normal_session(self) -> None:
        """Default session has verify=False, no legacy adapter."""
        session = create_session()
        assert session.verify is False
        # No adapter mounted for https
        assert "https://" not in session.adapters or not isinstance(session.adapters.get("https://"), LegacySSLAdapter)

    def test_legacy_ssl_session(self) -> None:
        """Legacy SSL session has LegacySSLAdapter mounted."""
        session = create_session(legacy_ssl=True)
        assert isinstance(session.adapters["https://"], LegacySSLAdapter)


class TestConnectivityResult:
    """ConnectivityResult dataclass."""

    def test_defaults(self) -> None:
        """Default values for a failed result."""
        result = ConnectivityResult(success=False)
        assert result.protocol is None
        assert result.legacy_ssl is False
        assert result.working_url is None
        assert result.error is None
