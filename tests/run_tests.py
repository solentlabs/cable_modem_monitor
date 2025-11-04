***REMOVED***!/usr/bin/env python3
"""Standalone test runner for Cable Modem Monitor scraper."""
import sys
import os
from bs4 import BeautifulSoup

***REMOVED*** Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'custom_components', 'cable_modem_monitor'))

from custom_components.cable_modem_monitor.core.modem_scraper import ModemScraper


def load_fixture(filename):
    """Load HTML fixture file."""
    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', filename)
    with open(fixture_path, 'r') as f:
        return f.read()


def test_downstream_channels():
    """Test parsing downstream channels."""
    print("Testing downstream channel parsing...")
    scraper = ModemScraper("192.168.100.1")
    html = load_fixture('moto_connection.html')
    soup = BeautifulSoup(html, 'html.parser')

    channels = scraper._parse_downstream_channels(soup)

    assert len(channels) == 24, f"Expected 24 downstream channels, got {len(channels)}"

    first_ch = channels[0]
    assert 'channel' in first_ch, "Missing 'channel' field"
    assert 'power' in first_ch, "Missing 'power' field"
    assert 'snr' in first_ch, "Missing 'snr' field"
    assert 'frequency' in first_ch, "Missing 'frequency' field"
    assert 'corrected' in first_ch, "Missing 'corrected' field"
    assert 'uncorrected' in first_ch, "Missing 'uncorrected' field"

    print(f"  ✓ Parsed {len(channels)} downstream channels")
    print(f"  ✓ Channel 1: Power={first_ch['power']} dBmV, SNR={first_ch['snr']} dB")
    return True


def test_upstream_channels():
    """Test parsing upstream channels."""
    print("Testing upstream channel parsing...")
    scraper = ModemScraper("192.168.100.1")
    html = load_fixture('moto_connection.html')
    soup = BeautifulSoup(html, 'html.parser')

    channels = scraper._parse_upstream_channels(soup)

    assert len(channels) > 0, "Should have at least one upstream channel"

    first_ch = channels[0]
    assert 'channel' in first_ch, "Missing 'channel' field"
    assert 'power' in first_ch, "Missing 'power' field"
    assert 'frequency' in first_ch, "Missing 'frequency' field"

    print(f"  ✓ Parsed {len(channels)} upstream channels")
    print(f"  ✓ Channel 1: Power={first_ch['power']} dBmV")
    return True


def test_software_version():
    """Test parsing software version."""
    print("Testing software version parsing...")
    scraper = ModemScraper("192.168.100.1")
    html = load_fixture('moto_home.html')
    soup = BeautifulSoup(html, 'html.parser')

    version = scraper._parse_software_version(soup)

    assert version != "Unknown", f"Should find software version, got '{version}'"
    assert version == "7621-5.7.1.5", f"Expected '7621-5.7.1.5', got '{version}'"

    print(f"  ✓ Software version: {version}")
    return True


def test_system_uptime():
    """Test parsing system uptime."""
    print("Testing system uptime parsing...")
    scraper = ModemScraper("192.168.100.1")
    html = load_fixture('moto_connection.html')
    soup = BeautifulSoup(html, 'html.parser')

    uptime = scraper._parse_system_uptime(soup)

    assert uptime != "Unknown", f"Should find system uptime, got '{uptime}'"
    assert "days" in uptime.lower() or "h:" in uptime, \
        f"Uptime should contain time info, got '{uptime}'"

    print(f"  ✓ System uptime: {uptime}")
    return True


def test_channel_counts():
    """Test parsing channel counts."""
    print("Testing channel count parsing...")
    scraper = ModemScraper("192.168.100.1")
    html = load_fixture('moto_home.html')
    soup = BeautifulSoup(html, 'html.parser')

    counts = scraper._parse_channel_counts(soup)

    assert counts['downstream'] is not None, "Should find downstream count"
    assert counts['upstream'] is not None, "Should find upstream count"
    assert counts['downstream'] == 24, \
        f"Expected 24 downstream channels, got {counts['downstream']}"
    assert counts['upstream'] == 5, \
        f"Expected 5 upstream channels, got {counts['upstream']}"

    print(f"  ✓ Downstream channels: {counts['downstream']}")
    print(f"  ✓ Upstream channels: {counts['upstream']}")
    return True


def test_error_totals():
    """Test error total calculations."""
    print("Testing error total calculations...")
    scraper = ModemScraper("192.168.100.1")
    html = load_fixture('moto_connection.html')
    soup = BeautifulSoup(html, 'html.parser')

    channels = scraper._parse_downstream_channels(soup)
    total_corrected = sum(ch.get("corrected", 0) for ch in channels)
    total_uncorrected = sum(ch.get("uncorrected", 0) for ch in channels)

    assert isinstance(total_corrected, int), "Total corrected should be int"
    assert isinstance(total_uncorrected, int), "Total uncorrected should be int"
    assert total_corrected >= 0, "Total corrected should be non-negative"
    assert total_uncorrected >= 0, "Total uncorrected should be non-negative"

    print(f"  ✓ Total corrected errors: {total_corrected:,}")
    print(f"  ✓ Total uncorrected errors: {total_uncorrected:,}")
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("Cable Modem Monitor - Test Suite")
    print("=" * 60)
    print()

    tests = [
        ("Downstream Channels", test_downstream_channels),
        ("Upstream Channels", test_upstream_channels),
        ("Software Version", test_software_version),
        ("System Uptime", test_system_uptime),
        ("Channel Counts", test_channel_counts),
        ("Error Totals", test_error_totals),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            test_func()
            passed += 1
            print()
        except AssertionError as e:
            print(f"  ✗ FAILED: {e}")
            print()
            failed += 1
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            print()
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
    else:
        print("\n✅ All tests passed!")
        sys.exit(0)


if __name__ == '__main__':
    main()
