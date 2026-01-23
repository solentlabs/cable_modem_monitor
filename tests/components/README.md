# Component Tests

> Auto-generated from test files. Do not edit manually.

Tests for Home Assistant components including config flow, coordinator, sensors, buttons, diagnostics, and the modem scraper.

**Total Tests:** 325

## Test Files

| File | Tests | Description |
|------|-------|-------------|
| [test_auth.py](test_auth.py) | 3 |  |
| [test_button.py](test_button.py) | 0 | Tests for Cable Modem Monitor button platform. |
| [test_channel_utils.py](test_channel_utils.py) | 29 | Tests for channel_utils helper functions. |
| [test_config_flow.py](test_config_flow.py) | 32 | Tests for Cable Modem Monitor config flow. |
| [test_config_flow_helpers.py](test_config_flow_helpers.py) | 1 | Tests for config_flow_helpers.py. |
| [test_coordinator.py](test_coordinator.py) | 18 | Tests for Cable Modem Monitor coordinator functionality. |
| [test_coordinator_improvements.py](test_coordinator_improvements.py) | 5 | Tests for Cable Modem Monitor coordinator improvements. |
| [test_data_orchestrator.py](test_data_orchestrator.py) | 92 | Tests for Cable Modem Monitor scraper. |
| [test_diagnostics.py](test_diagnostics.py) | 52 | Tests for Cable Modem Monitor diagnostics platform. |
| [test_entity_migration.py](test_entity_migration.py) | 11 | Tests for entity migration utilities. |
| [test_protocol_caching.py](test_protocol_caching.py) | 12 | Tests for protocol caching optimization. |
| [test_sensor.py](test_sensor.py) | 68 | Tests for Cable Modem Monitor sensors. |
| [test_version_and_startup.py](test_version_and_startup.py) | 2 | Tests for version logging and startup optimizations. |

## Test Details

### test_auth.py

**TestAuth** (3 tests)
: Test the authentication system.

- `test_form_auth_uses_parser_hints`: Test form-based authentication uses parser's auth_form_hints.
- `test_parser_does_not_have_login_method`: Test that parsers don't have a login() method.
- `test_parser_without_hints_can_be_instantiated`: Test that parsers without auth_form_hints can still be used.

### test_button.py

Tests for Cable Modem Monitor button platform.

### test_channel_utils.py

Tests for channel_utils helper functions.

**TestNormalizeChannelType** (15 tests)
: Tests for normalize_channel_type function.

- `test_downstream_qam_from_channel_type`: QAM downstream with explicit channel_type.
- `test_downstream_qam_from_modulation_only`: QAM downstream with only modulation field.
- `test_downstream_qam_default`: QAM downstream when no type info provided.
- `test_downstream_ofdm_from_channel_type`: OFDM downstream with explicit channel_type.
- `test_downstream_ofdm_from_modulation`: OFDM downstream detected from modulation field.
- `test_downstream_ofdm_from_is_ofdm_flag`: OFDM downstream detected from is_ofdm flag.
- `test_upstream_atdma_from_channel_type`: ATDMA upstream with explicit channel_type from modem.
- `test_upstream_atdma_from_channel_type_lowercase`: ATDMA upstream with lowercase channel_type.
- `test_upstream_atdma_default`: ATDMA upstream when no type info provided.
- `test_upstream_ofdma_from_channel_type`: OFDMA upstream with explicit channel_type from modem.
- `test_upstream_ofdma_from_channel_type_lowercase`: OFDMA upstream with lowercase channel_type.
- `test_upstream_ofdma_from_modulation`: OFDMA upstream detected from modulation field.
- `test_upstream_ofdma_from_is_ofdm_flag`: OFDMA upstream detected from is_ofdm flag.
- `test_empty_channel`: Empty channel defaults correctly.
- `test_case_insensitivity`: Channel type matching is case-insensitive.

**TestExtractChannelId** (10 tests)
: Tests for extract_channel_id function.

- `test_numeric_string`: Numeric string channel ID.
- `test_numeric_int`: Integer channel ID (already numeric).
- `test_channel_field_fallback`: Falls back to 'channel' field if 'channel_id' missing.
- `test_ofdm_prefix`: OFDM-prefixed channel ID from G54 parser.
- `test_ofdma_prefix`: OFDMA-prefixed channel ID from G54 parser.
- `test_other_prefixes`: Other prefixed formats should also work.
- `test_missing_channel_id`: Returns default when no channel_id or channel field.
- `test_unparseable_string`: Returns default for unparseable strings.
- `test_none_value`: Returns default when channel_id is None.
- `test_whitespace_handling`: Handles whitespace in channel IDs.

**TestNormalizeChannels** (4 tests)
: Tests for normalize_channels function.

- `test_downstream_normalization`: Test downstream channel normalization.
- `test_upstream_ofdma_channels`: Test upstream OFDMA channel normalization (G54-style).
- `test_channels_sorted_by_frequency`: Channels within a type are sorted by frequency.
- `test_empty_channels`: Empty channel list returns empty dict.

### test_config_flow.py

Tests for Cable Modem Monitor config flow.

TEST DATA TABLES
================
This module uses table-driven tests for parameterized test cases.
Tables are defined at the top of the file with ASCII box-drawing comments.

