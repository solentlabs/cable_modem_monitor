"""Tests for the custom config setup path (CONFIG_FLOW_SPEC § Custom Config Setup).

TEST DATA TABLES
================
Catalog sync and YAML parsing are table-driven; tables sit at the top
of the file. Flow, repair and diagnostics tests follow.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry
from solentlabs.cable_modem_monitor_catalog import CATALOG_PATH

from custom_components.cable_modem_monitor.config_flow_helpers import (
    CustomAttempt,
    _run_custom_attempt,
    async_brand_icon_url,
)
from custom_components.cable_modem_monitor.const import (
    CONF_CUSTOM_BASE_VERSION,
    CONF_CUSTOM_BASE_YAML,
    CONF_CUSTOM_MODEM_YAML,
    DOMAIN,
)
from custom_components.cable_modem_monitor.custom_config import (
    CustomYamlError,
    build_report,
    capture_attempt,
    catalog_sync_action,
    parse_modem_yaml,
)
from custom_components.cable_modem_monitor.diagnostics import _custom_config_section
from custom_components.cable_modem_monitor.repairs import async_sync_with_catalog

from .conftest import FAKE_CATALOG, MOCK_ENTRY_DATA, MOCK_SINGLE_VARIANT, MOCK_SUMMARIES, MOCK_VALIDATION_RESULT

_CF = "custom_components.cable_modem_monitor.config_flow"
_REPAIRS = "custom_components.cable_modem_monitor.repairs"

# Any catalog modem.yaml: the tests need valid text, not a particular modem.
_CATALOG_YAML = next(iter(sorted(CATALOG_PATH.glob("**/modem.yaml")))).read_text(encoding="utf-8")

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

# =============================================================================
# Test Data Tables
# =============================================================================

# ┌───────────────────────┬───────────────────┬───────────────────┬─────────┬──────────────────────────┐
# │ catalog               │ user              │ base              │ action  │ description              │
# ├───────────────────────┼───────────────────┼───────────────────┼─────────┼──────────────────────────┤
# │ a: 1                  │ a: 1              │ a: 0              │ adopt   │ catalog caught up        │
# │ a: 1  # comment       │ a: 1              │ a: 0              │ adopt   │ comments don't count     │
# │ {b: 2, a: 1}          │ a: 1\nb: 2        │ a: 0              │ adopt   │ key order doesn't count  │
# │ a: 2                  │ a: 1              │ a: 0              │ repair  │ catalog changed, differs │
# │ a: 0                  │ a: 1              │ a: 0              │ keep    │ catalog unchanged        │
# │ a: 0                  │ a: 1              │ "a: 0  # old"     │ keep    │ base comments ignored    │
# └───────────────────────┴───────────────────┴───────────────────┴─────────┴──────────────────────────┘
#
# fmt: off
SYNC_CASES = [
    ("a: 1\n",            "a: 1\n",       "a: 0\n",          "adopt",  "catalog caught up"),
    ("a: 1  # comment\n", "a: 1\n",       "a: 0\n",          "adopt",  "comments don't count"),
    ("{b: 2, a: 1}\n",    "a: 1\nb: 2\n", "a: 0\n",          "adopt",  "key order doesn't count"),
    ("a: 2\n",            "a: 1\n",       "a: 0\n",          "repair", "catalog changed, differs"),
    ("a: 0\n",            "a: 1\n",       "a: 0\n",          "keep",   "catalog unchanged"),
    ("a: 0\n",            "a: 1\n",       "a: 0  # old\n",   "keep",   "base comments ignored"),
]
# fmt: on

# ┌──────────────────────────┬──────────────────────┬──────────────────────┐
# │ text                     │ message fragment     │ description          │
# ├──────────────────────────┼──────────────────────┼──────────────────────┤
# │ "a: [1"                  │ "YAML syntax"        │ not YAML             │
# │ "- 1"                    │ "mapping"            │ not a mapping        │
# │ "unknown_key: 1"         │ "schema"             │ fails ModemConfig    │
# └──────────────────────────┴──────────────────────┴──────────────────────┘
#
# fmt: off
BAD_YAML_CASES = [
    ("a: [1",          "YAML syntax", "not YAML"),
    ("- 1\n",          "mapping",     "not a mapping"),
    ("unknown_key: 1", "schema",      "fails ModemConfig"),
]
# fmt: on


# =============================================================================
# Pure helpers
# =============================================================================


@pytest.mark.parametrize(("catalog", "user", "base", "action", "desc"), SYNC_CASES, ids=[c[-1] for c in SYNC_CASES])
def test_catalog_sync_action(catalog: str, user: str, base: str, action: str, desc: str):
    """The startup rule compares parsed YAML (CONFIG_FLOW_SPEC § Custom Config Setup)."""
    assert catalog_sync_action(catalog_text=catalog, user_text=user, base_text=base) == action, desc


@pytest.mark.parametrize(("text", "fragment", "desc"), BAD_YAML_CASES, ids=[c[-1] for c in BAD_YAML_CASES])
def test_parse_modem_yaml_rejects(text: str, fragment: str, desc: str):
    """Bad text raises CustomYamlError before anything reaches the modem."""
    with pytest.raises(CustomYamlError, match=fragment):
        parse_modem_yaml(text)


def test_parse_modem_yaml_accepts_catalog_text():
    """Catalog text is valid custom config text."""
    assert parse_modem_yaml(_CATALOG_YAML) is not None


def test_capture_attempt_keeps_this_threads_debug_records_and_restores_levels():
    """DEBUG records from the attempt's thread are captured; other threads' are not."""
    core = logging.getLogger("solentlabs.cable_modem_monitor_core.test")
    parent = logging.getLogger("solentlabs.cable_modem_monitor_core")
    level_before = parent.level

    with capture_attempt() as records:
        core.debug("from the attempt")
        other = threading.Thread(target=lambda: core.debug("from another thread"))
        other.start()
        other.join()

    assert [r.getMessage() for r in records] == ["from the attempt"]
    assert parent.level == level_before


def test_capture_attempt_keeps_added_debug_lines_out_of_has_log():
    """HA's handlers get only what they got before the capture; the report gets every line."""
    package = logging.getLogger("solentlabs.cable_modem_monitor_core")
    child = logging.getLogger("solentlabs.cable_modem_monitor_core.test")
    package.setLevel(logging.INFO)
    seen: list[str] = []

    class _Sink(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            seen.append(record.getMessage())

    sink = _Sink(logging.DEBUG)
    logging.getLogger().addHandler(sink)
    try:
        with capture_attempt() as records:
            child.debug("detail only the report should hold")
            child.warning("a line HA logs anyway")
    finally:
        logging.getLogger().removeHandler(sink)

    assert [r.getMessage() for r in records] == ["detail only the report should hold", "a line HA logs anyway"]
    assert seen == ["a line HA logs anyway"]
    assert package.propagate is True


def test_build_report_scrubs_and_sanitizes():
    """The report goes through the caller's scrub and the diagnostics sanitizer."""
    record = logging.LogRecord(
        "solentlabs.cable_modem_monitor_core.auth", logging.WARNING, "", 0, "sent s3cret to 10.1.2.3", None, None
    )

    report = build_report(
        version="9.9.9",
        catalog_file="maker/model/modem.yaml",
        host="https://192.168.100.1",
        outcome="invalid_auth",
        records=[record],
        scrub=lambda text: text.replace("s3cret", "[REDACTED]"),
    )

    assert "custom config report" in report
    assert "outcome: invalid_auth" in report
    assert "s3cret" not in report
    assert "10.1.2.3" not in report


def test_run_custom_attempt_reports_the_failure_and_its_records():
    """A failed attempt returns the exception and every record it logged, scrubbed of the password."""

    def failing_validation(*args: Any) -> dict[str, Any]:
        logging.getLogger("solentlabs.cable_modem_monitor_core.auth").info("posting pw-123")
        raise PermissionError("auth_error:invalid_auth:rejected")

    with patch("custom_components.cable_modem_monitor.config_flow_helpers._run_validation", failing_validation):
        attempt = _run_custom_attempt("192.168.100.1", None, "admin", "pw-123", Path("/x"), None, "a: 1")

    assert attempt.validation is None
    assert isinstance(attempt.error, PermissionError)
    assert [r.getMessage() for r in attempt.records] == ["posting pw-123"]
    assert attempt.scrub("posting pw-123") == "posting [REDACTED]"


# =============================================================================
# Config flow — custom config path
# =============================================================================


async def _reach_custom_config_step(hass: HomeAssistant) -> Any:
    """Menu → custom config → manufacturer → model → connection → the custom_config form."""
    result: Any = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "custom_config_start"}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={"manufacturer": "__all__"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"model": "Solent Labs/TPS-2000", "entity_prefix": "none"}
    )
    return await hass.config_entries.flow.async_configure(result["flow_id"], user_input={"host": "192.168.100.1"})


