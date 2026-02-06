"""Tests for HTML helper utilities."""

from __future__ import annotations

import re
from pathlib import Path

from har_capture.patterns import is_allowlisted, load_pii_patterns
from har_capture.sanitization import check_for_pii, sanitize_html
from har_capture.sanitization.report import HeuristicMode

# Path to custom PII patterns for cable modem sanitization
CUSTOM_PATTERNS_PATH = (
    Path(__file__).parent.parent.parent / "custom_components" / "cable_modem_monitor" / "pii_patterns.json"
)


class TestCheckForPii:
    """Tests for check_for_pii function."""

    def test_detects_mac_address(self):
        """Test detection of MAC addresses."""
        content = "Device MAC: DE:AD:BE:EF:CA:FE"
        findings = check_for_pii(content)

        # MAC addresses may also match IPv6 pattern due to colon format
        mac_findings = [f for f in findings if f["pattern"] == "mac_address"]
        assert len(mac_findings) == 1
        assert mac_findings[0]["match"] == "DE:AD:BE:EF:CA:FE"

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
        # Use link-local address (not documentation range which is allowlisted)
        content = "IPv6 Address: fe80::1234:5678"
        findings = check_for_pii(content)

        ipv6_findings = [f for f in findings if f["pattern"] == "ipv6"]
        assert len(ipv6_findings) == 1
        assert "fe80::1234:5678" in ipv6_findings[0]["match"]

    def test_ignores_time_format(self):
        """Test that time formats are not flagged as IPv6."""
        content = "Uptime: 12:34:56"
        findings = check_for_pii(content)

        # Time format should not be flagged
        ipv6_findings = [f for f in findings if f["pattern"] == "ipv6"]
        assert len(ipv6_findings) == 0

    def test_ignores_allowlisted_placeholders(self):
        """Test that allowlisted placeholders are not flagged."""
        # har-capture uses these formats for allowlisted values:
        # - MAC: XX:XX:XX:XX:XX:XX or 02:xx:xx:xx:xx:xx (locally-administered)
        # - IP: 192.0.2.x (TEST-NET-1 documentation range, RFC 5737)
        # - Email: x@x.invalid or user@redacted.invalid
        content = """
        MAC: XX:XX:XX:XX:XX:XX
        IP: 192.0.2.100
        Email: x@x.invalid
        """
        findings = check_for_pii(content)

        # Allowlisted placeholders should not be flagged
        assert len(findings) == 0

    def test_returns_line_numbers(self):
        """Test that line numbers are correctly reported."""
        content = "Line 1\nLine 2\nMAC: DE:AD:BE:EF:CA:FE on line 3"
        findings = check_for_pii(content)

        # Filter to MAC pattern specifically
        mac_findings = [f for f in findings if f["pattern"] == "mac_address"]
        assert len(mac_findings) == 1
        assert mac_findings[0]["line"] == 3

    def test_includes_filename(self):
        """Test that filename is included in findings."""
        content = "MAC: DE:AD:BE:EF:CA:FE"
        findings = check_for_pii(content, filename="test.html")

        # Filter to MAC pattern specifically
        mac_findings = [f for f in findings if f["pattern"] == "mac_address"]
        assert len(mac_findings) == 1
        assert mac_findings[0]["filename"] == "test.html"

    def test_multiple_findings(self):
        """Test detection of multiple PII instances."""
        content = """
        MAC1: DE:AD:BE:EF:CA:FE
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
    """Tests for PII pattern definitions."""

    def test_patterns_defined(self):
        """Test that all expected patterns are defined."""
        data = load_pii_patterns()
        patterns = data.get("patterns", data)  # Handle nested structure
        assert "mac_address" in patterns
        assert "email" in patterns
        assert "public_ip" in patterns
        assert "ipv6" in patterns

    def test_allowlist_recognizes_placeholders(self):
        """Test that allowlist recognizes expected placeholder formats."""
        # Static placeholders
        assert is_allowlisted("XX:XX:XX:XX:XX:XX")
        assert is_allowlisted("[REDACTED]")
        # Format-preserving hashes (MAC in locally-administered range)
        assert is_allowlisted("02:ab:cd:ef:12:34")
        # Hash prefixes
        assert is_allowlisted("SERIAL_abcd1234")


class TestSanitizeHtmlEdgeCases:
    """Additional edge case tests for sanitize_html."""

    def test_multiple_mac_formats(self):
        """Test sanitization of MACs with different separators."""
        content = "WAN: AA:BB:CC:DD:EE:FF, LAN: 11-22-33-44-55-66"
        # Use salt=None for static placeholders (legacy behavior)
        sanitized = sanitize_html(content, salt=None)

        assert "AA:BB:CC:DD:EE:FF" not in sanitized
        assert "11-22-33-44-55-66" not in sanitized
        assert sanitized.count("XX:XX:XX:XX:XX:XX") == 2

    def test_ipv6_with_hex_letters(self):
        """Test that IPv6 with hex letters is sanitized."""
        content = "Gateway: fe80::1"
        sanitized = sanitize_html(content, salt=None)

        assert "fe80::1" not in sanitized
        # har-capture uses :: for static IPv6 placeholder
        assert "::" in sanitized

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

        # Original config filename should be removed
        assert "customer123.cfg" not in sanitized
        # har-capture uses CONFIG_ prefix for redacted config paths
        assert "CONFIG_" in sanitized or "[REDACTED]" in sanitized

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

    def test_preserves_firmware_version_strings(self):
        """Test that firmware version strings are preserved, not sanitized as IPs.

        Regression test: Version strings like "5.7.1.5" should not be treated as IP addresses.
        They are not PII and are critical for diagnostics.
        """
        test_cases = [
            ("<td>Software Version: 7621-5.7.1.5</td>", "5.7.1.5"),
            ("<td>Firmware: MB8611-8.1.0.24-GA</td>", "8.1.0.24"),
            ("<td>Version: V2.4.6.8</td>", "2.4.6.8"),
            ("<td>Build: SB8200-9.1.103AA6</td>", "9.1.103"),
        ]

        for html, version in test_cases:
            sanitized = sanitize_html(html, heuristics=HeuristicMode.REDACT)

            # Version string must be preserved
            assert version in sanitized, (
                f"Version string '{version}' was incorrectly sanitized. " f"Input: {html}\nOutput: {sanitized}"
            )

            # Should NOT be replaced with TEST-NET IPs
            assert "192.0.2." not in sanitized, (
                f"Version string was replaced with TEST-NET IP. " f"Input: {html}\nOutput: {sanitized}"
            )

    def test_ipv4_addresses_produce_valid_format(self):
        """Test that sanitized IPv4 addresses have valid 4-octet format.

        Regression test: Ensures IPv4 sanitization doesn't produce malformed addresses
        with incorrect number of octets or out-of-range values.
        """
        test_cases = [
            "<td>IP Address: 10.123.45.67</td>",
            "<td>Gateway: 192.168.1.254</td>",
            "<td>WAN IP: 172.16.0.1</td>",
        ]

        for html in test_cases:
            sanitized = sanitize_html(html, heuristics=HeuristicMode.REDACT)

            # Find all IP-like patterns in output
            ip_patterns = re.findall(r"\d+\.\d+\.\d+(?:\.\d+)*", sanitized)

            for ip_pattern in ip_patterns:
                octets = ip_pattern.split(".")

                # Must have exactly 4 octets (not 3, not 5)
                assert len(octets) == 4, (
                    f"Invalid IPv4 format with {len(octets)} octets: {ip_pattern}. "
                    f"Input: {html}\nOutput: {sanitized}"
                )

                # Each octet must be 0-255
                for octet in octets:
                    octet_val = int(octet)
                    assert 0 <= octet_val <= 255, (
                        f"Invalid octet value {octet_val} in {ip_pattern}. " f"Input: {html}\nOutput: {sanitized}"
                    )

    def test_distinguishes_ips_from_versions(self):
        """Test that IPs are sanitized while version strings are preserved in same HTML.

        Regression test: Ensures context-aware sanitization correctly identifies
        which dotted-decimal values are IPs vs. version strings.
        """
        html = """
        <table>
          <tr>
            <td>IP Address</td>
            <td>10.123.45.67</td>
          </tr>
          <tr>
            <td>Software Version</td>
            <td>5.7.1.5</td>
          </tr>
        </table>
        """

        sanitized = sanitize_html(html, heuristics=HeuristicMode.REDACT)

        # Original IP should be sanitized
        assert "10.123.45.67" not in sanitized, "IP address was not sanitized"

        # Version should be preserved
        assert "5.7.1.5" in sanitized, "Version string was incorrectly sanitized"

        # Verify sanitized IPs have valid format (exclude version string)
        ip_patterns = re.findall(r"\d+\.\d+\.\d+\.\d+", sanitized)
        for ip in ip_patterns:
            if ip != "5.7.1.5":  # Exclude version string
                octets = ip.split(".")
                assert len(octets) == 4, f"Sanitized IP has invalid format: {ip}"


class TestTagValueListSanitization:
    """Tests for WiFi credential sanitization in tagValueList."""

    def test_sanitizes_wifi_passphrase_in_dashboard(self):
        """Test that WiFi passphrases in DashBoard tagValueList are sanitized."""
        content = (
            "var tagValueList = '0|Good|| |NETGEAR38|NETGEAR38-5G|"
            "TestWiFiPass123|TestWiFiPass123|20|0|1|0|none|NETGEAR-Guest|"
            "None|NETGEAR-5G-Guest|None|0|0|0|0|0|1|0|0|1|0|0|0|0|"
            "---.---.---.---|1|';"
        )
        sanitized = sanitize_html(content, heuristics=HeuristicMode.REDACT)

        # WiFi passphrases should be redacted
        assert "TestWiFiPass123" not in sanitized
        # har-capture uses WIFI_ prefix for redacted WiFi credentials
        assert "WIFI_" in sanitized or "[REDACTED]" in sanitized

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
        sanitized = sanitize_html(content, heuristics=HeuristicMode.REDACT)

        # Passphrase-like values should be redacted
        assert "secretpass99" not in sanitized
        # har-capture uses WIFI_ prefix for redacted WiFi credentials
        assert "WIFI_" in sanitized or "[REDACTED]" in sanitized

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
        """Test that WIFI_CRED placeholder prefix is in allowlist."""
        # WIFI_ is a hash prefix, so WIFI_xxxxxxxx values are recognized
        assert is_allowlisted("WIFI_abcd1234")

    def test_sanitizes_device_names_before_ip(self):
        """Test that device names appearing before IP/MAC placeholders are redacted."""
        content = (
            "var tagValueList = '19|1|MyDevice|***PRIVATE_IP***|XX:XX:XX:XX:XX:XX|1|1|"
            "AnotherDevice|***PRIVATE_IP***|XX:XX:XX:XX:XX:XX|1|1|"
            "--|***PRIVATE_IP***|XX:XX:XX:XX:XX:XX|1|';"
        )
        sanitized = sanitize_html(content, heuristics=HeuristicMode.REDACT)

        # Device names should be redacted
        assert "MyDevice" not in sanitized
        assert "AnotherDevice" not in sanitized
        # har-capture redacts with hash prefixes (DEVICE_, WIFI_, etc.)
        # Accept any redaction - the important thing is sensitive values are gone
        import re

        assert re.search(r"[A-Z]+_[a-f0-9]{8}", sanitized), "Expected hash-based redaction pattern"
        # Empty placeholder should be preserved
        assert "|--|" in sanitized
