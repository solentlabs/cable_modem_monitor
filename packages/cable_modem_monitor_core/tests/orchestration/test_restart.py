"""Tests for RestartMonitor — restart recovery.

Covers response detection, channel stabilization, cancellation,
timeouts, and probe strategies.

Use case coverage:
- UC-40: Planned restart — full recovery
- UC-41: Restart cancel — clean shutdown
- UC-46: Response timeout — modem never responds
- UC-47: Channel stabilization timeout — channels never stabilize
- UC-48: Skip channel stabilization — channel_stabilization_timeout=0
"""

from __future__ import annotations

import threading
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from solentlabs.cable_modem_monitor_core.orchestration.channel_stability import (
    GRACE_PERIOD_SECONDS,
    STABILITY_COUNT,
)
from solentlabs.cable_modem_monitor_core.orchestration.models import (
    HealthInfo,
    ModemResult,
)
from solentlabs.cable_modem_monitor_core.orchestration.restart import (
    RestartMonitor,
)
from solentlabs.cable_modem_monitor_core.orchestration.signals import (
    CollectorSignal,
    HealthStatus,
    RestartPhase,
)

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_modem_data(
    ds_count: int = 24,
    us_count: int = 4,
) -> dict[str, Any]:
    """Build a minimal modem_data dict with channel lists."""
    return {
        "downstream": [{"channel_id": i + 1} for i in range(ds_count)],
        "upstream": [{"channel_id": i + 1} for i in range(us_count)],
        "system_info": {"firmware": "1.0"},
    }


def _ok_result(ds: int = 24, us: int = 4) -> ModemResult:
    """Build a successful ModemResult with channel counts."""
    return ModemResult(success=True, modem_data=_make_modem_data(ds, us))


def _fail_result() -> ModemResult:
    """Build a failed ModemResult (connectivity error)."""
    return ModemResult(
        success=False,
        signal=CollectorSignal.CONNECTIVITY,
        error="Connection refused",
    )


def _mock_collector(
    results: list[ModemResult] | None = None,
) -> MagicMock:
    """Build a mock ModemDataCollector."""
    collector = MagicMock()
    if results is not None:
        collector.execute.side_effect = results
    else:
        collector.execute.return_value = _ok_result()
    return collector


def _mock_health_monitor(
    responses: list[HealthInfo] | HealthInfo | None = None,
) -> MagicMock:
    """Build a mock HealthMonitor."""
    hm = MagicMock()
    if responses is None:
        hm.ping.return_value = HealthInfo(health_status=HealthStatus.RESPONSIVE)
    elif isinstance(responses, list):
        hm.ping.side_effect = responses
    else:
        hm.ping.return_value = responses
    return hm


def _make_restart_monitor(
    collector: MagicMock | None = None,
    health_monitor: MagicMock | None = None,
    response_timeout: int = 120,
    channel_stabilization_timeout: int = 300,
    probe_interval: int = 10,
) -> RestartMonitor:
    """Build a RestartMonitor with defaults."""
    if collector is None:
        collector = _mock_collector()
    return RestartMonitor(
        collector=collector,
        health_monitor=health_monitor,
        response_timeout=response_timeout,
        channel_stabilization_timeout=channel_stabilization_timeout,
        probe_interval=probe_interval,
    )


# ------------------------------------------------------------------
# UC-40: Planned restart — full recovery
# ------------------------------------------------------------------


