"""Tests for auth grading: pipeline-generated auth block vs committed."""

from __future__ import annotations

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.analysis.auth.grading import grade_auth

_FORM_AUTH = {
    "strategy": "form",
    "action": "/check.jst",
    "username_field": "username",
    "password_field": "password",
    "cookie_name": "DUKSID",
    "success": {"redirect": "/at_a_glance.jst"},
}


@pytest.mark.parametrize(
    ("generated", "committed", "expected"),
    [
        # Neither side has auth (public status pages) — nothing to grade
        (None, None, {}),
        # Committed auth the pipeline did not produce
        (None, _FORM_AUTH, {"strategy": "committed_only"}),
        # Generated auth the catalog never adopted
        (_FORM_AUTH, None, {"strategy": "pipeline_only"}),
        # Full reproduction
        (_FORM_AUTH, _FORM_AUTH, {"strategy": "match", "fields": "match"}),
        # Wrong strategy: fields comparison is meaningless, so it is omitted
        ({**_FORM_AUTH, "strategy": "form_nonce"}, _FORM_AUTH, {"strategy": "mismatch"}),
        # Right strategy, committed field not produced (coda56 login_page case)
        (
            {k: v for k, v in _FORM_AUTH.items() if k != "cookie_name"},
            _FORM_AUTH,
            {"strategy": "match", "fields": "partial"},
        ),
        # Right strategy, generated extra field the catalog never adopted
        ({**_FORM_AUTH, "hidden_fields": {"pws": "nologin"}}, _FORM_AUTH, {"strategy": "match", "fields": "partial"}),
        # Right strategy, field value differs (xb10 redirect-slash case)
        (
            {**_FORM_AUTH, "success": {"redirect": "at_a_glance.jst"}},
            _FORM_AUTH,
            {"strategy": "match", "fields": "partial"},
        ),
        # Strategy-only blocks (hnap-style) — nothing else to compare
        ({"strategy": "hnap"}, {"strategy": "hnap"}, {"strategy": "match", "fields": "match"}),
    ],
)
def test_grade_auth(
    generated: dict | None,
    committed: dict | None,
    expected: dict[str, str],
) -> None:
    """Each generated/committed pair grades to the expected statuses."""
    grades = grade_auth(generated, committed)
    assert {item: grade.status for item, grade in grades.items()} == expected


def test_non_match_grades_carry_detail() -> None:
    """Every non-match grade names what differs."""
    generated = {k: v for k, v in _FORM_AUTH.items() if k != "cookie_name"}
    grades = grade_auth(generated, _FORM_AUTH)
    assert "cookie_name" in grades["fields"].detail


def test_mismatch_detail_names_both_strategies() -> None:
    """A strategy mismatch states both sides."""
    grades = grade_auth({"strategy": "form"}, {"strategy": "form_pbkdf2"})
    assert "form" in grades["strategy"].detail
    assert "form_pbkdf2" in grades["strategy"].detail
