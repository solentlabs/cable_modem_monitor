"""Tests for the Arris SB6141 parser."""
import os
from bs4 import BeautifulSoup
import pytest

from custom_components.cable_modem_monitor.parsers.arris.sb6141 import ArrisSB6141Parser


@pytest.fixture
def arris_signal_html():
    """Load arris_sb6141_signal.html fixture."""
    fixture_path = os.path.join(
        os.path.dirname(__file__), "fixtures", "sb6141", "signal.html"
    )
    with open(fixture_path, "r") as f:
        return f.read()


def test_parser_detection(arris_signal_html):
    """Test that the Arris SB6141 parser detects the modem."""
    soup = BeautifulSoup(arris_signal_html, "html.parser")
    assert ArrisSB6141Parser.can_parse(
        soup, "http://192.168.100.1/cmSignal.html", arris_signal_html
    )


def test_parsing_downstream(arris_signal_html):
    """Test parsing of Arris SB6141 downstream data."""
    parser = ArrisSB6141Parser()
    soup = BeautifulSoup(arris_signal_html, "html.parser")
    data = parser.parse(soup)

    ***REMOVED*** Verify downstream channels (8 channels in fixture)
    assert "downstream" in data
    assert len(data["downstream"]) == 8

    ***REMOVED*** Check first downstream channel
    first_ds = data["downstream"][0]
    assert first_ds["channel_id"] == "10"
    assert first_ds["frequency"] == 519000000  ***REMOVED*** 519000000 Hz
    assert first_ds["snr"] == 39.0
    assert first_ds["power"] == 5.0
    assert first_ds["corrected"] == 573
    assert first_ds["uncorrected"] == 823

    ***REMOVED*** Check second channel to verify parsing
    second_ds = data["downstream"][1]
    assert second_ds["channel_id"] == "9"
    assert second_ds["frequency"] == 513000000


def test_parsing_upstream(arris_signal_html):
    """Test parsing of Arris SB6141 upstream data."""
    parser = ArrisSB6141Parser()
    soup = BeautifulSoup(arris_signal_html, "html.parser")
    data = parser.parse(soup)

    ***REMOVED*** Verify upstream channels (4 channels expected)
    assert "upstream" in data
    assert len(data["upstream"]) == 4

    ***REMOVED*** Check first upstream channel
    first_us = data["upstream"][0]
    assert first_us["channel_id"] == "7"
    assert first_us["frequency"] == 30600000
    assert first_us["power"] == 49.0


def test_parsing_system_info(arris_signal_html):
    """Test parsing of Arris SB6141 system info."""
    parser = ArrisSB6141Parser()
    soup = BeautifulSoup(arris_signal_html, "html.parser")
    data = parser.parse(soup)

    ***REMOVED*** Verify system info exists
    assert "system_info" in data
    assert isinstance(data["system_info"], dict)


def test_transposed_table_parsing(arris_signal_html):
    """Test that transposed table format is correctly parsed."""
    ***REMOVED*** Arris SB6141 uses a unique transposed table format where
    ***REMOVED*** channel IDs are in columns, not rows
    parser = ArrisSB6141Parser()
    soup = BeautifulSoup(arris_signal_html, "html.parser")
    data = parser.parse(soup)

    ***REMOVED*** All channels should have valid data
    for channel in data["downstream"]:
        assert channel["channel_id"] is not None
        assert channel["frequency"] is not None
        assert channel["snr"] is not None
        assert channel["power"] is not None
        ***REMOVED*** Note: Arris parser doesn't extract modulation data

    ***REMOVED*** Verify different channel IDs (not sequential)
    channel_ids = [ch["channel_id"] for ch in data["downstream"]]
    assert "10" in channel_ids
    assert "9" in channel_ids
    assert "11" in channel_ids