class TestUC40FullRecovery:
    """Full restart with response detection + channel stabilization."""

    @patch("solentlabs.cable_modem_monitor_core.orchestration.restart.time.sleep")
    @patch("solentlabs.cable_modem_monitor_core.orchestration.restart.time.monotonic")
    def test_full_recovery(self, mock_monotonic: MagicMock, mock_sleep: MagicMock) -> None:
        """Modem responds, channels stabilize → COMPLETE."""
        # Response detection: health monitor responds immediately
        hm = _mock_health_monitor()

        # Channel stabilization: collector returns stable counts
        stable_results = [_ok_result(24, 4)] * (STABILITY_COUNT + 4)
        collector = _mock_collector(stable_results)

        # Time simulation:
        # start=0, responds at probe 1 (~10s), channels stabilize
        times = [0.0]  # start
        # Response detection: deadline check, evidence clear check
        t = 0.0
        for _ in range(5):
            t += 0.1
            times.append(t)
        # Response succeeds quickly
        t = 10.0
        times.append(t)  # response_time log
        # Channel stabilization: each probe needs multiple monotonic calls
        for _i in range(STABILITY_COUNT + 5):
            t += 10.0
            times.extend([t, t, t + 0.01])
        # Grace period check — need to exceed GRACE_PERIOD_SECONDS
        t += GRACE_PERIOD_SECONDS + 1
        times.extend([t, t, t + 0.01])
        # Final elapsed
        times.append(t + 1)

        mock_monotonic.side_effect = times + [times[-1]] * 100

        monitor = _make_restart_monitor(
            collector=collector,
            health_monitor=hm,
            probe_interval=10,
        )
        result = monitor.monitor_recovery()

        assert result.success is True
        assert result.phase_reached == RestartPhase.COMPLETE
        collector.clear_session.assert_called_once()

    @patch("solentlabs.cable_modem_monitor_core.orchestration.restart.time.sleep")
    @patch("solentlabs.cable_modem_monitor_core.orchestration.restart.time.monotonic")
    def test_clears_session(self, mock_monotonic: MagicMock, mock_sleep: MagicMock) -> None:
        """Recovery clears collector session."""
        hm = _mock_health_monitor()
        collector = _mock_collector()

        # Quick success: respond immediately, skip channel stabilization
        mock_monotonic.side_effect = [0.0, 0.0, 0.1, 0.2, 10.0, 10.1] + [10.2] * 50

        monitor = _make_restart_monitor(
            collector=collector,
            health_monitor=hm,
            channel_stabilization_timeout=0,
        )
        monitor.monitor_recovery()

        collector.clear_session.assert_called_once()


# ------------------------------------------------------------------
# UC-41: Restart cancel — clean shutdown
# ------------------------------------------------------------------


class TestUC41Cancel:
    """Cancel event causes clean exit."""

    @patch("solentlabs.cable_modem_monitor_core.orchestration.restart.time.monotonic")
    def test_cancel_during_response_detection(self, mock_monotonic: MagicMock) -> None:
        """Cancel during response detection → WAITING_RESPONSE."""
        mock_monotonic.side_effect = [0.0, 0.0, 0.1, 0.2] + [0.3] * 50

        cancel = threading.Event()
        cancel.set()  # Already cancelled

        hm = _mock_health_monitor(HealthInfo(health_status=HealthStatus.UNRESPONSIVE))

        monitor = _make_restart_monitor(health_monitor=hm)
        result = monitor.monitor_recovery(cancel_event=cancel)

        assert result.success is False
        assert result.phase_reached == RestartPhase.WAITING_RESPONSE
        assert "Cancelled" in result.error

    @patch("solentlabs.cable_modem_monitor_core.orchestration.restart.time.monotonic")
    def test_cancel_during_channel_stabilization(self, mock_monotonic: MagicMock) -> None:
        """Cancel during channel stabilization → CHANNEL_SYNC."""
        # Response detection succeeds immediately
        hm = _mock_health_monitor()

        cancel = threading.Event()
        collector = _mock_collector([_ok_result(24, 4)] * 10)

        # Response: succeeds. Stabilization: one poll then cancel
        times = [0.0, 0.0, 0.1, 0.2, 10.0]  # start + response
        times += [10.1, 10.2, 10.3, 10.4]  # stabilization start
        times += [10.5] * 50
        mock_monotonic.side_effect = times

        monitor = _make_restart_monitor(
            collector=collector,
            health_monitor=hm,
            probe_interval=10,
        )

        # Cancel after response succeeds (checked at stabilization loop top)
        def set_cancel_on_wait(timeout: float) -> bool:
            cancel.set()
            return True

        cancel.wait = set_cancel_on_wait  # type: ignore[assignment]

        result = monitor.monitor_recovery(cancel_event=cancel)

        assert result.success is False
        assert result.phase_reached == RestartPhase.CHANNEL_SYNC


# ------------------------------------------------------------------
# UC-46: Response timeout
# ------------------------------------------------------------------


