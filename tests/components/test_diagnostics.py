"""Tests for Cable Modem Monitor diagnostics platform."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.cable_modem_monitor.const import DOMAIN
from custom_components.cable_modem_monitor.diagnostics import (
    _sanitize_html,
    _sanitize_log_message,
    async_get_config_entry_diagnostics,
)


class TestSanitizeHtml:
    """Test HTML sanitization function."""

    def test_sanitize_html_removes_mac_addresses(self):
        """Test that MAC addresses are sanitized."""
        html = """
        <tr><td>MAC Address</td><td>AA:BB:CC:DD:EE:FF</td></tr>
        <tr><td>HFC MAC</td><td>11-22-33-44-55-66</td></tr>
        """
        sanitized = _sanitize_html(html)

        assert "AA:BB:CC:DD:EE:FF" not in sanitized
        assert "11-22-33-44-55-66" not in sanitized
        assert "XX:XX:XX:XX:XX:XX" in sanitized

    def test_sanitize_html_removes_serial_numbers(self):
        """Test that serial numbers are sanitized."""
        test_cases = [
            ("Serial Number: 123456789ABC", "Serial Number: ***REDACTED***"),
            ("S/N: XYZ-999-ABC", "S/N: ***REDACTED***"),
            ("SN: 111222333", "SN: ***REDACTED***"),
        ]

        for original, expected_pattern in test_cases:
            sanitized = _sanitize_html(original)
            assert expected_pattern in sanitized
            assert original not in sanitized

    def test_sanitize_html_removes_account_ids(self):
        """Test that account/subscriber IDs are sanitized."""
        test_cases = [
            "Account ID: 123456789",
            "Subscriber Number: ABC-999-XYZ",
            "Customer ID: TEST-CUSTOMER-001",
            "Device Number: DEV123456",
        ]

        for original in test_cases:
            sanitized = _sanitize_html(original)
            assert "***REDACTED***" in sanitized
            # Original ID should be removed (check for the digits/unique part)
            assert not any(
                char.isdigit() for word in sanitized.split("***REDACTED***") for char in word if char.isalnum()
            )

    def test_sanitize_html_removes_private_ips(self):
        """Test that private IP addresses are sanitized."""
        test_cases = [
            ("Gateway: 10.0.1.1", "Gateway: ***PRIVATE_IP***"),
            ("Server: 172.16.5.10", "Server: ***PRIVATE_IP***"),
            ("Host: 192.168.50.100", "Host: ***PRIVATE_IP***"),
        ]

        for original, expected in test_cases:
            sanitized = _sanitize_html(original)
            assert expected in sanitized
            # Extract the original IP and verify it's gone
            original_ip = original.split(": ")[1]
            assert original_ip not in sanitized

    def test_sanitize_html_preserves_common_modem_ips(self):
        """Test that common modem IPs are preserved for debugging."""
        common_ips = [
            "192.168.100.1",  # Common Motorola modem IP
            "192.168.0.1",  # Common router IP
            "192.168.1.1",  # Common router IP
        ]

        for ip in common_ips:
            html = f"<td>Modem IP: {ip}</td>"
            sanitized = _sanitize_html(html)
            assert ip in sanitized  # Should be preserved

    def test_sanitize_html_removes_passwords(self):
        """Test that passwords and passphrases are sanitized."""
        test_cases = [
            'password="secret123"',
            "passphrase: MySecretPass",
            'psk="wireless-key-123"',
            "wpa2key: SuperSecret!",
        ]

        for original in test_cases:
            sanitized = _sanitize_html(original)
            assert "***REDACTED***" in sanitized
            assert "secret" not in sanitized.lower() or "***REDACTED***" in sanitized

    def test_sanitize_html_removes_password_form_values(self):
        """Test that password input field values are sanitized."""
        html = '<input type="password" name="pwd" value="MyPassword123">'
        sanitized = _sanitize_html(html)

        assert "MyPassword123" not in sanitized
        assert "***REDACTED***" in sanitized
        assert 'type="password"' in sanitized  # Structure preserved

    def test_sanitize_html_removes_session_tokens(self):
        """Test that session tokens and auth tokens are sanitized."""
        html = """
        <meta name="csrf-token" content="abc123def456ghi789jkl012mno345pqr678stu">
        session=xyz999abc888def777ghi666
        """
        sanitized = _sanitize_html(html)

        assert "abc123def456ghi789jkl012mno345pqr678stu" not in sanitized
        assert "xyz999abc888def777ghi666" not in sanitized
        assert "***REDACTED***" in sanitized

    def test_sanitize_html_preserves_signal_data(self):
        """Test that signal quality data is preserved for debugging."""
        html = """
        <tr>
            <td>Power Level</td><td>7.0 dBmV</td>
            <td>SNR</td><td>40.0 dB</td>
            <td>Frequency</td><td>555000000 Hz</td>
        </tr>
        """
        sanitized = _sanitize_html(html)

        # Signal data should be preserved
        assert "7.0 dBmV" in sanitized
        assert "40.0 dB" in sanitized
        assert "555000000 Hz" in sanitized

    def test_sanitize_html_preserves_channel_ids(self):
        """Test that channel IDs and counts are preserved."""
        html = """
        <tr><td>Channel ID</td><td>23</td></tr>
        <tr><td>Downstream Channels</td><td>32</td></tr>
        <tr><td>Corrected Errors</td><td>12345</td></tr>
        """
        sanitized = _sanitize_html(html)

        assert "Channel ID" in sanitized
        assert "23" in sanitized
        assert "32" in sanitized
        assert "12345" in sanitized

    def test_sanitize_html_handles_multiple_macs(self):
        """Test sanitization of multiple MAC addresses in same HTML."""
        html = """
        WAN MAC: AA:BB:CC:DD:EE:FF
        LAN MAC: 11:22:33:44:55:66
        WIFI MAC: 99-88-77-66-55-44
        """
        sanitized = _sanitize_html(html)

        # All MACs should be sanitized
        assert "AA:BB:CC:DD:EE:FF" not in sanitized
        assert "11:22:33:44:55:66" not in sanitized
        assert "99-88-77-66-55-44" not in sanitized
        # Should have 3 XX:XX:XX:XX:XX:XX replacements
        assert sanitized.count("XX:XX:XX:XX:XX:XX") == 3

    def test_sanitize_html_handles_empty_string(self):
        """Test that empty string is handled gracefully."""
        sanitized = _sanitize_html("")
        assert sanitized == ""

    def test_sanitize_html_handles_no_sensitive_data(self):
        """Test HTML with no sensitive data passes through mostly unchanged."""
        html = """
        <tr><td>Power</td><td>5.0 dBmV</td></tr>
        <tr><td>SNR</td><td>38 dB</td></tr>
        """
        sanitized = _sanitize_html(html)

        # Should be largely unchanged
        assert "5.0 dBmV" in sanitized
        assert "38 dB" in sanitized


class TestSanitizeLogMessage:
    """Test log message sanitization function."""

    def test_sanitize_log_removes_credentials(self):
        """Test that credentials are removed from log messages."""
        test_cases = [
            "password=secret123",
            "username: admin",
            "token=abc123xyz",
        ]

        for message in test_cases:
            sanitized = _sanitize_log_message(message)
            assert "***REDACTED***" in sanitized

    def test_sanitize_log_removes_file_paths(self):
        """Test that file paths are sanitized."""
        message = "Error in /config/custom_components/test.py and /home/user/.homeassistant/test.log"
        sanitized = _sanitize_log_message(message)

        assert "/config/***PATH***" in sanitized
        assert "/home/***PATH***" in sanitized
        assert "/config/custom_components/test.py" not in sanitized

    def test_sanitize_log_removes_private_ips(self):
        """Test that private IPs are removed but common modem IPs preserved."""
        message = "Connecting to 10.0.0.1 and 192.168.100.1 and 172.16.5.5"
        sanitized = _sanitize_log_message(message)

        # Private IPs should be sanitized except common modem IP
        assert "10.0.0.1" not in sanitized
        assert "172.16.5.5" not in sanitized
        assert "192.168.100.1" in sanitized  # Preserved
        assert "***PRIVATE_IP***" in sanitized


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = Mock(spec=ConfigEntry)
    entry.entry_id = "test_entry"
    entry.title = "Test Modem"
    entry.data = {
        "host": "192.168.100.1",
        "username": "admin",
        "password": "secret",
        "modem_choice": "Motorola MB8611",
        "detected_modem": "MB8611",
        "detected_manufacturer": "Motorola",
        "parser_name": "Motorola MB8611 (Static)",
        "working_url": "https://192.168.100.1/MotoConnection.asp",
        "last_detection": "2025-11-11T10:00:00",
    }
    return entry


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = Mock(spec=DataUpdateCoordinator)
    coordinator.last_update_success = True
    coordinator.update_interval = timedelta(seconds=600)
    coordinator.last_exception = None
    coordinator.data = {
        "cable_modem_connection_status": "online",
        "cable_modem_downstream_channel_count": 32,
        "cable_modem_upstream_channel_count": 4,
        "cable_modem_downstream": [
            {"channel_id": 1, "frequency": 555000000, "power": 7.0, "snr": 40.0, "corrected": 100, "uncorrected": 0},
        ],
        "cable_modem_upstream": [
            {"channel_id": 1, "frequency": 35000000, "power": 45.0},
        ],
        "cable_modem_total_corrected": 100,
        "cable_modem_total_uncorrected": 0,
        "cable_modem_software_version": "3.0.1",
        "cable_modem_system_uptime": "5 days",
    }
    return coordinator


@pytest.mark.asyncio
async def test_diagnostics_basic_structure(mock_config_entry, mock_coordinator):
    """Test basic diagnostics structure without HTML capture."""
    hass = Mock(spec=HomeAssistant)
    hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    # Verify basic structure
    assert "config_entry" in diagnostics
    assert "coordinator" in diagnostics
    assert "modem_data" in diagnostics
    assert "downstream_channels" in diagnostics
    assert "upstream_channels" in diagnostics

    # Verify config entry data
    assert diagnostics["config_entry"]["title"] == "Test Modem"
    assert diagnostics["config_entry"]["host"] == "192.168.100.1"
    assert diagnostics["config_entry"]["has_credentials"] is True

    # Verify modem data
    assert diagnostics["modem_data"]["connection_status"] == "online"
    assert diagnostics["modem_data"]["downstream_channel_count"] == 32


@pytest.mark.asyncio
async def test_diagnostics_includes_html_capture_not_expired(mock_config_entry, mock_coordinator):
    """Test diagnostics includes HTML capture when available and not expired."""
    hass = Mock(spec=HomeAssistant)
    hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}

    # Add HTML capture to coordinator data (not expired)
    future_time = datetime.now() + timedelta(minutes=3)
    mock_coordinator.data["_raw_html_capture"] = {
        "timestamp": datetime.now().isoformat(),
        "trigger": "manual",
        "ttl_expires": future_time.isoformat(),
        "urls": [
            {
                "url": "https://192.168.100.1/MotoConnection.asp",
                "method": "GET",
                "status_code": 200,
                "content_type": "text/html",
                "size_bytes": 12450,
                "html": """
                <html>
                    <tr><td>MAC</td><td>AA:BB:CC:DD:EE:FF</td></tr>
                    <tr><td>Power</td><td>7.0 dBmV</td></tr>
                    <tr><td>Serial Number</td><td>ABC123XYZ</td></tr>
                </html>
                """,
                "parser": "Motorola MB8611",
            }
        ],
    }

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    # Verify HTML capture is included
    assert "raw_html_capture" in diagnostics
    assert diagnostics["raw_html_capture"]["url_count"] == 1
    assert diagnostics["raw_html_capture"]["trigger"] == "manual"

    # Verify sanitization occurred
    captured_html = diagnostics["raw_html_capture"]["urls"][0]["html"]
    assert "AA:BB:CC:DD:EE:FF" not in captured_html  # MAC removed
    assert "XX:XX:XX:XX:XX:XX" in captured_html  # MAC sanitized
    assert "ABC123XYZ" not in captured_html  # Serial removed
    assert "***REDACTED***" in captured_html  # Serial sanitized
    assert "7.0 dBmV" in captured_html  # Signal data preserved


@pytest.mark.asyncio
async def test_diagnostics_includes_multiple_page_capture(mock_config_entry, mock_coordinator):
    hass = Mock(spec=HomeAssistant)
    hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}

    # Add HTML capture with multiple pages (login, status, software info, event log)
    future_time = datetime.now() + timedelta(minutes=3)
    mock_coordinator.data["_raw_html_capture"] = {
        "timestamp": datetime.now().isoformat(),
        "trigger": "manual",
        "ttl_expires": future_time.isoformat(),
        "urls": [
            {
                "url": "https://192.168.100.1/login.html",
                "method": "GET",
                "status_code": 200,
                "content_type": "text/html",
                "size_bytes": 5432,
                "html": "<html><form action='/login'>Username: <input name='user'></form></html>",
                "parser": "Motorola MB8611",
                "description": "Login/Auth page",
            },
            {
                "url": "https://192.168.100.1/login.html",
                "method": "POST",
                "status_code": 302,
                "content_type": "text/html",
                "size_bytes": 150,
                "html": "<html><body>Redirecting...</body></html>",
                "parser": "Motorola MB8611",
                "description": "Login/Auth page",
            },
            {
                "url": "https://192.168.100.1/MotoConnection.asp",
                "method": "GET",
                "status_code": 200,
                "content_type": "text/html",
                "size_bytes": 12450,
                "html": """
                <html>
                    <tr><td>MAC</td><td>AA:BB:CC:DD:EE:FF</td></tr>
                    <tr><td>Power</td><td>7.0 dBmV</td></tr>
                </html>
                """,
                "parser": "Motorola MB8611",
                "description": "Initial connection page",
            },
            {
                "url": "https://192.168.100.1/MotoStatusSoftware.asp",
                "method": "GET",
                "status_code": 200,
                "content_type": "text/html",
                "size_bytes": 3200,
                "html": "<html><tr><td>Software Version</td><td>3.0.1</td></tr></html>",
                "parser": "Motorola MB8611",
                "description": "Software info page",
            },
            {
                "url": "https://192.168.100.1/MotoEventLog.asp",
                "method": "GET",
                "status_code": 200,
                "content_type": "text/html",
                "size_bytes": 8900,
                "html": "<html><tr><td>Event</td><td>Connection established</td></tr></html>",
                "parser": "Motorola MB8611",
                "description": "Event log page",
            },
        ],
    }

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    # Verify HTML capture is included with all pages
    assert "raw_html_capture" in diagnostics
    assert diagnostics["raw_html_capture"]["url_count"] == 5
    assert diagnostics["raw_html_capture"]["trigger"] == "manual"

    # Verify all page types are present
    urls = diagnostics["raw_html_capture"]["urls"]
    descriptions = [url.get("description", "") for url in urls]
    assert "Login/Auth page" in descriptions
    assert "Initial connection page" in descriptions
    assert "Software info page" in descriptions
    assert "Event log page" in descriptions

    # Verify both GET and POST methods are captured
    methods = [url.get("method") for url in urls]
    assert "GET" in methods
    assert "POST" in methods

    # Verify sanitization occurred across all pages
    for url_data in urls:
        html = url_data.get("html", "")
        if "AA:BB:CC:DD:EE:FF" in mock_coordinator.data["_raw_html_capture"]["urls"][urls.index(url_data)]["html"]:
            # Original MAC should be removed, replacement should be present
            assert "AA:BB:CC:DD:EE:FF" not in html
            assert "XX:XX:XX:XX:XX:XX" in html


@pytest.mark.asyncio
async def test_diagnostics_excludes_expired_html_capture(mock_config_entry, mock_coordinator):
    """Test diagnostics excludes HTML capture when expired."""
    hass = Mock(spec=HomeAssistant)
    hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}

    # Add HTML capture to coordinator data (expired)
    past_time = datetime.now() - timedelta(minutes=10)
    mock_coordinator.data["_raw_html_capture"] = {
        "timestamp": past_time.isoformat(),
        "trigger": "manual",
        "ttl_expires": past_time.isoformat(),
        "urls": [
            {
                "url": "https://192.168.100.1/MotoConnection.asp",
                "html": "<html>test</html>",
            }
        ],
    }

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    # Verify HTML capture is NOT included (expired)
    assert "raw_html_capture" not in diagnostics


@pytest.mark.asyncio
async def test_diagnostics_without_html_capture(mock_config_entry, mock_coordinator):
    """Test diagnostics works normally when no HTML capture present."""
    hass = Mock(spec=HomeAssistant)
    hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}

    # Ensure no HTML capture in coordinator data
    assert "_raw_html_capture" not in mock_coordinator.data

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    # Should work fine without HTML capture
    assert "config_entry" in diagnostics
    assert "modem_data" in diagnostics
    assert "raw_html_capture" not in diagnostics


@pytest.mark.asyncio
async def test_diagnostics_handles_coordinator_without_data(mock_config_entry, mock_coordinator):
    # Create coordinator with no data
    coordinator = Mock(spec=DataUpdateCoordinator)
    coordinator.last_update_success = False
    coordinator.update_interval = timedelta(seconds=600)
    coordinator.last_exception = Exception("Connection failed")
    coordinator.data = None

    hass = Mock(spec=HomeAssistant)
    hass.data = {DOMAIN: {mock_config_entry.entry_id: coordinator}}

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    # Should still return basic structure
    assert "config_entry" in diagnostics
    assert "coordinator" in diagnostics
    assert "last_error" in diagnostics
    assert diagnostics["last_error"]["message"] is not None


@pytest.mark.asyncio
async def test_diagnostics_sanitizes_exception_messages(mock_config_entry, mock_coordinator):
    """Test that exception messages are sanitized."""
    hass = Mock(spec=HomeAssistant)
    hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}

    # Add exception with sensitive data
    mock_coordinator.last_exception = Exception("Failed to connect to 10.0.0.5 with password=secret123")

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    # Verify exception is included but sanitized
    assert "last_error" in diagnostics
    error_msg = diagnostics["last_error"]["message"]
    assert "***REDACTED***" in error_msg
    assert "secret123" not in error_msg
    assert "***PRIVATE_IP***" in error_msg or "10.0.0.5" not in error_msg
