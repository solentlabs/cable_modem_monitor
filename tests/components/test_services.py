"""Tests for the services module — YAML builders, channel helpers, and service handlers.

Most functions are pure (no I/O), tested via table-driven patterns.
Service handler tests mock runtime_data and HA infrastructure.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.cable_modem_monitor.const import DOMAIN
from custom_components.cable_modem_monitor.coordinator import (
    CableModemRuntimeData,
)
from custom_components.cable_modem_monitor.services import (
    _add_channel_graphs,
    _build_channel_graph_yaml,
    _build_error_graphs_yaml,
    _build_latency_graph_yaml,
    _build_status_card_yaml,
    _find_loaded_entries,
    _find_loaded_entry,
    _format_channel_label,
    _format_title_with_type,
    _get_channel_info,
    _get_dashboard_titles,
    _get_entity_prefix,
    _group_by_type,
    _resolve_config_entry_for_device,
    _resolve_target_entries,
    _unique_types,
    async_register_services,
    async_request_modem_refresh,
    async_unregister_services,
    create_generate_dashboard_handler,
    create_request_health_check_handler,
    create_request_refresh_handler,
)

# -----------------------------------------------------------------------
# _get_channel_info
# -----------------------------------------------------------------------

# ┌──────────────────────────────┬─────────────────────────────────────┬──────────────────────────────┐
# │ input channels               │ default_type │ expected output             │ description                │
# ├──────────────────────────────┼──────────────┼─────────────────────────────┼────────────────────────────┤
# │ typed + id                   │ "qam"        │ sorted by (type, id)        │ explicit channel_type+id   │
# │ no channel_type              │ "qam"        │ uses default_type           │ falls back to default      │
# │ string channel_id            │ "qam"        │ parsed to int               │ str→int conversion         │
# │ invalid string channel_id    │ "qam"        │ uses index+1 fallback       │ non-numeric fallback       │
# │ empty list                   │ "qam"        │ empty list                  │ no channels                │
# └──────────────────────────────┴──────────────┴─────────────────────────────┴────────────────────────────┘
#
# fmt: off
CHANNEL_INFO_CASES: list[tuple[list[dict[str, Any]], str, list[tuple[str, int]], str]] = [
    (
        [{"channel_type": "ofdm", "channel_id": 2}, {"channel_type": "qam", "channel_id": 1}],
        "qam",
        [("ofdm", 2), ("qam", 1)],
        "sorted_by_type_and_id",
    ),
    (
        [{"channel_id": 5}],
        "qam",
        [("qam", 5)],
        "default_type_used",
    ),
    (
        [{"channel_type": "qam", "channel_id": "3"}],
        "qam",
        [("qam", 3)],
        "string_id_parsed",
    ),
    (
        [{"channel_type": "qam", "channel_id": "abc"}],
        "qam",
        [("qam", 1)],
        "invalid_string_id_fallback",
    ),
    (
        [],
        "qam",
        [],
        "empty_list",
    ),
]
# fmt: on


@pytest.mark.parametrize(
    "channels,default_type,expected,desc",
    CHANNEL_INFO_CASES,
    ids=[c[3] for c in CHANNEL_INFO_CASES],
)
def test_get_channel_info(channels, default_type, expected, desc):
    """_get_channel_info extracts and sorts channel tuples."""
    assert _get_channel_info(channels, default_type) == expected


# -----------------------------------------------------------------------
# _group_by_type / _unique_types
# -----------------------------------------------------------------------


def test_group_by_type():
    """Channels grouped by type."""
    info = [("qam", 1), ("ofdm", 33), ("qam", 2)]
    grouped = _group_by_type(info)
    assert set(grouped.keys()) == {"qam", "ofdm"}
    assert grouped["qam"] == [("qam", 1), ("qam", 2)]
    assert grouped["ofdm"] == [("ofdm", 33)]


def test_unique_types():
    """Unique channel types extracted."""
    info = [("qam", 1), ("ofdm", 33), ("qam", 2)]
    assert _unique_types(info) == {"qam", "ofdm"}


# -----------------------------------------------------------------------
# _format_channel_label
# -----------------------------------------------------------------------

# fmt: off
LABEL_CASES = [
    ("qam", 1, "full",    "QAM Ch 1",  "full_format"),
    ("qam", 1, "id_only", "Ch 1",      "id_only_format"),
    ("qam", 1, "type_id", "QAM 1",     "type_id_format"),
]
# fmt: on


@pytest.mark.parametrize("ch_type,ch_id,fmt,expected,desc", LABEL_CASES, ids=[c[4] for c in LABEL_CASES])
def test_format_channel_label(ch_type: str, ch_id: int, fmt: str, expected: str, desc: str):
    """Channel labels formatted per style option."""
    assert _format_channel_label(ch_type, ch_id, fmt) == expected


# -----------------------------------------------------------------------
# _format_title_with_type
# -----------------------------------------------------------------------

# fmt: off
TITLE_CASES = [
    ("Downstream Power Levels (dBmV)", "qam",  False, "Downstream QAM Power Levels (dBmV)", "long_ds"),
    ("Upstream Power Levels (dBmV)",   "atdma", False, "Upstream ATDMA Power Levels (dBmV)", "long_us"),
    ("DS Power (dBmV)",                "qam",  True,  "DS QAM Power (dBmV)",                "short_ds"),
    ("US Power (dBmV)",                "atdma", True,  "US ATDMA Power (dBmV)",              "short_us"),
    ("Downstream Power",               None,   False, "Downstream Power",                    "no_type"),
    ("Other Title",                    "qam",  False, "Other Title",                         "no_prefix_match"),
]
# fmt: on


@pytest.mark.parametrize("base,ch_type,short,expected,desc", TITLE_CASES, ids=[c[4] for c in TITLE_CASES])
def test_format_title_with_type(base: str, ch_type: str | None, short: bool, expected: str, desc: str):
    """Title formatting with channel type insertion."""
    assert _format_title_with_type(base, ch_type, short) == expected


# -----------------------------------------------------------------------
# _get_dashboard_titles
# -----------------------------------------------------------------------


def test_dashboard_titles_short():
    """Short titles use abbreviated prefixes."""
    titles = _get_dashboard_titles(short_titles=True)
    assert titles["ds_power"] == "DS Power (dBmV)"
    assert titles["us_power"] == "US Power (dBmV)"


def test_dashboard_titles_long():
    """Long titles use full direction names."""
    titles = _get_dashboard_titles(short_titles=False)
    assert titles["ds_power"] == "Downstream Power Levels (dBmV)"
    assert titles["us_power"] == "Upstream Power Levels (dBmV)"


# -----------------------------------------------------------------------
# YAML builders
# -----------------------------------------------------------------------


def test_build_status_card_yaml_full():
    """Status card includes all entities when modem provides all data."""
    system_info = {
        "software_version": "1.0",
        "system_uptime": "12345",
        "total_corrected": 100,
        "total_uncorrected": 0,
    }
    lines = _build_status_card_yaml(
        "cable_modem",
        system_info,
        has_icmp=True,
        has_restart=True,
    )
    yaml = "\n".join(lines)
    assert "sensor.cable_modem_status" in yaml
    assert "sensor.cable_modem_ping_latency" in yaml
    assert "sensor.cable_modem_software_version" in yaml
    assert "sensor.cable_modem_system_uptime" in yaml
    assert "sensor.cable_modem_last_boot_time" in yaml
    assert "sensor.cable_modem_total_corrected_errors" in yaml
    assert "button.cable_modem_restart_modem" in yaml


def test_build_status_card_yaml_minimal():
    """Status card omits entities when modem data is sparse."""
    system_info = {}
    lines = _build_status_card_yaml(
        "cable_modem",
        system_info,
        has_icmp=False,
        has_restart=False,
    )
    yaml = "\n".join(lines)
    assert "sensor.cable_modem_status" in yaml
    assert "sensor.cable_modem_http_latency" in yaml
    assert "ds_channel_count" in yaml
    assert "ping_latency" not in yaml
    assert "software_version" not in yaml
    assert "system_uptime" not in yaml
    assert "last_boot_time" not in yaml
    assert "total_corrected_errors" not in yaml
    assert "restart_modem" not in yaml


def test_build_channel_graph_yaml():
    """Channel graph card has correct entity IDs and labels."""
    info = [("qam", 1), ("qam", 2)]
    lines = _build_channel_graph_yaml(
        "DS Power",
        24,
        info,
        "sensor.cm_ds_{ch_type}_ch_{ch_id}_power",
        "full",
    )
    yaml = "\n".join(lines)
    assert "title: DS Power" in yaml
    assert "hours_to_show: 24" in yaml
    assert "sensor.cm_ds_qam_ch_1_power" in yaml
    assert "sensor.cm_ds_qam_ch_2_power" in yaml


def test_build_error_graphs_yaml():
    """Error graphs reference correct entities."""
    titles = _get_dashboard_titles(False)
    lines = _build_error_graphs_yaml("cm", titles)
    yaml = "\n".join(lines)
    assert "sensor.cm_total_corrected_errors" in yaml
    assert "sensor.cm_total_uncorrected_errors" in yaml


def test_build_latency_graph_yaml_with_icmp():
    """Latency graph includes ICMP when available."""
    lines = _build_latency_graph_yaml("cm", has_icmp=True)
    yaml = "\n".join(lines)
    assert "sensor.cm_ping_latency" in yaml
    assert "sensor.cm_http_latency" in yaml


def test_build_latency_graph_yaml_no_icmp():
    """Latency graph omits ICMP when unavailable."""
    lines = _build_latency_graph_yaml("cm", has_icmp=False)
    yaml = "\n".join(lines)
    assert "ping_latency" not in yaml
    assert "sensor.cm_http_latency" in yaml


# -----------------------------------------------------------------------
# _add_channel_graphs (integration of builders + grouping)
# -----------------------------------------------------------------------


def test_add_channel_graphs_by_direction_single_type():
    """By-direction grouping with single type inserts type in title."""
    parts: list[str] = []
    info = [("qam", 1), ("qam", 2)]
    _add_channel_graphs(
        parts,
        info,
        "Downstream Power Levels (dBmV)",
        "sensor.cm_ds_{ch_type}_ch_{ch_id}_power",
        24,
        "auto",
        "by_direction",
        False,
    )
    yaml = "\n".join(parts)
    assert "QAM" in yaml  # type inserted in title
    assert "sensor.cm_ds_qam_ch_1_power" in yaml


def test_add_channel_graphs_by_type():
    """By-type grouping creates separate cards per type."""
    parts: list[str] = []
    info = [("qam", 1), ("ofdm", 33)]
    _add_channel_graphs(
        parts,
        info,
        "DS Power",
        "sensor.cm_ds_{ch_type}_ch_{ch_id}_power",
        24,
        "auto",
        "by_type",
        False,
    )
    yaml = "\n".join(parts)
    # Two separate title cards
    assert yaml.count("title:") == 2


def test_add_channel_graphs_empty():
    """Empty channel list produces no output."""
    parts: list[str] = []
    _add_channel_graphs(
        parts,
        [],
        "DS Power",
        "sensor.cm_ds_{ch_type}_ch_{ch_id}_power",
        24,
        "auto",
        "by_direction",
        False,
    )
    assert parts == []


# -----------------------------------------------------------------------
# Helpers for service handler tests
# -----------------------------------------------------------------------


def _make_mock_entry(
    runtime_data: CableModemRuntimeData,
    entry_id: str = "test_entry",
) -> MagicMock:
    """Create a mock config entry with runtime_data and domain."""
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.domain = DOMAIN
    entry.runtime_data = runtime_data
    return entry


def _make_mock_call(device_id: str | list[str] | None = None) -> MagicMock:
    """Create a mock ServiceCall with optional device_id."""
    call = MagicMock()
    call.data = {}
    if device_id is not None:
        call.data["device_id"] = device_id
    return call


# -----------------------------------------------------------------------
# async_request_modem_refresh (shared helper)
# -----------------------------------------------------------------------


# ┌──────────────────────┬──────────────────────────────────────────────────────┬────────────────┐
# │ health_coordinator   │ expected calls                                       │ description    │
# ├──────────────────────┼──────────────────────────────────────────────────────┼────────────────┤
# │ mock coordinator     │ reset_connectivity, health.refresh, data.refresh     │ with health    │
# │ None                 │ reset_connectivity, data.refresh                     │ without health │
# └──────────────────────┴──────────────────────────────────────────────────────┴────────────────┘
#
# fmt: off
REFRESH_HELPER_CASES = [
    (True,  "with_health"),
    (False, "without_health"),
]
# fmt: on


@pytest.mark.parametrize(
    "has_health,desc",
    REFRESH_HELPER_CASES,
    ids=[c[1] for c in REFRESH_HELPER_CASES],
)
async def test_async_request_modem_refresh(
    has_health: bool,
    desc: str,
    mock_orchestrator: MagicMock,
    mock_data_coordinator: MagicMock,
    mock_health_coordinator: MagicMock,
    mock_runtime_data: CableModemRuntimeData,
) -> None:
    """Shared helper resets backoff, optionally refreshes health, then data."""
    mock_data_coordinator.async_request_refresh = AsyncMock()

    if has_health:
        mock_health_coordinator.async_request_refresh = AsyncMock()
    else:
        mock_runtime_data.health_coordinator = None

    await async_request_modem_refresh(mock_runtime_data)

    mock_orchestrator.reset_connectivity.assert_called_once()
    mock_data_coordinator.async_request_refresh.assert_awaited_once()

    if has_health:
        mock_health_coordinator.async_request_refresh.assert_awaited_once()


async def test_refresh_helper_calls_health_before_data(
    mock_runtime_data: CableModemRuntimeData,
) -> None:
    """Health coordinator refreshed before data coordinator."""
    call_order: list[str] = []

    data_coord: MagicMock = mock_runtime_data.data_coordinator  # type: ignore[assignment]
    health_coord: MagicMock = mock_runtime_data.health_coordinator  # type: ignore[assignment]

    async def record_health() -> None:
        call_order.append("health")

    async def record_data() -> None:
        call_order.append("data")

    health_coord.async_request_refresh = record_health
    data_coord.async_request_refresh = record_data

    await async_request_modem_refresh(mock_runtime_data)

    assert call_order == ["health", "data"]


# -----------------------------------------------------------------------
# _find_loaded_entries
# -----------------------------------------------------------------------


def test_find_loaded_entries() -> None:
    """Returns only entries with non-None runtime_data."""
    loaded = MagicMock()
    loaded.runtime_data = MagicMock()

    unloaded = MagicMock(spec=[])  # no runtime_data attribute

    hass = MagicMock()
    hass.config_entries.async_entries.return_value = [loaded, unloaded]

    result = _find_loaded_entries(hass)

    hass.config_entries.async_entries.assert_called_once_with(DOMAIN)
    assert result == [loaded]


# -----------------------------------------------------------------------
# _resolve_config_entry_for_device
# -----------------------------------------------------------------------

# ┌─────────────────┬──────────────────────┬────────────────────┬──────────────────┐
# │ device exists?  │ config entry state   │ expected result    │ description      │
# ├─────────────────┼──────────────────────┼────────────────────┼──────────────────┤
# │ yes             │ loaded, our domain   │ the entry          │ valid_device     │
# │ no              │ —                    │ None               │ unknown_device   │
# │ yes             │ loaded, other domain │ None               │ wrong_domain     │
# │ yes             │ no runtime_data      │ None               │ not_loaded       │
# └─────────────────┴──────────────────────┴────────────────────┴──────────────────┘
#
# fmt: off
RESOLVE_DEVICE_CASES = [
    ("dev_1", True,  DOMAIN,  True,  True,  "valid_device"),
    ("dev_2", False, None,    None,  False, "unknown_device"),
    ("dev_3", True,  "other", True,  False, "wrong_domain"),
    ("dev_4", True,  DOMAIN,  False, False, "not_loaded"),
]
# fmt: on


@pytest.mark.parametrize(
    "device_id,device_exists,domain,has_runtime,expect_found,desc",
    RESOLVE_DEVICE_CASES,
    ids=[c[5] for c in RESOLVE_DEVICE_CASES],
)
@patch("custom_components.cable_modem_monitor.services.dr")
def test_resolve_config_entry_for_device(
    mock_dr: MagicMock,
    device_id: str,
    device_exists: bool,
    domain: str | None,
    has_runtime: bool | None,
    expect_found: bool,
    desc: str,
) -> None:
    """Device ID resolves to config entry only when valid."""
    hass = MagicMock()
    mock_registry = MagicMock()
    mock_dr.async_get.return_value = mock_registry

    if device_exists:
        device = MagicMock()
        device.config_entries = {"entry_1"}
        mock_registry.async_get.return_value = device

        entry = MagicMock()
        entry.domain = domain
        if has_runtime:
            entry.runtime_data = MagicMock()
        else:
            entry.runtime_data = None
        hass.config_entries.async_get_entry.return_value = entry
    else:
        mock_registry.async_get.return_value = None

    result = _resolve_config_entry_for_device(hass, device_id)

    if expect_found:
        assert result is not None
    else:
        assert result is None


# -----------------------------------------------------------------------
# _resolve_target_entries
# -----------------------------------------------------------------------


@patch("custom_components.cable_modem_monitor.services.dr")
def test_resolve_target_with_device_id(mock_dr: MagicMock) -> None:
    """Resolves device_id to matching config entry."""
    hass = MagicMock()
    entry = MagicMock()
    entry.domain = DOMAIN
    entry.runtime_data = MagicMock()

    mock_registry = MagicMock()
    mock_dr.async_get.return_value = mock_registry
    device = MagicMock()
    device.config_entries = {"entry_1"}
    mock_registry.async_get.return_value = device
    hass.config_entries.async_get_entry.return_value = entry

    call = _make_mock_call(device_id="dev_abc")
    result = _resolve_target_entries(hass, call)

    assert result == [entry]


def test_resolve_target_no_device_id_returns_all_loaded() -> None:
    """Falls back to all loaded entries when no device_id in call."""
    loaded = MagicMock()
    loaded.runtime_data = MagicMock()

    hass = MagicMock()
    hass.config_entries.async_entries.return_value = [loaded]

    call = _make_mock_call(device_id=None)
    result = _resolve_target_entries(hass, call)

    assert result == [loaded]


@patch("custom_components.cable_modem_monitor.services.dr")
def test_resolve_target_unknown_device_returns_empty(mock_dr: MagicMock) -> None:
    """Unknown device_id returns empty list, not fallback."""
    hass = MagicMock()
    mock_registry = MagicMock()
    mock_dr.async_get.return_value = mock_registry
    mock_registry.async_get.return_value = None

    call = _make_mock_call(device_id="nonexistent")
    result = _resolve_target_entries(hass, call)

    assert result == []


@patch("custom_components.cable_modem_monitor.services.dr")
def test_resolve_target_string_device_id(mock_dr: MagicMock) -> None:
    """Single string device_id is handled (not just list)."""
    hass = MagicMock()
    entry = MagicMock()
    entry.domain = DOMAIN
    entry.runtime_data = MagicMock()

    mock_registry = MagicMock()
    mock_dr.async_get.return_value = mock_registry
    device = MagicMock()
    device.config_entries = {"entry_1"}
    mock_registry.async_get.return_value = device
    hass.config_entries.async_get_entry.return_value = entry

    call = _make_mock_call(device_id="single_id")
    result = _resolve_target_entries(hass, call)

    assert len(result) == 1


# -----------------------------------------------------------------------
# request_refresh service handler
# -----------------------------------------------------------------------


async def test_request_refresh_triggers_refresh(
    mock_orchestrator: MagicMock,
    mock_data_coordinator: MagicMock,
    mock_health_coordinator: MagicMock,
    mock_runtime_data: CableModemRuntimeData,
) -> None:
    """Handler calls async_request_modem_refresh for resolved entry."""
    mock_data_coordinator.async_request_refresh = AsyncMock()
    mock_health_coordinator.async_request_refresh = AsyncMock()

    entry = _make_mock_entry(mock_runtime_data)
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = [entry]

    handler = create_request_refresh_handler(hass)
    call = _make_mock_call()

    await handler(call)

    mock_orchestrator.reset_connectivity.assert_called_once()
    mock_data_coordinator.async_request_refresh.assert_awaited_once()


async def test_request_refresh_no_entries() -> None:
    """Handler returns gracefully when no entries found."""
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = []

    handler = create_request_refresh_handler(hass)
    call = _make_mock_call()

    # Should not raise
    await handler(call)


# -----------------------------------------------------------------------
# request_health_check service handler
# -----------------------------------------------------------------------


async def test_request_health_check_triggers_probe(
    mock_health_coordinator: MagicMock,
    mock_runtime_data: CableModemRuntimeData,
) -> None:
    """Handler refreshes health coordinator when enabled."""
    mock_health_coordinator.async_request_refresh = AsyncMock()

    entry = _make_mock_entry(mock_runtime_data)
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = [entry]

    handler = create_request_health_check_handler(hass)
    call = _make_mock_call()

    await handler(call)

    mock_health_coordinator.async_request_refresh.assert_awaited_once()


async def test_request_health_check_no_health(
    mock_runtime_data: CableModemRuntimeData,
) -> None:
    """Handler skips when health monitoring is disabled."""
    mock_runtime_data.health_coordinator = None

    entry = _make_mock_entry(mock_runtime_data)
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = [entry]

    handler = create_request_health_check_handler(hass)
    call = _make_mock_call()

    # Should not raise — logs warning and returns
    await handler(call)


async def test_request_health_check_no_entries() -> None:
    """Handler returns gracefully when no entries found."""
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = []

    handler = create_request_health_check_handler(hass)
    call = _make_mock_call()

    # Should not raise
    await handler(call)


# -----------------------------------------------------------------------
# _get_entity_prefix
# -----------------------------------------------------------------------


def test_get_entity_prefix() -> None:
    """Entity prefix derived from device name via slugification."""
    entry = MagicMock()
    entry.data = {"entity_prefix": "none", "host": "192.168.100.1"}
    entry.runtime_data.modem_identity.model = "TPS-2000"

    assert _get_entity_prefix(entry) == "cable_modem"


# -----------------------------------------------------------------------
# _find_loaded_entry (singular)
# -----------------------------------------------------------------------


def test_find_loaded_entry_found() -> None:
    """Returns first loaded entry."""
    entry = MagicMock()
    entry.runtime_data = MagicMock()

    hass = MagicMock()
    hass.config_entries.async_entries.return_value = [entry]

    assert _find_loaded_entry(hass) is entry


def test_find_loaded_entry_none() -> None:
    """Returns None when no loaded entries exist."""
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = []

    assert _find_loaded_entry(hass) is None


# -----------------------------------------------------------------------
# _add_channel_graphs — multi-type by_direction
# -----------------------------------------------------------------------


def test_add_channel_graphs_multi_type_by_direction() -> None:
    """Multi-type by-direction uses base title and full labels."""
    parts: list[str] = []
    info = [("qam", 1), ("ofdm", 33)]
    _add_channel_graphs(
        parts,
        info,
        "Downstream Power Levels (dBmV)",
        "sensor.cm_ds_{ch_type}_ch_{ch_id}_power",
        24,
        "auto",
        "by_direction",
        False,
    )
    yaml = "\n".join(parts)
    # Multi-type uses base title (no type prefix)
    assert "Downstream Power Levels (dBmV)" in yaml
    # Auto label becomes "full" for multi-type
    assert "QAM Ch 1" in yaml
    assert "OFDM Ch 33" in yaml


# -----------------------------------------------------------------------
# generate_dashboard service handler
# -----------------------------------------------------------------------


def test_generate_dashboard_handler(
    mock_runtime_data: CableModemRuntimeData,
) -> None:
    """Dashboard handler generates YAML with channel graphs."""
    entry = _make_mock_entry(mock_runtime_data)
    entry.data = {
        "entity_prefix": "none",
        "host": "192.168.100.1",
        "supports_icmp": True,
    }

    hass = MagicMock()
    hass.config_entries.async_entries.return_value = [entry]

    handler = create_generate_dashboard_handler(hass)
    call = MagicMock()
    call.data = {
        "include_downstream_power": True,
        "include_downstream_snr": False,
        "include_downstream_frequency": False,
        "include_upstream_power": True,
        "include_upstream_frequency": False,
        "include_errors": True,
        "include_latency": True,
        "include_status_card": True,
        "graph_hours": 24,
        "short_titles": False,
        "channel_label": "auto",
        "channel_grouping": "by_direction",
    }

    result = handler(call)

    yaml = result["yaml"]
    assert "Cable Modem Dashboard" in yaml
    assert "sensor.cable_modem_status" in yaml
    assert "sensor.cable_modem_ds_qam_ch_1_power" in yaml
    assert "sensor.cable_modem_ds_ofdm_ch_2_power" in yaml
    assert "sensor.cable_modem_us_atdma_ch_1_power" in yaml
    assert "sensor.cable_modem_total_corrected_errors" in yaml
    assert "sensor.cable_modem_http_latency" in yaml


def test_generate_dashboard_no_entry() -> None:
    """Returns error YAML when no config entry loaded."""
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = []

    handler = create_generate_dashboard_handler(hass)
    call = MagicMock()
    call.data = {}

    result = handler(call)
    assert "Error" in result["yaml"]


def test_generate_dashboard_no_snapshot(
    mock_runtime_data: CableModemRuntimeData,
) -> None:
    """Returns error YAML when no modem data available."""
    mock_runtime_data.data_coordinator.data = None  # type: ignore[assignment]

    entry = _make_mock_entry(mock_runtime_data)
    entry.data = {"entity_prefix": "none", "host": "192.168.100.1"}

    hass = MagicMock()
    hass.config_entries.async_entries.return_value = [entry]

    handler = create_generate_dashboard_handler(hass)
    call = MagicMock()
    call.data = {}

    result = handler(call)
    assert "Error" in result["yaml"]


# -----------------------------------------------------------------------
# Service registration / unregistration
# -----------------------------------------------------------------------


def test_register_services() -> None:
    """Registers all three services."""
    hass = MagicMock()
    async_register_services(hass)

    assert hass.services.async_register.call_count == 3
    registered = {call.args[1] for call in hass.services.async_register.call_args_list}
    assert registered == {
        "generate_dashboard",
        "request_refresh",
        "request_health_check",
    }


def test_unregister_services() -> None:
    """Unregisters all three services."""
    hass = MagicMock()
    async_unregister_services(hass)

    assert hass.services.async_remove.call_count == 3
    removed = {call.args[1] for call in hass.services.async_remove.call_args_list}
    assert removed == {
        "generate_dashboard",
        "request_refresh",
        "request_health_check",
    }
