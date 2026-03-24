"""Tests for HNAPParser — channel extraction from delimited strings."""

from __future__ import annotations

from typing import Any

import pytest
from solentlabs.cable_modem_monitor_core.models.parser_config.hnap import HNAPSection
from solentlabs.cable_modem_monitor_core.parsers.formats.hnap import HNAPParser


def _make_config(**overrides: Any) -> HNAPSection:
    """Build a minimal HNAPSection config with overrides."""
    defaults: dict[str, Any] = {
        "format": "hnap",
        "response_key": "GetStatusDownstreamResponse",
        "data_key": "DownstreamChannel",
        "record_delimiter": "|+|",
        "field_delimiter": "^",
        "fields": [
            {"index": 3, "field": "channel_id", "type": "integer"},
            {"index": 4, "field": "frequency", "type": "frequency"},
            {"index": 5, "field": "power", "type": "float"},
            {"index": 6, "field": "snr", "type": "float"},
            {"index": 7, "field": "corrected", "type": "integer"},
            {"index": 8, "field": "uncorrected", "type": "integer"},
        ],
    }
    defaults.update(overrides)
    return HNAPSection(**defaults)


def _make_resources(
    data: str,
    response_key: str = "GetStatusDownstreamResponse",
    data_key: str = "DownstreamChannel",
) -> dict[str, Any]:
    """Build a resource dict with HNAP response data."""
    return {
        "hnap_response": {
            response_key: {
                data_key: data,
            },
        },
    }


class TestBasicExtraction:
    """Test basic channel extraction from delimited strings."""

    def test_single_channel(self) -> None:
        """Extract one channel from a single record."""
        config = _make_config()
        parser = HNAPParser(config)
        resources = _make_resources("1^Locked^QAM256^24^567000000^3.2^41.5^100^5")

        channels = parser.parse(resources)

        assert len(channels) == 1
        ch = channels[0]
        assert ch["channel_id"] == 24
        assert ch["frequency"] == 567000000
        assert ch["power"] == 3.2
        assert ch["snr"] == 41.5
        assert ch["corrected"] == 100
        assert ch["uncorrected"] == 5

    def test_multiple_channels(self) -> None:
        """Extract multiple channels from pipe-delimited records."""
        config = _make_config()
        parser = HNAPParser(config)
        resources = _make_resources(
            "1^Locked^QAM256^24^567000000^3^41^0^0" "|+|" "2^Locked^QAM256^25^573000000^2.5^40^10^1"
        )

        channels = parser.parse(resources)

        assert len(channels) == 2
        assert channels[0]["channel_id"] == 24
        assert channels[1]["channel_id"] == 25

    def test_empty_records_skipped(self) -> None:
        """Empty records between delimiters are skipped."""
        config = _make_config()
        parser = HNAPParser(config)
        resources = _make_resources(
            "1^Locked^QAM256^24^567000000^3^41^0^0" "|+|" "|+|" "2^Locked^QAM256^25^573000000^2.5^40^0^0"
        )

        channels = parser.parse(resources)
        assert len(channels) == 2

    def test_trailing_delimiter(self) -> None:
        """Trailing delimiter doesn't produce an extra channel."""
        config = _make_config()
        parser = HNAPParser(config)
        resources = _make_resources("1^Locked^QAM256^24^567000000^3^41^0^0^|+|")

        channels = parser.parse(resources)
        assert len(channels) == 1


# ┌──────────────────────────────────┬──────────────┬──────────────────────────┐
# │ frequency input                  │ expected_hz  │ description              │
# ├──────────────────────────────────┼──────────────┼──────────────────────────┤
# │ 567000000                        │ 567000000    │ hz unchanged             │
# │ 567                              │ 567000000    │ mhz converted            │
# └──────────────────────────────────┴──────────────┴──────────────────────────┘
#
# fmt: off
FREQUENCY_CASES = [
    # (freq_input,   expected_hz, description)
    ("567000000",    567000000,   "hz unchanged"),
    ("567",          567000000,   "mhz converted"),
]
# fmt: on


