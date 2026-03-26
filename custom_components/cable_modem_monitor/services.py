"""Service handlers for Cable Modem Monitor.

Services:
    cable_modem_monitor.generate_dashboard:
        Generates Lovelace YAML for a complete modem dashboard based on
        current channel data.

See HA_ADAPTER_SPEC.md § Services.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.util import slugify as ha_slugify

from .const import (
    CONF_ENTITY_PREFIX,
    CONF_SUPPORTS_ICMP,
    DOMAIN,
    ENTITY_PREFIX_IP,
    ENTITY_PREFIX_MODEL,
)
from .coordinator import CableModemConfigEntry

_LOGGER = logging.getLogger(__name__)

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


# ------------------------------------------------------------------
# Entity ID prefix — matches _update_device_registry in __init__.py
# ------------------------------------------------------------------


def _get_entity_prefix(entry: CableModemConfigEntry) -> str:
    """Derive the entity ID prefix from config entry settings.

    Must match the device_name logic in _update_device_registry so
    generated entity IDs match what HA actually creates.
    """
    data = entry.data
    prefix = data.get(CONF_ENTITY_PREFIX, "none")

    if prefix == ENTITY_PREFIX_MODEL:
        identity = entry.runtime_data.modem_identity
        device_name = f"Cable Modem {identity.model}"
    elif prefix == ENTITY_PREFIX_IP:
        device_name = f"Cable Modem {data[CONF_HOST]}"
    else:
        device_name = "Cable Modem"

    return str(ha_slugify(device_name))


# ------------------------------------------------------------------
# Channel helpers — read v3.14 ModemSnapshot data directly
# ------------------------------------------------------------------


def _get_channel_info(
    channels: list[dict[str, Any]],
    default_type: str,
) -> list[tuple[str, int]]:
    """Extract (channel_type, channel_id) pairs from a channel list.

    Core's parser coordinator normalizes these fields, so this is a
    straight read — no type guessing or ID parsing needed.

    Args:
        channels: Channel dicts from modem_data["downstream"] or
            modem_data["upstream"].
        default_type: Fallback type when channel_type is absent.
    """
    result: list[tuple[str, int]] = []
    for idx, ch in enumerate(channels):
        ch_type = ch.get("channel_type", default_type)
        ch_id = ch.get("channel_id", idx + 1)
        if isinstance(ch_id, str):
            try:
                ch_id = int(ch_id)
            except ValueError:
                ch_id = idx + 1
        result.append((ch_type, ch_id))
    return sorted(result)


def _group_by_type(
    channel_info: list[tuple[str, int]],
) -> dict[str, list[tuple[str, int]]]:
    """Group channel info tuples by channel type."""
    grouped: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for ch_type, ch_id in channel_info:
        grouped[ch_type].append((ch_type, ch_id))
    return dict(grouped)


def _unique_types(channel_info: list[tuple[str, int]]) -> set[str]:
    """Get unique channel types from channel info."""
    return {ch_type for ch_type, _ in channel_info}


# ------------------------------------------------------------------
# YAML builders
# ------------------------------------------------------------------


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


def _format_title_with_type(
    base_title: str,
    channel_type: str | None,
    short_titles: bool,
) -> str:
    """Format a title with optional channel type prefix.

    For single-type directions, puts the type in the title so labels
    can omit it (e.g., "Downstream QAM Power Levels (dBmV)").
    """
    if not channel_type:
        return base_title
    type_upper = channel_type.upper()
    if short_titles:
        if base_title.startswith("DS "):
            return f"DS {type_upper} {base_title[3:]}"
        if base_title.startswith("US "):
            return f"US {type_upper} {base_title[3:]}"
    else:
        if base_title.startswith("Downstream "):
            return f"Downstream {type_upper} {base_title[11:]}"
        if base_title.startswith("Upstream "):
            return f"Upstream {type_upper} {base_title[9:]}"
    return base_title


def _format_channel_label(
    ch_type: str,
    ch_id: int,
    label_format: str,
) -> str:
    """Format a channel label for the dashboard.

    Args:
        ch_type: Channel type (e.g., "qam", "ofdm").
        ch_id: Channel ID number.
        label_format: One of "full", "id_only", "type_id".
    """
    if label_format == "id_only":
        return f"Ch {ch_id}"
    if label_format == "type_id":
        return f"{ch_type.upper()} {ch_id}"
    return f"{ch_type.upper()} Ch {ch_id}"


def _build_status_card_yaml(
    entity_prefix: str,
    *,
    has_icmp: bool,
    has_restart: bool,
) -> list[str]:
    """Build YAML for the status entities card.

    Args:
        entity_prefix: Entity ID prefix (e.g., "cable_modem").
        has_icmp: Whether ICMP ping latency entity exists.
        has_restart: Whether the restart button exists.
    """
    lines = [
        "  - type: entities",
        "    title: Cable Modem Status",
        "    entities:",
        f"      - entity: sensor.{entity_prefix}_status",
        "        name: Status",
    ]
    if has_icmp:
        lines.append(f"      - entity: sensor.{entity_prefix}_ping_latency")
        lines.append("        name: Ping")
    lines.extend(
        [
            f"      - entity: sensor.{entity_prefix}_http_latency",
            "        name: HTTP",
            "        icon: mdi:speedometer",
            f"      - entity: sensor.{entity_prefix}_software_version",
            "        name: Software Version",
            f"      - entity: sensor.{entity_prefix}_system_uptime",
            "        name: Uptime",
            f"      - entity: sensor.{entity_prefix}_last_boot_time",
            "        name: Last Boot",
            "        format: date",
            f"      - entity: sensor.{entity_prefix}_ds_channel_count",
            "        name: Downstream Channel Count",
            f"      - entity: sensor.{entity_prefix}_us_channel_count",
            "        name: Upstream Channel Count",
            f"      - entity: sensor.{entity_prefix}_total_corrected_errors",
            "        name: Total Corrected Errors",
            f"      - entity: sensor.{entity_prefix}_total_uncorrected_errors",
            "        name: Total Uncorrected Errors",
        ]
    )
    if has_restart:
        lines.append(f"      - entity: button.{entity_prefix}_restart_modem")
        lines.append("        name: Restart")
    lines.extend(
        [
            "    show_header_toggle: false",
            "    state_color: false",
        ]
    )
    return lines


def _build_channel_graph_yaml(
    title: str,
    hours: int,
    channel_info: list[tuple[str, int]],
    entity_pattern: str,
    channel_label: str,
) -> list[str]:
    """Build YAML for a channel history graph card."""
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


def _build_error_graphs_yaml(entity_prefix: str, titles: dict[str, str]) -> list[str]:
    """Build YAML for error history graphs."""
    return [
        "  - type: history-graph",
        f"    title: {titles['corrected']}",
        "    hours_to_show: 168",
        "    entities:",
        f"      - entity: sensor.{entity_prefix}_total_corrected_errors",
        "        name: Corrected Error Count",
        "  - type: history-graph",
        f"    title: {titles['uncorrected']}",
        "    hours_to_show: 168",
        "    entities:",
        f"      - entity: sensor.{entity_prefix}_total_uncorrected_errors",
        "        name: Uncorrected Error Count",
    ]


def _build_latency_graph_yaml(entity_prefix: str, *, has_icmp: bool) -> list[str]:
    """Build YAML for the latency history graph."""
    lines = [
        "  - type: history-graph",
        "    title: Latency",
        "    hours_to_show: 6",
        "    entities:",
    ]
    if has_icmp:
        lines.append(f"      - entity: sensor.{entity_prefix}_ping_latency")
        lines.append("        name: Ping")
    lines.append(f"      - entity: sensor.{entity_prefix}_http_latency")
    lines.append("        name: HTTP")
    return lines


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
    """Add channel graph cards based on grouping preference.

    Modifies *yaml_parts* in place.
    """
    if not channel_info:
        return

    types = _unique_types(channel_info)
    is_single_type = len(types) == 1

    if channel_grouping == "by_type":
        grouped = _group_by_type(channel_info)
        for ch_type in sorted(grouped):
            channels = grouped[ch_type]
            title = _format_title_with_type(base_title, ch_type, short_titles)
            effective_label = "id_only" if channel_label == "auto" else channel_label
            yaml_parts.extend(
                _build_channel_graph_yaml(
                    title,
                    graph_hours,
                    channels,
                    entity_pattern,
                    effective_label,
                )
            )
    else:
        if is_single_type:
            single_type = next(iter(types))
            title = _format_title_with_type(base_title, single_type, short_titles)
            effective_label = "id_only" if channel_label == "auto" else channel_label
        else:
            title = base_title
            effective_label = "full" if channel_label == "auto" else channel_label
        yaml_parts.extend(
            _build_channel_graph_yaml(
                title,
                graph_hours,
                channel_info,
                entity_pattern,
                effective_label,
            )
        )


# ------------------------------------------------------------------
# Service handler factory
# ------------------------------------------------------------------


def _find_loaded_entry(
    hass: HomeAssistant,
) -> CableModemConfigEntry | None:
    """Find the first loaded config entry for our domain."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if hasattr(entry, "runtime_data") and entry.runtime_data is not None:
            return entry  # type: ignore[return-value]
    return None


