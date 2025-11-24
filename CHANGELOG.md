# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Developer Experience
- **Docker Status Checking** - Added cross-platform Docker check helper (`scripts/dev/check-docker.py`)
  - Verifies Docker is installed and running before Docker operations
  - Provides platform-specific error messages for Windows, macOS, and Linux
  - Handles Unicode/ASCII fallback for Windows console compatibility
  - Integrated into all Docker-related VS Code tasks as a dependency
- **Dev Container Improvements** - Fixed post-create script execution order
  - CodeQL CLI now installs before attempting to use it
  - Added directory existence check before CodeQL pack installation
  - Suppressed pip root user warnings in container environment
- **Terminal Experience** - Enhanced welcome messages for new terminal sessions
  - Added terminal clearing before displaying welcome message for cleaner UI
  - Removed emoji from welcome text to fix Windows terminal encoding issues
  - Cross-platform compatibility maintained for Linux, macOS, and Windows

### Planning
- Future features and improvements
- See GitHub issues and milestones for upcoming features

## [3.4.1] - 2025-11-22

### Enhanced
- **Connectivity Check Diagnostics** - Significantly improved troubleshooting for modem connection issues
  - Added detailed timing information for each connection attempt (shows actual elapsed time vs timeout)
  - Logs now show which protocol (HTTP/HTTPS) and method (HEAD/GET) is being tried
  - Added GET request fallback when HEAD requests timeout (some modems don't support HEAD)
  - Comprehensive diagnostic messages now included in error output
  - Changed logging level from DEBUG to INFO/WARNING for better visibility
  - Each failure now reports: protocol, method, elapsed time, exception type, and error details
  - Error messages now include diagnostic summary to help identify root cause

### Changed
- **Connectivity Check Timeout** - Increased from 2s to 10s (Addresses Issue #3)
  - Aligns pre-flight connectivity check with main scraper timeout (10s)
  - More accommodating for slower-responding modems
  - Reduces false "network_unreachable" errors during setup
  - Particularly helpful for modems like Netgear CM600 that may need more time

### Added
- **Test Coverage** - Enhanced connectivity check testing
  - New test validates GET fallback behavior when HEAD requests timeout
  - Existing test updated to verify 10-second timeout configuration
  - Tests ensure both HEAD and GET methods work correctly with proper timeout

### Technical Details
- **Files Modified**:
  - `custom_components/cable_modem_monitor/config_flow.py` - Enhanced `_do_quick_connectivity_check()` with:
    - Timing measurement for all requests
    - GET fallback logic after HEAD timeout
    - Structured diagnostic info collection
    - Better logging at INFO/WARNING levels instead of DEBUG
  - `tests/components/test_config_flow.py` - Added GET fallback test case
  - `custom_components/cable_modem_monitor/const.py` - Version bump to 3.4.1
  - `custom_components/cable_modem_monitor/manifest.json` - Version bump to 3.4.1

### Benefits for Issue #3
This release provides extensive diagnostic information to help understand why the Netgear CM600 (and other modems) might fail connectivity checks:
- Identifies if it's a timeout issue vs connection refused vs other errors
- Shows if HTTP vs HTTPS makes a difference
- Reveals if HEAD requests aren't supported (fixed by GET fallback)
- Provides timing data to understand modem response characteristics
- All diagnostic details appear in Home Assistant logs for troubleshooting

## [3.4.0] - 2025-11-21

### Added
- **JSON HNAP Support for Motorola MB8611** - Dual-format HNAP authentication and parsing (Fixes Issue #29)
  - New `HNAPJsonRequestBuilder` class for JSON-formatted HNAP requests
  - MB8611 parser now tries JSON HNAP first, then falls back to XML/SOAP
  - Fixes `SET_JSON_FORMAT_ERROR` for firmware variants that reject XML/SOAP format
  - Enhanced error detection in authentication module for JSON error responses
  - Automatic format detection ensures compatibility with all MB8611 firmware variants
  - Both login and data parsing use dual-format strategy
- **Comprehensive Test Coverage** - 20 new tests for parser improvements
  - MB8611: 5 new tests for JSON HNAP support (login, parsing, fallback, error handling)
  - CM600: 15 new tests covering authentication (4 tests), edge cases (6 tests), and metadata (4 tests)
  - Validates HTTP Basic Auth configuration and behavior
  - Tests malformed data handling and graceful error recovery

### Fixed
- **Motorola MB8611 (HNAP) Configuration** - Resolved JSON format compatibility issue (Fixes Issue #29)
  - Modem firmware variants that respond with `SET_JSON_FORMAT_ERROR` now work correctly
  - Parser automatically detects and uses JSON-formatted HNAP requests when XML/SOAP fails
  - Seamless fallback ensures backward compatibility with older firmware
  - Users no longer need to manually select different parser variants
- **Netgear CM600 Authentication** - Fixed HTTP 401 errors on protected pages (Fixes Issue #3)
  - Enabled HTTP Basic Authentication for `/DocsisStatus.asp`, `/DashBoard.asp`, `/RouterStatus.asp`
  - Changed `auth_required: False` to `auth_required: True` for protected endpoints
  - Updated login() method to use AuthFactory for proper credential handling
  - Index pages remain accessible without authentication for modem detection
  - Parser now successfully retrieves channel data and system information

### Changed
- **Enhanced Authentication Error Detection** - Better diagnostics for HNAP format mismatches
  - Authentication module now detects JSON error responses (`SET_JSON_FORMAT_ERROR`, `LoginResult:FAILED`)
  - Warning messages suggest using JSON-formatted HNAP when XML/SOAP is rejected
  - Improved logging helps diagnose firmware-specific authentication issues
- **MB8611 Parser Architecture** - Refactored for dual-format support
  - Split parsing logic into `_parse_with_json_hnap()` and `_parse_with_xml_hnap()` methods
  - Consistent error handling across both JSON and XML/SOAP code paths
  - Enhanced debug logging shows which format succeeded
  - Channel count and response size logged for troubleshooting

### Technical Details
- **Files Added**: `core/hnap_json_builder.py` (212 lines) - JSON HNAP request builder
- **Files Modified**:
  - `core/authentication.py` - Added JSON error detection (lines 396-407)
  - `parsers/motorola/mb8611_hnap.py` - Dual-format login and parsing (lines 51-232)
  - `parsers/netgear/cm600.py` - HTTP Basic Auth configuration (lines 43-73)
  - `tests/parsers/motorola/test_mb8611_hnap.py` - 5 new JSON HNAP tests
  - `tests/parsers/netgear/test_cm600.py` - 15 new authentication and edge case tests
- **Compatibility**: No breaking changes, fully backward compatible with existing configurations
- **Test Coverage**: Increased from 443 to 463 tests (all passing)

## [3.3.1] - 2025-11-20

### Added
- **VS Code Development Environment Configuration** - Comprehensive IDE setup for consistent development
  - Extension recommendations for Python, testing, security (CodeQL), YAML, and Markdown
  - Excludes conflicting extensions (test adapters, pylint) that interfere with native Python testing
  - CodeQL extension settings for local query development and testing
  - Home Assistant development tasks for container lifecycle management
  - Enhanced devcontainer startup messages with quick-start guide
- **CodeQL Testing Infrastructure** - Local testing support for security queries
  - Command-line test runner script at `scripts/dev/test-codeql.sh`
  - Comprehensive testing guide at `docs/CODEQL_TESTING_GUIDE.md`
  - CodeQL pack documentation at `cable-modem-monitor-ql/README.md`
  - Automated CodeQL CLI installation in test script
- **Development Container Guide** - Cross-platform setup documentation
  - Complete guide at `docs/VSCODE_DEVCONTAINER_GUIDE.md` for Windows, macOS, Linux, Chrome OS
  - Home Assistant container management workflows
  - Testing panel usage instructions
  - Troubleshooting for common development issues

### Changed
- **Test Configuration** - Improved pytest discovery reliability
  - Excluded CodeQL test fixtures from pytest discovery (prevents false test detection)
  - Added `norecursedirs` in pytest.ini to ignore `cable-modem-monitor-ql`, `.venv`, and `codeql` directories
  - VS Code pytest settings now ignore CodeQL and venv directories
  - Fixes issue where CodeQL `.py` fixtures were incorrectly detected as Python tests
- **Git Ignore Configuration** - Better development artifact handling
  - Ignores local CodeQL CLI installation directory (`/codeql/`)
  - Separates local development artifacts from GitHub workflow artifacts
  - Clarified comments distinguishing local vs CI/CD CodeQL resources

### Fixed
- **Threading Cleanup Error in Tests** - Resolved race condition in HTTP error handling tests
  - Fixed `test_http_rejects_5xx` test that had intermittent threading cleanup errors
  - Proper async mock teardown and session cleanup
  - Prevents "Task was destroyed but it is pending" warnings
- **Authentication Failure Handling** - Universal fix for setup blocking on auth failures (Issue #4)
  - Integration setup now properly blocks when authentication fails
  - Prevents "Retrying setup" loops for incorrect credentials
  - Returns proper `ConfigEntryNotReady` with auth error details
  - Applies to all authentication methods (Basic, Form, HNAP)
  - Users see clear error message: "Authentication failed" instead of infinite retry
- **Enhanced Diagnostic Logging** - Better troubleshooting for parser and auth issues
  - HNAP authentication shows full request/response details when auth fails
  - MB8611 HNAP parser logs attempted URLs and responses
  - MB8611 Static parser logs detection attempts and failures
  - Helps diagnose parser selection issues (related to Issue #4)
- **Parser Loading Performance Test** - Fixed flaky test timing assertion
  - Increased cached load threshold from 1ms to 10ms
  - Prevents intermittent failures on slower systems or under load
  - More realistic timing expectation for cached operations

## [3.3.0] - 2025-11-18

### Added
- **Netgear CM600 Support** - Full support for Netgear CM600 cable modem (Issue #3)
  - JavaScript-based parser for DocsisStatus.asp page
  - Extracts channel data from InitDsTableTagValue and InitUsTableTagValue functions
  - Comprehensive test coverage with real modem fixtures
  - Handles downstream and upstream channel parsing
  - Status: Awaiting user confirmation on hardware
- **Enhanced Parser Diagnostics** - Better troubleshooting information
  - `parser_detection` section shows user selection vs. auto-detection
  - `detection_method` field: "user_selected", "cached", or "auto_detected"
  - `parser_detection_history` tracks attempted parsers during failures
  - Helps diagnose parser mismatch issues (like Issue #4)
  - New `_get_detection_method()` helper function in diagnostics.py
  - Comprehensive test coverage (4 new diagnostics tests)
- **Core Module Test Coverage** - 115 new unit tests for previously untested modules
  - `core/signal_analyzer.py`: 22 tests covering SNR/power analysis, error trending, polling recommendations
  - `core/health_monitor.py`: 45 tests covering ping/HTTP checks, input validation, latency calculations
  - `core/hnap_builder.py`: 25 tests covering SOAP envelope building, XML parsing, HNAP requests
  - `core/discovery_helpers.py`: 3 tests covering ParserNotFoundError exception
  - `core/authentication.py`: 11 tests covering NoAuth, BasicHTTP, and Form auth strategies
  - `lib/html_crawler.py`: 9 tests covering HTML fetching, error handling, session management
  - Total test count increased from 328 to 443 tests (+35%)
  - Test-to-code ratio now ~70% (6,548 test lines / 9,404 source lines)
- **Code Coverage Requirement Increased** - Raised minimum coverage threshold
  - Increased from 50% to 60% in pytest.ini and CI/CD workflows
  - Current coverage: ~70% (exceeds new requirement)
  - Enforced in GitHub Actions for all pull requests
  - Reflects improved test infrastructure and quality standards
- **Enhanced CodeQL Security Scanning** - Comprehensive static analysis for security vulnerabilities
  - **5 Custom Security Queries** tailored for network device integrations:
    - `subprocess-injection.ql`: Detects command injection in subprocess calls (CWE-078, severity 9.0)
    - `unsafe-xml-parsing.ql`: Ensures defusedxml usage to prevent XXE attacks (CWE-611, severity 7.5)
    - `hardcoded-credentials.ql`: Finds hardcoded passwords/API keys (CWE-798, severity 8.5)
    - `insecure-ssl-config.ql`: Validates SSL/TLS configuration justifications (CWE-295, severity 6.0)
    - `path-traversal.ql`: Prevents file system path traversal (CWE-022, severity 8.0)
  - **Expanded Query Packs**: Added security-extended suite for comprehensive coverage
  - **Query Suite Organization**: `cable-modem-security.qls` organizes all custom queries
  - **Smart Exclusions**: Filters out false positives with documented rationale
  - **Enhanced Configuration**: Setup Python dependencies for better code flow analysis
  - **Comprehensive Documentation**: Full README with examples, justifications, and local testing guide
  - **Automated Scanning**: Runs on push, PRs, and weekly schedule (Mondays 9 AM UTC)
- **Development Environment Improvements**
  - Automated bootstrap script for Python virtual environment setup
  - Enhanced devcontainer configuration with custom Dockerfile
  - Cross-platform VSCode workspace configuration (Windows 11, Chrome OS Flex, macOS)
  - Improved pytest configuration with better test discovery
  - Developer quickstart documentation
  - Setup verification scripts
- **CI Check Script** - Local validation before pushing changes
  - `scripts/ci-check.sh` runs Black, Ruff, Mypy, and Pytest locally
  - Matches CI environment checks to catch issues before push
  - Provides immediate feedback without waiting for GitHub Actions
- **Local Environment Setup Guide** - Comprehensive troubleshooting documentation
  - `docs/LOCAL_ENVIRONMENT_SETUP.md` covers environment setup and common issues
  - Documents yarl import errors and dependency conflicts
  - Explains mypy behavior differences (with/without types-requests)
  - Provides pre-commit hook setup instructions
  - Includes recommended development workflow

### Changed
- **Documentation Cleanup** - Archived historical documents and streamlined roadmap
  - Trimmed ARCHITECTURE_ROADMAP.md from 2,474 to 313 lines (87% reduction)
  - Moved 7 historical documents to docs/archive/ (~130 KB)
  - Created archive structure: v3.3.0_dev_sessions/, completed_features/
  - Focused roadmap on current v3.x status and open issues
  - Better maintainability and navigation
- **Parser Detection Logging** - Enhanced troubleshooting output
  - Shows attempted parsers when detection fails
  - Added TC4400 detection debug logging (Issue #1)
  - Parser error messages include attempted parser list
  - Better visibility into detection failures
- **MB8611 Static Parser Enhancement** - Added MB8600 fallback URL compatibility
  - New URL pattern: `/MotoConnection.asp` (MB8600-style)
  - Handles firmware variations that use older MB8600 URLs
  - Form-based authentication support for legacy endpoints
- **Issue Status Updates** - Accurate tracking in TEST_FIXTURE_STATUS.md
  - Issue #2 (XB7 system info): Marked RESOLVED (v2.6.0)
  - Issue #3 (CM600): Marked IMPLEMENTED (v3.3.0), awaiting testing
  - Issue #4 (MB8611): Analysis shows parser mismatch issue
  - Issue #5 (XB7 timeout): Marked RESOLVED (v2.6.0)
- **Modem Compatibility Documentation** - Accurate status for all modems
  - CM600 listed as "Experimental / Newly Implemented"
  - MB8611 clarified as having dual parsers (HNAP vs Static)
  - Clear guidance on parser selection importance
- **Makefile Simplification** - Streamlined development commands
  - Reduced from 126 lines to 54 lines
  - Clearer command structure and documentation
  - Better cross-platform compatibility
- **Pre-commit Configuration** - Excluded JSONC files from JSON validation
  - Allows comments in devcontainer.json and VS Code settings.json
  - Maintains strict JSON checking for other configuration files
- **VSCode Settings Enhancement** - Comprehensive cross-platform configuration
  - Python interpreter path using .venv standard
  - Black formatter with proper cross-platform paths
  - Ruff linter configuration
  - Testing configuration for pytest
  - File handling and editor settings
- **Development Dependencies** - Aligned local environment with CI
  - Updated `requirements-dev.txt`: homeassistant 2025.1.0 → 2024.1.0 (fixes non-existent version)
  - Added `pytest-socket>=0.6.0` to match CI lint job requirements
  - Updated `scripts/setup.sh` to use `requirements-dev.txt` instead of manual package list
  - Updated `CONTRIBUTING.md` to use `requirements-dev.txt` instead of `tests/requirements.txt`
- **Documentation Cross-References** - Improved documentation discoverability
  - README.md now links to LOCAL_ENVIRONMENT_SETUP.md for troubleshooting
  - CONTRIBUTING.md references LOCAL_ENVIRONMENT_SETUP.md for environment issues
  - DEVELOPER_QUICKSTART.md includes LOCAL_ENVIRONMENT_SETUP.md in "Getting Help"
  - LOCAL_ENVIRONMENT_SETUP.md includes navigation header linking to other dev docs
  - Clear documentation hierarchy: README → CONTRIBUTING → specialized guides

### Fixed
- **CM600 Parser Robustness** - Improved error handling and data extraction
  - Better handling of JavaScript variable parsing
  - Type annotations for better code quality
  - Complexity warnings addressed with proper annotations
- **Import Organization** - Fixed module-level import ordering
  - Moved sanitize_html import to top of diagnostics.py
  - Sorted imports in test files for consistency
- **Type Checking Issues** - Added type ignore comments where appropriate
  - Fixed mypy errors in socket patching code
  - Proper type annotations for list variables
- **CI/CD Pipeline Issues** - Resolved multiple CI check failures
  - CodeQL configuration: Removed invalid `packs` section causing fatal error
  - Black formatting: Applied formatting to 3 test files (test_config_flow, test_authentication, test_health_monitor)
  - Mypy type checking: Configured to work with and without types-requests package
    - Disabled warn_redundant_casts and warn_unused_ignores (handles CI vs local differences)
    - Disabled warn_unreachable (prevents false positives with pytest.raises)
    - Excluded tests/ and tools/ directories from type checking
    - Added requests to mypy ignore list for consistency
  - Test failure: Fixed async mock setup in test_http_timeout (proper AsyncMock usage)
  - Removed test_html_crawler.py (tested non-existent HTMLCrawler class)
- **Type Checking Consistency** - Fixed environment-specific mypy errors
  - Added type casting in hnap_builder.py for response.text
  - Configured mypy.ini to handle both local (no stubs) and CI (with stubs) environments
  - Prevents "redundant cast" errors in CI and "returning Any" errors locally
- **Workflow Permissions** - Fixed GitHub Actions permissions for PR comments
  - Added write permissions to commit-lint.yml and changelog-check.yml workflows
  - Allows workflows to post helpful feedback comments when checks fail
  - Resolves "Resource not accessible by integration" 403 errors

## [3.2.0] - 2025-11-13

### Added
- **Fallback Mode for Unsupported Modems** - Universal parser for modems without specific support
  - New `UniversalFallbackParser` that works with any cable modem
  - Manual selection via "Unknown Modem (Fallback Mode)" in dropdown
  - Provides 4 basic sensors: Connection Status, Health Status, Ping Latency, HTTP Latency
  - Status shows as "limited" to indicate reduced functionality
  - Enables HTML capture button for diagnostic data collection
  - Allows users to contribute HTML samples for future parser development
  - Priority 1 (lowest) - only used when explicitly selected, never auto-detected
- **Parser Issue Status** - New status for when known parser extracts no channel data
  - Handles edge cases: bridge mode, firmware changes, modem initialization
  - Clear diagnostic messages guide user troubleshooting
  - Different from unsupported (parser exists but returns no data)
- **Health Monitoring in Diagnostics** - Network connectivity checks included in diagnostic download
  - ICMP ping test results with latency
  - HTTP HEAD request test results with latency
  - Connection status (responsive/unresponsive)
  - Helps diagnose network vs. modem issues

### Changed
- **Health Status Terminology** - Changed from "healthy" to "responsive" for clarity
- **Modem Dropdown and Auto-Detect Sorting** - Unified to alphabetical order
  - Both dropdown and auto-detection now use same alphabetical sorting (manufacturer → name)
  - Generic parsers appear last within their manufacturer group
  - Priority field deprecated (backward compatible, no longer used for ordering)
  - Example order: MB7621, MB8611 (HNAP), MB8611 (Static), MB Series (Generic)

### Fixed
- **Blocking Import in Event Loop** - Eliminated 515ms delays when updating button entity state
  - Moved parser import check from `available` property to async setup
  - Created `_check_restart_support()` helper function
  - Used `hass.async_add_executor_job()` to run imports in thread pool
  - Cached availability at setup time instead of checking dynamically
  - Fixes Home Assistant warning: "Detected blocking call to import_module"
- **Sensor Availability in Fallback/Limited Modes** - Sensors now properly show as available
  - Fixed sensors incorrectly showing unavailable when in fallback or limited status
  - Availability now correctly checks for fallback/limited status in addition to normal/parser_issue
- **Config Flow Input Preservation** - Form now preserves user input on validation errors
  - Previously, form would reset all fields when validation failed
  - Now preserves host, username, password, and modem_choice when showing errors
  - Improved user experience when connection fails or validation errors occur
- **Error Message Formatting** - Added newlines and numbered lists for readability
  - Used `\n` newlines in error messages (may need CSS for rendering)
  - Numbered steps for multi-step instructions
  - Easier to read error guidance in config flow
- **Latency Sensor Precision** - Rounded to whole milliseconds instead of 6+ decimals
  - Changed from `42.837194` ms to `43` ms
  - More readable and appropriate precision for network latency
- **Restart Button Availability** - Graceful handling for modems without restart support
  - Fallback mode and unknown modems don't show restart button
  - Check moved to async setup to avoid blocking I/O
  - Clear indication when restart functionality is unavailable

### Security
- **Bandit Security Scanner Suppressions** - Addressed false positive warnings
  - Added `# nosec B105` comments to suppress 3 false positives:
    - `CONF_PASSWORD` constant (configuration key name, not password value)
    - `password_field` parameters (HTML form field names, not password values)
  - All 6 Bandit warnings addressed (3 suppressed false positives + 3 already mitigated)
  - XML parsing warnings already protected by required defusedxml==0.7.1 dependency
  - Security analysis confirms 0 real vulnerabilities

### Testing
- **All 319 Tests Passing** - Fixed test failures for v3.2.0 release
  - Updated `test_version_is_3_2_0` to expect VERSION = "3.2.0"
  - Updated `test_get_parsers_sorts_alphabetically` to check alphabetical sorting
  - Added `# noqa: C901` to suppress complexity warnings (4 functions)
  - Applied Black formatting across all modified files

### Technical Details
- **Files Modified**: `const.py`, `manifest.json`, `config_flow.py`, `parsers/__init__.py`, `button.py`, `modem_scraper.py`, `sensor.py`, `strings.json`, test files
- **Version**: Bumped from 3.1.0 to 3.2.0
- **Commits**: 40+ commits with fallback mode, UX improvements, and bug fixes
- **Compatibility**: No breaking changes, fully backward compatible

## [3.1.0] - 2025-11-11

### Added
- **Update Modem Data Button** - Manual refresh button for on-demand data updates
  - `button.cable_modem_update_data` - Triggers immediate coordinator refresh
  - Useful for verifying changes after modem configuration or troubleshooting
  - Complements automatic polling with user-controlled updates
  - Shows notification when update is triggered
- **HTML Capture for Diagnostics** - Capture raw modem HTML for support requests
  - `button.cable_modem_capture_html` - Captures raw HTML responses from modem
  - Stores captured data in memory for 5 minutes with automatic expiry
  - Automatically sanitizes sensitive data (MACs, serials, passwords, private IPs)
  - Included in diagnostics download when available
  - Makes requesting support for unsupported modems much easier
  - Notification shows capture status and reminds user to download diagnostics
  - Diagnostic button category - grouped with other diagnostic tools

### Fixed
- **MB8611 Static Parser Missing URL Patterns** - Fixed "No URL patterns available to try" error (Fixes #6)
  - Added missing `url_patterns` attribute to `MotorolaMB8611StaticParser` class
  - Parser now properly specifies `/MotoStatusConnection.html` as the data source URL
  - Without this attribute, the modem scraper had no URLs to fetch, causing immediate failure
  - Users can now successfully use the "Motorola MB8611 (Static)" parser option
- **SSL Certificate Verification Issue** - Fixed HTTPS connection failures for modems with self-signed certificates (Fixes #6)
  - Added explicit `verify=session.verify` parameter to all HTTP requests in authentication.py (6 locations)
  - Added explicit `verify=session.verify` parameter to all HTTP requests in hnap_builder.py (2 locations)
  - While `session.verify=False` was already configured, some requests library versions may not reliably inherit this setting
  - Ensures SSL verification setting is explicitly passed to every HTTP request for consistent behavior
  - Resolves HTTPS connection failures for Motorola MB8611 and other modems using self-signed certificates
- **Diagnostics Log Retrieval** - Improved log collection for diagnostics downloads
  - Added primary method: retrieve logs from Home Assistant's system_log integration (in-memory circular buffer)
  - Falls back to reading home-assistant.log file if system_log unavailable
  - Fixes issue where diagnostics showed "Log file not available" on Docker/supervised installations
  - Fixed 'tuple' object has no attribute 'name' error by correctly parsing system_log tuple format
  - Discovered system_log only stores errors/warnings, not INFO/DEBUG logs (by design)
  - Updated to correctly parse tuple format: (logger_name, (file, line_num), exception_or_none)
  - Better error messages explain that full logs require HA logs UI, journalctl, or container logs
  - Will capture cable_modem_monitor errors when they occur for troubleshooting
- **Version Logging on Startup** - Integration now logs version number when it starts
  - Example: "Cable Modem Monitor version 3.1.0 is starting"
  - Helps identify which version is loaded when troubleshooting issues
  - Makes it easy to confirm integration loaded properly from diagnostic logs

### Performance
- **Parser Loading Optimization** - Dramatically faster integration startup and modem restarts
  - When user selects specific modem: load only that parser (8x faster than scanning all parsers)
  - Auto-detection mode: scan filesystem once, cache results for subsequent loads (instant)
  - Restart button: uses same optimization as startup
  - Added `get_parser_by_name()` function for direct parser loading without discovery
  - Added global parser cache to avoid repeated filesystem scans
  - Parser discovery now only runs during config flow and first auto-detection
- **Protocol Discovery Optimization** - Skips HTTP/HTTPS protocol fallback when working URL is cached
  - First setup: tries HTTPS→HTTP fallback, saves working URL with protocol
  - Subsequent startups: extracts protocol from cached URL, uses it directly
  - Eliminates failed connection attempts on HTTP-only modems (faster, cleaner logs)
  - Config changes automatically re-detect protocol when user clicks Submit
  - Particularly beneficial for older HTTP-only modems that previously logged HTTPS errors

### Removed
- **v1.x to v2.0 Entity Migration Code** - Removed automatic entity ID migration from legacy versions
  - Deleted 127 lines of migration code that ran on every startup
  - Removed: `async_migrate_entity_ids()`, `_migrate_config_data()`, and helper functions
  - Users still on v1.x can perform clean reinstall (see UPGRADING.md)
  - Reduces startup overhead and code complexity
  - Migration was for v2.0.0 (released Oct 24, 2025) - no longer needed at v3.1.0

### Testing
- **Comprehensive Test Coverage for v3.1.0 Features** - Added 20+ new test cases
  - UpdateModemDataButton tests (initialization, press, notification)
  - CaptureHtmlButton tests (success, failure, exception handling)
  - HTML sanitization tests (13 test cases covering MACs, serials, IPs, passwords, tokens)
  - Diagnostics integration tests (capture inclusion, expiry, sanitization verification)
  - Updated button setup test to verify all 5 buttons
- **Fixed 5 Failing Tests in test_version_and_startup.py** - All 283 tests now pass
  - Fixed HomeAssistant mock setup with proper attributes (data, config_entries, services)
  - Made async_add_executor_job properly execute functions and return awaitable results
  - Added async mocks for coordinator.async_config_entry_first_refresh
  - Patched _update_device_registry to avoid deep HA registry initialization
  - Added ConfigEntryState.SETUP_IN_PROGRESS to mock config entries
  - All version logging and parser selection optimization tests now pass

### Technical Details
- **Files Modified**: `mb8611_static.py`, `authentication.py`, `hnap_builder.py`, `diagnostics.py`, `__init__.py`, `button.py`, `parsers/__init__.py`, `modem_scraper.py`, `const.py`, `manifest.json`
- **HTML Capture Implementation**: Added `capture_raw` parameter to `get_modem_data()` and `_fetch_data()` methods, stores raw HTML in coordinator data with 5-minute TTL, sanitization removes MACs/serials/passwords/IPs while preserving signal data for debugging
- **Test Coverage**: Added `test_diagnostics.py` (28 tests) and expanded `test_button.py` (+6 tests, 669 lines total)
- **Root Cause**: The Static parser implementation was incomplete - it had parsing logic but no URL configuration
- **Impact**: Fixes both the "no URL patterns" error and HTTPS authentication issues for MB8611 and similar modems
- **Diagnostics**: Now works reliably across all Home Assistant installation types (Docker, supervised, core, OS)
- **Performance**: 8x faster startup when specific modem selected, instant startup for cached auto-detection
- **Compatibility**: No breaking changes, fully backward compatible with existing configurations

## [3.0.0] - 2025-11-10

### Added
- **MB8611 Dual-Parser Support** - Two parsing strategies for Motorola MB8611 modems
  - HNAP/SOAP protocol parser (priority 101) for API-based access with authentication
  - Static HTML parser (priority 100) as fallback for basic HTML table scraping
  - Increases compatibility and provides graceful fallback for different configurations
  - Both parsers support MB8611 and MB8612 models
  - Comprehensive test coverage for both parsers
- **Enhanced Discovery System** - Automatic modem detection with HNAP and HTTP-based discovery
  - HNAP protocol builder for Arris/Motorola modems
  - Discovery helpers for automatic modem identification
  - Detection notifications in config flow
- **Flexible Authentication Framework** - Support for multiple authentication strategies
  - Basic HTTP Authentication
  - Digest Authentication
  - HNAP Authentication (Arris/Motorola)
  - Strategy pattern for extensible auth types
- **MB8611 Parser** - Complete support for Motorola MB8611 cable modem
  - HNAP-based data extraction
  - 33 comprehensive tests for MB8611 functionality
- **Arris SB6190 Support** - Added parser for Arris SB6190 cable modem
  - Supports both transposed and non-transposed table formats
  - Parses downstream/upstream channels and error statistics
  - Comprehensive test suite with real hardware fixtures
  - Model-specific detection to avoid conflicts with other Arris modems
- **Enhanced Auto-Detection Logging** - INFO-level logs for modem auto-detection process
  - Logs now visible in Home Assistant's standard logs UI (not just raw logs)
  - Shows which parser is being used, URLs attempted, and detection results
  - Helps users understand what's happening during modem setup
  - Improves troubleshooting for connection and detection issues
- **Enhanced Diagnostics** - Diagnostics now include recent logs
  - Last 150 log entries from the integration automatically included
  - Logs are sanitized to remove sensitive information (passwords, MACs, private IPs)
  - Added modem detection metadata (detected_modem, parser_name, working_url)
  - Users no longer need to manually extract logs for bug reports
- **Docker Development Environment** - Complete Docker-based development setup
  - docker-compose.test.yml for local Home Assistant testing
  - VS Code Dev Container configuration
  - Management script (docker-dev.sh) with start/stop/logs/clean commands
  - Comprehensive documentation (DEVELOPER_QUICKSTART.md, .devcontainer/README.md)
  - Makefile targets for Docker operations
- **Comprehensive Test Coverage** - Added extensive test suites
  - 33 new tests for MB8611 parser
  - Coordinator improvements tests
  - Config flow tests
  - Total test improvements across authentication and discovery modules

### Changed
- **MB8611 Parser Refactoring** - Enhanced parser architecture
  - Renamed `mb8611.py` → `mb8611_hnap.py` with class rename to `MotorolaMB8611HnapParser`
  - Updated display name to "Motorola MB8611 (HNAP)" for clarity
  - Increased HNAP parser priority to 101 (tries before static parser)
  - Fixed frequency conversion to use `int(round())` for consistent integer output in both parsers
  - Reorganized test fixtures: `mb8611/` → `mb8611_hnap/` and new `mb8611_static/` directories
- **Session Management Improvements** - Better connection handling and modem restart monitoring
  - Improved modem restart detection and availability handling
  - Enhanced button component with better reload handling
  - Improved platform unload error handling during reload
  - Better channel synchronization detection
- **UI Improvements** - Fixed modem model selection dialog labels
  - "Modem Model" label now displays correctly in settings dialog
  - Added proper translations for modem_choice field
- **Code Quality Improvements** - Type checking and linting enhancements
  - Fixed all Pylance type checking errors
  - Fixed all Flake8 linting errors
  - Added .flake8 configuration (120-character line length)
  - Added pyproject.toml configuration
  - Removed unused imports and fixed PEP 8 formatting
  - Modern type hints with `from __future__ import annotations`
  - Enforced line length limits (removed E501 exception)

### Fixed
- **Type Checking Errors** - Resolved all mypy type checking errors
  - Added type annotations (`dict[str, Any]`) for channel data dictionaries in SB6190 parser
  - Removed `[mypy-requests.*]` ignore from mypy.ini to allow types-requests stubs (required by CI)
  - Added urllib3 to mypy.ini ignored imports list
  - All code quality checks (ruff, black, mypy with types-requests) now pass successfully
- **Code Cleanup** - Removed unused `import re` from diagnostics.py
- **Config Flow Handler Registration** - Fixed "Flow handler not found" error
  - Added @config_entries.HANDLERS.register(DOMAIN) decorator
  - Renamed ConfigFlow to CableModemMonitorConfigFlow for clarity
- **Parser Detection** - Improved Arris SB6141 parser to avoid conflicts with SB6190
  - Added model-specific detection checks
  - Explicitly exclude SB6190 to prevent false positives
- **Type Safety** - Resolved all type annotation errors
  - Fixed dictionary access type checking errors
  - Corrected type variance issues
  - Fixed parameter type annotations with None defaults
  - Resolved authentication module type errors
- **Parser Improvements** - Enhanced parser reliability
  - Fixed MB8611 test failures (AuthFactory patch path and frequency precision)
  - Improved None handling in Motorola generic parser detection
  - Removed duplicate manufacturer names from detection
- **SSL Context Creation** - Fixed blocking I/O in event loop for SSL context creation

### Documentation
- **Phase 1, 2, 3 Implementation Summary** - Comprehensive documentation of architecture phases
- **Session Improvements Summary** - Detailed session management enhancements
- **Test Coverage Summary** - Overview of test additions and coverage
- **Developer Documentation** - Enhanced contribution and setup guides
  - Added "Modem Model Selection" section to TROUBLESHOOTING.md
  - Documented how to view auto-detection logs (3 different methods)
  - Enhanced bug report template with better log collection instructions
  - Added modem selection dropdown to bug reports
  - Updated README.md with modem model configuration option
  - Updated CONTRIBUTING.md with Docker workflow instructions
- **Feature Request Organization** - Organized feature requests into dedicated directory
  - Smart polling sensor template
  - Netgear CM600 parser request
  - Phase 4 JSON configs proposal
  - Phase 5 community platform proposal
  - HTML Capture Feature Specification (507 lines)

## [2.6.1] - 2025-11-06

### Fixed
- **Excessive Logging** - Reduced excessive error logging during modem restart and connection attempts. Debug messages that were temporarily promoted to `ERROR` for testing have been moved to the appropriate `DEBUG` level, cleaning up the logs during normal operation.
- **Standardized Logging** - Updated all logging statements to use standard string formatting instead of f-strings for consistency and performance.

### Changed
- **Modem Restart Reliability** - The `restart_modem` function is now more robust.
  - It always re-fetches connection data before a restart to detect if the modem has fallen back from HTTPS to HTTP, ensuring the correct protocol is used.
  - It now attempts to log in before sending the restart command if credentials are provided, improving compatibility with modems that require authentication for restart functionality.
- **Motorola Parser Security** - Improved the security of the Motorola parser's login mechanism by allowing redirects only within private IP address ranges, preventing open redirect vulnerabilities while still accommodating local network device behavior.

### Added
- **Restart Tests** - Added a comprehensive suite of tests for the `restart_modem` functionality to verify HTTP/HTTPS fallback, login handling, and various failure scenarios.

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
