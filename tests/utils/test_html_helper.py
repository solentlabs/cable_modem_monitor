"""Tests for HTML helper utilities."""

from __future__ import annotations

from custom_components.cable_modem_monitor.utils.html_helper import (
    PII_ALLOWLIST,
    PII_PATTERNS,
    check_for_pii,
    sanitize_html,
)


class TestCheckForPii:
    """Tests for check_for_pii function."""

    def test_detects_mac_address(self):
        """Test detection of MAC addresses."""
        content = "Device MAC: AA:BB:CC:DD:EE:FF"
        findings = check_for_pii(content)

        # MAC addresses may also match IPv6 pattern due to colon format
        mac_findings = [f for f in findings if f["pattern"] == "mac_address"]
        assert len(mac_findings) == 1
        assert mac_findings[0]["match"] == "AA:BB:CC:DD:EE:FF"

    def test_detects_email(self):
        """Test detection of email addresses."""
        content = "Contact: admin@example.com for support"
        findings = check_for_pii(content)

        assert len(findings) == 1
        assert findings[0]["pattern"] == "email"
        assert findings[0]["match"] == "admin@example.com"

    def test_detects_public_ip(self):
        """Test detection of public IP addresses."""
        content = "External DNS: 8.8.8.8"
        findings = check_for_pii(content)

        # Should detect public IP
        public_ip_findings = [f for f in findings if f["pattern"] == "public_ip"]
        assert len(public_ip_findings) == 1
        assert public_ip_findings[0]["match"] == "8.8.8.8"

    def test_detects_ipv6(self):
        """Test detection of IPv6 addresses."""
        content = "IPv6 Address: 2001:db8::1"
        findings = check_for_pii(content)

        ipv6_findings = [f for f in findings if f["pattern"] == "ipv6"]
        assert len(ipv6_findings) == 1
        assert "2001:db8::1" in ipv6_findings[0]["match"]

    def test_ignores_time_format(self):
        """Test that time formats are not flagged as IPv6."""
        content = "Uptime: 12:34:56"
        findings = check_for_pii(content)

        # Time format should not be flagged
        ipv6_findings = [f for f in findings if f["pattern"] == "ipv6"]
        assert len(ipv6_findings) == 0

    def test_ignores_allowlisted_placeholders(self):
        """Test that allowlisted placeholders are not flagged."""
        content = """
        MAC: XX:XX:XX:XX:XX:XX
        IP: ***PRIVATE_IP***
        Email: ***EMAIL***
        """
        findings = check_for_pii(content)

        # Allowlisted placeholders should not be flagged
        assert len(findings) == 0

    def test_returns_line_numbers(self):
        """Test that line numbers are correctly reported."""
        content = "Line 1\nLine 2\nMAC: AA:BB:CC:DD:EE:FF on line 3"
        findings = check_for_pii(content)

        # Filter to MAC pattern specifically
        mac_findings = [f for f in findings if f["pattern"] == "mac_address"]
        assert len(mac_findings) == 1
        assert mac_findings[0]["line"] == 3

    def test_includes_filename(self):
        """Test that filename is included in findings."""
        content = "MAC: AA:BB:CC:DD:EE:FF"
        findings = check_for_pii(content, filename="test.html")

        # Filter to MAC pattern specifically
        mac_findings = [f for f in findings if f["pattern"] == "mac_address"]
        assert len(mac_findings) == 1
        assert mac_findings[0]["filename"] == "test.html"

    def test_multiple_findings(self):
        """Test detection of multiple PII instances."""
        content = """
        MAC1: AA:BB:CC:DD:EE:FF
        MAC2: 11:22:33:44:55:66
        Email: test@example.com
        """
        findings = check_for_pii(content)

        # Should find 2 MACs and 1 email
        mac_findings = [f for f in findings if f["pattern"] == "mac_address"]
        email_findings = [f for f in findings if f["pattern"] == "email"]

        assert len(mac_findings) == 2
        assert len(email_findings) == 1

    def test_empty_content(self):
        """Test with empty content."""
        findings = check_for_pii("")
        assert len(findings) == 0

    def test_clean_content(self):
        """Test content with no PII."""
        content = """
        Power Level: 7.0 dBmV
        SNR: 40.0 dB
        Channel ID: 23
        """
        findings = check_for_pii(content)
        assert len(findings) == 0


class TestPiiPatterns:
    """Tests for PII pattern constants."""

    def test_patterns_defined(self):
        """Test that all expected patterns are defined."""
        assert "mac_address" in PII_PATTERNS
        assert "email" in PII_PATTERNS
        assert "public_ip" in PII_PATTERNS
        assert "ipv6" in PII_PATTERNS

    def test_allowlist_defined(self):
        """Test that allowlist contains expected placeholders."""
        assert "XX:XX:XX:XX:XX:XX" in PII_ALLOWLIST
        assert "***REDACTED***" in PII_ALLOWLIST
        assert "***PRIVATE_IP***" in PII_ALLOWLIST
        assert "***PUBLIC_IP***" in PII_ALLOWLIST
        assert "***IPv6***" in PII_ALLOWLIST
        assert "***EMAIL***" in PII_ALLOWLIST


