"""Tests for detection.read_reply() and detection.narrow() — the pure evidence and tiering steps.

Table-driven, invented names. Contract: DETECTION_SPEC.md § Reply evidence,
§ Signals and § Narrowing.
"""

from __future__ import annotations

import pytest
from solentlabs.cable_modem_monitor_core.catalog_manager import ModemSummary
from solentlabs.cable_modem_monitor_core.detection import (
    Observation,
    PageMatch,
    Reply,
    narrow,
    read_reply,
)
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import LandingSignals

HTML = {"Content-Type": "text/html"}


def _hop(url: str, body: str = "", headers: dict[str, str] | None = None) -> tuple[str, dict[str, str], bytes]:
    return url, headers if headers is not None else HTML, body.encode()


# ┌─────────────────────────────────────────────┬──────────────────────────────────────────────┐
# │ body                                        │ paths                                        │
# ├─────────────────────────────────────────────┼──────────────────────────────────────────────┤
# │ script src, link href, form action, data    │ each, in page order                          │
# │ relative values                             │ resolved against the response URL            │
# │ ./ and ../ values                           │ resolved                                     │
# │ query string and fragment                   │ dropped                                      │
# │ another host                                │ dropped                                      │
# │ same host, other scheme                     │ kept                                         │
# │ "/", "#", javascript:, mailto:, data: URIs  │ dropped                                      │
# │ the same path twice                         │ listed once                                  │
# │ quoted either way, or unquoted              │ read                                         │
# │ meta refresh                                │ its target                                   │
# │ no attributes                               │ none                                         │
# └─────────────────────────────────────────────┴──────────────────────────────────────────────┘
#
# fmt: off
PATH_CASES = [
    ('<script src="/a.js"></script><link href="/b.css"><form action="/c.cgi"><object data="/d.swf">',
     ["/a.js", "/b.css", "/c.cgi", "/d.swf"], "attributes"),
    ('<script src="js/a.js">', ["/login/js/a.js"], "relative_to_url_directory"),
    ('<script src="./js/a.js"><script src="../up.js">', ["/login/js/a.js", "/up.js"], "dot_segments"),
    ('<form action=""><a href="#top">', [], "empty_and_fragment_only_are_the_page_itself"),
    ('<script src="/a.js?V=2#top">', ["/a.js"], "query_and_fragment"),
    ('<script src="http://cdn.example/a.js"><script src="/b.js">', ["/b.js"], "other_host_dropped"),
    ('<script src="https://192.168.100.1/a.js">', ["/a.js"], "same_host_other_scheme"),
    ('<a href="/"><a href="#"><a href="javascript:void(0)"><a href="mailto:x@y"><img src="data:image/png;base64,AA">',
     [], "non_paths_dropped"),
    ('<script src="/a.js"><script src="/a.js?x=1">', ["/a.js"], "listed_once"),
    ("<script src='/a.js'><script src=/b.js>", ["/a.js", "/b.js"], "quote_styles"),
    ('<meta http-equiv="refresh" content="0; url=/home.html">', ["/home.html"], "meta_refresh"),
    ('<META CONTENT="0;URL=/home.html" HTTP-EQUIV=Refresh>', ["/home.html"], "meta_refresh_any_order"),
    ("<html><body>plain</body></html>", [], "no_attributes"),
]
# fmt: on


@pytest.mark.parametrize(("body", "paths", "case_id"), PATH_CASES, ids=[c[-1] for c in PATH_CASES])
def test_read_reply_paths(body: str, paths: list[str], case_id: str) -> None:
    reply = read_reply([_hop("http://192.168.100.1/login/index.html", body)])

    assert reply.paths == paths


def test_a_redirects_location_is_not_a_path() -> None:
    """Where a redirect points is a correlation; the page it leads to carries the evidence."""
    hops = [
        _hop("http://192.168.100.1/", "", {"Location": "/Login.html"}),
        _hop("http://192.168.100.1/Login.html", '<script src="/js/a.js">'),
    ]

    assert read_reply(hops).paths == ["/js/a.js"]


def test_every_hop_of_the_chain_is_read_in_order() -> None:
    hops = [
        _hop("http://192.168.100.1/", '<meta http-equiv="refresh" content="0;url=/first.html">'),
        _hop("http://192.168.100.1/first.html", '<script src="/second.js">'),
    ]

    assert read_reply(hops).paths == ["/first.html", "/second.js"]


