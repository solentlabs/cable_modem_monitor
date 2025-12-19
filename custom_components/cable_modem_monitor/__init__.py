"""The Cable Modem Monitor integration."""

from __future__ import annotations

import logging
import sqlite3
import ssl
from datetime import datetime, timedelta
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_DOCSIS_VERSION,
    CONF_HOST,
    CONF_MODEM_CHOICE,
    CONF_PARSER_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_SUPPORTS_ICMP,
    CONF_USERNAME,
    CONF_WORKING_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    VERIFY_SSL,
    VERSION,
)
from .core.health_monitor import ModemHealthMonitor
from .core.modem_scraper import ModemScraper
from .parsers import get_parser_by_name, get_parsers
from .utils.entity_migration import migrate_docsis30_entities

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]


def _normalize_channel_type(channel: dict[str, Any], direction: str) -> str:
    """Normalize channel type from parser data.

    Maps raw parser values to standardized types:
    - Downstream: 'qam' (DOCSIS 3.0) or 'ofdm' (DOCSIS 3.1)
    - Upstream: 'atdma' (DOCSIS 3.0) or 'ofdma' (DOCSIS 3.1)

    Falls back to 'qam'/'atdma' if modulation not specified.
    """
    modulation = channel.get("modulation", "").lower()

    if direction == "downstream":
        if "ofdm" in modulation:
            return "ofdm"
        return "qam"  # Default for DOCSIS 3.0 or unspecified
    else:  # upstream
        if "ofdma" in modulation:
            return "ofdma"
        return "atdma"  # Default for DOCSIS 3.0 or unspecified


def _normalize_channels(channels: list[dict[str, Any]], direction: str) -> dict[tuple[str, int], dict[str, Any]]:
    """Normalize and index channels by (type, id) tuple.

    Groups channels by type, sorts by frequency within each type,
    and assigns stable indices based on frequency order.

    Returns dict mapping (channel_type, channel_id) -> channel data with added metadata.
    """
    from collections import defaultdict

    # Group channels by type
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for idx, ch in enumerate(channels):
        ch_type = _normalize_channel_type(ch, direction)
        ch_id = int(ch.get("channel_id", ch.get("channel", idx + 1)))
        by_type[ch_type].append({**ch, "_channel_type": ch_type, "_channel_id": ch_id})

    # Sort each type by frequency and assign index
    result: dict[tuple[str, int], dict[str, Any]] = {}
    for _channel_type, group in by_type.items():
        # Sort by frequency (use 0 if not present)
        sorted_group = sorted(group, key=lambda x: float(x.get("frequency", 0) or 0))
        for index, ch in enumerate(sorted_group):
            ch["_index"] = index + 1  # 1-based index
            key = (ch["_channel_type"], ch["_channel_id"])
            result[key] = ch

    return result


SERVICE_CLEAR_HISTORY = "clear_history"
SERVICE_CLEAR_HISTORY_SCHEMA = vol.Schema(
    {
        vol.Required("days_to_keep"): cv.positive_int,
    }
)

SERVICE_GENERATE_DASHBOARD = "generate_dashboard"
SERVICE_GENERATE_DASHBOARD_SCHEMA = vol.Schema(
    {
        vol.Optional("include_downstream_power", default=True): cv.boolean,
        vol.Optional("include_downstream_snr", default=True): cv.boolean,
        vol.Optional("include_upstream_power", default=True): cv.boolean,
        vol.Optional("include_upstream_frequency", default=False): cv.boolean,
        vol.Optional("include_errors", default=True): cv.boolean,
        vol.Optional("include_latency", default=True): cv.boolean,
        vol.Optional("include_status_card", default=True): cv.boolean,
        vol.Optional("graph_hours", default=24): cv.positive_int,
        vol.Optional("short_titles", default=False): cv.boolean,
        vol.Optional("channel_label", default="auto"): vol.In(["auto", "full", "id_only", "type_id"]),
        vol.Optional("channel_grouping", default="by_direction"): vol.In(["by_direction", "by_type"]),
    }
)


