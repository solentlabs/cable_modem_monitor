***REMOVED*** Troubleshooting Guide

Common issues and solutions for Cable Modem Monitor integration.

***REMOVED******REMOVED*** Table of Contents
- [Connection and Authentication Issues](***REMOVED***connection-and-authentication-issues)
- [Upstream Sensors Not Appearing](***REMOVED***upstream-sensors-not-appearing)
- [Orphaned Channel Sensors](***REMOVED***orphaned-channel-sensors)
- [Duplicate Entities](***REMOVED***duplicate-entities)

---

***REMOVED******REMOVED*** Connection and Authentication Issues

***REMOVED******REMOVED******REMOVED*** Problem: Login Failures and Timeout Errors

**Symptoms:**
- "Failed to log in to modem" error message
- Sensors show "unavailable" or "unknown"
- Logs show timeout or connection errors
- XB7 users may see timeout messages in logs

**Logging Levels:**
Connection issues are logged with appropriate severity levels:
- **Timeouts** - Logged at DEBUG level (modem may be busy or rebooting)
- **Connection errors** - Logged at WARNING level (network issue)
- **Authentication failures** - Logged at ERROR level (wrong credentials)

This reduces log noise while still capturing important diagnostic information.

**Common Causes & Solutions:**

***REMOVED******REMOVED******REMOVED******REMOVED*** 1. Modem Rebooting or Busy

**Symptoms:**
- Intermittent timeout errors
- Sensors occasionally unavailable
- Happens randomly, then recovers

**What's Happening:**
Cable modems periodically reboot or become busy during channel maintenance. This is normal.

**Solution:**
- **No action needed** - Integration will retry on next poll
- Check the Cable Modem Health Status sensor (v2.6.0+) to see modem responsiveness
- If timeouts persist for >10 minutes, check modem power and connections

***REMOVED******REMOVED******REMOVED******REMOVED*** 2. Network Issues vs. Web Server Issues

**Dual-Layer Health Monitoring**

The integration performs both ICMP ping and HTTP checks to diagnose connectivity:

| ICMP Ping | HTTP HEAD | Status | Diagnosis |
|-----------|-----------|--------|-----------|
| ✅ Success | ✅ Success | `healthy` | Fully responsive |
| ✅ Success | ❌ Fail | `degraded` | Web server issue |
| ❌ Fail | ✅ Success | `icmp_blocked` | ICMP blocked (firewall) |
| ❌ Fail | ❌ Fail | `unresponsive` | Network down / offline |

**Check Health Status:**
- Look at `sensor.cable_modem_health_status` (v2.6.0+)
- Check `sensor.cable_modem_ping_latency_ms` for network performance
- Check `sensor.cable_modem_http_latency_ms` for web server performance
- Monitor `sensor.cable_modem_availability` for uptime percentage

**What to Do:**
- **Degraded**: Web server crashed, try restarting modem
- **ICMP Blocked**: Firewall blocking ping, check network settings
- **Unresponsive**: Check modem power, cables, and network connection

***REMOVED******REMOVED******REMOVED******REMOVED*** 3. Wrong Credentials

**Symptoms:**
- Consistent login failures
- Error message about authentication
- Works from web browser but not from integration

**Solution:**
1. Verify credentials work in web browser
2. Check for special characters (some parsers may need escaping)
3. Update credentials in integration settings:
   - Settings → Devices & Services → Cable Modem Monitor
   - Click Configure → Update credentials

***REMOVED******REMOVED******REMOVED******REMOVED*** 4. Incorrect IP Address or Port

**Symptoms:**
- Connection errors every poll
- Never connects successfully
- "Network unreachable" errors

**Solution:**
1. Verify modem IP address:
   ```bash
   ping 192.168.100.1  ***REMOVED*** or your modem IP
   ```
2. Check if HTTP is enabled on modem (some ISPs disable web interface)
3. Try default gateway IP:
   - Windows: `ipconfig | findstr "Default Gateway"`
   - Linux/Mac: `ip route | grep default`

***REMOVED******REMOVED******REMOVED******REMOVED*** 5. ISP Disabled Web Interface

**Symptoms:**
- Cannot access modem web interface from ANY device
- Integration always fails to connect
- Modem works for internet but no web UI

**Solution:**
- Some ISPs disable modem web interfaces (Xfinity, Rogers, etc.)
- **No workaround available** - Contact your ISP
- Consider using modem stats from ISP app if available

***REMOVED******REMOVED******REMOVED*** Using Health Monitoring to Diagnose Issues

**Diagnostic Sensors**

Three sensors help diagnose connectivity:

