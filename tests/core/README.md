# Core Module Tests

> Auto-generated from test files. Do not edit manually.

Unit tests for core functionality including signal analysis, health monitoring, HNAP builders, authentication, and discovery helpers.

**Total Tests:** 382

## Test Files

| File | Tests | Description |
|------|-------|-------------|
| [test_auth_detection.py](test_auth_detection.py) | 10 | Tests for auth/detection.py - login page detection. |
| [test_auth_discovery.py](test_auth_discovery.py) | 49 | Tests for Authentication Discovery. |
| [test_auth_handler.py](test_auth_handler.py) | 29 | Tests for the AuthHandler class. |
| [test_authentication.py](test_authentication.py) | 43 | Tests for Authentication Strategies. |
| [test_base_parser.py](test_base_parser.py) | 19 | Tests for core/base_parser.py. |
| [test_discovery_helpers.py](test_discovery_helpers.py) | 55 | Tests for core/discovery_helpers.py. |
| [test_form_ajax_auth.py](test_form_ajax_auth.py) | 17 | Tests for FormAjaxAuthStrategy. |
| [test_form_dynamic_auth.py](test_form_dynamic_auth.py) | 9 | Tests for FormDynamicAuthStrategy. |
| [test_health_monitor.py](test_health_monitor.py) | 27 | Tests for Modem Health Monitor. |
| [test_hnap_builder.py](test_hnap_builder.py) | 25 | Tests for HNAP Request Builder. |
| [test_hnap_json_builder.py](test_hnap_json_builder.py) | 50 | Tests for JSON-based HNAP Request Builder with challenge-... |
| [test_log_buffer.py](test_log_buffer.py) | 6 | Tests for the log buffer module. |
| [test_network.py](test_network.py) | 0 | Tests for core/network.py. |
| [test_parser_utils.py](test_parser_utils.py) | 13 | Tests for core/parser_utils.py. |
| [test_signal_analyzer.py](test_signal_analyzer.py) | 22 | Tests for Signal Quality Analyzer. |
| [test_url_token_session_auth.py](test_url_token_session_auth.py) | 8 | Tests for UrlTokenSessionStrategy. |

## Test Details

### test_auth_detection.py

Tests for auth/detection.py - login page detection.

Tests:
- has_password_field(): Lenient string search
- has_login_form(): Strict DOM-based check
- is_login_page(): Smart detection using aggregated hints from all modems

**TestHasPasswordField** (1 tests)
: Test lenient password field detection.

- `test_has_password_field`: Table-driven test for lenient password detection.

**TestHasLoginForm** (1 tests)
: Test strict login form detection.

- `test_has_login_form`: Table-driven test for strict form detection.

**TestRealWorldSamples** (4 tests)
: Test with realistic modem login page HTML.

- `test_netgear_cm_login`: Netgear CM login page pattern.
- `test_arris_sb_login`: ARRIS Surfboard login page pattern.
- `test_motorola_status_page`: Motorola modem status page (not a login page).
- `test_js_template_with_password`: JavaScript template containing password field string (edge case).

**TestIsLoginPage** (4 tests)
: Test is_login_page() which is an alias for has_password_field().

- `test_login_page_with_password_field`: Page with password field is detected as login page.
- `test_data_page_without_password_field`: Page without password field is NOT a login page.
- `test_empty_and_none`: Empty string and None return False.
- `test_is_alias_for_has_password_field`: is_login_page() returns same result as has_password_field().

### test_auth_discovery.py

Tests for Authentication Discovery.

**TestStripPatternKey** (1 tests)
: Tests for _strip_pattern_key helper.

- `test_strip_pattern_key`: Table-driven test for _strip_pattern_key.

**TestGetAttrStr** (1 tests)
: Tests for _get_attr_str helper.

- `test_get_attr_str`: Table-driven test for _get_attr_str.

**TestDiscoveredFormConfig** (3 tests)
: Test DiscoveredFormConfig dataclass.

- `test_to_dict`: Test serialization to dict.
- `test_from_dict`: Test deserialization from dict.
- `test_roundtrip`: Test serialization and deserialization roundtrip.

**TestAuthDiscoveryNoAuth** (2 tests)
: Test detection of no-auth modems.

- `test_200_with_parseable_data_returns_no_auth`: Test that 200 with parseable data returns NO_AUTH.
- `test_200_with_parseable_data_ignores_credentials`: Test that 200 with parseable data ignores provided credentials.

**TestAuthDiscoveryBasicAuth** (3 tests)
: Test detection of HTTP Basic auth.

- `test_401_triggers_basic_auth`: Test that 401 response triggers Basic Auth.
- `test_401_without_credentials_returns_error`: Test that 401 without credentials returns error.
- `test_401_with_invalid_credentials_returns_error`: Test that 401 after auth retry returns invalid credentials error.

**TestAuthDiscoveryFormAuth** (2 tests)
: Test detection of form-based auth.

- `test_login_form_detected`: Test that login form is detected.
- `test_login_form_without_credentials_returns_error`: Test that login form without credentials returns error.

**TestFormIntrospection** (7 tests)
: Test form field detection - table-driven.

- `test_username_field_detection`: Table-driven test for username field detection.
- `test_form_attributes`: Table-driven test for form action and method extraction.
- `test_invalid_forms_return_none`: Table-driven test for forms that should return None.
- `test_find_password_by_type`: Test finding password field by type='password'.
- `test_find_password_by_type_case_insensitive`: Test finding password field with type='Password' (capital P).
- `test_hidden_fields_captured`: Test that hidden fields are captured from form.
- `test_parser_hints_override_detection`: Test that parser hints override generic detection.

**TestAuthDiscoveryRedirect** (3 tests)
: Test redirect handling.

- `test_meta_refresh_redirect_followed`: Test that meta refresh redirect is followed.
- `test_302_redirect_followed`: Test that HTTP 302 redirect is followed.
- `test_redirect_loop_protection`: Test that redirect loops are detected and stopped.

