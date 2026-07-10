"""Tests for HealthMonitor — lightweight modem probes.

Covers ICMP + TCP + HTTP HEAD probes, probe configurations, status
derivation, logging, and collection evidence (TCP/HEAD probe
suppression). Status derivation uses ICMP + TCP. HEAD is a
latency-only signal that populates http_latency_ms only when the
modem advertises supports_head=True; GET-only modems skip the HEAD
probe entirely (no fallback to GET — its bimodal cold/warm timing
would corrupt the metric).

Use case coverage:
- UC-50: Normal health check — both probes
- UC-53: Outage detection between data polls
- UC-54: ICMP blocked network
- UC-55: Degraded — TCP fails, ICMP succeeds
- UC-56: Both probes disabled
- UC-57: Health during restart — independent
- Collection evidence: TCP/HEAD skipped during/after data collection
- UC-59a: ICMP failure forces the TCP probe past the skip gate
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest
import requests
from solentlabs.cable_modem_monitor_core.orchestration.models import HealthInfo
from solentlabs.cable_modem_monitor_core.orchestration.modem_health import (
    _PING_TIME_RE,
    HealthMonitor,
)
from solentlabs.cable_modem_monitor_core.orchestration.signals import HealthStatus

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_MODULE = "solentlabs.cable_modem_monitor_core.orchestration.modem_health"


@pytest.fixture(autouse=True)
def _mock_tcp_socket():
    """Mock socket.create_connection for TCP probe in all health tests.

    Returns a mock socket instantly so TCP connect time is ~0ms.
    Server latency ~ response.elapsed (negligible subtraction).
    """
    mock_sock = MagicMock()
    with patch(f"{_MODULE}.socket.create_connection", return_value=mock_sock):
        yield


def _make_monitor(
    *,
    supports_icmp: bool = True,
    supports_head: bool = True,
    http_probe: bool = True,
    legacy_ssl: bool = False,
    timeout: int = 5,
) -> tuple[HealthMonitor, MagicMock]:
    """Build a HealthMonitor with a mocked session.

    Patches create_session during construction so no real HTTP session
    is created. Returns the monitor and the mock session so tests can
    set up .head/.get return values with proper typing.
    """
    with patch(f"{_MODULE}.create_session") as mock_cs:
        mock_session = MagicMock()
        mock_cs.return_value = mock_session
        monitor = HealthMonitor(
            base_url="http://192.168.100.1",
            model="T100",
            supports_icmp=supports_icmp,
            supports_head=supports_head,
            http_probe=http_probe,
            legacy_ssl=legacy_ssl,
            timeout=timeout,
        )
    return monitor, mock_session


def _mock_ping_success(latency_ms: float = 4.12) -> MagicMock:
    """Build a subprocess.run result for a successful ICMP ping."""
    result = MagicMock()
    result.returncode = 0
    result.stdout = (
        f"PING 192.168.100.1 (192.168.100.1) 56(84) bytes of data.\n"
        f"64 bytes from 192.168.100.1: icmp_seq=1 ttl=64 time={latency_ms} ms\n"
        f"\n--- 192.168.100.1 ping statistics ---\n"
        f"1 packets transmitted, 1 received, 0% packet loss, time 0ms\n"
        f"rtt min/avg/max/mdev = {latency_ms}/{latency_ms}/{latency_ms}/0.000 ms\n"
    )
    return result


def _mock_ping_failure() -> MagicMock:
    """Build a subprocess.run result for a failed ICMP ping."""
    result = MagicMock()
    result.returncode = 1
    result.stdout = (
        "PING 192.168.100.1 (192.168.100.1) 56(84) bytes of data.\n"
        "\n--- 192.168.100.1 ping statistics ---\n"
        "1 packets transmitted, 0 received, 100% packet loss, time 0ms\n"
    )
    return result


def _mock_http_response(latency_s: float = 0.012) -> MagicMock:
    """Build a requests response for a successful HTTP probe."""
    response = MagicMock()
    response.status_code = 200
    from datetime import timedelta

    response.elapsed = timedelta(seconds=latency_s)
    return response


# ------------------------------------------------------------------
# Ping time regex
# ------------------------------------------------------------------


# ┌──────────────────────────────┬──────────┬──────────────────────────┐
# │ input                        │ expected │ description              │
# ├──────────────────────────────┼──────────┼──────────────────────────┤
# │ "time=4.12 ms"               │ 4.12     │ Linux/macOS standard     │
# │ "time=0.5 ms"                │ 0.5      │ sub-millisecond          │
# │ "time=123 ms"                │ 123.0    │ integer latency          │
# │ "time<1ms"                   │ 1.0      │ Windows <1ms             │
# │ "time=4.12ms"                │ 4.12     │ no space before ms       │
# │ "no match here"              │ None     │ no time field            │
# └──────────────────────────────┴──────────┴──────────────────────────┘
#
# fmt: off
PING_TIME_CASES = [
    ("time=4.12 ms",  4.12,  "linux_standard"),
    ("time=0.5 ms",   0.5,   "sub_millisecond"),
    ("time=123 ms",   123.0, "integer_latency"),
    ("time<1ms",      1.0,   "windows_lt_1ms"),
    ("time=4.12ms",   4.12,  "no_space_before_ms"),
    ("no match here", None,  "no_time_field"),
]
# fmt: on


@pytest.mark.parametrize(
    "text, expected, _desc",
    PING_TIME_CASES,
    ids=[c[2] for c in PING_TIME_CASES],
)
def test_ping_time_regex(text: str, expected: float | None, _desc: str) -> None:
    """Verify the ping time extraction regex."""
    match = _PING_TIME_RE.search(text)
    if expected is None:
        assert match is None
    else:
        assert match is not None
        assert float(match.group(1)) == expected


# ------------------------------------------------------------------
# URL host extraction
# ------------------------------------------------------------------


# ┌──────────────────────────────────────┬───────────────────┬─────────────┐
# │ url                                  │ expected          │ description │
# ├──────────────────────────────────────┼───────────────────┼─────────────┤
# │ "http://192.168.100.1"               │ "192.168.100.1"   │ ip_no_port  │
# │ "http://192.168.100.1:8080"          │ "192.168.100.1"   │ ip_with_port│
# │ "https://modem.local/path"           │ "modem.local"     │ hostname    │
# │ "http://10.0.0.1/"                   │ "10.0.0.1"        │ trailing_sl │
# └──────────────────────────────────────┴───────────────────┴─────────────┘
#
# fmt: off
HOST_CASES = [
    ("http://192.168.100.1",      "192.168.100.1", "ip_no_port"),
    ("http://192.168.100.1:8080", "192.168.100.1", "ip_with_port"),
    ("https://modem.local/path",  "modem.local",   "hostname"),
    ("http://10.0.0.1/",          "10.0.0.1",      "trailing_slash"),
]
# fmt: on


@pytest.mark.parametrize(
    "url, expected, _desc",
    HOST_CASES,
    ids=[c[2] for c in HOST_CASES],
)
def test_extract_host(url: str, expected: str, _desc: str) -> None:
    """Verify host extraction from URLs."""
    assert HealthMonitor._extract_host(url) == expected


# ------------------------------------------------------------------
# URL port extraction
# ------------------------------------------------------------------


# ┌──────────────────────────────────────┬──────────┬─────────────┐
# │ url                                  │ expected │ description │
# ├──────────────────────────────────────┼──────────┼─────────────┤
# │ "http://192.168.100.1"               │ 80       │ http_default│
# │ "https://192.168.100.1"              │ 443      │ https_def   │
# │ "http://192.168.100.1:8080"          │ 8080     │ custom_port │
# │ "https://modem.local:9443/path"      │ 9443     │ https_custom│
# │ "http://10.0.0.1/"                   │ 80       │ trailing_sl │
# └──────────────────────────────────────┴──────────┴─────────────┘
#
# fmt: off
PORT_CASES = [
    ("http://192.168.100.1",          80,   "http_default"),
    ("https://192.168.100.1",         443,  "https_default"),
    ("http://192.168.100.1:8080",     8080, "custom_port"),
    ("https://modem.local:9443/path", 9443, "https_custom_port"),
    ("http://10.0.0.1/",              80,   "trailing_slash"),
    ("192.168.100.1",                 80,   "no_scheme"),
]
# fmt: on


@pytest.mark.parametrize(
    "url, expected, _desc",
    PORT_CASES,
    ids=[c[2] for c in PORT_CASES],
)
def test_extract_port(url: str, expected: int, _desc: str) -> None:
    """Verify port extraction from URLs."""
    assert HealthMonitor._extract_port(url) == expected


# ------------------------------------------------------------------
# Platform-specific ping command
# ------------------------------------------------------------------


class TestBuildPingCommand:
    """Verify platform-specific ping command generation."""

    @patch(f"{_MODULE}.platform.system")
    def test_linux(self, mock_system: MagicMock) -> None:
        """Linux uses -c 1 -W timeout."""
        mock_system.return_value = "Linux"
        monitor, session = _make_monitor(timeout=5)
        cmd = monitor._build_ping_command()
        assert cmd == ["ping", "-c", "1", "-W", "5", "192.168.100.1"]

    @patch(f"{_MODULE}.platform.system")
    def test_darwin(self, mock_system: MagicMock) -> None:
        """macOS uses -c 1 -t timeout."""
        mock_system.return_value = "Darwin"
        monitor, session = _make_monitor(timeout=5)
        cmd = monitor._build_ping_command()
        assert cmd == ["ping", "-c", "1", "-t", "5", "192.168.100.1"]

    @patch(f"{_MODULE}.platform.system")
    def test_windows(self, mock_system: MagicMock) -> None:
        """Windows uses -n 1 -w timeout_ms."""
        mock_system.return_value = "Windows"
        monitor, session = _make_monitor(timeout=5)
        cmd = monitor._build_ping_command()
        assert cmd == ["ping", "-n", "1", "-w", "5000", "192.168.100.1"]


# ------------------------------------------------------------------
# Session creation
# ------------------------------------------------------------------


class TestSessionCreation:
    """Verify HealthMonitor creates session with correct SSL config."""

    def test_default_session(self) -> None:
        """Default construction passes legacy_ssl=False."""
        with patch(f"{_MODULE}.create_session") as mock_cs:
            mock_cs.return_value = MagicMock()
            HealthMonitor(base_url="http://192.168.100.1")
            mock_cs.assert_called_once_with(legacy_ssl=False)

    def test_legacy_ssl_session(self) -> None:
        """legacy_ssl=True is forwarded to create_session."""
        with patch(f"{_MODULE}.create_session") as mock_cs:
            mock_cs.return_value = MagicMock()
            HealthMonitor(base_url="https://192.168.100.1", legacy_ssl=True)
            mock_cs.assert_called_once_with(legacy_ssl=True)


# ------------------------------------------------------------------
# UC-50: Normal health check — both probes
# ------------------------------------------------------------------


class TestUC50BothProbes:
    """Both ICMP and HTTP probes run and succeed."""

    @patch(f"{_MODULE}.subprocess.run")
    def test_both_pass(self, mock_run: MagicMock) -> None:
        """ICMP + HTTP both succeed → RESPONSIVE."""
        mock_run.return_value = _mock_ping_success(4.0)

        monitor, session = _make_monitor()
        session.head.return_value = _mock_http_response(0.012)
        info = monitor.ping()

        assert info.health_status == HealthStatus.RESPONSIVE
        assert info.icmp_latency_ms == 4.0
        assert info.http_latency_ms == pytest.approx(12.0, abs=0.1)

    @patch(f"{_MODULE}.subprocess.run")
    def test_latest_property(self, mock_run: MagicMock) -> None:
        """ping() result accessible via latest property."""
        mock_run.return_value = _mock_ping_success()

        monitor, session = _make_monitor()
        session.head.return_value = _mock_http_response()
        info = monitor.ping()

        assert monitor.latest is info

    def test_latest_default(self) -> None:
        """latest returns UNKNOWN before first ping()."""
        monitor, session = _make_monitor()
        assert monitor.latest.health_status == HealthStatus.UNKNOWN

    @patch(f"{_MODULE}.subprocess.run")
    def test_no_head_probe_when_unsupported(self, mock_run: MagicMock) -> None:
        """supports_head=False → HEAD is skipped entirely (no GET fallback).

        TCP probe still runs as the L4 reachability signal, and status
        derivation succeeds via ICMP + TCP. http_latency_ms remains None
        because GET timing is bimodal on most embedded modems and would
        corrupt the metric.
        """
        mock_run.return_value = _mock_ping_success()

        monitor, session = _make_monitor(supports_head=False)
        info = monitor.ping()

        session.head.assert_not_called()
        session.get.assert_not_called()
        assert info.health_status == HealthStatus.RESPONSIVE
        assert info.http_latency_ms is None
        assert info.tcp_latency_ms is not None

    @patch(f"{_MODULE}.subprocess.run")
    def test_http_probe_does_not_follow_redirects(self, mock_run: MagicMock) -> None:
        """HTTP probe uses allow_redirects=False — any response is alive."""
        mock_run.return_value = _mock_ping_success()

        redirect_response = _mock_http_response(0.005)
        redirect_response.status_code = 302

        monitor, session = _make_monitor()
        session.head.return_value = redirect_response
        info = monitor.ping()

        session.head.assert_called_once_with(
            "http://192.168.100.1",
            timeout=5,
            allow_redirects=False,
        )
        assert info.health_status == HealthStatus.RESPONSIVE
        assert info.http_latency_ms == pytest.approx(5.0, abs=0.1)


# ------------------------------------------------------------------
# UC-53: Outage detection between data polls
# ------------------------------------------------------------------


class TestUC53OutageDetection:
    """Health probes detect outage between data polls."""

    @patch(f"{_MODULE}.subprocess.run")
    def test_detects_modem_down(self, mock_run: MagicMock) -> None:
        """ICMP + TCP both fail → UNRESPONSIVE."""
        mock_run.return_value = _mock_ping_failure()

        monitor, session = _make_monitor()
        session.head.side_effect = requests.ConnectionError("refused")
        with patch(
            f"{_MODULE}.socket.create_connection",
            side_effect=OSError("refused"),
        ):
            info = monitor.ping()

        assert info.health_status == HealthStatus.UNRESPONSIVE
        assert info.icmp_latency_ms is None
        assert info.tcp_latency_ms is None
        assert info.http_latency_ms is None


# ------------------------------------------------------------------
# UC-54: ICMP blocked network
# ------------------------------------------------------------------


class TestUC54ICMPBlocked:
    """Network blocks ICMP but TCP works."""

    @patch(f"{_MODULE}.subprocess.run")
    def test_icmp_fail_tcp_pass(self, mock_run: MagicMock) -> None:
        """ICMP fails + TCP succeeds → ICMP_BLOCKED."""
        mock_run.return_value = _mock_ping_failure()

        monitor, session = _make_monitor()
        session.head.return_value = _mock_http_response()
        info = monitor.ping()

        assert info.health_status == HealthStatus.ICMP_BLOCKED


# ------------------------------------------------------------------
# UC-55: Degraded — TCP fails, ICMP succeeds
# ------------------------------------------------------------------


class TestUC55Degraded:
    """ICMP works but TCP fails (modem L4 stack not accepting).

    HTTP failures alone no longer affect status — the slow poll catches
    application-layer issues. DEGRADED specifically means L3 reachable
    but L4 unreachable.
    """

    @patch(f"{_MODULE}.subprocess.run")
    def test_icmp_pass_tcp_fail(self, mock_run: MagicMock) -> None:
        """ICMP succeeds + TCP fails → DEGRADED."""
        mock_run.return_value = _mock_ping_success(4.0)

        monitor, session = _make_monitor()
        session.head.return_value = _mock_http_response()
        with patch(
            f"{_MODULE}.socket.create_connection",
            side_effect=OSError("refused"),
        ):
            info = monitor.ping()

        assert info.health_status == HealthStatus.DEGRADED
        assert info.icmp_latency_ms == 4.0
        assert info.tcp_latency_ms is None


# ------------------------------------------------------------------
# UC-56: Both probes disabled
# ------------------------------------------------------------------


class TestUC56NeitherProbe:
    """No probes enabled → UNKNOWN."""

    def test_no_probes(self) -> None:
        """supports_icmp=False + http_probe=False → UNKNOWN."""
        monitor, session = _make_monitor(supports_icmp=False, http_probe=False)
        info = monitor.ping()

        assert info.health_status == HealthStatus.UNKNOWN
        assert info.icmp_latency_ms is None
        assert info.http_latency_ms is None


# ------------------------------------------------------------------
# UC-57: Health during restart — independent
# ------------------------------------------------------------------


class TestUC57HealthDuringRestart:
    """Health checks continue independently during restart."""

    @patch(f"{_MODULE}.subprocess.run")
    def test_ping_works_independently(self, mock_run: MagicMock) -> None:
        """ping() works regardless of restart state (stateless probes)."""
        mock_run.return_value = _mock_ping_failure()

        monitor, session = _make_monitor()
        session.head.side_effect = requests.ConnectionError("refused")
        with patch(
            f"{_MODULE}.socket.create_connection",
            side_effect=OSError("refused"),
        ):
            info = monitor.ping()

        assert info.health_status == HealthStatus.UNRESPONSIVE


# ------------------------------------------------------------------
# TCP-only mode (supports_icmp=False)
# ------------------------------------------------------------------


class TestTCPOnlyMode:
    """Only TCP probe runs for L4 reachability when ICMP is not supported.

    HTTP HEAD may also run as a latency-only signal but does not affect
    status derivation.
    """

    @patch(f"{_MODULE}.subprocess.run")
    def test_tcp_pass(self, mock_run: MagicMock) -> None:
        """TCP succeeds (ICMP disabled) → RESPONSIVE."""
        monitor, session = _make_monitor(supports_icmp=False)
        session.head.return_value = _mock_http_response()
        info = monitor.ping()

        mock_run.assert_not_called()
        assert info.health_status == HealthStatus.RESPONSIVE
        assert info.tcp_latency_ms is not None

    def test_tcp_fail(self) -> None:
        """TCP fails (ICMP disabled) → UNRESPONSIVE."""
        monitor, session = _make_monitor(supports_icmp=False)
        session.head.side_effect = requests.Timeout("timeout")
        with patch(
            f"{_MODULE}.socket.create_connection",
            side_effect=OSError("refused"),
        ):
            info = monitor.ping()

        assert info.health_status == HealthStatus.UNRESPONSIVE


# ------------------------------------------------------------------
# ICMP-only mode (http_probe=False)
# ------------------------------------------------------------------


class TestICMPOnlyMode:
    """Only ICMP runs when HTTP probe is disabled."""

    @patch(f"{_MODULE}.subprocess.run")
    def test_icmp_pass(self, mock_run: MagicMock) -> None:
        """ICMP only, passes → RESPONSIVE."""
        mock_run.return_value = _mock_ping_success()

        monitor, session = _make_monitor(http_probe=False)
        info = monitor.ping()

        assert info.health_status == HealthStatus.RESPONSIVE
        assert info.http_latency_ms is None

    @patch(f"{_MODULE}.subprocess.run")
    def test_icmp_fail(self, mock_run: MagicMock) -> None:
        """ICMP only, fails → UNRESPONSIVE."""
        mock_run.return_value = _mock_ping_failure()

        monitor, session = _make_monitor(http_probe=False)
        info = monitor.ping()

        assert info.health_status == HealthStatus.UNRESPONSIVE


# ------------------------------------------------------------------
# ICMP error handling
# ------------------------------------------------------------------


class TestICMPErrorHandling:
    """ICMP probe handles subprocess errors gracefully."""

    @patch(f"{_MODULE}.subprocess.run")
    def test_subprocess_timeout(self, mock_run: MagicMock) -> None:
        """subprocess.TimeoutExpired → probe fails gracefully."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["ping"], timeout=7)

        monitor, session = _make_monitor(supports_icmp=True, http_probe=False)
        info = monitor.ping()

        assert info.icmp_latency_ms is None
        assert info.health_status == HealthStatus.UNRESPONSIVE

    @patch(f"{_MODULE}.subprocess.run")
    def test_os_error(self, mock_run: MagicMock) -> None:
        """OSError (ping not found) → probe fails gracefully."""
        mock_run.side_effect = OSError("No such file or directory: 'ping'")

        monitor, session = _make_monitor(supports_icmp=True, http_probe=False)
        info = monitor.ping()

        assert info.icmp_latency_ms is None
        assert info.health_status == HealthStatus.UNRESPONSIVE

    @patch(f"{_MODULE}.subprocess.run")
    def test_ping_success_unparseable_output(self, mock_run: MagicMock) -> None:
        """Return code 0 but unparseable output → success with no latency."""
        result = MagicMock()
        result.returncode = 0
        result.stdout = "unexpected output format"
        mock_run.return_value = result

        monitor, session = _make_monitor(supports_icmp=True, http_probe=False)
        info = monitor.ping()

        # Probe is success (rc=0) but no latency extracted
        assert info.health_status == HealthStatus.RESPONSIVE
        assert info.icmp_latency_ms is None


# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------


class TestHealthLogging:
    """Verify logging contract."""

    @patch(f"{_MODULE}.subprocess.run")
    def test_first_responsive_logs_info(
        self,
        mock_run: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """First RESPONSIVE check (status transition) logs at INFO."""
        mock_run.return_value = _mock_ping_success(4.0)

        monitor, session = _make_monitor()
        session.head.return_value = _mock_http_response()
        with caplog.at_level("INFO"):
            monitor.ping()

        assert "Health check [T100]: responsive" in caplog.text

    @patch(f"{_MODULE}.subprocess.run")
    def test_routine_responsive_logs_debug(
        self,
        mock_run: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Repeated RESPONSIVE checks (no transition) log at DEBUG."""
        mock_run.return_value = _mock_ping_success(4.0)

        monitor, session = _make_monitor()
        session.head.return_value = _mock_http_response()
        monitor.ping()  # first check — transitions UNKNOWN → RESPONSIVE

        caplog.clear()
        with caplog.at_level("DEBUG"):
            monitor.ping()  # second check — still RESPONSIVE

        assert "Health check [T100]: responsive" in caplog.text
        # Verify it was DEBUG, not INFO
        for record in caplog.records:
            if "Health check:" in record.message:
                assert record.levelname == "DEBUG"

    @patch(f"{_MODULE}.subprocess.run")
    def test_degraded_logs_warning(
        self,
        mock_run: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """DEGRADED logs at WARNING level (ICMP ok, TCP fails)."""
        mock_run.return_value = _mock_ping_success()

        monitor, session = _make_monitor()
        session.head.return_value = _mock_http_response()
        with (
            patch(
                f"{_MODULE}.socket.create_connection",
                side_effect=OSError("refused"),
            ),
            caplog.at_level("WARNING"),
        ):
            monitor.ping()

        assert "Health check [T100]: degraded" in caplog.text

    @patch(f"{_MODULE}.subprocess.run")
    def test_unresponsive_logs_warning(
        self,
        mock_run: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """UNRESPONSIVE logs at WARNING level (ICMP and TCP both fail)."""
        mock_run.return_value = _mock_ping_failure()

        monitor, session = _make_monitor()
        session.head.side_effect = requests.ConnectionError("refused")
        with (
            patch(
                f"{_MODULE}.socket.create_connection",
                side_effect=OSError("refused"),
            ),
            caplog.at_level("WARNING"),
        ):
            monitor.ping()

        assert "Health check [T100]: unresponsive" in caplog.text


# ------------------------------------------------------------------
# Collection evidence — HTTP probe suppression
#
# See ORCHESTRATION_SPEC.md § HealthMonitor / Collection Evidence.
# The orchestrator signals collection start/end; the health monitor
# skips the HTTP probe when a collection is active or recently
# succeeded. ICMP always runs.
# ------------------------------------------------------------------

# Status derivation matrix with collection evidence.
#
# An ICMP failure forces the TCP probe past the skip gate (UC-59a) —
# the autouse socket mock makes the forced probe succeed, so the
# icmp=fail rows confirm ICMP_BLOCKED with a real TCP measurement.
#
# ┌─────────────────────┬──────────┬──────────────┬────────────┬────────────┬──────────────────┐
# │ evidence_state      │ icmp     │ status       │ http_calls │ tcp_probed │ description      │
# ├─────────────────────┼──────────┼──────────────┼────────────┼────────────┼──────────────────┤
# │ active              │ pass     │ RESPONSIVE   │ 0          │ no         │ active_icmp_pass │
# │ active              │ fail     │ ICMP_BLOCKED │ 0          │ forced     │ active_icmp_fail │
# │ active              │ disabled │ RESPONSIVE   │ 0          │ no         │ active_no_icmp   │
# │ recent_success      │ pass     │ RESPONSIVE   │ 0          │ no         │ recent_icmp_pass │
# │ recent_success      │ fail     │ ICMP_BLOCKED │ 0          │ forced     │ recent_icmp_fail │
# │ failed_collection   │ pass     │ RESPONSIVE   │ 1          │ normal     │ failed_icmp_pass │
# │ no_evidence         │ pass     │ RESPONSIVE   │ 1          │ normal     │ none_icmp_pass   │
# └─────────────────────┴──────────┴──────────────┴────────────┴────────────┴──────────────────┘
#
# fmt: off
EVIDENCE_CASES = [
    ("active",            "pass",     HealthStatus.RESPONSIVE,   0, False, "active_icmp_pass"),
    ("active",            "fail",     HealthStatus.ICMP_BLOCKED, 0, True,  "active_icmp_fail"),
    ("active",            "disabled", HealthStatus.RESPONSIVE,   0, False, "active_no_icmp"),
    ("recent_success",    "pass",     HealthStatus.RESPONSIVE,   0, False, "recent_icmp_pass"),
    ("recent_success",    "fail",     HealthStatus.ICMP_BLOCKED, 0, True,  "recent_icmp_fail"),
    ("failed_collection", "pass",     HealthStatus.RESPONSIVE,   1, True,  "failed_icmp_pass"),
    ("no_evidence",       "pass",     HealthStatus.RESPONSIVE,   1, True,  "none_icmp_pass"),
]
# fmt: on


def _setup_evidence(
    monitor: HealthMonitor,
    session: MagicMock,
    state: str,
) -> None:
    """Apply collection evidence state to the monitor.

    All states that expect HTTP suppression require a prior ping()
    to establish a baseline — the first ping never skips HTTP so
    consumers get at least one real measurement.
    """
    if state == "active":
        session.head.return_value = _mock_http_response()
        monitor.ping()  # establish baseline
        session.head.reset_mock()
        monitor.record_collection_start()
    elif state == "recent_success":
        session.head.return_value = _mock_http_response()
        monitor.ping()  # establish baseline
        session.head.reset_mock()
        monitor.record_collection_start()
        monitor.record_collection_end(success=True)
    elif state == "failed_collection":
        monitor.record_collection_start()
        monitor.record_collection_end(success=False)
    # no_evidence: nothing to do


@pytest.mark.parametrize(
    "evidence_state, icmp, expected_status, http_calls, tcp_probed, _desc",
    EVIDENCE_CASES,
    ids=[c[5] for c in EVIDENCE_CASES],
)
@patch(f"{_MODULE}.subprocess.run")
def test_collection_evidence_matrix(
    mock_run: MagicMock,
    evidence_state: str,
    icmp: str,
    expected_status: HealthStatus,
    http_calls: int,
    tcp_probed: bool,
    _desc: str,
) -> None:
    """Verify HTTP probe suppression and status derivation with collection evidence."""
    # ICMP setup
    if icmp == "disabled":
        monitor, session = _make_monitor(supports_icmp=False)
    elif icmp == "pass":
        mock_run.return_value = _mock_ping_success(1.5)
        monitor, session = _make_monitor()
    else:
        mock_run.return_value = _mock_ping_failure()
        monitor, session = _make_monitor()

    # Evidence setup
    _setup_evidence(monitor, session, evidence_state)

    # HTTP response for cases where the probe should run
    if http_calls > 0:
        session.head.return_value = _mock_http_response()

    info = monitor.ping()

    assert info.health_status == expected_status
    assert session.head.call_count == http_calls
    assert (info.tcp_latency_ms is not None) == tcp_probed
    if http_calls == 0:
        assert info.http_latency_ms is None
    else:
        assert info.http_latency_ms is not None


# ------------------------------------------------------------------
# Collection evidence — behavioral tests (multi-step, stay inline)
# ------------------------------------------------------------------


class TestCollectionEvidenceBehavior:
    """Multi-step behavioral tests for collection evidence lifecycle."""

    @patch(f"{_MODULE}.subprocess.run")
    def test_evidence_consumed_once(self, mock_run: MagicMock) -> None:
        """First ping after collection skips HTTP; second ping runs it."""
        mock_run.return_value = _mock_ping_success()

        monitor, session = _make_monitor()

        # Baseline ping — establishes _last_ping_time
        session.head.return_value = _mock_http_response()
        monitor.ping()
        session.head.reset_mock()

        # Successful collection
        monitor.record_collection_start()
        monitor.record_collection_end(success=True)

        # First ping after collection — evidence fresh, HTTP skipped
        monitor.ping()
        assert session.head.call_count == 0

        # Second ping — evidence consumed, HTTP runs
        session.head.return_value = _mock_http_response()
        monitor.ping()
        assert session.head.call_count == 1

    @patch(f"{_MODULE}.subprocess.run")
    def test_collection_end_clears_active_flag(self, mock_run: MagicMock) -> None:
        """record_collection_end(False) clears active flag; HTTP runs normally."""
        mock_run.return_value = _mock_ping_success()

        monitor, session = _make_monitor()
        monitor.record_collection_start()
        monitor.record_collection_end(success=False)

        session.head.return_value = _mock_http_response()
        info = monitor.ping()

        session.head.assert_called_once()
        assert info.http_latency_ms is not None

    @patch(f"{_MODULE}.subprocess.run")
    def test_http_disabled_ignores_evidence(self, mock_run: MagicMock) -> None:
        """http_probe=False — evidence has no effect on already-disabled probe."""
        mock_run.return_value = _mock_ping_success()

        monitor, session = _make_monitor(http_probe=False)
        monitor.record_collection_start()
        info = monitor.ping()

        assert info.health_status == HealthStatus.RESPONSIVE
        assert info.http_latency_ms is None

    @patch(f"{_MODULE}.subprocess.run")
    def test_first_ping_never_skips_http(self, mock_run: MagicMock) -> None:
        """First ping always runs HTTP — consumers need a real baseline."""
        mock_run.return_value = _mock_ping_success()

        monitor, session = _make_monitor()
        monitor.record_collection_start()

        session.head.return_value = _mock_http_response()
        info = monitor.ping()

        session.head.assert_called_once()
        assert info.http_latency_ms is not None

    @patch(f"{_MODULE}.subprocess.run")
    def test_logs_skipped_active(
        self,
        mock_run: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Log detail shows 'TCP/HEAD skipped' when collection suppresses probes."""
        mock_run.return_value = _mock_ping_success(1.5)

        monitor, session = _make_monitor()

        # Baseline ping
        session.head.return_value = _mock_http_response()
        monitor.ping()

        monitor.record_collection_start()

        with caplog.at_level("DEBUG"):
            monitor.ping()

        assert "TCP/HEAD skipped (collection active)" in caplog.text

    @patch(f"{_MODULE}.subprocess.run")
    def test_logs_skipped_recent_collection(
        self,
        mock_run: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Log shows 'recent collection' when skip is post-collection, not active."""
        mock_run.return_value = _mock_ping_success(1.5)

        monitor, session = _make_monitor()

        # Baseline ping
        session.head.return_value = _mock_http_response()
        monitor.ping()

        # Collection completes (not active — already ended)
        monitor.record_collection_start()
        monitor.record_collection_end(success=True)

        with caplog.at_level("DEBUG"):
            monitor.ping()

        assert "TCP/HEAD skipped (recent collection)" in caplog.text


# ------------------------------------------------------------------
# Collection evidence — ICMP contradiction override (UC-59a)
#
# Collection evidence is a statement about the past; a failing ICMP
# probe is a current observation that contradicts it. The override
# forces the TCP probe past the skip gate so status derivation uses
# a live reading instead of fabricating tcp_ok=True — otherwise an
# outage beginning within one health interval of a successful poll
# reports a false ICMP_BLOCKED.
# ------------------------------------------------------------------


class TestIcmpFailureOverridesSkipGate:
    """A failing ICMP probe forces the TCP probe past the skip gate."""

    @staticmethod
    def _monitor_with_recent_collection(mock_run: MagicMock) -> tuple[HealthMonitor, MagicMock]:
        """Monitor with a consumed baseline ping and fresh collection evidence."""
        mock_run.return_value = _mock_ping_success()
        monitor, session = _make_monitor()
        session.head.return_value = _mock_http_response()
        monitor.ping()  # baseline — first ping never skips
        session.head.reset_mock()
        monitor.record_collection_start()
        monitor.record_collection_end(success=True)
        return monitor, session

    @patch(f"{_MODULE}.subprocess.run")
    def test_dead_modem_is_unresponsive_not_icmp_blocked(self, mock_run: MagicMock) -> None:
        """Outage right after a poll: ICMP fail + forced TCP fail → UNRESPONSIVE."""
        monitor, session = self._monitor_with_recent_collection(mock_run)
        mock_run.return_value = _mock_ping_failure()

        with patch(f"{_MODULE}.socket.create_connection", side_effect=OSError):
            info = monitor.ping()

        assert info.health_status == HealthStatus.UNRESPONSIVE
        session.head.assert_not_called()

    @patch(f"{_MODULE}.subprocess.run")
    def test_live_modem_confirms_icmp_blocked(self, mock_run: MagicMock) -> None:
        """ICMP fail + forced TCP pass → ICMP_BLOCKED backed by a real measurement."""
        monitor, session = self._monitor_with_recent_collection(mock_run)
        mock_run.return_value = _mock_ping_failure()

        info = monitor.ping()

        assert info.health_status == HealthStatus.ICMP_BLOCKED
        assert info.tcp_latency_ms is not None
        assert info.http_latency_ms is None
        session.head.assert_not_called()

    @patch(f"{_MODULE}.subprocess.run")
    def test_override_applies_during_active_collection(self, mock_run: MagicMock) -> None:
        """Skip reason 'collection active' is also overridden by ICMP failure."""
        mock_run.return_value = _mock_ping_success()
        monitor, session = _make_monitor()
        session.head.return_value = _mock_http_response()
        monitor.ping()  # baseline — first ping never skips
        session.head.reset_mock()
        monitor.record_collection_start()
        mock_run.return_value = _mock_ping_failure()

        with patch(f"{_MODULE}.socket.create_connection", side_effect=OSError):
            info = monitor.ping()

        assert info.health_status == HealthStatus.UNRESPONSIVE
        session.head.assert_not_called()

    @patch(f"{_MODULE}.subprocess.run")
    def test_log_shows_forced_tcp(
        self,
        mock_run: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Log detail names the skip reason and the forced TCP probe."""
        monitor, _session = self._monitor_with_recent_collection(mock_run)
        mock_run.return_value = _mock_ping_failure()

        with (
            patch(f"{_MODULE}.socket.create_connection", side_effect=OSError),
            caplog.at_level("DEBUG"),
        ):
            monitor.ping()

        assert "HEAD skipped (recent collection; TCP forced by ICMP failure)" in caplog.text


# ------------------------------------------------------------------
# TCP connect probe
# ------------------------------------------------------------------


class TestTCPConnectProbe:
    """Verify TCP connect timing is measured and logged separately."""

    @patch(f"{_MODULE}.subprocess.run")
    def test_tcp_time_in_log(
        self,
        mock_run: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Log includes TCP connect time when probe succeeds."""
        mock_run.return_value = _mock_ping_success(3.0)

        monitor, session = _make_monitor()
        session.head.return_value = _mock_http_response(0.012)

        with caplog.at_level("INFO"):
            monitor.ping()

        assert "TCP " in caplog.text

    @patch(f"{_MODULE}.subprocess.run")
    def test_tcp_failure_logs_timeout(
        self,
        mock_run: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Log shows 'TCP timeout' when TCP probe fails (status: DEGRADED).

        TCP is now the primary L4 signal, so its failure is logged
        explicitly rather than silently omitted.
        """
        mock_run.return_value = _mock_ping_success(3.0)

        monitor, session = _make_monitor()
        session.head.return_value = _mock_http_response(0.012)

        with (
            patch(
                f"{_MODULE}.socket.create_connection",
                side_effect=OSError("refused"),
            ),
            caplog.at_level("WARNING"),
        ):
            info = monitor.ping()

        assert "TCP timeout" in caplog.text
        assert info.health_status == HealthStatus.DEGRADED
        assert info.tcp_latency_ms is None
        # http_latency_ms uses full elapsed when TCP is unavailable
        assert info.http_latency_ms is not None

    @patch(f"{_MODULE}.subprocess.run")
    def test_server_latency_subtracts_tcp(self, mock_run: MagicMock) -> None:
        """http_latency_ms reflects server time, not total elapsed."""
        mock_run.return_value = _mock_ping_success(3.0)

        monitor, session = _make_monitor()
        # elapsed=12ms, TCP probe will measure ~2ms
        session.head.return_value = _mock_http_response(0.012)

        # Override the autouse fixture with a controlled TCP time
        with patch.object(monitor, "_measure_tcp_connect", return_value=2.0):
            info = monitor.ping()

        # server_ms = 12.0 - 2.0 = 10.0
        assert info.http_latency_ms == pytest.approx(10.0, abs=0.1)

    @patch(f"{_MODULE}.subprocess.run")
    def test_tcp_exceeds_elapsed_uses_full_elapsed(self, mock_run: MagicMock) -> None:
        """When TCP >= elapsed (pool warm edge case), use full elapsed."""
        mock_run.return_value = _mock_ping_success(3.0)

        monitor, session = _make_monitor()
        session.head.return_value = _mock_http_response(0.005)  # 5ms

        # TCP took longer than the full request (shouldn't subtract)
        with patch.object(monitor, "_measure_tcp_connect", return_value=10.0):
            info = monitor.ping()

        # No subtraction — use full elapsed
        assert info.http_latency_ms == pytest.approx(5.0, abs=0.1)

    @patch(f"{_MODULE}.subprocess.run")
    def test_tcp_logged_http_failed(self, mock_run: MagicMock) -> None:
        """TCP runs even when HEAD fails — HEAD failure no longer affects status.

        ICMP + TCP both succeed → RESPONSIVE. HEAD timeout means
        http_latency_ms is None, but the modem is still considered
        reachable at L3 and L4. Application-layer issues surface via
        slow-poll instead.
        """
        mock_run.return_value = _mock_ping_success(3.0)

        monitor, session = _make_monitor()
        session.head.side_effect = requests.Timeout("timeout")

        with patch.object(monitor, "_measure_tcp_connect", return_value=2.0):
            info = monitor.ping()

        assert info.health_status == HealthStatus.RESPONSIVE
        assert info.tcp_latency_ms == 2.0
        assert info.http_latency_ms is None

    @patch(f"{_MODULE}.subprocess.run")
    def test_http_ok_no_latency_detail(self, mock_run: MagicMock) -> None:
        """Probe detail shows 'HTTP HEAD OK' when success but no latency."""
        mock_run.return_value = _mock_ping_success(3.0)

        monitor, session = _make_monitor()
        # Build a HealthInfo with http_ok=True but no http_latency_ms
        info = HealthInfo(health_status=HealthStatus.RESPONSIVE)
        detail = monitor._probe_detail(
            info,
            icmp_ok=True,
            tcp_ok=True,
            http_ok=True,
        )
        assert "HTTP HEAD OK" in detail

    @patch(f"{_MODULE}.subprocess.run")
    def test_no_tcp_when_probes_skipped(
        self,
        mock_run: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """TCP probe does not run when collection evidence skips probes."""
        mock_run.return_value = _mock_ping_success(1.5)

        monitor, session = _make_monitor()

        # Baseline ping
        session.head.return_value = _mock_http_response()
        monitor.ping()

        monitor.record_collection_start()
        monitor.record_collection_end(success=True)

        caplog.clear()
        with caplog.at_level("DEBUG"):
            monitor.ping()

        assert "TCP " not in caplog.text
        assert "TCP/HEAD skipped" in caplog.text
