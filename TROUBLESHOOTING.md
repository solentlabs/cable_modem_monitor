# Troubleshooting Guide

Common issues and solutions for Cable Modem Monitor integration.

## Table of Contents
- [Entity ID Cleanup](#entity-id-cleanup)
- [Upstream Sensors Not Appearing](#upstream-sensors-not-appearing)
- [Duplicate Entities](#duplicate-entities)
- [Migration Issues](#migration-issues)

---

## Entity ID Cleanup

### Problem: Old Entity IDs Without `cable_modem_` Prefix

**Symptoms:**
- Entities like `sensor.us_ch_1_power` or `sensor.downstream_ch_1_power` exist
- Cannot delete them through the UI (delete button disabled)
- These are from before v2.0 entity naming standardization

**Why This Happens:**
These entities were created before v2.0's automatic entity ID migration, or were created after migration but with the wrong naming scheme. They're tied to the active config entry, which prevents normal deletion.

**Solution: Rename Entities to Use Correct Prefix**

You can rename them through the UI or use a script for bulk updates.

#### Option 1: Manual Rename (1-2 entities)

1. Go to **Settings → Devices & Services → Entities**
2. Search for the old entity (e.g., `us_ch_1_power`)
3. Click on it
4. Click the **settings gear icon**
5. Under "Entity ID", change it to include the `cable_modem_` prefix:
   - `sensor.us_ch_1_power` → `sensor.cable_modem_upstream_ch_1_power`
   - `sensor.downstream_ch_1_power` → `sensor.cable_modem_downstream_ch_1_power`
6. Click **Update**
7. **Restart Home Assistant**
8. **Hard refresh your browser** (Ctrl+Shift+R) to clear cache

#### Option 2: Bulk Rename Script (10+ entities)

If you have many entities to rename, use this Python script:

**⚠️ IMPORTANT: Stop Home Assistant before running this script!**

```python
#!/usr/bin/env python3
"""
Rename cable modem entities to use correct cable_modem_ prefix.
Run this script while Home Assistant is STOPPED.
"""
import json
import sys

# Define the renames needed (add your specific entities here)
renames = {
    'sensor.us_ch_1_power': 'sensor.cable_modem_upstream_ch_1_power',
    'sensor.us_ch_1_frequency': 'sensor.cable_modem_upstream_ch_1_frequency',
    'sensor.us_ch_2_power': 'sensor.cable_modem_upstream_ch_2_power',
    'sensor.us_ch_2_frequency': 'sensor.cable_modem_upstream_ch_2_frequency',
    # Add more as needed...
}

# Load entity registry
registry_path = '/config/.storage/core.entity_registry'
try:
    with open(registry_path, 'r') as f:
        data = json.load(f)
except FileNotFoundError:
    print(f"ERROR: Could not find {registry_path}")
    print("Make sure you run this on your Home Assistant server")
    sys.exit(1)

# Create backup
backup_path = registry_path + '.backup'
with open(backup_path, 'w') as f:
    json.dump(data, f, indent=2)
print(f"✓ Backup created: {backup_path}")

# Rename entities
renamed = 0
skipped = 0
for entity in data['data']['entities']:
    old_id = entity.get('entity_id')
    if old_id in renames:
        new_id = renames[old_id]
        # Check if new_id already exists
        existing = any(e.get('entity_id') == new_id for e in data['data']['entities'])
        if existing:
            print(f"⊗ Skipping {old_id}: {new_id} already exists")
            skipped += 1
            continue
        entity['entity_id'] = new_id
        print(f"✓ Renamed: {old_id} → {new_id}")
        renamed += 1

print(f"\nTotal renamed: {renamed}")
print(f"Skipped (already exist): {skipped}")

if renamed > 0:
    # Save the updated registry
    with open(registry_path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"\n✓ Changes saved to {registry_path}")
    print("\nNext steps:")
    print("1. Start Home Assistant")
    print("2. Hard refresh your browser (Ctrl+Shift+R)")
    print("3. Verify entities appear with new names")
else:
    print("\nNo changes made.")
```

**Steps:**

1. **Stop Home Assistant** (Settings → System → Stop)
2. Copy the script to your Home Assistant server
3. Edit the `renames` dictionary with your specific entity IDs
4. Run: `sudo python3 rename_entities.py`
5. **Start Home Assistant**
6. **Hard refresh your browser** (Ctrl+Shift+R)

**To restore from backup if needed:**
```bash
sudo cp /config/.storage/core.entity_registry.backup /config/.storage/core.entity_registry
```

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

If upstream sensors still don't appear after upgrading to v2.0.0+, please [open an issue](https://github.com/kwschulz/cable_modem_monitor/issues) with:
- Your modem model
- Debug logs showing upstream parsing
- Diagnostics download from the integration

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

## Migration Issues

### Problem: Entities Not Migrating from v1.x to v2.0

**Symptoms:**
- After upgrading to v2.0, entities still have old IDs
- No automatic migration occurred
- Entities use old naming without `cable_modem_` prefix

**What Should Happen:**
v2.0 includes automatic entity ID migration that runs on first startup after upgrade.

**If Migration Didn't Work:**

1. **Check if migration ran**:
   - Settings → System → Logs
   - Search for "Migrating" or "entity_id"
   - Look for migration log messages

2. **Manual Migration Options**:
   - See [UPGRADING.md](UPGRADING.md) for detailed steps
   - Option 1: Fresh install (cleanest)
   - Option 2: Manual rename (preserves history)

3. **Common Migration Blockers**:
   - **Conflict with another integration** - If another integration already uses the target entity ID, migration will skip that entity
   - **Platform mismatch** - If entity is from a different platform (not `cable_modem_monitor`), it won't migrate
   - **Missing entity registry** - Rare, but entity registry corruption can prevent migration

**Check for Conflicts:**
```yaml
# Look for log messages like:
"Cannot migrate sensor.downstream_ch_1_power: Target entity ID already exists (platform: other_integration)"
```

**Solution for Conflicts:**
1. Delete or rename the conflicting entity from the other integration
2. Reload Cable Modem Monitor integration
3. Migration will retry automatically

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
3. **Download Diagnostics**:
   - Settings → Devices & Services → Cable Modem Monitor
   - Click ⋮ → Download diagnostics
4. **Open an Issue**: [GitHub Issues](https://github.com/kwschulz/cable_modem_monitor/issues)
   - Include your modem model
   - Include relevant logs
   - Attach diagnostics file

---

## Quick Reference

### Correct Entity ID Format (v2.0+)

| Sensor Type | Entity ID | Display Name |
|------------|-----------|--------------|
| Downstream Power | `sensor.cable_modem_downstream_ch_1_power` | DS Ch 1 Power |
| Downstream SNR | `sensor.cable_modem_downstream_ch_1_snr` | DS Ch 1 SNR |
| Upstream Power | `sensor.cable_modem_upstream_ch_1_power` | US Ch 1 Power |
| Upstream Frequency | `sensor.cable_modem_upstream_ch_1_frequency` | US Ch 1 Frequency |
| Channel Count | `sensor.cable_modem_downstream_channel_count` | Downstream Channel Count |

**Note:**
- Entity IDs always include `cable_modem_` prefix
- Display names use DS/US abbreviations (industry standard)
- DS = Downstream, US = Upstream