**TestAuthDiscoveryHNAP** (2 tests)
: Test HNAP detection.

- `test_hnap_detected_by_soapaction_script`: Test HNAP detection via SOAPAction.js script.
- `test_hnap_detected_by_hnap_script`: Test HNAP detection via HNAP in script path.

**TestAuthDiscoveryJSAuth** (2 tests)
: Test JavaScript-based auth detection.

- `test_js_form_with_parser_hint`: Test JS form detection with parser hint.
- `test_js_form_without_hint_returns_error`: Test JS form without parser hint returns error.

**TestAuthDiscoveryUnknown** (1 tests)
: Test unknown pattern handling.

- `test_unknown_pattern_captured`: Test that unknown patterns are captured for debugging.

**TestAuthDiscoveryConnectionErrors** (1 tests)
: Test connection error handling.

- `test_connection_error_returns_failure`: Test that connection errors return failure.

**TestAuthDiscoveryURLResolution** (2 tests)
: Test URL resolution.

- `test_resolve_relative_url`: Test relative URL resolution.
- `test_resolve_absolute_url`: Test absolute URL passthrough.

**TestIsLoginForm** (1 tests)
: Test login form detection - table-driven.

- `test_is_login_form`: Table-driven test for login form detection.

**TestIsJsForm** (1 tests)
: Test JavaScript form detection - table-driven.

- `test_is_js_form`: Table-driven test for JS form detection.

**TestIsRedirect** (1 tests)
: Test redirect detection - table-driven.

- `test_is_redirect`: Table-driven test for redirect detection.

**TestVerificationUrl** (4 tests)
: Test verification URL for login success checking.

- `test_discover_accepts_verification_url_parameter`: Test that discover() accepts verification_url parameter.
- `test_discovered_form_config_has_success_redirect_field`: Test DiscoveredFormConfig includes success_redirect field.
- `test_discovered_form_config_success_redirect_defaults_to_none`: Test success_redirect defaults to None when not provided.
- `test_form_auth_uses_success_redirect_for_verification`: Test that form auth uses success_redirect URL for verification.

**TestCombinedCredentialForm** (9 tests)
: Test SB6190-style combined credential form detection and handling.

- `test_is_combined_credential_form_detects_sb6190_pattern`: Test detection of SB6190-style combined credential form.
- `test_is_combined_credential_form_rejects_standard_form`: Test that standard login forms are not detected as combined.
- `test_is_combined_credential_form_requires_adv_pwd_cgi`: Test that action must contain adv_pwd_cgi.
- `test_is_combined_credential_form_requires_nonce`: Test that ar_nonce field is required.
- `test_is_combined_credential_form_requires_arguments`: Test that arguments field is required.
- `test_is_combined_credential_form_accepts_visible_password_field`: Test that forms with visible password field are still detected as combined.
- `test_parse_combined_form_extracts_config`: Test parsing combined credential form.
- `test_combined_form_auth_encodes_credentials`: Test combined credential form encodes credentials correctly.
- `test_combined_form_returns_form_plain_strategy`: Test that combined form auth returns FORM_PLAIN strategy with base64 encoding.

**TestDiscoveredFormConfigCombinedMode** (3 tests)
: Test DiscoveredFormConfig with combined credential fields.

- `test_to_dict_includes_combined_fields`: Test serialization includes combined credential fields.
- `test_from_dict_restores_combined_fields`: Test deserialization restores combined credential fields.
- `test_roundtrip_with_combined_fields`: Test serialization roundtrip with combined fields.

### test_auth_handler.py

Tests for the AuthHandler class.

This tests the runtime authentication handler that applies stored
authentication strategies during polling.

**TestAuthHandlerInit** (7 tests)
: Test AuthHandler initialization.

- `test_init_with_string_strategy`: Test initialization with string strategy.
- `test_init_with_enum_strategy`: Test initialization with enum strategy.
- `test_init_with_none_strategy`: Test initialization with None strategy.
- `test_init_with_unknown_string`: Test initialization with unknown string defaults to UNKNOWN.
- `test_init_with_uppercase_string`: Test initialization with uppercase string (case-insensitive matching).
- `test_init_with_legacy_form_base64`: Test that legacy form_base64 strategy maps to form_plain.
- `test_init_with_form_config`: Test initialization with form config.

**TestAuthHandlerNoAuth** (1 tests)
: Test NO_AUTH strategy.

- `test_no_auth_succeeds_without_credentials`: Test NO_AUTH strategy succeeds.

**TestAuthHandlerBasicAuth** (4 tests)
: Test BASIC_HTTP strategy.

- `test_basic_auth_sets_session_auth`: Test Basic Auth sets session.auth but does NOT return HTML.
- `test_basic_auth_fails_without_credentials`: Test Basic Auth fails without credentials.
- `test_basic_auth_fails_on_401`: Test Basic Auth fails on 401 response.
- `test_basic_auth_handles_exception`: Test Basic Auth handles connection exception.

**TestAuthHandlerFormAuth** (8 tests)
: Test FORM_PLAIN strategy.

- `test_form_auth_submits_form`: Test form auth submits form data.
- `test_form_auth_fails_without_credentials`: Test form auth fails without credentials.
- `test_form_auth_fails_without_form_config`: Test form auth fails without form config.
- `test_form_auth_detects_login_page_failure`: Test form auth detects when base URL still shows login page after form submission.
- `test_form_auth_succeeds_when_form_action_has_password_but_base_url_does_not`: Test form auth succeeds when form action response has password field but base URL doesn't.
- `test_form_auth_uses_get_method`: Test form auth uses GET when method is GET.
- `test_form_auth_base64_encodes_password`: Test FORM_PLAIN strategy with password_encoding=base64 encodes the password.
- `test_form_auth_combined_credentials`: Test FORM_PLAIN strategy with combined credentials (SB6190-style).