def _select_parser(parsers: list, modem_choice: str):
    """Select appropriate parser based on user choice.

    Returns either a single parser instance or list of all parsers.
    """
    if not modem_choice or modem_choice == "auto":
        # Auto mode - return all parsers
        return parsers

    # Strip " *" suffix used to mark unverified parsers in the UI
    modem_choice_clean = modem_choice.rstrip(" *")

    # User selected specific parser - find and instantiate it
    for parser_class in parsers:
        if parser_class.name == modem_choice_clean:
            _LOGGER.info("Using user-selected parser: %s", parser_class.name)
            return parser_class()

    _LOGGER.warning("Parser '%s' not found, falling back to auto", modem_choice)
    return parsers


async def _create_health_monitor(hass: HomeAssistant):
    """Create health monitor with SSL context."""

    def create_ssl_context():
        """Create SSL context (runs in executor to avoid blocking)."""
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    ssl_context = await hass.async_add_executor_job(create_ssl_context)
    return ModemHealthMonitor(max_history=100, verify_ssl=VERIFY_SSL, ssl_context=ssl_context)


def _create_update_function(hass: HomeAssistant, scraper, health_monitor, host: str, supports_icmp: bool = True):
    """Create the async update function for the coordinator."""

    async def async_update_data() -> dict[str, Any]:
        """Fetch data from the modem."""
        base_url = f"http://{host}"

        # Use config-based ICMP setting (auto-detected during setup/options flow)
        # This allows different IPs of the same modem to have different ICMP behavior
        health_result = await health_monitor.check_health(base_url, skip_ping=not supports_icmp)

        try:
            data: dict[str, Any] = await hass.async_add_executor_job(scraper.get_modem_data)

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
                data["_downstream_by_id"] = _normalize_channels(data["cable_modem_downstream"], "downstream")
            if "cable_modem_upstream" in data:
                data["_upstream_by_id"] = _normalize_channels(data["cable_modem_upstream"], "upstream")

            # Add parser metadata for sensor attributes (works without re-adding integration)
            detection_info = scraper.get_detection_info()
            if detection_info:
                data["_parser_release_date"] = detection_info.get("release_date")
                data["_parser_docsis_version"] = detection_info.get("docsis_version")
                data["_parser_fixtures_url"] = detection_info.get("fixtures_url")
                data["_parser_verified"] = detection_info.get("verified", False)

            return data
        except Exception as err:
            # If scraper fails but health check succeeded, return partial data
            if health_result.is_healthy:
                _LOGGER.warning("Scraper failed but modem is responding to health checks: %s", err)
                return {
                    "cable_modem_connection_status": "offline",
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


async def _perform_initial_refresh(coordinator, entry: ConfigEntry) -> None:
    """Perform initial data refresh based on entry state."""
    if entry.state == ConfigEntryState.SETUP_IN_PROGRESS:
        await coordinator.async_config_entry_first_refresh()
    else:
        # During reload, just do a regular refresh
        await coordinator.async_refresh()


def _update_device_registry(hass: HomeAssistant, entry: ConfigEntry, host: str) -> None:
    """Update device registry with detected modem info.

    NOTE: Device name is kept as "Cable Modem" (without host) for entity ID stability.
    With has_entity_name=True, entity IDs are generated from device name.
    Users can rename the device in the UI if desired.
    """
    device_registry = dr.async_get(hass)

    # Use detected_modem for model field (shown in device info)
    actual_model = entry.data.get("actual_model")
    detected_modem = entry.data.get("detected_modem")

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="Cable Modem",
    )

    device_registry.async_update_device(
        device.id,
        manufacturer=entry.data.get("detected_manufacturer", "Unknown"),
        model=actual_model or detected_modem or "Cable Modem Monitor",
    )
    _LOGGER.debug(
        "Updated device registry: manufacturer=%s, model=%s",
        entry.data.get("detected_manufacturer"),
        actual_model or detected_modem,
    )


