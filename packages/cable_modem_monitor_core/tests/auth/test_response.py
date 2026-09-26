"""Tests for auth.response shared JSON helpers."""

from __future__ import annotations

import json
import logging
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests
from solentlabs.cable_modem_monitor_core.auth.base import AuthResult
from solentlabs.cable_modem_monitor_core.auth.response import (
    matches_criteria,
    parse_json_dict,
    post_form,
    post_json,
    safe_preview,
)

_LONG_STRING = "x" * 300


def _mock_response(
    *,
    json_value: Any = None,
    json_error: bool = False,
    text: str = "",
    status_code: int = 200,
) -> MagicMock:
    """Build a mock Response for response helper tests."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.text = text
    if json_error:
        resp.json.side_effect = ValueError("not json")
    else:
        resp.json.return_value = json_value
    return resp


# ── safe_preview ─────────────────────────────────────────────


class TestSafePreview:
    """safe_preview() value truncation."""

    # ┌───────────────────┬────────────────┬──────────────────────────┐
    # │ value             │ expected_in    │ description              │
    # ├───────────────────┼────────────────┼──────────────────────────┤
    # │ "short"           │ "short"        │ short string unchanged   │
    # │ 42                │ "42"           │ integer value            │
    # │ None              │ "None"         │ None value               │
    # │ [1, 2]            │ "[1, 2]"       │ list value               │
    # │ {"a": 1}          │ "{'a': 1}"     │ dict value               │
    # └───────────────────┴────────────────┴──────────────────────────┘
    #
    # fmt: off
    PREVIEW_CASES = [
        ("short",   "short",    "short string unchanged"),
        (42,        "42",       "integer value"),
        (None,      "None",     "None value"),
        ([1, 2],    "[1, 2]",   "list value"),
        ({"a": 1},  "{'a': 1}", "dict value"),
    ]
    # fmt: on

    @pytest.mark.parametrize(
        "value,expected_in,desc",
        PREVIEW_CASES,
        ids=[c[2] for c in PREVIEW_CASES],
    )
    def test_preview_contains_value(
        self,
        value: object,
        expected_in: str,
        desc: str,
    ) -> None:
        """Preview contains expected representation."""
        result = safe_preview(value)
        assert expected_in in result

    def test_long_string_truncated(self) -> None:
        """Long values are truncated with ellipsis."""
        result = safe_preview(_LONG_STRING)
        assert result.endswith("...")
        assert len(result) == 203  # 200 + "..."

    def test_custom_max_len(self) -> None:
        """Custom max_len overrides default."""
        result = safe_preview("a" * 50, max_len=10)
        assert len(result) == 13  # 10 + "..."
        assert result.endswith("...")


# ── parse_json_dict ──────────────────────────────────────────


class TestParseJsonDict:
    """parse_json_dict() response parsing."""

    def test_success_returns_dict(self) -> None:
        """Dict response returns parsed dict."""
        resp = _mock_response(json_value={"ok": True}, text='{"ok": true}')
        result = parse_json_dict(resp)
        assert isinstance(result, dict)
        assert result == {"ok": True}

    def test_not_json_returns_auth_result(self) -> None:
        """Non-JSON response returns AuthResult with body preview."""
        resp = _mock_response(json_error=True, text="<html>Login Required</html>")
        result = parse_json_dict(resp)
        assert isinstance(result, AuthResult)
        assert result.success is False
        assert "not valid json" in result.error.lower()
        assert "Login Required" in result.error
        assert result.response is resp

    # ┌───────────────────────────────────┬──────────┬──────────────────┬───────────────────┐
    # │ json_value                        │ exp_type │ exp_preview      │ description       │
    # ├───────────────────────────────────┼──────────┼──────────────────┼───────────────────┤
    # │ "NOSESSION"                       │ "str"    │ "NOSESSION"      │ modem error str   │
    # │ _LONG_STRING                      │ "str"    │ "xxx"            │ long str truncated│
    # │ [1, 2, 3]                         │ "list"   │ "[1, 2, 3]"      │ list value        │
    # │ 42                                │ "int"    │ "42"             │ integer value     │
    # │ True                              │ "bool"   │ "True"           │ boolean value     │
    # │ None                              │ "NoneType"│ "None"          │ null value        │
    # └───────────────────────────────────┴──────────┴──────────────────┴───────────────────┘
    #
    # fmt: off
    NON_DICT_CASES = [
        ("NOSESSION",       "str",      "NOSESSION",    "modem error string"),
        (_LONG_STRING,      "str",      "xxx",          "long string truncated"),
        ([1, 2, 3],         "list",     "[1, 2, 3]",    "list value"),
        (42,                "int",      "42",           "integer value"),
        (True,              "bool",     "True",         "boolean value"),
        (None,              "NoneType", "None",         "null value"),
    ]
    # fmt: on

    @pytest.mark.parametrize(
        "json_value,expected_type,expected_preview,desc",
        NON_DICT_CASES,
        ids=[c[3] for c in NON_DICT_CASES],
    )
    def test_non_dict_error_includes_type_and_preview(
        self,
        json_value: object,
        expected_type: str,
        expected_preview: str,
        desc: str,
    ) -> None:
        """Non-dict JSON returns error with type name and value preview."""
        resp = _mock_response(json_value=json_value, text=str(json_value))
        result = parse_json_dict(resp)
        assert isinstance(result, AuthResult)
        assert result.success is False
        assert "expected json object" in result.error.lower()
        assert expected_type in result.error
        assert expected_preview in result.error
        assert result.response is resp

    def test_long_string_preview_truncated(self) -> None:
        """Long non-dict string values are truncated in the error."""
        resp = _mock_response(json_value=_LONG_STRING, text=_LONG_STRING)
        result = parse_json_dict(resp)
        assert isinstance(result, AuthResult)
        assert result.success is False
        assert len(result.error) < 400
        assert "..." in result.error

    def test_double_encoded_json_unwrapped(self) -> None:
        """Double-encoded JSON string wrapping a dict is unwrapped."""
        inner = json.dumps({"status": "ok"})
        resp = _mock_response(json_value=inner, text=json.dumps(inner))
        result = parse_json_dict(resp)
        assert isinstance(result, dict)
        assert result == {"status": "ok"}

    def test_double_encoded_non_dict_fails(self) -> None:
        """Double-encoded value that unwraps to non-dict still fails."""
        inner = json.dumps([1, 2, 3])
        resp = _mock_response(json_value=inner, text=json.dumps(inner))
        result = parse_json_dict(resp)
        assert isinstance(result, AuthResult)
        assert result.success is False
        assert "list" in result.error

    def test_context_in_error_message(self) -> None:
        """Context label appears in error message."""
        resp = _mock_response(json_error=True, text="bad")
        result = parse_json_dict(resp, context="Salt response")
        assert isinstance(result, AuthResult)
        assert "Salt response" in result.error

    def test_status_code_in_error(self) -> None:
        """HTTP status code is included in error message."""
        resp = _mock_response(json_error=True, text="err", status_code=500)
        result = parse_json_dict(resp)
        assert isinstance(result, AuthResult)
        assert "500" in result.error

    def test_debug_log_on_response(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Response body is logged at DEBUG level."""
        resp = _mock_response(
            json_value={"ok": True},
            text='{"ok": true}',
        )
        with caplog.at_level(
            logging.DEBUG,
            logger="solentlabs.cable_modem_monitor_core.auth.response",
        ):
            parse_json_dict(resp)

        assert any("200" in r.message for r in caplog.records)

    def test_type_error_caught(self) -> None:
        """TypeError from response.json() is caught like ValueError."""
        resp = _mock_response(text="")
        resp.json.side_effect = TypeError("unexpected")
        result = parse_json_dict(resp)
        assert isinstance(result, AuthResult)
        assert result.success is False
        assert "not valid json" in result.error.lower()


