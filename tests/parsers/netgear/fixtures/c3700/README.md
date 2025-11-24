# Netgear C3700-100NAS Test Fixtures

Complete HTML capture from a Netgear C3700-100NAS cable modem/router.

## Device Information

- **Model**: C3700-100NAS
- **Type**: DOCSIS 3.0 Cable Modem/Router Combo
- **Firmware Version**: V1.0.0.42_1.0.11
- **Hardware Version**: V2.02.18
- **Channel Bonding**: 24x8 (24 downstream, 8 upstream)
- **Authentication**: HTTP Basic Auth

## Capture Details

- **Initial Capture**: 2025-11-23 (modem offline, 21 pages)
- **DocsisStatus Update**: 2025-11-23 (modem online, channel data added)
- **Status**: Modem ONLINE with active DOCSIS connection
- **Total Pages**: 22 HTML pages (including DocsisStatus.htm)
- **Source**: Home Assistant diagnostics data

## Available Fixtures

### Core Pages
- `root.html` - Root page (401 unauthorized redirect)
- `index.htm` - Main page with navigation menu (80KB)
- `DashBoard.htm` - Dashboard overview (54KB)
- `Diagnostics.htm` - Network diagnostics tools (40KB)

### DOCSIS/Modem Pages
- `DocsisOffline.htm` - Offline error page (displayed when modem has no cable connection)
- `DocsisStatus.htm` - **✅ DOCSIS channel data** (40KB - REQUIRED for channel parsing)

### Router/WiFi Pages
- `WirelessSettings.htm` - WiFi configuration (161KB - largest page)
- `GuestNetwork.htm` - Guest network settings (111KB)
- `LANSetup.htm` - LAN configuration (46KB)
- `WANSetup.htm` - WAN setup (34KB)
- `RouterStatus.htm` - Router status (if available)

### Security/Access Control
- `AccessControl.htm` - Access control rules (52KB)
- `BlockSites.htm` - Site blocking configuration (26KB)

### Advanced Features
- `UPnP.htm` - UPnP settings (18KB)
- `UPnPMedia.htm` - UPnP media server (13KB)
- `DynamicDNS.htm` - DDNS configuration (76KB)
- `SpeedTest.htm` - Built-in speed test (15KB)

### Logs & Monitoring
- `Logs.htm` - System logs (52KB)
- `eventLog.htm` - Event log viewer (28KB)

### Management
- `BackupSettings.htm` - Backup/restore settings (13KB)
- `Schedule.htm` - Scheduling features (35KB)
- `document.htm` - Documentation/help (3KB)

### WiFi Setup
- `AddWPSClient_TOP.htm` - WPS client setup (11KB)

## Channel Data Format

### DocsisStatus.htm Structure

The C3700 embeds channel data in JavaScript functions with pipe-delimited values:

#### Downstream Channels
```javascript
function InitDsTableTagValue() {
    var tagValueList = '8|1|Locked|QAM256|1|345000000 Hz|2.9|46.3|289|320|2|Locked|QAM256|2|...';
    return tagValueList.split("|");
}
```

**Format:** `count|ch1_num|ch1_lock|ch1_mod|ch1_id|ch1_freq|ch1_power|ch1_snr|ch1_corr|ch1_uncorr|ch2_num|...`

**Fields per channel (9 total):**
1. Channel number (1-24)
2. Lock status ("Locked" or "Not Locked")
3. Modulation (e.g., "QAM256")
4. Channel ID (DOCSIS channel identifier)
5. Frequency (Hz, with " Hz" suffix)
6. Power level (dBmV)
7. SNR (dB)
8. Corrected errors (count)
9. Uncorrected errors (count)

#### Upstream Channels
```javascript
function InitUsTableTagValue() {
    var tagValueList = '4|1|Locked|ATDMA|1|5120000|30840000 Hz|47.5|2|Not Locked|ATDMA|...';
    return tagValueList.split("|");
}
```

**Format:** `count|ch1_num|ch1_lock|ch1_type|ch1_id|ch1_symrate|ch1_freq|ch1_power|ch2_num|...`

**Fields per channel (7 total):**
1. Channel number (1-8)
2. Lock status ("Locked" or "Not Locked")
3. Channel type (e.g., "ATDMA", "TDMA")
4. Channel ID (DOCSIS channel identifier)
5. Symbol rate (symbols/sec)
6. Frequency (Hz, with " Hz" suffix)
7. Power level (dBmV)

### Actual Channel Data (from live modem)

**Downstream:** 8 channels active (out of 24 possible)
- All 8 channels: **Locked** with QAM256 modulation
- Frequencies: 345-399 MHz
- Power levels: 2.8-3.3 dBmV
- SNR: 45.6-46.4 dB (excellent signal quality)
- Corrected errors: 125-320 per channel
- Uncorrected errors: 105-320 per channel

**Upstream:** 4 channels configured (out of 8 possible)
- **Only 1 channel locked** (channel 1)
- Channel 1: ATDMA, 30.84 MHz, 47.5 dBmV (locked)
- Channels 2-4: ATDMA, 0 Hz, 0.0 dBmV (not locked)

