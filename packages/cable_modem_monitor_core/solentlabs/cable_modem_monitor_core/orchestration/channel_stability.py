"""Channel stability monitor — post-restart channel count stabilization.

Polls the modem via ModemDataCollector until downstream and upstream
channel counts are stable for a configurable number of consecutive
reads, then enters a grace period before declaring stability.

See ORCHESTRATION_SPEC.md § RestartMonitor and ORCHESTRATION_USE_CASES.md
UC-43 through UC-48.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from .response_monitor import _is_cancelled, _wait_or_cancel

if TYPE_CHECKING:
    import threading

    from .collector import ModemDataCollector

_logger = logging.getLogger(__name__)

# Number of consecutive stable channel counts required before
# entering the grace period.
STABILITY_COUNT = 3

# Duration of the grace period after initial stability detection.
# If channel counts change during this window, the counter resets.
GRACE_PERIOD_SECONDS = 30


class ChannelStabilityMonitor:
    """Polls until channel counts stabilize after a restart.

    Stability = N consecutive identical (DS, US) counts + grace
    period where counts remain unchanged.

    Transient — created for one restart, discarded after.

    Args:
        collector: ModemDataCollector for channel data.
        channel_stabilization_timeout: Max seconds to wait for stable
            channel counts. 0 to skip entirely.
        probe_interval: Seconds between probes.
    """

    def __init__(
        self,
        collector: ModemDataCollector,
        channel_stabilization_timeout: int = 300,
        probe_interval: int = 10,
    ) -> None:
        self._collector = collector
        self._channel_stabilization_timeout = channel_stabilization_timeout
        self._probe_interval = probe_interval

    @property
    def channel_stabilization_timeout(self) -> int:
        """Max seconds to wait for stable channel counts."""
        return self._channel_stabilization_timeout

    def wait_for_stability(
        self,
        cancel_event: threading.Event | None,
    ) -> bool:
        """Poll until channel counts stabilize or timeout expires.

        Stability = STABILITY_COUNT consecutive identical (DS, US)
        counts + GRACE_PERIOD_SECONDS grace period where counts
        remain unchanged.

        Args:
            cancel_event: Optional cancellation event.

        Returns:
            True if channels stabilized, False on timeout or cancel.
        """
        stabilization_start = time.monotonic()
        deadline = stabilization_start + self._channel_stabilization_timeout

        consecutive_stable = 0
        last_counts: tuple[int, int] | None = None
        grace_start: float | None = None
        probe_num = 0

        while time.monotonic() < deadline:
            if _is_cancelled(cancel_event):
                return False

            counts = self._poll_channel_counts()
            probe_num += 1

            if counts is None:
                consecutive_stable = 0
                grace_start = None
                _logger.debug("Restart recovery: probe %d — collection failed", probe_num)
            else:
                consecutive_stable, grace_start = _update_stability(
                    counts, last_counts, consecutive_stable, grace_start, probe_num
                )
                last_counts = counts
                if grace_start is not None and (time.monotonic() - grace_start) >= GRACE_PERIOD_SECONDS:
                    return True

            if _wait_or_cancel(cancel_event, self._probe_interval):
                return False

        return False

    def _poll_channel_counts(self) -> tuple[int, int] | None:
        """Execute a collection and extract channel counts.

        Returns (downstream_count, upstream_count) or None on failure.
        """
        try:
            result = self._collector.execute()
            if not result.success or result.modem_data is None:
                return None

            ds = len(result.modem_data.get("downstream", []))
            us = len(result.modem_data.get("upstream", []))
            return (ds, us)
        except Exception:
            _logger.debug(
                "Restart recovery: channel poll exception",
                exc_info=True,
            )
            return None


def _update_stability(
    counts: tuple[int, int],
    last_counts: tuple[int, int] | None,
    consecutive_stable: int,
    grace_start: float | None,
    probe_num: int,
) -> tuple[int, float | None]:
    """Update stability tracking after a successful channel poll.

    Returns updated (consecutive_stable, grace_start).
    """
    if last_counts is not None and counts == last_counts:
        consecutive_stable += 1
    else:
        consecutive_stable = 1
        grace_start = None

    _logger.debug(
        "Restart recovery: probe %d — %d DS, %d US (stable: %d/%d)",
        probe_num,
        counts[0],
        counts[1],
        consecutive_stable,
        STABILITY_COUNT,
    )

    if consecutive_stable >= STABILITY_COUNT and grace_start is None:
        grace_start = time.monotonic()
        _logger.info(
            "Restart recovery: channels stable (%d DS, %d US), entering grace period",
            counts[0],
            counts[1],
        )

    return consecutive_stable, grace_start