@pytest.mark.parametrize(
    "freq_input,expected_hz,desc",
    FREQUENCY_CASES,
    ids=[c[2] for c in FREQUENCY_CASES],
)
def test_frequency_conversion(freq_input: str, expected_hz: int, desc: str) -> None:
    """Verify frequency normalization via type_conversion."""
    config = _make_config()
    parser = HNAPParser(config)
    resources = _make_resources(f"1^Locked^QAM^1^{freq_input}^3^41^0^0")

    channels = parser.parse(resources)
    assert channels[0]["frequency"] == expected_hz


class TestChannelTypeMap:
    """Test map-based channel_type detection."""

    def test_channel_type_from_inline_map(self) -> None:
        """Channel type derived from inline map on channel mapping."""
        config = _make_config(
            fields=[
                {"index": 2, "field": "channel_type", "type": "string", "map": {"QAM256": "qam", "OFDM PLC": "ofdm"}},
                {"index": 3, "field": "channel_id", "type": "integer"},
                {"index": 4, "field": "frequency", "type": "frequency"},
                {"index": 5, "field": "power", "type": "float"},
                {"index": 6, "field": "snr", "type": "float"},
                {"index": 7, "field": "corrected", "type": "integer"},
                {"index": 8, "field": "uncorrected", "type": "integer"},
            ],
        )
        parser = HNAPParser(config)
        resources = _make_resources(
            "1^Locked^QAM256^24^567000000^3^41^0^0" "|+|" "2^Locked^OFDM PLC^33^663000000^1^38^0^0"
        )

        channels = parser.parse(resources)

        assert len(channels) == 2
        assert channels[0]["channel_type"] == "qam"
        assert channels[1]["channel_type"] == "ofdm"

    def test_fixed_channel_type(self) -> None:
        """Fixed channel type applied to all channels."""
        config = _make_config(channel_type={"fixed": "atdma"})
        parser = HNAPParser(config)
        resources = _make_resources("1^Locked^SC-QAM^1^38400000^47^0^0^0")

        channels = parser.parse(resources)
        assert channels[0]["channel_type"] == "atdma"

    def test_unmapped_value_passes_through(self) -> None:
        """Unmapped channel_type value passes through as raw string."""
        config = _make_config(
            fields=[
                {"index": 2, "field": "channel_type", "type": "string", "map": {"QAM256": "qam"}},
                {"index": 3, "field": "channel_id", "type": "integer"},
                {"index": 4, "field": "frequency", "type": "frequency"},
                {"index": 5, "field": "power", "type": "float"},
                {"index": 6, "field": "snr", "type": "float"},
                {"index": 7, "field": "corrected", "type": "integer"},
                {"index": 8, "field": "uncorrected", "type": "integer"},
            ],
        )
        parser = HNAPParser(config)
        resources = _make_resources("1^Locked^UNKNOWN^24^567000000^3^41^0^0")

        channels = parser.parse(resources)

        assert len(channels) == 1
        assert channels[0]["channel_type"] == "UNKNOWN"


class TestFilter:
    """Test filter rules on HNAP channels."""

    def test_filter_excludes_placeholder(self) -> None:
        """Filter with {not: 0} excludes channels with channel_id 0."""
        config = _make_config(filter={"channel_id": {"not": 0}})
        parser = HNAPParser(config)
        resources = _make_resources("1^Locked^QAM^0^0^0^0^0^0" "|+|" "2^Locked^QAM^24^567000000^3^41^0^0")

        channels = parser.parse(resources)

        assert len(channels) == 1
        assert channels[0]["channel_id"] == 24


# ┌──────────────────────────┬──────────────┬──────────────────────────────────┐
# │ resources                │ expected     │ description                      │
# ├──────────────────────────┼──────────────┼──────────────────────────────────┤
# │ {}                       │ []           │ no hnap_response key             │
# │ wrong response_key       │ []           │ response key not found           │
# │ empty data string        │ []           │ empty data                       │
# │ truncated record         │ []           │ too few fields                   │
# └──────────────────────────┴──────────────┴──────────────────────────────────┘
#
_DS = "GetStatusDownstreamResponse"
_DK = "DownstreamChannel"

