# Integration Tests

> Auto-generated from test files. Do not edit manually.

End-to-end integration tests using mock HTTP/HTTPS servers with fixture data. Tests real SSL/TLS handling, authentication flows, and modem communication patterns.

**Total Tests:** 73

## Test Files

| File | Tests | Description |
|------|-------|-------------|
| [test_config_flow_e2e.py](test_config_flow_e2e.py) | 9 | E2E tests for config flow against mock modem servers. |
| [test_fixture_validation.py](test_fixture_validation.py) | 28 | Fixture-Based Validation Tests for Auth Strategy Discovery. |
| [test_hnap_protocol_fallback.py](test_hnap_protocol_fallback.py) | 6 | Tests for HNAP modem protocol fallback behavior. |
| [test_mock_server_delay.py](test_mock_server_delay.py) | 4 | Tests for MockModemServer response delay feature. |
| [test_modem_e2e.py](test_modem_e2e.py) | 9 | End-to-end tests for modems using MockModemServer. |
| [test_session_limit.py](test_session_limit.py) | 7 | Tests for single-session modem behavior (max_concurrent=1). |
| [test_url_token_polling.py](test_url_token_polling.py) | 10 | Tests for URL token authentication during polling cycle. |

## Test Details

### test_config_flow_e2e.py

E2E tests for config flow against mock modem servers.

Tests the known modem setup flow using MockModemServer to simulate
real modem behavior without hardware. These tests verify the path
users take when selecting their modem model from the dropdown.

Tests run on both HTTP and HTTPS protocols to ensure protocol detection
works correctly for all modems.

**TestAuthTypeSelection** (2 tests)
: Test that auth type dropdown appears for correct modems.

- `test_multi_auth_modem_needs_selection`: Modems with multiple auth types should show dropdown.
- `test_single_auth_modem_no_selection`: Modems with single auth type should not show dropdown.

**TestStaticAuthConfig** (1 tests)
: Test that static auth config is built correctly from modem.yaml.

- `test_build_static_auth_config`: Static auth config should have correct strategy.

**TestKnownModemSetupE2E** (1 tests)
: E2E tests running known modem setup against mock servers.

- `test_setup_with_static_auth`: Known modem setup should succeed with static auth config from modem.yaml.

**TestFormAuthE2E** (2 tests)
: E2E tests for form-based authentication.

- `test_sb6190_form_nonce_auth`: SB6190 form_nonce auth should authenticate and parse.
- `test_sb6190_wrong_credentials`: SB6190 form_nonce auth should fail with wrong credentials.

**TestNoAuthE2E** (1 tests)
: E2E tests for modems without authentication.

- `test_sb6190_no_auth`: SB6190 no-auth variant should work without credentials.

**TestWorkingUrlFormat** (2 tests)
: Tests to verify working_url is always a base URL without path.

- `test_cga2121_working_url_is_base_url`: CGA2121 setup should return base URL without page path.
- `test_mb7621_working_url_is_base_url`: MB7621 setup should return base URL without page path.

### test_fixture_validation.py

Fixture-Based Validation Tests for Auth Strategy Discovery.

These tests validate auth strategies using committed fixture files:
1. HNAP request/response format validation
2. Login page detection patterns
3. Parser hint consistency
4. Auth strategy matching

Unlike HAR files (which are gitignored), these fixtures are committed
to the repo and always available for testing.

**TestSB8200AuthValidation** (4 tests)
: Validate SB8200 URL token auth pattern using fixtures.

- `test_login_page_exists`: Verify login page fixture is available.
- `test_login_page_has_javascript_auth`: Verify login page contains JavaScript-based auth pattern.
- `test_parser_js_auth_hints_complete`: Verify SB8200 modem.yaml has complete js_auth_hints (v3.12.0+).
- `test_data_page_can_be_parsed`: Verify parser can parse data page from fixture.

**TestS33AuthValidation** (6 tests)
: Validate S33 HNAP auth pattern using fixtures.

- `test_login_page_exists`: Verify login page fixture is available.
- `test_login_page_has_hnap_pattern`: Verify login page contains HNAP auth pattern.
- `test_hnap_request_uses_empty_string`: Verify S33 HNAP request uses empty string for action values.
- `test_hnap_login_response_has_challenge`: Verify HNAP login response contains challenge pattern.
- `test_parser_hnap_hints_complete`: Verify S33 modem.yaml has complete hnap_hints (v3.12.0+).
- `test_hnap_response_can_be_parsed`: Verify parser can handle HNAP response format.

**TestMB8611AuthValidation** (6 tests)
: Validate MB8611 HNAP auth pattern using fixtures.

- `test_login_page_exists`: Verify login page fixture is available.
- `test_login_page_has_hnap_pattern`: Verify login page contains HNAP auth pattern.
- `test_hnap_request_uses_empty_string`: Verify MB8611 HNAP request uses empty string for action values.
- `test_hnap_login_response_has_challenge`: Verify HNAP login response contains challenge pattern.
- `test_parser_hnap_hints_complete`: Verify MB8611 modem.yaml has complete hnap_hints (v3.12.0+).
- `test_hnap_response_can_be_parsed`: Verify parser can handle HNAP response format.

