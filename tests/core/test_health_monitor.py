"""Tests for Modem Health Monitor."""

from __future__ import annotations

import ssl
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.cable_modem_monitor.core.health_monitor import HealthCheckResult, ModemHealthMonitor


class TestHealthCheckResult:
    """Test HealthCheckResult dataclass."""

    def test_is_healthy_both_pass(self):
        """Test is_healthy when both ping and HTTP pass."""
        result = HealthCheckResult(
            timestamp=1234567890.0,
            ping_success=True,
            ping_latency_ms=5.0,
            http_success=True,
            http_latency_ms=10.0,
        )

        assert result.is_healthy is True

    def test_is_healthy_ping_only(self):
        """Test is_healthy when only ping passes."""
        result = HealthCheckResult(
            timestamp=1234567890.0,
            ping_success=True,
            ping_latency_ms=5.0,
            http_success=False,
            http_latency_ms=None,
        )

        assert result.is_healthy is True

    def test_is_healthy_http_only(self):
        """Test is_healthy when only HTTP passes."""
        result = HealthCheckResult(
            timestamp=1234567890.0,
            ping_success=False,
            ping_latency_ms=None,
            http_success=True,
            http_latency_ms=10.0,
        )

        assert result.is_healthy is True

    def test_is_healthy_both_fail(self):
        """Test is_healthy when both ping and HTTP fail."""
        result = HealthCheckResult(
            timestamp=1234567890.0,
            ping_success=False,
            ping_latency_ms=None,
            http_success=False,
            http_latency_ms=None,
        )

        assert result.is_healthy is False

    def test_status_responsive(self):
        """Test status when fully responsive."""
        result = HealthCheckResult(
            timestamp=1234567890.0, ping_success=True, ping_latency_ms=5.0, http_success=True, http_latency_ms=10.0
        )

        assert result.status == "responsive"

    def test_status_degraded(self):
        """Test status when ping works but HTTP fails."""
        result = HealthCheckResult(
            timestamp=1234567890.0, ping_success=True, ping_latency_ms=5.0, http_success=False, http_latency_ms=None
        )

        assert result.status == "degraded"

    def test_status_icmp_blocked(self):
        """Test status when HTTP works but ping fails."""
        result = HealthCheckResult(
            timestamp=1234567890.0, ping_success=False, ping_latency_ms=None, http_success=True, http_latency_ms=10.0
        )

        assert result.status == "icmp_blocked"

    def test_status_unresponsive(self):
        """Test status when both checks fail."""
        result = HealthCheckResult(
            timestamp=1234567890.0, ping_success=False, ping_latency_ms=None, http_success=False, http_latency_ms=None
        )

        assert result.status == "unresponsive"

    def test_diagnosis_messages(self):
        """Test diagnosis messages for all states."""
        responsive = HealthCheckResult(1.0, True, 5.0, True, 10.0)
        degraded = HealthCheckResult(1.0, True, 5.0, False, None)
        icmp_blocked = HealthCheckResult(1.0, False, None, True, 10.0)
        unresponsive = HealthCheckResult(1.0, False, None, False, None)

        assert responsive.diagnosis == "Fully responsive"
        assert degraded.diagnosis == "Web server issue"
        assert icmp_blocked.diagnosis == "ICMP blocked (firewall)"
        assert unresponsive.diagnosis == "Network down / offline"


class TestModemHealthMonitorInit:
    """Test ModemHealthMonitor initialization."""

    def test_init_defaults(self):
        """Test initialization with default parameters."""
        monitor = ModemHealthMonitor()

        assert monitor.max_history == 100
        assert monitor.verify_ssl is False
        assert len(monitor.history) == 0
        assert monitor.consecutive_failures == 0
        assert monitor.total_checks == 0
        assert monitor.successful_checks == 0

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        monitor = ModemHealthMonitor(max_history=50, verify_ssl=True)

        assert monitor.max_history == 50
        assert monitor.verify_ssl is True

    def test_init_with_ssl_context(self):
        """Test initialization with pre-created SSL context."""
        custom_context = ssl.create_default_context()
        monitor = ModemHealthMonitor(ssl_context=custom_context)

        assert monitor._ssl_context is custom_context

    def test_init_creates_ssl_context_when_none_provided(self):
        """Test that SSL context is created if not provided."""
        monitor = ModemHealthMonitor()

        assert isinstance(monitor._ssl_context, ssl.SSLContext)