def test_a_non_html_body_is_not_read_for_paths() -> None:
    hops = [_hop("http://192.168.100.1/api", '{"src": "x"} src="/a.js"', {"Content-Type": "application/json"})]

    assert read_reply(hops).paths == []


def test_a_body_with_no_content_type_is_read() -> None:
    assert read_reply([_hop("http://192.168.100.1/", '<script src="/a.js">', {})]).paths == ["/a.js"]


# fmt: off
SERVER_CASES = [
    ({"Server": "lighttpd/1.4.67"}, "lighttpd", "version_cut"),
    ({"Server": "ARRIS Server"}, "ARRIS Server", "no_version"),
    ({"server": "NET-DK/1.0"}, "NET-DK", "any_case"),
    ({}, None, "absent"),
]
# fmt: on


@pytest.mark.parametrize(("headers", "server", "case_id"), SERVER_CASES, ids=[c[-1] for c in SERVER_CASES])
def test_read_reply_server_product(headers: dict[str, str], server: str | None, case_id: str) -> None:
    assert read_reply([_hop("http://h/", "", headers)]).server == server


def test_the_final_response_supplies_the_server() -> None:
    hops = [_hop("http://h/", "", {"Server": "redirector/1"}), _hop("http://h/x", "", {"Server": "real/2"})]

    assert read_reply(hops).server == "real"


def test_cookies_are_kept_once_in_first_seen_order() -> None:
    assert read_reply([_hop("http://h/")], cookies=["B", "A", "B"]).cookies == ["B", "A"]


# ---------------------------------------------------------------------------
# narrow()
# ---------------------------------------------------------------------------

OBSERVATION = Observation("http", 200, "/", None, None, None, False)
LOGIN_FORM = Observation("http", 200, "/", None, None, None, True)


def _entry(
    model: str,
    *,
    manufacturer: str = "Acme",
    paths: tuple[str, ...] = (),
    cookies: tuple[str, ...] = (),
    server: list[str] | None = None,
    strategies: list[str] | None = None,
) -> ModemSummary:
    return ModemSummary(
        manufacturer=manufacturer,
        model=model,
        landing_signals=LandingSignals(paths, cookies),
        server_headers=server or [],
        auth_strategies=strategies or ["form"],
    )


def _match(*, models: list[ModemSummary] | None = None, buckets: list[str] | None = None) -> PageMatch:
    return PageMatch(models=models or [], buckets=buckets or [], matched=[])


def _tiers(
    catalog: list[ModemSummary],
    *,
    match: PageMatch | None = None,
    reply: Reply | None = None,
    observation: Observation = OBSERVATION,
) -> list[tuple[str, int]]:
    result = narrow(catalog, match or _match(), reply or Reply([], [], None), observation)
    return [(c.summary.model, c.tier) for c in result]


def test_page_names_a_model_tier_1() -> None:
    a, b = _entry("A"), _entry("B")

    assert _tiers([a, b], match=_match(models=[b])) == [("B", 1), ("A", 3)]


def test_path_signal_found_tier_1_and_listed() -> None:
    a = _entry("A", paths=("/check.jst",))
    reply = Reply(["/x.js", "/check.jst"], [], None)

    result = narrow([a, _entry("B", paths=("/other.cgi",))], _match(), reply, OBSERVATION)

    assert [(c.summary.model, c.tier, c.signals) for c in result] == [("A", 1, ["/check.jst"]), ("B", 3, [])]


def test_cookie_signal_found_tier_1_and_listed() -> None:
    a = _entry("A", cookies=("PHPSESSID",))

    result = narrow([a], _match(), Reply([], ["PHPSESSID"], None), OBSERVATION)

    assert [(c.tier, c.signals) for c in result] == [(1, ["PHPSESSID"])]


def test_a_path_signal_does_not_match_a_cookie_of_the_same_name() -> None:
    a = _entry("A", paths=("/sid",), cookies=("sid",))

    assert _tiers([a], reply=Reply([], ["/sid"], None)) == [("A", 3)]


def test_maker_named_tier_2() -> None:
    assert _tiers([_entry("A"), _entry("B", manufacturer="Bolt")], match=_match(buckets=["Bolt"])) == [
        ("B", 2),
        ("A", 3),
    ]