**TestS33VsMB8611Similarities** (3 tests)
: Validate S33 and MB8611 HNAP share the same empty_action_value.

- `test_empty_action_value_same`: Verify both S33 and MB8611 use '' for action values (v3.12.0+).
- `test_request_fixtures_match_parser_hints`: Verify request fixtures match parser empty_action_value hints.
- `test_action_names_differ`: Verify S33 uses GetCustomer* while MB8611 uses GetMoto* actions.

**TestAuthStrategyConstants** (3 tests)
: Validate auth strategy constants match expected values.

- `test_all_strategies_defined`: Verify all auth strategies are defined.
- `test_strategy_string_values`: Verify strategy string values for storage.
- `test_strategy_from_string`: Verify strategies can be created from string values.

**TestParserHintsConsistency** (3 tests)
: Validate modem.yaml auth hints are consistent across parsers (v3.12.0+).

- `test_s33_hnap_hints_complete`: Verify S33 modem.yaml has complete HNAP hints.
- `test_mb8611_hnap_hints_complete`: Verify MB8611 modem.yaml has complete HNAP hints.
- `test_sb8200_js_auth_hints_complete`: Verify SB8200 modem.yaml has complete JS auth hints.

**TestRealHARValidation** (3 tests)
: Validate parser hints against real HAR-derived fixtures.

- `test_mb8611_empty_action_value_matches_fixture`: Verify MB8611 modem.yaml empty_action_value matches real HAR-derived fixture (v3.12.0+).
- `test_s33_empty_action_value_matches_parser`: Verify S33 modem.yaml uses empty string for action values (v3.12.0+).
- `test_default_hnap_config_uses_empty_string`: Verify DEFAULT_HNAP_CONFIG uses empty string for action values.

### test_hnap_protocol_fallback.py

Tests for HNAP modem protocol fallback behavior.

Issue: S34 and other HNAP modems respond to HTTP but only work over HTTPS.
The connectivity check accepts HTTP responses, but HNAP auth fails.

These tests verify:
1. CURRENT BEHAVIOR: setup_modem fails when HTTP is tried first for HNAP modems
2. DESIRED BEHAVIOR: setup_modem tries HTTPS if HTTP auth fails

Related: PR #90 (S34 support), Issue #81 (SB8200)

**TestCurrentBehavior** (2 tests)
: Tests documenting CURRENT (broken) behavior for HNAP protocol selection.

- `test_explicit_https_works`: CURRENT: Explicit HTTPS URL works for HNAP modems.
- `test_explicit_http_fails_for_hnap`: CURRENT: Explicit HTTP URL fails for HNAP modems.

**TestProtocolFallback** (3 tests)
: Tests for protocol fallback behavior.

- `test_hnap_paradigm_tries_https_first`: HNAP paradigm should try HTTPS first.
- `test_html_paradigm_tries_http_first`: HTML paradigm should try HTTP first.
- `test_fallback_when_first_protocol_fails`: Should fall back to second protocol when first fails.

**TestRealWorldScenario** (1 tests)
: Tests using actual modem fixtures (closer to real deployment).

- `test_s34_explicit_https_with_mock_server`: S34 with explicit HTTPS using MockModemServer.

### test_mock_server_delay.py

Tests for MockModemServer response delay feature.

Verifies that response_delay parameter correctly delays responses
for timeout testing scenarios.

**TestResponseDelay** (4 tests)
: Test response_delay parameter.

- `test_no_delay_by_default`: Responses should be fast when no delay configured.
- `test_delay_applied_to_responses`: Responses should be delayed when response_delay is set.
- `test_delay_applied_to_multiple_requests`: Each request should be delayed independently.
- `test_zero_delay_is_valid`: Zero delay should work (no-op).

### test_modem_e2e.py

End-to-end tests for modems using MockModemServer.

Auto-discovers all modems in modems/**/modem.yaml and runs
a complete auth + parse workflow against MockModemServer.

Note: Tests use the repo root modems/ directory (source of truth),
not custom_components/.../modems/ (deployment sync target).

**TestModemE2E** (5 tests)
: End-to-end tests for modem configurations.

- `test_public_pages_accessible`: Test that public pages are accessible without authentication.
- `test_protected_pages_require_auth`: Test that protected pages require authentication.
- `test_form_auth_workflow`: Test complete form authentication workflow.
- `test_auth_handler_integration`: Test that AuthHandler works with MockModemServer.
- `test_parser_detection_with_fixtures`: Test that the declared parser can parse the fixture data.

**TestModemE2EFullWorkflow** (1 tests)
: Full workflow tests: auth -> fetch -> parse.

- `test_complete_workflow`: Test complete workflow: auth, fetch data pages, parse.

**TestDiscoveryPipelineE2E** (3 tests)
: Test the actual discovery pipeline against MockModemServer.

- `test_discovery_pipeline_dynamic_auth`: Test run_discovery_pipeline with dynamic auth discovery.
- `test_discovery_pipeline_auto_detection`: Test discovery pipeline with auto-detection (no pre-selected parser).
- `test_known_modem_setup_static_auth`: Test setup_modem with static auth config from modem.yaml.

