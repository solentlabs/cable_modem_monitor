"""Tests for the Auto-detect path of the config flow.

Contract: CONFIG_FLOW_SPEC.md § Auto-detect. Mocks: Core's ``detect()``
(the network sweep), the catalog loaders, ``validate_connection``.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from solentlabs.cable_modem_monitor_core.catalog_manager import ModemSummary
from solentlabs.cable_modem_monitor_core.detection import Candidate, Detection, Observation, PageMatch, Reply
from solentlabs.cable_modem_monitor_core.orchestration.events import DetectionChosen

from custom_components.cable_modem_monitor.config_flow_detect import code_span, describe_observations, plan_detection
from custom_components.cable_modem_monitor.const import DOMAIN

from .conftest import FAKE_CATALOG, MOCK_SINGLE_VARIANT, MOCK_VALIDATION_RESULT

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

_CF = "custom_components.cable_modem_monitor.config_flow"
_COMPONENT_DIR = Path(__file__).resolve().parents[2] / "custom_components" / "cable_modem_monitor"


def _summary(model: str, *, manufacturer: str = "Acme", host: str = "192.168.100.1") -> ModemSummary:
    return ModemSummary(
        manufacturer=manufacturer,
        model=model,
        default_host=host,
        auth_strategy="none",
        status="confirmed",
        path=FAKE_CATALOG / manufacturer.lower() / model.lower(),
    )


CATALOG = [_summary(f"M{i}") for i in range(1, 7)] + [_summary("Z1", manufacturer="Zeta", host="192.168.0.1")]
M1, M2, M3, M4, M5, M6, Z1 = CATALOG

OBSERVATION = Observation(
    scheme="http",
    status=200,
    final_path="/",
    server="micro_httpd",
    title="Login",
    www_authenticate=None,
    password_field=True,
)


def _detection(
    host: str,
    *,
    models: list[ModemSummary],
    named: list[str] | None = None,
    signals: list[str] | None = None,
    page_names: list[ModemSummary] | None = None,
) -> Detection:
    """An answering host whose tier-1 entries are ``models`` (``page_names`` of them named); the rest are tier 3."""
    candidates = [Candidate(m, 1, list(signals or []), named=m in (page_names or [])) for m in models]
    candidates.sort(key=lambda c: not c.named)
    candidates += [Candidate(m, 3) for m in CATALOG if m not in models]
    return Detection(
        host=host,
        observation=OBSERVATION,
        match=PageMatch(models, [], list(named or [])),
        reply=Reply([], [], None),
        candidates=candidates,
    )


H1, H2 = "192.168.100.1", "192.168.0.1"
_d = _detection


async def _start(hass: HomeAssistant, detections: list[Detection]) -> Any:
    """Open Step 1a and choose Auto-detect with ``detect()`` returning ``detections``."""
    with (
        patch(f"{_CF}.load_modem_catalog", return_value=CATALOG),
        patch(f"{_CF}.detect", return_value=detections),
    ):
        result: Any = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        return await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"manufacturer": "__detect__"}
        )


def _options(result: Any, field: str) -> list[dict[str, str]]:
    schema = result["data_schema"].schema
    key = next(k for k in schema if k == field)
    return list(schema[key].config["options"])


async def test_auto_detect_is_the_second_step_1a_option(hass: HomeAssistant):
    """Auto-detect sits below All while its matching is a best attempt."""
    with patch(f"{_CF}.load_modem_catalog", return_value=CATALOG):
        result: Any = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})

    values = [o["value"] for o in _options(result, "manufacturer")]
    assert values[:2] == ["__all__", "__detect__"]


async def test_detect_runs_in_an_executor_thread(hass: HomeAssistant):
    """The blocking sweep never runs on the event loop thread."""
    threads: list[threading.Thread] = []

    def fake_detect(summaries: list[ModemSummary]) -> list[Detection]:
        threads.append(threading.current_thread())
        return []

    with (
        patch(f"{_CF}.load_modem_catalog", return_value=CATALOG),
        patch(f"{_CF}.detect", fake_detect),
    ):
        result: Any = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        await hass.config_entries.flow.async_configure(result["flow_id"], user_input={"manufacturer": "__detect__"})

    assert len(threads) == 1
    assert threads[0] is not threading.main_thread()


# ┌──────────────────┬──────────────────────────────┬────────────────┐
# │ answers          │ tier-1 entries               │ next step      │
# ├──────────────────┼──────────────────────────────┼────────────────┤
# │ one host         │ 1                            │ detect_confirm │
# │ one host         │ 2                            │ detect_pick    │
# │ one host         │ 4                            │ detect_pick    │
# │ one host         │ 5                            │ model          │
# │ two hosts        │ the same entry on each       │ detect_pick    │
# │ one host         │ none                         │ user           │
# │ nothing answered │ -                            │ no_match       │
# └──────────────────┴──────────────────────────────┴────────────────┘
#
# fmt: off
ROUTE_CASES = [
    ([_d(H1, models=[M1])],                      "detect_confirm", "one_model"),
    ([_d(H1, models=[M1, M2])],                  "detect_pick",    "two_models"),
    ([_d(H1, models=[M1, M2, M3, M4])],          "detect_pick",    "four_models"),
    ([_d(H1, models=[M1, M2, M3, M4, M5])],      "model",          "five_models"),
    ([_d(H1, models=[M1]), _d(H2, models=[M1])], "detect_pick",    "same_model_two_hosts"),
    ([_d(H1, models=[])],                        "user",           "nothing_identified"),
    ([],                                         "no_match",       "nothing_answered"),
]
# fmt: on


@pytest.mark.parametrize(("detections", "step_id", "case_id"), ROUTE_CASES, ids=[c[-1] for c in ROUTE_CASES])
async def test_detection_routes_to_the_spec_page(
    hass: HomeAssistant, detections: list[Detection], step_id: str, case_id: str
):
    """The sweep result picks the page (CONFIG_FLOW_SPEC § Auto-detect flowchart)."""
    result: Any = await _start(hass, detections)

    assert result["type"] is FlowResultType.FORM
    assert result.get("step_id") == step_id


@pytest.mark.parametrize(("detections", "step_id", "case_id"), ROUTE_CASES, ids=[c[-1] for c in ROUTE_CASES])
def test_plan_matches_the_route(detections: list[Detection], step_id: str, case_id: str):
    """The pure planner and the flow agree on the page; the flow adds only what each page shows."""
    expected = {
        "detect_confirm": "confirm",
        "detect_pick": "pick",
        "model": "filtered_models",
        "user": "manufacturers",
        "no_match": "no_match",
    }

    assert plan_detection(detections).route == expected[step_id]


async def test_exactly_one_named_entry_gets_the_confirm_page_whatever_else_matched(hass: HomeAssistant):
    """Six tier-1 entries, one named: the page that spells a model outranks six shared signals."""
    result: Any = await _start(hass, [_d(H1, models=[M1, M2, M3, M4, M5, M6], page_names=[M4])])

    assert result.get("step_id") == "detect_confirm"
    assert result["description_placeholders"]["model"] == "Acme M4"


async def test_two_named_entries_are_a_choice_not_a_confirmation(hass: HomeAssistant):
    result: Any = await _start(hass, [_d(H1, models=[M1, M2, M3], page_names=[M2, M3])])

    assert result.get("step_id") == "detect_pick"
    assert [o["label"] for o in _options(result, "model")] == ["Acme M2", "Acme M3", "Acme M1"]


async def test_filtered_models_list_the_named_entries_first_not_alphabetically(hass: HomeAssistant):
    result: Any = await _start(hass, [_d(H1, models=[M1, M2, M3, M4, M5, M6], page_names=[M5, M6])])

    # Two named: no confirm page, and six entries open Step 1b with the named ones on top.
    assert result.get("step_id") == "model"
    assert [o["label"] for o in _options(result, "model")][:2] == ["Acme M5", "Acme M6"]


async def test_filtered_models_lists_only_the_tier_1_models(hass: HomeAssistant):
    """Five or more tier-1 entries open Step 1b with just those models."""
    result: Any = await _start(hass, [_detection("192.168.100.1", models=[M1, M2, M3, M4, M5])])

    labels = [o["label"] for o in _options(result, "model")]
    assert len(labels) == 5
    assert not any("M6" in label or "Z1" in label for label in labels)


async def test_nothing_identified_lands_on_the_manufacturer_step_with_the_host_carried(hass: HomeAssistant):
    """The device answered and nothing matched: Step 1a lists every maker, without Auto-detect."""
    with patch(f"{_CF}.log_event") as log_event, patch(f"{_CF}.load_modem_catalog", return_value=CATALOG):
        result: Any = await _start(hass, [_detection("192.168.0.1", models=[])])
        values = [o["value"] for o in _options(result, "manufacturer")]
        result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={"manufacturer": "Zeta"})
        result = await _confirm(
            hass, result["flow_id"], {"model": "Zeta/Z1", "entity_prefix": "none", "channel_identity": "number"}
        )

    assert values == ["__all__", "Acme", "Zeta"]
    assert _host_default(result) == "192.168.0.1"
    assert [(e.outcome, e.host, e.selected) for e in _chosen(log_event)] == [("no_match", "192.168.0.1", None)]


async def _confirm(hass: HomeAssistant, flow_id: str, user_input: dict[str, Any]) -> Any:
    with (
        patch(f"{_CF}.load_variant_list", return_value=MOCK_SINGLE_VARIANT),
        patch(f"{_CF}.CATALOG_PATH", FAKE_CATALOG),
    ):
        return await hass.config_entries.flow.async_configure(flow_id, user_input=user_input)


def _host_default(result: Any) -> str:
    """The Step 3 host field's default."""
    key: Any = next(k for k in result["data_schema"].schema if k == "host")
    return str(key.default())