**TestAuthHandlerHNAP** (2 tests)
: Test HNAP_SESSION strategy.

- `test_hnap_auth_no_credentials`: Test HNAP strategy returns False without credentials.
- `test_hnap_auth_with_credentials`: Test HNAP strategy authenticates using HNAPJsonRequestBuilder.

**TestAuthHandlerURLToken** (2 tests)
: Test URL_TOKEN_SESSION strategy.

- `test_url_token_auth_no_credentials`: Test URL token strategy skips auth without credentials.
- `test_url_token_auth_with_credentials`: Test URL token strategy authenticates with credentials.

**TestAuthHandlerUnknown** (1 tests)
: Test UNKNOWN strategy.

- `test_unknown_returns_true_for_fallback`: Test unknown strategy returns True to allow fallback.

**TestFallbackStrategies** (4 tests)
: Test try-until-success fallback strategies (v3.12+).

- `test_init_with_fallback_strategies`: Test initialization with fallback strategies list.
- `test_fallback_tried_on_primary_failure`: Test that fallback strategy is tried when primary fails.
- `test_fallback_updates_strategy_on_success`: Test that successful fallback updates the handler's strategy.
- `test_all_strategies_fail`: Test that failure is returned when all strategies fail.

### test_authentication.py

Tests for Authentication Strategies.

**TestNoAuthStrategy** (2 tests)
: Test NoAuthStrategy.

- `test_no_auth_always_succeeds`: Test that NoAuthStrategy always returns success.
- `test_no_auth_with_credentials`: Test NoAuthStrategy ignores credentials.

**TestBasicHttpAuthStrategy** (6 tests)
: Test BasicHttpAuthStrategy.

- `test_basic_auth_sets_session_auth`: Test that Basic Auth sets credentials on session and verifies.
- `test_basic_auth_without_credentials`: Test Basic Auth fails without credentials.
- `test_basic_auth_missing_username`: Test Basic Auth fails with missing username.
- `test_basic_auth_missing_password`: Test Basic Auth fails with missing password.
- `test_basic_auth_401_returns_failure`: Test that 401 response returns failure and clears auth.
- `test_basic_auth_connection_error`: Test connection error returns failure.

**TestFormPlainAuthStrategy** (5 tests)
: Test FormPlainAuthStrategy.

- `test_form_auth_success`: Test successful form authentication.
- `test_form_auth_without_credentials`: Test form auth fails without credentials.
- `test_form_auth_wrong_config_type`: Test form auth with wrong config type.
- `test_form_auth_large_response_indicator`: Test form auth with size-based success indicator.
- `test_form_auth_no_indicator_returns_html_when_not_login_page`: Test form auth returns HTML when no success_indicator and response is not a login page.

**TestRedirectFormAuthStrategy** (9 tests)
: Test RedirectFormAuthStrategy.

- `test_redirect_form_success`: Test successful redirect form authentication.
- `test_redirect_form_without_credentials`: Test redirect form requires credentials.
- `test_redirect_form_wrong_config_type`: Test redirect form with wrong config type.
- `test_redirect_form_login_http_error`: Test redirect form handles HTTP error.
- `test_redirect_form_wrong_redirect`: Test redirect form fails on wrong redirect.
- `test_redirect_form_cross_host_security`: Test redirect form rejects cross-host redirects.
- `test_redirect_form_timeout_handling`: Test redirect form handles timeout.
- `test_redirect_form_connection_error`: Test redirect form handles connection error.
- `test_redirect_form_authenticated_page_error`: Test redirect form handles authenticated page fetch failure.

**TestHNAPSessionAuthStrategy** (9 tests)
: Test HNAPSessionAuthStrategy.

- `test_hnap_session_success`: Test successful HNAP session authentication.
- `test_hnap_session_without_credentials`: Test HNAP session requires credentials.
- `test_hnap_session_wrong_config_type`: Test HNAP session with wrong config type.
- `test_hnap_session_http_error`: Test HNAP session handles HTTP error.
- `test_hnap_session_timeout_indicator`: Test HNAP session detects timeout indicator.
- `test_hnap_session_json_error_response`: Test HNAP session detects JSON error response.
- `test_hnap_session_timeout_handling`: Test HNAP session handles timeout.
- `test_hnap_session_connection_error`: Test HNAP session handles connection error.
- `test_hnap_session_builds_correct_envelope`: Test HNAP session builds correct SOAP envelope.

**TestAuthStrategyFactoryPattern** (1 tests)
: Test that auth strategies can be instantiated and used polymorphically.

- `test_all_strategies_have_login_method`: Test that all strategies implement login method.

**TestUrlTokenSessionStrategy** (7 tests)
: Test UrlTokenSessionStrategy (URL-based token auth pattern).

- `test_no_credentials_skips_auth`: Test that missing credentials skips auth.
- `test_empty_credentials_skips_auth`: Test that empty credentials skips auth.
- `test_login_url_contains_base64_token`: Test that login URL contains base64-encoded credentials.
- `test_login_includes_authorization_header`: Test that login request includes Authorization header.
- `test_success_when_data_in_login_response`: Test success when login response contains channel data.
- `test_fetches_data_page_with_session_token`: Test that data page is fetched with session token from cookie.
- `test_401_returns_failure`: Test that 401 response returns failure.

**TestGetCookieSafe** (4 tests)
: Test get_cookie_safe utility function.

- `test_single_cookie_returns_value`: Test normal case with single cookie.
- `test_duplicate_cookies_different_paths_returns_root`: Test that duplicate cookies with different paths returns root path value.
- `test_missing_cookie_returns_none`: Test that missing cookie returns None.
- `test_three_or_more_cookies_returns_root_path`: Test that 3+ cookies with same name returns root path value.

### test_base_parser.py

Tests for core/base_parser.py.

