# Deployment Guide - Cable Modem Monitor v1.2.2

This guide will help you deploy the updated integration to your Home Assistant instance.

## What's New in v1.2.2

- ✅ Fixed zero values being recorded in history during modem issues
- ✅ Added diagnostics support for troubleshooting
- ✅ Improved error handling and validation
- ✅ Documentation for cleaning up existing bad data

## Deployment Methods

### Method 1: Manual Copy via File Editor (Easiest)

1. **Access Home Assistant File Editor**
   - Install the "File Editor" add-on if not already installed
   - Navigate to Settings → Add-ons → File Editor

2. **Navigate to custom_components**
   - Open the file browser to `/config/custom_components/cable_modem_monitor/`

3. **Update Files**
   Copy the following files from your local project to Home Assistant:

   - `manifest.json` (updated version to 1.2.2)
   - `modem_scraper.py` (improved validation and error handling)
   - `diagnostics.py` (NEW - add this file)
   - `__init__.py` (unchanged, but confirm it's there)
   - `sensor.py` (unchanged, but confirm it's there)
   - Other files should remain unchanged

4. **Restart Home Assistant**
   - Go to Developer Tools → YAML
   - Click "Restart" under "Configuration Validation"
   - Or use Settings → System → Restart

### Method 2: SSH/SCP Deployment

If you have SSH access configured:

```bash
# From your project directory
cd /mnt/c/Users/ken_s/OneDrive/Documents/Projects/cable_modem_monitor

# Option A: Use the deployment script (requires SSH keys)
./deploy_to_ha.sh

# Option B: Manual SCP
scp -r custom_components/cable_modem_monitor/* claude@192.168.5.2:/config/custom_components/cable_modem_monitor/

# Restart Home Assistant
ssh claude@192.168.5.2 "ha core restart"
```

### Method 3: HACS Update (Future)

Once this is published to HACS:
1. Go to HACS → Integrations
2. Find "Cable Modem Monitor"
3. Click "Update"
4. Restart Home Assistant

## Post-Deployment Steps

### 1. Verify Installation

After restarting Home Assistant:

1. Check the integration is loaded:
   - Settings → Devices & Services
   - Find "Cable Modem Monitor"
   - Should show version 1.2.2

2. Check logs for any issues:
   - Settings → System → Logs
   - Look for "cable_modem_monitor" entries
   - You should see normal operation or warnings about invalid data (not errors)

### 2. Access Diagnostics

The new diagnostics feature is available:

1. Go to Settings → Devices & Services
2. Click on "Cable Modem Monitor" integration
3. Click the three dots menu (⋮)
4. Select "Download diagnostics"
5. This will download a JSON file with:
   - Current channel data
   - Error counts
   - Last update status
   - Any errors encountered

### 3. Clean Up Historical Zero Values

If you have existing zero values in your history (like the ones at 12:03am), follow the cleanup guide:

**See `cleanup_zero_values.md` for detailed instructions**

Quick option - Purge specific time range (SQL):
```sql
-- Backup first!
cp /config/home-assistant_v2.db /config/home-assistant_v2.db.backup

-- Delete zero values from specific time
sqlite3 /config/home-assistant_v2.db
DELETE FROM states
WHERE metadata_id IN (
    SELECT metadata_id FROM states_meta
    WHERE entity_id LIKE 'sensor.downstream_ch_%'
    OR entity_id LIKE 'sensor.upstream_ch_%'
)
AND state = '0'
AND datetime(last_updated, 'localtime') BETWEEN '2025-10-21 00:00:00' AND '2025-10-21 00:10:00';
.quit
```

### 4. Monitor for Future Issues

With the new changes:

- ✅ Invalid data will be skipped (no more zeros in history)
- ✅ Warnings will be logged when bad data is detected
- ✅ Integration will retry next update cycle automatically
- ✅ Diagnostics available for troubleshooting

Watch the logs for these messages:
- `Skipping downstream channel with all null values` - Normal, invalid data was rejected
- `No valid channel data parsed from modem - skipping update` - Modem unreachable or returning bad data
- `Error communicating with modem` - Network/connection issue

## Verification Checklist

- [ ] Integration shows version 1.2.2
- [ ] Sensors are updating normally
- [ ] No errors in Home Assistant logs
- [ ] Diagnostics download works
- [ ] Historical zero values cleaned up (if applicable)
- [ ] Monitor for 24 hours to ensure no new zero values appear

## Rollback (If Needed)

If you need to rollback to the previous version:

1. SSH into Home Assistant:
   ```bash
   ssh claude@192.168.5.2
   ```

2. Restore backup:
   ```bash
   # List backups
   ls -la /config/custom_components/cable_modem_monitor.backup-*

   # Restore the most recent
   rm -rf /config/custom_components/cable_modem_monitor
   cp -r /config/custom_components/cable_modem_monitor.backup-YYYYMMDD-HHMMSS /config/custom_components/cable_modem_monitor
   ```

3. Restart Home Assistant:
   ```bash
   ha core restart
   ```

## Troubleshooting

### Integration Won't Load

1. Check file permissions:
   ```bash
   ls -la /config/custom_components/cable_modem_monitor/
   ```

2. Verify all files are present:
   - `__init__.py`
   - `manifest.json`
   - `config_flow.py`
   - `const.py`
   - `modem_scraper.py`
   - `sensor.py`
   - `button.py`
   - `diagnostics.py` (NEW)

3. Check logs for specific errors

### Sensors Not Updating

1. Download diagnostics (see step 2 above)
2. Check `last_update_success` status
3. Look for errors in the diagnostics output
4. Verify modem is accessible from Home Assistant

### Still Seeing Zero Values

If you still see zeros after the update:

1. Check that version is actually 1.2.2
2. Verify the integration restarted (check logs for init messages)
3. Download diagnostics to see current data
4. Check that the zero values are NEW (not old historical data)

## Getting Help

If you encounter issues:

1. Download diagnostics
2. Check Home Assistant logs
3. Open an issue on GitHub with:
   - Diagnostics file
   - Relevant log entries
   - Description of the problem
   - Home Assistant version

GitHub Issues: https://github.com/kwschulz/cable_modem_monitor/issues