def _create_clear_history_handler(hass: HomeAssistant):
    """Create the clear history service handler."""

    async def handle_clear_history(call: ServiceCall) -> None:
        """Handle the clear_history service call."""
        days_to_keep = call.data.get("days_to_keep", 30)
        _LOGGER.info("Clearing cable modem history older than %s days", days_to_keep)

        # Get all cable modem entities
        entity_reg = er.async_get(hass)
        cable_modem_entities = [
            entity_entry.entity_id for entity_entry in entity_reg.entities.values() if entity_entry.platform == DOMAIN
        ]

        if not cable_modem_entities:
            _LOGGER.warning("No cable modem entities found in registry")
            return

        _LOGGER.info("Found %s cable modem entities to purge", len(cable_modem_entities))

        # Clear history in database
        deleted = await hass.async_add_executor_job(_clear_db_history, hass, cable_modem_entities, days_to_keep)

        if deleted > 0:
            _LOGGER.info("Successfully cleared %s historical records", deleted)
        else:
            _LOGGER.warning("No records were deleted")

    return handle_clear_history


def _get_dashboard_titles(short_titles: bool) -> dict[str, str]:
    """Get dashboard card titles based on user preference."""
    if short_titles:
        return {
            "ds_power": "DS Power (dBmV)",
            "ds_snr": "DS SNR (dB)",
            "us_power": "US Power (dBmV)",
            "us_freq": "US Frequency (MHz)",
            "corrected": "Corrected Errors",
            "uncorrected": "Uncorrected Errors",
        }
    return {
        "ds_power": "Downstream Power Levels (dBmV)",
        "ds_snr": "Downstream Signal-to-Noise Ratio (dB)",
        "us_power": "Upstream Power Levels (dBmV)",
        "us_freq": "Upstream Frequency (MHz)",
        "corrected": "Corrected Errors (Total)",
        "uncorrected": "Uncorrected Errors (Total)",
    }


def _format_title_with_type(base_title: str, channel_type: str | None, short_titles: bool) -> str:
    """Format a title with optional channel type.

    For single-type directions, includes the channel type in the title.
    E.g., "Downstream Power Levels (dBmV)" -> "Downstream QAM Power Levels (dBmV)"
    """
    if not channel_type:
        return base_title

    type_upper = channel_type.upper()

    if short_titles:
        # "DS Power (dBmV)" -> "DS QAM Power (dBmV)"
        if base_title.startswith("DS "):
            return f"DS {type_upper} {base_title[3:]}"
        elif base_title.startswith("US "):
            return f"US {type_upper} {base_title[3:]}"
    else:
        # "Downstream Power Levels (dBmV)" -> "Downstream QAM Power Levels (dBmV)"
        if base_title.startswith("Downstream "):
            return f"Downstream {type_upper} {base_title[11:]}"
        elif base_title.startswith("Upstream "):
            return f"Upstream {type_upper} {base_title[9:]}"

    return base_title


def _get_channel_info(
    coordinator,
) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """Extract downstream and upstream channel info from coordinator data.

    Returns tuples of (channel_type, channel_id) for each direction.
    """
    downstream_info: list[tuple[str, int]] = []
    upstream_info: list[tuple[str, int]] = []

    if not coordinator.data:
        return downstream_info, upstream_info

    if "_downstream_by_id" in coordinator.data:
        # Keys are already (channel_type, channel_id) tuples
        downstream_info = sorted(coordinator.data["_downstream_by_id"].keys())
    elif "cable_modem_downstream" in coordinator.data:
        for idx, ch in enumerate(coordinator.data["cable_modem_downstream"]):
            ch_type = _normalize_channel_type(ch, "downstream")
            ch_id = int(ch.get("channel_id", ch.get("channel", idx + 1)))
            downstream_info.append((ch_type, ch_id))
        downstream_info = sorted(downstream_info)

    if "_upstream_by_id" in coordinator.data:
        # Keys are already (channel_type, channel_id) tuples
        upstream_info = sorted(coordinator.data["_upstream_by_id"].keys())
    elif "cable_modem_upstream" in coordinator.data:
        for idx, ch in enumerate(coordinator.data["cable_modem_upstream"]):
            ch_type = _normalize_channel_type(ch, "upstream")
            ch_id = int(ch.get("channel_id", ch.get("channel", idx + 1)))
            upstream_info.append((ch_type, ch_id))
        upstream_info = sorted(upstream_info)

    return downstream_info, upstream_info