class TestInputValidation:
    """Test input validation methods."""

    def test_is_valid_host_ipv4(self):
        """Test IPv4 address validation."""
        monitor = ModemHealthMonitor()

        assert monitor._is_valid_host("192.168.1.1") is True
        assert monitor._is_valid_host("10.0.0.1") is True
        assert monitor._is_valid_host("255.255.255.255") is True

    def test_is_valid_host_hostname(self):
        """Test hostname validation."""
        monitor = ModemHealthMonitor()

        assert monitor._is_valid_host("modem.local") is True
        assert monitor._is_valid_host("my-modem") is True
        assert monitor._is_valid_host("example.com") is True

    def test_is_valid_host_invalid_chars(self):
        """Test that shell metacharacters are blocked."""
        monitor = ModemHealthMonitor()

        assert monitor._is_valid_host("192.168.1.1; rm -rf /") is False
        assert monitor._is_valid_host("192.168.1.1 && echo hacked") is False
        assert monitor._is_valid_host("$(malicious)") is False
        assert monitor._is_valid_host("host|pipe") is False
        assert monitor._is_valid_host("host`backtick`") is False

    def test_is_valid_host_empty_or_too_long(self):
        """Test empty or overly long hostnames."""
        monitor = ModemHealthMonitor()

        assert monitor._is_valid_host("") is False
        assert monitor._is_valid_host("a" * 254) is False  ***REMOVED*** Too long

    def test_is_valid_url(self):
        """Test URL validation."""
        monitor = ModemHealthMonitor()

        assert monitor._is_valid_url("http://192.168.1.1") is True
        assert monitor._is_valid_url("https://192.168.1.1") is True
        assert monitor._is_valid_url("http://modem.local") is True
        assert monitor._is_valid_url("https://modem.local:8080") is True

    def test_is_valid_url_invalid_scheme(self):
        """Test that non-HTTP schemes are rejected."""
        monitor = ModemHealthMonitor()

        assert monitor._is_valid_url("ftp://192.168.1.1") is False
        assert monitor._is_valid_url("file:///etc/passwd") is False
        assert monitor._is_valid_url("javascript:alert(1)") is False

    def test_is_valid_url_no_netloc(self):
        """Test that URLs without netloc are rejected."""
        monitor = ModemHealthMonitor()

        assert monitor._is_valid_url("http://") is False
        assert monitor._is_valid_url("https://") is False

    def test_is_safe_redirect_same_host(self):
        """Test that same-host redirects are allowed."""
        monitor = ModemHealthMonitor()

        assert monitor._is_safe_redirect("http://192.168.1.1/page1", "http://192.168.1.1/page2") is True

    def test_is_safe_redirect_relative(self):
        """Test that relative redirects are allowed."""
        monitor = ModemHealthMonitor()

        assert monitor._is_safe_redirect("http://192.168.1.1/page1", "/page2") is True

    def test_is_safe_redirect_cross_host(self):
        """Test that cross-host redirects are blocked."""
        monitor = ModemHealthMonitor()

        assert monitor._is_safe_redirect("http://192.168.1.1", "http://evil.com") is False

    def test_is_safe_redirect_non_http_scheme(self):
        """Test that non-HTTP scheme redirects are blocked."""
        monitor = ModemHealthMonitor()

        assert monitor._is_safe_redirect("http://192.168.1.1", "ftp://192.168.1.1") is False
        assert monitor._is_safe_redirect("http://192.168.1.1", "javascript:alert(1)") is False


@pytest.mark.asyncio
class TestHealthCheckPing:
    """Test ping check functionality."""

    async def test_ping_success(self):
        """Test successful ping check."""
        monitor = ModemHealthMonitor()

        with (
            patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
            patch(
                "custom_components.cable_modem_monitor.core.health_monitor.time.time",
                side_effect=[1000.0, 1000.05],
            ),
        ):
            ***REMOVED*** Mock successful ping
            mock_proc = AsyncMock()
            mock_proc.communicate.return_value = (b"", b"")
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            success, latency = await monitor._check_ping("192.168.1.1")

            assert success is True
            assert latency is not None
            assert latency > 0

            ***REMOVED*** Verify ping command
            mock_exec.assert_called_once_with(
                "ping", "-c", "1", "-W", "2", "192.168.1.1", stdout=-1, stderr=-1  ***REMOVED*** asyncio.subprocess.PIPE
            )

    async def test_ping_failure(self):
        """Test failed ping check."""
        monitor = ModemHealthMonitor()

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            ***REMOVED*** Mock failed ping
            mock_proc = AsyncMock()
            mock_proc.communicate.return_value = (b"", b"ping: unknown host")
            mock_proc.returncode = 1
            mock_exec.return_value = mock_proc

            success, latency = await monitor._check_ping("192.168.1.1")

            assert success is False
            assert latency is None

    async def test_ping_invalid_host(self):
        """Test ping with invalid host."""
        monitor = ModemHealthMonitor()

        success, latency = await monitor._check_ping("invalid; rm -rf /")

        assert success is False
        assert latency is None

    async def test_ping_exception_handling(self):
        """Test ping handles exceptions gracefully."""
        monitor = ModemHealthMonitor()

        with patch("asyncio.create_subprocess_exec", side_effect=Exception("Network error")):
            success, latency = await monitor._check_ping("192.168.1.1")

            assert success is False
            assert latency is None