**TestParserStatus** (2 tests)
: Tests for ParserStatus enum.

- `test_status_values`: Test all status values exist.
- `test_status_is_string`: Test status can be used as string.

**TestModemCapability** (2 tests)
: Tests for ModemCapability enum.

- `test_capability_values`: Test all capability values exist.
- `test_capability_is_string`: Test capability value can be used as string.

**TestModemParserHasCapability** (2 tests)
: Tests for ModemParser.has_capability method.

- `test_has_capability_returns_true_when_present`: Test has_capability returns True for declared capabilities.
- `test_has_capability_returns_false_when_absent`: Test has_capability returns False for undeclared capabilities.

**TestModemParserGetFixturesUrl** (3 tests)
: Tests for ModemParser.get_fixtures_url method.

- `test_returns_url_when_fixtures_exist`: Test returns GitHub URL when adapter has fixtures path.
- `test_returns_none_when_no_adapter`: Test returns None when no adapter found.
- `test_returns_none_when_no_fixtures_path`: Test returns None when adapter has no fixtures path.

**TestModemParserGetDeviceMetadata** (3 tests)
: Tests for ModemParser.get_device_metadata method.

- `test_returns_metadata_with_adapter`: Test returns full metadata when adapter exists.
- `test_returns_fallback_metadata_without_adapter`: Test returns fallback metadata when no adapter exists.
- `test_includes_release_date_and_end_of_life`: Test includes release_date and end_of_life when set.

**TestModemParserGetActualModel** (1 tests)
: Tests for ModemParser.get_actual_model method.

- `test_get_actual_model`: Test get_actual_model extracts model from various data formats.

**TestModemParserParseResources** (2 tests)
: Tests for ModemParser.parse_resources abstract method.

- `test_parse_resources_is_abstract`: Test parse_resources must be implemented by subclasses.
- `test_parse_calls_parse_resources`: Test parse() convenience method calls parse_resources().

**TestModemParserInitSubclass** (4 tests)
: Tests for ModemParser.__init_subclass__ auto-population.

- `test_handles_adapter_exception_gracefully`: Test __init_subclass__ handles exceptions and uses defaults.
- `test_populates_from_adapter_when_available`: Test __init_subclass__ populates attributes from adapter.
- `test_filters_invalid_capabilities`: Test __init_subclass__ filters out invalid capability values.
- `test_populates_end_of_life_when_available`: Test __init_subclass__ populates end_of_life when adapter provides it.

**TestParser** (0 tests)


**TestParser** (0 tests)


**TestParser** (0 tests)


**TestParser** (0 tests)


**TestParser** (0 tests)


**TestParser** (0 tests)


**TestParser** (0 tests)


**TestParser** (0 tests)


**TestParser** (0 tests)


### test_discovery_helpers.py

Tests for core/discovery_helpers.py.

**TestHintMatch** (1 tests)
: Tests for HintMatch dataclass.

- `test_hint_match_creation`: Test creating a HintMatch.

**TestHintMatcherMatchPreAuth** (3 tests)
: Tests for HintMatcher.match_pre_auth method.

- `test_match_pre_auth`: Test match_pre_auth with various inputs.
- `test_match_pre_auth_returns_empty_when_no_index`: Test match_pre_auth returns empty list when index is None.
- `test_match_login_markers_alias`: Test backwards compatibility alias.

**TestHintMatcherMatchPostAuth** (3 tests)
: Tests for HintMatcher.match_post_auth method.

- `test_match_post_auth`: Test match_post_auth with various inputs.
- `test_match_post_auth_returns_empty_when_no_index`: Test match_post_auth returns empty when index is None.
- `test_match_model_strings_alias`: Test backwards compatibility alias.

**TestHintMatcherGetPageHint** (2 tests)
: Tests for HintMatcher.get_page_hint method.

- `test_get_page_hint`: Test get_page_hint with various inputs.
- `test_get_page_hint_returns_none_when_no_index`: Test get_page_hint returns None when index is None.

**TestHintMatcherGetAllModems** (2 tests)
: Tests for HintMatcher.get_all_modems method.

- `test_get_all_modems`: Test get_all_modems returns all entries.
- `test_get_all_modems_returns_empty_when_no_index`: Test get_all_modems returns empty when index is None.

**TestHintMatcherSingleton** (3 tests)
: Tests for HintMatcher singleton pattern.

- `test_get_instance_returns_singleton`: Test get_instance returns same instance.
- `test_load_index_handles_file_not_found`: Test _load_index handles missing file gracefully.
- `test_load_index_handles_yaml_error`: Test _load_index handles YAML parse errors.

**TestParserHeuristicsGetLikelyParsers** (4 tests)
: Tests for ParserHeuristics.get_likely_parsers method.

- `test_returns_likely_parsers_first`: Test likely parsers are returned before unlikely ones.
- `test_returns_all_parsers_on_non_200_response`: Test returns all parsers when root page returns non-200.
- `test_returns_all_parsers_on_request_exception`: Test returns all parsers when request fails.
- `test_matches_model_numbers`: Test matching by model number in HTML.

**TestParserHeuristicsCheckAnonymousAccess** (4 tests)
: Tests for ParserHeuristics.check_anonymous_access method.

- `test_returns_html_for_public_url`: Test returns HTML when public URL accessible.
- `test_returns_none_when_no_url_patterns`: Test returns None when parser has no URL patterns.
- `test_returns_none_when_all_urls_require_auth`: Test returns None when all URLs require auth.
- `test_handles_request_exception`: Test handles request exceptions gracefully.

**TestParserHeuristicsCheckAuthenticatedAccess** (3 tests)
: Tests for ParserHeuristics.check_authenticated_access method.

- `test_returns_html_for_protected_url`: Test returns HTML when protected URL accessible with session.
- `test_skips_static_assets`: Test skips CSS, JS, and image files.
- `test_returns_none_when_no_url_patterns`: Test returns None when no URL patterns.