def _flow_patches(attempt: CustomAttempt) -> Any:
    """Catalog, variant list and attempt stubs for a custom config flow."""
    return (
        patch(f"{_CF}.load_modem_catalog", return_value=MOCK_SUMMARIES),
        patch(f"{_CF}.load_variant_list", return_value=MOCK_SINGLE_VARIANT),
        patch(f"{_CF}.CATALOG_PATH", FAKE_CATALOG),
        patch(f"{_CF}.read_variant_yaml", return_value=_CATALOG_YAML),
        patch(f"{_CF}.run_custom_attempt", AsyncMock(return_value=attempt)),
        patch("custom_components.cable_modem_monitor.async_setup_entry", return_value=True),
    )


async def test_first_screen_offers_both_setup_paths(hass: HomeAssistant):
    """The first screen is a menu: Add modem, or Add modem with custom config."""
    result: Any = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})

    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["manufacturer", "custom_config_start"]


async def test_custom_path_opens_the_editor_with_the_catalog_text(hass: HomeAssistant):
    """After Step 3 the custom path shows the variant's modem.yaml instead of validating."""
    failed = CustomAttempt(validation=None, error=None, records=[], scrub=lambda t: t)
    p = _flow_patches(failed)
    with p[0], p[1], p[2], p[3], p[4] as attempt_mock, p[5]:
        result: Any = await _reach_custom_config_step(hass)

    assert result["step_id"] == "custom_config"
    defaults = {str(k): k.default() for k in result["data_schema"].schema}
    assert defaults["modem_config"] == _CATALOG_YAML
    attempt_mock.assert_not_called()


