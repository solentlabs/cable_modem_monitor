"""Tests for scripts/har/har_auth_format.py — JSON-to-text/YAML converter."""

from __future__ import annotations

from scripts.har.har_auth_format import format_text, format_yaml

# ---------------------------------------------------------------------------
# Shared sample data
# ---------------------------------------------------------------------------

SAMPLE_DATA = {
    "modem_name": "CM1200",
    "protocol": "https",
    "interface_type": "html",
    "auth_pattern": "unknown",
    "auth_confidence": "insufficient_evidence",
    "is_post_auth": True,
    "login_url": None,
    "form_action": None,
    "form_method": "POST",
    "form_fields": [],
    "username_field": None,
    "password_field": None,
    "csrf_field": None,
    "csrf_source": None,
    "session_cookie": None,
    "credential_cookie": None,
    "session_header": None,
    "auth_header": None,
    "url_token_prefix": None,
    "login_entry_index": None,
    "auth_entry_index": None,
    "session": {
        "mechanism": "cookie",
        "cookies": [],
        "js_cookies": ["XSRF_TOKEN"],
        "headers": [],
        "csrf": None,
        "csrf_source": None,
    },
    "ghost_cookies": [
        {"name": "XSRF_TOKEN", "first_seen_entry": 1, "first_seen_url": "http://modem/page", "category": "csrf"},
    ],
    "page_auth_map": {
        "/": {
            "path": "/",
            "status_codes": [200],
            "has_401": False,
            "www_authenticate": None,
            "request_cookies": [],
            "response_set_cookies": [],
            "has_login_form": False,
            "has_auth_header": False,
            "response_content_type": "text/html",
        },
    },
    "probe": None,
    "warnings": ["JS-set cookie XSRF_TOKEN"],
    "issues": ["No login page detected"],
    "modem_yaml_auth": None,
    "cross_validation_issues": [],
}


# -------------------------------------------------------------------
# format_text
# -------------------------------------------------------------------


def test_format_text_header_fields() -> None:
    """Header section includes modem name, protocol, confidence."""
    text = format_text(SAMPLE_DATA)
    assert "Modem: CM1200" in text
    assert "Protocol: https" in text
    assert "Confidence: insufficient_evidence" in text
    assert "Post-Auth Capture: yes" in text


def test_format_text_ghost_cookies() -> None:
    text = format_text(SAMPLE_DATA)
    assert "XSRF_TOKEN [csrf]" in text


def test_format_text_warnings() -> None:
    text = format_text(SAMPLE_DATA)
    assert "!! JS-set cookie XSRF_TOKEN" in text


def test_format_text_issues() -> None:
    text = format_text(SAMPLE_DATA)
    assert "No login page detected" in text


def test_format_text_verbose_page_map() -> None:
    """Verbose mode includes page_auth_map detail."""
    text_normal = format_text(SAMPLE_DATA, verbose=False)
    text_verbose = format_text(SAMPLE_DATA, verbose=True)
    assert "Page Auth Map:" not in text_normal
    assert "Page Auth Map:" in text_verbose
    assert "/ — 200" in text_verbose


def test_format_text_cross_validation() -> None:
    data = {**SAMPLE_DATA, "cross_validation_issues": ["yaml contradiction"]}
    text = format_text(data)
    assert "!! yaml contradiction" in text


# -------------------------------------------------------------------
# format_yaml
# -------------------------------------------------------------------


def test_format_yaml_core_fields() -> None:
    text = format_yaml(SAMPLE_DATA)
    assert "modem: CM1200" in text
    assert "protocol: https" in text
    assert "auth_confidence: insufficient_evidence" in text
    assert "is_post_auth: true" in text


def test_format_yaml_ghost_cookies() -> None:
    text = format_yaml(SAMPLE_DATA)
    assert "- name: XSRF_TOKEN" in text
    assert "category: csrf" in text


def test_format_yaml_warnings() -> None:
    text = format_yaml(SAMPLE_DATA)
    assert "- JS-set cookie XSRF_TOKEN" in text


def test_format_yaml_probe_data() -> None:
    data = {
        **SAMPLE_DATA,
        "probe": {
            "auth_status_code": 401,
            "www_authenticate": 'Basic realm="modem"',
            "auth_set_cookies": [],
            "auth_error": None,
            "icmp_reachable": True,
        },
    }
    text = format_yaml(data)
    assert "probe_auth_status: 401" in text
    assert "probe_www_authenticate: Basic" in text
