***REMOVED*** Quick Upgrade Summary - v1.2.2

***REMOVED******REMOVED*** What Was Fixed

Your cable modem integration was recording **0 values at 12:03am** instead of skipping that bad reading. This has been fixed.

***REMOVED******REMOVED*** Root Cause

The `_extract_number()` and `_extract_float()` functions were returning `0` when they couldn't parse valid data from the modem. This meant during brief network issues or modem reboots, all your sensors would record zeros instead of skipping the update.

***REMOVED******REMOVED*** Changes Made

***REMOVED******REMOVED******REMOVED*** 1. modem_scraper.py
- ✅ `_extract_number()` now returns `None` instead of `0` for invalid data
- ✅ `_extract_float()` now returns `None` instead of `0.0` for invalid data
- ✅ Added validation to skip channels when all values are `None`
- ✅ Skip entire update if no valid channel data is found
- ✅ Fixed error calculations to handle `None` values

***REMOVED******REMOVED******REMOVED*** 2. diagnostics.py (NEW)
- ✅ Added diagnostics platform for troubleshooting
- ✅ Accessible via HA UI: Settings → Devices & Services → Cable Modem Monitor → Download Diagnostics
- ✅ Shows channel data, error counts, connection status, and any errors

***REMOVED******REMOVED******REMOVED*** 3. Documentation
- ✅ `cleanup_zero_values.md` - Guide to remove existing bad data from history
- ✅ `DEPLOYMENT_GUIDE.md` - Detailed upgrade instructions
- ✅ `deploy_to_ha.sh` - Automated deployment script
- ✅ Updated `CHANGELOG.md` with full release notes

***REMOVED******REMOVED******REMOVED*** 4. Version Updates
- ✅ Version bumped from 1.2.1 → 1.2.2
- ✅ Git commit and push completed
- ✅ GitHub release created: https://github.com/kwschulz/cable_modem_monitor/releases/tag/v1.2.2

***REMOVED******REMOVED*** Next Steps for You

***REMOVED******REMOVED******REMOVED*** Step 1: Deploy to Home Assistant

**Option A: Manual (Recommended for first time)**

1. Open Home Assistant File Editor
2. Navigate to `/config/custom_components/cable_modem_monitor/`
3. Update these files:
   - `manifest.json` (version 1.2.2)
   - `modem_scraper.py` (new validation logic)
   - `diagnostics.py` (NEW file - add this)
4. Restart Home Assistant

**Option B: Using SSH (if you have keys set up)**
```bash
cd /mnt/c/Users/ken_s/OneDrive/Documents/Projects/cable_modem_monitor
./deploy_to_ha.sh 192.168.5.2 claude 22
```

***REMOVED******REMOVED******REMOVED*** Step 2: Verify Installation

1. Go to Settings → Devices & Services → Cable Modem Monitor
2. Should show version **1.2.2**
3. Download diagnostics to verify it's working
4. Check logs for any issues

***REMOVED******REMOVED******REMOVED*** Step 3: Clean Up Historical Data

The zeros at 12:03am are still in your database. To remove them:

**See `cleanup_zero_values.md` for full instructions.**

Quick SQL method (backup first!):
```bash
***REMOVED*** SSH into Home Assistant
ssh claude@192.168.5.2

***REMOVED*** Backup database
cp /config/home-assistant_v2.db /config/home-assistant_v2.db.backup

***REMOVED*** Connect to database
sqlite3 /config/home-assistant_v2.db

***REMOVED*** Delete zeros from that specific time
DELETE FROM states
WHERE metadata_id IN (
    SELECT metadata_id FROM states_meta
    WHERE entity_id LIKE 'sensor.downstream_ch_%'
    OR entity_id LIKE 'sensor.upstream_ch_%'
)
AND state = '0'
AND datetime(last_updated, 'localtime') BETWEEN '2025-10-21 00:00:00' AND '2025-10-21 00:10:00';

.quit

***REMOVED*** Restart HA
ha core restart
```

***REMOVED******REMOVED******REMOVED*** Step 4: Monitor

Watch for the next 24 hours to ensure:
- ✅ No new zero values appear
- ✅ Integration logs show proper validation
- ✅ Sensors update normally

***REMOVED******REMOVED*** Files Changed

```
modified:   CHANGELOG.md
modified:   custom_components/cable_modem_monitor/manifest.json
modified:   custom_components/cable_modem_monitor/modem_scraper.py
new:        custom_components/cable_modem_monitor/diagnostics.py
new:        DEPLOYMENT_GUIDE.md
new:        cleanup_zero_values.md
new:        deploy_to_ha.sh
new:        UPGRADE_SUMMARY.md (this file)
```

***REMOVED******REMOVED*** What You'll See in Logs

After the update, when the modem returns bad data:

```
WARNING (MainThread) [custom_components.cable_modem_monitor.modem_scraper] Skipping downstream channel with all null values: <empty>
ERROR (MainThread) [custom_components.cable_modem_monitor.modem_scraper] No valid channel data parsed from modem - skipping update
```

This is **GOOD** - it means the integration is correctly rejecting invalid data instead of recording zeros!

***REMOVED******REMOVED*** Need Help?

1. Check `DEPLOYMENT_GUIDE.md` for detailed instructions
2. Check `cleanup_zero_values.md` for database cleanup
3. Download diagnostics from HA UI
4. Open GitHub issue with diagnostics if problems persist

***REMOVED******REMOVED*** GitHub

- **Release**: https://github.com/kwschulz/cable_modem_monitor/releases/tag/v1.2.2
- **Issues**: https://github.com/kwschulz/cable_modem_monitor/issues
- **Commits**: https://github.com/kwschulz/cable_modem_monitor/commits/main