**TestConfigFlow** (4 tests)
: Test the config flow.

- `test_scan_interval_minimum_valid`: Test that minimum scan interval (60s) is accepted.
- `test_scan_interval_maximum_valid`: Test that maximum scan interval (1800s) is accepted.
- `test_scan_interval_default_value`: Test that default scan interval is 600s (10 minutes).
- `test_scan_interval_range_valid`: Test that scan interval range makes sense.

**TestValidateInput** (1 tests)
: Test input validation.

- `test_requires_host`: Test that host is required.

**TestScanIntervalValidation** (4 tests)
: Test scan interval validation logic.

- `test_scan_interval_below_minimum_invalid`: Test that values below minimum are invalid.
- `test_scan_interval_above_maximum_invalid`: Test that values above maximum are invalid.
- `test_scan_interval_at_boundaries_valid`: Test that boundary values are valid.
- `test_scan_interval_valid_values`: Test valid scan interval values via table-driven cases.

**TestModemNameFormatting** (0 tests)
: Test modem name and manufacturer formatting in titles.


**TestConfigConstants** (2 tests)
: Test configuration constants are properly defined.

- `test_all_config_keys_defined`: Test that all config keys are defined.
- `test_defaults_are_reasonable`: Test that default values make sense.

**TestOptionsFlow** (3 tests)
: Test the options flow for reconfiguration.

- `test_exists`: Test that OptionsFlowHandler class exists.
- `test_has_init_step`: Test that options flow has init step.
- `test_can_instantiate_without_arguments`: Test that OptionsFlowHandler can be instantiated without arguments.

**TestConfigFlowRegistration** (1 tests)
: Test the config flow registration.

- `test_handler_is_registered`: Test that the config flow handler is registered.

**TestValidationProgressHelper** (8 tests)
: Test the ValidationProgressHelper state machine.

- `test_initial_state`: Test helper initializes with empty state.
- `test_is_running_when_no_task`: Test is_running returns False when no task exists.
- `test_is_running_when_task_done`: Test is_running returns False when task is complete.
- `test_is_running_when_task_active`: Test is_running returns True when task is running.
- `test_start_stores_user_input`: Test start() stores user input and creates task.
- `test_reset_clears_all_state`: Test reset() clears all state.
- `test_get_error_type_with_known_error`: Test get_error_type returns correct classification.
- `test_get_error_type_with_no_error`: Test get_error_type when no error is set.

**TestAuthTypeFlow** (0 tests)
: Test the auth type selection flow.


**TestEntityPrefixLogic** (3 tests)
: Test the entity prefix dropdown conditional logic.

- `test_first_modem_has_none_option`: Test first modem config includes 'None' prefix option.
- `test_second_modem_no_none_option`: Test second modem config excludes 'None' prefix option.
- `test_default_entity_prefix_preserved`: Test that explicitly passed default_entity_prefix is used.

**TestOptionsFlowCredentialPreservation** (4 tests)
: Test the options flow credential preservation logic.

- `test_preserve_password_when_empty`: Test password is preserved when user leaves it empty.
- `test_preserve_username_when_empty`: Test username is preserved when user leaves it empty.
- `test_new_password_not_overwritten`: Test new password is not overwritten by existing.
- `test_preserve_both_when_both_empty`: Test both credentials preserved when both empty.

**TestOptionsFlowDetectionPreservation** (2 tests)
: Test the options flow detection info preservation.

- `test_preserve_detection_info_copies_all_fields`: Test all detection fields are preserved.
- `test_preserve_detection_with_missing_fields`: Test preservation handles missing fields gracefully.

### test_config_flow_helpers.py

Tests for config_flow_helpers.py.

**TestClassifyError** (1 tests)
: Tests for classify_error function.

- `test_classify_error`: Test classify_error returns correct error code for each error type.

**TestBuildParserDropdown** (0 tests)
: Tests for build_parser_dropdown function.


**TestGetAuthTypesForParser** (0 tests)
: Tests for get_auth_types_for_parser function.


**TestNeedsAuthTypeSelection** (0 tests)
: Tests for needs_auth_type_selection function.


**TestGetAuthTypeDropdown** (0 tests)
: Tests for get_auth_type_dropdown function.


**TestBuildStaticConfigForAuthType** (0 tests)
: Tests for _build_static_config_for_auth_type function.


**TestLoadParserHints** (0 tests)
: Tests for load_parser_hints function.


**TestValidateInput** (0 tests)
: Tests for validate_input function.


### test_coordinator.py

Tests for Cable Modem Monitor coordinator functionality.

**TestCoordinatorInterval** (4 tests)
: Test coordinator respects scan interval configuration.

- `test_default_scan_interval_as_timedelta`: Test default scan interval converts to timedelta correctly.
- `test_minimum_scan_interval_as_timedelta`: Test minimum scan interval converts to timedelta correctly.
- `test_maximum_scan_interval_as_timedelta`: Test maximum scan interval converts to timedelta correctly.
- `test_custom_scan_intervals`: Test various custom scan intervals.

**TestModemDataUpdate** (3 tests)
: Test data update logic.