# ── post_json / post_form ────────────────────────────────────

# Both helpers share the same POST→parse contract. Parametrize
# over both to avoid duplicated tests.

# fmt: off
_POST_FUNCTIONS = [
    pytest.param(post_json, id="post_json"),
    pytest.param(post_form, id="post_form"),
]
# fmt: on


class TestPostHelpers:
    """post_json() and post_form() — shared POST + parse contract."""

    @pytest.mark.parametrize("post_fn", _POST_FUNCTIONS)
    def test_success_returns_tuple(
        self,
        session: requests.Session,
        post_fn: Any,
    ) -> None:
        """Dict response returns (response, data) tuple."""
        resp = _mock_response(json_value={"ok": True}, text='{"ok": true}')
        with patch.object(session, "post", return_value=resp):
            result = post_fn(session, "http://modem/api", {}, 10)
        assert isinstance(result, tuple)
        assert result[1] == {"ok": True}

    @pytest.mark.parametrize("post_fn", _POST_FUNCTIONS)
    def test_connection_error_propagates(
        self,
        session: requests.Session,
        post_fn: Any,
    ) -> None:
        """ConnectionError propagates for collector."""
        with (
            patch.object(
                session,
                "post",
                side_effect=requests.ConnectionError("refused"),
            ),
            pytest.raises(requests.ConnectionError),
        ):
            post_fn(session, "http://modem/api", {}, 10)

    @pytest.mark.parametrize("post_fn", _POST_FUNCTIONS)
    def test_timeout_propagates(
        self,
        session: requests.Session,
        post_fn: Any,
    ) -> None:
        """Timeout propagates for collector."""
        with (
            patch.object(
                session,
                "post",
                side_effect=requests.Timeout("timed out"),
            ),
            pytest.raises(requests.Timeout),
        ):
            post_fn(session, "http://modem/api", {}, 10)

    @pytest.mark.parametrize("post_fn", _POST_FUNCTIONS)
    def test_other_request_error(
        self,
        session: requests.Session,
        post_fn: Any,
    ) -> None:
        """Non-connectivity RequestException returns AuthResult.

        Error must include the exception class name so log analysis can
        distinguish HTTP-layer errors (HTTPError, ChunkedEncodingError,
        etc.) from generic transport failures at a glance.
        """
        with patch.object(
            session,
            "post",
            side_effect=requests.RequestException("other"),
        ):
            result = post_fn(session, "http://modem/api", {}, 10)
        assert isinstance(result, AuthResult)
        assert result.success is False
        assert "POST failed" in result.error
        assert "RequestException" in result.error

    # Each row: (exception_class, exception_arg, expected_type_name).
    # Covers RequestException subclasses that bypass the
    # ConnectionError/Timeout re-raise gate and are wrapped into
    # AuthResult.
    _NON_CONNECTIVITY_EXCEPTIONS = [
        (requests.HTTPError, "503 server error", "HTTPError"),
        (requests.TooManyRedirects, "redirect loop", "TooManyRedirects"),
        (requests.exceptions.ChunkedEncodingError, "bad chunk", "ChunkedEncodingError"),
        (requests.exceptions.ContentDecodingError, "gzip failed", "ContentDecodingError"),
        (requests.RequestException, "generic", "RequestException"),
    ]

    @pytest.mark.parametrize("post_fn", _POST_FUNCTIONS)
    @pytest.mark.parametrize(
        "exc_class,exc_arg,expected_type_name",
        _NON_CONNECTIVITY_EXCEPTIONS,
        ids=[c[2] for c in _NON_CONNECTIVITY_EXCEPTIONS],
    )
    def test_error_includes_exception_class_name(
        self,
        session: requests.Session,
        post_fn: Any,
        exc_class: type[Exception],
        exc_arg: str,
        expected_type_name: str,
    ) -> None:
        """AuthResult.error includes the raised exception's class name."""
        with patch.object(session, "post", side_effect=exc_class(exc_arg)):
            result = post_fn(session, "http://modem/api", {}, 10)
        assert isinstance(result, AuthResult)
        assert result.success is False
        assert expected_type_name in result.error

    @pytest.mark.parametrize("post_fn", _POST_FUNCTIONS)
    def test_not_json_error(
        self,
        session: requests.Session,
        post_fn: Any,
    ) -> None:
        """Non-JSON response returns error with body preview."""
        resp = _mock_response(
            json_error=True,
            text="<html>Login Required</html>",
        )
        with patch.object(session, "post", return_value=resp):
            result = post_fn(session, "http://modem/api", {}, 10)
        assert isinstance(result, AuthResult)
        assert "not valid json" in result.error.lower()
        assert "Login Required" in result.error

    @pytest.mark.parametrize("post_fn", _POST_FUNCTIONS)
    def test_non_dict_error(
        self,
        session: requests.Session,
        post_fn: Any,
    ) -> None:
        """Non-dict JSON returns error with type and preview."""
        resp = _mock_response(
            json_value="NOSESSION",
            text='"NOSESSION"',
        )
        with patch.object(session, "post", return_value=resp):
            result = post_fn(session, "http://modem/api", {}, 10)
        assert isinstance(result, AuthResult)
        assert "expected json object" in result.error.lower()
        assert "NOSESSION" in result.error

    @pytest.mark.parametrize("post_fn", _POST_FUNCTIONS)
    def test_long_preview_truncated(
        self,
        session: requests.Session,
        post_fn: Any,
    ) -> None:
        """Long non-dict value is truncated in error."""
        resp = _mock_response(json_value=_LONG_STRING, text=_LONG_STRING)
        with patch.object(session, "post", return_value=resp):
            result = post_fn(session, "http://modem/api", {}, 10)
        assert isinstance(result, AuthResult)
        assert len(result.error) < 400
        assert "..." in result.error

    @pytest.mark.parametrize("post_fn", _POST_FUNCTIONS)
    def test_double_encoded_json(
        self,
        session: requests.Session,
        post_fn: Any,
    ) -> None:
        """Double-encoded JSON string wrapping a dict is unwrapped."""
        inner = json.dumps({"p_status": "AdminMatch"})
        resp = _mock_response(json_value=inner, text=json.dumps(inner))
        with patch.object(session, "post", return_value=resp):
            result = post_fn(session, "http://modem/api", {}, 10)
        assert isinstance(result, tuple)
        assert result[1] == {"p_status": "AdminMatch"}

    @pytest.mark.parametrize("post_fn", _POST_FUNCTIONS)
    def test_default_context_includes_url(
        self,
        session: requests.Session,
        caplog: pytest.LogCaptureFixture,
        post_fn: Any,
    ) -> None:
        """Default context label includes the POST URL."""
        resp = _mock_response(json_value={"ok": True}, text='{"ok": true}')
        with (
            caplog.at_level(
                logging.DEBUG,
                logger="solentlabs.cable_modem_monitor_core.auth.response",
            ),
            patch.object(session, "post", return_value=resp),
        ):
            post_fn(session, "http://modem/api", {}, 10)

        assert any("POST http://modem/api" in r.message for r in caplog.records)


