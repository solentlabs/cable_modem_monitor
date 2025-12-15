# Cable Modem Monitor for Home Assistant

<!-- Status & Installation -->
[![GitHub Release](https://img.shields.io/github/v/release/solentlabs/cable_modem_monitor)](https://github.com/solentlabs/cable_modem_monitor/releases)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

<!-- Build Status -->
[![GitHub Actions](https://github.com/solentlabs/cable_modem_monitor/actions/workflows/tests.yml/badge.svg)](https://github.com/solentlabs/cable_modem_monitor/actions/workflows/tests.yml)
[![CodeQL](https://github.com/solentlabs/cable_modem_monitor/actions/workflows/codeql.yml/badge.svg)](https://github.com/solentlabs/cable_modem_monitor/actions/workflows/codeql.yml)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

<!-- Meta -->
[![AI Assisted](https://img.shields.io/badge/AI-Claude%20Assisted-5A67D8.svg)](https://claude.ai)
[![Help Add Your Modem](https://img.shields.io/badge/Help-Add%20Your%20Modem-brightgreen)](./docs/MODEM_REQUEST.md)

A custom Home Assistant integration that monitors cable modem signal quality, power levels, and error rates. Perfect for tracking your internet connection health and identifying potential issues before they cause problems.

<img src="images/dashboard-screenshot.png" alt="Cable Modem Health Dashboard" width="500">

*Monitor your cable modem's signal quality, errors, and connection health in real-time*

> **⭐ If you find this integration useful, please star this repo!**
> It helps others discover the project and shows that the integration is actively used.

> **🤖 AI-Assisted Development**: This project uses AI-assisted development (Claude) to accelerate implementation while maintaining human oversight for architecture and community decisions.

## Quick Links
- [**Installation Guide**](#installation)
- [**Supported Modems**](#supported-modems)
- [**Troubleshooting Guide**](./docs/TROUBLESHOOTING.md)
- [**Contributing Guide**](./CONTRIBUTING.md)
- [**Development**](#development) (for contributors)

---

## Development

**📖 See the [Getting Started Guide](./docs/setup/GETTING_STARTED.md)** for development environment setup.

Quick start:
```bash
git clone https://github.com/solentlabs/cable_modem_monitor.git
cd cable_modem_monitor
./scripts/setup.sh    # Local Python setup
# OR open in VS Code and click "Reopen in Container" for Dev Container
```

---

## At a Glance

**What it monitors:**
- 📊 **Signal Quality**: Power levels, SNR, frequency for every channel
- ⚠️ **Error Tracking**: Corrected & uncorrected errors per channel
- 🔌 **Connection Health**: Status, uptime, and last boot time
- 💓 **Modem Health**: Real-time ping and HTTP latency monitoring
- 📈 **Trends**: Full historical data for analysis and graphing

**What it does:**
- 🔄 **Remote Control**: Restart your modem from Home Assistant
- 🤖 **Automation Ready**: Trigger actions on signal degradation or errors
- 🔐 **Privacy First**: All local processing, automatic PII sanitization
- 🛡️ **Security Focused**: CodeQL scanned with 6 custom security queries
- 🔌 **Plug & Play**: Easy UI configuration, no YAML editing needed

### See It In Action

Track your cable modem's health with comprehensive dashboards and real-time monitoring:

<p align="center">
  <img src="images/dashboard-screenshot.png" alt="Cable Modem Health Dashboard" width="400"><br>
  <em>Complete dashboard showing connection status, signal quality, and error tracking</em>
</p>

<p align="center">
  <img src="images/downstream-power-levels.png" alt="Downstream Power Levels" width="500"><br>
  <em>Real-time power level monitoring across all downstream channels</em>
</p>

<p align="center">
  <img src="images/signal-to-noise-ratio.png" alt="Signal-to-Noise Ratio" width="500"><br>
  <em>SNR tracking helps identify signal quality issues before they cause problems</em>
</p>

<p align="center">
  <img src="images/latency.png" alt="Modem Latency Monitoring" width="500"><br>
  <em>Ping and HTTP latency monitoring for real-time health assessment</em>
</p>

<p align="center">
  <img src="images/corrected_errors.png" alt="Corrected Errors" width="500"><br>
  <em>Track corrected errors over time to spot developing line issues</em>
</p>

---

## Features

### Monitoring & Data Collection
- **Easy Setup**: Configure via Home Assistant UI - no YAML editing required
- **Comprehensive Channel Monitoring**: Tracks all downstream and upstream channels
- **Per-Channel Metrics**:
  - Power levels (dBmV)
  - Signal-to-Noise Ratio (SNR in dB)
  - Frequency (Hz)
  - Corrected/Uncorrected errors
- **Summary Sensors**: Total corrected and uncorrected errors across all channels
- **Unified Status**: Single sensor showing operational state (Operational/Degraded/Not Locked/Unresponsive)
- **System Information**: Software version, uptime, channel counts, and last boot time
- **Health Monitoring**: Real-time modem health checks with:
  - Ping latency monitoring
  - HTTP response time tracking
  - Automatic health status assessment
  - Circuit breaker pattern for reliability

### Control & Automation
- **Modem Control**: Restart your modem directly from Home Assistant
- **Automation-Friendly**: Last boot time sensor with timestamp device class for reboot detection
- **Consistent Entity Naming**: All entities use `cable_modem_` prefix for predictability
- **Historical Data**: All metrics are stored for trend analysis
- **Dashboard Ready**: Create graphs and alerts based on signal quality

### Developer Friendly
- **Extensible**: Plugin architecture makes adding new modem models easy
- **Well Tested**: 440+ test cases with comprehensive coverage
- **Type Safe**: Full type hints and mypy validation

## Supported Modems

This integration supports modems from ARRIS, Motorola, Netgear, and Technicolor. Compatibility varies based on firmware versions and ISP customizations.

> **📊 [View the Modem Fixture Library](./tests/parsers/FIXTURES.md)** - Complete list with DOCSIS versions, ISP compatibility, verification status, and model timelines.

### Fallback Mode
If your modem isn't listed, you can still install the integration! It will enter **Fallback Mode** which:
- Allows installation to succeed
- Enables the "Capture HTML" diagnostics button
- Lets you provide HTML samples to help add support for your modem
- See [How to Help Add Support](#how-to-help-add-support-for-your-modem) below

## Help Verify Modem Support

Using a modem marked with asterisk (*)? **[Report it working](https://github.com/solentlabs/cable_modem_monitor/issues/new?template=modem_verification.yml)** to help other users!

---

## How to Help Add Support for Your Modem

If your modem isn't supported or you'd like to help expand compatibility, we'd love your help!

**📖 See the [Modem Request Guide](./docs/MODEM_REQUEST.md)** for step-by-step instructions on capturing and submitting diagnostic data.

**Want to develop the parser yourself?** See the [Contributing Guide](./CONTRIBUTING.md) for details.



## Installation

### Method 1: HACS (Recommended)

**Prerequisites:** You must have HACS installed. If you don't have HACS yet:
1. Go to Settings → Add-ons → Add-on Store
2. Click three dots (⋮) → Repositories
3. Add: `https://github.com/hacs/addons`
4. Install and start the "Get HACS" add-on
5. Restart Home Assistant
6. Go to Settings → Devices & Services → Add Integration → Search for "HACS"
7. Complete HACS setup (requires free GitHub account)

**Installing Cable Modem Monitor via HACS:**

1. Open **HACS** from the Home Assistant sidebar
2. Click the **Integrations** tab
3. Click the **three dots (⋮)** in the top-right corner
4. Select **"Custom repositories"**
5. Add this repository URL: `https://github.com/solentlabs/cable_modem_monitor`
6. Category: **Integration**
7. Click **"Add"**
8. Search for **"Cable Modem Monitor"** in HACS
9. Click **"Download"**
10. **Restart Home Assistant**
11. Add the integration: **Settings → Devices & Services → Add Integration → Cable Modem Monitor**

### Method 2: Manual Installation

1. Download the [latest release](https://github.com/solentlabs/cable_modem_monitor/releases/latest)
2. Extract the zip file
3. Copy the `custom_components/cable_modem_monitor` folder to your Home Assistant's `config/custom_components/` directory
4. Restart Home Assistant
5. Go to Settings → Devices & Services
6. Click "+ Add Integration"
7. Search for "Cable Modem Monitor"
8. Enter your modem's IP address (typically `192.168.100.1`)

## Configuration

1. **Find your modem's IP address**: Usually `192.168.100.1` or `192.168.0.1`
2. **Verify web interface access**: Open `http://192.168.100.1` (or your modem's IP) in a browser
3. **Add the integration**:
   - Settings → Devices & Services → Add Integration
   - Search for "Cable Modem Monitor"
   - Enter the IP address

### Configuration Options

After installation, you can configure additional settings:

1. Go to **Settings → Devices & Services**
2. Find **Cable Modem Monitor** and click **Configure**
3. Available options:
   - **Modem IP Address**: Update if your modem's IP changes
   - **Username/Password**: Update authentication credentials
   - **Modem Model**: Select your modem model or use "auto" for automatic detection (recommended)
   - **Polling Interval**: How often to check modem status (60-1800 seconds, default: 600 - 10 minutes)
   - **History Retention**: Number of days to keep when using Clear History button (1-365 days, default: 30)

<img src="images/cable-modem-settings.png" alt="Cable Modem Configuration Settings" width="400">

*Configuration options available through the Settings UI*

---

## Available Sensors

All sensors use the `cable_modem_` prefix for consistent entity naming and easy identification.

**Entity Naming Pattern:**
- System sensors: `sensor.cable_modem_{metric}` (e.g., `sensor.cable_modem_status`)
- Channel sensors: `sensor.cable_modem_{direction}_ch_{number}_{metric}`
  - Example: `sensor.cable_modem_ds_ch_1_power` (downstream channel 1 power)
  - Example: `sensor.cable_modem_us_ch_3_frequency` (upstream channel 3 frequency)

### Modem Status
- `sensor.cable_modem_status`: Unified pass/fail status combining connection, health, and DOCSIS lock state
  - **Operational**: All good - data parsed, DOCSIS locked, reachable
  - **ICMP Blocked**: HTTP works but ping fails (check parser `supports_icmp` setting)
  - **Partial Lock**: Some downstream channels not locked
  - **Not Locked**: DOCSIS not locked to ISP
  - **Parser Error**: Modem reachable but data couldn't be parsed
  - **Unresponsive**: Can't reach modem via HTTP

### System Information
- `sensor.cable_modem_software_version`: Modem firmware/software version
- `sensor.cable_modem_system_uptime`: How long the modem has been running
- `sensor.cable_modem_last_boot_time`: When the modem last rebooted (timestamp device class)
- `sensor.cable_modem_ds_channel_count`: Number of active downstream channels
- `sensor.cable_modem_us_channel_count`: Number of active upstream channels

### Latency Monitoring
- `sensor.cable_modem_ping_latency`: Ping response time in milliseconds
- `sensor.cable_modem_http_latency`: HTTP response time in milliseconds

### Summary Sensors
- `sensor.cable_modem_total_corrected_errors`: Total corrected errors across all downstream channels
- `sensor.cable_modem_total_uncorrected_errors`: Total uncorrected errors across all downstream channels

### Per-Channel Downstream Sensors (for each channel)
Replace `X` with the channel number (1-32 depending on your modem):
- `sensor.cable_modem_downstream_ch_X_power`: Power level in dBmV
- `sensor.cable_modem_downstream_ch_X_snr`: Signal-to-Noise Ratio in dB
- `sensor.cable_modem_downstream_ch_X_frequency`: Channel frequency in Hz
- `sensor.cable_modem_downstream_ch_X_corrected`: Corrected errors
- `sensor.cable_modem_downstream_ch_X_uncorrected`: Uncorrected errors

### Per-Channel Upstream Sensors (for each channel)
Replace `X` with the channel number (1-8 depending on your modem):
- `sensor.cable_modem_upstream_ch_X_power`: Transmit power level in dBmV
- `sensor.cable_modem_upstream_ch_X_frequency`: Channel frequency in Hz

### Controls
- `button.cable_modem_restart_modem`: Restart your cable modem remotely

### Services
- `cable_modem_monitor.clear_history`: Clear old historical data (keeps specified number of days)
- `cable_modem_monitor.cleanup_entities`: Remove orphaned entities from registry (useful after upgrades)

## Understanding the Values

### Downstream Power (dBmV)
- **Ideal range**: -7 to +7 dBmV
- **Acceptable**: -15 to +15 dBmV
- **Poor**: Below -15 or above +15 dBmV

### Signal-to-Noise Ratio (dB)
- **Excellent**: Above 40 dB
- **Good**: 33-40 dB
- **Acceptable**: 25-33 dB
- **Poor**: Below 25 dB

### Upstream Power (dBmV)
- **Ideal range**: 35-50 dBmV
- **Acceptable**: 30-55 dBmV
- **Poor**: Below 30 or above 55 dBmV

### Corrected vs Uncorrected Errors
- **Corrected errors**: Normal in small amounts; modem can fix these
- **Uncorrected errors**: Indicate data loss; any sustained increase is concerning
- **Monitor trends**: Sudden increases may indicate line issues

## Examples

Ready-to-use dashboard and automation examples are available in the **[Examples Guide](./docs/EXAMPLES.md)**.

Includes:
- Complete dashboard YAML for monitoring all channels
- Automations for error alerts, SNR warnings, and auto-restart
- Last boot time display format options

## Troubleshooting

**📖 See the [Troubleshooting Guide](./docs/TROUBLESHOOTING.md)** for solutions to common issues including connection problems, missing sensors, and duplicate entities.

## Contributing

Contributions are welcome! If you have:
- Support for additional modem models
- Bug fixes
- Feature improvements

Please see the [Contributing Guide](./CONTRIBUTING.md) for details on how to add support for your modem, run tests, and submit changes.

## Privacy & Security

### Privacy Protection
- **100% Local**: All data stays on your Home Assistant instance - no cloud services
- **Read-Only**: Only reads data from your modem (never modifies configuration)
- **PII Sanitization**: Automatic removal of sensitive data from diagnostics
  - IP addresses, MAC addresses, serial numbers automatically redacted
  - Safe to share diagnostic files for support
- **Secure Credentials**: Stored in Home Assistant's encrypted storage

### Security Features
- **CodeQL Scanning**: Automated security analysis on every commit
  - 100+ standard security queries (OWASP Top 10, CWE coverage)
  - 6 custom security queries specific to cable modem integration:
    - HTTP requests without timeouts
    - Command injection prevention
    - XML External Entity (XXE) protection
    - Hardcoded credential detection
    - SSL/TLS misconfiguration checks
    - Path traversal prevention
- **Security Documentation**: See [CodeQL Testing Guide](./docs/reference/CODEQL_TESTING_GUIDE.md) for details
- **Vulnerability Reporting**: See [SECURITY.md](./SECURITY.md) for responsible disclosure

### Authentication Support
- HTTP Basic Authentication
- Form-based authentication
- HNAP/SOAP authentication
- No authentication (for open modems)

## License

MIT License - see LICENSE file for details

## Support

- [GitHub Issues](https://github.com/solentlabs/cable_modem_monitor/issues)
- [Home Assistant Community Forum](https://community.home-assistant.io/)

## Resources

### Project Documentation
- [Changelog](./CHANGELOG.md) - Version history and release notes
- [Contributing Guide](./CONTRIBUTING.md) - How to contribute code or add modem support
- [Troubleshooting Guide](./docs/TROUBLESHOOTING.md) - Common issues and solutions
- [Examples](./docs/EXAMPLES.md) - Dashboard and automation YAML
- [Modem Request Guide](./docs/MODEM_REQUEST.md) - Help add support for your modem
- [AI Context](./AI_CONTEXT.md) - Project context for AI assistants

### External Resources
- [Home Assistant Releases](https://github.com/home-assistant/core/releases)
- [HACS Brand Repository](https://github.com/home-assistant/brands/tree/master/custom_integrations/cable_modem_monitor)

## Credits

Created for monitoring Cox Cable Motorola modems, but designed to work with various cable modem brands.

---

## Legal & Safety

**⚠️ Disclaimer:**
This integration interacts with the **user-facing diagnostic interface** (LAN side) of your modem. It does not modify boot files, interact with the ISP side (WAN), or bypass any service limits.

Solent Labs™ is not affiliated with Arris, Motorola, Netgear, or any ISP. All product names are trademarks of their respective owners. Use this software at your own risk.
