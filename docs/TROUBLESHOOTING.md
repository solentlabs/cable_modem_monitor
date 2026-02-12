# Troubleshooting Guide

Common issues and solutions for Cable Modem Monitor integration.

## Table of Contents
- [Connection and Authentication Issues](#connection-and-authentication-issues)
  - [Degraded Mode (Ping Works, HTTP Doesn't)](#2b-degraded-mode-ping-works-http-doesnt)
  - [Auth Discovery Issues (v3.12+)](#4-auth-discovery-issues-v312)
  - [Combo Modem/Routers (Two IP Addresses)](#6-combo-modemrouters-two-ip-addresses)
- [Upstream Sensors Not Appearing](#upstream-sensors-not-appearing)
- [Orphaned Channel Sensors](#orphaned-channel-sensors)
- [Duplicate Entities](#duplicate-entities)

---

## Connection and Authentication Issues

### Problem: Login Failures and Timeout Errors

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

#### 1. Modem Rebooting or Busy

**Symptoms:**
- Intermittent timeout errors
- Sensors occasionally unavailable
- Happens randomly, then recovers

**What's Happening:**
Cable modems periodically reboot or become busy during channel maintenance. This is normal.

**Solution:**
- **No action needed** - Integration will retry on next poll
- Check `sensor.cable_modem_status` to see current operational state
- If timeouts persist for >10 minutes, check modem power and connections

#### 2. Network Issues vs. Web Server Issues

**Dual-Layer Health Monitoring**

The integration performs both ICMP ping and HTTP checks to diagnose connectivity:

| ICMP Ping | HTTP HEAD | Status | Diagnosis |
|-----------|-----------|--------|-----------|
| ✅ Success | ✅ Success | `healthy` | Fully responsive |
| ✅ Success | ❌ Fail | `degraded` | Web server issue |
| ❌ Fail | ✅ Success | `icmp_blocked` | ICMP blocked (firewall) |
| ❌ Fail | ❌ Fail | `unresponsive` | Network down / offline |

**Check Status:**
- Look at `sensor.cable_modem_status` for overall operational state
- Check `sensor.cable_modem_ping_latency` for network performance
- Check `sensor.cable_modem_http_latency` for web server performance

**What to Do:**
- **ICMP Blocked**: Ping fails but HTTP works - check if modem blocks ICMP (set `supports_icmp = False` in parser)
- **Unresponsive**: Check modem power, cables, and network connection
- **Parser Error**: Modem reachable but data format changed - report issue with diagnostics

#### 2b. Degraded Mode (Ping Works, HTTP Doesn't)

**Symptoms:**
- Status sensor shows "Degraded"
- Ping Latency sensor shows a value (e.g., 1-5ms)
- HTTP Latency sensor shows "Unavailable"
- All channel sensors show "Unavailable"
- Modem web interface doesn't load in browser either

**What's Happening:**

The modem's embedded web server has hung while the underlying network stack continues working. This is a known behavior with consumer cable modem firmware - the modem's DOCSIS functions (internet connectivity) remain operational, but the status web server becomes unresponsive.

Common causes:
- Memory leak in the modem's web server accumulating over days/weeks
- Session table exhaustion from stale connections
- Internal resource deadlock

**What You'll See in Logs:**
```
WARNING: Scraper failed but modem is responding to health checks: [timeout error]
DEBUG: Health check: degraded (ping=True, http=False)
```

**Available Sensors in Degraded Mode:**
| Sensor | Status | Notes |
|--------|--------|-------|
| Ping Latency | ✅ Available | Shows ICMP response time |
| HTTP Latency | ❌ Unavailable | Web server not responding |
| Status | ✅ Available | Shows "Degraded" |
| Channel sensors | ❌ Unavailable | Require HTTP to fetch data |

**Recovery Options:**

1. **Wait for internal watchdog** (often works within hours)
   - Most modems have internal monitoring that will restart the hung web server
   - Your internet connection continues working during this time
   - The integration will automatically recover once HTTP responds

2. **Power cycle the modem** (immediate fix)
   - Unplug modem for 30 seconds, then reconnect
   - Will briefly interrupt internet connectivity

3. **Reload integration after recovery**
   - Once HTTP is working again, reload the integration to recreate all sensors
   - Settings → Devices & Services → Cable Modem Monitor → ⋮ → Reload

**Note:** If you only see 11 sensors instead of 100+, this means the integration started while in degraded mode. Reload the integration after HTTP recovers to get all channel sensors.

#### 3. Wrong Credentials

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

#### 4. Auth Discovery Issues (v3.12+)

**Symptoms:**
- Setup shows "Unknown authentication pattern"
- Diagnostics shows `auth_strategy: unknown`
- Modem works in browser but not in integration

**What's Happening:**

As of v3.12.0, the integration automatically detects your modem's authentication method
by inspecting the login page response. If detection fails, the integration captures
the response for debugging.

**Solution:**

1. **Check diagnostics export** - Look for `auth_discovery` section:
   ```json
   {
     "auth_discovery": {
       "status": "unknown_pattern",
       "strategy": "unknown",
       "captured_response": { ... }
     }
   }
   ```

2. **Share diagnostics** - Open an issue with your diagnostics export. The captured
   response helps developers add support for your modem's auth pattern.

3. **Capture HAR file** - For fastest fix, capture a browser HAR file during login:
   - Open browser Developer Tools → Network tab
   - Log into your modem
   - Right-click → Save all as HAR
   - **Sanitize before sharing**: `pip install har-capture && har-capture sanitize modem.har -o safe.har`
   - Attach sanitized file to GitHub issue
   - See [har-capture](https://github.com/solentlabs/har-capture) for automatic PII removal

**Common Auth Patterns:**

| Pattern | Detection | Notes |
|---------|-----------|-------|
| NO_AUTH | 200 + data | Modem allows anonymous access |
| BASIC_HTTP | 401 response | HTTP Basic Auth |
| FORM_PLAIN | HTML form with password | Standard login form |
| HNAP_SESSION | SOAPAction.js script | Arris S33, Motorola MB8611 |
| URL_TOKEN | JS-based form | Arris SB8200 |

#### 5. Incorrect IP Address or Port

**Symptoms:**
- Connection errors every poll
- Never connects successfully
- "Network unreachable" errors

**Solution:**
1. Verify modem IP address:
   ```bash
   ping 192.168.100.1  # or your modem IP
   ```
2. Check if HTTP is enabled on modem (some ISPs disable web interface)
3. Try default gateway IP:
   - Windows: `ipconfig | findstr "Default Gateway"`
   - Linux/Mac: `ip route | grep default`

#### 6. Combo Modem/Routers (Two IP Addresses)

**Symptoms:**
- Health status shows `icmp_blocked` but modem works
- One IP address works, another doesn't
- Slow response on one IP, fast on another

**What's Happening:**

Combo modem/router devices (like Netgear C3700, C7000, Arris TG series) have **two network interfaces** in one box:

```
[Cable ISP] ←→ [Cable Modem Chip] ←→ [Router Chip] ←→ [Your Devices]
                192.168.100.1          192.168.0.1
```

| Interface | Typical IP | Purpose | ICMP Ping |
|-----------|------------|---------|-----------|
| Cable Modem | 192.168.100.1 | DOCSIS management | Often blocked |
| Router LAN | 192.168.0.1 | Gateway for devices | Usually works |

**Why ICMP is blocked on one:**
- The modem interface (192.168.100.1) has stricter firewall rules
- ISPs often require blocking ICMP on the "upstream" interface for security
- The router interface (192.168.0.1) is the trusted LAN side

**Solution:**

If you see `icmp_blocked` status:
1. **Try the other IP address** - If using 192.168.100.1, try 192.168.0.1 (or vice versa)
2. **Check your gateway** - `ip route | grep default` shows your router's LAN IP
3. **Both IPs may work** - Choose based on preference:
   - Modem IP (192.168.100.1): Faster response, but `icmp_blocked` health status
   - Router IP (192.168.0.1): Full health status, but separate auth session

**Note:** This only applies to combo modem/router devices. Standalone modems (like Arris SB8200, Netgear CM2000) only have one interface.

#### 7. ISP Disabled Web Interface

**Symptoms:**
- Cannot access modem web interface from ANY device
- Integration always fails to connect
- Modem works for internet but no web UI

**Solution:**
- Some ISPs disable modem web interfaces (Xfinity, Rogers, etc.)
- **No workaround available** - Contact your ISP
- Consider using modem stats from ISP app if available

### Using Health Monitoring to Diagnose Issues

**Diagnostic Sensors**

Key sensors help diagnose connectivity:

1. **Cable Modem Status** (`sensor.cable_modem_status`)
   - Pass/fail status: `Operational`, `ICMP Blocked`, `Partial Lock`, `Not Locked`, `Parser Error`, `Unresponsive`
   - Use in automations to alert on modem issues
   - Combines connection, health, and DOCSIS lock status

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
  - alias: "Cable Modem Status Alert"
    trigger:
      - platform: state
        entity_id: sensor.cable_modem_status
        to: "Unresponsive"
        for:
          minutes: 5
    action:
      - service: notify.mobile_app
        data:
          title: "Modem Offline"
          message: "Cable modem is not responding. Check power and connections."
```

### Modem Model Selection

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
INFO [data_orchestrator] Tier 3: Auto-detection mode - trying all parsers
INFO [data_orchestrator] Successfully connected to http://192.168.100.1/MotoSwInfo.asp
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

### Viewing Detailed Logs

**Normal Logs (INFO level):**
```
XB7: Successfully authenticated and fetched status page
```

**Debug Logs (for troubleshooting):**
```yaml
# configuration.yaml
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

## Upstream Sensors Not Appearing

### Problem: No Upstream Channel Sensors Created

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

## Orphaned Channel Sensors

### Problem: Unavailable Channel Sensors After Cable Company Changes

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

## Duplicate Entities

### Problem: Seeing Same Entity Twice (One Under Device, One Ungrouped)

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

## Getting Help

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

## Quick Reference

### Entity ID Format (v3.11+)

Channel sensors now include channel type for DOCSIS 3.1 compatibility:

| Sensor Type | Entity ID | Display Name |
|------------|-----------|--------------|
| Downstream QAM Power | `sensor.cable_modem_ds_qam_ch_32_power` | DS QAM Ch 32 Power |
| Downstream OFDM Power | `sensor.cable_modem_ds_ofdm_ch_1_power` | DS OFDM Ch 1 Power |
| Downstream SNR | `sensor.cable_modem_ds_qam_ch_32_snr` | DS QAM Ch 32 SNR |
| Upstream ATDMA Power | `sensor.cable_modem_us_atdma_ch_3_power` | US ATDMA Ch 3 Power |
| Upstream OFDMA Power | `sensor.cable_modem_us_ofdma_ch_1_power` | US OFDMA Ch 1 Power |
| Channel Count | `sensor.cable_modem_downstream_channel_count` | DS Channel Count |

**Note:**
- Entity IDs always include `cable_modem_` prefix
- Channel type is included: `qam`, `ofdm`, `atdma`, `ofdma`
- DS = Downstream, US = Upstream

### DOCSIS Channel Types

Cable modems use different modulation schemes based on DOCSIS version:

| Channel Type | Direction | DOCSIS | Description | Spec Reference |
|-------------|-----------|--------|-------------|----------------|
| **QAM** | Downstream | 3.0/3.1 | [Quadrature Amplitude Modulation](https://en.wikipedia.org/wiki/QAM_(television)) - Traditional downstream channel using 256-QAM or 1024-QAM | [DOCSIS 3.0 PHY](https://www.cablelabs.com/specifications/CM-SP-PHYv3.0) |
| **OFDM** | Downstream | 3.1 | [Orthogonal Frequency-Division Multiplexing](https://en.wikipedia.org/wiki/Orthogonal_frequency-division_multiplexing) - High-capacity DOCSIS 3.1 downstream using 4096-QAM | [DOCSIS 3.1 PHY](https://www.cablelabs.com/specifications/CM-SP-PHYv3.1) |
| **ATDMA** | Upstream | 3.0/3.1 | [Advanced Time Division Multiple Access](https://en.wikipedia.org/wiki/DOCSIS#DOCSIS_2.0) - Traditional upstream channel | [DOCSIS 3.0 PHY](https://www.cablelabs.com/specifications/CM-SP-PHYv3.0) |
| **OFDMA** | Upstream | 3.1 | [Orthogonal Frequency-Division Multiple Access](https://en.wikipedia.org/wiki/Orthogonal_frequency-division_multiple_access) - High-capacity DOCSIS 3.1 upstream | [DOCSIS 3.1 PHY](https://www.cablelabs.com/specifications/CM-SP-PHYv3.1) |

**DOCSIS 3.0 modems:** Only have QAM (downstream) and ATDMA (upstream) channels.
**DOCSIS 3.1 modems:** Have both traditional channels (QAM/ATDMA) and high-capacity channels (OFDM/OFDMA).

### Sensor Attributes

Each channel sensor exposes these attributes:
- `channel_id`: CMTS-assigned channel identifier (stable per frequency)
- `channel_type`: Modulation type (qam, ofdm, atdma, ofdma)
- `frequency`: Channel frequency in Hz (power/SNR sensors only)