- `test_scraper_returns_valid_data`: Test that scraper returns expected data structure.
- `test_scraper_handles_connection_failure`: Test that scraper can raise exceptions for connection failures.
- `test_scraper_data_types`: Test that scraper returns correct data types.

**TestUpdateFailureHandling** (3 tests)
: Test how coordinator handles update failures.

- `test_connection_error_structure`: Test that connection errors can be caught.
- `test_timeout_error_structure`: Test that timeout errors can be caught.
- `test_parsing_error_structure`: Test that parsing errors can be caught.

**TestCoordinatorConfiguration** (5 tests)
: Test coordinator configuration from config entry.

- `test_extract_scan_interval_from_config`: Test extracting scan interval from config entry data.
- `test_default_scan_interval_when_not_configured`: Test using default when scan interval not in config.
- `test_scan_interval_validation_minimum`: Test that scan interval respects minimum.
- `test_scan_interval_validation_maximum`: Test that scan interval respects maximum.
- `test_scan_interval_validation_range`: Test scan interval clamping to valid range.

**TestReloadFunctionality** (3 tests)
: Test that configuration changes trigger reload.

- `test_reload_function_exists`: Test that async_reload_entry function signature exists.
- `test_config_change_detection`: Test detecting config changes that require reload.
- `test_no_reload_when_config_unchanged`: Test that identical config doesn't trigger reload.

### test_coordinator_improvements.py

Tests for Cable Modem Monitor coordinator improvements.

**TestCoordinatorSSLContext** (1 tests)
: Test SSL context creation in executor.

- `test_ssl_context_created_in_executor`: Test that SSL context is created in executor to avoid blocking I/O.

**TestCoordinatorConfigEntry** (1 tests)
: Test coordinator config_entry parameter.

- `test_coordinator_has_config_entry_parameter`: Test that DataUpdateCoordinator includes config_entry parameter.

**TestCoordinatorPartialData** (1 tests)
: Test coordinator returns partial data when scraper fails but health checks succeed.

- `test_partial_data_when_scraper_fails_health_succeeds`: Test that coordinator returns partial data when scraper fails but health check succeeds.

**TestCoordinatorUnload** (0 tests)
: Test coordinator unload error handling.


**TestCoordinatorStateCheck** (2 tests)
: Test coordinator handles different config entry states.

- `test_uses_first_refresh_for_setup_in_progress`: Test that async_config_entry_first_refresh is used during SETUP_IN_PROGRESS.
- `test_uses_regular_refresh_for_loaded_state`: Test that async_refresh is used when entry is already LOADED.

### test_data_orchestrator.py

Tests for Cable Modem Monitor scraper.

These tests validate the DataOrchestrator core functionality using mock parsers.
No modem-specific references - tests exercise the scraper mechanism itself.

NOTE: The scraper is core/generic functionality that will be further abstracted
in future versions. Using mock parsers (not real modems) ensures these tests
remain stable as the architecture evolves toward declarative modem configs.

**TestDataOrchestrator** (11 tests)
: Test the DataOrchestrator class.

- `test_scraper_with_mock_parser`: Test the scraper with a mock parser.
- `test_fetch_data_url_ordering`: Test that the scraper tries URLs in the correct order when all fail.
- `test_fetch_data_stops_on_first_success`: Test that the scraper stops trying URLs after first successful response.
- `test_restart_modem_https_to_http_fallback`: Test that restart_modem falls back from HTTPS to HTTP when connection refused.
- `test_restart_modem_calls_login_with_credentials`: Test that restart_modem calls login when credentials are provided.
- `test_restart_modem_skips_login_without_credentials`: Test that restart_modem skips login when no credentials provided.
- `test_restart_modem_fails_when_login_fails`: Test that restart_modem aborts when login fails.
- `test_restart_modem_fails_when_connection_fails`: Test that restart_modem fails gracefully when connection fails.
- `test_restart_modem_fails_when_parser_not_detected`: Test that restart_modem fails when parser cannot be detected.
- `test_restart_modem_fails_when_modem_yaml_has_no_restart_action`: Test that restart_modem fails when modem.yaml has no actions.restart config.
- `test_restart_modem_always_fetches_data_even_with_cached_parser`: Test that restart_modem always calls _fetch_data even when parser is cached.

**TestRestartValidation** (6 tests)
: Tests for _validate_restart_capability method.

- `test_validate_restart_returns_true_when_modem_yaml_has_restart`: Test validation succeeds when modem.yaml has actions.restart configured.
- `test_validate_restart_returns_false_when_no_restart_action`: Test validation fails when modem.yaml has no actions.restart.
- `test_validate_restart_returns_false_when_no_actions_key`: Test validation fails when modem.yaml has no actions key at all.
- `test_validate_restart_returns_false_when_no_adapter`: Test validation fails when no modem.yaml adapter found.
- `test_validate_restart_returns_false_when_no_parser`: Test validation fails when parser is not set.
- `test_validate_restart_with_hnap_action_type`: Test validation succeeds for HNAP restart action type.

**TestFallbackParserDetection** (6 tests)
: Test that fallback parser is excluded from detection phases and only used as last resort.

