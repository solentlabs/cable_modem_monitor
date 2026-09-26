"""Characterization: form_nonce credential-encoding setup.

Setup-time work only form_nonce has: pre-fetch the login page, detect
whether credentials go as plain fields or base64-packed into a hidden
field, and store the result on the auth config. Rows pin the runtime
re-apply (``apply_setup_params``, fed the entry-data shape HA stores),
the login form analyser, and the test harness runner's pre-fetch, which
runs the same Core detection the HA config flow calls.

Pinned so the move to a strategy-module setup entry point
(ARCHITECTURE_DECISIONS § Strategy knowledge lives with the strategy)
can prove nothing changed.

TEST DATA TABLES
================
This module uses table-driven tests. Tables are defined at the top
of the file with ASCII box-drawing comments for readability.
"""

from __future__ import annotations

from typing import Any

import pytest
from solentlabs.cable_modem_monitor_core.auth.form_nonce import _analyze_login_form
from solentlabs.cable_modem_monitor_core.auth.setup import apply_setup_params
from solentlabs.cable_modem_monitor_core.test_harness.runner import _run_setup_detection

from ._characterization import RecordingServer, build_modem_config

# =============================================================================
# Auth blocks and login pages
# =============================================================================

FORM_NONCE = {"strategy": "form_nonce", "action": "/login", "nonce_field": "nonce"}
FORM_NONCE_PACKED = {**FORM_NONCE, "credential_encoding": "b64_packed", "credential_field": "prev"}

OTHER_STRATEGIES: list[dict[str, Any] | None] = [
    None,
    {"strategy": "basic"},
    {"strategy": "bearer", "login_endpoint": "/api/login", "token_path": "token"},
    {"strategy": "form", "action": "/login"},
    {"strategy": "form_cbn"},
    {"strategy": "form_pbkdf2", "login_endpoint": "/api/login", "pbkdf2_iterations": 1000, "pbkdf2_key_length": 128},
    {"strategy": "form_sjcl", "login_endpoint": "/login", "pbkdf2_iterations": 1000, "pbkdf2_key_length": 128},
    {"strategy": "hnap", "hmac_algorithm": "md5"},
    {
        "strategy": "json_sjcl",
        "login_page": "/login.php",
        "login_endpoint": "/login",
        "pbkdf2_iterations": 1000,
        "pbkdf2_key_length": 128,
        "aad": "AAD",
        "token_header": "X-Token",
    },
    {"strategy": "none"},
    {"strategy": "url_token", "login_page": "/login.html"},
]

PAGE_PLAIN = '<form><input name="username"><input name="password"><input type="hidden" name="nonce" value=""></form>'
PAGE_PACKED = '<form><input type="hidden" name="nonce" value=""><input type="hidden" name="arguments" value=""></form>'
PAGE_FILLED = '<form><input type="hidden" name="nonce" value=""><input type="hidden" name="csrf" value="x"></form>'
PAGE_NO_FORM = "<html><body>login</body></html>"
PAGE_EMPTY = ""

# =============================================================================
# Test Data Tables
# =============================================================================

# ┌───────────────────┬──────────────────────────┬────────────────────────────┬──────────────────────────────┐
# │ start config      │ stored params            │ result (encoding, field)   │ description                  │
# ├───────────────────┼──────────────────────────┼────────────────────────────┼──────────────────────────────┤
# │ plain, ""         │ plain                    │ plain, ""                  │ plain stays plain            │
# │ plain, ""         │ b64_packed, arguments    │ b64_packed, arguments      │ packed sets both             │
# │ b64_packed, prev  │ plain                    │ plain, ""                  │ plain clears the old field   │
# │ plain, ""         │ unknown value            │ plain, ""                  │ anything else reads plain    │
# └───────────────────┴──────────────────────────┴────────────────────────────┴──────────────────────────────┘
#
# fmt: off
APPLY_FORM_NONCE_CASES = [
    # (auth,              encoding,     field,       expected_encoding, expected_field, id)
    (FORM_NONCE,          "plain",      "",          "plain",           "",             "plain"),
    (FORM_NONCE,          "b64_packed", "arguments", "b64_packed",      "arguments",    "packed"),
    # Sanctioned change: plain always carries an empty field, so it no
    # longer leaves a stale one (no catalog entry sets credential_field).
    (FORM_NONCE_PACKED,   "plain",      "",          "plain",           "",             "plain_over_packed"),
    (FORM_NONCE,          "other",      "arguments", "plain",           "",             "unknown_encoding"),
]
# fmt: on

# ┌──────────────────────┬────────────────────────────┬──────────────────────────────────┐
# │ login page           │ detection (encoding, field)│ description                      │
# ├──────────────────────┼────────────────────────────┼──────────────────────────────────┤
# │ named username input │ plain, ""                  │ credentials are form fields      │
# │ empty hidden input   │ b64_packed, arguments      │ packed credential field          │
# │ only filled hiddens  │ plain, ""                  │ no empty non-nonce hidden        │
# │ no <form>            │ plain, ""                  │ nothing to analyse               │
# │ empty body           │ plain, ""                  │ nothing to analyse               │
# └──────────────────────┴────────────────────────────┴──────────────────────────────────┘
#
# fmt: off
DETECTION_CASES = [
    # (page,                  encoding,     field,       id)
    (PAGE_PLAIN,              "plain",      "",          "plain"),
    (PAGE_PACKED,             "b64_packed", "arguments", "packed"),
    (PAGE_FILLED,   "plain",      "",          "prefilled_hidden"),
    (PAGE_NO_FORM,            "plain",      "",          "no_form"),
    (PAGE_EMPTY,              "plain",      "",          "empty"),
]
# fmt: on

