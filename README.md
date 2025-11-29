***REMOVED*** Cable Modem Monitor for Home Assistant

<!-- Status & Installation -->
[![GitHub Release](https://img.shields.io/github/v/release/kwschulz/cable_modem_monitor)](https://github.com/kwschulz/cable_modem_monitor/releases)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

<!-- Build Status -->
[![GitHub Actions](https://github.com/kwschulz/cable_modem_monitor/actions/workflows/tests.yml/badge.svg)](https://github.com/kwschulz/cable_modem_monitor/actions/workflows/tests.yml)
[![CodeQL](https://github.com/kwschulz/cable_modem_monitor/actions/workflows/codeql.yml/badge.svg)](https://github.com/kwschulz/cable_modem_monitor/actions/workflows/codeql.yml)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

<!-- Meta -->
[![AI Assisted](https://img.shields.io/badge/AI-Claude%20Assisted-5A67D8.svg)](https://claude.ai)
[![Help Add Your Modem](https://img.shields.io/badge/Help-Add%20Your%20Modem-brightgreen)](./docs/HAR_CAPTURE_GUIDE.md)

A custom Home Assistant integration that monitors cable modem signal quality, power levels, and error rates. Perfect for tracking your internet connection health and identifying potential issues before they cause problems.

![Cable Modem Health Dashboard](images/dashboard-screenshot.png)

*Monitor your cable modem's signal quality, errors, and connection health in real-time*

> **⭐ If you find this integration useful, please star this repo!**
> It helps others discover the project and shows that the integration is actively used.

> **🤖 AI-Assisted Development**: This project uses AI-assisted development (Claude) to accelerate implementation while maintaining human oversight for architecture and community decisions.

***REMOVED******REMOVED*** Quick Links
- [**Installation Guide**](***REMOVED***installation)
- [**Supported Modems**](***REMOVED***supported-modems)
- [**Troubleshooting Guide**](./docs/TROUBLESHOOTING.md)
- [**Contributing Guide**](./CONTRIBUTING.md)
- [**Development Setup**](***REMOVED***development-setup) (for contributors)

---

***REMOVED******REMOVED*** Development Setup

***REMOVED******REMOVED******REMOVED*** Quick Start (2 options)

**Option 1: Local Python (Fastest)**
```bash
git clone https://github.com/kwschulz/cable_modem_monitor.git
cd cable_modem_monitor
./scripts/setup.sh    ***REMOVED*** Installs dependencies in .venv
code .                ***REMOVED*** Opens in VS Code - that's it!
```

**Option 2: Dev Container (Zero setup)**
```bash
git clone https://github.com/kwschulz/cable_modem_monitor.git
cd cable_modem_monitor
code .                ***REMOVED*** Opens in VS Code
***REMOVED*** Click "Reopen in Container" when prompted (wait 2-3 min first time)
```

**Both work identically** - choose based on preference. See [Getting Started Guide](./docs/GETTING_STARTED.md) for detailed comparison and troubleshooting.

***REMOVED******REMOVED******REMOVED*** After Opening in VS Code

***REMOVED******REMOVED******REMOVED******REMOVED*** What You'll See

**Notifications:**

| Notification | Action |
|--------------|--------|
| "Dev Container configuration available..." | **Option A:** Click "Reopen in Container" (no setup needed)<br>**Option B:** Dismiss and use local Python |
| "Install recommended extensions?" | Click **"Install"** (Python, Ruff, Black, YAML) |
| "GitLens" or "CodeQL" | **Optional** - dismiss if you don't need them |

**Terminal Window:**
- If `.venv` doesn't exist yet, you'll see friendly setup instructions
- Run `bash scripts/setup.sh` to set up (takes ~2 minutes)
- After setup, close and reopen the terminal - it will auto-activate `.venv`

Then validate everything works:
```bash
***REMOVED*** In terminal OR use VS Code task (Ctrl+Shift+P → Tasks → Quick Validation)
make validate
```

**Having issues?** See [Getting Started Guide](./docs/GETTING_STARTED.md) for detailed troubleshooting.

**Testing fresh developer experience?** Run `python scripts/dev/fresh_start.py` to reset VS Code state.

Full guides: [Getting Started](./docs/GETTING_STARTED.md) | [Contributing](./CONTRIBUTING.md) | [Developer Quickstart](./docs/DEVELOPER_QUICKSTART.md)

---

***REMOVED******REMOVED*** At a Glance

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

***REMOVED******REMOVED******REMOVED*** See It In Action

Track your cable modem's health with comprehensive dashboards and real-time monitoring:

<p align="center">
  <img src="images/dashboard-screenshot.png" alt="Cable Modem Health Dashboard" width="600"><br>
  <em>Complete dashboard showing connection status, signal quality, and error tracking</em>
</p>

<p align="center">
  <img src="images/downstream-power-levels.png" alt="Downstream Power Levels" width="600"><br>
  <em>Real-time power level monitoring across all downstream channels</em>
</p>

<p align="center">
  <img src="images/signal-to-noise-ratio.png" alt="Signal-to-Noise Ratio" width="600"><br>
  <em>SNR tracking helps identify signal quality issues before they cause problems</em>
</p>

---

***REMOVED******REMOVED*** Features

***REMOVED******REMOVED******REMOVED*** Monitoring & Data Collection
- **Easy Setup**: Configure via Home Assistant UI - no YAML editing required
- **Comprehensive Channel Monitoring**: Tracks all downstream and upstream channels
- **Per-Channel Metrics**:
  - Power levels (dBmV)
  - Signal-to-Noise Ratio (SNR in dB)
  - Frequency (Hz)
  - Corrected/Uncorrected errors
- **Summary Sensors**: Total corrected and uncorrected errors across all channels
- **Connection Status**: Monitor modem online/offline state
- **System Information**: Software version, uptime, channel counts, and last boot time
- **Health Monitoring**: Real-time modem health checks with:
  - Ping latency monitoring
  - HTTP response time tracking
  - Automatic health status assessment
  - Circuit breaker pattern for reliability

***REMOVED******REMOVED******REMOVED*** Control & Automation
- **Modem Control**: Restart your modem directly from Home Assistant
- **Automation-Friendly**: Last boot time sensor with timestamp device class for reboot detection
- **Consistent Entity Naming**: All entities use `cable_modem_` prefix for predictability
- **Historical Data**: All metrics are stored for trend analysis
- **Dashboard Ready**: Create graphs and alerts based on signal quality

***REMOVED******REMOVED******REMOVED*** Privacy & Security
- **Privacy First**: All data stays local, automatic PII sanitization
- **Security Scanned**: CodeQL security analysis with 6 custom security queries
- **Secure Storage**: Credentials stored in Home Assistant's encrypted storage
- **Safe Diagnostics**: HAR capture tools with automatic credential removal

***REMOVED******REMOVED******REMOVED*** Developer Friendly
- **Extensible**: Plugin architecture makes adding new modem models easy
- **Well Tested**: 440+ test cases with comprehensive coverage
- **Type Safe**: Full type hints and mypy validation

***REMOVED******REMOVED*** Supported Modems

This integration relies on community contributions for modem support. Compatibility varies based on firmware versions and ISP customizations.

> **📊 [View the Modem Fixture Library](./tests/parsers/FIXTURES.md)** - Visual timeline of all supported modems with DOCSIS versions, ISP compatibility, and verification status.

***REMOVED******REMOVED******REMOVED*** ✅ Verified Working
These models have been confirmed working with real hardware:

| Model | Verification | Features |
|-------|-------------|----------|
| **Arris SB6141** | Community verified ([forum](https://community.home-assistant.io/t/cable-modem-monitor-track-your-internet-signal-quality-in-home-assistant)) | Full channel data, system info |
| **Motorola MB7621** | Maintainer verified | Full channel data, system info, restart |
| **Netgear C3700** | Maintainer verified | Full channel data, system info (combo modem/router) |
| **Netgear CM600** | User verified ([Issue ***REMOVED***3](https://github.com/kwschulz/cable_modem_monitor/issues/3)) | 24 DS / 8 US channels, system info, restart |

***REMOVED******REMOVED******REMOVED*** ⚠️ Unverified Parsers
These parsers exist but need user confirmation:

| Model | Status | Notes |
|-------|--------|-------|
| **Arris SB6190** | Needs testing | Parser based on SB6141, no user reports yet |
| **Motorola MB8611** | Needs testing | HNAP auth added in v3.8.0, awaiting verification ([Issue ***REMOVED***6](https://github.com/kwschulz/cable_modem_monitor/issues/6)) |
| **Netgear CM2000** | Needs testing | Parser added in v3.8.0, awaiting verification ([Issue ***REMOVED***38](https://github.com/kwschulz/cable_modem_monitor/issues/38)) |
| **Technicolor XB7 (CGM4331COM)** | Needs testing | Parser exists, needs user verification |
| **Technicolor TC4400** | Needs testing | See [Issue ***REMOVED***1](https://github.com/kwschulz/cable_modem_monitor/issues/1) |
| **Motorola Generic** | Needs testing | May work with other Motorola DOCSIS 3.x modems |

***REMOVED******REMOVED******REMOVED*** ❌ Known Issues
These parsers have confirmed problems:

| Model | Issue | Status |
|-------|-------|--------|
| **Motorola MB8600** | HNAP authentication broken | See [Issue ***REMOVED***40](https://github.com/kwschulz/cable_modem_monitor/issues/40) - Newer firmware uses HNAP_AUTH header, 3-strike login lockout |

**Note**: Unverified parsers will be marked as such in the UI during setup.

***REMOVED******REMOVED******REMOVED*** 🔄 On Hold
- **Arris/CommScope S33** - Uses HNAP protocol with authentication challenges. Development on hold pending HNAP improvements ([Issue ***REMOVED***32](https://github.com/kwschulz/cable_modem_monitor/issues/32))

***REMOVED******REMOVED******REMOVED*** 🆕 Fallback Mode
If your modem isn't listed, you can still install the integration! It will enter **Fallback Mode** which:
- Allows installation to succeed
- Enables the "Capture HTML" diagnostics button
- Lets you provide HTML samples to help add support for your modem
- See [How to Help Add Support](***REMOVED***how-to-help-add-support-for-your-modem) below

***REMOVED******REMOVED*** 📝 Help Verify Modem Support

**Did you successfully install with a modem marked with an asterisk (*)?** Please help verify it!

Your feedback helps other users know which parsers are reliable and well-tested.

***REMOVED******REMOVED******REMOVED*** Quick Verification (2 minutes)

**[→ Report Working Modem](https://github.com/kwschulz/cable_modem_monitor/issues/new?template=modem_verification.yml)**

Just fill out the simple form with:
- ✅ Your modem model and firmware version
- ✅ Which features are working (channels, restart, etc.)
- ✅ Optional: Attach diagnostics file for validation

**What happens next?**
- Maintainer reviews your report
- Modem gets moved to "✅ Verified Working" section
- Asterisk (*) removed in next release
- Other users benefit from your confirmation!

**No GitHub account?** You can also report in [Home Assistant Community Forums](https://community.home-assistant.io/t/cable-modem-monitor-track-your-internet-signal-quality-in-home-assistant/817820).

---

***REMOVED******REMOVED*** How to Help Add Support for Your Modem

If your modem isn't fully supported or you'd like to help expand compatibility:

***REMOVED******REMOVED******REMOVED*** Easy Way: Built-in Diagnostics (Recommended)

1. **Install the integration** with your modem's IP address
2. **Go to Settings → Devices & Services → Cable Modem Monitor**
3. **Click the device**, then **Download Diagnostics**
4. **Open a GitHub Issue** with your modem model and attach the diagnostics file

The diagnostics file automatically captures all the HTML pages we need to build a parser for your modem!

***REMOVED******REMOVED******REMOVED*** Advanced Way: HAR Capture (Best for Authentication Issues)

**⭐ Recommended for authentication/login problems** (HNAP, form-based auth, etc.)

HAR (HTTP Archive) files capture the **complete HTTP conversation** with your modem, including:
- Full authentication flow (login sequence, cookies, headers)
- Session management and redirects
- All requests and responses

This is **much more useful** than HTML alone when debugging authentication issues.

**Two Methods:**

1. **Automated Script (Easiest)** - One command, fully automated:
   ```bash
   pip install playwright
   playwright install chromium
   python scripts/capture_modem.py
   ```

2. **Browser DevTools (Manual)** - Use your browser's Network tab to save HAR

**📖 See the [HAR Capture Guide](./docs/HAR_CAPTURE_GUIDE.md)** for complete step-by-step instructions with screenshots.

**Privacy:** HAR files are automatically sanitized to remove passwords and sensitive data before sharing.

**When to use HAR:**
- ✅ Your modem requires login and authentication isn't working
- ✅ HNAP-based modems (Motorola MB8600/MB8611, Arris S33)
- ✅ Form-based authentication issues
- ✅ Complex login flows with redirects

***REMOVED******REMOVED******REMOVED*** Manual Way: HTML Capture (Simple Cases)

For modems with **no authentication** or when login works but parsing fails:

1. **Capture HTML Samples**: Provide us with the HTML source from your modem's status pages
   - See the [HTML Capture Guide](./docs/HTML_CAPTURE_GUIDE.md) for detailed instructions
2. **Open a GitHub Issue**: Create an issue with your modem model and attach the captured HTML samples

**Your contribution helps everyone with the same modem model!**

**Want to develop the parser yourself?** This integration uses a plugin architecture that makes adding new models easy. See the [Contributing Guide](./CONTRIBUTING.md) for details on how to add support for your modem.



***REMOVED******REMOVED*** Installation

***REMOVED******REMOVED******REMOVED*** Method 1: HACS (Recommended)

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
5. Add this repository URL: `https://github.com/kwschulz/cable_modem_monitor`
6. Category: **Integration**
7. Click **"Add"**
8. Search for **"Cable Modem Monitor"** in HACS
9. Click **"Download"**
10. **Restart Home Assistant**
11. Add the integration: **Settings → Devices & Services → Add Integration → Cable Modem Monitor**

***REMOVED******REMOVED******REMOVED*** Method 2: Manual Installation

1. Download the [latest release](https://github.com/kwschulz/cable_modem_monitor/releases/latest)
2. Extract the zip file
3. Copy the `custom_components/cable_modem_monitor` folder to your Home Assistant's `config/custom_components/` directory
4. Restart Home Assistant
5. Go to Settings → Devices & Services
6. Click "+ Add Integration"
7. Search for "Cable Modem Monitor"
8. Enter your modem's IP address (typically `192.168.100.1`)

***REMOVED******REMOVED*** Configuration

1. **Find your modem's IP address**: Usually `192.168.100.1` or `192.168.0.1`
2. **Verify web interface access**: Open `http://192.168.100.1` (or your modem's IP) in a browser
3. **Add the integration**:
   - Settings → Devices & Services → Add Integration
   - Search for "Cable Modem Monitor"
   - Enter the IP address

***REMOVED******REMOVED******REMOVED*** Configuration Options

After installation, you can configure additional settings:

1. Go to **Settings → Devices & Services**
2. Find **Cable Modem Monitor** and click **Configure**
3. Available options:
   - **Modem IP Address**: Update if your modem's IP changes
   - **Username/Password**: Update authentication credentials
   - **Modem Model**: Select your modem model or use "auto" for automatic detection (recommended)
   - **Polling Interval**: How often to check modem status (60-1800 seconds, default: 600 - 10 minutes)
   - **History Retention**: Number of days to keep when using Clear History button (1-365 days, default: 30)

![Cable Modem Configuration Settings](images/cable-modem-settings.png)

*Configuration options available through the Settings UI*

---

***REMOVED******REMOVED*** Available Sensors

All sensors use the `cable_modem_` prefix for consistent entity naming and easy identification.

**Entity Naming Pattern:**
- System sensors: `sensor.cable_modem_{metric}` (e.g., `sensor.cable_modem_connection_status`)
- Channel sensors: `sensor.cable_modem_{direction}_ch_{number}_{metric}`
  - Example: `sensor.cable_modem_ds_ch_1_power` (downstream channel 1 power)
  - Example: `sensor.cable_modem_us_ch_3_frequency` (upstream channel 3 frequency)

***REMOVED******REMOVED******REMOVED*** Connection Status
- `sensor.cable_modem_connection_status`: Overall connection state (online/offline)

***REMOVED******REMOVED******REMOVED*** System Information
- `sensor.cable_modem_software_version`: Modem firmware/software version
- `sensor.cable_modem_system_uptime`: How long the modem has been running
- `sensor.cable_modem_last_boot_time`: When the modem last rebooted (timestamp device class)
- `sensor.cable_modem_downstream_channel_count`: Number of active downstream channels
- `sensor.cable_modem_upstream_channel_count`: Number of active upstream channels

***REMOVED******REMOVED******REMOVED*** Health Monitoring
- `sensor.cable_modem_health_status`: Overall modem health (healthy/degraded/offline)
- `sensor.cable_modem_ping_latency`: Ping response time in milliseconds
- `sensor.cable_modem_http_latency`: HTTP response time in milliseconds

***REMOVED******REMOVED******REMOVED*** Summary Sensors
- `sensor.cable_modem_total_corrected_errors`: Total corrected errors across all downstream channels
- `sensor.cable_modem_total_uncorrected_errors`: Total uncorrected errors across all downstream channels

***REMOVED******REMOVED******REMOVED*** Per-Channel Downstream Sensors (for each channel)
Replace `X` with the channel number (1-32 depending on your modem):
- `sensor.cable_modem_downstream_ch_X_power`: Power level in dBmV
- `sensor.cable_modem_downstream_ch_X_snr`: Signal-to-Noise Ratio in dB
- `sensor.cable_modem_downstream_ch_X_frequency`: Channel frequency in Hz
- `sensor.cable_modem_downstream_ch_X_corrected`: Corrected errors
- `sensor.cable_modem_downstream_ch_X_uncorrected`: Uncorrected errors

***REMOVED******REMOVED******REMOVED*** Per-Channel Upstream Sensors (for each channel)
Replace `X` with the channel number (1-8 depending on your modem):
- `sensor.cable_modem_upstream_ch_X_power`: Transmit power level in dBmV
- `sensor.cable_modem_upstream_ch_X_frequency`: Channel frequency in Hz

***REMOVED******REMOVED******REMOVED*** Controls
- `button.cable_modem_restart_modem`: Restart your cable modem remotely

***REMOVED******REMOVED******REMOVED*** Services
- `cable_modem_monitor.clear_history`: Clear old historical data (keeps specified number of days)
- `cable_modem_monitor.cleanup_entities`: Remove orphaned entities from registry (useful after upgrades)

***REMOVED******REMOVED*** Understanding the Values

***REMOVED******REMOVED******REMOVED*** Downstream Power (dBmV)
- **Ideal range**: -7 to +7 dBmV
- **Acceptable**: -15 to +15 dBmV
- **Poor**: Below -15 or above +15 dBmV

***REMOVED******REMOVED******REMOVED*** Signal-to-Noise Ratio (dB)
- **Excellent**: Above 40 dB
- **Good**: 33-40 dB
- **Acceptable**: 25-33 dB
- **Poor**: Below 25 dB

***REMOVED******REMOVED******REMOVED*** Upstream Power (dBmV)
- **Ideal range**: 35-50 dBmV
- **Acceptable**: 30-55 dBmV
- **Poor**: Below 30 or above 55 dBmV

***REMOVED******REMOVED******REMOVED*** Corrected vs Uncorrected Errors
- **Corrected errors**: Normal in small amounts; modem can fix these
- **Uncorrected errors**: Indicate data loss; any sustained increase is concerning
- **Monitor trends**: Sudden increases may indicate line issues

***REMOVED******REMOVED*** Example Dashboard

Create a comprehensive dashboard to monitor your modem health. This example shows all 24 downstream channels (typical for DOCSIS 3.0 modems), upstream channels, and error tracking:

<details>
<summary><b>Click to expand full dashboard YAML</b></summary>

```yaml
type: vertical-stack
cards:
  - type: entities
    title: Cable Modem Status
    entities:
      - entity: sensor.cable_modem_connection_status
        name: Status
      - entity: sensor.cable_modem_software_version
        name: Software Version
      - entity: sensor.cable_modem_system_uptime
        name: Uptime
      - entity: sensor.cable_modem_last_boot_time
        name: Last Boot
        format: date
      - entity: sensor.cable_modem_downstream_channel_count
        name: DS Channel Count
      - entity: sensor.cable_modem_upstream_channel_count
        name: US Channel Count
      - entity: sensor.cable_modem_total_corrected_errors
        name: Total Corrected Errors
      - entity: sensor.cable_modem_total_uncorrected_errors
        name: Total Uncorrected Errors
      - entity: button.cable_modem_restart_modem
    show_header_toggle: false
    state_color: false
  - type: history-graph
    title: Downstream Power Levels (dBmV)
    hours_to_show: 24
    entities:
      - entity: sensor.cable_modem_ds_ch_1_power
        name: Ch 1
      - entity: sensor.cable_modem_ds_ch_2_power
        name: Ch 2
      - entity: sensor.cable_modem_ds_ch_3_power
        name: Ch 3
      - entity: sensor.cable_modem_ds_ch_4_power
        name: Ch 4
      - entity: sensor.cable_modem_ds_ch_5_power
        name: Ch 5
      - entity: sensor.cable_modem_ds_ch_6_power
        name: Ch 6
      - entity: sensor.cable_modem_ds_ch_7_power
        name: Ch 7
      - entity: sensor.cable_modem_ds_ch_8_power
        name: Ch 8
      - entity: sensor.cable_modem_ds_ch_9_power
        name: Ch 9
      - entity: sensor.cable_modem_ds_ch_10_power
        name: Ch 10
      - entity: sensor.cable_modem_ds_ch_11_power
        name: Ch 11
      - entity: sensor.cable_modem_ds_ch_12_power
        name: Ch 12
      - entity: sensor.cable_modem_ds_ch_13_power
        name: Ch 13
      - entity: sensor.cable_modem_ds_ch_14_power
        name: Ch 14
      - entity: sensor.cable_modem_ds_ch_15_power
        name: Ch 15
      - entity: sensor.cable_modem_ds_ch_16_power
        name: Ch 16
      - entity: sensor.cable_modem_ds_ch_17_power
        name: Ch 17
      - entity: sensor.cable_modem_ds_ch_18_power
        name: Ch 18
      - entity: sensor.cable_modem_ds_ch_19_power
        name: Ch 19
      - entity: sensor.cable_modem_ds_ch_20_power
        name: Ch 20
      - entity: sensor.cable_modem_ds_ch_21_power
        name: Ch 21
      - entity: sensor.cable_modem_ds_ch_22_power
        name: Ch 22
      - entity: sensor.cable_modem_ds_ch_23_power
        name: Ch 23
      - entity: sensor.cable_modem_ds_ch_24_power
        name: Ch 24
  - type: history-graph
    title: Downstream Signal-to-Noise Ratio (dB)
    hours_to_show: 24
    entities:
      - entity: sensor.cable_modem_ds_ch_1_snr
        name: Ch 1
      - entity: sensor.cable_modem_ds_ch_2_snr
        name: Ch 2
      - entity: sensor.cable_modem_ds_ch_3_snr
        name: Ch 3
      - entity: sensor.cable_modem_ds_ch_4_snr
        name: Ch 4
      - entity: sensor.cable_modem_ds_ch_5_snr
        name: Ch 5
      - entity: sensor.cable_modem_ds_ch_6_snr
        name: Ch 6
      - entity: sensor.cable_modem_ds_ch_7_snr
        name: Ch 7
      - entity: sensor.cable_modem_ds_ch_8_snr
        name: Ch 8
      - entity: sensor.cable_modem_ds_ch_9_snr
        name: Ch 9
      - entity: sensor.cable_modem_ds_ch_10_snr
        name: Ch 10
      - entity: sensor.cable_modem_ds_ch_11_snr
        name: Ch 11
      - entity: sensor.cable_modem_ds_ch_12_snr
        name: Ch 12
      - entity: sensor.cable_modem_ds_ch_13_snr
        name: Ch 13
      - entity: sensor.cable_modem_ds_ch_14_snr
        name: Ch 14
      - entity: sensor.cable_modem_ds_ch_15_snr
        name: Ch 15
      - entity: sensor.cable_modem_ds_ch_16_snr
        name: Ch 16
      - entity: sensor.cable_modem_ds_ch_17_snr
        name: Ch 17
      - entity: sensor.cable_modem_ds_ch_18_snr
        name: Ch 18
      - entity: sensor.cable_modem_ds_ch_19_snr
        name: Ch 19
      - entity: sensor.cable_modem_ds_ch_20_snr
        name: Ch 20
      - entity: sensor.cable_modem_ds_ch_21_snr
        name: Ch 21
      - entity: sensor.cable_modem_ds_ch_22_snr
        name: Ch 22
      - entity: sensor.cable_modem_ds_ch_23_snr
        name: Ch 23
      - entity: sensor.cable_modem_ds_ch_24_snr
        name: Ch 24
  - type: history-graph
    title: Upstream Power Levels (dBmV)
    hours_to_show: 24
    entities:
      - entity: sensor.cable_modem_us_ch_1_power
        name: US Ch 1
      - entity: sensor.cable_modem_us_ch_2_power
        name: US Ch 2
      - entity: sensor.cable_modem_us_ch_3_power
        name: US Ch 3
      - entity: sensor.cable_modem_us_ch_4_power
        name: US Ch 4
      - entity: sensor.cable_modem_us_ch_5_power
        name: US Ch 5
  - type: history-graph
    title: Upstream Frequency (MHz)
    hours_to_show: 24
    entities:
      - entity: sensor.cable_modem_us_ch_1_frequency
        name: US Ch 1
      - entity: sensor.cable_modem_us_ch_2_frequency
        name: US Ch 2
      - entity: sensor.cable_modem_us_ch_3_frequency
        name: US Ch 3
      - entity: sensor.cable_modem_us_ch_4_frequency
        name: US Ch 4
      - entity: sensor.cable_modem_us_ch_5_frequency
        name: US Ch 5
  - type: history-graph
    title: Corrected Errors (Total)
    hours_to_show: 24
    entities:
      - sensor.cable_modem_total_corrected_errors
  - type: history-graph
    title: Uncorrected Errors (Total)
    hours_to_show: 24
    entities:
      - sensor.cable_modem_total_uncorrected_errors
```

</details>

**Note**: This dashboard example includes all 24 downstream channels. If your modem has fewer channels (e.g., 16 or 8), simply remove the extra channel entries. If you have more channels, add them by following the same pattern with entity_ids like `sensor.cable_modem_ds_ch_X_power` where X is the channel number.

***REMOVED******REMOVED******REMOVED*** Last Boot Time Display Options

The `sensor.cable_modem_last_boot_time` is a timestamp sensor. You can customize how it displays:

**Relative time (recommended)** - Compact and informative:
```yaml
- entity: sensor.cable_modem_last_boot_time
  format: relative
```
*Shows: "29 days ago"*

**Date only** - Just the date:
```yaml
- entity: sensor.cable_modem_last_boot_time
  format: date
```
*Shows: "2025-09-25"*

**Time only** - Just the time:
```yaml
- entity: sensor.cable_modem_last_boot_time
  format: time
```
*Shows: "00:38:00"*

**Full datetime (fits in UI)** - Date and time:
```yaml
- entity: sensor.cable_modem_last_boot_time
  format: datetime
```
*Shows: "2025-09-25 00:38:00"*

**Custom template** - For more control (may be too long for some UIs):
```yaml
type: markdown
content: >
  Last Reboot: {{
    as_timestamp(states('sensor.cable_modem_last_boot_time'))
    | timestamp_custom('%Y-%m-%d %H:%M')
  }}
```
*Shows: "Last Reboot: 2025-09-25 00:38"*

***REMOVED******REMOVED*** Automation Examples

<details>
<summary><b>Click to expand automation examples</b></summary>

***REMOVED******REMOVED******REMOVED*** Alert on High Uncorrected Errors

```yaml
automation:
  - alias: "Cable Modem - High Uncorrected Errors"
    trigger:
      - platform: numeric_state
        entity_id: sensor.cable_modem_total_uncorrected_errors
        above: 100
    action:
      - service: notify.notify
        data:
          title: "Cable Modem Alert"
          message: "High uncorrected errors detected. Check your cable connection."
```

***REMOVED******REMOVED******REMOVED*** Alert on Low SNR

```yaml
automation:
  - alias: "Cable Modem - Low SNR Warning"
    trigger:
      - platform: numeric_state
        entity_id: sensor.cable_modem_downstream_ch_1_snr
        below: 30
    action:
      - service: notify.notify
        data:
          title: "Cable Modem Alert"
          message: "Low signal quality detected on downstream channel 1."
```

***REMOVED******REMOVED******REMOVED*** Alert on Channel Count Changes

```yaml
automation:
  - alias: "Cable Modem - Channel Count Changed"
    trigger:
      - platform: state
        entity_id:
          - sensor.cable_modem_downstream_channel_count
          - sensor.cable_modem_upstream_channel_count
    condition:
      - condition: template
        value_template: "{{ trigger.from_state.state != 'unavailable' }}"
    action:
      - service: notify.notify
        data:
          title: "Cable Modem Alert"
          message: "Channel count changed: {{ trigger.to_state.name }} is now {{ trigger.to_state.state }}"
```

***REMOVED******REMOVED******REMOVED*** Auto-Restart on Network Issues

```yaml
automation:
  - alias: "Cable Modem - Auto Restart on High Errors"
    trigger:
      - platform: numeric_state
        entity_id: sensor.cable_modem_total_uncorrected_errors
        above: 1000
    action:
      - service: notify.notify
        data:
          title: "Cable Modem Alert"
          message: "High error count detected. Restarting modem..."
      - service: button.press
        target:
          entity_id: button.cable_modem_restart_modem
```

</details>

***REMOVED******REMOVED*** Troubleshooting

> **📖 For detailed troubleshooting help, see [TROUBLESHOOTING.md](./docs/TROUBLESHOOTING.md)**
>
> Covers: entity ID cleanup, upstream sensors not appearing, duplicate entities, migration issues, and more.

***REMOVED******REMOVED******REMOVED*** Integration doesn't appear
1. Check that files are in `/config/custom_components/cable_modem_monitor/`
2. Restart Home Assistant
3. Check logs for errors: Settings → System → Logs

***REMOVED******REMOVED******REMOVED*** "Cannot Connect" error
1. Verify modem IP address is correct
2. Open modem web interface in browser to confirm it's accessible
3. Ensure Home Assistant can reach the modem (same network)
4. If modem requires authentication, enter username and password in the config dialog

***REMOVED******REMOVED******REMOVED*** Sensors show "Unknown" or no data
The modem's HTML format may differ from expected. To debug:
1. Enable debug logging in `configuration.yaml`:
   ```yaml
   logger:
     default: warning
     logs:
       custom_components.cable_modem_monitor: debug
   ```
2. Restart Home Assistant
3. Check logs for parsing errors
4. Open an issue with your modem model and a sample of the HTML

***REMOVED******REMOVED******REMOVED*** Different modem page URL
Some modems use different URLs for signal data:
- `/cmSignalData.htm` (common Motorola)
- `/cmSignal.html`
- `/` (root page)

The integration tries multiple common URLs automatically.

***REMOVED******REMOVED*** Contributing

Contributions are welcome! If you have:
- Support for additional modem models
- Bug fixes
- Feature improvements

Please see the [Contributing Guide](./CONTRIBUTING.md) for details on how to add support for your modem, run tests, and submit changes.

***REMOVED******REMOVED*** Privacy & Security

***REMOVED******REMOVED******REMOVED*** Privacy Protection
- **100% Local**: All data stays on your Home Assistant instance - no cloud services
- **Read-Only**: Only reads data from your modem (never modifies configuration)
- **PII Sanitization**: Automatic removal of sensitive data from diagnostics
  - IP addresses, MAC addresses, serial numbers automatically redacted
  - Safe to share diagnostic files for support
- **Secure Credentials**: Stored in Home Assistant's encrypted storage

***REMOVED******REMOVED******REMOVED*** Security Features
- **CodeQL Scanning**: Automated security analysis on every commit
  - 100+ standard security queries (OWASP Top 10, CWE coverage)
  - 6 custom security queries specific to cable modem integration:
    - HTTP requests without timeouts
    - Command injection prevention
    - XML External Entity (XXE) protection
    - Hardcoded credential detection
    - SSL/TLS misconfiguration checks
    - Path traversal prevention
- **Security Documentation**: See [CodeQL Overview](./docs/CODEQL_OVERVIEW.md) for details
- **Vulnerability Reporting**: See [SECURITY.md](./SECURITY.md) for responsible disclosure

***REMOVED******REMOVED******REMOVED*** Authentication Support
- HTTP Basic Authentication
- Form-based authentication
- HNAP/SOAP authentication
- No authentication (for open modems)

***REMOVED******REMOVED*** License

MIT License - see LICENSE file for details

***REMOVED******REMOVED*** Support

- [GitHub Issues](https://github.com/kwschulz/cable_modem_monitor/issues)
- [Home Assistant Community Forum](https://community.home-assistant.io/)

***REMOVED******REMOVED*** Resources

***REMOVED******REMOVED******REMOVED*** Project Documentation
- [Changelog](./CHANGELOG.md) - Complete version history and release notes
- [Verification Status](./VERIFICATION_STATUS.md) - Verified modem compatibility list
- [Contributing Guide](./CONTRIBUTING.md) - How to contribute code or add modem support
- [CodeQL Security Overview](./docs/CODEQL_OVERVIEW.md) - Security scanning details
- [Troubleshooting Guide](./docs/TROUBLESHOOTING.md) - Common issues and solutions
- [HAR Capture Guide](./docs/HAR_CAPTURE_GUIDE.md) - Help add support for your modem

***REMOVED******REMOVED******REMOVED*** External Resources
- [Home Assistant Releases](https://github.com/home-assistant/core/releases)
- [HACS Brand Repository](https://github.com/home-assistant/brands/tree/master/custom_integrations/cable_modem_monitor)

***REMOVED******REMOVED*** Credits

Created for monitoring Cox Cable Motorola modems, but designed to work with various cable modem brands.

---

**Disclaimer**: This integration reads data from your modem's web interface. It does not modify modem settings or configuration.