### test_session_limit.py

Tests for single-session modem behavior (max_concurrent=1).

Reproduces Issue #61: Netgear C7000v2 only allows one authenticated session.
The v3.13 refactor introduced a bug where setup_modem() creates two separate
sessions (connectivity check + auth check), causing auth to fail on single-session modems.

**TestSessionLimit** (5 tests)
: Test single-session modem behavior.

- `test_single_session_allows_first_client`: First authenticated request should succeed.
- `test_single_session_blocks_second_client`: Second client should be blocked when max_concurrent=1.
- `test_logout_releases_session`: Logout should allow new client to connect.
- `test_same_client_can_make_multiple_requests`: Same client should be able to make multiple requests.
- `test_unlimited_sessions_allows_multiple_clients`: With max_concurrent=0 (default), multiple clients should work.

**TestSetupModemSessionBug** (2 tests)
: Test that reproduces the setup_modem() session bug from Issue #61.

- `test_setup_modem_works_with_ip_based_sessions`: Test that setup_modem works when sessions are tracked by IP.
- `test_setup_modem_with_connection_based_sessions`: Test setup_modem if Netgear tracks sessions by TCP connection.

### test_url_token_polling.py

Tests for URL token authentication during polling cycle.

These tests verify:
1. Config flow works with URL token auth
2. DataOrchestrator uses AuthHandler during get_modem_data()
3. Strict URL token validation works (cookies alone rejected)

**TestConfigFlowVsPolling** (1 tests)
: Compare config flow behavior vs polling behavior for URL token auth.

- `test_config_flow_works_with_url_token`: Config flow successfully authenticates with URL token auth.

**TestAuthHandlerUsage** (2 tests)
: Tests verifying AuthHandler is used during data fetch.

- `test_get_modem_data_uses_auth_handler`: Verify get_modem_data uses reactive auth for URL token sessions.
- `test_login_uses_auth_handler`: Verify _login() uses AuthHandler.

**TestUrlTokenAuthRequirement** (1 tests)
: Tests verifying URL token auth works correctly.

- `test_authenticated_request_succeeds`: Verify mock server works with correct URL token auth.

**TestStrictUrlTokenAuth** (2 tests)
: Tests with strict URL token validation (cookies alone don't work).

- `test_cookies_alone_are_rejected`: Verify that cookies alone don't authenticate - URL token required.
- `test_polling_with_strict_url_token_server`: Test that polling works with strict URL token validation.

**TestTwoStepUrlTokenAuth** (4 tests)
: Tests with two-step URL token auth (real SB8200 HTTPS firmware behavior).

- `test_two_step_login_returns_token_not_html`: Verify two-step mock returns token in body, not HTML.
- `test_two_step_data_fetch_requires_token`: Verify data page requires token after two-step login.
- `test_polling_with_two_step_url_token`: Test full polling cycle with two-step URL token auth.
- `test_loader_fetches_additional_pages_with_correct_token`: Verify HTMLLoader uses CORRECT token (from response body, not cookie).

## Fixtures

| Fixture | Description |
|---------|-------------|
| `test_certs` | Generate self-signed certificates for HTTPS testing. |
| `http_server` | Provide a plain HTTP server (no SSL). |
| `https_modern_server` | Provide an HTTPS server with modern ciphers (default SSL ... |
| `https_legacy_server` | Provide an HTTPS server that ONLY accepts legacy ciphers. |
| `https_self_signed_server` | Provide an HTTPS server with self-signed certificate. |
| `sb8200_server_noauth` | Provide SB8200 mock server without auth (Tim's variant). |
| `sb8200_server_auth` | Provide SB8200 mock server with URL-based auth (Travis's ... |
| `sb8200_server_auth_https` | Provide SB8200 mock server with HTTPS + auth (full Travis... |
| `basic_auth_server` | Provide mock server requiring HTTP Basic Auth. |
| `form_auth_server` | Provide mock server with form-based authentication. |
| `hnap_auth_server` | Provide mock server with HNAP-style login page. |
| `redirect_auth_server` | Provide mock server with meta refresh redirect to login. |
| `hnap_soap_server` | Provide HNAP SOAP server with challenge-response auth. |
| `session_expiry_server` | Provide server that expires sessions after N requests. |
| `http_302_redirect_server` | Provide server using HTTP 302 redirects. |
| `form_base64_server` | Provide server requiring base64-encoded password. |
| `https_form_auth_server` | Provide HTTPS server with form-based authentication. |
| `mb7621_modem_server` | MB7621 server using modem.yaml configuration. |
| `sb8200_modem_server` | SB8200 server using modem.yaml configuration. |
| `s33_modem_server` | S33 server using modem.yaml configuration. |
| `g54_modem_server` | G54 server using modem.yaml configuration. |
| `sb6190_modem_server` | SB6190 server using modem.yaml configuration. |
| `cga2121_modem_server` | CGA2121 server using modem.yaml configuration. |
| `mb8611_modem_server` | MB8611 server using modem.yaml configuration. |

---
*Generated by `scripts/generate_test_docs.py`*
