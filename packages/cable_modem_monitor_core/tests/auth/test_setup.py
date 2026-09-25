"""Tests for the generic setup-time dispatch in ``auth/setup.py``.

A strategy with setup entry points (form_nonce) gets its page fetched,
its params detected and applied; every other strategy is a no-op.

TEST DATA TABLES
================
This module uses table-driven tests. Tables are defined at the top
of the file with ASCII box-drawing comments for readability.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests
from solentlabs.cable_modem_monitor_core.auth.setup import (
    apply_setup_params,
    detect_setup_params,
    detect_setup_params_from_html,
    setup_param_keys,
)
from solentlabs.cable_modem_monitor_core.models.modem_config import ModemConfig

from .conftest import load_html_fixture

_CREATE_SESSION = "solentlabs.cable_modem_monitor_core.connectivity.create_session"
_BASE_URL = "http://192.168.100.1"

FORM_NONCE = {"strategy": "form_nonce", "action": "/login", "nonce_field": "ar_nonce"}

NO_SETUP_STEP: list[dict[str, Any] | None] = [
    None,
    {"strategy": "none"},
    {"strategy": "basic"},
    {"strategy": "form", "action": "/login"},
    {"strategy": "url_token", "login_page": "/login.html"},
]

PLAIN = {"credential_encoding": "plain", "credential_field": ""}
PACKED = {"credential_encoding": "b64_packed", "credential_field": "arguments"}


def _config(auth: dict[str, Any] | None) -> ModemConfig:
    """Minimal valid http-transport modem config around an auth block."""
    return ModemConfig.model_validate(
        {
            "manufacturer": "Solent Labs",
            "model": "T100",
            "transport": "http",
            "default_host": "192.168.100.1",
            "status": "unsupported",
            "auth": auth,
        }
    )


def _auth_state(config: ModemConfig) -> tuple[str, str]:
    dump = config.auth.model_dump() if config.auth else {}
    return dump["credential_encoding"], dump["credential_field"]


def _session_returning(text: str) -> MagicMock:
    session = MagicMock()
    session.get.return_value = MagicMock(text=text)
    return session


def _session_raising(exc: Exception) -> MagicMock:
    session = MagicMock()
    session.get.side_effect = exc
    return session


def _no_setup_id(auth: dict[str, Any] | None) -> str:
    return auth["strategy"] if auth else "no_auth"


# =============================================================================
# Test Data Tables
# =============================================================================

# ┌──────────────────────────┬──────────────────┬──────────────────────────────┐
# │ login page               │ params           │ description                  │
# ├──────────────────────────┼──────────────────┼──────────────────────────────┤
# │ named username input     │ plain            │ credentials are form fields  │
# │ empty hidden input       │ packed           │ packed credential field      │
# │ no <form>                │ plain            │ nothing to analyse           │
# │ not HTML at all          │ plain            │ garbage reads plain          │
# │ empty body               │ plain            │ nothing to analyse           │
# └──────────────────────────┴──────────────────┴──────────────────────────────┘
#
# fmt: off
HTML_CASES = [
    # (page,                                       params,  id)
    (load_html_fixture("login_form_plain.html"),   PLAIN,   "plain"),
    (load_html_fixture("login_form_b64.html"),     PACKED,  "packed"),
    (load_html_fixture("login_form_no_form.html"), PLAIN,   "no_form"),
    ("\x00\xff<<not html>>",                       PLAIN,   "garbage"),
    ("",                                           PLAIN,   "empty"),
]
# fmt: on

# ┌─────────────────────────────┬──────────────────────────┬─────────────────────────────┐
# │ GET outcome                 │ result                   │ description                 │
# ├─────────────────────────────┼──────────────────────────┼─────────────────────────────┤
# │ packed page                 │ packed params            │ detection on the page       │
# │ requests.ConnectionError    │ raises ConnectionError   │ unreachable modem surfaces  │
# │ requests.Timeout            │ raises ConnectionError   │ unresponsive modem surfaces │
# │ any other exception         │ plain params             │ strategy's empty-page read  │
# └─────────────────────────────┴──────────────────────────┴─────────────────────────────┘
#
# fmt: off
FETCH_CASES = [
    # (session,                                                        expected,         id)
    (_session_returning(load_html_fixture("login_form_b64.html")),     PACKED,           "packed_page"),
    (_session_raising(requests.ConnectionError("refused")),            ConnectionError,  "connection_error"),
    (_session_raising(requests.Timeout("timed out")),                  ConnectionError,  "timeout"),
    (_session_raising(ValueError("unexpected")),                       PLAIN,            "other_error"),
]
# fmt: on

# ┌──────────────────┬──────────────────────────────┬──────────────────────┬─────────────────────────────────┐
# │ start config     │ params                       │ result               │ description                     │
# ├──────────────────┼──────────────────────────────┼──────────────────────┼─────────────────────────────────┤
# │ plain, ""        │ packed                       │ b64_packed, arguments│ packed sets both                │
# │ b64_packed, prev │ plain                        │ plain, ""            │ detected plain clears the field │
# │ b64_packed, prev │ encoding plain, no field key │ plain, ""            │ plain always clears the field   │
# │ plain, ""        │ {}                           │ plain, ""            │ missing keys read plain         │
# │ plain, ""        │ entry-data shape             │ b64_packed, arguments│ unrelated keys ignored          │
# └──────────────────┴──────────────────────────────┴──────────────────────┴─────────────────────────────────┘
#
# fmt: off
FORM_NONCE_PACKED = {**FORM_NONCE, "credential_encoding": "b64_packed", "credential_field": "prev"}
APPLY_CASES = [
    # (auth,              params,                              expected,                    id)
    (FORM_NONCE,          PACKED,                              ("b64_packed", "arguments"), "packed"),
    (FORM_NONCE_PACKED,   PLAIN,                               ("plain", ""),               "plain_clears_field"),
    (FORM_NONCE_PACKED,   {"credential_encoding": "plain"},    ("plain", ""),               "plain_without_field"),
    (FORM_NONCE,          {},                                  ("plain", ""),               "empty_params"),
    (FORM_NONCE,          {"host": "h", "password": "p", **PACKED}, ("b64_packed", "arguments"), "entry_data_shape"),
]
# fmt: on


class TestDetectFromHtml:
    """``detect_setup_params_from_html`` returns the strategy's params, or none."""

    @pytest.mark.parametrize("page,params,desc", HTML_CASES, ids=[c[2] for c in HTML_CASES])
    def test_form_nonce(self, page: str, params: dict[str, str], desc: str) -> None:
        """form_nonce classifies the page."""
        assert detect_setup_params_from_html(_config(FORM_NONCE), page) == params, desc

    @pytest.mark.parametrize("auth", NO_SETUP_STEP, ids=[_no_setup_id(a) for a in NO_SETUP_STEP])
    def test_no_setup_step(self, auth: dict[str, Any] | None) -> None:
        """A strategy without entry points has no params."""
        page = load_html_fixture("login_form_b64.html")
        assert detect_setup_params_from_html(_config(auth), page) == {}


