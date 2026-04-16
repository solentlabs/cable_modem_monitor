"""Tests for the channel mapping manager.

The mapping manager translates Core's channel list into keyed entity
slots based on the user's channel identity mode.  It is a pure module
(no HA imports) — all tests are synchronous.

Channel data lives in JSON fixture files under ``tests/fixtures/channels/``.
Add a file to add a test case.

See CHANNEL_IDENTIFICATION_SPEC.md § 5, § 10.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from custom_components.cable_modem_monitor.const import ChannelIdentity
from custom_components.cable_modem_monitor.mapping_manager import (
    ChannelMap,
    build_channel_map,
)

# -----------------------------------------------------------------------
# Fixture loading
# -----------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "channels"


def _load(name: str) -> list[dict[str, Any]]:
    """Load a channel fixture by filename (without path)."""
    return json.loads((FIXTURES_DIR / name).read_text())


@pytest.fixture
def ds_locked() -> list[dict[str, Any]]:
    return _load("ds_locked.json")


@pytest.fixture
def us_locked() -> list[dict[str, Any]]:
    return _load("us_locked.json")


@pytest.fixture
def ds_with_unlocked() -> list[dict[str, Any]]:
    return _load("ds_with_unlocked.json")


@pytest.fixture
def ds_all_unlocked() -> list[dict[str, Any]]:
    return _load("ds_all_unlocked.json")


# -----------------------------------------------------------------------
# build_channel_map — position mode ("number")
# -----------------------------------------------------------------------


class TestPositionMode:
    """Position mode: slots keyed by channel_number, all positions included."""

    def test_locked_channels_keyed_by_number(self, ds_locked, us_locked) -> None:
        """All locked channels appear keyed by channel_number."""
        result = build_channel_map(ds_locked, us_locked, ChannelIdentity.NUMBER)
        assert set(result.downstream.keys()) == {1, 2}
        assert set(result.upstream.keys()) == {1}

    def test_channel_data_preserved(self, ds_locked, us_locked) -> None:
        """Locked channel data passes through unchanged."""
        result = build_channel_map(ds_locked, us_locked, ChannelIdentity.NUMBER)
        ch = result.downstream[1]
        assert ch["power"] == 2.5
        assert ch["channel_id"] == 29
        assert ch["channel_type"] == "qam"

    def test_unlocked_included_with_null_metrics(self, ds_with_unlocked) -> None:
        """Unlocked positions are included with only channel_number and lock_status."""
        result = build_channel_map(ds_with_unlocked, [], ChannelIdentity.NUMBER)
        assert set(result.downstream.keys()) == {1, 2, 3}

        unlocked = result.downstream[2]
        assert unlocked["channel_number"] == 2
        assert unlocked["lock_status"] == "not_locked"
        assert unlocked["power"] is None
        assert unlocked["snr"] is None
        assert unlocked["channel_id"] is None
        assert unlocked["channel_type"] is None

    def test_unlocked_preserves_locked_neighbors(self, ds_with_unlocked) -> None:
        """Locked channels next to unlocked ones are not affected."""
        result = build_channel_map(ds_with_unlocked, [], ChannelIdentity.NUMBER)
        assert result.downstream[1]["power"] == 2.5
        assert result.downstream[1]["channel_id"] == 29
        assert result.downstream[3]["power"] == -0.5
        assert result.downstream[3]["channel_id"] == 31

    def test_empty_channels(self) -> None:
        """Empty channel lists produce empty channel map."""
        result = build_channel_map([], [], ChannelIdentity.NUMBER)
        assert result.downstream == {}
        assert result.upstream == {}

    def test_returns_channel_map_type(self, ds_locked, us_locked) -> None:
        """build_channel_map returns a ChannelMap instance."""
        result = build_channel_map(ds_locked, us_locked, ChannelIdentity.NUMBER)
        assert isinstance(result, ChannelMap)


# -----------------------------------------------------------------------
# build_channel_map — ID mode ("id")
# -----------------------------------------------------------------------


class TestIdMode:
    """ID mode: slots keyed by (channel_type, channel_id), unlocked excluded."""

    def test_locked_channels_keyed_by_type_and_id(self, ds_locked, us_locked) -> None:
        """Locked channels keyed by (channel_type, channel_id) tuple."""
        result = build_channel_map(ds_locked, us_locked, ChannelIdentity.ID)
        assert set(result.downstream.keys()) == {("qam", 29), ("ofdm", 30)}
        assert set(result.upstream.keys()) == {("atdma", 5)}

    def test_channel_data_preserved(self, ds_locked, us_locked) -> None:
        """Channel data passes through unchanged in ID mode."""
        result = build_channel_map(ds_locked, us_locked, ChannelIdentity.ID)
        ch = result.downstream[("qam", 29)]
        assert ch["power"] == 2.5
        assert ch["channel_number"] == 1

    def test_unlocked_excluded(self, ds_with_unlocked) -> None:
        """Unlocked channels are excluded in ID mode (no valid key)."""
        result = build_channel_map(ds_with_unlocked, [], ChannelIdentity.ID)
        assert set(result.downstream.keys()) == {("qam", 29), ("ofdm", 31)}

    def test_missing_channel_id_excluded(self) -> None:
        """Channels without channel_id are excluded in ID mode."""
        channels = [{"channel_number": 1, "channel_type": "qam", "lock_status": "locked", "power": 1.0}]
        result = build_channel_map(channels, [], ChannelIdentity.ID)
        assert result.downstream == {}

    def test_missing_channel_type_excluded(self) -> None:
        """Channels missing channel_type are excluded (no valid key component)."""
        channels = [{"channel_number": 1, "channel_id": 5, "lock_status": "locked", "power": 1.0}]
        result = build_channel_map(channels, [], ChannelIdentity.ID)
        assert result.downstream == {}

    def test_empty_channels(self) -> None:
        """Empty channel lists produce empty channel map."""
        result = build_channel_map([], [], ChannelIdentity.ID)
        assert result.downstream == {}
        assert result.upstream == {}


# -----------------------------------------------------------------------
# Edge cases — both modes
# -----------------------------------------------------------------------

# ┌────────────────────────────────┬───────────┬───────────────────────────────┐
# │ scenario                       │ mode      │ expected                      │
# ├────────────────────────────────┼───────────┼───────────────────────────────┤
# │ all_unlocked_position          │ number    │ all slots present, all nulled │
# │ all_unlocked_id                │ id        │ empty (all excluded)          │
# │ upstream_position              │ number    │ keyed by channel_number       │
# │ upstream_id                    │ id        │ keyed by (type, id)           │
# └────────────────────────────────┴───────────┴───────────────────────────────┘


class TestEdgeCases:
    """Edge cases spanning both identity modes."""

    def test_all_unlocked_position_mode(self, ds_all_unlocked) -> None:
        """Position mode: all unlocked channels present with nulled metrics."""
        result = build_channel_map(ds_all_unlocked, [], ChannelIdentity.NUMBER)
        assert set(result.downstream.keys()) == {1, 2}
        for slot in result.downstream.values():
            assert slot["power"] is None
            assert slot["lock_status"] == "not_locked"

    def test_all_unlocked_id_mode(self, ds_all_unlocked) -> None:
        """ID mode: all unlocked channels excluded -> empty."""
        result = build_channel_map(ds_all_unlocked, [], ChannelIdentity.ID)
        assert result.downstream == {}

    def test_upstream_position_mode(self, us_locked) -> None:
        """Upstream channels keyed by channel_number in position mode."""
        result = build_channel_map([], us_locked, ChannelIdentity.NUMBER)
        assert set(result.upstream.keys()) == {1}
        assert result.upstream[1]["power"] == 42.0

    def test_upstream_id_mode(self, us_locked) -> None:
        """Upstream channels keyed by (type, id) in ID mode."""
        result = build_channel_map([], us_locked, ChannelIdentity.ID)
        assert set(result.upstream.keys()) == {("atdma", 5)}
        assert result.upstream[("atdma", 5)]["power"] == 42.0
