"""Tests for HealthMonitor — lightweight modem probes.

Covers ICMP + HTTP probes, probe configurations, status derivation,
and logging. Health checks are fully decoupled from data collection.

Use case coverage:
- UC-50: Normal health check — both probes
- UC-53: Outage detection between data polls
- UC-54: ICMP blocked network
- UC-55: Degraded — HTTP fails, ICMP succeeds
- UC-56: Both probes disabled
- UC-57: Health during restart — independent
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest
import requests
from solentlabs.cable_modem_monitor_core.orchestration.modem_health import (
    _PING_TIME_RE,
    HealthMonitor,
)
from solentlabs.cable_modem_monitor_core.orchestration.signals import HealthStatus

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_MODULE = "solentlabs.cable_modem_monitor_core.orchestration.modem_health"


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
    def test_http_uses_get_when_head_unsupported(self, mock_run: MagicMock) -> None:
        """supports_head=False → uses GET instead of HEAD."""
        mock_run.return_value = _mock_ping_success()

        monitor, session = _make_monitor(supports_head=False)
        session.get.return_value = _mock_http_response()
        info = monitor.ping()

        session.get.assert_called_once()
        session.head.assert_not_called()
        assert info.health_status == HealthStatus.RESPONSIVE

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
        """Both probes fail → UNRESPONSIVE."""
        mock_run.return_value = _mock_ping_failure()

        monitor, session = _make_monitor()
        session.head.side_effect = requests.ConnectionError("refused")
        info = monitor.ping()

        assert info.health_status == HealthStatus.UNRESPONSIVE
        assert info.icmp_latency_ms is None
        assert info.http_latency_ms is None


# ------------------------------------------------------------------
# UC-54: ICMP blocked network
# ------------------------------------------------------------------


class TestUC54ICMPBlocked:
    """Network blocks ICMP but HTTP works."""

    @patch(f"{_MODULE}.subprocess.run")
    def test_icmp_fail_http_pass(self, mock_run: MagicMock) -> None:
        """ICMP fails + HTTP succeeds → ICMP_BLOCKED."""
        mock_run.return_value = _mock_ping_failure()

        monitor, session = _make_monitor()
        session.head.return_value = _mock_http_response()
        info = monitor.ping()

        assert info.health_status == HealthStatus.ICMP_BLOCKED


# ------------------------------------------------------------------
# UC-55: Degraded — HTTP fails, ICMP succeeds
# ------------------------------------------------------------------


class TestUC55Degraded:
    """ICMP works but HTTP fails (web server hung)."""

    @patch(f"{_MODULE}.subprocess.run")
    def test_icmp_pass_http_fail(self, mock_run: MagicMock) -> None:
        """ICMP succeeds + HTTP fails → DEGRADED."""
        mock_run.return_value = _mock_ping_success(4.0)

        monitor, session = _make_monitor()
        session.head.side_effect = requests.Timeout("timeout")
        info = monitor.ping()

        assert info.health_status == HealthStatus.DEGRADED
        assert info.icmp_latency_ms == 4.0
        assert info.http_latency_ms is None


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
        info = monitor.ping()

        assert info.health_status == HealthStatus.UNRESPONSIVE


# ------------------------------------------------------------------
# HTTP-only mode (supports_icmp=False)
# ------------------------------------------------------------------


class TestHTTPOnlyMode:
    """Only HTTP probe runs when ICMP is not supported."""

    @patch(f"{_MODULE}.subprocess.run")
    def test_http_pass(self, mock_run: MagicMock) -> None:
        """HTTP only, passes → RESPONSIVE."""
        monitor, session = _make_monitor(supports_icmp=False)
        session.head.return_value = _mock_http_response()
        info = monitor.ping()

        mock_run.assert_not_called()
        assert info.health_status == HealthStatus.RESPONSIVE

    def test_http_fail(self) -> None:
        """HTTP only, fails → UNRESPONSIVE."""
        monitor, session = _make_monitor(supports_icmp=False)
        session.head.side_effect = requests.Timeout("timeout")
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
        """DEGRADED logs at WARNING level."""
        mock_run.return_value = _mock_ping_success()

        monitor, session = _make_monitor()
        session.head.side_effect = requests.Timeout("timeout")
        with caplog.at_level("WARNING"):
            monitor.ping()

        assert "Health check [T100]: degraded" in caplog.text

    @patch(f"{_MODULE}.subprocess.run")
    def test_unresponsive_logs_warning(
        self,
        mock_run: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """UNRESPONSIVE logs at WARNING level."""
        mock_run.return_value = _mock_ping_failure()

        monitor, session = _make_monitor()
        session.head.side_effect = requests.ConnectionError("refused")
        with caplog.at_level("WARNING"):
            monitor.ping()

        assert "Health check [T100]: unresponsive" in caplog.text
