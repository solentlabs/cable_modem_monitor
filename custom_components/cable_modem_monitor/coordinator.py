"""Data coordinator utilities for Cable Modem Monitor.

Provides functions for:
- Creating the health monitor with SSL context
- Creating the async update function for DataUpdateCoordinator
- Performing initial data refresh
"""

from __future__ import annotations

import logging
import ssl
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from .channel_utils import normalize_channels
from .const import VERIFY_SSL
from .core.health_monitor import ModemHealthMonitor

_LOGGER = logging.getLogger(__name__)


async def create_health_monitor(hass: HomeAssistant, legacy_ssl: bool = False) -> ModemHealthMonitor:
    """Create health monitor with SSL context.

    Args:
        hass: Home Assistant instance
        legacy_ssl: Use legacy SSL ciphers (SECLEVEL=0) for older modem firmware
    """

    def create_ssl_context(use_legacy: bool):
        """Create SSL context (runs in executor to avoid blocking)."""
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        # Enable legacy ciphers for older modem firmware
        if use_legacy:
            context.set_ciphers("DEFAULT:@SECLEVEL=0")
            _LOGGER.info("Legacy SSL cipher support enabled (SECLEVEL=0) for health monitor")

        return context

    ssl_context = await hass.async_add_executor_job(create_ssl_context, legacy_ssl)
    return ModemHealthMonitor(
        max_history=100,
        verify_ssl=VERIFY_SSL,
        ssl_context=ssl_context,
        legacy_ssl=legacy_ssl,
    )


def create_update_function(hass: HomeAssistant, modem_client, health_monitor, host: str, supports_icmp: bool = True):
    """Create the async update function for the coordinator."""

    async def async_update_data() -> dict[str, Any]:
        """Fetch data from the modem."""
        # Host may already include protocol (http:// or https://)
        base_url = host if host.startswith(("http://", "https://")) else f"http://{host}"

        # Use config-based ICMP setting (auto-detected during setup/options flow)
        # This allows different IPs of the same modem to have different ICMP behavior
        health_result = await health_monitor.check_health(base_url, skip_ping=not supports_icmp)

        try:
            data: dict[str, Any] = await hass.async_add_executor_job(modem_client.get_modem_data)

            # Add health monitoring data
            data["health_status"] = health_result.status
            data["health_diagnosis"] = health_result.diagnosis
            data["ping_success"] = health_result.ping_success
            data["ping_latency_ms"] = health_result.ping_latency_ms
            data["http_success"] = health_result.http_success
            data["http_latency_ms"] = health_result.http_latency_ms
            data["consecutive_failures"] = health_monitor.consecutive_failures
            data["supports_icmp"] = supports_icmp

            # Create indexed lookups for O(1) channel access (performance optimization)
            # This prevents O(n) linear searches in each sensor's native_value property
            # Keys are (channel_type, channel_id) tuples for DOCSIS 3.1 disambiguation
            if "cable_modem_downstream" in data:
                data["_downstream_by_id"] = normalize_channels(data["cable_modem_downstream"], "downstream")
            if "cable_modem_upstream" in data:
                data["_upstream_by_id"] = normalize_channels(data["cable_modem_upstream"], "upstream")

            # Add parser metadata for sensor attributes (works without re-adding integration)
            detection_info = modem_client.get_detection_info()
            if detection_info:
                data["_parser_release_date"] = detection_info.get("release_date")
                data["_parser_docsis_version"] = detection_info.get("docsis_version")
                data["_parser_fixtures_url"] = detection_info.get("fixtures_url")
                data["_parser_verified"] = detection_info.get("verified", False)
                data["_parser_capabilities"] = detection_info.get("capabilities", [])

            return data
        except Exception as err:
            # If modem_client fails but health check succeeded, return partial data
            if health_result.is_healthy:
                _LOGGER.warning("Data fetch failed but modem is responding to health checks: %s", err)
                # Use "degraded" status to indicate partial connectivity
                # This allows ping/http sensors to report while other sensors show unavailable
                return {
                    "cable_modem_connection_status": "degraded",
                    "health_status": health_result.status,
                    "health_diagnosis": health_result.diagnosis,
                    "ping_success": health_result.ping_success,
                    "ping_latency_ms": health_result.ping_latency_ms,
                    "http_success": health_result.http_success,
                    "http_latency_ms": health_result.http_latency_ms,
                    "consecutive_failures": health_monitor.consecutive_failures,
                    "supports_icmp": supports_icmp,
                }
            raise UpdateFailed(f"Error communicating with modem: {err}") from err

    return async_update_data


async def perform_initial_refresh(coordinator, entry: ConfigEntry) -> None:
    """Perform initial data refresh based on entry state."""
    if entry.state == ConfigEntryState.SETUP_IN_PROGRESS:
        await coordinator.async_config_entry_first_refresh()
    else:
        # During reload, just do a regular refresh
        await coordinator.async_refresh()