@pytest.mark.asyncio
class TestHealthCheckHTTP:
    """Test HTTP check functionality."""

    async def test_http_success_head(self):
        """Test successful HTTP HEAD check."""
        monitor = ModemHealthMonitor()

        time_patch = "custom_components.cable_modem_monitor.core.health_monitor.time.time"
        timeout_patch = "custom_components.cable_modem_monitor.core.health_monitor.aiohttp.ClientTimeout"
        connector_patch = "custom_components.cable_modem_monitor.core.health_monitor.aiohttp.TCPConnector"
        session_patch = "custom_components.cable_modem_monitor.core.health_monitor.aiohttp.ClientSession"

        with (
            patch(time_patch, side_effect=[1000.0, 1000.01]),
            patch(timeout_patch),
            patch(connector_patch),
            patch(session_patch) as mock_session_class,
        ):
            ***REMOVED*** Create the response that will be returned when entering the context manager
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.headers = {}

            ***REMOVED*** Create the async context manager that head() returns
            mock_head_cm = MagicMock()
            mock_head_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_head_cm.__aexit__ = AsyncMock(return_value=None)

            ***REMOVED*** Create the session
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            ***REMOVED*** head() returns the context manager directly (not a coroutine)
            mock_session.head = MagicMock(return_value=mock_head_cm)

            mock_session_class.return_value = mock_session

            success, latency = await monitor._check_http("http://192.168.1.1")

            assert success is True
            assert latency is not None
            assert latency > 0

    async def test_http_fallback_to_get(self):
        """Test HTTP falls back to GET when HEAD fails."""
        monitor = ModemHealthMonitor()

        time_patch = "custom_components.cable_modem_monitor.core.health_monitor.time.time"
        timeout_patch = "custom_components.cable_modem_monitor.core.health_monitor.aiohttp.ClientTimeout"
        connector_patch = "custom_components.cable_modem_monitor.core.health_monitor.aiohttp.TCPConnector"
        session_patch = "custom_components.cable_modem_monitor.core.health_monitor.aiohttp.ClientSession"

        with (
            patch(time_patch, side_effect=[1000.0, 1000.005, 1000.020]),
            patch(timeout_patch),
            patch(connector_patch),
            patch(session_patch) as mock_session_class,
        ):
            ***REMOVED*** GET response
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.headers = {}

            ***REMOVED*** Create the async context manager that get() returns
            mock_get_cm = MagicMock()
            mock_get_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_get_cm.__aexit__ = AsyncMock(return_value=None)

            ***REMOVED*** Create the session
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            ***REMOVED*** HEAD fails
            mock_session.head = MagicMock(side_effect=aiohttp.ClientError("HEAD not supported"))
            ***REMOVED*** GET returns the context manager directly (not a coroutine)
            mock_session.get = MagicMock(return_value=mock_get_cm)

            mock_session_class.return_value = mock_session

            success, latency = await monitor._check_http("http://192.168.1.1")

            assert success is True
            assert latency is not None

    async def test_http_accepts_4xx_as_alive(self):
        """Test that 4xx responses are considered alive."""
        monitor = ModemHealthMonitor()

        time_patch = "custom_components.cable_modem_monitor.core.health_monitor.time.time"
        timeout_patch = "custom_components.cable_modem_monitor.core.health_monitor.aiohttp.ClientTimeout"
        connector_patch = "custom_components.cable_modem_monitor.core.health_monitor.aiohttp.TCPConnector"
        session_patch = "custom_components.cable_modem_monitor.core.health_monitor.aiohttp.ClientSession"

        with (
            patch(time_patch, side_effect=[1000.0, 1000.012]),
            patch(timeout_patch),
            patch(connector_patch),
            patch(session_patch) as mock_session_class,
        ):
            ***REMOVED*** Create the response that will be returned when entering the context manager
            mock_response = MagicMock()
            mock_response.status = 404  ***REMOVED*** Not Found, but server is alive
            mock_response.headers = {}

            ***REMOVED*** Create the async context manager that head() returns
            mock_head_cm = MagicMock()
            mock_head_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_head_cm.__aexit__ = AsyncMock(return_value=None)

            ***REMOVED*** Create the session
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            ***REMOVED*** head() returns the context manager directly (not a coroutine)
            mock_session.head = MagicMock(return_value=mock_head_cm)

            mock_session_class.return_value = mock_session

            success, latency = await monitor._check_http("http://192.168.1.1")

            assert success is True  ***REMOVED*** Server responded

    async def test_http_rejects_5xx(self):
        """Test that 5xx responses are considered failures."""
        monitor = ModemHealthMonitor()

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_response = AsyncMock()
            mock_response.status = 500  ***REMOVED*** Server error
            mock_response.__aenter__.return_value = mock_response
            mock_session.head.return_value = mock_response
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = AsyncMock()
            mock_session_class.return_value = mock_session

            success, latency = await monitor._check_http("http://192.168.1.1")

            assert success is False

    async def test_http_invalid_url(self):
        """Test HTTP check with invalid URL."""
        monitor = ModemHealthMonitor()

        success, latency = await monitor._check_http("ftp://invalid")

        assert success is False
        assert latency is None

    async def test_http_timeout(self):
        """Test HTTP check handles timeout."""
        monitor = ModemHealthMonitor()

        time_patch = "custom_components.cable_modem_monitor.core.health_monitor.time.time"
        timeout_patch = "custom_components.cable_modem_monitor.core.health_monitor.aiohttp.ClientTimeout"
        connector_patch = "custom_components.cable_modem_monitor.core.health_monitor.aiohttp.TCPConnector"
        session_patch = "custom_components.cable_modem_monitor.core.health_monitor.aiohttp.ClientSession"

        with (
            patch(time_patch),
            patch(timeout_patch),
            patch(connector_patch),
            patch(session_patch) as mock_session_class,
        ):
            ***REMOVED*** Create the session
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            ***REMOVED*** Both HEAD and GET timeout
            mock_session.head = MagicMock(side_effect=TimeoutError("Connection timeout"))
            mock_session.get = MagicMock(side_effect=TimeoutError("Connection timeout"))

            mock_session_class.return_value = mock_session

            success, latency = await monitor._check_http("http://192.168.1.1")

            assert success is False
            assert latency is None


