"""Tests for form field discovery — extract_form_fields()."""

from __future__ import annotations

from pathlib import Path

import pytest
from solentlabs.cable_modem_monitor_core.mcp.analysis.auth.form_discovery import (
    detect_form_selector,
    extract_form_fields,
    extract_hidden_fields,
)

_FIXTURES = Path(__file__).parent / "fixtures" / "form_discovery"


def _load(name: str) -> str:
    return (_FIXTURES / name).read_text()


# ---------------------------------------------------------------------------
# Table-driven: extract_form_fields()
# ---------------------------------------------------------------------------

# fmt: off
# (description, fixture_file, form_selector, expected)
EXTRACT_CASES = [
    (
        "single_form_hidden_fields",
        "single_form_hidden.html",
        "",
        {"tok": "x", "mode": "login"},
    ),
    (
        "text_and_password_inputs",
        "text_and_password.html",
        "",
        {"user": "", "pwd": ""},
    ),
    (
        "multiple_forms_no_selector",
        "multiple_forms.html",
        "",
        {"q": ""},  # first form wins
    ),
    (
        "multiple_forms_with_selector",
        "multiple_forms.html",
        "form#login",
        {"user": "admin"},
    ),
    (
        "selector_no_match_falls_back",
        "selector_no_match.html",
        "form#missing",
        {"a": "1"},  # falls back to first <form>
    ),
    (
        "no_form_bare_inputs",
        "bare_inputs.html",
        "",
        {"x": "y"},  # page-level fallback
    ),
    (
        "empty_html",
        "empty.html",
        "",
        {},
    ),
    (
        "no_inputs_at_all",
        "no_inputs.html",
        "",
        {},
    ),
    (
        "input_without_name",
        "input_without_name.html",
        "",
        {},
    ),
    (
        "input_without_value",
        "input_without_value.html",
        "",
        {"field": ""},
    ),
    (
        "select_element_selected",
        "select_element.html",
        "",
        {"lang": "en"},
    ),
    (
        "select_no_selected_option",
        "select_no_selected.html",
        "",
        {"lang": "en"},  # falls back to first option
    ),
    (
        "mixed_inputs_and_hidden",
        "mixed_inputs.html",
        "",
        {
            "login_user": "technician",
            "pws": "",
            "todo": "login",
            "this_file": "login.html",
            "language": "en",
            "passwd": "",
            "cur_passwd": "",
        },
    ),
]
# fmt: on


@pytest.mark.parametrize(
    "desc,fixture,form_selector,expected",
    EXTRACT_CASES,
    ids=[c[0] for c in EXTRACT_CASES],
)
def test_extract_form_fields(
    desc: str,
    fixture: str,
    form_selector: str,
    expected: dict[str, str],
) -> None:
    """extract_form_fields returns the expected field dict."""
    html = _load(fixture)
    result = extract_form_fields(html, form_selector)
    assert result == expected


# ---------------------------------------------------------------------------
# Table-driven: extract_hidden_fields() — type="hidden" inputs only
# ---------------------------------------------------------------------------

# fmt: off
# (description, fixture_file, form_selector, expected)
HIDDEN_FIELD_CASES = [
    (
        "hidden_inputs_only",
        "single_form_hidden.html",
        "",
        {"tok": "x", "mode": "login"},
    ),
    (
        "no_hidden_inputs",
        "text_and_password.html",
        "",
        {},
    ),
    (
        "mixed_types_extracts_hidden_only",
        "mixed_inputs.html",
        "",
        {
            "todo": "login",
            "this_file": "login.html",
            "language": "en",
            "passwd": "",
            "cur_passwd": "",
        },
    ),
    (
        "multi_form_with_selector",
        "multiple_forms_with_hidden.html",
        "form#login",
        {"webToken": "csrf123"},
    ),
    (
        "multi_form_no_selector_first_wins",
        "multiple_forms_with_hidden.html",
        "",
        {},  # first form (search) has no hidden inputs
    ),
    (
        "empty_html",
        "empty.html",
        "",
        {},
    ),
]
# fmt: on


@pytest.mark.parametrize(
    "desc,fixture,form_selector,expected",
    HIDDEN_FIELD_CASES,
    ids=[c[0] for c in HIDDEN_FIELD_CASES],
)
def test_extract_hidden_fields(
    desc: str,
    fixture: str,
    form_selector: str,
    expected: dict[str, str],
) -> None:
    """extract_hidden_fields returns only type='hidden' input fields."""
    html = _load(fixture)
    result = extract_hidden_fields(html, form_selector)
    assert result == expected


# ---------------------------------------------------------------------------
# Table-driven: detect_form_selector() — multi-form CSS selector detection
# ---------------------------------------------------------------------------

# fmt: off
# (description, fixture_file, post_action, expected_selector)
FORM_SELECTOR_CASES = [
    (
        "single_form_no_selector_needed",
        "single_form_hidden.html",
        "/goform/login",
        "",
    ),
    (
        "multi_form_id_selector",
        "multiple_forms_with_hidden.html",
        "/goform/login",
        "form#login",
    ),
    (
        "multi_form_name_selector",
        "multiple_forms_name_attr.html",
        "/goform/login",
        'form[name="loginForm"]',
    ),
    (
        "multi_form_action_fallback",
        "multiple_forms_action_only.html",
        "/goform/login",
        'form[action="/goform/login"]',
    ),
    (
        "multi_form_no_action_match",
        "multiple_forms_with_hidden.html",
        "/unknown/endpoint",
        "",
    ),
    (
        "empty_html",
        "empty.html",
        "/goform/login",
        "",
    ),
]
# fmt: on


@pytest.mark.parametrize(
    "desc,fixture,post_action,expected",
    FORM_SELECTOR_CASES,
    ids=[c[0] for c in FORM_SELECTOR_CASES],
)
def test_detect_form_selector(
    desc: str,
    fixture: str,
    post_action: str,
    expected: str,
) -> None:
    """detect_form_selector returns CSS selector only for multi-form pages."""
    html = _load(fixture)
    result = detect_form_selector(html, post_action)
    assert result == expected
