# Cable Modem Monitor for Home Assistant

[![Tests](https://github.com/kwschulz/cable_modem_monitor/actions/workflows/tests.yml/badge.svg)](https://github.com/kwschulz/cable_modem_monitor/actions/workflows/tests.yml)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/github/v/release/kwschulz/cable_modem_monitor)](https://github.com/kwschulz/cable_modem_monitor/releases)

A custom Home Assistant integration that monitors cable modem signal quality, power levels, and error rates. Perfect for tracking your internet connection health and identifying potential issues before they cause problems.

> **⭐ If you find this integration useful, please star this repo!**
> It helps others discover the project and shows that the integration is actively used.

![Cable Modem Health Dashboard](images/dashboard-screenshot.png)

## Features

- **Easy Setup**: Configure via Home Assistant UI - no YAML editing required
- **Comprehensive Monitoring**: Tracks downstream and upstream channels
- **Per-Channel Metrics**:
  - Power levels (dBmV)
  - Signal-to-Noise Ratio (SNR in dB)
  - Frequency (Hz)
  - Corrected/Uncorrected errors
- **Summary Sensors**: Total corrected and uncorrected errors across all channels
- **Connection Status**: Monitor modem online/offline state
- **System Information**: Software version, uptime, and channel counts
- **Modem Control**: Restart your modem directly from Home Assistant
- **Historical Data**: All metrics are stored for trend analysis
- **Dashboard Ready**: Create graphs and alerts based on signal quality

## Supported Modems

This integration is designed for cable modems with web-based status pages.

**Confirmed Working:**
- **Motorola MB7621** (other MB series models likely compatible)
- **Arris SB6183, SB8200** (newer models - reported by community)

**Being Tested:**
- **Arris SB6141** (parser added, awaiting user confirmation)
- **Technicolor TC4400** (parser added, awaiting user confirmation)

**Note**: The integration may work with other brands. If your modem has a web interface showing downstream/upstream channel data, it's worth trying!

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
5. Add this repository URL: `https://github.com/kwschulz/cable_modem_monitor`
6. Category: **Integration**
7. Click **"Add"**
8. Search for **"Cable Modem Monitor"** in HACS
9. Click **"Download"**
10. **Restart Home Assistant**
11. Add the integration: **Settings → Devices & Services → Add Integration → Cable Modem Monitor**

### Method 2: Manual Installation

1. Download the [latest release](https://github.com/kwschulz/cable_modem_monitor/releases/latest)
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
   - **Polling Interval**: How often to check modem status (60-1800 seconds, default: 600 - 10 minutes)
   - **History Retention**: Number of days to keep when using Clear History button (1-365 days, default: 30)

![Cable Modem Configuration Settings](images/cable-modem-settings.png)

*Configuration options available through the Settings UI*

---

## Available Sensors

### Connection Status
- `sensor.modem_connection_status`: Overall connection state (online/offline)

### System Information
- `sensor.software_version`: Modem firmware/software version
- `sensor.system_uptime`: How long the modem has been running
- `sensor.downstream_channel_count`: Number of active downstream channels
- `sensor.upstream_channel_count`: Number of active upstream channels

### Summary Sensors
- `sensor.total_corrected_errors`: Total corrected errors across all downstream channels
- `sensor.total_uncorrected_errors`: Total uncorrected errors across all downstream channels

### Per-Channel Downstream Sensors (for each channel)
- `sensor.downstream_ch_X_power`: Power level in dBmV
- `sensor.downstream_ch_X_snr`: Signal-to-Noise Ratio in dB
- `sensor.downstream_ch_X_frequency`: Channel frequency in Hz
- `sensor.downstream_ch_X_corrected`: Corrected errors (if available)
- `sensor.downstream_ch_X_uncorrected`: Uncorrected errors (if available)

### Per-Channel Upstream Sensors (for each channel)
- `sensor.upstream_ch_X_power`: Transmit power level in dBmV
- `sensor.upstream_ch_X_frequency`: Channel frequency in Hz

### Controls
- `button.restart_modem`: Restart your cable modem remotely
- `button.clear_history`: Clear old historical data (keeps last 30 days)

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

## Example Dashboard

Here's an example of a simple, clean dashboard showing all key modem health metrics:

![Cable Modem Health Dashboard](images/dashboard-screenshot.png)

### Example Graphs

Track your signal quality over time with history graphs:

![Downstream Power Levels](images/downstream-power-levels.png)

*Downstream power levels across all channels - ideal range is -7 to +7 dBmV*

![Signal-to-Noise Ratio](images/signal-to-noise-ratio.png)

*Signal-to-Noise Ratio for all channels - higher is better, aim for above 40 dB*

Create a dashboard to monitor your modem health:

```yaml
type: vertical-stack
cards:
  - type: entities
    title: Cable Modem Status
    entities:
      - sensor.modem_connection_status
      - sensor.software_version
      - sensor.system_uptime
      - sensor.downstream_channel_count
      - sensor.upstream_channel_count
      - sensor.total_corrected_errors
      - sensor.total_uncorrected_errors
      - button.restart_modem
      - button.clear_history

  - type: history-graph
    title: Downstream Power Levels
    hours_to_show: 24
    entities:
      - sensor.downstream_ch_1_power
      - sensor.downstream_ch_2_power
      - sensor.downstream_ch_3_power

  - type: history-graph
    title: Signal-to-Noise Ratio
    hours_to_show: 24
    entities:
      - sensor.downstream_ch_1_snr
      - sensor.downstream_ch_2_snr
      - sensor.downstream_ch_3_snr

  - type: history-graph
    title: Error Rates (Trend Analysis)
    hours_to_show: 24
    entities:
      - sensor.total_corrected_errors
      - sensor.total_uncorrected_errors
```

## Automation Examples

### Alert on High Uncorrected Errors

```yaml
automation:
  - alias: "Cable Modem - High Uncorrected Errors"
    trigger:
      - platform: numeric_state
        entity_id: sensor.total_uncorrected_errors
        above: 100
    action:
      - service: notify.notify
        data:
          title: "Cable Modem Alert"
          message: "High uncorrected errors detected. Check your cable connection."
```

### Alert on Low SNR

```yaml
automation:
  - alias: "Cable Modem - Low SNR Warning"
    trigger:
      - platform: numeric_state
        entity_id: sensor.downstream_ch_1_snr
        below: 30
    action:
      - service: notify.notify
        data:
          title: "Cable Modem Alert"
          message: "Low signal quality detected on downstream channel 1."
```

### Alert on Channel Count Changes

```yaml
automation:
  - alias: "Cable Modem - Channel Count Changed"
    trigger:
      - platform: state
        entity_id:
          - sensor.downstream_channel_count
          - sensor.upstream_channel_count
    condition:
      - condition: template
        value_template: "{{ trigger.from_state.state != 'unavailable' }}"
    action:
      - service: notify.notify
        data:
          title: "Cable Modem Alert"
          message: "Channel count changed: {{ trigger.to_state.name }} is now {{ trigger.to_state.state }}"
```

### Auto-Restart on Network Issues

```yaml
automation:
  - alias: "Cable Modem - Auto Restart on High Errors"
    trigger:
      - platform: numeric_state
        entity_id: sensor.total_uncorrected_errors
        above: 1000
    action:
      - service: notify.notify
        data:
          title: "Cable Modem Alert"
          message: "High error count detected. Restarting modem..."
      - service: button.press
        target:
          entity_id: button.restart_modem
```

## Troubleshooting

### Integration doesn't appear
1. Check that files are in `/config/custom_components/cable_modem_monitor/`
2. Restart Home Assistant
3. Check logs for errors: Settings → System → Logs

### "Cannot Connect" error
1. Verify modem IP address is correct
2. Open modem web interface in browser to confirm it's accessible
3. Ensure Home Assistant can reach the modem (same network)
4. If modem requires authentication, enter username and password in the config dialog

### Sensors show "Unknown" or no data
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

### Different modem page URL
Some modems use different URLs for signal data:
- `/cmSignalData.htm` (common Motorola)
- `/cmSignal.html`
- `/` (root page)

The integration tries multiple common URLs automatically.

## Contributing

Contributions are welcome! If you have:
- Support for additional modem models
- Bug fixes
- Feature improvements

Please open an issue or pull request on GitHub.

## Adding Support for Your Modem

If your modem isn't working:

1. Access your modem's web interface
2. Find the signal/status page
3. View the page source (right-click → View Page Source)
4. Open an issue with:
   - Modem make and model
   - The URL of the status page
   - A sample of the HTML table structure (sanitize any personal info)

## Update Interval

By default, the integration polls your modem every 10 minutes. This is defined in `const.py` as `DEFAULT_SCAN_INTERVAL = 600` (seconds).

To change this, edit the value in `custom_components/cable_modem_monitor/const.py` and restart Home Assistant.

## Managing Historical Data

The integration stores all sensor data in Home Assistant's database for historical tracking and trend analysis. Over time, this data can grow large.

### Clear History Button

The easiest way to clean up old data is using the **Clear History** button:
- Found in Settings → Devices & Services → Cable Modem Monitor device page
- Uses the retention period configured in settings (default: 30 days)
- To change retention period: Settings → Devices & Services → Cable Modem Monitor → Configure → History Retention
- Keeps recent data for trend analysis

### Clear History Service

For more control, use the `cable_modem_monitor.clear_history` service:

```yaml
service: cable_modem_monitor.clear_history
data:
  days_to_keep: 60  # Keep 60 days of history
```

You can call this service:
- Manually via Developer Tools → Services
- In an automation to run periodically
- In a script for custom maintenance workflows

**Example Automation** - Clear history monthly:
```yaml
automation:
  - alias: "Cable Modem - Monthly History Cleanup"
    trigger:
      - platform: time
        at: "03:00:00"
    condition:
      - condition: template
        value_template: "{{ now().day == 1 }}"  # First day of month
    action:
      - service: cable_modem_monitor.clear_history
        data:
          days_to_keep: 90  # Keep 3 months of data
```

## Privacy & Security

- All data stays local - no cloud services involved
- Only reads data from your modem (no configuration changes)
- Supports authentication for modems that require login
- Credentials are stored securely in Home Assistant's encrypted storage

## License

MIT License - see LICENSE file for details

## Support

- [GitHub Issues](https://github.com/kwschulz/cable_modem_monitor/issues)
- [Home Assistant Community Forum](https://community.home-assistant.io/)

## Credits

Created for monitoring Cox Cable Motorola modems, but designed to work with various cable modem brands.

---

**Disclaimer**: This integration reads data from your modem's web interface. It does not modify modem settings or configuration.
