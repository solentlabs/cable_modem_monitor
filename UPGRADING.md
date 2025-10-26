***REMOVED*** Upgrading Cable Modem Monitor

***REMOVED******REMOVED*** Upgrading from v1.x to v2.0

Version 2.0 introduces **breaking changes** to entity naming for improved consistency and predictability.

***REMOVED******REMOVED******REMOVED*** What Changed

**Entity ID Prefix**: All sensor entity IDs now use the hard-coded `cable_modem_` prefix.

**Before (v1.x)**: Entity IDs could vary based on configuration:
- `sensor.downstream_ch_1_power` (no prefix)
- `sensor.cable_modem_downstream_ch_1_power` (domain prefix)

**After (v2.0)**: All entity IDs consistently use:
- `sensor.cable_modem_downstream_ch_1_power`
- `sensor.cable_modem_upstream_ch_1_power`

**Display Names**: Changed to use industry-standard DS/US abbreviations:
- "Downstream Ch 1 Power" → "DS Ch 1 Power"
- "Upstream Ch 1 Power" → "US Ch 1 Power"
- "Total Corrected Errors" (unchanged)
- "Modem Connection Status" (unchanged)

This follows cable industry standards (DS = Downstream, US = Upstream) and prevents confusion between upstream and downstream channels.

***REMOVED******REMOVED******REMOVED*** Why This Change?

1. **Predictability**: Entity IDs are now consistent across all installations
2. **Simplicity**: No configuration choices that could cause confusion
3. **Best Practice**: Follows Home Assistant naming conventions (domain as prefix)
4. **Maintainability**: Reduces code complexity and potential bugs

***REMOVED******REMOVED******REMOVED*** Migration Steps

***REMOVED******REMOVED******REMOVED******REMOVED*** Option 1: Fresh Install (Recommended for Simple Setups)

This is the cleanest approach if you don't have extensive automations or history:

1. **Backup your configuration** (optional but recommended)
2. **Remove the integration** from Home Assistant:
   - Go to Settings → Devices & Services
   - Find Cable Modem Monitor
   - Click the three dots → Delete
3. **Upgrade to v2.0** (install via HACS or manual install)
4. **Restart Home Assistant**
5. **Re-add the integration**:
   - Go to Settings → Devices & Services
   - Click Add Integration
   - Search for "Cable Modem Monitor"
   - Configure with your modem's IP and credentials

**Result**: All entities will have the correct `cable_modem_` prefix.

***REMOVED******REMOVED******REMOVED******REMOVED*** Option 2: Update Entity IDs (Preserves History)

Use this approach if you want to keep historical data:

1. **Upgrade to v2.0** (install via HACS or manual install)
2. **Restart Home Assistant**
3. **Go to Settings → Devices & Services → Cable Modem Monitor**
4. **For each entity**:
   - Click the entity
   - Click the gear icon (settings)
   - Update the Entity ID to include `cable_modem_` prefix
   - Example: Change `sensor.downstream_ch_1_power` to `sensor.cable_modem_downstream_ch_1_power`
5. **Update your automations, scripts, and dashboards** to use the new entity IDs

**Note**: This approach preserves history but is manual and time-consuming for many channels.

***REMOVED******REMOVED******REMOVED******REMOVED*** Option 3: Entity ID Aliases (Temporary Compatibility)

If you have many automations referencing the old entity IDs:

1. **Upgrade to v2.0** and restart Home Assistant
2. **Remove and re-add the integration** (Option 1 above)
3. **For each old entity reference in automations/scripts**:
   - Update to use the new `cable_modem_` prefixed entity IDs
4. **Test all automations** to ensure they work with new entity IDs

***REMOVED******REMOVED******REMOVED*** What to Update

After upgrading, search your configuration for old entity references:

**Configuration YAML**:
```yaml
***REMOVED*** OLD (v1.x)
sensor.downstream_ch_1_power
sensor.total_corrected_errors

***REMOVED*** NEW (v2.0)
sensor.cable_modem_downstream_ch_1_power
sensor.cable_modem_total_corrected_errors
```

**Dashboard Cards**:
```yaml
***REMOVED*** Update entity references in your dashboard YAML
- entity: sensor.cable_modem_downstream_ch_1_power  ***REMOVED*** was sensor.downstream_ch_1_power
- entity: sensor.cable_modem_total_corrected_errors  ***REMOVED*** was sensor.total_corrected_errors
```

**Automations and Scripts**:
- Review all automations that reference Cable Modem Monitor sensors
- Update entity IDs to include `cable_modem_` prefix

**Templates**:
```jinja2
{***REMOVED*** OLD ***REMOVED***}
{{ states('sensor.downstream_ch_1_power') }}

{***REMOVED*** NEW ***REMOVED***}
{{ states('sensor.cable_modem_downstream_ch_1_power') }}
```

***REMOVED******REMOVED******REMOVED*** Finding Old Entity References

Use Home Assistant's search features:

1. **Developer Tools → States**: Search for your old entity IDs to confirm they're gone
2. **Configuration → Automations**: Review each automation
3. **Configuration → Scripts**: Review each script
4. **Dashboard**: Edit dashboards and check entity references

Or use command-line tools to search your configuration:
```bash
cd /config
grep -r "sensor\.downstream_ch" .
grep -r "sensor\.upstream_ch" .
grep -r "sensor\.total_" .
```