class TestUC46ResponseTimeout:
    """Modem never responds — response detection times out."""

    @patch("solentlabs.cable_modem_monitor_core.orchestration.restart.time.sleep")
    @patch("solentlabs.cable_modem_monitor_core.orchestration.restart.time.monotonic")
    def test_response_timeout(self, mock_monotonic: MagicMock, mock_sleep: MagicMock) -> None:
        """All probes fail for response_timeout → WAITING_RESPONSE."""
        hm = _mock_health_monitor(HealthInfo(health_status=HealthStatus.UNRESPONSIVE))

        # Time advances past deadline
        times = [0.0, 0.0]  # start, deadline calc
        t = 0.0
        for _i in range(15):
            t += 10.0
            times.extend([t, t + 0.1])
        # Past deadline
        times.append(121.0)
        times += [121.0] * 20

        mock_monotonic.side_effect = times

        monitor = _make_restart_monitor(
            health_monitor=hm,
            response_timeout=120,
            probe_interval=10,
        )
        result = monitor.monitor_recovery()

        assert result.success is False
        assert result.phase_reached == RestartPhase.WAITING_RESPONSE
        assert "timeout" in result.error.lower()

    @patch("solentlabs.cable_modem_monitor_core.orchestration.restart.time.sleep")
    @patch("solentlabs.cable_modem_monitor_core.orchestration.restart.time.monotonic")
    def test_collector_fallback_timeout(self, mock_monotonic: MagicMock, mock_sleep: MagicMock) -> None:
        """No health monitor → collector fallback, still times out."""
        collector = _mock_collector([_fail_result()] * 20)

        times = [0.0, 0.0]
        t = 0.0
        for _ in range(15):
            t += 10.0
            times.extend([t, t + 0.1])
        times.append(121.0)
        times += [121.0] * 20

        mock_monotonic.side_effect = times

        monitor = _make_restart_monitor(
            collector=collector,
            health_monitor=None,
            response_timeout=120,
            probe_interval=10,
        )
        result = monitor.monitor_recovery()

        assert result.success is False
        assert result.phase_reached == RestartPhase.WAITING_RESPONSE


# ------------------------------------------------------------------
# UC-47: Channel stabilization timeout
# ------------------------------------------------------------------


class TestUC47ChannelStabilizationTimeout:
    """Channels never stabilize — channel stabilization times out."""

    @patch("solentlabs.cable_modem_monitor_core.orchestration.restart.time.sleep")
    @patch("solentlabs.cable_modem_monitor_core.orchestration.restart.time.monotonic")
    def test_channel_stabilization_timeout(self, mock_monotonic: MagicMock, mock_sleep: MagicMock) -> None:
        """Counts keep changing → CHANNEL_SYNC timeout."""
        hm = _mock_health_monitor()

        # Collector returns changing channel counts
        changing_results = [_ok_result(ds, 4) for ds in range(8, 38)]
        collector = _mock_collector(changing_results)

        # Response: quick success. Stabilization: time exceeds deadline
        times = [0.0, 0.0, 0.1, 0.2, 10.0]  # response detection
        t = 10.0
        for _ in range(35):
            t += 10.0
            times.extend([t, t + 0.01, t + 0.02])
        # Past channel deadline
        times.append(t + 300.0)
        times += [t + 300.0] * 20

        mock_monotonic.side_effect = times

        monitor = _make_restart_monitor(
            collector=collector,
            health_monitor=hm,
            channel_stabilization_timeout=300,
            probe_interval=10,
        )
        result = monitor.monitor_recovery()

        assert result.success is False
        assert result.phase_reached == RestartPhase.CHANNEL_SYNC
        assert "timeout" in result.error.lower()


# ------------------------------------------------------------------
# UC-48: Skip channel stabilization
# ------------------------------------------------------------------


class TestUC48SkipChannelStabilization:
    """channel_stabilization_timeout=0 → stabilization skipped."""

    @patch("solentlabs.cable_modem_monitor_core.orchestration.restart.time.sleep")
    @patch("solentlabs.cable_modem_monitor_core.orchestration.restart.time.monotonic")
    def test_skip_channel_stabilization(self, mock_monotonic: MagicMock, mock_sleep: MagicMock) -> None:
        """timeout=0 → COMPLETE immediately after response."""
        hm = _mock_health_monitor()

        mock_monotonic.side_effect = [0.0, 0.0, 0.1, 0.2, 10.0, 10.1] + [10.2] * 20

        monitor = _make_restart_monitor(
            health_monitor=hm,
            channel_stabilization_timeout=0,
        )
        result = monitor.monitor_recovery()

        assert result.success is True
        assert result.phase_reached == RestartPhase.COMPLETE


