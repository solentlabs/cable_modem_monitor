"""Tests for connectivity — protocol detection and health probes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
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

_MODULE = "solentlabs.cable_modem_monitor_core.connectivity"

# =====================================================================
# detect_protocol()
# =====================================================================
#
# Protocol detection probes TCP :80 and :443. If :443 accepts a TCP
# connection AND completes a TLS handshake, HTTPS wins — modems that
# expose both ports almost always intend HTTPS for authenticated
# traffic. Standard Python SSL is tried first; SECLEVEL=0 is the
# fallback. ``legacy_ssl=True`` when standard SSL fails but SECLEVEL=0
# succeeds, or when the negotiated TLS version is TLS 1.1 or older.
#
# Scenario list lives in ``DETECT_PROTOCOL_CASES`` below — adding a
# row adds a test.


# Each row drives one full detect_protocol() invocation. ``tls_outcome``
# is None when the TLS handshake is not expected to run (either because
# :443 was closed or the user pinned http://…). When set, it's the
# ``(handshake_ok, legacy_negotiated)`` tuple ``_tls_handshake`` returns.
_DetectCase = tuple[
    str,  # description
    str,  # input host
    bool,  # :80 open?
    bool,  # :443 open?
    tuple[bool, bool] | None,  # _tls_handshake mock return; None if not called
    bool,  # expected success
    str | None,  # expected protocol
    bool,  # expected legacy_ssl
    str | None,  # expected working_url ("…" or None)
    list[int],  # expected ports passed to _tcp_probe
]

# fmt: off
DETECT_PROTOCOL_CASES: list[_DetectCase] = [
    ("http_only",
     "192.168.100.1",  True,  False, None,
     True,  "http",  False, "http://192.168.100.1",  [80, 443]),
    ("https_modern_preferred",
     "192.168.100.1",  True,  True,  (True, False),
     True,  "https", False, "https://192.168.100.1", [80, 443]),
    ("https_legacy_negotiated",
     "192.168.100.1",  False, True,  (True, True),
     True,  "https", True,  "https://192.168.100.1", [80, 443]),
    # UC-85 alt path: both ports open, standard SSL fails but SECLEVEL=0
    # succeeds — HTTPS preferred with legacy_ssl=True (issue #170).
    ("https_weak_cipher_both_ports_open",
     "192.168.100.1",  True,  True,  (True, True),
     True,  "https", True,  "https://192.168.100.1", [80, 443]),
    ("https_handshake_fails_falls_back_to_http",
     "192.168.100.1",  True,  True,  (False, False),
     True,  "http",  False, "http://192.168.100.1",  [80, 443]),
    ("https_only",
     "192.168.100.1",  False, True,  (True, False),
     True,  "https", False, "https://192.168.100.1", [80, 443]),
    ("https_open_but_handshake_fails_no_http",
     "192.168.100.1",  False, True,  (False, False),
     False, None,    False, None,                     [80, 443]),
    ("both_ports_closed",
     "192.168.100.1",  False, False, None,
     False, None,    False, None,                     [80, 443]),
    ("explicit_http_skips_tls_probe",
     "http://192.168.100.1", True, True, None,
     True,  "http",  False, "http://192.168.100.1",  [80]),
    ("explicit_https_skips_http_probe",
     "https://192.168.100.1", True, True, (True, False),
     True,  "https", False, "https://192.168.100.1", [443]),
    ("explicit_http_with_port_probes_only_that_port",
     "http://127.0.0.1:36771", True, False, None,
     True,  "http",  False, "http://127.0.0.1:36771", [36771]),
    ("explicit_https_with_port_probes_only_that_port",
     "https://127.0.0.1:8443", False, True, (True, False),
     True,  "https", False, "https://127.0.0.1:8443", [8443]),
]
# fmt: on


@pytest.mark.parametrize(
    "description, host, port_80_open, port_443_open, tls_outcome, "
    "expected_success, expected_protocol, expected_legacy_ssl, "
    "expected_working_url, expected_tcp_ports",
    DETECT_PROTOCOL_CASES,
    ids=[c[0] for c in DETECT_PROTOCOL_CASES],
)
class TestDetectProtocol:
    """Protocol detection — one row per scenario in DETECT_PROTOCOL_CASES."""

    def test_detection_outcome(
        self,
        description: str,
        host: str,
        port_80_open: bool,
        port_443_open: bool,
        tls_outcome: tuple[bool, bool] | None,
        expected_success: bool,
        expected_protocol: str | None,
        expected_legacy_ssl: bool,
        expected_working_url: str | None,
        expected_tcp_ports: list[int],
    ) -> None:
        """One detect_protocol() invocation per row."""
        tcp_calls: list[int] = []

        def tcp_side_effect(host: str, port: int, timeout: float) -> bool:
            tcp_calls.append(port)
            # When user provides a custom port, both http_port and
            # https_port collapse to it. The row's port_80_open /
            # port_443_open booleans then map by *intent*: for an
            # http://-prefixed input, port_80_open governs the user
            # port; for an https://-prefixed input, port_443_open
            # governs it. detect_protocol only probes one port in
            # the explicit-prefix case, so this disambiguates cleanly.
            if port == 80:
                return port_80_open
            if port == 443:
                return port_443_open
            # Custom (non-default) port — return whichever side is
            # marked open in the row. The cases that exercise this
            # path always set exactly one side True.
            return port_443_open if port_443_open else port_80_open

        tls_patch = (
            patch(f"{_MODULE}._tls_handshake", return_value=tls_outcome)
            if tls_outcome is not None
            else patch(f"{_MODULE}._tls_handshake")
        )
        with (
            patch(f"{_MODULE}._tcp_probe", side_effect=tcp_side_effect),
            tls_patch as tls,
        ):
            result = detect_protocol(host)

        assert result.success is expected_success, description
        assert result.protocol == expected_protocol, description
        assert result.legacy_ssl is expected_legacy_ssl, description
        if expected_working_url is None:
            assert result.working_url is None, description
            assert result.error is not None, description
        else:
            assert result.working_url == expected_working_url, description

        assert tcp_calls == expected_tcp_ports, description

        if tls_outcome is None:
            tls.assert_not_called()
        else:
            tls.assert_called_once()


# =====================================================================
# _strip_protocol() — pure helper, exhaustive table
# =====================================================================

# fmt: off
_STRIP_PROTOCOL_CASES = [
    ("bare_ip",                   "192.168.100.1",            (None,    "192.168.100.1")),
    ("bare_hostname",             "modem.local",              (None,    "modem.local")),
    ("http_prefix",               "http://192.168.100.1",     ("http",  "192.168.100.1")),
    ("https_prefix",              "https://192.168.100.1",    ("https", "192.168.100.1")),
    ("http_with_path",            "http://192.168.100.1/x",   ("http",  "192.168.100.1")),
    ("https_with_path_and_query", "https://m.local/a?b=1",    ("https", "m.local")),
    ("bare_ip_with_path",         "192.168.100.1/login",      (None,    "192.168.100.1")),
    ("http_with_port",            "http://192.168.100.1:8080", ("http", "192.168.100.1:8080")),
]
# fmt: on


@pytest.mark.parametrize(
    "description, host, expected",
    _STRIP_PROTOCOL_CASES,
    ids=[c[0] for c in _STRIP_PROTOCOL_CASES],
)
def test_strip_protocol(description: str, host: str, expected: tuple[str | None, str]) -> None:
    """_strip_protocol returns (protocol, bare_host_with_optional_port)."""
    from solentlabs.cable_modem_monitor_core.connectivity import _strip_protocol

    assert _strip_protocol(host) == expected, description


# =====================================================================
# _split_host_port() — pure helper, exhaustive table
# =====================================================================

# fmt: off
_SPLIT_HOST_PORT_CASES = [
    ("ipv4_no_port",             "192.168.100.1",        ("192.168.100.1", None)),
    ("ipv4_with_port",           "192.168.100.1:8080",   ("192.168.100.1", 8080)),
    ("hostname_no_port",         "modem.local",          ("modem.local",   None)),
    ("hostname_with_port",       "modem.local:8443",     ("modem.local",   8443)),
    ("loopback_with_high_port",  "127.0.0.1:36771",      ("127.0.0.1",     36771)),
    ("ipv6_bracketed_no_port",   "[::1]",                ("::1",           None)),
    ("ipv6_bracketed_with_port", "[::1]:8080",           ("::1",           8080)),
    ("ipv6_bracketed_partial",   "[::1",                 ("[::1",          None)),  # malformed — pass through
    ("trailing_colon_no_port",   "host:",                ("host:",         None)),  # not a digit suffix
]
# fmt: on


@pytest.mark.parametrize(
    "description, host, expected",
    _SPLIT_HOST_PORT_CASES,
    ids=[c[0] for c in _SPLIT_HOST_PORT_CASES],
)
def test_split_host_port(description: str, host: str, expected: tuple[str, int | None]) -> None:
    """_split_host_port returns (hostname, port|None) preserving IPv6 bracket form."""
    from solentlabs.cable_modem_monitor_core.connectivity import _split_host_port

    assert _split_host_port(host) == expected, description


class TestTcpProbe:
    """Direct tests for _tcp_probe — covers IPv4 pinning and timeout."""

    @patch(f"{_MODULE}.socket.getaddrinfo")
    def test_resolution_failure_returns_false(self, mock_gai: MagicMock) -> None:
        from solentlabs.cable_modem_monitor_core.connectivity import _tcp_probe

        mock_gai.side_effect = OSError("name not known")
        assert _tcp_probe("nope.invalid", 80, timeout=1.0) is False

    @patch(f"{_MODULE}.socket.socket")
    @patch(f"{_MODULE}.socket.getaddrinfo")
    def test_pins_to_ipv4(self, mock_gai: MagicMock, mock_socket: MagicMock) -> None:
        """getaddrinfo is called with AF_INET — never IPv6."""
        import socket as _socket

        from solentlabs.cable_modem_monitor_core.connectivity import _tcp_probe

        mock_gai.return_value = [
            (
                _socket.AF_INET,
                _socket.SOCK_STREAM,
                0,
                "",
                ("192.168.100.1", 80),
            )
        ]
        # Avoid touching the real network
        mock_socket.return_value.connect.return_value = None

        _tcp_probe("192.168.100.1", 80, timeout=1.0)

        mock_gai.assert_called_once()
        call_kwargs = mock_gai.call_args.kwargs
        assert call_kwargs.get("family") == _socket.AF_INET


class TestTlsHandshake:
    """Direct tests for _tls_handshake — standard SSL probe, SECLEVEL=0 fallback, version classification."""

    @pytest.mark.parametrize(
        "negotiated_version,expected_legacy",
        [
            ("TLSv1.3", False),
            ("TLSv1.2", False),
            ("TLSv1.1", True),
            ("TLSv1", True),
            ("SSLv3", True),
        ],
    )
    @patch(f"{_MODULE}.socket.create_connection")
    @patch(f"{_MODULE}.ssl.SSLContext")
    def test_version_classification(
        self,
        mock_context_cls: MagicMock,
        mock_create_conn: MagicMock,
        negotiated_version: str,
        expected_legacy: bool,
    ) -> None:
        from solentlabs.cable_modem_monitor_core.connectivity import _tls_handshake

        # ``with create_connection(...) as raw_sock``
        raw_sock = MagicMock()
        mock_create_conn.return_value.__enter__.return_value = raw_sock

        # ``with context.wrap_socket(...) as tls_sock``
        tls_sock = MagicMock()
        tls_sock.version.return_value = negotiated_version
        ctx = mock_context_cls.return_value
        ctx.wrap_socket.return_value.__enter__.return_value = tls_sock

        ok, legacy = _tls_handshake("192.168.100.1", 443, timeout=2.0)

        assert ok is True
        assert legacy is expected_legacy

    @patch(f"{_MODULE}.socket.create_connection")
    @patch(f"{_MODULE}.ssl.SSLContext")
    def test_standard_ssl_fails_seclevel0_succeeds(
        self,
        mock_context_cls: MagicMock,
        mock_create_conn: MagicMock,
    ) -> None:
        """Standard SSL fails; SECLEVEL=0 succeeds → (True, True). UC-85 alt path (issue #170)."""
        import ssl as _ssl

        from solentlabs.cable_modem_monitor_core.connectivity import _tls_handshake

        raw_sock = MagicMock()
        mock_create_conn.return_value.__enter__.return_value = raw_sock

        # First SSLContext (standard): wrap_socket raises handshake failure
        standard_ctx = MagicMock()
        standard_ctx.wrap_socket.return_value.__enter__.side_effect = _ssl.SSLError("SSLV3_ALERT_HANDSHAKE_FAILURE")

        # Second SSLContext (SECLEVEL=0): wrap_socket succeeds with TLS 1.2
        tls_sock = MagicMock()
        tls_sock.version.return_value = "TLSv1.2"
        legacy_ctx = MagicMock()
        legacy_ctx.wrap_socket.return_value.__enter__.return_value = tls_sock

        mock_context_cls.side_effect = [standard_ctx, legacy_ctx]

        ok, legacy = _tls_handshake("192.168.100.1", 443, timeout=2.0)

        assert ok is True
        assert legacy is True

    @patch(f"{_MODULE}.socket.create_connection")
    def test_phase1_timeout_skips_phase2(
        self,
        mock_create_conn: MagicMock,
    ) -> None:
        """Phase 1 timeout → (False, False) immediately; Phase 2 is not attempted."""
        from solentlabs.cable_modem_monitor_core.connectivity import _tls_handshake

        mock_create_conn.side_effect = TimeoutError("timed out")

        ok, legacy = _tls_handshake("192.168.100.1", 443, timeout=2.0)

        assert ok is False
        assert legacy is False
        assert mock_create_conn.call_count == 1  # Phase 2 never ran

    @patch(f"{_MODULE}.socket.create_connection")
    def test_handshake_failure_returns_false_false(
        self,
        mock_create_conn: MagicMock,
    ) -> None:
        """Both phases tried on ssl.SSLError; both fail → (False, False)."""
        import ssl as _ssl

        from solentlabs.cable_modem_monitor_core.connectivity import _tls_handshake

        mock_create_conn.side_effect = _ssl.SSLError("handshake failure")

        ok, legacy = _tls_handshake("192.168.100.1", 443, timeout=2.0)

        assert ok is False
        assert legacy is False
        # ssl.SSLError triggers Phase 2; both fail → 2 create_connection calls.
        assert mock_create_conn.call_count == 2

    @patch(f"{_MODULE}.socket.create_connection")
    def test_phase1_connection_error_skips_phase2(
        self,
        mock_create_conn: MagicMock,
    ) -> None:
        """Network-level OSError in Phase 1 → (False, False); Phase 2 not attempted."""
        from solentlabs.cable_modem_monitor_core.connectivity import _tls_handshake

        mock_create_conn.side_effect = ConnectionResetError("connection reset by peer")

        ok, legacy = _tls_handshake("192.168.100.1", 443, timeout=2.0)

        assert ok is False
        assert legacy is False
        # Non-ssl.SSLError OSError exits immediately — no second probe.
        assert mock_create_conn.call_count == 1


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