async def test_failed_attempt_keeps_the_form_and_logs_one_report(hass: HomeAssistant, caplog: pytest.LogCaptureFixture):
    """A failure re-shows the form with the error and writes the report as one WARNING."""
    failed = CustomAttempt(
        validation=None, error=PermissionError("auth_error:invalid_auth:rejected"), records=[], scrub=lambda t: t
    )
    p = _flow_patches(failed)
    with p[0], p[1], p[2], p[3], p[4], p[5]:
        result: Any = await _reach_custom_config_step(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"modem_config": "edited: true"}
        )

    assert result["step_id"] == "custom_config"
    assert result["errors"] == {"base": "custom_attempt_failed"}
    reports = [r for r in caplog.records if "custom config report" in r.getMessage()]
    assert len(reports) == 1
    assert reports[0].levelno == logging.WARNING
    assert "host: 192.168.100.1" in reports[0].getMessage()
    assert "outcome: invalid_auth: rejected" in reports[0].getMessage()


async def test_passing_attempt_creates_the_entry_with_the_custom_fields(hass: HomeAssistant):
    """A pass creates the entry carrying the user's text, its base, and the base version."""
    passed = CustomAttempt(validation=dict(MOCK_VALIDATION_RESULT), error=None, records=[], scrub=lambda t: t)
    p = _flow_patches(passed)
    with p[0], p[1], p[2], p[3], p[4], p[5]:
        result: Any = await _reach_custom_config_step(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"modem_config": "edited: true"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CUSTOM_MODEM_YAML] == "edited: true"
    assert result["data"][CONF_CUSTOM_BASE_YAML] == _CATALOG_YAML
    assert result["data"][CONF_CUSTOM_BASE_VERSION]


