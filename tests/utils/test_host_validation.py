"""Tests for host validation utilities."""

from __future__ import annotations

import pytest

from custom_components.cable_modem_monitor.utils.host_validation import (
    extract_hostname,
    is_valid_host,
)


class TestIsValidHost:
    """Tests for is_valid_host function."""

    def test_valid_ipv4_addresses(self):
        """Test valid IPv4 addresses."""
        valid_ips = [
            "192.168.100.1",
            "10.0.0.1",
            "172.16.0.1",
            "255.255.255.255",
            "0.0.0.0",
            "1.1.1.1",
        ]
        for ip in valid_ips:
            assert is_valid_host(ip), f"{ip} should be valid"

    def test_valid_ipv6_addresses(self):
        """Test valid IPv6 addresses."""
        valid_ips = [
            "::1",
            "fe80::1",
            "2001:db8::1",
        ]
        for ip in valid_ips:
            assert is_valid_host(ip), f"{ip} should be valid"

    def test_valid_hostnames(self):
        """Test valid hostnames."""
        valid_hosts = [
            "localhost",
            "modem",
            "router.local",
            "my-modem.home.lan",
            "cable-modem",
            "a",  # Single character
            "test123",
        ]
        for host in valid_hosts:
            assert is_valid_host(host), f"{host} should be valid"

    def test_invalid_empty_host(self):
        """Test empty host is invalid."""
        assert not is_valid_host("")
        assert not is_valid_host(None)  # type: ignore[arg-type]

    def test_invalid_too_long_host(self):
        """Test host exceeding max length is invalid."""
        long_host = "a" * 254  # Max is 253
        assert not is_valid_host(long_host)

    def test_invalid_shell_metacharacters(self):
        """Test hosts with shell metacharacters are rejected."""
        dangerous_hosts = [
            "192.168.1.1; rm -rf /",
            "host$(whoami)",
            "host`id`",
            "host|cat /etc/passwd",
            "host&echo pwned",
            "host>output.txt",
            "host<input.txt",
            "host\nmalicious",
        ]
        for host in dangerous_hosts:
            assert not is_valid_host(host), f"{host} should be invalid (shell metachar)"

    def test_invalid_formats_rejected(self):
        """Test that truly invalid formats are rejected."""
        # Note: The validator is permissive - things like "256.1.1.1" pass
        # because they match the hostname pattern. This tests actual rejections.
        invalid_hosts: list[str | None] = [
            "",
            None,
            "host; command",  # Shell injection
            "host|pipe",
            "host`backtick`",
        ]
        for host in invalid_hosts:
            assert not is_valid_host(host), f"{host} should be invalid"  # type: ignore[arg-type]

    def test_invalid_hostname_formats(self):
        """Test invalid hostname formats."""
        invalid_hosts = [
            "-startswithdash",
            "ends-with-dash-",
            ".startswithperiod",
            "has spaces",
            "has_underscore",
        ]
        for host in invalid_hosts:
            assert not is_valid_host(host), f"{host} should be invalid"


class TestExtractHostname:
    """Tests for extract_hostname function."""

    def test_extract_from_http_url(self):
        """Test hostname extraction from HTTP URL."""
        assert extract_hostname("http://192.168.100.1") == "192.168.100.1"
        assert extract_hostname("http://192.168.100.1/") == "192.168.100.1"
        assert extract_hostname("http://192.168.100.1/status.html") == "192.168.100.1"

    def test_extract_from_https_url(self):
        """Test hostname extraction from HTTPS URL."""
        assert extract_hostname("https://192.168.100.1") == "192.168.100.1"
        assert extract_hostname("https://modem.local/") == "modem.local"

    def test_extract_from_url_with_port(self):
        """Test hostname extraction from URL with port."""
        assert extract_hostname("http://192.168.100.1:8080") == "192.168.100.1"
        assert extract_hostname("https://modem.local:443/") == "modem.local"

    def test_extract_plain_hostname(self):
        """Test extraction when plain hostname is provided."""
        assert extract_hostname("192.168.100.1") == "192.168.100.1"
        assert extract_hostname("modem.local") == "modem.local"

    def test_strips_whitespace(self):
        """Test that whitespace is stripped."""
        assert extract_hostname("  192.168.100.1  ") == "192.168.100.1"
        assert extract_hostname("\tmodem.local\n") == "modem.local"

    def test_raises_on_empty_host(self):
        """Test ValueError on empty host."""
        with pytest.raises(ValueError, match="empty"):
            extract_hostname("")

        with pytest.raises(ValueError, match="empty"):
            extract_hostname(None)  # type: ignore[arg-type]

    def test_raises_on_invalid_host(self):
        """Test ValueError on invalid host format."""
        with pytest.raises(ValueError, match="Invalid host"):
            extract_hostname("host; rm -rf /")

    def test_raises_on_invalid_url(self):
        """Test ValueError on invalid URL."""
        with pytest.raises(ValueError):
            extract_hostname("http://")

    def test_raises_on_non_http_protocol(self):
        """Test rejection of non-HTTP protocols."""
        # ftp:// should be treated as a hostname, not a URL
        # It will fail validation because of the ":"
        with pytest.raises(ValueError):
            extract_hostname("ftp://some.server")