def create_generate_dashboard_handler(
    hass: HomeAssistant,
) -> Any:
    """Create the generate_dashboard service handler."""

    def handle_generate_dashboard(call: ServiceCall) -> dict[str, Any]:
        """Handle the generate_dashboard service call."""
        entry = _find_loaded_entry(hass)
        if entry is None:
            return {"yaml": "# Error: No cable modem configured"}

        snapshot = entry.runtime_data.data_coordinator.data
        if snapshot is None or snapshot.modem_data is None:
            return {"yaml": "# Error: No modem data available"}

        modem_data = snapshot.modem_data
        entity_prefix = _get_entity_prefix(entry)
        has_icmp = bool(entry.data.get(CONF_SUPPORTS_ICMP, False))
        has_restart = entry.runtime_data.orchestrator.supports_restart

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

        downstream_info = _get_channel_info(modem_data.get("downstream", []), "qam")
        upstream_info = _get_channel_info(modem_data.get("upstream", []), "atdma")

        yaml_parts = [
            "# Cable Modem Dashboard",
            "# Copy from here, paste into:" " Dashboard > Add Card > Manual",
            "type: vertical-stack",
            "cards:",
        ]

        if opts["status"]:
            yaml_parts.extend(_build_status_card_yaml(entity_prefix, has_icmp=has_icmp, has_restart=has_restart))

        # fmt: off
        channel_graphs = [
            ("ds_power", downstream_info, "ds_power", f"sensor.{entity_prefix}_ds_{{ch_type}}_ch_{{ch_id}}_power"),
            ("ds_snr",   downstream_info, "ds_snr",   f"sensor.{entity_prefix}_ds_{{ch_type}}_ch_{{ch_id}}_snr"),
            ("ds_freq",  downstream_info, "ds_freq",  f"sensor.{entity_prefix}_ds_{{ch_type}}_ch_{{ch_id}}_frequency"),
            ("us_power", upstream_info,   "us_power", f"sensor.{entity_prefix}_us_{{ch_type}}_ch_{{ch_id}}_power"),
            ("us_freq",  upstream_info,   "us_freq",  f"sensor.{entity_prefix}_us_{{ch_type}}_ch_{{ch_id}}_frequency"),
        ]
        # fmt: on

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
            yaml_parts.extend(_build_error_graphs_yaml(entity_prefix, titles))

        if opts["latency"]:
            yaml_parts.extend(_build_latency_graph_yaml(entity_prefix, has_icmp=has_icmp))

        _LOGGER.info(
            "Generated dashboard: %d DS channels, %d US channels, prefix=%s",
            len(downstream_info),
            len(upstream_info),
            entity_prefix,
        )
        return {"yaml": "\n".join(yaml_parts)}

    return handle_generate_dashboard


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------


def async_register_services(hass: HomeAssistant) -> None:
    """Register services (called on first entry setup)."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE_DASHBOARD,
        create_generate_dashboard_handler(hass),
        schema=SERVICE_GENERATE_DASHBOARD_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    _LOGGER.debug("Registered %s service", SERVICE_GENERATE_DASHBOARD)


def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister services (called when last entry is removed)."""
    hass.services.async_remove(DOMAIN, SERVICE_GENERATE_DASHBOARD)
    _LOGGER.debug("Unregistered %s service", SERVICE_GENERATE_DASHBOARD)