1. **Cable Modem Health Status** (`sensor.cable_modem_health_status`)
   - Shows: `healthy`, `degraded`, `icmp_blocked`, or `unresponsive`
   - Use in automations to alert on modem issues

2. **Cable Modem Ping Latency** (`sensor.cable_modem_ping_latency`)
   - Shows Layer 3 (ICMP) response time in milliseconds
   - Normal: 1-10ms for local network
   - Alert if >100ms consistently

3. **Cable Modem HTTP Latency** (`sensor.cable_modem_http_latency`)
   - Shows Layer 7 (HTTP) response time in milliseconds
   - Normal: 10-50ms for local network
   - Alert if >500ms consistently

> **📚 Network Layers**: These refer to the [OSI model](https://grokipedia.com/page/OSI_model). Layer 3 (Network) handles IP routing and ICMP ping, while Layer 7 (Application) handles HTTP. By testing both layers, we can pinpoint whether issues are at the network level or the modem's web server.

**Example Automation:**
```yaml
automation:
  - alias: "Cable Modem Health Alert"
    trigger:
      - platform: state
        entity_id: sensor.cable_modem_health_status
        to: "unresponsive"
        for:
          minutes: 5
    action:
      - service: notify.mobile_app
        data:
          title: "Modem Offline"
          message: "Cable modem is not responding. Check power and connections."
```

***REMOVED******REMOVED******REMOVED*** Modem Model Selection

During setup and in settings, you can select your specific modem model or use auto-detection:

**Auto Detection (Recommended):**
- Select "auto" from the Modem Model dropdown
- Integration will try all available parsers to find the right one
- Successful detection info is shown in notifications
- Detection result is cached for faster subsequent connections

**Manual Selection:**
- Choose your specific modem model if auto-detection doesn't work
- Useful if you know your exact model
- Faster connection since it skips auto-detection
- Required for some modems with unique authentication

**Viewing Auto-Detection Logs:**

When using auto-detection, INFO-level logs show the detection process:

```
INFO [config_flow] Using auto-detection mode (modem_choice=auto, cached_parser=None)
INFO [config_flow] No cached parser, will try all available parsers
INFO [config_flow] Attempting to connect to modem at 192.168.100.1
INFO [modem_scraper] Tier 3: Auto-detection mode - trying all parsers
INFO [modem_scraper] Successfully connected to http://192.168.100.1/MotoSwInfo.asp
INFO [config_flow] Detection successful: {'modem_name': 'Motorola MB7621', 'manufacturer': 'Motorola', ...}
INFO [config_flow] Auto-detection successful: updating modem_choice from 'auto' to 'Motorola MB7621'
```

**How to View These Logs:**

INFO-level messages may not appear in the filtered Home Assistant logs UI. To see them:

1. **Method 1 - Download Raw Logs:**
   - Settings → System → Logs
   - Click "Download full log"
   - Open the downloaded file and search for "auto-detection" or "Detection successful"

2. **Method 2 - View Raw Logs (if available):**
   - Settings → System → Logs
   - Look for "View Raw Logs" link
   - Search for "cable_modem_monitor" and "auto-detection"

3. **Method 3 - SSH/Terminal:**
   ```bash
   docker logs homeassistant 2>&1 | grep -i "auto-detection\|Detection successful"
   ```

**If Auto-Detection Fails:**

If you see errors or auto-detection doesn't find your modem:
1. Check the logs for which parsers were attempted
2. Note any error messages (SSL errors, connection refused, etc.)
3. Try manually selecting your modem model if you know it
4. Open a GitHub issue with the auto-detection logs

***REMOVED******REMOVED******REMOVED*** Viewing Detailed Logs

**Normal Logs (INFO level):**
```
XB7: Successfully authenticated and fetched status page
```

**Debug Logs (for troubleshooting):**
```yaml
***REMOVED*** configuration.yaml
logger:
  default: info
  logs:
    custom_components.cable_modem_monitor: debug
```

**What You'll See in Debug Mode:**
- XB7 login flow details
- Timeout details (without stack traces)
- Connection error details
- Parsing debug information
- Detailed auto-detection attempts (all parsers tried, all URLs attempted)

**After enabling debug logging:**
1. Reload integration
2. Wait for next poll
3. Check logs: Settings → System → Logs
4. Search for "cable_modem_monitor"

---

***REMOVED******REMOVED*** Upstream Sensors Not Appearing

***REMOVED******REMOVED******REMOVED*** Problem: No Upstream Channel Sensors Created

**Symptoms:**
- You see `sensor.cable_modem_upstream_channel_count` showing 4-8 channels
- But individual upstream sensors (`US Ch X Power`, `US Ch X Frequency`) are missing
- Only downstream sensors are created

**Causes:**
1. **Missing Frequency Data** - Some modems don't report upstream frequency (fixed in v2.0.0)
2. **Parser Column Mismatch** - Parser reading from wrong HTML table columns (fixed in v2.0.0)
3. **Validation Too Strict** - Upstream channels rejected due to missing optional data (fixed in v2.0.0)

**Solution:**

1. **Upgrade to v2.0.0 or later** - These issues are fixed
2. **Check logs** for parsing errors:
   - Settings → System → Logs
   - Search for "cable_modem_monitor"
   - Look for "Parsed upstream channel" messages
3. **Enable debug logging** to see detailed parsing:
   ```yaml
   logger:
     default: info
     logs:
       custom_components.cable_modem_monitor: debug
   ```
4. **Reload the integration**:
   - Settings → Devices & Services → Cable Modem Monitor
   - Click ⋮ (three dots) → Reload

If upstream sensors still don't appear after upgrading to v2.0.0+, please [open an issue](https://github.com/solentlabs/cable_modem_monitor/issues) with:
- Your modem model
- Debug logs showing upstream parsing
- Diagnostics download from the integration

---

***REMOVED******REMOVED*** Orphaned Channel Sensors

***REMOVED******REMOVED******REMOVED*** Problem: Unavailable Channel Sensors After Cable Company Changes

**Symptoms:**
- Some channel sensors show "unavailable" permanently
- Happened after cable company made network changes
- Modem now reports fewer channels than before

**Cause:**
Sensors are created at integration startup based on the channels your modem reports. If your cable company decommissions channels, the sensors persist but return no data.

**Solution:**
Press the **Reset Entities** button to clean up:
1. Settings → Devices & Services → Cable Modem Monitor
2. Click on the device
3. Press "Reset Entities" button
4. Integration will reload with only current channels

Historical data is preserved - the same channels will reconnect to their history.

---

***REMOVED******REMOVED*** Duplicate Entities

***REMOVED******REMOVED******REMOVED*** Problem: Seeing Same Entity Twice (One Under Device, One Ungrouped)

**Symptoms:**
- Same sensor name appears twice in entity list
- One is under "Cable Modem" device
- One is under "Ungrouped" or orphaned
- Often happens after renaming entities

**Cause:**
Browser cache is showing old entity registry data.

**Solution:**

1. **Hard Refresh Browser**
   - Windows/Linux: `Ctrl + Shift + R`
   - Mac: `Cmd + Shift + R`

2. **Or Clear Browser Cache**
   - Clear cache for your Home Assistant URL
   - Reload the page

3. **Or Restart Home Assistant**
   - Settings → System → Restart
   - This forces a complete refresh

The "Ungrouped" entity will disappear once the browser cache is cleared.

---

***REMOVED******REMOVED*** Getting Help

If you encounter issues not covered here:

1. **Check Logs**: Settings → System → Logs
2. **Enable Debug Logging**:
   ```yaml
   logger:
     default: info
     logs:
       custom_components.cable_modem_monitor: debug
   ```
3. **Download Diagnostics** (Highly Recommended):
   - Settings → Devices & Services → Cable Modem Monitor
   - Click ⋮ → Download diagnostics
   - **Diagnostics now include:**
     - Configuration and detection info
     - Modem data and channel information
     - Recent logs (last 150 entries, sanitized)
     - Error details
   - This provides complete debugging information in one file!
4. **Open an Issue**: [GitHub Issues](https://github.com/solentlabs/cable_modem_monitor/issues)
   - Include your modem model
   - Attach diagnostics file (includes logs automatically)
   - If diagnostics aren't available, include manual logs

---

***REMOVED******REMOVED*** Quick Reference

***REMOVED******REMOVED******REMOVED*** Correct Entity ID Format (v2.0+)

| Sensor Type | Entity ID | Display Name |
|------------|-----------|--------------|
| Downstream Power | `sensor.cable_modem_downstream_ch_1_power` | DS Ch 1 Power |
| Downstream SNR | `sensor.cable_modem_downstream_ch_1_snr` | DS Ch 1 SNR |
| Upstream Power | `sensor.cable_modem_upstream_ch_1_power` | US Ch 1 Power |
| Upstream Frequency | `sensor.cable_modem_upstream_ch_1_frequency` | US Ch 1 Frequency |
| Channel Count | `sensor.cable_modem_downstream_channel_count` | DS Channel Count |

**Note:**
- Entity IDs always include `cable_modem_` prefix
- Display names use DS/US abbreviations (industry standard)
- DS = Downstream, US = Upstream