def _chosen(log_event: MagicMock) -> list[DetectionChosen]:
    return [c.args[1] for c in log_event.call_args_list if isinstance(c.args[1], DetectionChosen)]


async def test_confirm_yes_carries_host_and_selections_into_the_entry(hass: HomeAssistant):
    """Yes continues to Step 3 with the answering address; prefix and identity reach the entry."""
    with patch(f"{_CF}.log_event") as log_event:
        result: Any = await _start(hass, [_detection("192.168.0.1", models=[M1])])
        assert result["description_placeholders"]["host"] == "192.168.0.1"
        result = await _confirm(
            hass, result["flow_id"], {"choice": "yes", "entity_prefix": "model", "channel_identity": "id"}
        )
        assert result["step_id"] == "connection"
        assert _host_default(result) == "192.168.0.1"
        with (
            patch(f"{_CF}.validate_connection", return_value=MOCK_VALIDATION_RESULT),
            patch("custom_components.cable_modem_monitor.async_setup_entry", return_value=True),
            patch(f"{_CF}.CATALOG_PATH", FAKE_CATALOG),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={"host": "192.168.0.1"}
            )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert (result["data"]["entity_prefix"], result["data"]["channel_identity"]) == ("model", "id")
    assert [(e.outcome, e.host, e.selected) for e in _chosen(log_event)] == [("confirmed", "192.168.0.1", "Acme M1")]


