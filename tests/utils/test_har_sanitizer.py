"""Tests for HAR sanitization utilities."""

import json

from custom_components.cable_modem_monitor.utils.har_sanitizer import (
    is_sensitive_field,
    sanitize_entry,
    sanitize_har,
    sanitize_header_value,
    sanitize_post_data,
)


class TestSensitiveFieldDetection:
    """Tests for sensitive field detection."""

    def test_detects_password_fields(self):
        """Test detection of various password field names."""
        assert is_sensitive_field("password") is True
        assert is_sensitive_field("loginPassword") is True
        assert is_sensitive_field("user_password") is True
        assert is_sensitive_field("passwd") is True
        assert is_sensitive_field("pwd") is True

    def test_detects_auth_fields(self):
        """Test detection of authentication-related fields."""
        assert is_sensitive_field("auth_token") is True
        assert is_sensitive_field("apikey") is True
        assert is_sensitive_field("api_key") is True
        assert is_sensitive_field("secret") is True

    def test_allows_safe_fields(self):
        """Test that normal fields are not flagged."""
        assert is_sensitive_field("username") is False
        assert is_sensitive_field("loginName") is False
        assert is_sensitive_field("channel_id") is False
        assert is_sensitive_field("frequency") is False


class TestHeaderSanitization:
    """Tests for header value sanitization."""

    def test_redacts_authorization_header(self):
        """Test Authorization header is redacted."""
        result = sanitize_header_value("Authorization", "Bearer abc123xyz")
        assert result == "[REDACTED]"

    def test_redacts_cookie_values(self):
        """Test cookie values are redacted but names preserved."""
        result = sanitize_header_value("Cookie", "session=abc123; user=admin")
        assert "session=[REDACTED]" in result
        assert "user=[REDACTED]" in result
        assert "abc123" not in result

    def test_redacts_set_cookie_values(self):
        """Test Set-Cookie values are redacted."""
        result = sanitize_header_value("Set-Cookie", "session=xyz789; Path=/")
        assert "session=[REDACTED]" in result
        assert "xyz789" not in result

    def test_preserves_safe_headers(self):
        """Test non-sensitive headers are preserved."""
        result = sanitize_header_value("Content-Type", "text/html")
        assert result == "text/html"

        result = sanitize_header_value("Content-Length", "1234")
        assert result == "1234"


class TestPostDataSanitization:
    """Tests for POST data sanitization."""

    def test_sanitizes_password_in_params(self):
        """Test password params are redacted."""
        post_data = {
            "mimeType": "application/x-www-form-urlencoded",
            "params": [
                {"name": "loginName", "value": "admin"},
                {"name": "loginPassword", "value": "secret123"},
            ],
        }

        result = sanitize_post_data(post_data)

        assert result is not None
        # Username preserved
        assert result["params"][0]["value"] == "admin"
        # Password redacted
        assert result["params"][1]["value"] == "[REDACTED]"

    def test_sanitizes_password_in_text(self):
        """Test password in form-urlencoded text is redacted."""
        post_data = {
            "mimeType": "application/x-www-form-urlencoded",
            "text": "loginName=admin&loginPassword=secret123",
        }

        result = sanitize_post_data(post_data)

        assert result is not None
        assert "loginName=admin" in result["text"]
        assert "loginPassword=[REDACTED]" in result["text"]
        assert "secret123" not in result["text"]

    def test_sanitizes_json_post_data(self):
        """Test password in JSON body is redacted."""
        post_data = {
            "mimeType": "application/json",
            "text": '{"username": "admin", "password": "secret123"}',
        }

        result = sanitize_post_data(post_data)

        assert result is not None
        parsed = json.loads(result["text"])

        assert parsed["username"] == "admin"
        assert parsed["password"] == "[REDACTED]"

    def test_handles_none_post_data(self):
        """Test None post data returns None."""
        assert sanitize_post_data(None) is None

    def test_handles_empty_post_data(self):
        """Test empty post data is handled."""
        result = sanitize_post_data({})
        assert result == {}


