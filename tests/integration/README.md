# Integration Tests

> Auto-generated from test files. Do not edit manually.

End-to-end integration tests using mock HTTP/HTTPS servers with fixture data. Tests real SSL/TLS handling, authentication flows, and modem communication patterns.

**Total Tests:** 44

## Test Files

| File | Tests | Description |
|------|-------|-------------|
| [test_config_flow_e2e.py](test_config_flow_e2e.py) | 7 | E2E tests for config flow against mock modem servers. |
| [test_fixture_validation.py](test_fixture_validation.py) | 28 | Fixture-Based Validation Tests for Auth Strategy Discovery. |
| [test_modem_e2e.py](test_modem_e2e.py) | 9 | End-to-end tests for modems using MockModemServer. |

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

- `test_sb6190_form_auth`: SB6190 form auth should authenticate and parse.
- `test_sb6190_wrong_credentials`: SB6190 form auth should fail with wrong credentials.

**TestNoAuthE2E** (1 tests)
: E2E tests for modems without authentication.

- `test_sb6190_no_auth`: SB6190 no-auth variant should work without credentials.

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
