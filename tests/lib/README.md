# Library Tests

> Auto-generated from test files. Do not edit manually.

Tests for library modules including the HTML crawler and general utilities.

**Total Tests:** 120

## Test Files

| File | Tests | Description |
|------|-------|-------------|
| [test_har_sanitizer.py](test_har_sanitizer.py) | 18 | Tests for HAR sanitization utilities. |
| [test_host_validation.py](test_host_validation.py) | 17 | Tests for host validation utilities. |
| [test_html_crawler.py](test_html_crawler.py) | 36 | Tests for HTML crawler utility functions. |
| [test_html_helper.py](test_html_helper.py) | 27 | Tests for HTML helper utilities. |
| [test_utils.py](test_utils.py) | 22 | Tests for utility functions in lib/utils.py. |

## Test Details

### test_har_sanitizer.py

Tests for HAR sanitization utilities.

**TestSensitiveFieldDetection** (3 tests)
: Tests for sensitive field detection.

- `test_detects_password_fields`: Test detection of various password field names.
- `test_detects_auth_fields`: Test detection of authentication-related fields.
- `test_allows_safe_fields`: Test that normal fields are not flagged.

**TestHeaderSanitization** (4 tests)
: Tests for header value sanitization.

- `test_redacts_authorization_header`: Test Authorization header is redacted.
- `test_redacts_cookie_values`: Test cookie values are redacted but names preserved.
- `test_redacts_set_cookie_values`: Test Set-Cookie values are redacted.
- `test_preserves_safe_headers`: Test non-sensitive headers are preserved.

**TestPostDataSanitization** (5 tests)
: Tests for POST data sanitization.

- `test_sanitizes_password_in_params`: Test password params are redacted.
- `test_sanitizes_password_in_text`: Test password in form-urlencoded text is redacted.
- `test_sanitizes_json_post_data`: Test password in JSON body is redacted.
- `test_handles_none_post_data`: Test None post data returns None.
- `test_handles_empty_post_data`: Test empty post data is handled.

**TestEntrySanitization** (3 tests)
: Tests for full HAR entry sanitization.

- `test_sanitizes_request_headers`: Test request headers are sanitized.
- `test_sanitizes_response_content`: Test response HTML content is sanitized.
- `test_sanitizes_post_data`: Test POST data is sanitized.

**TestFullHarSanitization** (3 tests)
: Tests for complete HAR file sanitization.

- `test_sanitizes_all_entries`: Test all entries in HAR are sanitized.
- `test_handles_missing_log_key`: Test handling of invalid HAR without log key.
- `test_preserves_har_structure`: Test HAR structure is preserved after sanitization.

### test_host_validation.py

Tests for host validation utilities.

**TestIsValidHost** (8 tests)
: Tests for is_valid_host function.

- `test_valid_ipv4_addresses`: Test valid IPv4 addresses.
- `test_valid_ipv6_addresses`: Test valid IPv6 addresses.
- `test_valid_hostnames`: Test valid hostnames.
- `test_invalid_empty_host`: Test empty host is invalid.
- `test_invalid_too_long_host`: Test host exceeding max length is invalid.
- `test_invalid_shell_metacharacters`: Test hosts with shell metacharacters are rejected.
- `test_invalid_formats_rejected`: Test that truly invalid formats are rejected.
- `test_invalid_hostname_formats`: Test invalid hostname formats.

**TestExtractHostname** (9 tests)
: Tests for extract_hostname function.

- `test_extract_from_http_url`: Test hostname extraction from HTTP URL.
- `test_extract_from_https_url`: Test hostname extraction from HTTPS URL.
- `test_extract_from_url_with_port`: Test hostname extraction from URL with port.
- `test_extract_plain_hostname`: Test extraction when plain hostname is provided.
- `test_strips_whitespace`: Test that whitespace is stripped.
- `test_raises_on_empty_host`: Test ValueError on empty host.
- `test_raises_on_invalid_host`: Test ValueError on invalid host format.
- `test_raises_on_invalid_url`: Test ValueError on invalid URL.
- `test_raises_on_non_http_protocol`: Test rejection of non-HTTP protocols.