# ┌──────────────────────┬───────────────────┬────────────────────────────┬──────────────────────────────┐
# │ login page           │ start config      │ config after runner detect │ description                  │
# ├──────────────────────┼───────────────────┼────────────────────────────┼──────────────────────────────┤
# │ named username input │ b64_packed, prev  │ plain, ""                  │ detection overwrites both    │
# │ empty hidden input   │ plain, ""         │ b64_packed, arguments      │ detection overwrites both    │
# │ no <form>            │ b64_packed, prev  │ plain, ""                  │ fallback overwrites both     │
# │ empty body           │ b64_packed, prev  │ plain, ""                  │ fallback overwrites both     │
# └──────────────────────┴───────────────────┴────────────────────────────┴──────────────────────────────┘
#
# fmt: off
RUNNER_CASES = [
    # (page,          auth,               encoding,     field,       id)
    (PAGE_PLAIN,      FORM_NONCE_PACKED,  "plain",      "",          "plain"),
    (PAGE_PACKED,     FORM_NONCE,         "b64_packed", "arguments", "packed"),
    (PAGE_NO_FORM,    FORM_NONCE_PACKED,  "plain",      "",          "no_form"),
    # Sanctioned change: the runner now runs the config flow's detection
    # (ARCHITECTURE § Core Extraction Pipeline: harness and runtime run
    # identical code), which reads an empty page as plain.
    (PAGE_EMPTY,      FORM_NONCE_PACKED,  "plain",      "",          "empty_body"),
]
# fmt: on


def _other_id(auth: dict[str, Any] | None) -> str:
    return auth["strategy"] if auth else "no_auth"


class TestApplySetupParams:
    """``apply_setup_params`` writes form_nonce config and nothing else."""

    @pytest.mark.parametrize(
        "auth,encoding,field,expected_encoding,expected_field,desc",
        APPLY_FORM_NONCE_CASES,
        ids=[c[5] for c in APPLY_FORM_NONCE_CASES],
    )
    def test_form_nonce(
        self,
        auth: dict[str, Any],
        encoding: str,
        field: str,
        expected_encoding: str,
        expected_field: str,
        desc: str,
    ) -> None:
        """The form_nonce auth block ends in the recorded state."""
        config = build_modem_config(auth)
        apply_setup_params(config, {"credential_encoding": encoding, "credential_field": field})
        assert config.auth is not None
        assert config.auth.model_dump()["credential_encoding"] == expected_encoding, desc
        assert config.auth.model_dump()["credential_field"] == expected_field, desc

    @pytest.mark.parametrize("auth", OTHER_STRATEGIES, ids=[_other_id(a) for a in OTHER_STRATEGIES])
    def test_other_strategies_untouched(self, auth: dict[str, Any] | None) -> None:
        """Every other strategy, and no auth block, leaves the config byte-identical."""
        config = build_modem_config(auth)
        before = config.model_dump()
        apply_setup_params(config, {"credential_encoding": "b64_packed", "credential_field": "arguments"})
        assert config.model_dump() == before


class TestLoginFormDetection:
    """``_analyze_login_form`` classifies login pages as recorded."""

    @pytest.mark.parametrize(
        "page,encoding,field,desc",
        DETECTION_CASES,
        ids=[c[3] for c in DETECTION_CASES],
    )
    def test_analyze(self, page: str, encoding: str, field: str, desc: str) -> None:
        """The analyser returns the recorded encoding and credential field."""
        detection = _analyze_login_form(page, "username", "nonce")
        assert (detection.encoding, detection.credential_field) == (encoding, field), desc


class TestRunnerDetection:
    """The test harness runner's pre-fetch detection writes the auth config as recorded."""

    @pytest.mark.parametrize(
        "page,auth,encoding,field,desc",
        RUNNER_CASES,
        ids=[c[4] for c in RUNNER_CASES],
    )
    def test_runner_detect(self, page: str, auth: dict[str, Any], encoding: str, field: str, desc: str) -> None:
        """The runner GETs the form action and stores the detection on the config."""
        config = build_modem_config(auth)
        with RecordingServer("text/html", page) as server:
            _run_setup_detection(config, server.base_url)

        assert [(r.method, r.path) for r in server.requests] == [("GET", "/login")], desc
        assert config.auth is not None
        assert config.auth.model_dump()["credential_encoding"] == encoding, desc
        assert config.auth.model_dump()["credential_field"] == field, desc

    @pytest.mark.parametrize("auth", OTHER_STRATEGIES, ids=[_other_id(a) for a in OTHER_STRATEGIES])
    def test_runner_skips_other_strategies(self, auth: dict[str, Any] | None) -> None:
        """Other strategies make no request and keep their config."""
        config = build_modem_config(auth)
        before = config.model_dump()
        with RecordingServer("text/html", PAGE_PACKED) as server:
            _run_setup_detection(config, server.base_url)

        assert server.requests == []
        assert config.model_dump() == before