def test_brand_named_tier_2() -> None:
    branded = ModemSummary(manufacturer="Bolt", model="B", brands=["Cosmos"])

    assert _tiers([branded], match=_match(buckets=["cosmos"])) == [("B", 2)]


def test_server_listed_tier_2() -> None:
    assert _tiers([_entry("A", server=["lighttpd"]), _entry("B")], reply=Reply([], [], "lighttpd")) == [
        ("A", 2),
        ("B", 3),
    ]


def test_tier_1_beats_tier_2_for_one_entry() -> None:
    a = _entry("A", server=["lighttpd"], paths=("/p",))

    assert _tiers([a], reply=Reply(["/p"], [], "lighttpd")) == [("A", 1)]


def test_within_tier_1_the_named_entries_come_first_in_catalog_order() -> None:
    catalog = [_entry("A", paths=("/p",)), _entry("B"), _entry("C", paths=("/p",)), _entry("D")]
    match = _match(models=[catalog[1], catalog[3]])

    result = narrow(catalog, match, Reply(["/p"], [], None), OBSERVATION)

    assert [(c.summary.model, c.named) for c in result] == [("B", True), ("D", True), ("A", False), ("C", False)]


def test_candidates_are_tier_1_then_2_then_3_each_in_catalog_order() -> None:
    catalog = [_entry("C"), _entry("B", server=["s"]), _entry("A", paths=("/p",)), _entry("D", paths=("/p",))]

    result = _tiers(catalog, reply=Reply(["/p"], [], "s"))

    assert result == [("A", 1), ("D", 1), ("B", 2), ("C", 3)]


def test_missing_names_and_signals_remove_nothing() -> None:
    catalog = [_entry("A", paths=("/never.js",)), _entry("B", cookies=("never",))]

    assert _tiers(catalog, match=_match(models=[_entry("X")])) == [("A", 3), ("B", 3)]


# ┌──────────────────────────────┬──────────────┬──────────────────────────────┐
# │ entry strategies             │ password     │ result                       │
# ├──────────────────────────────┼──────────────┼──────────────────────────────┤
# │ none                         │ yes          │ removed                      │
# │ none, none                   │ yes          │ removed                      │
# │ none, form                   │ yes          │ kept (a variant has a login) │
# │ form                         │ yes          │ kept                         │
# │ none                         │ no           │ kept                         │
# │ (no variants recorded)       │ yes          │ kept                         │
# └──────────────────────────────┴──────────────┴──────────────────────────────┘
#
# fmt: off
CONTRADICTION_CASES = [
    (["none"],          True,  False, "no_auth_removed"),
    (["none", "none"],  True,  False, "all_variants_no_auth_removed"),
    (["none", "form"],  True,  True,  "one_login_variant_kept"),
    (["form"],          True,  True,  "login_kept"),
    (["none"],          False, True,  "no_password_kept"),
    ([],                True,  True,  "unknown_strategies_kept"),
]
# fmt: on


@pytest.mark.parametrize(
    ("strategies", "password_field", "kept", "case_id"), CONTRADICTION_CASES, ids=[c[-1] for c in CONTRADICTION_CASES]
)
def test_contradiction_rule(strategies: list[str], password_field: bool, kept: bool, case_id: str) -> None:
    entry = ModemSummary(manufacturer="Acme", model="A", auth_strategies=strategies)
    observation = LOGIN_FORM if password_field else OBSERVATION

    result = narrow([entry], _match(), Reply([], [], None), observation)

    assert bool(result) is kept


def test_tier_1_evidence_protects_a_no_auth_entry_from_the_login_form() -> None:
    """Never exclude a real modem: a name or a found signal outweighs the contradiction."""
    named = ModemSummary(manufacturer="Acme", model="A", auth_strategies=["none"])
    signalled = ModemSummary(
        manufacturer="Acme",
        model="B",
        auth_strategies=["none"],
        landing_signals=LandingSignals(("/status.html",)),
    )

    result = narrow([named, signalled], _match(models=[named]), Reply(["/status.html"], [], None), LOGIN_FORM)

    assert [(c.summary.model, c.tier) for c in result] == [("A", 1), ("B", 1)]
