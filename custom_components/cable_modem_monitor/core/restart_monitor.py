"""Modem restart monitoring with status tracking.

Monitors modem restart process in two phases:
1. Wait for modem to respond to HTTP requests (max 2 min)
2. Wait for channels to synchronize with grace period (max 5 min)

Sends persistent notifications at each stage to keep user informed.

Usage:
    monitor = RestartMonitor(hass, coordinator, notify_callback)
    await monitor.start()
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class RestartMonitor:
    """Monitors modem restart and provides status updates.

    Lifecycle:
        1. Modem restart command sent (external)
        2. start() called - begins monitoring
        3. Phase 1: Poll until modem responds (or timeout)
        4. Phase 2: Wait for channel sync with grace period
        5. Send final notification
        6. Restore original polling interval
    """

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: DataUpdateCoordinator,
        notify: Callable[[str, str], Awaitable[None]],
    ) -> None:
        """Initialize the restart monitor.

        Args:
            hass: Home Assistant instance
            coordinator: Data update coordinator for polling
            notify: Async callback for notifications (title, message)
        """
        self._hass = hass
        self._coordinator = coordinator
        self._notify = notify
        self._original_interval: timedelta | None = None

    async def start(self) -> None:
        """Start monitoring the restart process."""
        _LOGGER.info("Starting modem restart monitoring")

        # Save original update interval
        self._original_interval = self._coordinator.update_interval

        try:
            # Set fast polling (10 seconds)
            self._coordinator.update_interval = timedelta(seconds=10)
            _LOGGER.debug("Set polling interval to 10s (original: %s)", self._original_interval)

            # Wait 5 seconds for modem to go offline
            await asyncio.sleep(5)

            # Clear auth cache before polling resumes
            # Modem invalidates all sessions on reboot, so cached credentials become stale
            if hasattr(self._coordinator, "scraper"):
                self._coordinator.scraper.clear_auth_cache()
                _LOGGER.debug("Cleared auth cache after modem restart")

            # Phase 1: Wait for modem to respond (max 2 minutes)
            phase1_max_wait = 120
            modem_responding, elapsed_time = await self._wait_for_modem_response(phase1_max_wait)

            if not modem_responding:
                _LOGGER.error("Phase 1 failed: Modem did not respond after %ss", phase1_max_wait)
                await self._send_final_notification(False, False, elapsed_time)
                return

            # Send intermediate notification
            await self._notify(
                "Modem Restarting",
                f"Modem responding after {elapsed_time}s. Waiting for channels to sync...",
            )

            # Phase 2: Wait for channels to sync (max 5 minutes)
            phase2_max_wait = 300
            modem_fully_online, phase2_elapsed = await self._wait_for_channel_sync(phase2_max_wait)

            # Send final notification
            total_time = elapsed_time + phase2_elapsed
            await self._send_final_notification(modem_responding, modem_fully_online, total_time)

        except Exception as e:
            _LOGGER.error("Critical error in restart monitoring: %s", e)
        finally:
            # ALWAYS restore original polling interval, even if there's an error
            if self._original_interval:
                self._coordinator.update_interval = self._original_interval
                _LOGGER.info("Restored polling interval to %s", self._original_interval)
            # Force one final refresh with restored interval
            await self._coordinator.async_request_refresh()

    async def _wait_for_modem_response(self, max_wait: int) -> tuple[bool, int]:
        """Phase 1: Wait for modem to respond to HTTP requests.

        Args:
            max_wait: Maximum seconds to wait

        Returns:
            Tuple of (modem_responding, elapsed_time)
        """
        _LOGGER.info("Phase 1: Waiting for modem to respond to HTTP requests...")
        elapsed_time = 0

        while elapsed_time < max_wait:
            try:
                await self._coordinator.async_request_refresh()
                await asyncio.sleep(10)
                elapsed_time += 10

                if self._coordinator.last_update_success and self._coordinator.data:
                    status = self._coordinator.data.get("cable_modem_connection_status")
                    _LOGGER.info("Modem responding after %ss (status: %s)", elapsed_time, status)
                    return True, elapsed_time

                _LOGGER.debug("Modem not responding yet after %ss", elapsed_time)
            except Exception as e:
                _LOGGER.debug("Error during phase 1 monitoring: %s", e)
                await asyncio.sleep(10)
                elapsed_time += 10

        return False, elapsed_time

    async def _wait_for_channel_sync(self, max_wait: int) -> tuple[bool, int]:
        """Phase 2: Wait for channels to synchronize.

        Args:
            max_wait: Maximum seconds to wait

        Returns:
            Tuple of (modem_fully_online, phase2_elapsed)
        """
        _LOGGER.info("Phase 2: Modem responding, waiting for channel sync...")
        phase2_elapsed = 0
        prev_downstream = 0
        prev_upstream = 0
        stable_count = 0
        grace_period_active = False
        grace_period_start = 0

        while phase2_elapsed < max_wait:
            try:
                await self._coordinator.async_request_refresh()
                await asyncio.sleep(10)
                phase2_elapsed += 10

                downstream_count = self._coordinator.data.get("cable_modem_downstream_channel_count", 0)
                upstream_count = self._coordinator.data.get("cable_modem_upstream_channel_count", 0)
                connection_status = self._coordinator.data.get("cable_modem_connection_status")

                # Check if channels are stable
                if downstream_count == prev_downstream and upstream_count == prev_upstream:
                    stable_count += 1
                else:
                    stable_count = 0
                    grace_period_active = False
                    _LOGGER.info(
                        "Phase 2: %ss - Channels still synchronizing: %s→%s down, %s→%s up",
                        phase2_elapsed,
                        prev_downstream,
                        downstream_count,
                        prev_upstream,
                        upstream_count,
                    )

                prev_downstream = downstream_count
                prev_upstream = upstream_count

                # Enter grace period after initial stability
                if (
                    connection_status == "online"
                    and downstream_count > 0
                    and upstream_count > 0
                    and stable_count >= 3
                    and not grace_period_active
                ):
                    grace_period_active = True
                    grace_period_start = phase2_elapsed
                    _LOGGER.info(
                        "Phase 2: Channels stable (%s down, %s up), entering 30s grace period",
                        downstream_count,
                        upstream_count,
                    )

                # Check if grace period is complete
                if grace_period_active and (phase2_elapsed - grace_period_start) >= 30:
                    _LOGGER.info(
                        "Modem fully online with stable channels (%s down, %s up)", downstream_count, upstream_count
                    )
                    return True, phase2_elapsed

            except Exception as e:
                _LOGGER.debug("Error during phase 2 monitoring: %s", e)
                await asyncio.sleep(10)
                phase2_elapsed += 10

        return False, phase2_elapsed

    async def _send_final_notification(self, modem_responding: bool, modem_fully_online: bool, total_time: int) -> None:
        """Send final notification about restart status.

        Args:
            modem_responding: Whether modem is responding to HTTP requests
            modem_fully_online: Whether channels are fully synchronized
            total_time: Total elapsed time in seconds
        """
        if not modem_responding:
            await self._notify(
                "Modem Restart Timeout",
                f"Modem did not respond after {total_time} seconds. Check your modem.",
            )
        elif modem_fully_online:
            downstream_count = self._coordinator.data.get("cable_modem_downstream_channel_count", 0)
            upstream_count = self._coordinator.data.get("cable_modem_upstream_channel_count", 0)
            await self._notify(
                "Modem Restart Complete",
                f"Modem fully online after {total_time}s with {downstream_count} downstream "
                f"and {upstream_count} upstream channels.",
            )
        else:
            await self._notify(
                "Modem Restart Warning",
                f"Modem responding but channels not fully synced after {total_time}s. "
                "This may be normal - check modem status.",
            )