- `test_excluded_from_anonymous_probing`: Test that fallback parser is excluded from Phase 1 (anonymous probing).
- `test_excluded_from_prioritized_parsers`: Test that fallback parser is excluded from Phase 3 (prioritized parsers).
- `test_excluded_from_url_discovery_tier2`: Test that fallback parser is excluded from Tier 2 URL discovery.
- `test_excluded_from_url_discovery_tier3`: Test that fallback parser is excluded from Tier 3 URL discovery.
- `test_not_auto_selected_raises_error`: Test that fallback parser is NOT auto-selected when detection fails.
- `test_known_modem_detected_before_fallback`: Test that a known modem parser is detected before fallback parser.

**TestLogoutAfterPoll** (10 tests)
: Tests for session cleanup after polling.

- `test_perform_logout_calls_endpoint_when_defined`: Test that _perform_logout calls the logout endpoint when parser defines it.
- `test_perform_logout_skips_when_no_endpoint`: Test that _perform_logout does nothing when parser has no logout_endpoint.
- `test_perform_logout_skips_when_no_parser`: Test that _perform_logout does nothing when no parser is set.
- `test_perform_logout_handles_request_failure`: Test that _perform_logout gracefully handles request failures.
- `test_get_modem_data_calls_logout_in_finally`: Test that get_modem_data calls _perform_logout even on success.
- `test_get_modem_data_calls_logout_on_error`: Test that get_modem_data calls _perform_logout even on error.
- `test_get_detection_info_includes_logout_endpoint`: Test that get_detection_info exposes logout_endpoint from adapter.
- `test_get_detection_info_logout_endpoint_none_when_not_set`: Test that get_detection_info returns None for logout_endpoint when not set.
- `test_perform_logout_with_https_url`: Test that _perform_logout works with HTTPS base URL.
- `test_perform_logout_with_different_endpoint_formats`: Test that _perform_logout works with various endpoint formats.

**TestDataOrchestratorInitialization** (13 tests)
: Tests for DataOrchestrator initialization and configuration.

- `test_init_with_plain_ip_uses_https_default`: Test that plain IP defaults to HTTPS.
- `test_init_with_http_url_preserves_protocol`: Test that explicit HTTP URL is preserved.
- `test_init_with_https_url_preserves_protocol`: Test that explicit HTTPS URL is preserved.
- `test_init_with_trailing_slash_removed`: Test that trailing slashes are removed from URL.
- `test_init_uses_cached_url_protocol`: Test that cached URL protocol is used for plain IP.
- `test_init_with_credentials`: Test initialization with credentials.
- `test_init_with_parser_instance`: Test initialization with a parser instance.
- `test_init_with_parser_class`: Test initialization with a parser class.
- `test_init_with_verify_ssl_true`: Test initialization with SSL verification enabled.
- `test_init_with_verify_ssl_false`: Test initialization with SSL verification disabled.
- `test_init_with_legacy_ssl_mounts_adapter`: Test that legacy SSL mode mounts the LegacySSLAdapter.
- `test_init_legacy_ssl_not_mounted_for_http`: Test that legacy SSL adapter is NOT mounted for HTTP URLs.
- `test_init_with_parser_name_for_tier2`: Test initialization with parser_name for Tier 2 caching.

**TestCapturingSession** (4 tests)
: Tests for the CapturingSession class.

- `test_capturing_session_calls_callback`: Test that CapturingSession calls the callback on each request.
- `test_capturing_session_detects_hnap_requests`: Test that CapturingSession identifies HNAP requests.
- `test_capturing_session_detects_login_pages`: Test that CapturingSession identifies login pages.
- `test_capturing_session_detects_status_pages`: Test that CapturingSession identifies status pages.

**TestClearAuthCache** (4 tests)
: Tests for auth cache clearing.

- `test_clear_auth_cache_creates_new_session`: Test that clear_auth_cache creates a fresh session.
- `test_clear_auth_cache_preserves_verify_setting`: Test that clear_auth_cache preserves SSL verify setting.
- `test_clear_auth_cache_clears_hnap_builder`: Test that clear_auth_cache clears HNAP builder cache via auth_handler.
- `test_clear_auth_cache_handles_missing_builder`: Test that clear_auth_cache handles auth handler without HNAP builder.

**TestCaptureResponse** (3 tests)
: Tests for response capture functionality.

- `test_capture_response_when_disabled`: Test that capture is skipped when disabled.
- `test_capture_response_when_enabled`: Test that response is captured when enabled.
- `test_capture_response_deduplicates_urls`: Test that duplicate URLs are not captured twice.

**TestRecordFailedUrl** (3 tests)
: Tests for failed URL recording.

- `test_record_failed_url_when_disabled`: Test that failed URL is not recorded when capture disabled.
- `test_record_failed_url_when_enabled`: Test that failed URL is recorded when capture enabled.
- `test_record_failed_url_with_response_body`: Test that response body is recorded for error pages.

**TestProtocolDetection** (3 tests)
: Tests for HTTP/HTTPS protocol detection and fallback.

- `test_fetch_data_tries_https_first`: Test that _fetch_data tries HTTPS before HTTP.
- `test_fetch_data_falls_back_to_http`: Test that _fetch_data falls back to HTTP when HTTPS fails.
- `test_fetch_data_updates_base_url_on_success`: Test that base_url is updated when HTTP fallback succeeds.

**TestLoginFlow** (3 tests)
: Tests for the login flow.