def _group_channels_by_type(
    channel_info: list[tuple[str, int]],
) -> dict[str, list[tuple[str, int]]]:
    """Group channels by their type.

    Returns dict mapping channel_type -> list of (channel_type, channel_id) tuples.
    """
    from collections import defaultdict

    grouped: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for ch_type, ch_id in channel_info:
        grouped[ch_type].append((ch_type, ch_id))
    return dict(grouped)


def _get_channel_types(channel_info: list[tuple[str, int]]) -> set[str]:
    """Get unique channel types from channel info."""
    return {ch_type for ch_type, _ in channel_info}


def _build_status_card_yaml() -> list[str]:
    """Build YAML for the status entities card."""
    return [
        "  - type: entities",
        "    title: Cable Modem Status",
        "    entities:",
        "      - entity: sensor.cable_modem_status",
        "        name: Status",
        "      - entity: sensor.cable_modem_ping_latency",
        "        name: Ping",
        "      - entity: sensor.cable_modem_http_latency",
        "        name: HTTP",
        "        icon: mdi:speedometer",
        "      - entity: sensor.cable_modem_software_version",
        "        name: Software Version",
        "      - entity: sensor.cable_modem_system_uptime",
        "        name: Uptime",
        "      - entity: sensor.cable_modem_last_boot_time",
        "        name: Last Boot",
        "        format: date",
        "      - entity: sensor.cable_modem_ds_channel_count",
        "        name: Downstream Channel Count",
        "      - entity: sensor.cable_modem_us_channel_count",
        "        name: Upstream Channel Count",
        "      - entity: sensor.cable_modem_total_corrected_errors",
        "        name: Total Corrected Errors",
        "      - entity: sensor.cable_modem_total_uncorrected_errors",
        "        name: Total Uncorrected Errors",
        "      - entity: button.cable_modem_restart_modem",
        "        name: Restart",
        "    show_header_toggle: false",
        "    state_color: false",
    ]


def _format_channel_label(ch_type: str, ch_id: int, label_format: str) -> str:
    """Format channel label based on user preference.

    label_format options:
    - 'full': 'QAM Ch 32' or 'OFDM Ch 1'
    - 'id_only': 'Ch 32'
    - 'type_id': 'QAM 32' or 'OFDM 1'
    """
    if label_format == "id_only":
        return f"Ch {ch_id}"
    elif label_format == "type_id":
        return f"{ch_type.upper()} {ch_id}"
    else:  # 'full' (default)
        return f"{ch_type.upper()} Ch {ch_id}"


def _build_channel_graph_yaml(
    title: str,
    hours: int,
    channel_info: list[tuple[str, int]],
    entity_pattern: str,
    channel_label: str = "full",
) -> list[str]:
    """Build YAML for a channel history graph.

    channel_info: list of (channel_type, channel_id) tuples
    entity_pattern: pattern with {ch_type} and {ch_id} placeholders
    channel_label: 'full', 'id_only', or 'type_id'
    """
    yaml_parts = [
        "  - type: history-graph",
        f"    title: {title}",
        f"    hours_to_show: {hours}",
        "    entities:",
    ]
    for ch_type, ch_id in channel_info:
        entity_id = entity_pattern.format(ch_type=ch_type, ch_id=ch_id)
        label = _format_channel_label(ch_type, ch_id, channel_label)
        yaml_parts.append(f"      - entity: {entity_id}")
        yaml_parts.append(f"        name: {label}")
    return yaml_parts


