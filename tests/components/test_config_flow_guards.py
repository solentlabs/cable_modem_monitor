"""Tests for the config flow's guard aborts, state helpers and options cooloff.

Completes the 100% config-flow coverage HA's quality scale asks for
(config-flow-test-coverage). Guards the UI cannot reach (a selector
offering only valid values, a step entered without its prior state)
are driven by calling the step on a bare flow; paths the UI can reach
go through HA's flow machinery as in test_config_flow.py.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.cable_modem_monitor.config_flow import (
    CableModemMonitorConfigFlow,
    OptionsFlowHandler,
)
from custom_components.cable_modem_monitor.const import DOMAIN
from tests.ha_harness import MockConfigEntry

from .conftest import (
    FAKE_CATALOG,
    MOCK_ENTRY_DATA,
    MOCK_MULTI_VARIANTS,
    MOCK_SINGLE_VARIANT,
    MOCK_SUMMARIES,
    start_add_modem,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

_CF = "custom_components.cable_modem_monitor.config_flow"
_TPS2000, _TPS3000 = MOCK_SUMMARIES
_UNKNOWN_MODEL_DATA = {**MOCK_ENTRY_DATA, "model": "Retired-1000"}


def _bare_flow(hass: HomeAssistant, **state: Any) -> Any:
    """A config flow outside the flow manager, with the given attributes preset."""
    flow: Any = CableModemMonitorConfigFlow()
    flow.hass = hass
    flow.flow_id = "test_flow"
    flow.handler = DOMAIN
    flow.context = {"source": config_entries.SOURCE_USER}
    for name, value in state.items():
        setattr(flow, name, value)
    return flow


# -----------------------------------------------------------------------
# Guard aborts — steps entered with missing or invalid state
# -----------------------------------------------------------------------

# ┌──────────────────────────┬──────────────────────────────────┬─────────────────┬──────────────────────────────┐
# │ step                     │ state / input                    │ abort reason    │ description                  │
# ├──────────────────────────┼──────────────────────────────────┼─────────────────┼──────────────────────────────┤
# │ async_step_model         │ model not in catalog             │ unknown_model   │ stale model key              │
# │ async_step_detect_confirm│ no detection plan                │ missing_input   │ entered without detection    │
# │ async_step_detect_pick   │ no detection plan                │ missing_input   │ entered without detection    │
# │ async_step_detect_pick   │ index past the candidates        │ unknown_model   │ out-of-range pick            │
# │ async_step_variant       │ variant key not offered          │ unknown_variant │ stale variant key            │
# │ async_step_custom_config │ no connection input              │ missing_input   │ entered without Step 3       │
# │ async_step_reauth_confirm│ no entry_id in context           │ reauth_failed   │ reauth without an entry      │
# │ async_step_reauth_confirm│ entry_id not registered          │ reauth_failed   │ entry removed mid-flow       │
# │ _async_validate          │ no connection input              │ missing_input   │ validate without Step 3      │
# └──────────────────────────┴──────────────────────────────────┴─────────────────┴──────────────────────────────┘
#
_ONE_CANDIDATE_PLAN = SimpleNamespace(route="pick", tier_1=[MagicMock()])

# fmt: off
GUARD_CASES = [
    # (step, state, context, user_input, reason, id)
    ("async_step_model", {"_summaries": MOCK_SUMMARIES}, {}, {"model": "Nobody/Nothing"},
     "unknown_model", "model_not_in_catalog"),
    ("async_step_detect_confirm", {}, {}, None,
     "missing_input", "confirm_without_plan"),
    ("async_step_detect_pick", {}, {}, None,
     "missing_input", "pick_without_plan"),
    ("async_step_detect_pick", {"_detect_plan": _ONE_CANDIDATE_PLAN}, {}, {"model": "5"},
     "unknown_model", "pick_out_of_range"),
    ("async_step_variant", {"_variants": MOCK_MULTI_VARIANTS}, {}, {"variant": "no-such-variant"},
     "unknown_variant", "variant_not_offered"),
    ("async_step_custom_config", {}, {}, None,
     "missing_input", "custom_without_connection"),
    ("async_step_reauth_confirm", {}, {}, None,
     "reauth_failed", "reauth_without_entry_id"),
    ("async_step_reauth_confirm", {}, {"entry_id": "not-there"}, None,
     "reauth_failed", "reauth_entry_gone"),
    ("_async_validate", {}, {}, ...,
     "missing_input", "validate_without_connection"),
]
# fmt: on


@pytest.mark.parametrize(
    "step,state,context,user_input,reason",
    [c[:5] for c in GUARD_CASES],
    ids=[c[5] for c in GUARD_CASES],
)
async def test_guard_aborts(
    hass: HomeAssistant,
    step: str,
    state: dict[str, Any],
    context: dict[str, Any],
    user_input: Any,
    reason: str,
) -> None:
    """A step entered without the state it needs aborts with its reason."""
    flow = _bare_flow(hass, **state)
    flow.context.update(context)
    method = getattr(flow, step)
    # Ellipsis marks a method that takes no user_input argument.
    with patch(f"{_CF}.CATALOG_PATH", FAKE_CATALOG):
        result: Any = await (method() if user_input is ... else method(user_input))
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_reauth_aborts_when_model_left_catalog(hass: HomeAssistant) -> None:
    """Reauth on an entry whose model is no longer in the catalog aborts."""
    entry = MockConfigEntry(domain=DOMAIN, version=2, data=_UNKNOWN_MODEL_DATA)
    entry.add_to_hass(hass)

    with (
        patch("custom_components.cable_modem_monitor.async_setup_entry", return_value=True),
        patch(f"{_CF}.load_modem_catalog", return_value=MOCK_SUMMARIES),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        result: Any = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
            data=entry.data,
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"host": "192.168.100.1", "username": "admin", "password": "pw"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_failed"


async def test_options_aborts_when_model_left_catalog(hass: HomeAssistant) -> None:
    """Options submit on an entry whose model is no longer in the catalog aborts."""
    entry = MockConfigEntry(domain=DOMAIN, version=2, data=_UNKNOWN_MODEL_DATA, options={})
    entry.add_to_hass(hass)

    with (
        patch("custom_components.cable_modem_monitor.async_setup_entry", return_value=True),
        patch(f"{_CF}.load_modem_catalog", return_value=MOCK_SUMMARIES),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        result: Any = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "host": "192.168.100.1",
                "username": "admin",
                "password": "pw",
                "scan_interval": {"hours": 0, "minutes": 10, "seconds": 0},
                "health_check_interval": {"hours": 0, "minutes": 0, "seconds": 30},
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown_model"


async def test_model_without_variants_uses_summary_dir(hass: HomeAssistant) -> None:
    """A model with no variant files goes straight to Step 3 from its summary directory."""
    with (
        patch(f"{_CF}.load_modem_catalog", return_value=MOCK_SUMMARIES),
        patch(f"{_CF}.load_variant_list", return_value=[]),
        patch(f"{_CF}.CATALOG_PATH", FAKE_CATALOG),
    ):
        result: Any = await start_add_modem(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"manufacturer": "__all__"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"model": "Solent Labs/TPS-2000", "entity_prefix": "none"},
        )
        flow: Any = hass.config_entries.flow._progress[result["flow_id"]]

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connection"
    assert flow._selected_modem_dir == _TPS2000.path


# -----------------------------------------------------------------------
# State helpers — auth strategy, modem directory, credential fields
# -----------------------------------------------------------------------

# ┌───────────────┬──────────────────┬──────────────────────┬─────────────┬──────────────────────────────┐
# │ modem dir set │ selected variant │ variants             │ summary     │ expected strategy            │
# ├───────────────┼──────────────────┼──────────────────────┼─────────────┼──────────────────────────────┤
# │ no            │ "v2"             │ multi                │ —           │ form_nonce (named variant)   │
# │ no            │ "gone"           │ multi                │ —           │ none (no match)              │
# │ no            │ —                │ multi                │ —           │ basic (first variant)        │
# │ no            │ —                │ —                    │ TPS-3000    │ basic (summary default)      │
# │ no            │ —                │ —                    │ —           │ none (nothing selected)      │
# └───────────────┴──────────────────┴──────────────────────┴─────────────┴──────────────────────────────┘
#
# fmt: off
AUTH_STRATEGY_CASES = [
    # (state,                                                             expected,     id)
    ({"_selected_variant": "v2",   "_variants": MOCK_MULTI_VARIANTS},     "form_nonce", "named_variant"),
    ({"_selected_variant": "gone", "_variants": MOCK_MULTI_VARIANTS},     "none",       "named_variant_missing"),
    ({"_variants": MOCK_MULTI_VARIANTS},                                  "basic",      "first_variant"),
    ({"_selected_summary": _TPS3000},                                     "basic",      "summary_default"),
    ({},                                                                  "none",       "nothing_selected"),
]
# fmt: on


@pytest.mark.parametrize(
    "state,expected",
    [c[:2] for c in AUTH_STRATEGY_CASES],
    ids=[c[2] for c in AUTH_STRATEGY_CASES],
)
def test_selected_auth_strategy(hass: HomeAssistant, state: dict[str, Any], expected: str) -> None:
    """The auth strategy falls back from directory match to variant, first variant, summary, none."""
    assert _bare_flow(hass, **state)._get_selected_auth_strategy() == expected


def test_selected_modem_dir_falls_back_to_summary(hass: HomeAssistant) -> None:
    """Before Step 2 the modem directory is the summary's."""
    assert _bare_flow(hass, _selected_summary=_TPS2000)._get_selected_modem_dir() == _TPS2000.path