class TestSanitizeHtmlEdgeCases:
    """Additional edge case tests for sanitize_html."""

    def test_multiple_mac_formats(self):
        """Test sanitization of MACs with different separators."""
        content = "WAN: AA:BB:CC:DD:EE:FF, LAN: 11-22-33-44-55-66"
        sanitized = sanitize_html(content)

        assert "AA:BB:CC:DD:EE:FF" not in sanitized
        assert "11-22-33-44-55-66" not in sanitized
        assert sanitized.count("XX:XX:XX:XX:XX:XX") == 2

    def test_ipv6_with_hex_letters(self):
        """Test that IPv6 with hex letters is sanitized."""
        content = "Gateway: fe80::1"
        sanitized = sanitize_html(content)

        assert "fe80::1" not in sanitized
        assert "***IPv6***" in sanitized

    def test_ipv6_without_hex_letters_preserved(self):
        """Test that time-like patterns are not over-sanitized."""
        content = "Uptime: 01:23:45"
        sanitized = sanitize_html(content)

        # Should be preserved since it's not a valid IPv6
        assert "01:23:45" in sanitized

    def test_config_file_path_sanitized(self):
        """Test that config file paths are sanitized."""
        content = "Config File Name: customer123.cfg"
        sanitized = sanitize_html(content)

        assert "customer123.cfg" not in sanitized
        assert "***CONFIG_PATH***" in sanitized

    def test_preserves_signal_metrics(self):
        """Test that signal metrics are preserved."""
        content = """
        Power: 7.5 dBmV
        SNR: 38.2 dB
        Frequency: 555000000 Hz
        Corrected: 12345
        Uncorrected: 0
        """
        sanitized = sanitize_html(content)

        assert "7.5 dBmV" in sanitized
        assert "38.2 dB" in sanitized
        assert "555000000" in sanitized
        assert "12345" in sanitized


class TestTagValueListSanitization:
    """Tests for WiFi credential sanitization in tagValueList."""

    def test_sanitizes_wifi_passphrase_in_dashboard(self):
        """Test that WiFi passphrases in DashBoard tagValueList are sanitized."""
        content = (
            "var tagValueList = '0|Good|| |NETGEAR38|NETGEAR38-5G|"
            "happymango167|happymango167|20|0|1|0|none|NETGEAR-Guest|"
            "None|NETGEAR-5G-Guest|None|0|0|0|0|0|1|0|0|1|0|0|0|0|"
            "---.---.---.---|1|';"
        )
        sanitized = sanitize_html(content)

        # WiFi passphrases should be redacted
        assert "happymango167" not in sanitized
        assert "***WIFI_CRED***" in sanitized

    def test_preserves_status_values_in_tagvaluelist(self):
        """Test that status values like 'Locked', 'Good' are preserved."""
        content = (
            "var tagValueList = '345000000|Locked|OK|Operational|OK|"
            "Operational|&nbsp;|&nbsp;|Enabled|BPI+|Mon Nov 24 2025|0|0|0';"
        )
        sanitized = sanitize_html(content)

        # Status values should be preserved
        assert "Locked" in sanitized
        assert "OK" in sanitized
        assert "Operational" in sanitized
        assert "Enabled" in sanitized
        assert "BPI+" in sanitized

    def test_preserves_numeric_values_in_tagvaluelist(self):
        """Test that numeric values like frequencies are preserved."""
        content = "var tagValueList = '345000000|8|1|256|5120000|30840000';"
        sanitized = sanitize_html(content)

        # Numeric values should be preserved
        assert "345000000" in sanitized
        assert "5120000" in sanitized
        assert "30840000" in sanitized

    def test_preserves_version_strings_in_tagvaluelist(self):
        """Test that version strings are preserved."""
        content = "var tagValueList = 'V2.02.18|0|0|1|0|retail|0|1|0|0|0|1|1|';"
        sanitized = sanitize_html(content)

        # Version strings should be preserved
        assert "V2.02.18" in sanitized
        assert "retail" in sanitized

    def test_sanitizes_double_quoted_tagvaluelist(self):
        """Test that double-quoted tagValueList is also sanitized."""
        content = 'var tagValueList = "0|Good|both|none|MySSID1234|secretpass99";'
        sanitized = sanitize_html(content)

        # Passphrase-like values should be redacted
        assert "secretpass99" not in sanitized
        assert "***WIFI_CRED***" in sanitized

    def test_preserves_short_values_in_tagvaluelist(self):
        """Test that short values (< 8 chars) are preserved."""
        content = "var tagValueList = '0|Good|| |ABC|XYZ123|none|Off|On';"
        sanitized = sanitize_html(content)

        # Short values should be preserved (under 8 chars)
        assert "ABC" in sanitized
        assert "Good" in sanitized
        assert "none" in sanitized

    def test_handles_docsis_channel_data(self):
        """Test that DOCSIS channel data is not incorrectly sanitized."""
        content = (
            "var tagValueList = '8|1|Locked|QAM256|1|345000000 Hz|2.9|"
            "46.3|289|320|2|Locked|QAM256|2|351000000 Hz|3|46.4|240|278';"
        )
        sanitized = sanitize_html(content)

        # DOCSIS data should be preserved
        assert "Locked" in sanitized
        assert "QAM256" in sanitized
        assert "345000000 Hz" in sanitized

    def test_wifi_cred_in_allowlist(self):
        """Test that WIFI_CRED placeholder is in allowlist."""
        assert "***WIFI_CRED***" in PII_ALLOWLIST

    def test_sanitizes_device_names_before_ip(self):
        """Test that device names appearing before IP/MAC placeholders are redacted."""
        content = (
            "var tagValueList = '19|1|MyDevice|***PRIVATE_IP***|XX:XX:XX:XX:XX:XX|1|1|"
            "AnotherDevice|***PRIVATE_IP***|XX:XX:XX:XX:XX:XX|1|1|"
            "--|***PRIVATE_IP***|XX:XX:XX:XX:XX:XX|1|';"
        )
        sanitized = sanitize_html(content)

        # Device names should be redacted
        assert "MyDevice" not in sanitized
        assert "AnotherDevice" not in sanitized
        assert "***DEVICE***" in sanitized
        # Empty placeholder should be preserved
        assert "|--|" in sanitized