def _build_error_graphs_yaml(titles: dict[str, str]) -> list[str]:
    """Build YAML for error history graphs."""
    return [
        "  - type: history-graph",
        f"    title: {titles['corrected']}",
        "    hours_to_show: 168",
        "    entities:",
        "      - entity: sensor.cable_modem_total_corrected_errors",
        "        name: Corrected Error Count",
        "  - type: history-graph",
        f"    title: {titles['uncorrected']}",
        "    hours_to_show: 168",
        "    entities:",
        "      - entity: sensor.cable_modem_total_uncorrected_errors",
        "        name: Uncorrected Error Count",
    ]


def _build_latency_graph_yaml() -> list[str]:
    """Build YAML for the latency history graph."""
    return [
        "  - type: history-graph",
        "    title: Latency",
        "    hours_to_show: 6",
        "    entities:",
        "      - entity: sensor.cable_modem_ping_latency",
        "        name: Ping",
        "      - entity: sensor.cable_modem_http_latency",
        "        name: HTTP",
    ]


def _add_channel_graphs(
    yaml_parts: list[str],
    channel_info: list[tuple[str, int]],
    base_title: str,
    entity_pattern: str,
    graph_hours: int,
    channel_label: str,
    channel_grouping: str,
    short_titles: bool,
) -> None:
    """Add channel graph cards based on grouping and labeling options.

    Modifies yaml_parts in place.
    """
    if not channel_info:
        return

    channel_types = _get_channel_types(channel_info)
    is_single_type = len(channel_types) == 1

    if channel_grouping == "by_type":
        # Separate cards per channel type
        grouped = _group_channels_by_type(channel_info)
        for ch_type in sorted(grouped.keys()):
            channels = grouped[ch_type]
            title = _format_title_with_type(base_title, ch_type, short_titles)
            # With by_type, labels should be id_only (type is in title)
            effective_label = "id_only" if channel_label == "auto" else channel_label
            yaml_parts.extend(_build_channel_graph_yaml(title, graph_hours, channels, entity_pattern, effective_label))
    else:
        # by_direction: all channels in one card
        if is_single_type:
            # Single type: put type in title, use id_only labels
            single_type = next(iter(channel_types))
            title = _format_title_with_type(base_title, single_type, short_titles)
            effective_label = "id_only" if channel_label == "auto" else channel_label
        else:
            # Mixed types: keep base title, need type in labels
            title = base_title
            effective_label = "full" if channel_label == "auto" else channel_label

        yaml_parts.extend(_build_channel_graph_yaml(title, graph_hours, channel_info, entity_pattern, effective_label))


def _create_generate_dashboard_handler(hass: HomeAssistant):
    """Create the generate dashboard service handler."""

    def handle_generate_dashboard(call: ServiceCall) -> dict[str, Any]:
        """Handle the generate_dashboard service call."""
        # Get options from call
        opts = {
            "ds_power": call.data.get("include_downstream_power", True),
            "ds_snr": call.data.get("include_downstream_snr", True),
            "us_power": call.data.get("include_upstream_power", True),
            "us_freq": call.data.get("include_upstream_frequency", False),
            "errors": call.data.get("include_errors", True),
            "latency": call.data.get("include_latency", True),
            "status": call.data.get("include_status_card", True),
        }
        graph_hours = call.data.get("graph_hours", 24)
        short_titles = call.data.get("short_titles", False)
        titles = _get_dashboard_titles(short_titles)
        channel_label = call.data.get("channel_label", "auto")
        channel_grouping = call.data.get("channel_grouping", "by_direction")

        # Get coordinator data to find actual channel info
        if DOMAIN not in hass.data or not hass.data[DOMAIN]:
            return {"yaml": "# Error: No cable modem configured"}

        entry_id = next(iter(hass.data[DOMAIN]))
        coordinator = hass.data[DOMAIN][entry_id]
        downstream_info, upstream_info = _get_channel_info(coordinator)

        # Build YAML
        yaml_parts = [
            "# Cable Modem Dashboard",
            "# Copy from here, paste into: Dashboard > Add Card > Manual",
            "type: vertical-stack",
            "cards:",
        ]

        if opts["status"]:
            yaml_parts.extend(_build_status_card_yaml())

        if opts["ds_power"]:
            _add_channel_graphs(
                yaml_parts,
                downstream_info,
                titles["ds_power"],
                "sensor.cable_modem_ds_{ch_type}_ch_{ch_id}_power",
                graph_hours,
                channel_label,
                channel_grouping,
                short_titles,
            )

        if opts["ds_snr"]:
            _add_channel_graphs(
                yaml_parts,
                downstream_info,
                titles["ds_snr"],
                "sensor.cable_modem_ds_{ch_type}_ch_{ch_id}_snr",
                graph_hours,
                channel_label,
                channel_grouping,
                short_titles,
            )

        if opts["us_power"]:
            _add_channel_graphs(
                yaml_parts,
                upstream_info,
                titles["us_power"],
                "sensor.cable_modem_us_{ch_type}_ch_{ch_id}_power",
                graph_hours,
                channel_label,
                channel_grouping,
                short_titles,
            )

        if opts["us_freq"]:
            _add_channel_graphs(
                yaml_parts,
                upstream_info,
                titles["us_freq"],
                "sensor.cable_modem_us_{ch_type}_ch_{ch_id}_frequency",
                graph_hours,
                channel_label,
                channel_grouping,
                short_titles,
            )

        if opts["errors"]:
            yaml_parts.extend(_build_error_graphs_yaml(titles))

        if opts["latency"]:
            yaml_parts.extend(_build_latency_graph_yaml())

        return {"yaml": "\n".join(yaml_parts)}

    return handle_generate_dashboard