- `test_login_skipped_without_credentials`: Test that login is skipped when no credentials provided.
- `test_login_skipped_without_parser`: Test that login assumes no auth required when no parser is set.
- `test_login_assumes_no_auth_when_parser_has_no_hints`: Test that login assumes no auth required when parser has no hints.

**TestSessionExpiryHandling** (5 tests)
: Tests for session expiry detection and re-fetch.

- `test_authenticate_detects_session_expiry`: When original HTML is login page, session expiry is detected.
- `test_authenticate_skips_refetch_when_not_login_page`: When original HTML is NOT a login page, no re-fetch needed.
- `test_authenticate_uses_auth_html_when_provided`: When _login returns authenticated_html, use it directly.
- `test_authenticate_returns_none_on_login_failure`: When _login fails, return None.
- `test_authenticate_handles_refetch_still_login_page`: When re-fetch still returns login page, fall back to original.

**TestTierUrlGeneration** (3 tests)
: Tests for URL generation in different tiers.

- `test_tier1_urls_from_explicit_parser`: Test Tier 1: URLs from explicitly selected parser.
- `test_tier2_urls_from_cached_parser`: Test Tier 2: URLs from cached parser name.
- `test_tier3_excludes_fallback_parser`: Test Tier 3: Fallback parser excluded from URL discovery.

**TestGetModemData** (3 tests)
: Tests for the main get_modem_data flow.

- `test_get_modem_data_clears_captures_on_start`: Test that get_modem_data clears previous captures.
- `test_get_modem_data_returns_status_on_connection_failure`: Test that get_modem_data returns status dict on connection failure.
- `test_get_modem_data_sets_capture_enabled_flag`: Test that get_modem_data sets _capture_enabled flag when capture_raw=True.

**TestV312DetectionMethods** (9 tests)
: Tests for v3.12 HintMatcher-based detection methods.

- `test_get_parser_by_name_found`: Test _get_parser_by_name returns parser when found.
- `test_get_parser_by_name_not_found`: Test _get_parser_by_name returns None when not found.
- `test_try_instant_detection_with_prefetched_html`: Test instant detection uses pre-fetched HTML from auth discovery.
- `test_try_instant_detection_skipped_when_no_html`: Test instant detection is skipped when no pre-fetched HTML.
- `test_try_instant_detection_skipped_when_parser_exists`: Test instant detection is skipped when parser already detected.
- `test_login_markers_detection`: Table-driven test for _try_login_markers_detection.
- `test_disambiguate_finds_intersection`: Test disambiguation finds parser in both login and model matches.
- `test_disambiguate_no_intersection`: Test disambiguation returns None when no intersection.
- `test_try_quick_detection_delegates_to_login_markers`: Test _try_quick_detection delegates to _try_login_markers_detection.

**TestV312ScraperInitialization** (6 tests)
: Tests for v3.12 scraper initialization parameters.

- `test_init_with_auth_hnap_config`: Test initialization with HNAP config from config entry.
- `test_init_with_auth_url_token_config`: Test initialization with URL token config from config entry.
- `test_init_with_authenticated_html`: Test initialization with pre-fetched HTML.
- `test_init_with_session_pre_authenticated`: Test initialization with pre-authenticated session flag.
- `test_login_skipped_when_pre_authenticated`: Test _login returns success without auth when session is pre-authenticated.
- `test_login_proceeds_after_pre_auth_flag_cleared`: Test subsequent _login calls proceed normally after flag is cleared.

### test_diagnostics.py

Tests for Cable Modem Monitor diagnostics platform.

**TestSanitizeHtml** (13 tests)
: Test HTML sanitization function.

- `test_removes_mac_addresses`: Test that MAC addresses are sanitized.
- `test_removes_serial_numbers`: Test that serial numbers are sanitized.
- `test_removes_account_ids`: Test that account/subscriber IDs are sanitized.
- `test_removes_private_ips`: Test that private IP addresses are sanitized.
- `test_preserves_common_modem_ips`: Test that common modem IPs are preserved for debugging.
- `test_removes_passwords`: Test that passwords and passphrases are sanitized.
- `test_removes_password_form_values`: Test that password input field values are sanitized.
- `test_removes_session_tokens`: Test that session tokens and auth tokens are sanitized.
- `test_preserves_signal_data`: Test that signal quality data is preserved for debugging.
- `test_preserves_channel_ids`: Test that channel IDs and counts are preserved.
- `test_handles_multiple_macs`: Test sanitization of multiple MAC addresses in same HTML.
- `test_handles_empty_string`: Test that empty string is handled gracefully.
- `test_handles_no_sensitive_data`: Test HTML with no sensitive data passes through mostly unchanged.

**TestSanitizeLogMessage** (3 tests)
: Test log message sanitization function.

- `test_removes_credentials`: Test that credentials are removed from log messages.
- `test_removes_file_paths`: Test that file paths are sanitized.
- `test_removes_private_ips`: Test that private IPs are removed but common modem IPs preserved.

**TestGetHnapAuthAttempt** (7 tests)
: Test _get_hnap_auth_attempt helper function.

