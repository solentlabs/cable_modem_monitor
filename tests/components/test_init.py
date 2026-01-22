"""Tests for __init__.py helper functions."""

import pytest

from custom_components.cable_modem_monitor import (
    _extract_channel_id,
    _normalize_channel_type,
    _normalize_channels,
)


class TestNormalizeChannelType:
    """Tests for _normalize_channel_type function."""

    # Downstream QAM cases
    def test_downstream_qam_from_channel_type(self):
        """QAM downstream with explicit channel_type."""
        channel = {"channel_type": "qam", "modulation": "QAM256"}
        assert _normalize_channel_type(channel, "downstream") == "qam"

    def test_downstream_qam_from_modulation_only(self):
        """QAM downstream with only modulation field."""
        channel = {"modulation": "QAM256"}
        assert _normalize_channel_type(channel, "downstream") == "qam"

    def test_downstream_qam_default(self):
        """QAM downstream when no type info provided."""
        channel = {"frequency": 765000000}
        assert _normalize_channel_type(channel, "downstream") == "qam"

    # Downstream OFDM cases
    def test_downstream_ofdm_from_channel_type(self):
        """OFDM downstream with explicit channel_type."""
        channel = {"channel_type": "ofdm", "modulation": "OFDM"}
        assert _normalize_channel_type(channel, "downstream") == "ofdm"

    def test_downstream_ofdm_from_modulation(self):
        """OFDM downstream detected from modulation field."""
        channel = {"modulation": "OFDM"}
        assert _normalize_channel_type(channel, "downstream") == "ofdm"

    def test_downstream_ofdm_from_is_ofdm_flag(self):
        """OFDM downstream detected from is_ofdm flag."""
        channel = {"is_ofdm": True}
        assert _normalize_channel_type(channel, "downstream") == "ofdm"

    # Upstream ATDMA cases
    def test_upstream_atdma_from_channel_type(self):
        """ATDMA upstream with explicit channel_type from modem."""
        channel = {"channel_type": "ATDMA", "symbol_rate": 5120}
        assert _normalize_channel_type(channel, "upstream") == "atdma"

    def test_upstream_atdma_from_channel_type_lowercase(self):
        """ATDMA upstream with lowercase channel_type."""
        channel = {"channel_type": "atdma"}
        assert _normalize_channel_type(channel, "upstream") == "atdma"

    def test_upstream_atdma_default(self):
        """ATDMA upstream when no type info provided."""
        channel = {"frequency": 13200000}
        assert _normalize_channel_type(channel, "upstream") == "atdma"

    # Upstream OFDMA cases - these were failing before the fix!
    def test_upstream_ofdma_from_channel_type(self):
        """OFDMA upstream with explicit channel_type from modem.

        This was the bug: some modems output channel_type='OFDMA' but the old
        code only checked modulation field, causing OFDMA to be classified as ATDMA.
        """
        channel = {"channel_type": "OFDMA", "is_ofdm": True}
        assert _normalize_channel_type(channel, "upstream") == "ofdma"

    def test_upstream_ofdma_from_channel_type_lowercase(self):
        """OFDMA upstream with lowercase channel_type."""
        channel = {"channel_type": "ofdma"}
        assert _normalize_channel_type(channel, "upstream") == "ofdma"

    def test_upstream_ofdma_from_modulation(self):
        """OFDMA upstream detected from modulation field."""
        channel = {"modulation": "OFDMA"}
        assert _normalize_channel_type(channel, "upstream") == "ofdma"

    def test_upstream_ofdma_from_is_ofdm_flag(self):
        """OFDMA upstream detected from is_ofdm flag."""
        channel = {"is_ofdm": True}
        assert _normalize_channel_type(channel, "upstream") == "ofdma"

    # Edge cases
    def test_empty_channel(self):
        """Empty channel defaults correctly."""
        assert _normalize_channel_type({}, "downstream") == "qam"
        assert _normalize_channel_type({}, "upstream") == "atdma"

    def test_case_insensitivity(self):
        """Channel type matching is case-insensitive."""
        assert _normalize_channel_type({"channel_type": "OFDM"}, "downstream") == "ofdm"
        assert _normalize_channel_type({"channel_type": "Ofdma"}, "upstream") == "ofdma"