async def test_choose_manually_goes_straight_to_step_1a_with_the_host_carried(hass: HomeAssistant):
    """Manual: back to the start (no Auto-detect, no not-identified page), host prefilled for Step 3."""
    with patch(f"{_CF}.log_event") as log_event, patch(f"{_CF}.load_modem_catalog", return_value=CATALOG):
        result: Any = await _start(hass, [_detection("192.168.0.1", models=[M1])])
        result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={"choice": "manual"})
        assert result.get("step_id") == "user"
        assert "__detect__" not in [o["value"] for o in _options(result, "manufacturer")]

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"manufacturer": "__all__"}
        )
        result = await _confirm(
            hass, result["flow_id"], {"model": "Acme/M2", "entity_prefix": "none", "channel_identity": "number"}
        )

    assert result["step_id"] == "connection"
    assert _host_default(result) == "192.168.0.1"
    assert [(e.outcome, e.host, e.selected) for e in _chosen(log_event)] == [("rejected", "192.168.0.1", None)]


async def test_nothing_answered_logs_no_match_and_prefills_the_modem_default(hass: HomeAssistant):
    """With no answer the host falls back to the chosen modem's catalog default."""
    with patch(f"{_CF}.log_event") as log_event, patch(f"{_CF}.load_modem_catalog", return_value=CATALOG):
        result: Any = await _start(hass, [])
        assert result["step_id"] == "no_match"
        assert result["description_placeholders"]["observed"] == "-"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={"manufacturer": "Zeta"})
        result = await _confirm(
            hass, result["flow_id"], {"model": "Zeta/Z1", "entity_prefix": "none", "channel_identity": "number"}
        )

    assert _host_default(result) == "192.168.0.1"
    assert [(e.outcome, e.host, e.selected) for e in _chosen(log_event)] == [("no_match", None, None)]