@pytest.mark.asyncio
class TestHealthCheckFullFlow:
    """Test full health check flow."""

    async def test_check_health_both_succeed(self):
        """Test health check when both ping and HTTP succeed."""
        monitor = ModemHealthMonitor()

        with (
            patch.object(monitor, "_check_ping", return_value=(True, 5.0)),
            patch.object(monitor, "_check_http", return_value=(True, 10.0)),
        ):
            result = await monitor.check_health("http://192.168.1.1")

            assert result.ping_success is True
            assert result.http_success is True
            assert result.status == "responsive"
            assert len(monitor.history) == 1
            assert monitor.total_checks == 1
            assert monitor.successful_checks == 1
            assert monitor.consecutive_failures == 0

    async def test_check_health_both_fail(self):
        """Test health check when both checks fail."""
        monitor = ModemHealthMonitor()

        with (
            patch.object(monitor, "_check_ping", return_value=(False, None)),
            patch.object(monitor, "_check_http", return_value=(False, None)),
        ):
            result = await monitor.check_health("http://192.168.1.1")

            assert result.ping_success is False
            assert result.http_success is False
            assert result.status == "unresponsive"
            assert monitor.total_checks == 1
            assert monitor.successful_checks == 0
            assert monitor.consecutive_failures == 1

    async def test_check_health_handles_exceptions(self):
        """Test that check_health handles exceptions gracefully."""
        monitor = ModemHealthMonitor()

        with (
            patch.object(monitor, "_check_ping", side_effect=Exception("Ping error")),
            patch.object(monitor, "_check_http", side_effect=Exception("HTTP error")),
        ):
            result = await monitor.check_health("http://192.168.1.1")

            assert result.ping_success is False
            assert result.http_success is False
            assert result.status == "unresponsive"

    async def test_history_limit(self):
        """Test that history is limited to max_history."""
        monitor = ModemHealthMonitor(max_history=5)

        with (
            patch.object(monitor, "_check_ping", return_value=(True, 5.0)),
            patch.object(monitor, "_check_http", return_value=(True, 10.0)),
        ):
            ***REMOVED*** Add 10 checks
            for _ in range(10):
                await monitor.check_health("http://192.168.1.1")

            ***REMOVED*** History should be limited to 5
            assert len(monitor.history) == 5

    async def test_consecutive_failures_reset(self):
        """Test that consecutive failures reset on success."""
        monitor = ModemHealthMonitor()

        ***REMOVED*** Fail twice
        with (
            patch.object(monitor, "_check_ping", return_value=(False, None)),
            patch.object(monitor, "_check_http", return_value=(False, None)),
        ):
            await monitor.check_health("http://192.168.1.1")
            await monitor.check_health("http://192.168.1.1")

        assert monitor.consecutive_failures == 2

        ***REMOVED*** Succeed once
        with (
            patch.object(monitor, "_check_ping", return_value=(True, 5.0)),
            patch.object(monitor, "_check_http", return_value=(True, 10.0)),
        ):
            await monitor.check_health("http://192.168.1.1")

        assert monitor.consecutive_failures == 0


