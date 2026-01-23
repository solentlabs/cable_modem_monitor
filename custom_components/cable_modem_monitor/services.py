"""Service handlers for Cable Modem Monitor.

Services:
    cable_modem_monitor.clear_history: Clear historical sensor data
    cable_modem_monitor.generate_dashboard: Generate Lovelace dashboard YAML
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er

from .channel_utils import get_channel_info, get_channel_types, group_channels_by_type
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Service definitions
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
        vol.Optional("include_downstream_frequency", default=True): cv.boolean,
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


def _get_dashboard_titles(short_titles: bool) -> dict[str, str]:
    """Get dashboard card titles based on user preference."""
    if short_titles:
        return {
            "ds_power": "DS Power (dBmV)",
            "ds_snr": "DS SNR (dB)",
            "ds_freq": "DS Frequency (MHz)",
            "us_power": "US Power (dBmV)",
            "us_freq": "US Frequency (MHz)",
            "corrected": "Corrected Errors",
            "uncorrected": "Uncorrected Errors",
        }
    return {
        "ds_power": "Downstream Power Levels (dBmV)",
        "ds_snr": "Downstream Signal-to-Noise Ratio (dB)",
        "ds_freq": "Downstream Frequency (MHz)",
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

    channel_types = get_channel_types(channel_info)
    is_single_type = len(channel_types) == 1

    if channel_grouping == "by_type":
        # Separate cards per channel type
        grouped = group_channels_by_type(channel_info)
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


def create_clear_history_handler(hass: HomeAssistant):
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


def create_generate_dashboard_handler(hass: HomeAssistant):  # noqa: C901
    """Create the generate dashboard service handler."""

    def handle_generate_dashboard(call: ServiceCall) -> dict[str, Any]:  # noqa: C901
        """Handle the generate_dashboard service call."""
        try:
            # Get options from call
            opts = {
                "ds_power": call.data.get("include_downstream_power", True),
                "ds_snr": call.data.get("include_downstream_snr", True),
                "ds_freq": call.data.get("include_downstream_frequency", True),
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

            # Find first coordinator (skip non-coordinator entries like "log_buffer")
            coordinator = None
            for value in hass.data[DOMAIN].values():
                if hasattr(value, "data") and hasattr(value, "async_refresh"):
                    coordinator = value
                    break

            if coordinator is None:
                return {"yaml": "# Error: No cable modem coordinator found"}

            downstream_info, upstream_info = get_channel_info(coordinator)

            # Build YAML
            yaml_parts = [
                "# Cable Modem Dashboard",
                "# Copy from here, paste into: Dashboard > Add Card > Manual",
                "type: vertical-stack",
                "cards:",
            ]

            if opts["status"]:
                yaml_parts.extend(_build_status_card_yaml())

            # Channel graph configurations: (opt_key, channel_info, title_key, entity_pattern)
            channel_graphs = [
                ("ds_power", downstream_info, "ds_power", "sensor.cable_modem_ds_{ch_type}_ch_{ch_id}_power"),
                ("ds_snr", downstream_info, "ds_snr", "sensor.cable_modem_ds_{ch_type}_ch_{ch_id}_snr"),
                ("ds_freq", downstream_info, "ds_freq", "sensor.cable_modem_ds_{ch_type}_ch_{ch_id}_frequency"),
                ("us_power", upstream_info, "us_power", "sensor.cable_modem_us_{ch_type}_ch_{ch_id}_power"),
                ("us_freq", upstream_info, "us_freq", "sensor.cable_modem_us_{ch_type}_ch_{ch_id}_frequency"),
            ]

            for opt_key, ch_info, title_key, entity_pattern in channel_graphs:
                if opts[opt_key]:
                    _add_channel_graphs(
                        yaml_parts,
                        ch_info,
                        titles[title_key],
                        entity_pattern,
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

        except Exception as e:
            _LOGGER.exception("Error generating dashboard: %s", e)
            return {"yaml": f"# Error generating dashboard: {e}"}

    return handle_generate_dashboard