***REMOVED******REMOVED******REMOVED*** Data and History

**Important: History May Be Lost During Automatic Migration**

The v2.0 upgrade includes automatic entity ID migration that attempts to preserve your history. However, due to the way Home Assistant's recorder works, **some historical data may be lost or orphaned** during the migration process.

**What Happens:**
- The integration automatically migrates entity IDs on startup (e.g., `sensor.downstream_ch_1_power` → `sensor.cable_modem_downstream_ch_1_power`)
- Home Assistant's recorder attempts to migrate the history to the new entity IDs
- If conflicts occur (from previous delete/re-add cycles), some history may become orphaned
- Error sensor history is most commonly affected due to the complexity of migrations

**Why This Happens:**
- Multiple delete/re-add cycles during testing create duplicate entity registrations
- Database conflicts between old and new entity IDs
- Recorder migration limitations with renamed entities

**Recommendation:**
1. **Accept the history loss** - v2.0 is a major version upgrade with breaking changes
2. **Clean up orphaned data** using the clear_history service:
   ```yaml
   service: cable_modem_monitor.clear_history
   data:
     days_to_keep: 30  ***REMOVED*** Removes data older than 30 days
   ```
3. **Move forward** - New entities will build fresh, accurate history going forward

**Will Orphaned Records Be Deleted Automatically?**

No, orphaned records will NOT be deleted automatically. Home Assistant's retention policy only applies to active entities. Orphaned records (from deleted/renamed entities) remain in the database indefinitely unless you:
- Use the `clear_history` service (recommended)
- Manually purge old data using Developer Tools → Services → Recorder: Purge
- Use a database cleanup tool

**Statistics:**
- Long-term statistics for old entity IDs will remain separate from new entities
- New entities will start fresh statistics
- Old statistics are not automatically merged

***REMOVED******REMOVED******REMOVED*** Troubleshooting

**"Entity not available"**:
- Old entity IDs no longer exist after upgrade
- Update references to new `cable_modem_` prefixed entity IDs

**Dashboard broken**:
- Edit dashboard YAML to update entity IDs
- Or recreate dashboard cards pointing to new entities

**Automations not triggering**:
- Check automation entity IDs match new format
- Test automations manually after updating

**Old entities still showing**:
- Go to Configuration → Entities
- Search for old entity IDs
- Delete orphaned entities manually

**Entities Missing `cable_modem_` Prefix After Reinstall**

If you have performed a fresh install (removed and re-added the integration) and your entities are still missing the `cable_modem_` prefix (e.g., you see `sensor.ds_ch_1_power` instead of `sensor.cable_modem_ds_ch_1_power`), it's likely that old entity references are still present in your Home Assistant configuration.

This can happen even after a reinstall if Home Assistant has cached the old entity structure. Here is a more thorough procedure to ensure a completely clean reinstallation:

**1. Remove the Integration**

- Go to **Settings → Devices & Services**.
- Find **Cable Modem Monitor** and click the three dots (⋮) → **Delete**.

**2. Check for Orphaned Entities**

- Go to **Settings → Devices & Services → Entities**.
- Search for any entities that still have the old naming scheme (e.g., `sensor.ds_ch_1_power`, `sensor.us_ch_1_power`).
- If you find any, select them and click **"Remove Entity"**.
- **Note:** If you are unable to delete the entity directly, you may need to re-associate it with the correct sensor first. Click on the entity, then click the gear icon (settings), and in the "Entity ID" field, type in the correct, new entity ID (e.g., `sensor.cable_modem_ds_ch_1_power`). After re-associating, you should be able to remove the old, orphaned entity.

**3. Restart Home Assistant**

- This is a crucial step to ensure the entity registry is updated.
- Go to **Developer Tools → YAML** and click **"Restart"**.

**4. Verify Removal**

- After restarting, go back to **Settings → Devices & Services → Entities**.
- Search again for the old entity names to ensure they are completely gone.

**5. Reinstall the Integration**

- Now, reinstall the integration via HACS or manually.
- Go to **Settings → Devices & Services → Add Integration**.
- Search for "Cable Modem Monitor" and complete the setup.

**6. Verify the New Entities**

- After the integration is re-added, go to **Settings → Devices & Services → Entities**.
- All your cable modem entities should now have the correct `cable_modem_` prefix.

This more forceful cleanup process should resolve the issue of the missing prefix.

***REMOVED******REMOVED******REMOVED*** Getting Help

If you encounter issues:

1. Check the [GitHub Issues](https://github.com/kwschulz/cable_modem_monitor/issues)
2. Search for existing issues about entity naming
3. Create a new issue with:
   - Your upgrade path (Option 1, 2, or 3)
   - Version you upgraded from
   - Error messages or unexpected behavior
   - Relevant configuration snippets

***REMOVED******REMOVED*** Version History

***REMOVED******REMOVED******REMOVED*** v2.0.0 (Breaking Changes)
- **BREAKING**: All entity IDs now use `cable_modem_` prefix
- **REMOVED**: Entity naming configuration options
- **REMOVED**: Custom prefix, IP prefix, and no-prefix modes
- **FIXED**: Clear history service now uses entity registry
- Simplified configuration flow (single-step options)

***REMOVED******REMOVED******REMOVED*** v1.x
- Configurable entity prefixes (no prefix, domain, IP, custom)
- Multi-step configuration flow
- Various parser improvements
