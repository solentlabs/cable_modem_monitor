"""Tests for ParseDiagnostics and AnchorCount.

Behavioral tests inline (table-driven). The dataclasses are small and
pure — no fixtures needed.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from solentlabs.cable_modem_monitor_core.parsers.diagnostics import (
    AnchorCount,
    ParseDiagnostics,
)

# ---------------------------------------------------------------------------
# AnchorCount
# ---------------------------------------------------------------------------


def test_anchor_count_defaults_to_zero() -> None:
    count = AnchorCount()
    assert count.expected == 0
    assert count.fulfilled == 0


def test_anchor_count_addition_aggregates_per_resource() -> None:
    """Two sections sharing a resource → counts sum."""
    downstream = AnchorCount(expected=2, fulfilled=2)
    upstream = AnchorCount(expected=1, fulfilled=0)

    total = downstream + upstream

    assert total.expected == 3
    assert total.fulfilled == 2


def test_anchor_count_is_immutable() -> None:
    count = AnchorCount(expected=4, fulfilled=4)
    with pytest.raises(FrozenInstanceError):
        count.fulfilled = 0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ParseDiagnostics — has_zero_fulfillment
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,by_resource,expected_zero_fulfillment",
    [
        (
            "happy_full_fulfillment",
            {"/status.html": AnchorCount(expected=4, fulfilled=4)},
            False,
        ),
        (
            "partial_fulfillment_firmware_variant",
            {"/status.html": AnchorCount(expected=4, fulfilled=2)},
            False,
        ),
        (
            "stub_zero_fulfillment_single_resource",
            {"/status.html": AnchorCount(expected=4, fulfilled=0)},
            True,
        ),
        (
            "stub_zero_fulfillment_one_of_many",
            {
                "/status.html": AnchorCount(expected=4, fulfilled=4),
                "/router.html": AnchorCount(expected=2, fulfilled=0),
            },
            True,
        ),
        (
            "no_anchors_declared",
            {"/static.html": AnchorCount(expected=0, fulfilled=0)},
            False,
        ),
        (
            "empty_diagnostics",
            {},
            False,
        ),
    ],
)
def test_has_zero_fulfillment(
    name: str,
    by_resource: dict[str, AnchorCount],
    expected_zero_fulfillment: bool,
) -> None:
    diagnostics = ParseDiagnostics(by_resource=by_resource)
    assert diagnostics.has_zero_fulfillment is expected_zero_fulfillment


def test_zero_fulfillment_resources_lists_affected_paths() -> None:
    diagnostics = ParseDiagnostics(
        by_resource={
            "/ok.html": AnchorCount(expected=2, fulfilled=2),
            "/stub_a.html": AnchorCount(expected=4, fulfilled=0),
            "/partial.html": AnchorCount(expected=3, fulfilled=1),
            "/stub_b.html": AnchorCount(expected=1, fulfilled=0),
        }
    )

    affected = diagnostics.zero_fulfillment_resources

    assert sorted(affected) == ["/stub_a.html", "/stub_b.html"]


def test_no_anchors_declared_is_not_zero_fulfillment() -> None:
    """expected=0 with fulfilled=0 is not stub detection — nothing was
    expected, so absence is not a failure signal."""
    diagnostics = ParseDiagnostics(by_resource={"/no_anchors.html": AnchorCount(expected=0, fulfilled=0)})
    assert diagnostics.has_zero_fulfillment is False
    assert diagnostics.zero_fulfillment_resources == []
