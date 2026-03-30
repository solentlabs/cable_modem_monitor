"""Tests for the services module — YAML builders and channel helpers.

Most functions are pure (no I/O), tested via table-driven patterns.
The service handler test mocks runtime_data.
"""

from __future__ import annotations

from typing import Any

import pytest

from custom_components.cable_modem_monitor.services import (
    _add_channel_graphs,
    _build_channel_graph_yaml,
    _build_error_graphs_yaml,
    _build_latency_graph_yaml,
    _build_status_card_yaml,
    _format_channel_label,
    _format_title_with_type,
    _get_channel_info,
    _get_dashboard_titles,
    _group_by_type,
    _unique_types,
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


def test_build_status_card_yaml_with_icmp_and_restart():
    """Status card includes ICMP ping and restart button."""
    lines = _build_status_card_yaml("cable_modem", has_icmp=True, has_restart=True)
    yaml = "\n".join(lines)
    assert "sensor.cable_modem_status" in yaml
    assert "sensor.cable_modem_ping_latency" in yaml
    assert "button.cable_modem_restart_modem" in yaml


def test_build_status_card_yaml_no_icmp_no_restart():
    """Status card omits ICMP and restart when not available."""
    lines = _build_status_card_yaml("cable_modem", has_icmp=False, has_restart=False)
    yaml = "\n".join(lines)
    assert "ping_latency" not in yaml
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
