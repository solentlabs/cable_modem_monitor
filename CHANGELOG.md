# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.7.1] - 2025-10-23

### Fixed
- **Nested Table Parsing** - Fixed HTML parsing for modems with nested table structures
  - Some Motorola modems were showing "0 tables found" despite successful connection
  - Updated `_parse_downstream_channels()` and `_parse_upstream_channels()` to use `recursive=False` when searching for table rows
  - Prevents duplicate channel data from being parsed
  - All 67 tests pass
- **Deprecated config_entry Warning** - Removed explicit `self.config_entry` assignment in OptionsFlowHandler
  - Fixes Home Assistant 2025.12 deprecation warning
  - `config_entry` is now provided automatically by the base class

### Changed
- **Default Polling Interval** - Increased from 5 minutes (300s) to 10 minutes (600s)
  - Reduces load on modem and Home Assistant
  - Still within industry best practices (5-10 minute range)
  - Users can adjust via configuration options if needed
- **Attribution** - Updated credit to @captain-coredump in v1.7.0 release notes

## [1.7.0] - 2025-10-22

### Added
- **ARRIS SB6141 Support (Testing)** - Added parser for ARRIS SB6141 modem (awaiting user confirmation)
  - Handles unique HTML structure where columns represent channels instead of rows
  - Parses downstream channels with power, SNR, frequency, and error statistics
  - Parses upstream channels with power and frequency
  - Added comprehensive test coverage with 3 new tests
  - Based on HTML sample contributed by @captain-coredump from community forum
  - **Status**: Parser implemented and tested, awaiting real-world confirmation from user

### Technical
- Added `_parse_arris_sb6141()` method for ARRIS-specific parsing
- Added `_parse_arris_transposed_table()` for column-based channel data
- Added `_merge_arris_error_stats()` to combine error data from separate table
- Handles nested tables in Power Level row
- Created test fixture: `tests/fixtures/arris_sb6141_signal.html`

## [1.6.1] - 2025-10-22

### Changed
- **Improved Authentication UX** - Changed username default from "admin" to empty string for modems without authentication
  - Makes it clearer that credentials are optional
  - Reduces confusion for users with modems like ARRIS SB6141 that don't require login
- **Enhanced Error Messages** - Better diagnostics to distinguish connection failures from parsing failures
  - Error messages now clarify when auth is optional
  - Guides users to enable debug logging for unsupported modems
  - Provides clear instructions for requesting modem support

### Fixed
- **Better Debug Logging** - Improved logging for unsupported modem HTML formats
  - Logs successful connection URL and HTML structure details
  - Reduced log verbosity for connection attempts (moved to debug level)
  - Helps diagnose when modem connects but HTML format isn't recognized

### Technical
- Updated config_flow.py: Changed CONF_USERNAME default from "admin" to ""
- Updated modem_scraper.py: Added HTML structure logging and better error messages
- Updated strings.json and translations/en.json: Enhanced error messages and field descriptions

## [1.6.0] - 2025-10-22

### Added
- **Technicolor TC4400 Support** - Added support for TC4400 cable modems
  - Added `/cmconnectionstatus.html` URL endpoint
  - Based on research from philfry's check_tc4400 project (see ATTRIBUTION.md)
- **Comprehensive Sensor Tests** - Added tests/test_sensor.py with 17 test functions
  - Tests all sensor types: connection status, error counters, channel counts, system info
  - Tests edge cases: missing data, None values, invalid data
  - All 64 tests passing (47 existing + 17 new)
- **Ruff Configuration** - Added .ruff.toml for project-wide code quality standards
  - 120-character line limit for better readability
  - McCabe complexity limit of 12 for parsing functions

### Changed
- **Code Quality Improvements** - Fixed line length violations across codebase
  - Improved SQL query formatting in __init__.py
  - Better readability in modem_scraper.py parsing logic

## [1.4.0] - 2025-10-21

### Added
- **Clear History Button** - New UI button entity to clean up old historical data
  - Appears alongside Restart Modem button in device page
  - Uses configurable retention period from settings
  - One-click cleanup without using Developer Tools
- **Configurable History Retention** - New configuration option for history management
  - Set retention period: 1-365 days (default: 30 days)
  - Configure via Settings → Devices & Services → Cable Modem Monitor → Configure
  - Button automatically uses configured retention value
- **Example Graphs in Documentation** - Added two new screenshots showing real signal data
  - Downstream Power Levels graph with all channels
  - Signal-to-Noise Ratio graph with all channels

### Changed
- **Enhanced Documentation** - Comprehensive updates to README.md
  - New "Configuration Options" section explaining all settings
  - Expanded "Managing Historical Data" section
  - Updated dashboard YAML examples to include Clear History button
  - Added visual examples of historical graphs