- `test_returns_note_when_no_scraper`: Test returns explanatory note when scraper not available.
- `test_returns_note_when_no_auth_handler`: Test returns explanatory note when auth handler not available.
- `test_returns_note_when_no_json_builder`: Test returns explanatory note when no JSON builder (not HNAP modem).
- `test_returns_note_when_no_auth_attempt`: Test returns explanatory note when no auth attempt recorded.
- `test_returns_auth_attempt_data`: Test returns auth attempt data when available.
- `test_sanitizes_sensitive_data`: Test that auth attempt data is sanitized.
- `test_handles_exception_gracefully`: Test that exceptions are handled gracefully.

**TestGetAuthDiscoveryInfo** (7 tests)
: Test _get_auth_discovery_info helper function (v3.12.0+).

- `test_returns_minimal_info_when_no_strategy`: Test returns minimal info when no auth strategy configured.
- `test_strategy_descriptions`: Test strategy descriptions are correct for each auth type.
- `test_returns_form_config_for_form_auth`: Test returns form config for form-based auth.
- `test_form_plain_encoding_descriptions`: Test form_plain description reflects password_encoding from form_config.
- `test_includes_failure_info_when_discovery_failed`: Test includes failure info when discovery failed but modem works.
- `test_includes_captured_response_for_unknown_pattern`: Test includes captured response for unknown auth patterns.
- `test_sanitizes_captured_response_html`: Test that captured response HTML is sanitized.

**TestCreateLogEntry** (4 tests)
: Test _create_log_entry pure function.

- `test_creates_entry_with_all_fields`: Test creates log entry with timestamp, level, logger, message.
- `test_strips_component_prefix_from_logger`: Test that component prefix is stripped from logger name.
- `test_sanitizes_message`: Test that sensitive info in message is sanitized.
- `test_accepts_string_timestamp`: Test accepts ISO timestamp string.

**TestExtractAuthMethod** (4 tests)
: Test _extract_auth_method pure function.

- `test_returns_none_for_empty_patterns`: Test returns 'none' when url_patterns is empty.
- `test_extracts_auth_method_from_first_pattern`: Test extracts auth_method from first pattern.
- `test_returns_none_when_no_auth_method_key`: Test returns 'none' when pattern has no auth_method.
- `test_handles_various_auth_types`: Test handles various auth method types.

**TestGetDetectionMethod** (5 tests)
: Test _get_detection_method pure function.

- `test_returns_stored_method_when_present`: Test returns stored detection_method when available.
- `test_infers_auto_detected_from_matching_choice`: Test infers auto_detected when modem_choice matches parser_name.
- `test_infers_user_selected_when_no_match`: Test infers user_selected when modem_choice differs.
- `test_returns_user_selected_when_no_last_detection`: Test returns user_selected when no last_detection timestamp.
- `test_defaults_to_auto_for_empty_data`: Test handles empty data dictionary.

**TestParseLegacyRecord** (5 tests)
: Test _parse_legacy_record pure function.

- `test_parses_record_with_name_and_message_attrs`: Test parses SimpleEntry-like records.
- `test_parses_record_with_get_message_method`: Test parses standard LogRecord objects.
- `test_parses_legacy_tuple_format`: Test parses legacy tuple format.
- `test_returns_none_for_non_cable_modem_logs`: Test returns None for logs from other components.
- `test_handles_integer_level`: Test converts integer log level to string.

**TestGetLogsFromFile** (4 tests)
: Test _get_logs_from_file with real files.

- `test_returns_info_when_file_not_found`: Test returns info entry when log file doesn't exist.
- `test_parses_cable_modem_monitor_logs`: Test parses cable_modem_monitor log entries from file.
- `test_returns_empty_when_no_matching_logs`: Test returns empty list when no cable_modem_monitor logs.
- `test_sanitizes_sensitive_info_in_logs`: Test sanitizes passwords and IPs in log messages.

### test_entity_migration.py

Tests for entity migration utilities.

**TestMigrateDocsis30Entities** (0 tests)
: Tests for async_migrate_docsis30_entities function.


**TestMigrateRecorderHistory** (7 tests)
: Tests for _migrate_recorder_history_sync function.

- `test_migrates_downstream_entities`: Test migration of downstream entity history.
- `test_migrates_upstream_entities`: Test migration of upstream entity history.
- `test_merges_when_new_entity_exists`: Test that old states are merged when new entity already exists.
- `test_returns_zero_when_no_old_entities`: Test that 0 is returned when there are no old entities.
- `test_handles_missing_database_gracefully`: Test that missing database is handled gracefully.
- `test_migrates_all_metric_types`: Test migration of all metric types.
- `test_skips_already_migrated_entities`: Test that already-migrated entities are skipped.

**TestMigrateStatisticsMeta** (4 tests)
: Tests for statistics_meta migration.

- `test_migrates_statistics_downstream`: Test migration of downstream statistics.
- `test_migrates_statistics_upstream`: Test migration of upstream statistics.
- `test_merges_statistics_when_new_exists`: Test that old statistics are merged when new statistic already exists.
- `test_migrates_both_states_and_statistics`: Test that both states and statistics are migrated together.

### test_protocol_caching.py

Tests for protocol caching optimization.

**TestProtocolCaching** (7 tests)
: Test protocol caching from working URL.

