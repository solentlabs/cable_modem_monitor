# Cleaning Up Zero Values from Home Assistant History

If you experienced an issue where the cable modem integration recorded 0 values in your history (typically during a modem connection issue), you can clean them up using one of the methods below.

## Method 1: Using Home Assistant Developer Tools (Recommended)

1. Navigate to **Developer Tools** → **Services** in Home Assistant
2. Select service: `recorder.purge_entities`
3. Use the following YAML:

```yaml
service: recorder.purge_entities
data:
  entity_id:
    - sensor.downstream_ch_1_power
    - sensor.downstream_ch_1_snr
    # Add all your cable modem sensor entities here
  keep_days: 0  # Will purge all history
```

**Note**: This will delete ALL history for the specified entities. If you want to keep good data, use Method 2 instead.

## Method 2: Direct Database Cleanup (SQLite)

If you're using the default SQLite database and want to remove only the bad zero readings, you can use SQL to delete specific records.

**⚠️ WARNING**: Always backup your Home Assistant database before running SQL commands!

### Backup your database first:

```bash
# SSH into your Home Assistant
# Find your database location (usually /config/home-assistant_v2.db)
cp /config/home-assistant_v2.db /config/home-assistant_v2.db.backup
```

### Connect to the database:

```bash
sqlite3 /config/home-assistant_v2.db
```

### Example SQL to find zero values around midnight:

```sql
-- First, let's see what we're dealing with
SELECT
    s.entity_id,
    st.state,
    datetime(st.last_updated, 'localtime') as timestamp
FROM states st
JOIN states_meta s ON st.metadata_id = s.metadata_id
WHERE s.entity_id LIKE 'sensor.downstream_ch_%'
  AND st.state = '0'
  AND datetime(st.last_updated, 'localtime') LIKE '%-%-% 00:%'
ORDER BY st.last_updated DESC
LIMIT 100;
```

### Delete the zero values (be careful!):

```sql
-- Delete zero values from a specific time range (e.g., around 12:03 AM on a specific date)
DELETE FROM states
WHERE metadata_id IN (
    SELECT metadata_id FROM states_meta
    WHERE entity_id LIKE 'sensor.downstream_ch_%'
    OR entity_id LIKE 'sensor.upstream_ch_%'
    OR entity_id = 'sensor.total_corrected_errors'
    OR entity_id = 'sensor.total_uncorrected_errors'
)
AND state = '0'
AND datetime(last_updated, 'localtime') BETWEEN '2025-10-21 00:00:00' AND '2025-10-21 00:10:00';
```

Replace the date/time range with when your zero values were recorded.

### Exit SQLite:

```sql
.quit
```

### Restart Home Assistant:

After making database changes, restart Home Assistant for the changes to take effect.

## Method 3: Use the Recorder Integration Settings

1. Go to **Settings** → **System** → **Repairs**
2. Look for any issues with the recorder integration
3. You can also adjust the recorder purge settings to automatically remove old data

## Verifying the Fix

After cleanup and installing the updated integration:

1. The integration will now skip updates with invalid/zero data
2. Check the Home Assistant logs for warnings like "Skipping downstream channel with all null values"
3. Your history graphs should no longer show sudden drops to zero
4. The integration diagnostics tab will show any errors encountered during updates

## Prevention

The updated integration (v1.0.1+) now includes:

- ✅ Validation to skip channel data with all null/zero values
- ✅ Proper error handling when modem returns invalid data
- ✅ Diagnostic logging to track when bad data is encountered
- ✅ Integration will skip the entire update if no valid channels are found

This prevents zero values from being recorded in the future during transient modem issues.
