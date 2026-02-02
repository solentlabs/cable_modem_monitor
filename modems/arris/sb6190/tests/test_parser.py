"""Tests for the Arris SB6190 parser."""

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.discovery_helpers import HintMatcher
from modems.arris.sb6190.parser import ArrisSB6190Parser
from tests.fixtures import load_fixture


@pytest.fixture
def arris_signal_html():
    """Load SB6190 status page fixture."""
    return load_fixture("arris", "sb6190", "cgi-bin/status")


def test_parser_detection(arris_signal_html):
    """Test that the Arris SB6190 parser detects the modem via HintMatcher."""
    hint_matcher = HintMatcher.get_instance()
    matches = hint_matcher.match_login_markers(arris_signal_html)
    assert any(m.parser_name == "ArrisSB6190Parser" for m in matches)


def test_parsing_downstream(arris_signal_html):
    """Test parsing of Arris SB6141 downstream data."""
    parser = ArrisSB6190Parser()
    soup = BeautifulSoup(arris_signal_html, "html.parser")
    data = parser.parse(soup)

    # Verify downstream channels (8 channels in fixture)
    assert "downstream" in data
    assert len(data["downstream"]) == 32

    # Check first downstream channel
    first_ds = data["downstream"][0]
    assert first_ds["channel_id"] == "1"
    assert first_ds["frequency"] == 669000000  # 669.00 MHz in Hz
    assert first_ds["snr"] == 40.37
    assert first_ds["power"] == 2.40
    assert first_ds["corrected"] == 21
    assert first_ds["uncorrected"] == 0

    # Check second channel to verify parsing
    second_ds = data["downstream"][1]
    assert second_ds["channel_id"] == "2"
    assert second_ds["frequency"] == 675000000


def test_parsing_upstream(arris_signal_html):
    """Test parsing of Arris SB6141 upstream data."""
    parser = ArrisSB6190Parser()
    soup = BeautifulSoup(arris_signal_html, "html.parser")
    data = parser.parse(soup)

    # Verify upstream channels (4 channels expected)
    assert "upstream" in data
    assert len(data["upstream"]) == 4

    # Check first upstream channel
    first_us = data["upstream"][0]
    assert first_us["channel_id"] == "2"
    assert first_us["frequency"] == 25700000
    assert first_us["power"] == 44.5


def test_parsing_system_info(arris_signal_html):
    """Test parsing of Arris SB6141 system info."""
    parser = ArrisSB6190Parser()
    soup = BeautifulSoup(arris_signal_html, "html.parser")
    data = parser.parse(soup)

    # Verify system info exists
    assert "system_info" in data
    assert isinstance(data["system_info"], dict)


def test_transposed_table_parsing(arris_signal_html):
    """Test that transposed table format is correctly parsed."""
    # Arris SB6141 uses a unique transposed table format where
    # channel IDs are in columns, not rows
    parser = ArrisSB6190Parser()
    soup = BeautifulSoup(arris_signal_html, "html.parser")
    data = parser.parse(soup)

    # All channels should have valid data
    for channel in data["downstream"]:
        assert channel["channel_id"] is not None
        assert channel["frequency"] is not None
        # Only check snr and power if not None
        if channel["snr"] is not None:
            assert isinstance(channel["snr"], float)
        if channel["power"] is not None:
            assert isinstance(channel["power"], float)

    # Verify different channel IDs (not sequential)
    channel_ids = [ch["channel_id"] for ch in data["downstream"]]
    assert "10" in channel_ids
    assert "9" in channel_ids
    assert "11" in channel_ids
