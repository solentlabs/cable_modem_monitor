"""RestartMonitor — modem restart recovery.

Orchestrates modem recovery after a restart command: first waits for
the modem to respond (via ResponseMonitor), then waits for DOCSIS
channel counts to stabilize (via ChannelStabilityMonitor). Transient —
created per restart, discarded after.

See ORCHESTRATION_SPEC.md § RestartMonitor and ORCHESTRATION_USE_CASES.md
UC-40 through UC-48.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from .channel_stability import ChannelStabilityMonitor
from .models import RestartResult
from .response_monitor import ResponseMonitor
from .signals import RestartPhase

if TYPE_CHECKING:
    import threading

    from .collector import ModemDataCollector
    from .modem_health import HealthMonitor

_logger = logging.getLogger(__name__)


class RestartMonitor:
    """Modem restart recovery monitor.

    Composes ResponseMonitor (phase 1: wait for modem to respond) and
    ChannelStabilityMonitor (phase 2: wait for stable channel counts).

    Transient — created for one restart, discarded after.

    Args:
        collector: ModemDataCollector for channel data and fallback
            response detection.
        health_monitor: Optional HealthMonitor for lightweight response
            detection. None falls back to collector.
        response_timeout: Max seconds to wait for modem to respond.
        channel_stabilization_timeout: Max seconds to wait for stable
            channel counts after response. 0 to skip.
        probe_interval: Seconds between probes during recovery.
    """

    def __init__(
        self,
        collector: ModemDataCollector,
        health_monitor: HealthMonitor | None,
        response_timeout: int = 120,
        channel_stabilization_timeout: int = 300,
        probe_interval: int = 10,
        model: str = "",
    ) -> None:
        self._response_monitor = ResponseMonitor(
            collector=collector,
            health_monitor=health_monitor,
            response_timeout=response_timeout,
            probe_interval=probe_interval,
        )
        self._channel_monitor = ChannelStabilityMonitor(
            collector=collector,
            channel_stabilization_timeout=channel_stabilization_timeout,
            probe_interval=probe_interval,
            model=model,
        )
        self._collector = collector
        self._health_monitor = health_monitor
        self._model = model

    def monitor_recovery(
        self,
        cancel_event: threading.Event | None = None,
    ) -> RestartResult:
        """Run restart recovery sequence.

        1. Clear collector session and health evidence
        2. Wait for modem to respond (phase 1)
        3. Wait for channel stabilization (phase 2, if enabled)

        Args:
            cancel_event: Optional threading.Event for cooperative
                cancellation. Setting it causes exit within one
                probe_interval.

        Returns:
            RestartResult with recovery outcome.
        """
        start = time.monotonic()

        # Clear stale state
        self._collector.clear_session()

        _logger.info("Restart recovery [%s]: waiting for modem to respond", self._model)

        # Phase 1: Response detection
        result = self._wait_for_response(start, cancel_event)
        if result is not None:
            return result

        response_time = time.monotonic() - start
        _logger.info(
            "Restart recovery [%s]: modem responding (%.0fs), " "waiting for channel stabilization",
            self._model,
            response_time,
        )

        # Phase 2: Channel stabilization
        return self._wait_for_channel_stability(start, cancel_event)

    def _wait_for_response(
        self,
        start: float,
        cancel_event: threading.Event | None,
    ) -> RestartResult | None:
        """Run phase 1. Returns a RestartResult on failure, None on success."""
        modem_responded = self._response_monitor.wait_for_response(start, cancel_event)
        if modem_responded:
            return None

        elapsed = time.monotonic() - start
        if cancel_event is not None and cancel_event.is_set():
            _logger.info("Restart recovery [%s]: cancelled during response wait", self._model)
            return RestartResult(
                success=False,
                phase_reached=RestartPhase.WAITING_RESPONSE,
                elapsed_seconds=elapsed,
                error="Cancelled",
            )

        timeout = self._response_monitor.response_timeout
        _logger.warning(
            "Restart recovery [%s]: response timeout after %ds",
            self._model,
            timeout,
        )
        return RestartResult(
            success=False,
            phase_reached=RestartPhase.WAITING_RESPONSE,
            elapsed_seconds=elapsed,
            error=f"Response timeout after {timeout}s",
        )

    def _wait_for_channel_stability(
        self,
        start: float,
        cancel_event: threading.Event | None,
    ) -> RestartResult:
        """Run phase 2. Always returns a RestartResult."""
        timeout = self._channel_monitor.channel_stabilization_timeout

        # Skip if timeout is 0
        if timeout == 0:
            elapsed = time.monotonic() - start
            _logger.info(
                "Restart recovery [%s]: channel stabilization skipped (timeout=0), " "recovered in %.0fs",
                self._model,
                elapsed,
            )
            return RestartResult(
                success=True,
                phase_reached=RestartPhase.COMPLETE,
                elapsed_seconds=elapsed,
            )

        channels_stable = self._channel_monitor.wait_for_stability(cancel_event)
        elapsed = time.monotonic() - start

        if not channels_stable:
            if cancel_event is not None and cancel_event.is_set():
                _logger.info("Restart recovery [%s]: cancelled during channel sync", self._model)
                return RestartResult(
                    success=False,
                    phase_reached=RestartPhase.CHANNEL_SYNC,
                    elapsed_seconds=elapsed,
                    error="Cancelled",
                )
            _logger.warning(
                "Restart recovery [%s]: channel stabilization timeout after %ds " "(counts still changing)",
                self._model,
                timeout,
            )
            return RestartResult(
                success=False,
                phase_reached=RestartPhase.CHANNEL_SYNC,
                elapsed_seconds=elapsed,
                error=f"Channel stabilization timeout after {timeout}s",
            )

        _logger.info(
            "Restart recovery [%s]: grace period complete, recovered in %.0fs",
            self._model,
            elapsed,
        )
        return RestartResult(
            success=True,
            phase_reached=RestartPhase.COMPLETE,
            elapsed_seconds=elapsed,
        )
