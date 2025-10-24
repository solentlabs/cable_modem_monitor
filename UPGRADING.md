***REMOVED*** Upgrading Cable Modem Monitor

***REMOVED******REMOVED*** Upgrading from v1.x to v2.0

Version 2.0 introduces **breaking changes** to entity naming for improved consistency and predictability.

***REMOVED******REMOVED******REMOVED*** What Changed

**Entity ID Prefix**: All sensor entity IDs now use the hard-coded `cable_modem_` prefix.

**Before (v1.x)**: Entity IDs could vary based on configuration:
- `sensor.downstream_ch_1_power` (no prefix)
- `sensor.cable_modem_downstream_ch_1_power` (domain prefix)
- `sensor.192_168_100_1_downstream_ch_1_power` (IP prefix)
- `sensor.living_room_downstream_ch_1_power` (custom prefix)

**After (v2.0)**: All entity IDs consistently use:
- `sensor.cable_modem_downstream_ch_1_power`

**Display Names**: No change - display names remain simple without prefix:
- "Downstream Ch 1 Power"
- "Total Corrected Errors"
- "Modem Connection Status"

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

**Historical Data**:
- If using Option 1 (fresh install), old history remains in the database but won't be associated with new entities
- If using Option 2 (rename entities), history is preserved
- Consider using the `clear_history` service to remove old data:
  ```yaml
  service: cable_modem_monitor.clear_history
  data:
    days_to_keep: 30
  ```

**Statistics**:
- Long-term statistics for old entity IDs will remain separate
- New entities will start fresh statistics

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