# =============================================================================
# Options flow — editing a saved custom entry
# =============================================================================


async def _configure_custom_entry(hass: HomeAssistant, attempt: CustomAttempt, modem_config: str) -> tuple[Any, Any]:
    """Open Configure on a custom entry and submit ``modem_config``; return (entry, result)."""
    entry = _custom_entry(hass, user="a: 1\n", base="a: 0\n")
    with (
        patch(f"{_CF}.CATALOG_PATH", FAKE_CATALOG),
        patch(f"{_CF}.run_custom_attempt", AsyncMock(return_value=attempt)),
        patch("custom_components.cable_modem_monitor.async_setup_entry", return_value=True),
    ):
        result: Any = await hass.config_entries.options.async_init(entry.entry_id)
        form = {str(k): k.default() for k in result["data_schema"].schema}
        form.update(modem_config=modem_config, password="")
        result = await hass.config_entries.options.async_configure(result["flow_id"], user_input=form)
    return entry, result


async def test_configure_shows_the_saved_config_on_custom_entries_only(hass: HomeAssistant):
    """A custom entry's Configure opens custom_config with its text; an ordinary entry's has no config field."""
    custom = _custom_entry(hass, user="a: 1\n", base="a: 0\n")
    ordinary = MockConfigEntry(domain=DOMAIN, data=dict(MOCK_ENTRY_DATA))
    ordinary.add_to_hass(hass)

    custom_form: Any = await hass.config_entries.options.async_init(custom.entry_id)
    ordinary_form: Any = await hass.config_entries.options.async_init(ordinary.entry_id)

    assert custom_form["step_id"] == "custom_config"
    assert {str(k): k.default() for k in custom_form["data_schema"].schema}["modem_config"] == "a: 1\n"
    assert ordinary_form["step_id"] == "init"
    assert "modem_config" not in {str(k) for k in ordinary_form["data_schema"].schema}


async def test_configure_failure_logs_the_report_and_saves_nothing(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
):
    """A failed test re-shows the form with the user's text and leaves the entry as it was."""
    failed = CustomAttempt(
        validation=None, error=PermissionError("auth_error:invalid_auth:rejected"), records=[], scrub=lambda t: t
    )

    entry, result = await _configure_custom_entry(hass, failed, "a: 2\n")

    assert result["step_id"] == "custom_config"
    assert result["errors"] == {"base": "custom_attempt_failed"}
    assert {str(k): k.default() for k in result["data_schema"].schema}["modem_config"] == "a: 2\n"
    assert len([r for r in caplog.records if "custom config report" in r.getMessage()]) == 1
    assert entry.data[CONF_CUSTOM_MODEM_YAML] == "a: 1\n"


async def test_configure_pass_saves_the_text_and_keeps_the_base(hass: HomeAssistant):
    """A pass stores the new text; the base text, base version and password stay."""
    passed = CustomAttempt(validation=dict(MOCK_VALIDATION_RESULT), error=None, records=[], scrub=lambda t: t)

    entry, result = await _configure_custom_entry(hass, passed, "a: 2\n")

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data[CONF_CUSTOM_MODEM_YAML] == "a: 2\n"
    assert entry.data[CONF_CUSTOM_BASE_YAML] == "a: 0\n"
    assert entry.data[CONF_CUSTOM_BASE_VERSION] == "1"
    assert entry.data["password"] == MOCK_ENTRY_DATA["password"]


# =============================================================================
# Startup catalog sync
# =============================================================================


def _custom_fields(*, user: str, base: str) -> dict[str, str]:
    """The three entry fields a custom config setup stores."""
    return {CONF_CUSTOM_MODEM_YAML: user, CONF_CUSTOM_BASE_YAML: base, CONF_CUSTOM_BASE_VERSION: "1"}