class TestExtractChannelId:
    """Tests for _extract_channel_id function.

    This function handles both numeric IDs ("1", "32") and prefixed IDs
    like "OFDM-0" from the G54 parser.
    """

    # Numeric channel IDs (most modems)
    def test_numeric_string(self):
        """Numeric string channel ID."""
        assert _extract_channel_id({"channel_id": "1"}, 99) == 1
        assert _extract_channel_id({"channel_id": "32"}, 99) == 32

    def test_numeric_int(self):
        """Integer channel ID (already numeric)."""
        assert _extract_channel_id({"channel_id": 1}, 99) == 1
        assert _extract_channel_id({"channel_id": 32}, 99) == 32

    def test_channel_field_fallback(self):
        """Falls back to 'channel' field if 'channel_id' missing."""
        assert _extract_channel_id({"channel": "5"}, 99) == 5
        assert _extract_channel_id({"channel": 10}, 99) == 10

    # Prefixed channel IDs (G54 parser style)
    def test_ofdm_prefix(self):
        """OFDM-prefixed channel ID from G54 parser."""
        assert _extract_channel_id({"channel_id": "OFDM-0"}, 99) == 0
        assert _extract_channel_id({"channel_id": "OFDM-1"}, 99) == 1

    def test_ofdma_prefix(self):
        """OFDMA-prefixed channel ID from G54 parser."""
        assert _extract_channel_id({"channel_id": "OFDMA-0"}, 99) == 0
        assert _extract_channel_id({"channel_id": "OFDMA-1"}, 99) == 1

    def test_other_prefixes(self):
        """Other prefixed formats should also work."""
        assert _extract_channel_id({"channel_id": "CH-5"}, 99) == 5
        assert _extract_channel_id({"channel_id": "DS-10"}, 99) == 10

    # Default fallback cases
    def test_missing_channel_id(self):
        """Returns default when no channel_id or channel field."""
        assert _extract_channel_id({}, 99) == 99
        assert _extract_channel_id({"frequency": 765000000}, 42) == 42

    def test_unparseable_string(self):
        """Returns default for unparseable strings."""
        assert _extract_channel_id({"channel_id": "invalid"}, 99) == 99
        assert _extract_channel_id({"channel_id": ""}, 99) == 99

    def test_none_value(self):
        """Returns default when channel_id is None."""
        assert _extract_channel_id({"channel_id": None}, 99) == 99

    # Edge cases
    def test_whitespace_handling(self):
        """Handles whitespace in channel IDs."""
        assert _extract_channel_id({"channel_id": " 5 "}, 99) == 5
        assert _extract_channel_id({"channel_id": " OFDM-2 "}, 99) == 2


# ┌─────────────────────────────────────────────────────────────────────────────┐
# │ _normalize_channels test data                                               │
# ├────────────────┬────────────────────┬───────────────────────────────────────┤
# │ channel_id     │ expected_type      │ description                           │
# ├────────────────┼────────────────────┼───────────────────────────────────────┤
# │ "1"            │ qam                │ Standard QAM channel                  │
# │ "OFDM-0"       │ ofdm               │ G54-style OFDM channel                │
# │ "OFDMA-1"      │ ofdma              │ G54-style OFDMA channel               │
# └────────────────┴────────────────────┴───────────────────────────────────────┘
#
# fmt: off
NORMALIZE_CHANNELS_DOWNSTREAM_CASES = [
    # (channels, expected_keys, description)
    (
        [{"channel_id": "1", "frequency": 765000000, "modulation": "QAM256"}],
        [("qam", 1)],
        "single QAM channel",
    ),
    (
        [
            {"channel_id": "1", "frequency": 765000000, "modulation": "QAM256"},
            {"channel_id": "2", "frequency": 771000000, "modulation": "QAM256"},
        ],
        [("qam", 1), ("qam", 2)],
        "multiple QAM channels",
    ),
    (
        [{"channel_id": "OFDM-0", "frequency": 800000000, "is_ofdm": True}],
        [("ofdm", 0)],
        "G54-style OFDM channel",
    ),
    (
        [
            {"channel_id": "1", "frequency": 765000000, "modulation": "QAM256"},
            {"channel_id": "OFDM-0", "frequency": 800000000, "is_ofdm": True},
        ],
        [("qam", 1), ("ofdm", 0)],
        "mixed QAM and OFDM channels",
    ),
]
# fmt: on


class TestNormalizeChannels:
    """Tests for _normalize_channels function.

    Verifies that channels are correctly grouped by type and indexed,
    including support for G54-style OFDM channel IDs.
    """

    @pytest.mark.parametrize("channels,expected_keys,desc", NORMALIZE_CHANNELS_DOWNSTREAM_CASES)
    def test_downstream_normalization(self, channels, expected_keys, desc):
        """Test downstream channel normalization."""
        result = _normalize_channels(channels, "downstream")
        assert sorted(result.keys()) == sorted(expected_keys), f"Failed: {desc}"

    def test_upstream_ofdma_channels(self):
        """Test upstream OFDMA channel normalization (G54-style)."""
        channels = [
            {"channel_id": "1", "frequency": 13200000, "channel_type": "ATDMA"},
            {"channel_id": "OFDMA-0", "frequency": 50000000, "is_ofdm": True},
        ]
        result = _normalize_channels(channels, "upstream")
        assert ("atdma", 1) in result
        assert ("ofdma", 0) in result

    def test_channels_sorted_by_frequency(self):
        """Channels within a type are sorted by frequency."""
        channels = [
            {"channel_id": "2", "frequency": 800000000, "modulation": "QAM256"},
            {"channel_id": "1", "frequency": 765000000, "modulation": "QAM256"},
            {"channel_id": "3", "frequency": 850000000, "modulation": "QAM256"},
        ]
        result = _normalize_channels(channels, "downstream")

        # Check that _index reflects frequency order
        assert result[("qam", 1)]["_index"] == 1  # lowest freq
        assert result[("qam", 2)]["_index"] == 2  # middle freq
        assert result[("qam", 3)]["_index"] == 3  # highest freq

    def test_empty_channels(self):
        """Empty channel list returns empty dict."""
        assert _normalize_channels([], "downstream") == {}
        assert _normalize_channels([], "upstream") == {}