### test_html_crawler.py

Tests for HTML crawler utility functions.

**TestGenerateSeedUrls** (6 tests)
: Tests for generate_seed_urls function.

- `test_default_seeds`: Test default seed URL generation.
- `test_custom_bases_and_extensions`: Test with custom bases and extensions.
- `test_empty_base_with_empty_extension_adds_root`: Test that empty base with empty extension adds root path.
- `test_empty_base_with_extensions_skipped`: Test that empty base with extensions is skipped (no /.html).
- `test_no_duplicates`: Test that duplicate URLs are removed.
- `test_default_constants`: Test that default constants are defined correctly.

**TestNormalizeUrl** (5 tests)
: Tests for normalize_url function.

- `test_removes_fragment`: Test that URL fragments are removed.
- `test_removes_trailing_slash`: Test that trailing slashes are removed.
- `test_preserves_root_slash`: Test that root path slash is preserved.
- `test_preserves_query_string`: Test that query strings are preserved.
- `test_handles_complex_url`: Test normalization of complex URL.

**TestExtractLinksFromHtml** (9 tests)
: Tests for extract_links_from_html function.

- `test_extracts_absolute_links`: Test extraction of absolute links.
- `test_converts_relative_links`: Test that relative links are converted to absolute.
- `test_ignores_external_links`: Test that external domain links are ignored.
- `test_ignores_anchors`: Test that anchor-only links are ignored.
- `test_ignores_javascript_links`: Test that javascript: links are ignored.
- `test_ignores_mailto_links`: Test that mailto: links are ignored.
- `test_ignores_binary_files`: Test that binary file links are ignored.
- `test_handles_empty_html`: Test handling of empty HTML.
- `test_handles_malformed_html`: Test handling of malformed HTML.

**TestDiscoverLinksFromPages** (3 tests)
: Tests for discover_links_from_pages function.

- `test_discovers_from_multiple_pages`: Test link discovery from multiple pages.
- `test_deduplicates_links`: Test that duplicate links are deduplicated.
- `test_handles_empty_content`: Test handling of pages with empty content.

**TestGetNewLinksToCrawl** (3 tests)
: Tests for get_new_links_to_crawl function.

- `test_returns_uncaptured_links`: Test that only uncaptured links are returned.
- `test_respects_max_limit`: Test that max_new_links limit is respected.
- `test_returns_empty_when_all_captured`: Test empty result when all links already captured.

**TestExtractAllResourcesFromHtml** (9 tests)
: Tests for extract_all_resources_from_html function.

- `test_extracts_javascript_files`: Test extraction of JavaScript file references.
- `test_extracts_css_files`: Test extraction of CSS file references.
- `test_extracts_html_links`: Test extraction of HTML page links.
- `test_extracts_jquery_load_fragments`: Test extraction of jQuery .load() fragment URLs.
- `test_returns_all_resource_types`: Test that all resource type keys are present.
- `test_ignores_external_resources`: Test that external domain resources are ignored.
- `test_handles_inline_scripts`: Test that inline scripts without src are handled.
- `test_extracts_urls_from_inline_javascript`: Test that URLs are extracted from inline JavaScript menus.
- `test_handles_css_link_without_rel`: Test CSS detection by file extension when rel is missing.

**TestResourceTypeConstants** (1 tests)
: Tests for resource type constants.

- `test_constants_defined`: Test that resource type constants are properly defined.

### test_html_helper.py

Tests for HTML helper utilities.

**TestCheckForPii** (11 tests)
: Tests for check_for_pii function.

- `test_detects_mac_address`: Test detection of MAC addresses.
- `test_detects_email`: Test detection of email addresses.
- `test_detects_public_ip`: Test detection of public IP addresses.
- `test_detects_ipv6`: Test detection of IPv6 addresses.
- `test_ignores_time_format`: Test that time formats are not flagged as IPv6.
- `test_ignores_allowlisted_placeholders`: Test that allowlisted placeholders are not flagged.
- `test_returns_line_numbers`: Test that line numbers are correctly reported.
- `test_includes_filename`: Test that filename is included in findings.
- `test_multiple_findings`: Test detection of multiple PII instances.
- `test_empty_content`: Test with empty content.
- `test_clean_content`: Test content with no PII.