**TestDiscoveryCircuitBreaker** (7 tests)
: Tests for DiscoveryCircuitBreaker class.

- `test_circuit_breaker_attempts`: Test circuit breaker breaks at max attempts.
- `test_initial_state`: Test circuit breaker initial state.
- `test_should_continue_starts_timer_once`: Test should_continue only starts timer on first call.
- `test_timeout_breaks_circuit`: Test circuit breaks on timeout.
- `test_record_attempt_increments_counter`: Test record_attempt increments attempt counter.
- `test_get_stats`: Test get_stats returns correct information.
- `test_stays_broken_after_breaking`: Test circuit stays broken once broken.

**TestDetectionError** (4 tests)
: Tests for DetectionError base class.

- `test_creation_with_message`: Test creating DetectionError with message.
- `test_creation_with_diagnostics`: Test creating DetectionError with diagnostics.
- `test_get_user_message`: Test get_user_message returns string representation.
- `test_get_troubleshooting_steps_default`: Test base class returns empty troubleshooting steps.

**TestParserNotFoundError** (7 tests)
: Tests for ParserNotFoundError exception.

- `test_exception_creation_default`: Test creating ParserNotFoundError with defaults.
- `test_exception_with_modem_info`: Test creating ParserNotFoundError with modem info.
- `test_exception_with_attempted_parsers`: Test exception with list of attempted parsers.
- `test_exception_can_be_raised`: Test that exception can be raised and caught.
- `test_get_user_message`: Test user-friendly error message generation.
- `test_get_troubleshooting_steps`: Test troubleshooting steps are provided.
- `test_exception_with_full_context`: Test exception with complete context information.

**TestAuthenticationError** (3 tests)
: Tests for AuthenticationError exception.

- `test_default_message`: Test default error message.
- `test_custom_message`: Test custom error message.
- `test_troubleshooting_steps`: Test troubleshooting steps.

**TestSessionExpiredError** (3 tests)
: Tests for SessionExpiredError exception.

- `test_default_message`: Test default error message.
- `test_message_with_indicator`: Test message includes indicator.
- `test_troubleshooting_steps`: Test troubleshooting steps.

**TestModemConnectionError** (2 tests)
: Tests for ModemConnectionError exception.

- `test_creation`: Test creating ModemConnectionError.
- `test_troubleshooting_steps`: Test troubleshooting steps include common IPs.

**TestCircuitBreakerError** (3 tests)
: Tests for CircuitBreakerError exception.

- `test_creation_with_stats`: Test creating with stats dict.
- `test_get_user_message`: Test user-friendly message.
- `test_troubleshooting_steps`: Test troubleshooting steps.

**TestExceptionTroubleshootingSteps** (1 tests)
: Parameterized tests for exception troubleshooting steps.

- `test_troubleshooting_contains_expected_step`: Test each exception has expected troubleshooting content.

**TestParser** (0 tests)


### test_form_ajax_auth.py

Tests for FormAjaxAuthStrategy.

This tests the AJAX-based form authentication where login is handled via
JavaScript XMLHttpRequest instead of traditional form submission.

Auth flow:
1. Client generates random nonce (configurable length)
2. Credentials are formatted and base64-encoded:
   base64(urlencode("username={user}:password={pass}"))
3. POST to endpoint with arguments + nonce
4. Response is plain text: "Url:/path" (success) or "Error:msg" (failure)

**TestFormAjaxSuccessfulLogin** (5 tests)
: Test successful AJAX login flow.

- `test_successful_login_returns_ok`: Successful login returns AuthResult.ok with post-login HTML.
- `test_posts_to_correct_endpoint`: Verifies POST is sent to configured endpoint.
- `test_sends_correct_form_data_structure`: Verifies form data contains arguments and nonce fields.
- `test_credentials_are_properly_encoded`: Verifies credentials are base64(urlencode(format_string)).
- `test_sends_ajax_headers`: Verifies X-Requested-With header is sent (AJAX indicator).

**TestFormAjaxFailedLogin** (3 tests)
: Test AJAX login failure handling.

- `test_error_response_returns_failure`: Error: prefix in response returns AuthResult.fail.
- `test_unexpected_response_returns_failure`: Unexpected response format returns AuthResult.fail.
- `test_connection_error_returns_failure`: Connection error returns AuthResult.fail.

**TestFormAjaxCredentialValidation** (3 tests)
: Test credential validation.

- `test_missing_username_returns_failure`: Missing username returns AuthResult.fail.
- `test_missing_password_returns_failure`: Missing password returns AuthResult.fail.
- `test_wrong_config_type_returns_failure`: Wrong config type returns AuthResult.fail.

**TestFormAjaxNonceGeneration** (2 tests)
: Test nonce generation.

- `test_nonce_is_random`: Nonce is different on each call.
- `test_custom_nonce_length`: Custom nonce length is respected.

**TestFormAjaxCustomConfig** (4 tests)
: Test custom configuration options.

- `test_custom_endpoint`: Custom endpoint is used.
- `test_custom_field_names`: Custom field names are used.
- `test_custom_credential_format`: Custom credential format is used.
- `test_custom_response_prefixes`: Custom success/error prefixes are recognized.

### test_form_dynamic_auth.py

Tests for FormDynamicAuthStrategy.

This tests the dynamic form action extraction for modems where the login form
contains a dynamic parameter that changes per page load:
    <form action="/goform/Login?id=XXXXXXXXXX">

The static FormPlainAuthStrategy would use the configured action "/goform/Login",
missing the required ?id= parameter. FormDynamicAuthStrategy fetches the login
page first and extracts the actual action URL including any dynamic parameters.

**TestFormPlainStaticAction** (1 tests)
: Demonstrate that FormPlain uses static action, missing dynamic params.

- `test_form_plain_uses_static_action`: FormPlain submits to static action, missing the dynamic ?id=.

