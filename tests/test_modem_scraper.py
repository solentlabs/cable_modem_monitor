"""Tests for Cable Modem Monitor scraper."""
import pytest
from bs4 import BeautifulSoup
import sys
import os

***REMOVED*** Add parent directory to path to import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'custom_components', 'cable_modem_monitor'))

from modem_scraper import ModemScraper


class TestModemScraper:
    """Test the ModemScraper class."""

    @pytest.fixture
    def moto_connection_html(self):
        """Load MotoConnection.asp HTML fixture."""
        fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'moto_connection.html')
        with open(fixture_path, 'r') as f:
            return f.read()

    @pytest.fixture
    def moto_home_html(self):
        """Load MotoHome.asp HTML fixture."""
        fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'moto_home.html')
        with open(fixture_path, 'r') as f:
            return f.read()

    @pytest.fixture
    def scraper(self):
        """Create a ModemScraper instance."""
        return ModemScraper("192.168.100.1", "admin", "password")

    def test_parse_downstream_channels(self, scraper, moto_connection_html):
        """Test parsing downstream channel data."""
        soup = BeautifulSoup(moto_connection_html, 'html.parser')
        channels = scraper._parse_downstream_channels(soup)

        assert len(channels) > 0, "Should parse at least one downstream channel"
        assert len(channels) == 24, f"Should parse 24 downstream channels, got {len(channels)}"

        ***REMOVED*** Check first channel structure
        first_channel = channels[0]
        assert 'channel' in first_channel
        assert 'frequency' in first_channel
        assert 'power' in first_channel
        assert 'snr' in first_channel
        assert 'corrected' in first_channel
        assert 'uncorrected' in first_channel

        ***REMOVED*** Verify data types
        assert isinstance(first_channel['channel'], int)
        assert isinstance(first_channel['frequency'], (int, float))
        assert isinstance(first_channel['power'], (int, float))
        assert isinstance(first_channel['snr'], (int, float))
        assert isinstance(first_channel['corrected'], int)
        assert isinstance(first_channel['uncorrected'], int)

    def test_parse_upstream_channels(self, scraper, moto_connection_html):
        """Test parsing upstream channel data."""
        soup = BeautifulSoup(moto_connection_html, 'html.parser')
        channels = scraper._parse_upstream_channels(soup)

        assert len(channels) > 0, "Should parse at least one upstream channel"

        ***REMOVED*** Check first channel structure
        first_channel = channels[0]
        assert 'channel' in first_channel
        assert 'frequency' in first_channel
        assert 'power' in first_channel

    def test_parse_software_version(self, scraper, moto_home_html):
        """Test parsing software version from MotoHome.asp."""
        soup = BeautifulSoup(moto_home_html, 'html.parser')
        version = scraper._parse_software_version(soup)

        assert version != "Unknown", "Should find software version"
        assert version == "7621-5.7.1.5", f"Expected version '7621-5.7.1.5', got '{version}'"

    def test_parse_system_uptime(self, scraper, moto_connection_html):
        """Test parsing system uptime from MotoConnection.asp."""
        soup = BeautifulSoup(moto_connection_html, 'html.parser')
        uptime = scraper._parse_system_uptime(soup)

        assert uptime != "Unknown", "Should find system uptime"
        assert "days" in uptime.lower() or "h:" in uptime or "d " in uptime, \
            f"Uptime should contain time information, got: '{uptime}'"

    def test_parse_channel_counts(self, scraper, moto_home_html):
        """Test parsing channel counts from MotoHome.asp."""
        soup = BeautifulSoup(moto_home_html, 'html.parser')
        counts = scraper._parse_channel_counts(soup)

        assert counts['downstream'] is not None, "Should find downstream channel count"
        assert counts['upstream'] is not None, "Should find upstream channel count"
        assert counts['downstream'] == 24, f"Expected 24 downstream channels, got {counts['downstream']}"
        assert counts['upstream'] == 5, f"Expected 5 upstream channels, got {counts['upstream']}"

    def test_total_errors_calculation(self, scraper, moto_connection_html):
        """Test that total errors are calculated correctly."""
        soup = BeautifulSoup(moto_connection_html, 'html.parser')
        channels = scraper._parse_downstream_channels(soup)

        total_corrected = sum(ch.get("corrected", 0) for ch in channels)
        total_uncorrected = sum(ch.get("uncorrected", 0) for ch in channels)

        assert total_corrected >= 0, "Total corrected errors should be non-negative"
        assert total_uncorrected >= 0, "Total uncorrected errors should be non-negative"
        assert isinstance(total_corrected, int), "Total corrected should be an integer"
        assert isinstance(total_uncorrected, int), "Total uncorrected should be an integer"


