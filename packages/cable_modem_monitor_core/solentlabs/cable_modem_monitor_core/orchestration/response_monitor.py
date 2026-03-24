"""Response monitor — modem response detection after restart.

Probes the modem until it responds or a timeout expires. Uses
HealthMonitor for lightweight ICMP/HTTP probes when available,
otherwise falls back to a full ModemDataCollector cycle.

See ORCHESTRATION_SPEC.md § RestartMonitor and ORCHESTRATION_USE_CASES.md
UC-40 through UC-42.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from .models import HealthInfo
from .signals import HealthStatus

if TYPE_CHECKING:
    import threading

    from .collector import ModemDataCollector
    from .modem_health import HealthMonitor

_logger = logging.getLogger(__name__)


class ResponseMonitor:
    """Probes modem until it responds after a restart.

    Uses HealthMonitor if available (lightweight ICMP/HTTP). Falls
    back to ModemDataCollector (full auth+parse cycle) otherwise.

    Transient — created for one restart, discarded after.

    Args:
        collector: ModemDataCollector for fallback response detection.
        health_monitor: Optional HealthMonitor for lightweight probes.
        response_timeout: Max seconds to wait for modem to respond.
        probe_interval: Seconds between probes.
    """

    def __init__(
        self,
        collector: ModemDataCollector,
        health_monitor: HealthMonitor | None,
        response_timeout: int = 120,
        probe_interval: int = 10,
    ) -> None:
        self._collector = collector
        self._health_monitor = health_monitor
        self._response_timeout = response_timeout
        self._probe_interval = probe_interval

    @property
    def response_timeout(self) -> int:
        """Max seconds to wait for modem to respond."""
        return self._response_timeout

    def wait_for_response(
        self,
        start: float,
        cancel_event: threading.Event | None,
    ) -> bool:
        """Probe until modem responds or timeout expires.

        Args:
            start: Monotonic timestamp when recovery started.
            cancel_event: Optional cancellation event.

        Returns:
            True if modem responded, False on timeout or cancel.
        """
        deadline = start + self._response_timeout

        while time.monotonic() < deadline:
            if _is_cancelled(cancel_event):
                return False

            if self._probe_for_response():
                return True

            if _wait_or_cancel(cancel_event, self._probe_interval):
                return False

        return False

    def _probe_for_response(self) -> bool:
        """Run a single response detection probe.

        Uses HealthMonitor if available (lightweight). Falls back to
        collector.execute() which runs a full auth+parse cycle.
        """
        if self._health_monitor is not None:
            return self._probe_via_health_monitor()
        return self._probe_via_collector()

    def _probe_via_health_monitor(self) -> bool:
        """Probe using HealthMonitor (ICMP/HTTP)."""
        try:
            info: HealthInfo = self._health_monitor.ping()  # type: ignore[union-attr]
            responsive = info.health_status not in (
                HealthStatus.UNRESPONSIVE,
                HealthStatus.UNKNOWN,
            )
            _logger.debug(
                "Restart probe (health): %s",
                info.health_status.value,
            )
            return responsive
        except Exception:
            _logger.debug("Restart probe (health): exception", exc_info=True)
            return False

    def _probe_via_collector(self) -> bool:
        """Probe using collector (full auth+parse cycle)."""
        try:
            result = self._collector.execute()
            _logger.debug(
                "Restart probe (collector): success=%s signal=%s",
                result.success,
                result.signal.value,
            )
            return result.success
        except Exception:
            _logger.debug("Restart probe (collector): exception", exc_info=True)
            return False


def _is_cancelled(cancel_event: threading.Event | None) -> bool:
    """Check if cancel has been requested."""
    return cancel_event is not None and cancel_event.is_set()


def _wait_or_cancel(
    cancel_event: threading.Event | None,
    interval: int,
) -> bool:
    """Wait for next probe interval, return True if cancelled."""
    if cancel_event is not None:
        cancel_event.wait(interval)
        return cancel_event.is_set()
    time.sleep(interval)
    return False