**TestFormDynamicExtractsAction** (3 tests)
: Test that FormDynamic correctly extracts and uses dynamic action URL.

- `test_form_dynamic_fetches_page_and_extracts_action`: FormDynamic fetches login page, extracts form action with ?id=.
- `test_form_dynamic_uses_css_selector`: FormDynamic uses the configured CSS selector to find the form.
- `test_form_dynamic_falls_back_to_first_form`: Without a selector, FormDynamic uses the first form.

**TestFormDynamicFallback** (3 tests)
: Test fallback behavior when dynamic extraction fails.

- `test_fallback_when_no_form_found`: Falls back to static action when no form element exists.
- `test_fallback_when_form_has_no_action`: Falls back to static action when form has no action attribute.
- `test_fallback_when_page_fetch_fails`: Falls back to static action when login page fetch fails.

**TestFormDynamicInheritance** (2 tests)
: Verify FormDynamic inherits form submission logic from FormPlain.

- `test_submits_correct_form_data`: FormDynamic submits username/password in correct fields.
- `test_missing_credentials_returns_failure`: FormDynamic inherits credential validation from FormPlain.

### test_health_monitor.py

Tests for Modem Health Monitor.

**TestHealthCheckResult** (9 tests)
: Test HealthCheckResult dataclass.

- `test_is_healthy_both_pass`: Test is_healthy when both ping and HTTP pass.
- `test_is_healthy_ping_only`: Test is_healthy when only ping passes.
- `test_is_healthy_http_only`: Test is_healthy when only HTTP passes.
- `test_is_healthy_both_fail`: Test is_healthy when both ping and HTTP fail.
- `test_status_responsive`: Test status when fully responsive.
- `test_status_degraded`: Test status when ping works but HTTP fails.
- `test_status_icmp_blocked`: Test status when HTTP works but ping fails.
- `test_status_unresponsive`: Test status when both checks fail.
- `test_diagnosis_messages`: Test diagnosis messages for all states.

**TestModemHealthMonitorInit** (4 tests)
: Test ModemHealthMonitor initialization.

- `test_init_defaults`: Test initialization with default parameters.
- `test_init_with_custom_params`: Test initialization with custom parameters.
- `test_init_with_ssl_context`: Test initialization with pre-created SSL context.
- `test_init_creates_ssl_context_when_none_provided`: Test that SSL context is created if not provided.

**TestInputValidation** (11 tests)
: Test input validation methods.

- `test_is_valid_host_ipv4`: Test IPv4 address validation.
- `test_is_valid_host_hostname`: Test hostname validation.
- `test_is_valid_host_invalid_chars`: Test that shell metacharacters are blocked.
- `test_is_valid_host_empty_or_too_long`: Test empty or overly long hostnames.
- `test_is_valid_url`: Test URL validation.
- `test_is_valid_url_invalid_scheme`: Test that non-HTTP schemes are rejected.
- `test_is_valid_url_no_netloc`: Test that URLs without netloc are rejected.
- `test_is_safe_redirect_same_host`: Test that same-host redirects are allowed.
- `test_is_safe_redirect_relative`: Test that relative redirects are allowed.
- `test_is_safe_redirect_cross_host`: Test that cross-host redirects are blocked.
- `test_is_safe_redirect_non_http_scheme`: Test that non-HTTP scheme redirects are blocked.

**TestHealthCheckPing** (0 tests)
: Test ping check functionality.


**TestHealthCheckHTTP** (0 tests)
: Test HTTP check functionality.


**TestHealthCheckFullFlow** (0 tests)
: Test full health check flow.


**TestAverageLatency** (2 tests)
: Test average latency calculations.

- `test_no_history`: Test average latency with no history.
- `test_filters_failures`: Test that failed checks are excluded from averages.

**TestStatusSummary** (1 tests)
: Test status summary generation.

- `test_no_history`: Test status summary with no history.

### test_hnap_builder.py

Tests for HNAP Request Builder.

**TestHNAPRequestBuilderInit** (1 tests)
: Test HNAP builder initialization.

- `test_init`: Test initialization with endpoint and namespace.

**TestEnvelopeBuilding** (6 tests)
: Test SOAP envelope building.

- `test_build_envelope_no_params`: Test building envelope without parameters.
- `test_build_envelope_with_params`: Test building envelope with parameters.
- `test_build_envelope_valid_xml`: Test that built envelope is valid XML.
- `test_build_multi_envelope`: Test building GetMultipleHNAPs envelope.
- `test_build_multi_envelope_single_action`: Test building multi envelope with single action.
- `test_build_multi_envelope_valid_xml`: Test that multi envelope is valid XML.

**TestCallSingle** (4 tests)
: Test single HNAP action calls.

- `test_success`: Test successful single action call.
- `test_with_params`: Test single call with parameters.
- `test_handles_http_error`: Test that HTTP errors are raised.
- `test_uses_session_verify`: Test that session verify setting is used.

**TestCallMultiple** (2 tests)
: Test batched HNAP action calls.

- `test_success`: Test successful batched call.
- `test_handles_http_error`: Test that HTTP errors are raised for batched calls.

**TestParseResponse** (4 tests)
: Test XML response parsing.

- `test_success`: Test parsing a valid HNAP response.
- `test_without_namespace_prefix`: Test parsing response without namespace prefix.
- `test_not_found`: Test parsing when action response is not found.
- `test_invalid_xml`: Test parsing invalid XML.

**TestGetTextValue** (6 tests)
: Test text value extraction from XML elements.

- `test_found`: Test extracting text value from element.
- `test_not_found`: Test getting text value when tag doesn't exist.
- `test_with_custom_default`: Test custom default value.
- `test_none_element`: Test getting value from None element.
- `test_empty_tag`: Test getting value from empty tag.
- `test_strips_whitespace`: Test that whitespace is stripped from values.

