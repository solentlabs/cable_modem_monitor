***REMOVED*** Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

***REMOVED******REMOVED*** [1.3.0] - 2025-10-21

***REMOVED******REMOVED******REMOVED*** Added
- **Options Flow** - Users can now reconfigure the integration without reinstalling
  - Update modem IP address through UI
  - Change username/password through UI
  - Leave password blank to keep existing password
- **Clear History Service** - New service to clean up old historical data
  - `cable_modem_monitor.clear_history` service
  - Specify days to keep (deletes older data)
  - Cleans both states and statistics tables
  - Automatically vacuums database to reclaim space
- **Translation Support** - Added English translations for config flow and services
- **Service Definitions** - Added services.yaml for proper service documentation

***REMOVED******REMOVED******REMOVED*** Changed
- **Connection Status Improvements** - Now distinguishes between network issues and modem issues
  - `unreachable`: Cannot connect to modem (network/auth problem - Home Assistant issue)
  - `offline`: Modem responds but no channels detected (modem is actually down)
- **Sensor Availability** - All measurement sensors now become "unavailable" during connection failures
  - Charts no longer show drops to 0 during outages
  - Historical data gaps instead of misleading zero values
  - Connection status sensor remains available to show offline/unreachable state
- **Version Bump** - Updated to v1.3.0

***REMOVED******REMOVED******REMOVED*** Fixed
- **Diagnostics Download** - Fixed AttributeError when downloading diagnostics
  - Removed invalid `last_update_success_time` attribute reference
  - Diagnostics now successfully export all modem data

***REMOVED******REMOVED******REMOVED*** Technical
- Added `OptionsFlowHandler` class to config_flow.py for reconfiguration support
- Added clear_history service handler in __init__.py with SQLite database operations
- Modified sensor base class to control availability based on connection status
- Updated modem_scraper.py to return "unreachable" instead of "offline" for connection failures
- Added translations/en.json for internationalization support

***REMOVED******REMOVED*** [1.2.2] - 2025-10-21

***REMOVED******REMOVED******REMOVED*** Fixed
- **Zero values in history** - Integration now properly validates and skips updates when modem returns invalid/empty data
- Prevents recording of 0 values during modem connection issues or reboots
- Improved data extraction methods to return `None` instead of `0` for invalid data
- Added validation to skip channel data when all values are null/invalid

***REMOVED******REMOVED******REMOVED*** Added
- **Diagnostics support** - Integration now provides downloadable diagnostics via Home Assistant UI
- Diagnostics include channel data, error counts, connection status, and last error information
- Documentation for cleaning up existing zero values from history (`cleanup_zero_values.md`)

***REMOVED******REMOVED******REMOVED*** Technical
- `_extract_number()` and `_extract_float()` now return `None` instead of `0` when parsing fails
- Skip channel parsing when all critical values are `None`
- Skip entire update if no valid downstream or upstream channels are parsed
- Added comprehensive diagnostics platform for troubleshooting
- Improved error calculations to handle `None` values properly

***REMOVED******REMOVED*** [1.2.1] - 2025-10-21

***REMOVED******REMOVED******REMOVED*** Fixed
- **Error totals double-counting** - Fixed bug where Total row from modem table was being counted as a channel
- Error sensors now show correct values (previously were exactly double the actual errors)

***REMOVED******REMOVED******REMOVED*** Technical
- Added check to skip "Total" row in downstream channel table parsing
- Prevents Total row (4489/8821) from being added to per-channel sums

***REMOVED******REMOVED*** [1.2.0] - 2025-10-21

***REMOVED******REMOVED******REMOVED*** Fixed
- **Software version parsing** - Now correctly uses CSS class selectors to find the value cell
- **System uptime parsing** - Now correctly uses CSS class selectors to find the value cell
- Both parsers now avoid matching header/label text and get actual values

***REMOVED******REMOVED******REMOVED*** Technical
- Changed to class-based cell selection (`moto-param-value`, `moto-content-value`)
- More robust parsing that won't match table headers or labels

***REMOVED******REMOVED*** [1.1.3] - 2025-10-21