# ------------------------------------------------------------------
# Probe strategy
# ------------------------------------------------------------------


class TestProbeStrategy:
    """Response detection uses HealthMonitor when available."""

    @patch("solentlabs.cable_modem_monitor_core.orchestration.restart.time.sleep")
    @patch("solentlabs.cable_modem_monitor_core.orchestration.restart.time.monotonic")
    def test_uses_health_monitor_for_response_detection(self, mock_monotonic: MagicMock, mock_sleep: MagicMock) -> None:
        """Response detection probes via HealthMonitor, not collector."""
        hm = _mock_health_monitor()
        collector = _mock_collector()

        mock_monotonic.side_effect = [0.0, 0.0, 0.1, 0.2, 10.0, 10.1] + [10.2] * 20

        monitor = _make_restart_monitor(
            collector=collector,
            health_monitor=hm,
            channel_stabilization_timeout=0,
        )
        monitor.monitor_recovery()

        hm.ping.assert_called()
        # Collector.execute() NOT called during response detection
        # (only clear_session is called)
        collector.execute.assert_not_called()

    @patch("solentlabs.cable_modem_monitor_core.orchestration.restart.time.sleep")
    @patch("solentlabs.cable_modem_monitor_core.orchestration.restart.time.monotonic")
    def test_falls_back_to_collector_without_health_monitor(
        self, mock_monotonic: MagicMock, mock_sleep: MagicMock
    ) -> None:
        """No HealthMonitor → collector used for response detection."""
        collector = _mock_collector()

        mock_monotonic.side_effect = [0.0, 0.0, 0.1, 0.2, 10.0, 10.1] + [10.2] * 20

        monitor = _make_restart_monitor(
            collector=collector,
            health_monitor=None,
            channel_stabilization_timeout=0,
        )
        monitor.monitor_recovery()

        collector.execute.assert_called()

    @patch("solentlabs.cable_modem_monitor_core.orchestration.restart.time.sleep")
    @patch("solentlabs.cable_modem_monitor_core.orchestration.restart.time.monotonic")
    def test_health_monitor_exception_treated_as_failure(
        self, mock_monotonic: MagicMock, mock_sleep: MagicMock
    ) -> None:
        """Exception from health_monitor.ping() → probe fails, loop continues."""
        hm = _mock_health_monitor()
        # First call raises, second succeeds
        hm.ping.side_effect = [
            Exception("network error"),
            HealthInfo(health_status=HealthStatus.RESPONSIVE),
        ]

        mock_monotonic.side_effect = (
            [0.0, 0.0, 0.1, 0.2]  # start + first probe
            + [10.0, 10.1, 10.2]  # after sleep, second probe
            + [20.0, 20.1]  # elapsed
            + [20.2] * 20
        )

        monitor = _make_restart_monitor(
            health_monitor=hm,
            channel_stabilization_timeout=0,
        )
        result = monitor.monitor_recovery()

        assert result.success is True
        assert hm.ping.call_count == 2


# ------------------------------------------------------------------
# Channel stability details
# ------------------------------------------------------------------