**TestIntegration** (2 tests)
: Integration tests for complete workflows.

- `test_full_workflow_single_action`: Test complete workflow: build envelope, call, parse response.
- `test_endpoint_variations`: Test builders with different endpoint formats.

### test_hnap_json_builder.py

Tests for JSON-based HNAP Request Builder with challenge-response authentication.

**TestHmacMd5** (5 tests)
: Test the HMAC method with MD5 algorithm.

- `test_returns_uppercase_hex`: Test that HMAC-MD5 returns uppercase hexadecimal.
- `test_correct_length`: Test that HMAC-MD5 returns 32 character hex string.
- `test_known_value`: Test HMAC-MD5 against known value.
- `test_empty_strings`: Test HMAC-MD5 with empty strings.
- `test_special_characters`: Test HMAC-MD5 with special characters.

**TestHmacSha256** (3 tests)
: Test the HMAC method with SHA256 algorithm.

- `test_returns_uppercase_hex`: Test that HMAC-SHA256 returns uppercase hexadecimal.
- `test_correct_length`: Test that HMAC-SHA256 returns 64 character hex string.
- `test_different_from_md5`: Test that SHA256 produces different result than MD5.

**TestHmacAlgorithmValidation** (2 tests)
: Test algorithm type safety in builder initialization.

- `test_enum_value_stored`: Test that enum value is stored correctly.
- `test_md5_enum_value_stored`: Test that MD5 enum value is stored correctly.

**TestHNAPJsonRequestBuilderInit** (2 tests)
: Test JSON HNAP builder initialization.

- `test_init`: Test initialization with endpoint, namespace, and algorithm.
- `test_init_custom_values`: Test initialization with custom endpoint and namespace.

**TestHnapAuth** (3 tests)
: Test HNAP_AUTH header generation.

- `test_without_private_key`: Test auth generation without private key uses default.
- `test_with_private_key`: Test auth generation with private key.
- `test_timestamp_format`: Test that timestamp is correctly formatted.

**TestCallSingle** (5 tests)
: Test single JSON HNAP action calls.

- `test_success`: Test successful single action call.
- `test_request_format`: Test that request is properly formatted.
- `test_with_params`: Test single call with parameters.
- `test_handles_http_error`: Test that HTTP errors are raised.
- `test_logs_error_on_failed_response`: Test that failed responses are logged before raise_for_status.

**TestCallMultiple** (5 tests)
: Test batched JSON HNAP action calls.

- `test_success`: Test successful batched call.
- `test_request_format`: Test batched request format.
- `test_default_empty_action_value_is_empty_dict`: Test that default empty action value is {} for backwards compatibility.
- `test_configurable_empty_action_value_string`: Test that empty_action_value can be configured to empty string.
- `test_soap_action_header`: Test that SOAPAction header is correct for batched calls.

**TestLogin** (14 tests)
: Test JSON HNAP login with challenge-response authentication.

- `test_successful_login`: Test successful two-step login flow.
- `test_challenge_request_format`: Test that challenge request is properly formatted.
- `test_login_request_format`: Test that login request includes computed password.
- `test_private_key_computation`: Test that private key is computed correctly.
- `test_login_failed_result`: Test handling of failed login result.
- `test_challenge_missing_fields`: Test handling of incomplete challenge response.
- `test_challenge_http_error`: Test handling of HTTP error during challenge.
- `test_login_timeout`: Test handling of timeout during login.
- `test_login_connection_error`: Test handling of connection error during login.
- `test_invalid_json_challenge`: Test handling of invalid JSON in challenge response.
- `test_success_result_variations`: Test that both OK and SUCCESS are accepted as successful login.
- `test_login_http_error_after_challenge`: Test handling of HTTP error during login step (after successful challenge).
- `test_login_invalid_json_but_http_200`: Test handling of invalid JSON in login response but HTTP 200.
- `test_login_generic_exception`: Test handling of unexpected exception during login.

**TestAuthenticatedRequests** (2 tests)
: Test that authenticated requests use stored private key.

- `test_call_single_uses_private_key`: Test that call_single uses stored private key for auth.
- `test_call_multiple_uses_private_key`: Test that call_multiple uses stored private key for auth.

**TestIntegration** (1 tests)
: Integration tests for complete login and data retrieval workflow.

- `test_full_workflow`: Test complete workflow: login then fetch data.

**TestClearAuthCache** (3 tests)
: Test auth cache clearing for modem restart scenarios.

- `test_clear_auth_cache_clears_private_key`: Test that clear_auth_cache clears the stored private key.
- `test_clear_auth_cache_when_already_none`: Test clear_auth_cache is safe when private key is already None.
- `test_reauth_after_cache_clear`: Test that login works correctly after cache is cleared.

**TestAuthAttemptTracking** (5 tests)
: Test that auth attempts are tracked for diagnostics.

- `test_get_last_auth_attempt_initially_none`: Test that get_last_auth_attempt returns None before any login.
- `test_auth_attempt_stored_on_successful_login`: Test that successful login stores auth attempt data.
- `test_auth_attempt_contains_redacted_password`: Test that stored login request has password redacted.
- `test_auth_attempt_stores_error_on_failed_login`: Test that failed login stores error information.
- `test_auth_attempt_stores_challenge_request_format`: Test that challenge request includes PrivateLogin field.

### test_log_buffer.py

Tests for the log buffer module.

**TestLogEntry** (1 tests)
: Tests for LogEntry dataclass.

- `test_to_dict`: Test LogEntry converts to dict correctly.

**TestLogBuffer** (3 tests)
: Tests for LogBuffer class.

- `test_add_entry`: Test adding entries to buffer.
- `test_rotation`: Test buffer rotates when full.
- `test_clear`: Test clearing buffer.

**TestBufferingHandler** (2 tests)
: Tests for BufferingHandler class.