def _custom_entry(hass: HomeAssistant, *, user: str, base: str) -> MockConfigEntry:
    """A custom config entry added to hass."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_ENTRY_DATA, **_custom_fields(user=user, base=base)},
    )
    entry.add_to_hass(hass)
    return entry


async def test_sync_adopts_an_identical_catalog_file_and_notifies(hass: HomeAssistant):
    """Catalog equal to the user's text: custom fields dropped, user notified."""
    entry = _custom_entry(hass, user="a: 1\n", base="a: 0\n")
    calls = MagicMock()
    hass.services.async_register("persistent_notification", "create", calls)

    with patch(f"{_REPAIRS}.read_variant_yaml", return_value="a: 1  # now in the catalog\n"):
        await async_sync_with_catalog(hass, entry)
        await hass.async_block_till_done()

    assert CONF_CUSTOM_MODEM_YAML not in entry.data
    assert calls.call_count == 1


async def test_sync_raises_a_repair_when_the_catalog_changed(hass: HomeAssistant):
    """Catalog changed and differs from the user's text: fixable repair, custom fields kept."""
    entry = _custom_entry(hass, user="a: 1\n", base="a: 0\n")

    with patch(f"{_REPAIRS}.read_variant_yaml", return_value="a: 2\n"):
        await async_sync_with_catalog(hass, entry)

    issue = ir.async_get(hass).async_get_issue(DOMAIN, f"custom_config_catalog_changed_{entry.entry_id}")
    assert issue is not None and issue.is_fixable
    assert entry.data[CONF_CUSTOM_MODEM_YAML] == "a: 1\n"


async def test_sync_keeps_the_users_text_when_the_catalog_is_unchanged(hass: HomeAssistant):
    """Catalog unchanged since setup: nothing happens."""
    entry = _custom_entry(hass, user="a: 1\n", base="a: 0\n")

    with patch(f"{_REPAIRS}.read_variant_yaml", return_value="a: 0\n"):
        await async_sync_with_catalog(hass, entry)

    assert entry.data[CONF_CUSTOM_MODEM_YAML] == "a: 1\n"
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"custom_config_catalog_changed_{entry.entry_id}") is None


# =============================================================================
# Diagnostics
# =============================================================================


def test_diagnostics_carry_the_diff_for_custom_entries_only():
    """The custom_config block holds the base→user diff; other entries get none."""
    custom = {**MOCK_ENTRY_DATA, **_custom_fields(user="a: 1\n", base="a: 0\n")}

    section = _custom_config_section(custom)["custom_config"]

    assert "-a: 0" in section["diff"] and "+a: 1" in section["diff"]
    assert _custom_config_section(MOCK_ENTRY_DATA) == {}


async def test_sync_keeps_the_users_text_when_the_catalog_file_is_gone(hass: HomeAssistant):
    """A catalog that dropped the variant file leaves the custom config in use."""
    entry = _custom_entry(hass, user="a: 1\n", base="a: 0\n")

    with patch(f"{_REPAIRS}.read_variant_yaml", side_effect=FileNotFoundError("gone")):
        await async_sync_with_catalog(hass, entry)

    assert entry.data[CONF_CUSTOM_MODEM_YAML] == "a: 1\n"


async def test_unchanged_catalog_text_creates_an_ordinary_entry(hass: HomeAssistant):
    """Submitting the catalog text as-is (comments aside) stores no custom fields."""
    passed = CustomAttempt(validation=dict(MOCK_VALIDATION_RESULT), error=None, records=[], scrub=lambda t: t)
    p = _flow_patches(passed)
    with p[0], p[1], p[2], p[3], p[4], p[5]:
        result: Any = await _reach_custom_config_step(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"modem_config": _CATALOG_YAML + "# note\n"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_CUSTOM_MODEM_YAML not in result["data"]


async def test_brand_icon_is_served_once_and_skipped_without_http(hass: HomeAssistant):
    """The first screen's icon path is registered once; a headless HA gets no icon."""
    assert await async_brand_icon_url(hass) is None

    hass.config.components.add("http")
    hass.http = MagicMock(async_register_static_paths=AsyncMock())
    first = await async_brand_icon_url(hass)
    second = await async_brand_icon_url(hass)

    assert first == second == "/cable_modem_monitor/static/setup-icon.svg"
    hass.http.async_register_static_paths.assert_awaited_once()