class TestRealWorldScenarios:
    """Test real-world scenarios and edge cases."""

    @pytest.fixture
    def moto_connection_html(self):
        """Load MotoConnection.asp HTML fixture."""
        fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'moto_connection.html')
        with open(fixture_path, 'r') as f:
            return f.read()

    @pytest.fixture
    def moto_home_html(self):
        """Load MotoHome.asp HTML fixture."""
        fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'moto_home.html')
        with open(fixture_path, 'r') as f:
            return f.read()

    def test_motorola_mb_series_full_parse(self, moto_connection_html, moto_home_html):
        """Test complete parsing workflow for Motorola MB series modem."""
        scraper = ModemScraper("192.168.100.1", "admin", "password")

        ***REMOVED*** Parse connection page
        conn_soup = BeautifulSoup(moto_connection_html, 'html.parser')
        downstream = scraper._parse_downstream_channels(conn_soup)
        upstream = scraper._parse_upstream_channels(conn_soup)
        uptime = scraper._parse_system_uptime(conn_soup)

        ***REMOVED*** Parse home page
        home_soup = BeautifulSoup(moto_home_html, 'html.parser')
        version = scraper._parse_software_version(home_soup)
        counts = scraper._parse_channel_counts(home_soup)

        ***REMOVED*** Validate all data is present
        assert len(downstream) > 0, "Should have downstream channels"
        assert len(upstream) > 0, "Should have upstream channels"
        assert uptime != "Unknown", "Should have uptime"
        assert version != "Unknown", "Should have software version"
        assert counts['downstream'] is not None, "Should have downstream count"
        assert counts['upstream'] is not None, "Should have upstream count"

        ***REMOVED*** Validate counts match
        assert counts['downstream'] == 24, "Downstream count should be 24"
        assert counts['upstream'] == 5, "Upstream count should be 5"

    def test_power_levels_in_range(self, moto_connection_html):
        """Test that power levels are within reasonable ranges."""
        scraper = ModemScraper("192.168.100.1")
        soup = BeautifulSoup(moto_connection_html, 'html.parser')

        downstream = scraper._parse_downstream_channels(soup)
        upstream = scraper._parse_upstream_channels(soup)

        ***REMOVED*** Downstream power should be -15 to +15 dBmV typically
        for ch in downstream:
            assert -20 <= ch['power'] <= 20, \
                f"Downstream channel {ch['channel']} power {ch['power']} dBmV out of range"
            ***REMOVED*** SNR should be positive and typically 25-50 dB
            assert 0 <= ch['snr'] <= 60, \
                f"Downstream channel {ch['channel']} SNR {ch['snr']} dB out of range"

        ***REMOVED*** Upstream power should be 30-55 dBmV typically
        for ch in upstream:
            assert 20 <= ch['power'] <= 60, \
                f"Upstream channel {ch['channel']} power {ch['power']} dBmV out of range"

    def test_frequencies_in_valid_range(self, moto_connection_html):
        """Test that frequencies are in valid DOCSIS 3.0 ranges."""
        scraper = ModemScraper("192.168.100.1")
        soup = BeautifulSoup(moto_connection_html, 'html.parser')

        downstream = scraper._parse_downstream_channels(soup)
        upstream = scraper._parse_upstream_channels(soup)

        ***REMOVED*** Downstream: 108-1002 MHz typically
        for ch in downstream:
            freq_mhz = ch['frequency'] / 1_000_000  ***REMOVED*** Convert Hz to MHz
            assert 50 <= freq_mhz <= 1100, \
                f"Downstream channel {ch['channel']} frequency {freq_mhz} MHz out of range"

        ***REMOVED*** Upstream: 5-42 MHz typically (may extend to 85 MHz)
        for ch in upstream:
            freq_mhz = ch['frequency'] / 1_000_000
            assert 5 <= freq_mhz <= 200, \
                f"Upstream channel {ch['channel']} frequency {freq_mhz} MHz out of range"


