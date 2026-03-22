"""Tests for restart-window data quality filter."""

from __future__ import annotations

import pytest
from solentlabs.cable_modem_monitor_core.parsers.coordinator import (
    filter_restart_window,
)

# ┌───────────────────┬────────┬──────────┬────────────────────────────────┐
# │ uptime            │ window │ filtered │ description                    │
# ├───────────────────┼────────┼──────────┼────────────────────────────────┤
# │ 60                │ 300    │ yes      │ inside window                  │
# │ 300               │ 300    │ no       │ at boundary                    │
# │ 600               │ 300    │ no       │ outside window                 │
# │ None              │ 300    │ no       │ no uptime available            │
# │ "invalid"         │ 300    │ no       │ non-numeric uptime             │
# └───────────────────┴────────┴──────────┴────────────────────────────────┘
#
# fmt: off
FILTER_CASES = [
    (60,        300, True,  "inside window — zero-power channels removed"),
    (300,       300, False, "at boundary — not filtered"),
    (600,       300, False, "outside window — not filtered"),
    (None,      300, False, "no uptime — not filtered"),
    ("invalid", 300, False, "non-numeric uptime — not filtered"),
]
# fmt: on


def _make_data(uptime: object) -> dict:
    """Build sample ModemData with a mix of zero and non-zero power channels."""
    data: dict = {
        "downstream": [
            {"channel": 1, "power": 5.0},
            {"channel": 2, "power": 0},
            {"channel": 3, "power": 3.0},
        ],
        "upstream": [
            {"channel": 1, "power": 10.0},
            {"channel": 2, "power": 0},
        ],
    }
    if uptime is not None:
        data["system_info"] = {"system_uptime": uptime}
    return data


class TestFilterRestartWindow:
    """filter_restart_window removes zero-power channels during reboot."""

    @pytest.mark.parametrize(
        "uptime,window,should_filter,desc",
        FILTER_CASES,
        ids=[c[3] for c in FILTER_CASES],
    )
    def test_filter_behavior(
        self,
        uptime: object,
        window: int,
        should_filter: bool,
        desc: str,  # noqa: ARG002
    ) -> None:
        """Verify filtering based on uptime vs restart window."""
        data = _make_data(uptime)
        result = filter_restart_window(data, window)

        if should_filter:
            # Zero-power channels removed
            assert len(result["downstream"]) == 2
            assert all(ch["power"] != 0 for ch in result["downstream"])
            assert len(result["upstream"]) == 1
            assert all(ch["power"] != 0 for ch in result["upstream"])
        else:
            # Original data unchanged
            assert len(result["downstream"]) == 3
            assert len(result["upstream"]) == 2

    def test_no_system_info_section(self) -> None:
        """Data without system_info section is returned unmodified."""
        data = {
            "downstream": [{"channel": 1, "power": 0}],
            "upstream": [],
        }
        result = filter_restart_window(data, 300)
        assert len(result["downstream"]) == 1

    def test_all_zero_power_removed(self) -> None:
        """All channels removed when all have zero power during restart."""
        data = {
            "downstream": [{"channel": 1, "power": 0}, {"channel": 2, "power": 0}],
            "upstream": [{"channel": 1, "power": 0}],
            "system_info": {"system_uptime": 30},
        }
        result = filter_restart_window(data, 300)
        assert result["downstream"] == []
        assert result["upstream"] == []