***REMOVED******REMOVED******REMOVED*** Fixed
- **System uptime parsing** now correctly extracts uptime from MotoConnection.asp page
- Restored system_uptime sensor (was incorrectly removed - it IS available on Motorola modems)

***REMOVED******REMOVED******REMOVED*** Technical
- Fixed _parse_system_uptime() to match actual HTML structure from MotoConnection.asp
- Uptime parsed before fetching MotoHome.asp for efficiency

***REMOVED******REMOVED*** [1.1.1] - 2025-10-21

***REMOVED******REMOVED******REMOVED*** Fixed
- **Software version** now correctly parsed from MotoHome.asp page
- **Upstream channel count** now accurately reports modem's actual channel count from MotoHome.asp
- Channel counts now use modem-reported values instead of just counting parsed channels

***REMOVED******REMOVED******REMOVED*** Removed
- **System uptime sensor** - Not available on Motorola MB series modems

***REMOVED******REMOVED******REMOVED*** Technical
- Scraper now fetches additional data from MotoHome.asp for version and channel counts
- Added `_parse_channel_counts()` method for accurate channel counting
- Improved error handling for optional MotoHome.asp data

***REMOVED******REMOVED*** [1.1.0] - 2025-10-20

***REMOVED******REMOVED******REMOVED*** Added
- **Channel count sensors**: Track number of active upstream and downstream channels
- **Software version sensor**: Monitor modem firmware/software version
- **System uptime sensor**: Track how long the modem has been running
- **Modem restart button**: Remotely restart your cable modem from Home Assistant dashboard
- Enhanced dashboard examples with new sensors
- Automation examples for channel count monitoring and auto-restart

***REMOVED******REMOVED******REMOVED*** Enhanced
- Modem scraper now extracts additional system information
- Improved documentation with trend analysis use cases
- Better automation examples for proactive network monitoring

***REMOVED******REMOVED******REMOVED*** Technical
- Added button platform support
- Extended modem_scraper.py with version and uptime parsing
- New sensor classes for channel counts, version, and uptime
- Restart functionality with multiple endpoint fallbacks

***REMOVED******REMOVED*** [1.0.0] - 2025-10-20

***REMOVED******REMOVED******REMOVED*** Added
- Initial release of Cable Modem Monitor integration
- Config flow for easy UI-based setup
- Support for Motorola MB series modems (DOCSIS 3.0)
- Per-channel sensors for downstream channels:
  - Power levels (dBmV)
  - Signal-to-Noise Ratio (SNR in dB)
  - Frequency (MHz)
  - Corrected errors
  - Uncorrected errors
- Per-channel sensors for upstream channels:
  - Power levels (dBmV)
  - Frequency (MHz)
- Summary sensors for total corrected/uncorrected errors
- Connection status sensor
- Session-based authentication for password-protected modems
- Automatic detection of modem page URLs
- Integration reload support (no restart required for updates)
- Custom integration icons and branding
- Comprehensive documentation and examples
- HACS compatibility

***REMOVED******REMOVED******REMOVED*** Security
- Credentials stored securely in Home Assistant's encrypted storage
- Session-based authentication with proper cookie handling
- No cloud services - all data stays local

***REMOVED******REMOVED******REMOVED*** Known Issues
- Modem-specific HTML parsing may need adjustment for some models
- Limited to HTTP (no HTTPS support for modem connections)

[1.3.0]: https://github.com/kwschulz/cable_modem_monitor/releases/tag/v1.3.0
[1.2.2]: https://github.com/kwschulz/cable_modem_monitor/releases/tag/v1.2.2
[1.2.1]: https://github.com/kwschulz/cable_modem_monitor/releases/tag/v1.2.1
[1.2.0]: https://github.com/kwschulz/cable_modem_monitor/releases/tag/v1.2.0
[1.1.3]: https://github.com/kwschulz/cable_modem_monitor/releases/tag/v1.1.3
[1.1.1]: https://github.com/kwschulz/cable_modem_monitor/releases/tag/v1.1.1
[1.1.0]: https://github.com/kwschulz/cable_modem_monitor/releases/tag/v1.1.0
[1.0.0]: https://github.com/kwschulz/cable_modem_monitor/releases/tag/v1.0.0
