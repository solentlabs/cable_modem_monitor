"""Tests for metrics field computation.

Table-driven tests for compute_metrics() covering direction scope,
type-qualified scope, missing fields, empty channels, and no config.

See MODEM_YAML_SPEC.md Aggregate section.
"""

from __future__ import annotations

from typing import Any

import pytest
from solentlabs.cable_modem_monitor_core.models.modem_config.metadata import (
    AggregateField,
)
from solentlabs.cable_modem_monitor_core.orchestration.metrics import (
    compute_metrics,
)

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_modem_data(
    *,
    downstream: list[dict[str, Any]] | None = None,
    upstream: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a minimal ModemData dict for aggregate tests."""
    return {
        "downstream": downstream or [],
        "upstream": upstream or [],
        "system_info": {},
    }


def _agg(sum_field: str, channels: str) -> AggregateField:
    """Shorthand for AggregateField."""
    return AggregateField(sum=sum_field, channels=channels)


# ------------------------------------------------------------------
# Table-driven: scope and field combinations
# ------------------------------------------------------------------


# ┌──────────────────┬──────────────┬──────────────┬──────────┬────────────┐
# │ Config           │ DS channels  │ US channels  │ Expected │ Desc       │
# ├──────────────────┼──────────────┼──────────────┼──────────┼────────────┤
# │ sum:corrected    │ [100, 200]   │ —            │ 300      │ basic sum  │
# │ channels:ds      │              │              │          │            │
# ├──────────────────┼──────────────┼──────────────┼──────────┼────────────┤
# │ sum:corrected    │ —            │ [50, 75]     │ 125      │ upstream   │
# │ channels:us      │              │              │          │            │
# ├──────────────────┼──────────────┼──────────────┼──────────┼────────────┤
# │ sum:corrected    │ qam:100,     │ —            │ 100      │ type-      │
# │ channels:ds.qam  │ ofdm:200     │              │          │ qualified  │
# ├──────────────────┼──────────────┼──────────────┼──────────┼────────────┤
# │ sum:missing      │ [100, 200]   │ —            │ {}       │ field      │
# │ channels:ds      │              │              │          │ absent     │
# ├──────────────────┼──────────────┼──────────────┼──────────┼────────────┤
# │ sum:corrected    │ []           │ —            │ {}       │ no         │
# │ channels:ds      │              │              │          │ channels   │
# └──────────────────┴──────────────┴──────────────┴──────────┴────────────┘
#
AGGREGATE_CASES = [
    pytest.param(
        {"total_corrected": _agg("corrected", "downstream")},
        _make_modem_data(downstream=[{"corrected": 100}, {"corrected": 200}]),
        {"total_corrected": 300},
        id="downstream sum",
    ),
    pytest.param(
        {"total_corrected": _agg("corrected", "upstream")},
        _make_modem_data(upstream=[{"corrected": 50}, {"corrected": 75}]),
        {"total_corrected": 125},
        id="upstream sum",
    ),
    pytest.param(
        {"total_corrected": _agg("corrected", "downstream.qam")},
        _make_modem_data(
            downstream=[
                {"corrected": 100, "channel_type": "qam"},
                {"corrected": 200, "channel_type": "ofdm"},
            ]
        ),
        {"total_corrected": 100},
        id="type-qualified scope",
    ),
    pytest.param(
        {"total_corrected": _agg("missing_field", "downstream")},
        _make_modem_data(downstream=[{"corrected": 100}, {"corrected": 200}]),
        {},
        id="field absent on all channels",
    ),
    pytest.param(
        {"total_corrected": _agg("corrected", "downstream")},
        _make_modem_data(),
        {},
        id="no channels",
    ),
    pytest.param(
        {},
        _make_modem_data(downstream=[{"corrected": 100}]),
        {},
        id="no aggregate config",
    ),
]


@pytest.mark.parametrize(
    "aggregate_config,modem_data,expected",
    AGGREGATE_CASES,
)
def test_compute_metrics(
    aggregate_config: dict[str, AggregateField],
    modem_data: dict[str, Any],
    expected: dict[str, int | float],
) -> None:
    """Each aggregate config produces the expected result."""
    result = compute_metrics(modem_data, aggregate_config)
    assert result == expected


# ------------------------------------------------------------------
# Behavioral tests
# ------------------------------------------------------------------


class TestAggregateEdgeCases:
    """Edge cases for aggregate computation."""

    def test_partial_field_presence(self) -> None:
        """Channels missing the field are skipped, present ones summed."""
        config = {"total": _agg("corrected", "downstream")}
        data = _make_modem_data(
            downstream=[
                {"corrected": 100},
                {"other_field": 50},
                {"corrected": 200},
            ]
        )

        result = compute_metrics(data, config)

        assert result == {"total": 300}

    def test_multiple_aggregates(self) -> None:
        """Multiple aggregate fields computed independently."""
        config = {
            "total_corrected": _agg("corrected", "downstream"),
            "total_uncorrected": _agg("uncorrected", "downstream"),
        }
        data = _make_modem_data(
            downstream=[
                {"corrected": 100, "uncorrected": 5},
                {"corrected": 200, "uncorrected": 10},
            ]
        )

        result = compute_metrics(data, config)

        assert result == {"total_corrected": 300, "total_uncorrected": 15}

    def test_zero_values_summed(self) -> None:
        """Fields with value 0 are included (not skipped)."""
        config = {"total": _agg("corrected", "downstream")}
        data = _make_modem_data(downstream=[{"corrected": 0}, {"corrected": 0}])

        result = compute_metrics(data, config)

        assert result == {"total": 0}

    def test_float_values(self) -> None:
        """Float fields are summed correctly."""
        config = {"total_power": _agg("power", "downstream")}
        data = _make_modem_data(downstream=[{"power": 1.5}, {"power": 2.5}])

        result = compute_metrics(data, config)

        assert result == {"total_power": 4.0}

    def test_upstream_type_qualified(self) -> None:
        """Type-qualified upstream scope works."""
        config = {"total": _agg("corrected", "upstream.atdma")}
        data = _make_modem_data(
            upstream=[
                {"corrected": 10, "channel_type": "atdma"},
                {"corrected": 20, "channel_type": "ofdma"},
                {"corrected": 30, "channel_type": "atdma"},
            ]
        )

        result = compute_metrics(data, config)

        assert result == {"total": 40}