class TestAverageLatency:
    """Test average latency calculations."""

    @pytest.mark.asyncio
    async def test_average_ping_latency(self):
        """Test average ping latency calculation."""
        monitor = ModemHealthMonitor()

        ***REMOVED*** Add results with different ping latencies
        monitor.history.append(HealthCheckResult(1.0, True, 5.0, True, 10.0))
        monitor.history.append(HealthCheckResult(2.0, True, 7.0, True, 12.0))
        monitor.history.append(HealthCheckResult(3.0, True, 9.0, True, 14.0))

        avg = monitor.average_ping_latency

        assert avg == pytest.approx(7.0)  ***REMOVED*** (5 + 7 + 9) / 3

    @pytest.mark.asyncio
    async def test_average_http_latency(self):
        """Test average HTTP latency calculation."""
        monitor = ModemHealthMonitor()

        monitor.history.append(HealthCheckResult(1.0, True, 5.0, True, 10.0))
        monitor.history.append(HealthCheckResult(2.0, True, 7.0, True, 20.0))
        monitor.history.append(HealthCheckResult(3.0, True, 9.0, True, 30.0))

        avg = monitor.average_http_latency

        assert avg == pytest.approx(20.0)  ***REMOVED*** (10 + 20 + 30) / 3

    def test_no_history(self):
        """Test average latency with no history."""
        monitor = ModemHealthMonitor()

        assert monitor.average_ping_latency is None
        assert monitor.average_http_latency is None

    def test_filters_failures(self):
        """Test that failed checks are excluded from averages."""
        monitor = ModemHealthMonitor()

        monitor.history.append(HealthCheckResult(1.0, True, 5.0, True, 10.0))
        monitor.history.append(HealthCheckResult(2.0, False, None, False, None))  ***REMOVED*** Failed
        monitor.history.append(HealthCheckResult(3.0, True, 7.0, True, 20.0))

        assert monitor.average_ping_latency == pytest.approx(6.0)  ***REMOVED*** (5 + 7) / 2
        assert monitor.average_http_latency == pytest.approx(15.0)  ***REMOVED*** (10 + 20) / 2


class TestStatusSummary:
    """Test status summary generation."""

    @pytest.mark.asyncio
    async def test_with_history(self):
        """Test status summary with check history."""
        monitor = ModemHealthMonitor()

        monitor.history.append(HealthCheckResult(1.0, True, 5.0, True, 10.0))
        monitor.history.append(HealthCheckResult(2.0, True, 6.0, True, 12.0))
        monitor.total_checks = 2
        monitor.successful_checks = 2
        monitor.consecutive_failures = 0

        summary = monitor.get_status_summary()

        assert summary["status"] == "responsive"
        assert summary["diagnosis"] == "Fully responsive"
        assert summary["consecutive_failures"] == 0
        assert summary["total_checks"] == 2
        assert summary["ping_success"] is True
        assert summary["http_success"] is True
        assert "avg_ping_latency_ms" in summary
        assert "avg_http_latency_ms" in summary

    def test_no_history(self):
        """Test status summary with no history."""
        monitor = ModemHealthMonitor()

        summary = monitor.get_status_summary()

        assert summary["status"] == "unknown"
        assert summary["consecutive_failures"] == 0
        assert summary["total_checks"] == 0