**Note:** The diagnostics page shows 4 upstream channels configured, but only channel 1 has an active lock and valid frequency/power readings. This is typical when the ISP has configured bonding but not all channels are in use.

## Important Notes

### Multi-Page Parsing Requirement

The C3700 requires **multi-page parsing** to extract channel data:
1. Initial page load: `/index.htm` or `/RouterStatus.htm` (detection and system info)
2. Channel data fetch: `/DocsisStatus.htm` (requires authenticated session)

The parser's `parse()` method accepts `session` and `base_url` parameters to fetch DocsisStatus.htm automatically

### Parser Implementation
The parser (`custom_components/cable_modem_monitor/parsers/netgear/c3700.py`) is fully
implemented and ready to parse channel data. It follows the same JavaScript extraction
pattern as the Netgear CM600:
- `InitDsTableTagValue()` function for downstream channels
- `InitUsTableTagValue()` function for upstream channels
- Pipe-delimited data format

### Usage for Testing
These fixtures can be used for:
1. **Parser detection testing** - Verify C3700 is correctly identified
2. **System info extraction** - Test hardware/firmware version parsing
3. **Error handling** - Test offline/degraded state handling
4. **Future development** - Reference for implementing additional features
5. **Device mocking** - Create mock responses for integration testing

### Key Differences from CM600
- Uses `.htm` extensions instead of `.asp`
- Combo modem/router (not modem-only)
- Additional router-specific pages (WiFi, LAN, WAN, Guest Network)
- More complex UI with extensive JavaScript

## Mock Server Implementation

These fixtures are ideal for creating a **mock HTTP server** for testing. Benefits:

### Why Mock Server?
1. **Integration Testing** - Test full request/response cycle without real hardware
2. **State Simulation** - Test online/offline transitions, channel degradation, etc.
3. **Error Scenarios** - Simulate timeouts, auth failures, partial data
4. **CI/CD Testing** - Run full integration tests in GitHub Actions
5. **Development Speed** - No need for physical modem during development

### Implementation Approach

```python
# Example mock server structure
class C3700MockServer:
    """Mock HTTP server simulating Netgear C3700 behavior."""

    def __init__(self, fixtures_path: str, state: str = "online"):
        self.fixtures = self._load_fixtures(fixtures_path)
        self.state = state  # "online", "offline", "degraded"
        self.auth_required = True

    def handle_request(self, path: str, auth: tuple) -> tuple[int, str]:
        """Return status code and HTML content for requested path."""
        # Simulate authentication
        if self.auth_required and path not in ["/", "/index.htm"]:
            if not auth or auth != ("admin", "password"):
                return (401, self.fixtures["root.html"])

        # State-based responses
        if self.state == "offline" and path == "/DocsisStatus.htm":
            return (200, self.fixtures["DocsisOffline.htm"])

        if path == "/DocsisStatus.htm" and self.state == "online":
            return (200, self.fixtures["DocsisStatus.htm"])

        # Default fixture lookup
        filename = path.lstrip("/") or "index.htm"
        return (200, self.fixtures.get(filename, "404 Not Found"))
```

### Test Scenarios to Implement
1. **Normal Operation** - Online modem with all channels locked
2. **Partial Service** - Some channels locked, others degraded
3. **Offline State** - No DOCSIS connection
4. **Authentication Failures** - Invalid credentials, session timeouts
5. **Network Issues** - Slow responses, connection resets
6. **Data Variations** - Different channel counts, error patterns

### Integration with pytest

```python
@pytest.fixture
def c3700_mock_server():
    """Provide mock C3700 server for integration tests."""
    server = C3700MockServer(fixtures_path="tests/parsers/netgear/fixtures/c3700")
    # Start server on random port
    # Return base_url
    yield base_url
    # Cleanup

def test_full_integration_with_mock(c3700_mock_server):
    """Test full scraper + parser flow with mock server."""
    scraper = ModemScraper(
        base_url=c3700_mock_server,
        username="admin",
        password="password"
    )
    data = scraper.get_modem_data()
    assert data["downstream_channel_count"] == 8
```

## Future Enhancements

### Short Term
- [x] ~~Capture `DocsisStatus.htm` for channel data~~ ✅ COMPLETED
- [x] ~~Update tests to validate channel parsing~~ ✅ COMPLETED
- [x] ~~Document actual channel data format~~ ✅ COMPLETED

### Long Term
- [ ] Implement mock HTTP server using fixtures
- [ ] Add state simulation (online/offline/degraded)
- [ ] Create integration tests using mock server
- [ ] Document variations in channel data (different ISPs, configurations)
- [ ] Add RouterStatus.htm parsing for additional metrics

## Related Files

- Parser: `custom_components/cable_modem_monitor/parsers/netgear/c3700.py`
- Tests: `tests/parsers/netgear/test_c3700.py`
- Similar device: `fixtures/cm600/` (modem-only version)