def _clear_db_history(hass: HomeAssistant, cable_modem_entities: list, days_to_keep: int) -> int:
    """Clear history from database (runs in executor)."""
    try:
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        cutoff_ts = cutoff_date.timestamp()

        db_path = hass.config.path("home-assistant_v2.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Find metadata IDs for entities
        placeholders = ",".join("?" * len(cable_modem_entities))
        query = f"SELECT metadata_id, entity_id FROM states_meta WHERE entity_id IN ({placeholders})"  # nosec B608
        cursor.execute(query, cable_modem_entities)
        metadata_ids = [row[0] for row in cursor.fetchall()]

        if not metadata_ids:
            _LOGGER.warning("No cable modem sensors found in database states")
            conn.close()
            return 0

        # Delete old states
        placeholders = ",".join("?" * len(metadata_ids))
        query = f"DELETE FROM states WHERE metadata_id IN ({placeholders}) AND last_updated_ts < ?"  # nosec B608
        cursor.execute(query, (*metadata_ids, cutoff_ts))
        states_deleted = cursor.rowcount

        # Delete old statistics
        stats_deleted = _delete_statistics(cursor, cable_modem_entities, cutoff_ts)

        conn.commit()
        cursor.execute("VACUUM")
        conn.close()

        _LOGGER.info(
            "Cleared %d state records and %d statistics records older than %d days",
            states_deleted,
            stats_deleted,
            days_to_keep,
        )

        return states_deleted + stats_deleted

    except Exception as e:
        _LOGGER.error("Error clearing history: %s", e)
        return 0


def _delete_statistics(cursor, cable_modem_entities: list, cutoff_ts: float) -> int:
    """Delete statistics records (helper for _clear_db_history)."""
    placeholders = ",".join("?" * len(cable_modem_entities))
    query = f"SELECT id FROM statistics_meta WHERE statistic_id IN ({placeholders})"  # nosec B608
    cursor.execute(query, cable_modem_entities)
    stats_metadata_ids = [row[0] for row in cursor.fetchall()]

    if not stats_metadata_ids:
        return 0

    placeholders = ",".join("?" * len(stats_metadata_ids))

    # Delete from statistics table
    query = f"DELETE FROM statistics WHERE metadata_id IN ({placeholders}) AND start_ts < ?"  # nosec B608
    cursor.execute(query, (*stats_metadata_ids, cutoff_ts))
    stats_deleted: int = cursor.rowcount

    # Delete from statistics_short_term table
    query = f"DELETE FROM statistics_short_term WHERE metadata_id IN ({placeholders}) AND start_ts < ?"  # nosec B608
    cursor.execute(query, (*stats_metadata_ids, cutoff_ts))
    stats_deleted += cursor.rowcount

    return stats_deleted


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Cable Modem Monitor from a config entry."""
    _LOGGER.info("Cable Modem Monitor version %s is starting", VERSION)

    # Extract configuration
    host = entry.data[CONF_HOST]
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    scan_interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    modem_choice = entry.data.get(CONF_MODEM_CHOICE, "auto")

    # Optimization: Only do full parser discovery if needed
    if modem_choice and modem_choice != "auto":
        # User selected specific parser - load only that one (fast path)
        parser_class = await hass.async_add_executor_job(get_parser_by_name, modem_choice)
        if parser_class:
            _LOGGER.info("Loaded specific parser: %s (skipped full discovery)", modem_choice)
            selected_parser = parser_class()
            parser_name_hint = None
        else:
            # Fallback to auto if parser not found
            _LOGGER.warning("Parser '%s' not found, falling back to auto discovery", modem_choice)
            parsers = await hass.async_add_executor_job(get_parsers)
            selected_parser = parsers
            parser_name_hint = entry.data.get(CONF_PARSER_NAME)
    else:
        # Auto mode - need all parsers for discovery
        parsers = await hass.async_add_executor_job(get_parsers)
        selected_parser = parsers
        parser_name_hint = entry.data.get(CONF_PARSER_NAME)

    # Create scraper
    scraper = ModemScraper(
        host,
        username,
        password,
        parser=selected_parser,
        cached_url=entry.data.get(CONF_WORKING_URL),
        parser_name=parser_name_hint,
        verify_ssl=VERIFY_SSL,
    )

    # Create health monitor
    health_monitor = await _create_health_monitor(hass)

    # Get ICMP support setting (auto-detected during setup, re-tested on options change)
    supports_icmp = entry.data.get(CONF_SUPPORTS_ICMP, True)

    # Create coordinator
    async_update_data = _create_update_function(hass, scraper, health_monitor, host, supports_icmp)
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"Cable Modem {host}",
        update_method=async_update_data,
        update_interval=timedelta(seconds=scan_interval),
        config_entry=entry,
    )

    # Store scraper reference for cache invalidation after modem restart
    coordinator.scraper = scraper  # type: ignore[attr-defined]

    # Perform initial data fetch
    await _perform_initial_refresh(coordinator, entry)

    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Migrate entity IDs for DOCSIS 3.0 modems (v3.11+ naming change)
    # Must run before platform setup so sensors don't create duplicates
    docsis_version = entry.data.get(CONF_DOCSIS_VERSION)
    migrated = migrate_docsis30_entities(hass, entry, docsis_version)
    if migrated > 0:
        _LOGGER.info("Entity migration complete: %d entities updated", migrated)

    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Update device registry
    _update_device_registry(hass, entry, host)

    # Register update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Register services (only once)
    if not hass.services.has_service(DOMAIN, SERVICE_CLEAR_HISTORY):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CLEAR_HISTORY,
            _create_clear_history_handler(hass),
            schema=SERVICE_CLEAR_HISTORY_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_GENERATE_DASHBOARD):
        hass.services.async_register(
            DOMAIN,
            SERVICE_GENERATE_DASHBOARD,
            _create_generate_dashboard_handler(hass),
            schema=SERVICE_GENERATE_DASHBOARD_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Try to unload platforms, but handle case where they were never loaded
    try:
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    except ValueError as err:
        # Platforms were never loaded (setup failed before platforms were added)
        _LOGGER.debug("Platforms were never loaded for entry %s: %s", entry.entry_id, err)
        unload_ok = True  # Consider it successful since there's nothing to unload

    if unload_ok:
        # Clean up coordinator data
        hass.data[DOMAIN].pop(entry.entry_id, None)

        # Unregister services if this is the last entry
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_CLEAR_HISTORY)
            hass.services.async_remove(DOMAIN, SERVICE_GENERATE_DASHBOARD)

    return bool(unload_ok)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
