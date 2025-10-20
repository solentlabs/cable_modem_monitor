***REMOVED*** Cable Modem Monitor for Home Assistant

A custom Home Assistant integration that monitors cable modem signal quality, power levels, and error rates. Perfect for tracking your internet connection health and identifying potential issues before they cause problems.

***REMOVED******REMOVED*** Features

- **Easy Setup**: Configure via Home Assistant UI - no YAML editing required
- **Comprehensive Monitoring**: Tracks downstream and upstream channels
- **Per-Channel Metrics**:
  - Power levels (dBmV)
  - Signal-to-Noise Ratio (SNR in dB)
  - Frequency (Hz)
  - Corrected/Uncorrected errors
- **Summary Sensors**: Total corrected and uncorrected errors across all channels
- **Connection Status**: Monitor modem online/offline state
- **Historical Data**: All metrics are stored for trend analysis
- **Dashboard Ready**: Create graphs and alerts based on signal quality

***REMOVED******REMOVED*** Supported Modems

This integration is designed for cable modems with web-based status pages. It has been tested with:

- Motorola cable modems
- Arris cable modems (many Motorola-compatible)

**Note**: The integration may work with other brands. If your modem has a web interface showing downstream/upstream channel data, it's worth trying!

***REMOVED******REMOVED*** Installation

***REMOVED******REMOVED******REMOVED*** Method 1: Manual Installation

1. Download or clone this repository
2. Copy the `custom_components/cable_modem_monitor` folder to your Home Assistant's `config/custom_components/` directory
3. Restart Home Assistant
4. Go to Settings → Devices & Services
5. Click "+ Add Integration"
6. Search for "Cable Modem Monitor"
7. Enter your modem's IP address (typically `192.168.100.1`)

***REMOVED******REMOVED******REMOVED*** Method 2: HACS (Coming Soon)

This integration will be available through HACS for easier installation and updates.

***REMOVED******REMOVED*** Configuration

1. **Find your modem's IP address**: Usually `192.168.100.1` or `192.168.0.1`
2. **Verify web interface access**: Open `http://192.168.100.1` (or your modem's IP) in a browser
3. **Add the integration**:
   - Settings → Devices & Services → Add Integration
   - Search for "Cable Modem Monitor"
   - Enter the IP address

***REMOVED******REMOVED*** Available Sensors

***REMOVED******REMOVED******REMOVED*** Connection Status
- `sensor.modem_connection_status`: Overall connection state (online/offline)

***REMOVED******REMOVED******REMOVED*** Summary Sensors
- `sensor.total_corrected_errors`: Total corrected errors across all downstream channels
- `sensor.total_uncorrected_errors`: Total uncorrected errors across all downstream channels

***REMOVED******REMOVED******REMOVED*** Per-Channel Downstream Sensors (for each channel)
- `sensor.downstream_ch_X_power`: Power level in dBmV
- `sensor.downstream_ch_X_snr`: Signal-to-Noise Ratio in dB
- `sensor.downstream_ch_X_frequency`: Channel frequency in Hz
- `sensor.downstream_ch_X_corrected`: Corrected errors (if available)
- `sensor.downstream_ch_X_uncorrected`: Uncorrected errors (if available)

***REMOVED******REMOVED******REMOVED*** Per-Channel Upstream Sensors (for each channel)
- `sensor.upstream_ch_X_power`: Transmit power level in dBmV
- `sensor.upstream_ch_X_frequency`: Channel frequency in Hz

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

Create a dashboard to monitor your modem health:

```yaml
type: vertical-stack
cards:
  - type: entities
    title: Cable Modem Status
    entities:
      - sensor.modem_connection_status
      - sensor.total_corrected_errors
      - sensor.total_uncorrected_errors

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
    title: Error Rates
    hours_to_show: 24
    entities:
      - sensor.total_corrected_errors
      - sensor.total_uncorrected_errors
```

***REMOVED******REMOVED*** Automation Examples

***REMOVED******REMOVED******REMOVED*** Alert on High Uncorrected Errors

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

***REMOVED******REMOVED******REMOVED*** Alert on Low SNR

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

***REMOVED******REMOVED*** Troubleshooting

***REMOVED******REMOVED******REMOVED*** Integration doesn't appear
1. Check that files are in `/config/custom_components/cable_modem_monitor/`
2. Restart Home Assistant
3. Check logs for errors: Settings → System → Logs

***REMOVED******REMOVED******REMOVED*** "Cannot Connect" error
1. Verify modem IP address is correct
2. Open modem web interface in browser to confirm it's accessible
3. Ensure Home Assistant can reach the modem (same network)
4. Check if modem requires authentication (not currently supported)

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

Please open an issue or pull request on GitHub.

***REMOVED******REMOVED*** Adding Support for Your Modem

If your modem isn't working:

1. Access your modem's web interface
2. Find the signal/status page
3. View the page source (right-click → View Page Source)
4. Open an issue with:
   - Modem make and model
   - The URL of the status page
   - A sample of the HTML table structure (sanitize any personal info)

***REMOVED******REMOVED*** Update Interval

By default, the integration polls your modem every 5 minutes. This is defined in `const.py` as `DEFAULT_SCAN_INTERVAL = 300` (seconds).

To change this, edit the value in `custom_components/cable_modem_monitor/const.py` and restart Home Assistant.

***REMOVED******REMOVED*** Privacy & Security

- All data stays local - no cloud services involved
- Only reads data from your modem (no configuration changes)
- No authentication support yet (most modems don't require it for status pages)

***REMOVED******REMOVED*** License

MIT License - see LICENSE file for details

***REMOVED******REMOVED*** Support

- [GitHub Issues](https://github.com/kwschulz/cable_modem_monitor/issues)
- [Home Assistant Community Forum](https://community.home-assistant.io/)

***REMOVED******REMOVED*** Credits

Created for monitoring Cox Cable Motorola modems, but designed to work with various cable modem brands.

---

**Disclaimer**: This integration reads data from your modem's web interface. It does not modify modem settings or configuration.