class TestChannelStability:
    """Channel stabilization logic details."""

    @patch("solentlabs.cable_modem_monitor_core.orchestration.restart.time.sleep")
    @patch("solentlabs.cable_modem_monitor_core.orchestration.restart.time.monotonic")
    def test_stability_requires_consecutive_same_counts(self, mock_monotonic: MagicMock, mock_sleep: MagicMock) -> None:
        """Changing counts reset the stability counter."""
        hm = _mock_health_monitor()

        # Channel stabilization: counts change, then stabilize
        results = [
            _ok_result(16, 2),  # probe 1: initial
            _ok_result(20, 3),  # probe 2: changed → reset
            _ok_result(24, 4),  # probe 3: changed → reset
            _ok_result(24, 4),  # probe 4: stable 2/3
            _ok_result(24, 4),  # probe 5: stable 3/3 → grace
        ]
        # Grace period polls
        results += [_ok_result(24, 4)] * 5
        collector = _mock_collector(results)

        # Time: response quick, stabilization with enough time for grace
        times = [0.0, 0.0, 0.1, 0.2, 10.0]  # response detection
        t = 10.0
        for _i in range(len(results)):
            t += 10.0
            times.extend([t, t + 0.01, t + 0.02])
        # Grace period complete check: need time past grace_start + 30s
        t += GRACE_PERIOD_SECONDS + 1
        times.extend([t, t + 0.01, t + 0.02])
        times.append(t + 1)  # elapsed
        times += [t + 2] * 20

        mock_monotonic.side_effect = times

        monitor = _make_restart_monitor(
            collector=collector,
            health_monitor=hm,
            channel_stabilization_timeout=600,
            probe_interval=10,
        )
        result = monitor.monitor_recovery()

        assert result.success is True
        assert result.phase_reached == RestartPhase.COMPLETE

    @patch("solentlabs.cable_modem_monitor_core.orchestration.restart.time.sleep")
    @patch("solentlabs.cable_modem_monitor_core.orchestration.restart.time.monotonic")
    def test_collection_failure_resets_stability(self, mock_monotonic: MagicMock, mock_sleep: MagicMock) -> None:
        """Failed collection during channel stabilization resets counter."""
        hm = _mock_health_monitor()

        results = [
            _ok_result(24, 4),  # probe 1: initial
            _ok_result(24, 4),  # probe 2: stable 2/3
            _fail_result(),  # probe 3: fail → reset
            _ok_result(24, 4),  # probe 4: restart count
            _ok_result(24, 4),  # probe 5: stable 2/3
            _ok_result(24, 4),  # probe 6: stable 3/3 → grace
        ]
        results += [_ok_result(24, 4)] * 5
        collector = _mock_collector(results)

        times = [0.0, 0.0, 0.1, 0.2, 10.0]
        t = 10.0
        for _i in range(len(results)):
            t += 10.0
            times.extend([t, t + 0.01, t + 0.02])
        t += GRACE_PERIOD_SECONDS + 1
        times.extend([t, t + 0.01, t + 0.02])
        times.append(t + 1)
        times += [t + 2] * 20

        mock_monotonic.side_effect = times

        monitor = _make_restart_monitor(
            collector=collector,
            health_monitor=hm,
            channel_stabilization_timeout=600,
            probe_interval=10,
        )
        result = monitor.monitor_recovery()

        assert result.success is True


# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------


class TestRestartLogging:
    """Verify logging contract."""

    @patch("solentlabs.cable_modem_monitor_core.orchestration.restart.time.sleep")
    @patch("solentlabs.cable_modem_monitor_core.orchestration.restart.time.monotonic")
    def test_recovery_start_logged(
        self,
        mock_monotonic: MagicMock,
        mock_sleep: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Recovery start is logged at INFO."""
        hm = _mock_health_monitor()
        mock_monotonic.side_effect = [0.0, 0.0, 0.1, 0.2, 10.0, 10.1] + [10.2] * 20

        monitor = _make_restart_monitor(
            health_monitor=hm,
            channel_stabilization_timeout=0,
        )

        with caplog.at_level("INFO"):
            monitor.monitor_recovery()

        assert "waiting for modem to respond" in caplog.text

    @patch("solentlabs.cable_modem_monitor_core.orchestration.restart.time.sleep")
    @patch("solentlabs.cable_modem_monitor_core.orchestration.restart.time.monotonic")
    def test_response_timeout_logs_warning(
        self,
        mock_monotonic: MagicMock,
        mock_sleep: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Response timeout is logged at WARNING."""
        hm = _mock_health_monitor(HealthInfo(health_status=HealthStatus.UNRESPONSIVE))

        times = [0.0, 0.0]
        t = 0.0
        for _ in range(15):
            t += 10.0
            times.extend([t, t + 0.1])
        times.append(121.0)
        times += [121.0] * 20
        mock_monotonic.side_effect = times

        monitor = _make_restart_monitor(
            health_monitor=hm,
            response_timeout=120,
        )

        with caplog.at_level("WARNING"):
            monitor.monitor_recovery()

        assert "response timeout" in caplog.text