**TestPiiPatterns** (2 tests)
: Tests for PII pattern constants.

- `test_patterns_defined`: Test that all expected patterns are defined.
- `test_allowlist_defined`: Test that allowlist contains expected placeholders.

**TestSanitizeHtmlEdgeCases** (5 tests)
: Additional edge case tests for sanitize_html.

- `test_multiple_mac_formats`: Test sanitization of MACs with different separators.
- `test_ipv6_with_hex_letters`: Test that IPv6 with hex letters is sanitized.
- `test_ipv6_without_hex_letters_preserved`: Test that time-like patterns are not over-sanitized.
- `test_config_file_path_sanitized`: Test that config file paths are sanitized.
- `test_preserves_signal_metrics`: Test that signal metrics are preserved.

**TestTagValueListSanitization** (9 tests)
: Tests for WiFi credential sanitization in tagValueList.

- `test_sanitizes_wifi_passphrase_in_dashboard`: Test that WiFi passphrases in DashBoard tagValueList are sanitized.
- `test_preserves_status_values_in_tagvaluelist`: Test that status values like 'Locked', 'Good' are preserved.
- `test_preserves_numeric_values_in_tagvaluelist`: Test that numeric values like frequencies are preserved.
- `test_preserves_version_strings_in_tagvaluelist`: Test that version strings are preserved.
- `test_sanitizes_double_quoted_tagvaluelist`: Test that double-quoted tagValueList is also sanitized.
- `test_preserves_short_values_in_tagvaluelist`: Test that short values (< 8 chars) are preserved.
- `test_handles_docsis_channel_data`: Test that DOCSIS channel data is not incorrectly sanitized.
- `test_wifi_cred_in_allowlist`: Test that WIFI_CRED placeholder is in allowlist.
- `test_sanitizes_device_names_before_ip`: Test that device names appearing before IP/MAC placeholders are redacted.

### test_utils.py

Tests for utility functions in lib/utils.py.

**TestExtractNumber** (5 tests)
: Test the extract_number function.

- `test_positive_integer`: Test extracting a positive integer.
- `test_negative_integer`: Test extracting a negative integer.
- `test_string_with_text`: Test extracting an integer from a string with other text.
- `test_string_with_no_digits`: Test a string with no digits.
- `test_empty_string`: Test an empty string.

**TestExtractFloat** (5 tests)
: Test the extract_float function.

- `test_positive_float`: Test extracting a positive float.
- `test_negative_float`: Test extracting a negative float.
- `test_string_with_text`: Test extracting a float from a string with other text.
- `test_string_with_no_digits`: Test a string with no digits.
- `test_empty_string`: Test an empty string.

**TestParseUptime** (12 tests)
: Test the parse_uptime_to_seconds function.

- `test_days_hours`: Test parsing uptime with days and hours.
- `test_hours_only`: Test parsing uptime with only hours.
- `test_with_minutes`: Test parsing uptime with hours and minutes.
- `test_complex`: Test parsing complex uptime string.
- `test_unknown`: Test parsing Unknown uptime.
- `test_empty`: Test parsing empty uptime.
- `test_none`: Test parsing None uptime.
- `test_hms_format`: Test parsing HH:MM:SS format (e.g., CM600).
- `test_hms_format_short`: Test parsing shorter HH:MM:SS format.
- `test_hms_format_single_digits`: Test parsing H:M:S format with single digits.
- `test_days_plus_hms_format`: Test parsing 'X days HH:MM:SS' format (common in HNAP modems).
- `test_days_plus_hms_format_zero_days`: Test parsing '0 days HH:MM:SS' format.

---
*Generated by `scripts/generate_test_docs.py`*