async def test_pick_names_addresses_only_when_several_answered(hass: HomeAssistant):
    """Rows carry their address only when more than one address produced a match."""
    one = await _start(hass, [_detection("192.168.100.1", models=[M1, M2])])
    two = await _start(hass, [_detection("192.168.100.1", models=[M1]), _detection("192.168.0.1", models=[M1])])

    assert [o["label"] for o in _options(one, "model")] == ["Acme M1", "Acme M2"]
    assert [o["label"] for o in _options(two, "model")] == ["Acme M1 (192.168.100.1)", "Acme M1 (192.168.0.1)"]


async def test_pick_carries_that_rows_address(hass: HomeAssistant):
    """Picking the second row sends its address to Step 3 and logs it."""
    with patch(f"{_CF}.log_event") as log_event:
        result: Any = await _start(
            hass, [_detection("192.168.100.1", models=[M1]), _detection("192.168.0.1", models=[M1])]
        )
        result = await _confirm(
            hass, result["flow_id"], {"model": "1", "entity_prefix": "none", "channel_identity": "number"}
        )

    assert _host_default(result) == "192.168.0.1"
    assert [(e.outcome, e.host, e.selected) for e in _chosen(log_event)] == [("picked", "192.168.0.1", "Acme M1")]


async def test_filtered_route_logs_the_model_the_user_ends_on(hass: HomeAssistant):
    """Choosing from the filtered Step 1b logs `filtered` with the model and its address."""
    with patch(f"{_CF}.log_event") as log_event:
        result: Any = await _start(hass, [_detection("192.168.0.1", models=[M1, M2, M3, M4, M5])])
        result = await _confirm(
            hass, result["flow_id"], {"model": "Acme/M3", "entity_prefix": "none", "channel_identity": "number"}
        )

    assert _host_default(result) == "192.168.0.1"
    assert [(e.outcome, e.host, e.selected) for e in _chosen(log_event)] == [("filtered", "192.168.0.1", "Acme M3")]


# -----------------------------------------------------------------------
# Pure helpers
# -----------------------------------------------------------------------

# fmt: off
CODE_SPAN_CASES = [
    ("micro_httpd",       "`micro_httpd`",      "plain"),
    ("a`b",              "`a b`",              "backtick_removed"),
    ("[x](http://e.vil)", "`[x](http://e.vil)`", "link_stays_inside_span"),
    ("line1\nline2",     "`line1 line2`",      "newline_flattened"),
]
# fmt: on


@pytest.mark.parametrize(("text", "expected", "case_id"), CODE_SPAN_CASES, ids=[c[-1] for c in CODE_SPAN_CASES])
def test_code_span_quotes_device_text(text: str, expected: str, case_id: str):
    """Device-supplied text cannot break out of its span or render as a link."""
    assert code_span(text) == expected


def test_describe_observations_lists_each_answering_address():
    text = describe_observations([_detection("192.168.100.1", models=[])])

    assert text == "- `192.168.100.1`: http 200, Server: `micro_httpd`, Title: `Login`, password field"


# -----------------------------------------------------------------------
# Strings
# -----------------------------------------------------------------------

_STEP_PLACEHOLDERS = {
    "detect_confirm": {"model": "M", "host": "h"},
    "no_match": {"observed": "o", "catalog_url": "c", "request_url": "r"},
}
_LANGUAGE_FILES = sorted(p.name for p in (_COMPONENT_DIR / "translations").glob("*.json"))


@pytest.mark.parametrize("language_file", _LANGUAGE_FILES)
@pytest.mark.parametrize("step", sorted(_STEP_PLACEHOLDERS))
def test_detect_step_descriptions_format_with_the_flow_placeholders(language_file: str, step: str):
    """Every language carries each new description, and it uses only placeholders the flow supplies."""
    language = json.loads((_COMPONENT_DIR / "translations" / language_file).read_text(encoding="utf-8"))

    # str.format raises KeyError on a placeholder the flow does not supply.
    language["config"]["step"][step]["description"].format(**_STEP_PLACEHOLDERS[step])


