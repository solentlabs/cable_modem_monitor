# Troubleshooting Guide

Common issues and solutions for Cable Modem Monitor.

> **Authoritative references:**
>
> - [ORCHESTRATION_SPEC.md](../packages/cable_modem_monitor_core/docs/ORCHESTRATION_SPEC.md) — logging contracts, signal policy, health probes
> - [ENTITY_MODEL_SPEC.md](../custom_components/cable_modem_monitor/docs/ENTITY_MODEL_SPEC.md) — status cascade, entity model
> - [RUNTIME_POLLING_SPEC.md](../packages/cable_modem_monitor_core/docs/RUNTIME_POLLING_SPEC.md) — polling behavior, backoff, circuit breaker

## Table of Contents

- [Connection and Authentication Issues](#connection-and-authentication-issues)
  - [Degraded Mode (Web Server Hung)](#2b-degraded-mode-web-server-hung)
  - [Combo Modem/Routers (Two IP Addresses)](#6-combo-modemrouters-two-ip-addresses)
- [Understanding the Status Sensor](#understanding-the-status-sensor)
- [Understanding Log Output](#understanding-log-output)
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

**Log severity levels:**

| Condition | Level | Rationale |
| ----------- | ------- | ----------- |
| Timeouts | DEBUG | Modem may be busy or rebooting |
| Connection errors | WARNING | Network issue |
| Authentication failures | ERROR | Wrong credentials |

See [ORCHESTRATION_SPEC.md § Logging Contract](../packages/cable_modem_monitor_core/docs/ORCHESTRATION_SPEC.md#logging-contract) for the full logging contract.

**Common Causes & Solutions:**

#### 1. Modem Rebooting or Busy

**Symptoms:**

- Intermittent timeout errors
- Sensors occasionally unavailable
- Happens randomly, then recovers

Cable modems periodically reboot or become busy during channel maintenance. This is normal — the integration retries on the next poll. If timeouts persist for >10 minutes, check modem power and connections.

#### 2. Network Issues vs. Web Server Issues

The integration uses health probes (ICMP ping and HTTP HEAD/GET) to diagnose connectivity independently of data collection:

| ICMP | HTTP | Health Status | Diagnosis |
| ------ | ------ | --------------- | ----------- |
| Pass | Pass | `responsive` | Fully responsive |
| Pass | Fail | `degraded` | Web server may be hung |
| Fail | Pass | `icmp_blocked` | Network blocks ICMP |
| Fail | Fail | `unresponsive` | Modem is down |

Health probes are lightweight and run on their own cadence. Status transitions log at INFO (recovery) or WARNING (degradation); steady-state produces no visible output at default log levels.

See [ORCHESTRATION_SPEC.md § HealthMonitor](../packages/cable_modem_monitor_core/docs/ORCHESTRATION_SPEC.md#healthmonitor) for probe strategy and configuration details.

#### 2b. Degraded Mode (Web Server Hung)

**Symptoms:**

- Status sensor shows "Degraded"
- Ping Latency shows a value (e.g., 1-5ms)
- HTTP Latency shows "Unavailable"
- All channel sensors show "Unavailable"
- Modem web interface doesn't load in browser either

**What's Happening:**

The modem's embedded web server has hung while the underlying network stack continues working. The modem's DOCSIS functions (internet connectivity) remain operational, but the status web server is unresponsive.

Common causes:

- Memory leak in the modem's web server accumulating over days/weeks
- Session table exhaustion from stale connections
- Internal resource deadlock

**What You'll See in Logs:**

```
WARNING: Health check [MB7621]: degraded (ICMP 2ms, HTTP HEAD timeout)
```

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
   - Settings > Devices & Services > Cable Modem Monitor > ... > Reload

**Note:** If you only see a few sensors instead of 100+, the integration may have started while in degraded mode. Reload the integration after HTTP recovers to get all channel sensors.

#### 3. Wrong Credentials

**Symptoms:**

- Consistent login failures
- Error message about authentication
- Works from web browser but not from integration

**Solution:**

1. Verify credentials work in web browser
2. Check for special characters (some auth strategies may need escaping)
3. Update credentials in integration settings:
   - Settings > Devices & Services > Cable Modem Monitor
   - Click Configure > Update credentials

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
[Cable ISP] <-> [Cable Modem Chip] <-> [Router Chip] <-> [Your Devices]
                192.168.100.1          192.168.0.1
```

| Interface | Typical IP | Purpose | ICMP Ping |
| ----------- | ------------ | --------- | ----------- |
| Cable Modem | 192.168.100.1 | DOCSIS management | Often blocked |
| Router LAN | 192.168.0.1 | Gateway for devices | Usually works |

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

---

## Understanding the Status Sensor

The `sensor.cable_modem_status` entity combines three independent signals into a single display state using a 10-level priority cascade:

| Priority | Condition | Display State |
| ---------- | ----------- | --------------- |
| 1 | Health: unresponsive | Unresponsive |
| 2 | Connection: unreachable | Unreachable |
| 3 | Connection: auth_failed | Auth Failed |
| 4 | Health: degraded | Degraded |
| 5 | Connection: parser_issue | Parser Error |
| 6 | Connection: no_signal | No Signal |
| 7 | DOCSIS: not_locked | Not Locked |
| 8 | DOCSIS: partial_lock | Partial Lock |
| 9 | Health: icmp_blocked | ICMP Blocked |
| 10 | default | Operational |

The three input signals are:

- **connection_status** — from the data collection pipeline (auth, fetch, parse)
- **health_status** — from lightweight health probes (ICMP, HTTP)
- **docsis_status** — from downstream channel lock status

See [ENTITY_MODEL_SPEC.md § Status Sensor](../custom_components/cable_modem_monitor/docs/ENTITY_MODEL_SPEC.md#status-sensor) for full details.

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

---

## Understanding Log Output

All log lines include a `[MODEL]` tag for multi-modem disambiguation.

**The "pulse" — steady-state INFO output:**

At default log levels, a healthy modem produces one INFO line per poll:

```
Parse complete [MB7621]: 24 DS, 4 US channels
```

This is the integration's heartbeat. Auth, resource loading, and session details log at INFO on the first poll, then drop to DEBUG to keep multi-modem logs clean.

**Failures are always visible:**

```
WARNING: Poll failed [MB7621] — signal: connectivity, error: Connection timed out
WARNING: Health check [MB7621]: degraded (ICMP 2ms, HTTP HEAD timeout)
ERROR: Circuit breaker OPEN [MB7621] — polling stopped. Reconfigure credentials to resume.
```

**Enable debug logging for full detail:**

```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.cable_modem_monitor: debug
```

After enabling debug logging:

1. Reload integration
2. Wait for next poll
3. Check logs: Settings > System > Logs
4. Search for "cable_modem_monitor"

See [ORCHESTRATION_SPEC.md § Logging Contract](../packages/cable_modem_monitor_core/docs/ORCHESTRATION_SPEC.md#logging-contract-1) for the full log level tiers and example output.

---

## Upstream Sensors Not Appearing

### Problem: No Upstream Channel Sensors Created

**Symptoms:**

- You see `sensor.cable_modem_upstream_channel_count` showing 4-8 channels
- But individual upstream sensors (`US Ch X Power`, `US Ch X Frequency`) are missing
- Only downstream sensors are created

**Solution:**

1. **Upgrade to latest version** - Early versions had upstream parsing issues
2. **Check logs** for parsing errors:
   - Settings > System > Logs
   - Search for "cable_modem_monitor"
3. **Enable debug logging** to see detailed parsing
4. **Reload the integration**:
   - Settings > Devices & Services > Cable Modem Monitor
   - Click ... (three dots) > Reload

If upstream sensors still don't appear, please [open an issue](https://github.com/solentlabs/cable_modem_monitor/issues) with:

- Your modem model
- Debug logs showing parsing output
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

1. Settings > Devices & Services > Cable Modem Monitor
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
   - Settings > System > Restart
   - This forces a complete refresh

The "Ungrouped" entity will disappear once the browser cache is cleared.

---

## Getting Help

If you encounter issues not covered here:

1. **Check Logs**: Settings > System > Logs
2. **Enable Debug Logging** (see [Understanding Log Output](#understanding-log-output))
3. **Download Diagnostics** (Highly Recommended):
   - Settings > Devices & Services > Cable Modem Monitor
   - Click ... > Download diagnostics
   - Includes: configuration, modem data, recent logs (sanitized), error details
4. **Open an Issue**: [GitHub Issues](https://github.com/solentlabs/cable_modem_monitor/issues)
   - Include your modem model
   - Attach diagnostics file (includes logs automatically)
   - If diagnostics aren't available, include manual logs

---

## Quick Reference

### Entity ID Format

Channel sensors include channel type for DOCSIS 3.1 compatibility:

| Sensor Type | Entity ID | Display Name |
| ------------ | ----------- | -------------- |
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

| Channel Type | Direction | DOCSIS | Description |
| ------------- | ----------- | -------- | ------------- |
| **QAM** | Downstream | 3.0/3.1 | Traditional downstream (256-QAM or 1024-QAM) |
| **OFDM** | Downstream | 3.1 | High-capacity DOCSIS 3.1 downstream (4096-QAM) |
| **ATDMA** | Upstream | 3.0/3.1 | Traditional upstream |
| **OFDMA** | Upstream | 3.1 | High-capacity DOCSIS 3.1 upstream |

**DOCSIS 3.0 modems:** Only have QAM (downstream) and ATDMA (upstream) channels.
**DOCSIS 3.1 modems:** Have both traditional channels (QAM/ATDMA) and high-capacity channels (OFDM/OFDMA).

### Sensor Attributes

Each channel sensor exposes these attributes:

- `channel_id`: CMTS-assigned channel identifier (stable per frequency)
- `channel_type`: Modulation type (qam, ofdm, atdma, ofdma)
- `frequency`: Channel frequency in Hz (power/SNR sensors only)
