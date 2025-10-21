# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[1.2.2]: https://github.com/kwschulz/cable_modem_monitor/releases/tag/v1.2.2
[1.2.1]: https://github.com/kwschulz/cable_modem_monitor/releases/tag/v1.2.1
[1.2.0]: https://github.com/kwschulz/cable_modem_monitor/releases/tag/v1.2.0
[1.1.3]: https://github.com/kwschulz/cable_modem_monitor/releases/tag/v1.1.3
[1.1.1]: https://github.com/kwschulz/cable_modem_monitor/releases/tag/v1.1.1
[1.1.0]: https://github.com/kwschulz/cable_modem_monitor/releases/tag/v1.1.0
[1.0.0]: https://github.com/kwschulz/cable_modem_monitor/releases/tag/v1.0.0