def test_no_match_page_says_not_identified_never_unsupported():
    """CONFIG_FLOW_SPEC § No-match page: absence of a match is not a verdict on support."""
    strings = json.loads((_COMPONENT_DIR / "strings.json").read_text(encoding="utf-8"))
    page = strings["config"]["step"]["no_match"]

    text = f"{page['title']} {page['description']}".lower()
    assert "not identified" in text
    assert "unsupported" not in text


async def test_no_match_description_renders_with_flow_placeholders(hass: HomeAssistant):
    """The page supplies the catalog list and request links."""
    result: Any = await _start(hass, [])

    assert set(result["description_placeholders"]) == {"observed", "catalog_url", "request_url"}
    assert result["description_placeholders"]["request_url"].endswith("/docs/MODEM_REQUEST.md")


async def test_a_failed_sweep_lands_on_manual_selection(hass: HomeAssistant):
    """Auto-detect is a best attempt: an exception in detect() must not stop setup."""

    def broken(summaries: list[ModemSummary]) -> list[Detection]:
        raise RuntimeError("sweep failed")

    with (
        patch(f"{_CF}.log_event") as log_event,
        patch(f"{_CF}.load_modem_catalog", return_value=CATALOG),
        patch(f"{_CF}.detect", broken),
    ):
        result: Any = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"manufacturer": "__detect__"}
        )

    assert result.get("step_id") == "user"
    assert "__detect__" not in [o["value"] for o in _options(result, "manufacturer")]
    assert [(e.outcome, e.host, e.selected) for e in _chosen(log_event)] == [("no_match", None, None)]


def _detection_with_tier_2(
    host: str, *, tier_1: list[ModemSummary], tier_2: list[ModemSummary], named: ModemSummary
) -> Detection:
    """One host: the page-named tier-1 entry, its signal-only companions, and the tier-2 makers."""
    candidates = [Candidate(named, 1, [], named=True)]
    candidates += [Candidate(m, 1, ["SID"]) for m in tier_1]
    candidates += [Candidate(m, 2) for m in tier_2]
    candidates += [Candidate(m, 3) for m in CATALOG if m not in [named, *tier_1, *tier_2]]
    return Detection(
        host=host,
        observation=OBSERVATION,
        match=PageMatch([named], [], [named.model]),
        reply=Reply([], [], None),
        candidates=candidates,
    )


async def test_confirm_offers_three_ways_to_answer(hass: HomeAssistant):
    result: Any = await _start(hass, [_d(H1, models=[M1])])

    options = [o["value"] for o in _options(result, "choice")]
    key: Any = next(k for k in result["data_schema"].schema if k == "choice")
    assert options == ["yes", "others", "manual"]
    assert key.default() == "yes"


async def test_other_likely_matches_lists_the_rest_tier_1_first_and_carries_each_host(hass: HomeAssistant):
    """Not this one: the remaining tier-1 and tier-2 entries, named ones first, each with its own address."""
    detections = [_detection_with_tier_2(H2, tier_1=[M2], tier_2=[M3], named=M1)]
    with patch(f"{_CF}.log_event") as log_event:
        result: Any = await _start(hass, detections)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"choice": "others", "entity_prefix": "none", "channel_identity": "number"}
        )
        assert result.get("step_id") == "model"
        assert [o["label"] for o in _options(result, "model")] == ["Acme M2", "Acme M3"]
        result = await _confirm(
            hass, result["flow_id"], {"model": "Acme/M3", "entity_prefix": "none", "channel_identity": "number"}
        )

    assert _host_default(result) == H2
    assert [(e.outcome, e.host, e.selected) for e in _chosen(log_event)] == [("filtered", H2, "Acme M3")]


async def test_other_likely_matches_with_none_left_opens_the_manufacturer_step(hass: HomeAssistant):
    detections = [_detection_with_tier_2(H2, tier_1=[], tier_2=[], named=M1)]
    with patch(f"{_CF}.log_event") as log_event:
        result: Any = await _start(hass, detections)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"choice": "others", "entity_prefix": "none", "channel_identity": "number"}
        )

    assert result.get("step_id") == "user"
    assert "__detect__" not in [o["value"] for o in _options(result, "manufacturer")]
    assert [(e.outcome, e.host, e.selected) for e in _chosen(log_event)] == [("rejected", H2, None)]