# fmt: off
MISSING_DATA_CASES: list[tuple[dict[str, Any], list[Any], str]] = [
    # (resources,                                              expected, description)
    ({},                                                       [],       "no hnap_response key"),
    ({"hnap_response": {"WrongKey": {_DK: "x"}}},             [],       "response key not found"),
    ({"hnap_response": {_DS: {_DK: ""}}},                      [],       "empty data string"),
    ({"hnap_response": {_DS: {_DK: "1^Locked^QAM^24"}}},      [],       "truncated record"),
]
# fmt: on


@pytest.mark.parametrize(
    "resources,expected,desc",
    MISSING_DATA_CASES,
    ids=[c[2] for c in MISSING_DATA_CASES],
)
def test_missing_data(resources: dict, expected: list, desc: str) -> None:
    """Verify graceful handling of missing or malformed data."""
    config = _make_config()
    parser = HNAPParser(config)
    assert parser.parse(resources) == expected


class TestUpstreamSection:
    """Test upstream-style config with different field mappings."""

    def test_upstream_with_symbol_rate(self) -> None:
        """Upstream channels with symbol_rate field."""
        config = _make_config(
            response_key="GetStatusUpstreamResponse",
            data_key="UpstreamChannel",
            fields=[
                {"index": 2, "field": "channel_type", "type": "string", "map": {"SC-QAM": "atdma", "OFDMA": "ofdma"}},
                {"index": 3, "field": "channel_id", "type": "integer"},
                {"index": 4, "field": "symbol_rate", "type": "integer"},
                {"index": 5, "field": "frequency", "type": "frequency"},
                {"index": 6, "field": "power", "type": "float"},
            ],
        )
        parser = HNAPParser(config)
        resources = _make_resources(
            "1^Locked^SC-QAM^1^6400000^38400000^47.0" "|+|" "5^Locked^OFDMA^9^34000000^41800000^42.5",
            response_key="GetStatusUpstreamResponse",
            data_key="UpstreamChannel",
        )

        channels = parser.parse(resources)

        assert len(channels) == 2
        assert channels[0]["channel_id"] == 1
        assert channels[0]["channel_type"] == "atdma"
        assert channels[0]["symbol_rate"] == 6400000
        assert channels[0]["frequency"] == 38400000
        assert channels[0]["power"] == 47.0
        assert channels[1]["channel_type"] == "ofdma"


# ┌─────────────────┬──────────────────────────────────┬──────────┬───────────────────────────┐
# │ raw_value       │ map_config                       │ expected │ description               │
# ├─────────────────┼──────────────────────────────────┼──────────┼───────────────────────────┤
# │ "SC-QAM"        │ {"SC-QAM": "qam", "OFDM": ...}   │ "qam"    │ mapped value              │
# │ "OFDM"          │ {"SC-QAM": "qam", "OFDM": ...}   │ "ofdm"   │ second map entry          │
# │ "UNKNOWN"       │ {"SC-QAM": "qam"}                │ "UNKNOWN"│ unmatched passes through  │
# └─────────────────┴──────────────────────────────────┴──────────┴───────────────────────────┘
#
# fmt: off
FIELD_LEVEL_MAP_CASES = [
    # (raw_value,  map_config,                              expected,  description)
    ("SC-QAM",     {"SC-QAM": "qam", "OFDM": "ofdm"},      "qam",     "mapped value"),
    ("OFDM",       {"SC-QAM": "qam", "OFDM": "ofdm"},      "ofdm",    "second map entry"),
    ("UNKNOWN",    {"SC-QAM": "qam"},                        "UNKNOWN", "unmatched passes through"),
]
# fmt: on


@pytest.mark.parametrize(
    "raw_value,map_config,expected,desc",
    FIELD_LEVEL_MAP_CASES,
    ids=[c[3] for c in FIELD_LEVEL_MAP_CASES],
)
def test_field_level_map(raw_value: str, map_config: dict, expected: str, desc: str) -> None:
    """Test map attribute on ChannelMapping normalizes extracted values."""
    config = _make_config(
        fields=[
            {"index": 3, "field": "channel_id", "type": "integer"},
            {"index": 2, "field": "channel_type", "type": "string", "map": map_config},
        ],
    )
    parser = HNAPParser(config)
    resources = _make_resources(f"1^Locked^{raw_value}^24^567000000^3^41^0^0")

    channels = parser.parse(resources)

    assert len(channels) == 1
    assert channels[0]["channel_type"] == expected