class TestEntrySanitization:
    """Tests for full HAR entry sanitization."""

    def test_sanitizes_request_headers(self):
        """Test request headers are sanitized."""
        entry = {
            "request": {
                "method": "GET",
                "url": "http://192.168.100.1/",
                "headers": [
                    {"name": "Cookie", "value": "session=secret123"},
                    {"name": "Content-Type", "value": "text/html"},
                ],
            },
            "response": {
                "status": 200,
                "headers": [],
                "content": {"text": "", "mimeType": "text/html"},
            },
        }

        result = sanitize_entry(entry)

        cookie_header = next(h for h in result["request"]["headers"] if h["name"] == "Cookie")
        assert "secret123" not in cookie_header["value"]
        assert "[REDACTED]" in cookie_header["value"]

    def test_sanitizes_response_content(self):
        """Test response HTML content is sanitized."""
        entry = {
            "request": {
                "method": "GET",
                "url": "http://192.168.100.1/",
                "headers": [],
            },
            "response": {
                "status": 200,
                "headers": [],
                "content": {
                    "text": "<html>MAC: AA:BB:CC:DD:EE:FF</html>",
                    "mimeType": "text/html",
                },
            },
        }

        result = sanitize_entry(entry)

        content = result["response"]["content"]["text"]
        assert "AA:BB:CC:DD:EE:FF" not in content
        assert "XX:XX:XX:XX:XX:XX" in content

    def test_sanitizes_post_data(self):
        """Test POST data is sanitized."""
        entry = {
            "request": {
                "method": "POST",
                "url": "http://192.168.100.1/login",
                "headers": [],
                "postData": {
                    "mimeType": "application/x-www-form-urlencoded",
                    "params": [
                        {"name": "username", "value": "admin"},
                        {"name": "password", "value": "secret"},
                    ],
                    "text": "username=admin&password=secret",
                },
            },
            "response": {
                "status": 302,
                "headers": [],
                "content": {"text": "", "mimeType": "text/html"},
            },
        }

        result = sanitize_entry(entry)

        # Check params
        password_param = next(p for p in result["request"]["postData"]["params"] if p["name"] == "password")
        assert password_param["value"] == "[REDACTED]"

        # Check text
        assert "password=[REDACTED]" in result["request"]["postData"]["text"]
        assert "secret" not in result["request"]["postData"]["text"]


class TestFullHarSanitization:
    """Tests for complete HAR file sanitization."""

    def test_sanitizes_all_entries(self):
        """Test all entries in HAR are sanitized."""
        har_data = {
            "log": {
                "version": "1.2",
                "entries": [
                    {
                        "request": {
                            "method": "GET",
                            "url": "http://192.168.100.1/",
                            "headers": [{"name": "Cookie", "value": "session=abc"}],
                        },
                        "response": {
                            "status": 200,
                            "headers": [],
                            "content": {"text": "MAC: 11:22:33:44:55:66", "mimeType": "text/html"},
                        },
                    },
                    {
                        "request": {
                            "method": "POST",
                            "url": "http://192.168.100.1/login",
                            "headers": [],
                            "postData": {
                                "mimeType": "application/x-www-form-urlencoded",
                                "params": [{"name": "password", "value": "secret"}],
                                "text": "password=secret",
                            },
                        },
                        "response": {
                            "status": 302,
                            "headers": [{"name": "Set-Cookie", "value": "session=xyz"}],
                            "content": {"text": "", "mimeType": "text/html"},
                        },
                    },
                ],
            }
        }

        result = sanitize_har(har_data)

        # Check first entry
        entry1 = result["log"]["entries"][0]
        assert "11:22:33:44:55:66" not in entry1["response"]["content"]["text"]

        # Check second entry
        entry2 = result["log"]["entries"][1]
        assert entry2["request"]["postData"]["params"][0]["value"] == "[REDACTED]"

    def test_handles_missing_log_key(self):
        """Test handling of invalid HAR without log key."""
        har_data = {"invalid": "structure"}
        result = sanitize_har(har_data)
        assert "invalid" in result  # Returns input with warning

    def test_preserves_har_structure(self):
        """Test HAR structure is preserved after sanitization."""
        har_data = {
            "log": {
                "version": "1.2",
                "creator": {"name": "Test", "version": "1.0"},
                "entries": [],
                "pages": [{"title": "Test Page"}],
            }
        }

        result = sanitize_har(har_data)

        assert result["log"]["version"] == "1.2"
        assert result["log"]["creator"]["name"] == "Test"
        assert len(result["log"]["pages"]) == 1