class TestARRISSB6141:
    """Test ARRIS SB6141 modem parsing (transposed table format)."""

    @pytest.fixture
    def arris_sb6141_html(self):
        """Load ARRIS SB6141 signal data HTML fixture."""
        fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'arris_sb6141_signal.html')
        with open(fixture_path, 'r') as f:
            return f.read()

    def test_arris_sb6141_downstream_parsing(self, arris_sb6141_html):
        """Test parsing ARRIS SB6141 downstream channels."""
        scraper = ModemScraper("192.168.100.1")
        soup = BeautifulSoup(arris_sb6141_html, 'html.parser')

        downstream, upstream = scraper._parse_arris_sb6141(soup)

        ***REMOVED*** Should have 8 downstream channels based on fixture
        assert len(downstream) == 8, f"Expected 8 downstream channels, got {len(downstream)}"

        ***REMOVED*** Check first channel (ID=10)
        ch = downstream[0]
        assert ch['channel'] == 10
        assert ch['frequency'] == 519000000  ***REMOVED*** Hz
        assert ch['snr'] == 39.0  ***REMOVED*** dB
        assert ch['power'] == 5.0  ***REMOVED*** dBmV
        assert ch['corrected'] == 573
        assert ch['uncorrected'] == 823

        ***REMOVED*** Check last channel (ID=4)
        ch = downstream[7]
        assert ch['channel'] == 4
        assert ch['frequency'] == 471000000
        assert ch['snr'] == 39.0
        assert ch['power'] == 5.0
        assert ch['corrected'] == 552
        assert ch['uncorrected'] == 761

    def test_arris_sb6141_upstream_parsing(self, arris_sb6141_html):
        """Test parsing ARRIS SB6141 upstream channels."""
        scraper = ModemScraper("192.168.100.1")
        soup = BeautifulSoup(arris_sb6141_html, 'html.parser')

        downstream, upstream = scraper._parse_arris_sb6141(soup)

        ***REMOVED*** Should have 4 upstream channels based on fixture
        assert len(upstream) == 4, f"Expected 4 upstream channels, got {len(upstream)}"

        ***REMOVED*** Check first channel (ID=7)
        ch = upstream[0]
        assert ch['channel'] == 7
        assert ch['frequency'] == 30600000  ***REMOVED*** Hz
        assert ch['power'] == 49.0  ***REMOVED*** dBmV

        ***REMOVED*** Check last channel (ID=6)
        ch = upstream[3]
        assert ch['channel'] == 6
        assert ch['frequency'] == 24200000
        assert ch['power'] == 47.0

    def test_arris_sb6141_error_stats_merged(self, arris_sb6141_html):
        """Test that error stats are properly merged into downstream channels."""
        scraper = ModemScraper("192.168.100.1")
        soup = BeautifulSoup(arris_sb6141_html, 'html.parser')

        downstream, _ = scraper._parse_arris_sb6141(soup)

        ***REMOVED*** All downstream channels should have corrected/uncorrected values
        for ch in downstream:
            assert ch['corrected'] is not None, f"Channel {ch['channel']} missing corrected errors"
            assert ch['uncorrected'] is not None, f"Channel {ch['channel']} missing uncorrected errors"
            assert ch['corrected'] >= 0, "Corrected errors should be non-negative"
            assert ch['uncorrected'] >= 0, "Uncorrected errors should be non-negative"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
