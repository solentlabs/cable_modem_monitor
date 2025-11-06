# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.6.0] - 2025-11-06

### Added
- **GitHub Best Practices Implementation** - Comprehensive repository governance and security
  - `SECURITY.md` - Vulnerability reporting policy and security guidelines
  - `CODE_OF_CONDUCT.md` - Contributor Covenant v2.1 for community standards
  - `GOVERNANCE.md` - Project governance, release process, and decision-making policies
  - `.github/CODEOWNERS` - Code ownership and automatic review assignments
  - `.github/dependabot.yml` - Automated dependency vulnerability scanning
  - `.github/workflows/codeql.yml` - GitHub Advanced Security code scanning
  - `.github/workflows/release.yml` - Automated release creation on version tags
  - `.github/workflows/commit-lint.yml` - Conventional commits validation
  - `.github/workflows/changelog-check.yml` - CHANGELOG.md update verification
  - `.github/ISSUE_TEMPLATE/bug_report.yml` - Structured bug report template
  - `.github/ISSUE_TEMPLATE/feature_request.yml` - Structured feature request template
  - `.github/ISSUE_TEMPLATE/config.yml` - Issue template configuration
  - `.github/pull_request_template.md` - Comprehensive PR template with checklist
  - `docs/BRANCH_PROTECTION.md` - Step-by-step guide for configuring branch protection
  - `mypy.ini` - Type checking configuration with mypy
  - Coverage enforcement: 50% minimum threshold in pytest and CI
  - Type checking with mypy in pre-commit hooks and CI

### Changed
- Enhanced CI/CD workflows with additional quality checks
  - Added mypy type checking to lint job
  - Added coverage enforcement to test job (--cov-fail-under=50)
- Updated test requirements to include mypy and types-requests
- Updated pre-commit hooks to include mypy type checking

### Security
- **Comprehensive Security Remediation** - Resolved all 26 CodeQL security vulnerabilities
  - **SSL/TLS Security (Critical/High - 4 issues)**
    - Made SSL certificate verification configurable via integration settings
    - Removed global `urllib3.disable_warnings()` call that suppressed all SSL warnings
    - Fixed hardcoded `ssl=False` in health monitor with proper SSL context
    - Added conditional SSL warning suppression only when verification is explicitly disabled
    - Added enhanced user-facing warnings about MITM attack risks
    - Defaults to disabled (verify_ssl=False) for backward compatibility with self-signed certificates
  - **Open Redirect Prevention (Critical/High - 2 issues)**
    - Added redirect URL validation in health monitor HTTP checks
    - Implemented same-host redirect checking in Motorola parser login
    - Added cross-host redirect blocking in Technicolor XB7 parser
    - Validates all redirect targets to prevent phishing attacks
  - **Command Injection Prevention (Medium - 1 issue)**
    - Fixed unsafe subprocess execution in health monitor ping function
    - Added comprehensive host validation with IPv4/IPv6/hostname regex patterns
    - Implemented shell metacharacter blocking and input sanitization
    - Protected ping subprocess from command injection attacks
  - **Input Validation & Sanitization (Medium - 4 issues)**
    - Added strict URL validation in config flow with protocol checking (HTTP/HTTPS only)
    - Implemented hostname/IP format validation using proper patterns
    - Added character whitelist validation blocking dangerous shell metacharacters
    - Replaced regex-based URL extraction with proper `urllib.parse` throughout codebase
    - Added validation helpers: `_is_valid_host()`, `_is_valid_url()`, `_is_safe_redirect()`
  - **Credential Security (Medium - 3 issues)**
    - Removed username logging from Motorola parser to prevent credential leakage
    - Added comprehensive security documentation for Base64 password encoding
    - Documented that Base64 is NOT encryption - it's merely encoding (modem firmware limitation)
    - Sanitized all credential-related log messages
  - **Exception Handling (Low - 4 issues)**
    - Replaced broad `Exception` catches with specific exception types (`ValueError`, `TypeError`)
    - Improved error messages for better debugging while preventing information leakage
    - Maintained proper exception logging with context
  - **Information Disclosure (Low - 4 issues)**
    - Sanitized exception messages in diagnostics to prevent sensitive data exposure
    - Added regex-based redaction of passwords, tokens, keys, and credentials from error messages
    - Masked IP addresses and file paths in exception output
    - Truncated long exception messages to 200 character limit
  - **Files Modified**: `config_flow.py`, `core/health_monitor.py`, `core/modem_scraper.py`, `diagnostics.py`, `parsers/motorola/generic.py`, `parsers/technicolor/xb7.py`
  - **Impact**: Eliminates all critical security vulnerabilities while maintaining backward compatibility