# ── matches_criteria ─────────────────────────────────────────


class TestMatchesCriteria:
    """matches_criteria() subset match shared by login_busy and login_success."""

    # ┌──────────────────────────────┬──────────────────────────────┬──────────┬─────────────────────────┐
    # │ body                         │ criterion                    │ expected │ description             │
    # ├──────────────────────────────┼──────────────────────────────┼──────────┼─────────────────────────┤
    # │ {"result": "busy", "x": 1}   │ {"result": "busy"}           │ True     │ all pairs match         │
    # │ {"result": "ok", "code": 7}  │ {"result": "ok", "code": 8}  │ False    │ one pair mismatches     │
    # │ {"code": 7}                  │ {"result": "busy"}           │ False    │ criterion key missing   │
    # │ {"result": None}             │ {"result": None}             │ True     │ explicit None matches   │
    # │ {"result": "ok"}             │ {}                           │ True     │ empty criterion matches │
    # └──────────────────────────────┴──────────────────────────────┴──────────┴─────────────────────────┘
    #
    # fmt: off
    MATCH_CASES = [
        ({"result": "busy", "x": 1},  {"result": "busy"},          True,  "all pairs match"),
        ({"result": "ok", "code": 7}, {"result": "ok", "code": 8}, False, "one pair mismatches"),
        ({"code": 7},                 {"result": "busy"},          False, "criterion key missing"),
        ({"result": None},            {"result": None},            True,  "explicit None matches"),
        ({"result": "ok"},            {},                          True,  "empty criterion matches"),
    ]
    # fmt: on

    @pytest.mark.parametrize(
        "body,criterion,expected,desc",
        MATCH_CASES,
        ids=[c[3] for c in MATCH_CASES],
    )
    def test_matches_criteria(
        self,
        body: dict[str, Any],
        criterion: dict[str, Any],
        expected: bool,
        desc: str,
    ) -> None:
        """True only when every criterion pair is present in the body."""
        assert matches_criteria(body, criterion) is expected

    def test_non_dict_body_raises(self) -> None:
        """A non-dict body raises; callers only pass parse_json_dict's dict."""
        body: Any = ["result", "busy"]
        with pytest.raises(AttributeError):
            matches_criteria(body, {"result": "busy"})