def test_selected_modem_dir_without_selection_raises(hass: HomeAssistant) -> None:
    """With nothing selected there is no modem directory."""
    with pytest.raises(ValueError, match="No modem directory selected"):
        _bare_flow(hass)._get_selected_modem_dir()


async def test_restart_credentials_without_selection_is_false(hass: HomeAssistant) -> None:
    """With no modem selected, restart needs no credentials and no file is read."""
    flow = _bare_flow(hass, _restart_needs_credentials=True)
    with patch(f"{_CF}.restart_requires_credentials") as reader:
        await flow._resolve_restart_credentials()
    assert flow._restart_needs_credentials is False
    reader.assert_not_called()


def test_custom_config_always_shows_credentials(hass: HomeAssistant) -> None:
    """A custom config may change the login strategy, so its form asks for credentials."""
    assert _bare_flow(hass, _custom_config=True)._shows_credentials() is True


def test_restart_credentials_add_fields_to_unauthenticated_form(hass: HomeAssistant) -> None:
    """A no-auth modem whose restart needs auth still gets username and password fields."""
    flow = _bare_flow(
        hass,
        _selected_summary=_TPS2000,
        _variants=MOCK_SINGLE_VARIANT,
        _restart_needs_credentials=True,
    )
    fields = {str(key) for key in flow._build_connection_schema().schema}
    assert {"username", "password"} <= fields


