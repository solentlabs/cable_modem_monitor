***REMOVED*** Quick Start Guide

Get your cable modem monitoring in under 5 minutes!

***REMOVED******REMOVED*** Step 1: Find Your Modem's IP Address

Most cable modems use one of these addresses:
- `192.168.100.1` (most common for Motorola/Arris)
- `192.168.0.1`
- `10.0.0.1`

**Test it**: Open a browser and go to `http://192.168.100.1` (or try the others). You should see your modem's web interface.

***REMOVED******REMOVED*** Step 2: Install the Integration

***REMOVED******REMOVED******REMOVED*** Option A: Manual Install (5 minutes)

1. Copy the `custom_components/cable_modem_monitor` folder to:
   ```
   /config/custom_components/cable_modem_monitor/
   ```

2. Restart Home Assistant:
   - Settings → System → Restart

3. Add the integration:
   - Settings → Devices & Services
   - Click "+ Add Integration"
   - Search for "Cable Modem Monitor"
   - Enter your modem IP (e.g., `192.168.100.1`)
   - Click Submit

***REMOVED******REMOVED******REMOVED*** Option B: HACS (Coming Soon)

HACS support is planned for easier installation!

***REMOVED******REMOVED*** Step 3: Verify Sensors

1. Go to **Developer Tools → States**
2. Filter by: `cable_modem`
3. You should see sensors like:
   - `sensor.modem_connection_status`
   - `sensor.downstream_ch_1_power`
   - `sensor.downstream_ch_1_snr`
   - And many more!

***REMOVED******REMOVED*** Step 4: Create a Dashboard

Add a quick monitoring card:

1. Go to your dashboard
2. Click "Edit Dashboard"
3. Add a new card with this YAML:

```yaml
type: entities
title: Cable Modem Health
entities:
  - entity: sensor.modem_connection_status
    name: Status
  - entity: sensor.downstream_ch_1_power
    name: Ch1 Power
  - entity: sensor.downstream_ch_1_snr
    name: Ch1 SNR
  - entity: sensor.total_uncorrected_errors
    name: Errors
```

***REMOVED******REMOVED*** Step 5: Add Historical Graphs

Track trends over time:

```yaml
type: history-graph
title: Power Levels (Last 24h)
hours_to_show: 24
entities:
  - sensor.downstream_ch_1_power
  - sensor.downstream_ch_2_power
  - sensor.upstream_ch_1_power
```

***REMOVED******REMOVED*** Next Steps

- Check the main README.md for detailed documentation
- Set up automations to alert on signal issues
- Monitor error rates to catch problems early

***REMOVED******REMOVED*** Troubleshooting

**Integration not appearing?**
- Verify files are in `/config/custom_components/cable_modem_monitor/`
- Check Home Assistant logs for errors
- Restart Home Assistant again

**Cannot connect error?**
- Verify modem IP in browser first
- Ensure Home Assistant is on same network as modem
- Try different common IPs: 192.168.100.1, 192.168.0.1, 10.0.0.1

**Sensors show "Unknown"?**
- Your modem HTML format may be different
- Enable debug logging (see README.md)
- Open an issue with your modem model

***REMOVED******REMOVED*** What to Monitor

***REMOVED******REMOVED******REMOVED*** Priority 1: Uncorrected Errors
If this number keeps increasing, you have line quality issues. Contact your ISP.

***REMOVED******REMOVED******REMOVED*** Priority 2: SNR (Signal-to-Noise Ratio)
Should be above 30 dB. Lower values indicate signal degradation.

***REMOVED******REMOVED******REMOVED*** Priority 3: Power Levels
Downstream should be -7 to +7 dBmV ideally.
Upstream should be 35-50 dBmV ideally.

---

Need more help? Check the full README.md or open an issue on GitHub!