- **Health Monitoring System** - Dual-layer network diagnostics with 3 new sensors
  - `sensor.cable_modem_health_status` - Overall health (healthy/degraded/icmp_blocked/unresponsive)
  - `sensor.cable_modem_ping_latency` - ICMP ping response time in milliseconds
  - `sensor.cable_modem_http_latency` - HTTP web server response time in milliseconds
  - Runs on every coordinator poll (user-configurable 60-1800 seconds)
  - HTTP check supports SSL self-signed certs, redirects, and HEAD→GET fallback
- **XB7 System Information Enhancement** - New sensors for system details
  - `sensor.cable_modem_system_uptime` - Human-readable uptime (e.g., "21 days 15h:20m:33s")
  - `sensor.cable_modem_last_boot_time` - Calculated timestamp of last modem reboot
  - `sensor.cable_modem_software_version` - Firmware/software version from modem
  - Primary downstream channel detection (e.g., "Channel ID 10 is the Primary")
- **Reset Entities Button** - Configuration button to reset all entities
  - `button.cable_modem_reset_entities` - Removes all entities and reloads integration
  - Preserves entity IDs and historical data (linked by entity_id)
  - Useful after modem replacement or to fix entity registry issues
  - Includes comprehensive documentation about HA storage architecture
- **SSL Certificate Support** - Support for HTTPS modems with self-signed certificates
  - Adds `verify=False` to requests in modem_scraper.py
  - Suppresses urllib3 SSL warnings
  - Automatic HTTPS/HTTP protocol detection with fallback
  - Unblocks MB8611 and other HTTPS modems (Issue #6)

### Changed
- Enhanced CI/CD workflows with additional quality checks
  - Added mypy type checking to lint job
  - Added coverage enforcement to test job (--cov-fail-under=50)
- Updated test requirements to include mypy and types-requests
- Updated pre-commit hooks to include mypy type checking
- **Improved Exception Handling** - Better timeout and connection error handling in XB7 parser
  - Timeout errors logged at DEBUG level (reduces log noise during reboots)
  - Connection errors logged at WARNING level
  - Authentication errors logged at ERROR level
  - Helps distinguish between network issues, modem reboots, and authentication problems

### Documentation
- **TROUBLESHOOTING.md** - Comprehensive troubleshooting guide
  - Connection and authentication issues
  - Health monitoring diagnostic matrix
  - Example automations for health alerts
  - Timeout handling during modem reboots
- **ARCHITECTURE_ROADMAP.md** - Updated with Phase 0 completion and v3.0 plans
  - Complete implementation roadmap through v4.0
  - Issue management policy
  - Version targets and strategy

### Security
- **Comprehensive Security Remediation** - Resolved all 26 CodeQL security vulnerabilities
  - **SSL/TLS Security (Critical/High - 4 issues)**
    - Made SSL certificate verification configurable via integration settings
    - Removed global `urllib3.disable_warnings()` call that suppressed all SSL warnings
    - Fixed hardcoded `ssl=False` in health monitor with proper SSL context
    - Added conditional SSL warning suppression only when verification is explicitly disabled
    - Added enhanced user-facing warnings about MITM attack risks
    - Defaults to disabled (verify_ssl=False) for backward compatibility with self-signed certificates
  - **Open Redirect Prevention (Critical/High - 2 issues)**
    - Added redirect URL validation in health monitor HTTP checks
    - Implemented same-host redirect checking in Motorola parser login
    - Added cross-host redirect blocking in Technicolor XB7 parser
    - Validates all redirect targets to prevent phishing attacks
  - **Command Injection Prevention (Medium - 1 issue)**
    - Fixed unsafe subprocess execution in health monitor ping function
    - Added comprehensive host validation with IPv4/IPv6/hostname regex patterns
    - Implemented shell metacharacter blocking and input sanitization
    - Protected ping subprocess from command injection attacks
  - **Input Validation & Sanitization (Medium - 4 issues)**
    - Added strict URL validation in config flow with protocol checking (HTTP/HTTPS only)
    - Implemented hostname/IP format validation using proper patterns
    - Added character whitelist validation blocking dangerous shell metacharacters
    - Replaced regex-based URL extraction with proper `urllib.parse` throughout codebase
    - Added validation helpers: `_is_valid_host()`, `_is_valid_url()`, `_is_safe_redirect()`
  - **Credential Security (Medium - 3 issues)**
    - Removed username logging from Motorola parser to prevent credential leakage
    - Added comprehensive security documentation for Base64 password encoding
    - Documented that Base64 is NOT encryption - it's merely encoding (modem firmware limitation)
    - Sanitized all credential-related log messages
  - **Exception Handling (Low - 4 issues)**
    - Replaced broad `Exception` catches with specific exception types (`ValueError`, `TypeError`)
    - Improved error messages for better debugging while preventing information leakage
    - Maintained proper exception logging with context
  - **Information Disclosure (Low - 4 issues)**
    - Sanitized exception messages in diagnostics to prevent sensitive data exposure
    - Added regex-based redaction of passwords, tokens, keys, and credentials from error messages
    - Masked IP addresses and file paths in exception output
    - Truncated long exception messages to 200 character limit
  - **Files Modified**: `config_flow.py`, `core/health_monitor.py`, `core/modem_scraper.py`, `diagnostics.py`, `parsers/motorola/generic.py`, `parsers/technicolor/xb7.py`
  - **Impact**: Eliminates all critical security vulnerabilities while maintaining backward compatibility

### Test Fixtures
- **MB8611 Test Data** - Complete test fixtures for Motorola MB8611 (Issue #4)
  - HNAP JSON response with 33 downstream + 4 upstream channels
  - HTML pages: Login, Home, Connection, Software, Event Log
  - Ready for Phase 2 MB8611 parser implementation

### Technical Details
- Health monitoring uses ModemHealthMonitor class in `core/health_monitor.py`
- Health checks run async in parallel (ICMP + HTTP) during coordinator updates
- XB7 parser enhancements use regex parsing for uptime and boot time calculation
- Reset Entities button deletes entity registry entries but preserves recorder database
- Integration maintains stable `unique_id` pattern: `{entry.entry_id}_cable_modem_{sensor_name}`

## [2.5.0] - 2025-10-30

### Fixed
- **Critical Bug Fix** - Fixed config flow validation that allowed setup to succeed even when modem was unreachable
  - Changed `config_flow.py` to check correct key: `cable_modem_connection_status` instead of `connection_status`
  - This bug caused sensors to show as "unavailable" with no data despite successful integration setup
  - Resolves [#4](https://github.com/kwschulz/cable_modem_monitor/issues/4)
- **Diagnostics Data Fix** - Updated `diagnostics.py` to use correct data keys with `cable_modem_` prefix
  - Fixed all key names to match actual data structure returned by modem scraper
  - Diagnostics now properly display connection status, channel counts, and system info
- **Test Updates** - Updated all test files to use correct key names
  - `test_config_flow.py`: Fixed connection status key in mock data
  - `test_coordinator.py`: Fixed all data keys to match production code
  - `test_sensor.py`: Updated mock coordinator data keys

### Technical Details
- The root cause was a key name mismatch introduced during v2.0 refactoring
- `modem_scraper.py` returns `cable_modem_connection_status` but `config_flow.py` was checking `connection_status`
- Since `.get()` returns `None` for missing keys, validation incorrectly passed
- Users could "successfully" configure the integration but all entities remained unavailable

## [2.4.1] - 2025-10-29

### Added
- **Parser Priority System** - Model-specific parsers now tried before generic parsers
  - Ensures MB7621 uses its specific parser instead of generic Motorola parser
  - Priority 100 for model-specific parsers, 50 for generic/fallback parsers
  - Improves reliability and performance for supported models

### Fixed
- **MB7621 Auto-Detection Improvements**
  - Parser now checks software info page (`/MotoSwInfo.asp`) first for better detection
  - Prevents duplicate parser registration
  - Improved detection reliability

### Changed
- **Code Organization** - Refactored codebase for better maintainability
  - Organized parsers by manufacturer directories (motorola/, arris/, technicolor/)
  - Created `core/` directory for modem_scraper
  - Created `lib/` directory for shared utilities
  - Cleaner, more scalable architecture

## [2.3.0] - 2025-10-28

### Added
- **Technicolor XB7 Support** - Full parser implementation for XB7 cable modems
  - Supports 34 downstream + 5 upstream channels
  - Handles transposed table layout (similar to ARRIS SB6141)
  - Parses mixed frequency formats (both "609 MHz" text and "350000000" raw Hz)
  - Includes XB7-specific upstream fields: symbol rate and channel type
  - Parses error codewords (correctable/uncorrectable)
  - Detection by URL pattern (`network_setup.jst`) and content
  - Basic HTTP Authentication support
  - Used by Rogers (Canada), Comcast
  - Resolves [#2](https://github.com/kwschulz/cable_modem_monitor/issues/2)

### Test Coverage
- Added 27 comprehensive tests for XB7 parser:
  - 3 detection tests
  - 2 authentication tests
  - 9 downstream parsing tests
  - 9 upstream parsing tests
  - 2 system info tests
  - 2 integration tests
- **Total test suite: 108 tests passing** (was 81, added 27 new tests)

### Technical
- New file: `custom_components/cable_modem_monitor/parsers/technicolor_xb7.py`
- New test file: `tests/test_parser_technicolor_xb7.py`
- HTML fixture: `tests/fixtures/technicolor_xb7_network_setup.html`
- XB7-specific upstream channel fields:
  - `symbol_rate`: Integer (2560, 5120, 0)
  - `channel_type`: String (TDMA, ATDMA, TDMA_AND_ATDMA, OFDMA)

### Community Updates
- **ARRIS SB6141** confirmed working by @captain-coredump on [Community Forum](https://community.home-assistant.io/t/cable-modem-monitor-track-your-internet-signal-quality-in-home-assistant)
  - All 57 entities displaying correctly
  - Parser fully functional with v2.0.0+

### Thanks
- Special thanks to @esand for providing detailed HTML samples and modem information for XB7 support!
- Thanks to @captain-coredump for confirming ARRIS SB6141 compatibility and providing valuable testing feedback

## [2.2.1] - 2025-10-28

### Changed
- Updated manifest version and documentation images

## [2.2.0] - 2025-10-28

### Fixed
- **TC-4400 Authentication** - Corrected login method signature for TC4400 parser

## [2.1.0] - 2025-10-28

### Added
- **Cleanup Entities Button** - One-click cleanup of orphaned entities from entity registry
  - Useful after upgrades or entity ID changes
  - Displays notification showing how many entities were removed
  - Available in device controls alongside Restart Modem button

### Changed
- **Standardized Entity Naming** - All entities now use `cable_modem_` prefix
  - Provides consistent naming across all sensors
  - Makes entities easier to find and identify
  - Previous entity prefix configuration options removed (simpler UX)

## [2.0.0] - 2025-10-24

### Breaking Changes
- **Entity Naming Standardization** - All sensor entity IDs now use the hard-coded `cable_modem_` prefix
  - **Before (v1.x)**: Entity IDs could vary (no prefix or domain prefix)
  - **After (v2.0)**: All entity IDs consistently use `sensor.cable_modem_*` format
  - Automatic migration included - entity IDs will be renamed on first startup
  - Configuration options for entity prefixes have been removed
  - See UPGRADING.md for detailed migration guide

### Added
- **Automatic Entity ID Migration** - Seamlessly upgrades entity IDs from pre-v2.0 to v2.0 naming
  - Runs automatically on integration startup
  - Includes safety checks to prevent conflicts with other integrations
  - Logs all migrations for debugging
  - Preserves history where possible (some loss may occur due to database conflicts)
- **Enhanced Configuration Descriptions** - Detailed field descriptions in options flow
  - Clear instructions for password handling (leave blank to keep existing)
  - Current host/username displayed for context
  - Helpful descriptions for scan interval and history retention settings

### Changed
- **Simplified Configuration Flow** - Reduced from two steps to single-step options flow
  - Entity naming configuration removed (now hard-coded)
  - Cleaner, more intuitive configuration experience
- **Industry-Standard Sensor Names** - Channel sensors use DS/US abbreviations following industry standards
  - Downstream: "Downstream Ch 1 Power" → "DS Ch 1 Power"
  - Upstream: "Upstream Ch 1 Power" → "US Ch 1 Power"
  - Shorter names reduce redundancy in dashboard cards
  - Follows cable industry standard abbreviations (DS = Downstream, US = Upstream)
  - Entity IDs remain unchanged (still include downstream/upstream in the ID)
- **Improved Code Quality** - Code review and cleanup
  - Removed unused imports
  - Fixed SQL injection potential with parameterized queries
  - Added clarity comments explaining v2.0+ parser architecture
  - Better documentation throughout codebase

### Fixed
- **Upstream Channel Sensors** - Fixed upstream sensors not being created
  - Relaxed validation to allow upstream channels without frequency data
  - Fixed Motorola parser reading frequency from wrong column (was column 2, now column 5)
  - Fixed power reading from wrong column (was column 3, now column 6)
  - Upstream frequencies now display correctly in Hz
  - Only active "Locked" channels are shown (inactive "Not Locked" channels are filtered out)
  - Resolves issue where no upstream sensors appeared despite modem reporting 5 active channels

### Technical
- Added `async_migrate_entity_ids()` function in __init__.py for automatic migration
- Simplified config_flow.py to single-step options flow
- Removed deprecated CONF_ENTITY_PREFIX and related constants
- Updated sensor display names to use DS/US prefixes
- Updated clear_history service to use parameterized SQL queries
- All parser comments now reference v2.0+ (v1.8 was never released)
- Modified `base_parser.validate_upstream()` to make frequency optional
- Fixed Motorola MB parser upstream channel column indices
- Added filtering for "Not Locked" upstream channels in Motorola parser

### Migration Notes
- **Recommended**: Fresh install (cleanest approach)
- **Alternative**: Automatic migration will rename entities on first startup
- **History**: Some history loss may occur during migration due to database conflicts
- **Orphaned Data**: Old records from renamed entities persist - use clear_history service to clean up
- **Documentation**: See UPGRADING.md for complete migration guide

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