# -----------------------------------------------------------------------
# Options cooloff — wait for a quiet modem before re-authenticating
# -----------------------------------------------------------------------


class _FakeClock:
    """Monotonic clock that advances only when the code under test sleeps."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class _FakeHealth:
    """HealthMonitor stand-in: busy for the first ``busy_reads`` checks."""

    def __init__(self, clock: _FakeClock, busy_reads: int, success_age: float | None) -> None:
        self._busy_reads = busy_reads
        self.last_collection_success_at = None if success_age is None else clock.now - success_age

    @property
    def collection_active(self) -> bool:
        self._busy_reads -= 1
        return self._busy_reads >= 0


# ┌────────────┬────────────────────┬──────────────────────┬─────────────────────────────────┐
# │ busy reads │ last success age   │ expected sleeps      │ description                     │
# ├────────────┼────────────────────┼──────────────────────┼─────────────────────────────────┤
# │ 0          │ never              │ []                   │ idle, never polled              │
# │ 0          │ 60 s               │ []                   │ quiet long enough               │
# │ 0          │ 2 s                │ [3.0]                │ waits out the quiet window      │
# │ 2          │ never              │ [0.5, 0.5]           │ waits for collection to finish  │
# │ 1000       │ never              │ 60 × 0.5             │ gives up at the 30 s timeout    │
# └────────────┴────────────────────┴──────────────────────┴─────────────────────────────────┘
#
# fmt: off
COOLOFF_CASES = [
    # (busy_reads, success_age, expected_sleeps, id)
    (0,    None, [],          "idle_never_polled"),
    (0,    60.0, [],          "already_quiet"),
    (0,    2.0,  [3.0],       "waits_quiet_window"),
    (2,    None, [0.5, 0.5],  "waits_for_collection"),
    (1000, None, [0.5] * 60,  "times_out"),
]
# fmt: on


@pytest.mark.parametrize(
    "busy_reads,success_age,expected_sleeps",
    [c[:3] for c in COOLOFF_CASES],
    ids=[c[3] for c in COOLOFF_CASES],
)
async def test_wait_for_quiet_modem(busy_reads: int, success_age: float | None, expected_sleeps: list[float]) -> None:
    """Validation waits for no active collection and a 5 s quiet window, at most 30 s."""
    clock = _FakeClock()
    health = _FakeHealth(clock, busy_reads, success_age)
    entry: Any = SimpleNamespace(runtime_data=SimpleNamespace(health_monitor=health))
    with (
        patch(f"{_CF}.time", SimpleNamespace(monotonic=clock.monotonic)),
        patch(f"{_CF}.asyncio", SimpleNamespace(sleep=clock.sleep)),
    ):
        await OptionsFlowHandler()._wait_for_quiet_modem(entry)
    assert clock.sleeps == expected_sleeps


@pytest.mark.parametrize(
    "entry",
    [SimpleNamespace(), SimpleNamespace(runtime_data=SimpleNamespace(health_monitor=None))],
    ids=["no_runtime_data", "no_health_monitor"],
)
async def test_wait_for_quiet_modem_without_health_returns(entry: Any) -> None:
    """With no health monitor there is nothing to wait for."""
    clock = _FakeClock()
    with patch(f"{_CF}.asyncio", SimpleNamespace(sleep=clock.sleep)):
        await OptionsFlowHandler()._wait_for_quiet_modem(entry)
    assert clock.sleeps == []
