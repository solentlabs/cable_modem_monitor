***REMOVED*** Cable Modem Monitor

Monitor your cable modem's signal quality, power levels, and error rates directly in Home Assistant. Perfect for tracking internet connection health and identifying potential issues before they cause problems.

![Cable Modem Health Dashboard](images/dashboard-screenshot.png)

***REMOVED******REMOVED*** Features

✨ **Easy Setup** - Configure via UI, no YAML editing required
📊 **Per-Channel Monitoring** - Track power, SNR, frequency, and errors for each channel
📈 **Historical Tracking** - All metrics stored for trend analysis and graphing
🔔 **Automation Ready** - Create alerts for signal degradation or high error rates
🎛️ **Device Control** - Restart modem and manage history directly from UI
🔧 **Configurable** - Adjust settings including history retention (1-365 days)

***REMOVED******REMOVED*** What Gets Monitored

***REMOVED******REMOVED******REMOVED*** Downstream Channels
- Power levels (dBmV) - Ideal: -7 to +7
- Signal-to-Noise Ratio (dB) - Target: >40 dB
- Frequency and error rates

***REMOVED******REMOVED******REMOVED*** Upstream Channels
- Transmit power (dBmV) - Ideal: 35-50
- Frequency

***REMOVED******REMOVED******REMOVED*** System Information
- Connection status
- Software version and uptime
- Channel counts
- Total error statistics

***REMOVED******REMOVED*** Supported Modems

***REMOVED******REMOVED******REMOVED*** ✅ Confirmed Working
- **Motorola MB Series**: MB7420, MB7621, MB8600, MB8611
- **ARRIS SB6141**

***REMOVED******REMOVED******REMOVED*** ⚠️ Community Reported (Mixed Results)
- **Arris SB6183**
- **Arris SB8200**

***REMOVED******REMOVED******REMOVED*** 🧪 Experimental / Untested
- **Technicolor TC4400**
- **Technicolor XB7 (CGM4331COM)**

For a complete and up-to-date list, please see the [Modem Compatibility Guide](./MODEM_COMPATIBILITY_GUIDE.md).

***REMOVED******REMOVED*** Quick Example

Create automations like:

```yaml
automation:
  - alias: "Alert on High Errors"
    trigger:
      - platform: numeric_state
        entity_id: sensor.total_uncorrected_errors
        above: 100
    action:
      - service: notify.notify
        data:
          message: "Cable modem signal quality degraded!"
```

***REMOVED******REMOVED*** Installation

1. Install via HACS (search for "Cable Modem Monitor")
2. Restart Home Assistant
3. Add integration: Settings → Devices & Services → Add Integration
4. Enter your modem's IP address (usually 192.168.100.1)

***REMOVED******REMOVED*** Documentation

Full documentation including dashboard examples, automation ideas, and troubleshooting:
[GitHub Repository](https://github.com/kwschulz/cable_modem_monitor)