- `test_protocol_from_https_cached_url`: Test that HTTPS protocol is extracted from cached URL.
- `test_protocol_from_http_cached_url`: Test that HTTP protocol is extracted from cached URL.
- `test_no_cached_url_defaults_to_https`: Test that HTTPS is default when no cached URL.
- `test_explicit_protocol_in_host_overrides_cache`: Test that explicit protocol in host overrides cached URL.
- `test_cached_url_without_protocol_ignored`: Test that cached URL without protocol is ignored.
- `test_cached_url_with_path_only_uses_protocol`: Test that protocol is extracted even with different path.
- `test_with_different_hosts`: Test that protocol caching only applies to same host.

**TestProtocolDiscoveryBehavior** (2 tests)
: Test protocol discovery behavior with and without cache.

- `test_protocols_to_try_with_https_base`: Test that both protocols are tried when base is HTTPS.
- `test_protocols_to_try_with_http_cache`: Test that only HTTP is tried when cached URL is HTTP.

**TestSSLVerification** (3 tests)
: Test SSL verification settings.

- `test_false_by_default`: Test that SSL verification is disabled by default.
- `test_can_be_enabled`: Test that SSL verification can be enabled.
- `test_passed_through_requests`: Test that verify parameter is passed to requests.

### test_sensor.py

Tests for Cable Modem Monitor sensors.

**TestSensorImports** (1 tests)
: Test sensor imports.

- `test_sensor_entity_count`: Test minimum number of base sensors created.

**TestStatusSensor** (2 tests)
: Test unified status sensor.

- `test_status_operational`: Test status sensor with operational status.
- `test_status_unresponsive`: Test status sensor with unresponsive status.

**TestErrorSensors** (4 tests)
: Test error tracking sensors.

- `test_corrected_errors_sensor`: Test corrected errors sensor.
- `test_uncorrected_errors_sensor`: Test uncorrected errors sensor.
- `test_zero_errors`: Test sensors with zero errors.
- `test_unavailable_errors`: Test sensors return None when data unavailable (no channels).

**TestChannelCountSensors** (2 tests)
: Test channel count sensors.

- `test_downstream_count`: Test downstream (DS) channel count sensor.
- `test_upstream_count`: Test upstream (US) channel count sensor.

**TestSystemInfoSensors** (2 tests)
: Test system information sensors.

- `test_software_version`: Test software version sensor.
- `test_system_uptime`: Test system uptime sensor.

**TestPerChannelSensors** (2 tests)
: Test per-channel sensor creation.

- `test_downstream_channel_sensor_count`: Test that correct number of downstream sensors are created.
- `test_upstream_channel_sensor_count`: Test that correct number of upstream sensors are created.

**TestSensorAttributes** (2 tests)
: Test sensor attributes and metadata.

- `test_sensor_has_unique_id`: Test that sensors have unique IDs.
- `test_sensor_has_device_info`: Test that sensors have device info.

**TestSensorDataHandling** (2 tests)
: Test how sensors handle missing or invalid data.

- `test_missing_data_keys`: Test sensors with missing data keys.
- `test_none_values`: Test sensors with None values.

**TestEntityNaming** (1 tests)
: Test entity naming with different prefix configurations.

- `test_sensor_naming`: Test sensor naming has correct display names and unique IDs.

**TestLastBootTimeSensor** (4 tests)
: Test last boot time sensor functionality.

- `test_calculation`: Test last boot time calculation from uptime.
- `test_unknown_uptime`: Test last boot time with unknown uptime.
- `test_missing_uptime`: Test last boot time with missing uptime data.
- `test_sensor_attributes`: Test last boot time sensor attributes.

**TestLanStatsSensors** (4 tests)
: Test LAN statistics sensors.

- `test_lan_received_bytes_sensor`: Test LAN received bytes sensor.
- `test_lan_received_packets_sensor`: Test LAN received packets sensor.
- `test_lan_transmitted_bytes_sensor`: Test LAN transmitted bytes sensor.
- `test_lan_transmitted_packets_sensor`: Test LAN transmitted packets sensor.

**TestCapabilityBasedSensorCreation** (6 tests)
: Test that sensors are conditionally created based on parser capabilities.

- `test_has_capability_returns_true_when_present`: Test _has_capability returns True when capability is in list.
- `test_has_capability_returns_false_when_missing`: Test _has_capability returns False when capability is not in list.
- `test_has_capability_handles_missing_key`: Test _has_capability returns False when _parser_capabilities key is missing.
- `test_uptime_sensors_created_when_capability_present`: Test uptime/last boot sensors ARE created when SYSTEM_UPTIME capability is present.
- `test_uptime_sensors_not_created_when_capability_missing`: Test uptime/last boot sensors are NOT created when SYSTEM_UPTIME capability is missing.
- `test_base_sensors_always_created`: Test that base sensors (errors, channel counts, version) are always created.

**TestFallbackModeSensorCreation** (1 tests)
: Test that sensors are conditionally created based on fallback mode.

- `test_status_shows_operational_in_fallback`: Test that unified status sensor shows 'Operational' in fallback mode.

**TestChannelTypeNormalization** (0 tests)
: Test that channel_type is normalized to lowercase for sensor creation.


**TestConditionalSensorCreation** (0 tests)
: Test that optional sensors are only created when data is present.


