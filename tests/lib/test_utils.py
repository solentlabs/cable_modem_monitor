"""Tests for utility functions in lib/utils.py."""

from __future__ import annotations

from custom_components.cable_modem_monitor.lib.utils import (
    extract_float,
    extract_number,
    parse_uptime_to_seconds,
)


class TestExtractNumber:
    """Test the extract_number function."""

    def test_positive_integer(self):
        """Test extracting a positive integer."""
        assert extract_number("  123  ") == 123

    def test_negative_integer(self):
        """Test extracting a negative integer."""
        assert extract_number("-456") == -456

    def test_string_with_text(self):
        """Test extracting an integer from a string with other text."""
        assert extract_number("SNR: 35 dB") == 35

    def test_string_with_no_digits(self):
        """Test a string with no digits."""
        assert extract_number("N/A") is None

    def test_empty_string(self):
        """Test an empty string."""
        assert extract_number("") is None


class TestExtractFloat:
    """Test the extract_float function."""

    def test_positive_float(self):
        """Test extracting a positive float."""
        assert extract_float("  12.3  ") == 12.3

    def test_negative_float(self):
        """Test extracting a negative float."""
        assert extract_float("-45.6") == -45.6

    def test_string_with_text(self):
        """Test extracting a float from a string with other text."""
        assert extract_float("Power: -1.2 dBmV") == -1.2

    def test_string_with_no_digits(self):
        """Test a string with no digits."""
        assert extract_float("N/A") is None

    def test_empty_string(self):
        """Test an empty string."""
        assert extract_float("") is None


class TestParseUptime:
    """Test the parse_uptime_to_seconds function."""

    def test_days_hours(self):
        """Test parsing uptime with days and hours."""
        result = parse_uptime_to_seconds("2 days 5 hours")
        expected = (2 * 86400) + (5 * 3600)  # 2 days + 5 hours
        assert result == expected

    def test_hours_only(self):
        """Test parsing uptime with only hours."""
        result = parse_uptime_to_seconds("3 hours")
        expected = 3 * 3600
        assert result == expected

    def test_with_minutes(self):
        """Test parsing uptime with hours and minutes."""
        result = parse_uptime_to_seconds("3 hours 45 minutes")
        expected = (3 * 3600) + (45 * 60)
        assert result == expected

    def test_complex(self):
        """Test parsing complex uptime string."""
        result = parse_uptime_to_seconds("5 days 12 hours 30 minutes 15 seconds")
        expected = (5 * 86400) + (12 * 3600) + (30 * 60) + 15
        assert result == expected

    def test_unknown(self):
        """Test parsing Unknown uptime."""
        result = parse_uptime_to_seconds("Unknown")
        assert result is None

    def test_empty(self):
        """Test parsing empty uptime."""
        result = parse_uptime_to_seconds("")
        assert result is None

    def test_none(self):
        """Test parsing None uptime."""
        result = parse_uptime_to_seconds(None)
        assert result is None

    def test_hms_format(self):
        """Test parsing HH:MM:SS format (e.g., CM600)."""
        # 1308:19:22 = 1308 hours, 19 minutes, 22 seconds
        result = parse_uptime_to_seconds("1308:19:22")
        expected = (1308 * 3600) + (19 * 60) + 22
        assert result == expected

    def test_hms_format_short(self):
        """Test parsing shorter HH:MM:SS format."""
        result = parse_uptime_to_seconds("24:30:15")
        expected = (24 * 3600) + (30 * 60) + 15
        assert result == expected

    def test_hms_format_single_digits(self):
        """Test parsing H:M:S format with single digits."""
        result = parse_uptime_to_seconds("1:2:3")
        expected = (1 * 3600) + (2 * 60) + 3
        assert result == expected

    def test_days_plus_hms_format(self):
        """Test parsing 'X days HH:MM:SS' format (e.g., Arris S33)."""
        # "7 days 12:34:56" = 7 days + 12 hours + 34 minutes + 56 seconds
        result = parse_uptime_to_seconds("7 days 12:34:56")
        expected = (7 * 86400) + (12 * 3600) + (34 * 60) + 56
        assert result == expected

    def test_days_plus_hms_format_zero_days(self):
        """Test parsing '0 days HH:MM:SS' format."""
        result = parse_uptime_to_seconds("0 days 01:23:45")
        expected = (0 * 86400) + (1 * 3600) + (23 * 60) + 45
        assert result == expected