### Technical
- Added `CONF_HISTORY_DAYS` and `DEFAULT_HISTORY_DAYS` constants to const.py
- Extended config_flow.py options flow with history_days field (1-365 validation)
- Added `ClearHistoryButton` class to button.py
- Updated translations/en.json with button and configuration translations
- Button reads retention setting from config entry data

## [1.3.0] - 2025-10-21

### Added
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

### Changed
- **Connection Status Improvements** - Now distinguishes between network issues and modem issues
  - `unreachable`: Cannot connect to modem (network/auth problem - Home Assistant issue)
  - `offline`: Modem responds but no channels detected (modem is actually down)
- **Sensor Availability** - All measurement sensors now become "unavailable" during connection failures
  - Charts no longer show drops to 0 during outages
  - Historical data gaps instead of misleading zero values
  - Connection status sensor remains available to show offline/unreachable state
- **Version Bump** - Updated to v1.3.0

### Fixed
- **Diagnostics Download** - Fixed AttributeError when downloading diagnostics
  - Removed invalid `last_update_success_time` attribute reference
  - Diagnostics now successfully export all modem data

### Technical
- Added `OptionsFlowHandler` class to config_flow.py for reconfiguration support
- Added clear_history service handler in __init__.py with SQLite database operations
- Modified sensor base class to control availability based on connection status
- Updated modem_scraper.py to return "unreachable" instead of "offline" for connection failures
- Added translations/en.json for internationalization support

## [1.2.2] - 2025-10-21

### Fixed
- **Zero values in history** - Integration now properly validates and skips updates when modem returns invalid/empty data
- Prevents recording of 0 values during modem connection issues or reboots
- Improved data extraction methods to return `None` instead of `0` for invalid data
- Added validation to skip channel data when all values are null/invalid

### Added
- **Diagnostics support** - Integration now provides downloadable diagnostics via Home Assistant UI
- Diagnostics include channel data, error counts, connection status, and last error information
- Documentation for cleaning up existing zero values from history (`cleanup_zero_values.md`)

### Technical
- `_extract_number()` and `_extract_float()` now return `None` instead of `0` when parsing fails
- Skip channel parsing when all critical values are `None`
- Skip entire update if no valid downstream or upstream channels are parsed
- Added comprehensive diagnostics platform for troubleshooting
- Improved error calculations to handle `None` values properly

## [1.2.1] - 2025-10-21

### Fixed
- **Error totals double-counting** - Fixed bug where Total row from modem table was being counted as a channel
- Error sensors now show correct values (previously were exactly double the actual errors)

### Technical
- Added check to skip "Total" row in downstream channel table parsing
- Prevents Total row (4489/8821) from being added to per-channel sums

## [1.2.0] - 2025-10-21

### Fixed
- **Software version parsing** - Now correctly uses CSS class selectors to find the value cell
- **System uptime parsing** - Now correctly uses CSS class selectors to find the value cell
- Both parsers now avoid matching header/label text and get actual values

### Technical
- Changed to class-based cell selection (`moto-param-value`, `moto-content-value`)
- More robust parsing that won't match table headers or labels

## [1.1.3] - 2025-10-21

### Fixed
- **System uptime parsing** now correctly extracts uptime from MotoConnection.asp page
- Restored system_uptime sensor (was incorrectly removed - it IS available on Motorola modems)

### Technical
- Fixed _parse_system_uptime() to match actual HTML structure from MotoConnection.asp
- Uptime parsed before fetching MotoHome.asp for efficiency

## [1.1.1] - 2025-10-21

### Fixed
- **Software version** now correctly parsed from MotoHome.asp page
- **Upstream channel count** now accurately reports modem's actual channel count from MotoHome.asp
- Channel counts now use modem-reported values instead of just counting parsed channels

### Removed
- **System uptime sensor** - Not available on Motorola MB series modems

### Technical
- Scraper now fetches additional data from MotoHome.asp for version and channel counts
- Added `_parse_channel_counts()` method for accurate channel counting
- Improved error handling for optional MotoHome.asp data

## [1.1.0] - 2025-10-20

### Added
- **Channel count sensors**: Track number of active upstream and downstream channels
- **Software version sensor**: Monitor modem firmware/software version
- **System uptime sensor**: Track how long the modem has been running
- **Modem restart button**: Remotely restart your cable modem from Home Assistant dashboard
- Enhanced dashboard examples with new sensors
- Automation examples for channel count monitoring and auto-restart

### Enhanced
- Modem scraper now extracts additional system information
- Improved documentation with trend analysis use cases
- Better automation examples for proactive network monitoring

### Technical
- Added button platform support
- Extended modem_scraper.py with version and uptime parsing
- New sensor classes for channel counts, version, and uptime
- Restart functionality with multiple endpoint fallbacks

## [1.0.0] - 2025-10-20

### Added
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

### Security
- Credentials stored securely in Home Assistant's encrypted storage
- Session-based authentication with proper cookie handling
- No cloud services - all data stays local

### Known Issues
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