**TestStatusSensorBranches** (1 tests)
: Table-driven tests for ModemStatusSensor.native_value status branches.

- `test_status_branches`: Test all status sensor branches via table-driven cases.

**TestDocsisStatusDerivation** (1 tests)
: Table-driven tests for ModemStatusSensor._derive_docsis_status.

- `test_derive_docsis_status`: Test DOCSIS status derivation via table-driven cases.

**TestSensorBaseAvailability** (1 tests)
: Table-driven tests for ModemSensorBase.available property.

- `test_base_availability`: Test base sensor availability via table-driven cases.

**TestLatencySensors** (2 tests)
: Table-driven tests for latency sensors.

- `test_ping_latency_sensor`: Test ping latency sensor via table-driven cases.
- `test_http_latency_sensor`: Test HTTP latency sensor via table-driven cases.

**TestLanStatsSensorsBranches** (1 tests)
: Table-driven tests for LAN stats error/drop sensors.

- `test_lan_stats_sensors`: Test LAN stats sensors via table-driven cases.

**TestModemInfoSensor** (3 tests)
: Tests for ModemInfoSensor.

- `test_native_value`: Test ModemInfoSensor returns detected modem as state.
- `test_extra_state_attributes_full`: Test ModemInfoSensor extra attributes with all data present.
- `test_extra_state_attributes_minimal`: Test ModemInfoSensor extra attributes with minimal data.

**TestStatusSensorAvailable** (2 tests)
: Tests for ModemStatusSensor.available property.

- `test_available_true`: Test status sensor available when coordinator update succeeded.
- `test_available_false`: Test status sensor unavailable when coordinator update failed.

**TestStatusSensorExtraAttributes** (1 tests)
: Tests for ModemStatusSensor.extra_state_attributes.

- `test_extra_state_attributes`: Test ModemStatusSensor extra attributes.

**TestChannelSensorExtraAttributes** (8 tests)
: Tests for channel sensor extra_state_attributes.

- `test_downstream_power_extra_attrs`: Test downstream power sensor extra attributes.
- `test_downstream_snr_extra_attrs`: Test downstream SNR sensor extra attributes.
- `test_downstream_frequency_extra_attrs`: Test downstream frequency sensor extra attributes.
- `test_downstream_corrected_extra_attrs`: Test downstream corrected sensor extra attributes.
- `test_downstream_uncorrected_extra_attrs`: Test downstream uncorrected sensor extra attributes.
- `test_upstream_power_extra_attrs`: Test upstream power sensor extra attributes.
- `test_upstream_frequency_extra_attrs`: Test upstream frequency sensor extra attributes.
- `test_channel_not_found_returns_empty_attrs`: Test extra attributes return empty dict when channel not found.

**TestDeviceInfoConstruction** (3 tests)
: Tests for ModemSensorBase device_info construction.

- `test_device_info_with_actual_model`: Test device info uses actual_model when available.
- `test_device_info_strips_manufacturer_prefix`: Test device info strips manufacturer prefix from model.
- `test_device_info_fallback_to_detected_modem`: Test device info falls back to detected_modem when no actual_model.

**TestChannelSensorNativeValueEdgeCases** (7 tests)
: Tests for channel sensor native_value when channel not found.

- `test_downstream_power_not_found`: Test downstream power sensor returns None when channel not found.
- `test_downstream_snr_not_found`: Test downstream SNR sensor returns None when channel not found.
- `test_downstream_frequency_not_found`: Test downstream frequency sensor returns None when channel not found.
- `test_downstream_corrected_not_found`: Test downstream corrected sensor returns None when channel not found.
- `test_downstream_uncorrected_not_found`: Test downstream uncorrected sensor returns None when channel not found.
- `test_upstream_power_not_found`: Test upstream power sensor returns None when channel not found.
- `test_upstream_frequency_not_found`: Test upstream frequency sensor returns None when channel not found.

**TestLanStatsSensorMissingInterface** (1 tests)
: Tests for LAN stats sensors when interface is missing.

- `test_lan_stats_interface_not_found`: Test LAN stats sensor returns None when interface not found.

**TestLatencySensorDataNone** (2 tests)
: Tests for latency sensors with coordinator.data=None.

- `test_ping_latency_data_none`: Test ping latency sensor unavailable when coordinator.data is None.
- `test_http_latency_data_none`: Test HTTP latency sensor unavailable when coordinator.data is None.

**TestCreateSystemSensorsCapabilities** (2 tests)
: Tests for _create_system_sensors capability checks.

- `test_software_version_sensor_created_with_capability`: Test software version sensor IS created when capability present.
- `test_software_version_sensor_not_created_without_capability`: Test software version sensor NOT created when capability missing.

### test_version_and_startup.py

Tests for version logging and startup optimizations.

**TestVersionLogging** (2 tests)
: Test version logging on startup.

- `test_version_constant_format`: Test that VERSION constant is in correct format.
- `test_current_version`: Test that version is the correct current version.

**TestParserSelectionOptimization** (0 tests)
: Test parser selection optimization during startup.


**TestProtocolOptimizationIntegration** (0 tests)
: Test protocol optimization integration in startup.


---
*Generated by `scripts/generate_test_docs.py`*