class TestDetectFetch:
    """``detect_setup_params`` fetches the setup page and classifies the outcome."""

    @pytest.mark.parametrize("session,expected,desc", FETCH_CASES, ids=[c[2] for c in FETCH_CASES])
    def test_fetch_outcome(self, session: MagicMock, expected: Any, desc: str) -> None:
        """Connectivity failures raise; other failures take the plain fallback."""
        with patch(_CREATE_SESSION, return_value=session):
            if isinstance(expected, type):
                with pytest.raises(expected):
                    detect_setup_params(_config(FORM_NONCE), _BASE_URL)
            else:
                assert detect_setup_params(_config(FORM_NONCE), _BASE_URL) == expected, desc

    def test_request_shape(self) -> None:
        """GETs base_url + the strategy's setup page on a session built with legacy_ssl."""
        session = _session_returning("")
        with patch(_CREATE_SESSION, return_value=session) as create:
            detect_setup_params(_config(FORM_NONCE), _BASE_URL, legacy_ssl=True)

        create.assert_called_once_with(legacy_ssl=True)
        session.get.assert_called_once_with(f"{_BASE_URL}/login", timeout=10)

    @pytest.mark.parametrize("auth", NO_SETUP_STEP, ids=[_no_setup_id(a) for a in NO_SETUP_STEP])
    def test_no_setup_step_makes_no_request(self, auth: dict[str, Any] | None) -> None:
        """A strategy without entry points never opens a session."""
        with patch(_CREATE_SESSION) as create:
            assert detect_setup_params(_config(auth), _BASE_URL) == {}
        create.assert_not_called()


class TestApply:
    """``apply_setup_params`` sets params on the strategy config, or does nothing."""

    @pytest.mark.parametrize("auth,params,expected,desc", APPLY_CASES, ids=[c[3] for c in APPLY_CASES])
    def test_form_nonce(
        self,
        auth: dict[str, Any],
        params: dict[str, Any],
        expected: tuple[str, str],
        desc: str,
    ) -> None:
        """form_nonce config ends in the expected state."""
        config = _config(auth)
        apply_setup_params(config, params)
        assert _auth_state(config) == expected, desc

    @pytest.mark.parametrize("auth", NO_SETUP_STEP, ids=[_no_setup_id(a) for a in NO_SETUP_STEP])
    def test_no_setup_step(self, auth: dict[str, Any] | None) -> None:
        """Other strategies keep their config byte-identical."""
        config = _config(auth)
        before = config.model_dump()
        apply_setup_params(config, PACKED)
        assert config.model_dump() == before


class TestSetupParamKeys:
    """``setup_param_keys`` names the params a strategy stores."""

    def test_form_nonce(self) -> None:
        """form_nonce stores encoding and field."""
        assert setup_param_keys(_config(FORM_NONCE)) == ("credential_encoding", "credential_field")

    @pytest.mark.parametrize("auth", NO_SETUP_STEP, ids=[_no_setup_id(a) for a in NO_SETUP_STEP])
    def test_no_setup_step(self, auth: dict[str, Any] | None) -> None:
        """Other strategies store nothing."""
        assert setup_param_keys(_config(auth)) == ()

    def test_unknown_strategy_module(self) -> None:
        """A strategy literal with no module has no setup step."""
        config = MagicMock()
        config.auth.strategy = "no_such_strategy"
        assert setup_param_keys(config) == ()
        assert detect_setup_params_from_html(config, "") == {}