- `test_captures_logs`: Test handler captures log records to buffer.
- `test_filters_by_level`: Test handler respects log level filter.

### test_network.py

Tests for core/network.py.

**TestIcmpPing** (0 tests)
: Tests for test_icmp_ping function.


### test_parser_utils.py

Tests for core/parser_utils.py.

**TestSortParsersForDropdown** (5 tests)
: Tests for sort_parsers_for_dropdown function.

- `test_sorts_alphabetically_by_manufacturer`: Test parsers are sorted by manufacturer first.
- `test_sorts_by_name_within_manufacturer`: Test parsers are sorted by name within same manufacturer.
- `test_generic_parsers_sorted_last_within_manufacturer`: Test Generic parsers appear last within their manufacturer group.
- `test_unknown_manufacturer_sorted_last`: Test Unknown manufacturer appears at the very end.
- `test_empty_list`: Test empty list returns empty list.

**TestGetParserDisplayName** (1 tests)
: Tests for get_parser_display_name function.

- `test_display_name_suffix`: Test parser display name includes correct suffix based on status.

**TestSelectParserForValidation** (6 tests)
: Tests for select_parser_for_validation function.

- `test_auto_mode_returns_none_parser`: Test auto mode returns None for parser class.
- `test_auto_mode_with_cached_parser`: Test auto mode returns cached parser name as hint.
- `test_none_modem_choice_uses_auto`: Test None modem_choice treated as auto.
- `test_explicit_selection_returns_parser_class`: Test explicit parser selection returns the parser class.
- `test_explicit_selection_strips_asterisk_suffix`: Test explicit selection strips ' *' suffix from choice.
- `test_unknown_parser_returns_none`: Test unknown parser name returns None.

**TestCreateTitle** (1 tests)
: Tests for create_title function.

- `test_create_title`: Test create_title formats title correctly based on detection info.

### test_signal_analyzer.py

Tests for Signal Quality Analyzer.

**TestSignalAnalyzerBasics** (4 tests)
: Test basic signal analyzer functionality.

- `test_initialization`: Test analyzer initializes with empty history.
- `test_add_sample`: Test adding a sample to history.
- `test_add_multiple_samples`: Test adding multiple samples.
- `test_old_samples_removed`: Test that samples older than 48 hours are removed.

**TestSignalMetricExtraction** (5 tests)
: Test SNR, power, and error extraction.

- `test_extract_snr_values`: Test SNR value extraction.
- `test_extract_power_values`: Test power value extraction.
- `test_extract_snr_handles_none_values`: Test that None SNR values are filtered out.
- `test_extract_power_handles_none_values`: Test that None power values are filtered out.
- `test_calculate_error_rates`: Test error rate calculation.

**TestErrorTrendAnalysis** (4 tests)
: Test error trend calculation.

- `test_error_trend_increasing`: Test detection of increasing error trend.
- `test_error_trend_decreasing`: Test detection of decreasing error trend.
- `test_error_trend_stable`: Test detection of stable error trend.
- `test_error_trend_insufficient_data`: Test error trend with insufficient data.

**TestRecommendations** (6 tests)
: Test polling interval recommendations.

- `test_insufficient_samples`: Test recommendation with insufficient samples.
- `test_stable_signal_recommendation`: Test recommendation for very stable signal.
- `test_problematic_signal_recommendation`: Test recommendation for problematic signal.
- `test_fluctuating_signal_recommendation`: Test recommendation for fluctuating signal.
- `test_gradual_adjustment_prevents_drastic_changes`: Test that recommendations don't change too drastically.
- `test_clamping_to_valid_range`: Test that recommendations are clamped to 60-1800 second range.

**TestHistorySummary** (2 tests)
: Test history summary functionality.

- `test_summary_empty_history`: Test summary with no samples.
- `test_summary_with_samples`: Test summary with multiple samples.

**TestMetricsInRecommendation** (1 tests)
: Test that metrics are included in recommendations.

- `test_metrics_included`: Test that recommendation includes detailed metrics.

### test_url_token_session_auth.py

Tests for UrlTokenSessionStrategy.

This tests URL-based token authentication with session cookies, used by
modems like the ARRIS SB8200 HTTPS variant.

Auth flow:
1. Login: GET {login_page}?{login_prefix}{base64(user:pass)}
   - With Authorization: Basic {token} header
   - With X-Requested-With: XMLHttpRequest (if ajax_login=True)
2. Response sets session cookie
3. Data fetch: GET {data_page}?{token_prefix}{session_token}
   - With session cookie
   - WITHOUT Authorization header (if auth_header_data=False)

These tests verify the correct headers are sent based on config attributes,
matching real browser behavior observed in HAR captures (Issue #81).

**TestLoginRequestHeaders** (3 tests)
: Test that login request sends correct headers.

- `test_login_sends_authorization_header`: Login request includes Authorization: Basic header.
- `test_login_sends_ajax_header_when_configured`: Login request includes X-Requested-With when ajax_login=True.
- `test_login_omits_ajax_header_when_not_configured`: Login request omits X-Requested-With when ajax_login not set (default).

**TestDataRequestHeaders** (2 tests)
: Test that data request sends correct headers after login.

- `test_data_request_omits_auth_header_when_configured`: Data request does NOT include Authorization when auth_header_data=False.
- `test_data_request_includes_auth_header_by_default`: Data request includes Authorization by default (backwards compatible).

**TestDataRequestUrl** (1 tests)
: Test that data request URL is correctly formed.

- `test_data_request_includes_session_token_in_url`: Data request URL includes ?ct_<session_token>.

**TestSuccessfulAuthentication** (2 tests)
: Test successful authentication flow.

- `test_returns_data_html_on_success`: Successful auth returns AuthResult.ok with data page HTML.
- `test_returns_data_directly_if_login_response_has_indicator`: If login response already has data, return it directly (no second fetch).

---
*Generated by `scripts/generate_test_docs.py`*
