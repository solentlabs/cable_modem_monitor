"""Data page identity: a path, plus the query when the query selects the document.

Per ONBOARDING_SPEC.md § Data page identity.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.analysis.format import detect_sections
from solentlabs.cable_modem_monitor_catalog_tools.analysis.format.http import (
    analyze_page,
    identify_data_pages,
    identify_resources,
)

_DOC_A = {"rows": [{"a": 1}]}
_DOC_A_OTHER_VALUES = {"rows": [{"a": 2}, {"a": 3}]}
_DOC_B = {"info": {"b": "x"}}
_DOC_C = {"state": "up"}
_HTML = "<html>" + "x" * 200 + "</html>"


def _entry(url: str, body: Any, content_type: str = "application/json") -> dict[str, Any]:
    """A 200 GET entry; a non-string body is serialised as JSON."""
    text = body if isinstance(body, str) else json.dumps(body)
    return {
        "request": {"method": "GET", "url": f"http://192.168.100.1{url}", "headers": []},
        "response": {
            "status": 200,
            "headers": [{"name": "Content-Type", "value": content_type}],
            "content": {"size": len(text), "mimeType": content_type, "text": text},
        },
    }


# fmt: off
RESOURCE_CASES = [
    # (id, [(url, body, content_type)], expected resources in HAR order)
    ("selectors_each_requested_once",
     [("/setup.cgi?todo=A", _DOC_A, "application/json"), ("/setup.cgi?todo=B", _DOC_B, "application/json")],
     ["/setup.cgi?todo=A", "/setup.cgi?todo=B"]),
    ("misspelled_json_selectors",
     [("/setup.cgi?todo=A", _DOC_A, "applation/json"), ("/setup.cgi?todo=B", _DOC_B, "applation/json")],
     ["/setup.cgi?todo=A", "/setup.cgi?todo=B"]),
    ("one_document_ignores_cache_buster",
     [("/data.json?_=1", _DOC_A, "application/json"), ("/data.json?_=2", _DOC_A_OTHER_VALUES, "application/json")],
     ["/data.json"]),
    ("repeated_document_drops_varying_parameter",
     [("/p?todo=A&_n=1", _DOC_A, "application/json"), ("/p?todo=A&_n=2", _DOC_A_OTHER_VALUES, "application/json"),
      ("/p?todo=B&_n=3", _DOC_B, "application/json")],
     ["/p?todo=A", "/p?todo=B&_n=3"]),
    ("three_documents",
     [("/p?k=1", _DOC_A, "application/json"), ("/p?k=2", _DOC_B, "application/json"),
      ("/p?k=3", _DOC_C, "application/json")],
     ["/p?k=1", "/p?k=2", "/p?k=3"]),
    ("html_response_keeps_the_bare_path",
     [("/setup.cgi", _HTML, "text/html"), ("/setup.cgi?todo=A", _DOC_A, "application/json"),
      ("/setup.cgi?todo=B", _DOC_B, "application/json")],
     ["/setup.cgi", "/setup.cgi?todo=A", "/setup.cgi?todo=B"]),
    ("one_document_beside_an_acknowledgement",
     [("/status?login=1", "OK", "text/html"), ("/status", _DOC_A, "application/json")],
     ["/status"]),
    ("html_queries_stay_path_only",
     [("/page?x=1", _HTML, "text/html"), ("/page?x=2", _HTML + " ", "text/html")],
     ["/page"]),
    ("different_paths_untouched",
     [("/a.json?x=1", _DOC_A, "application/json"), ("/b.json?x=2", _DOC_B, "application/json")],
     ["/a.json", "/b.json"]),
]
# fmt: on


@pytest.mark.parametrize(
    ("responses", "expected"),
    [pytest.param(r, e, id=i) for i, r, e in RESOURCE_CASES],
)
def test_resources(responses: list[tuple[str, Any, str]], expected: list[str]) -> None:
    """Each document at a path is its own resource; a lone document is the bare path."""
    entries = [_entry(url, body, content_type) for url, body, content_type in responses]
    resources = [resource for _, resource in identify_resources(entries)]
    assert resources == expected
    assert identify_data_pages(entries) == [entry for entry, _ in identify_resources(entries)]


def test_largest_response_stands_for_a_document() -> None:
    """Of the responses returning one document, the largest body is the page."""
    small, large = _entry("/p?k=1", _DOC_A), _entry("/p?k=1", _DOC_A_OTHER_VALUES)
    pages = identify_resources([small, large, _entry("/p?k=2", _DOC_B)])
    assert pages[0][0] is large


def test_analyze_page_takes_the_resource_it_is_given() -> None:
    """A page analysed with its resource reports it, query included."""
    entry = _entry("/setup.cgi?todo=A", _DOC_A)
    assert analyze_page(entry, "/setup.cgi?todo=A").resource == "/setup.cgi?todo=A"
    assert analyze_page(entry).resource == "/setup.cgi"


WARNING_CASES = [
    ("one_parameter", [("/p?todo=A", _DOC_A), ("/p?todo=B", _DOC_B)], 0),
    ("two_parameters", [("/p?todo=A&_n=1", _DOC_A), ("/p?todo=B&_n=2", _DOC_B)], 2),
]


@pytest.mark.parametrize(
    ("responses", "warned"),
    [pytest.param(r, w, id=i) for i, r, w in WARNING_CASES],
)
def test_several_parameters_are_named_in_a_warning(responses: list[tuple[str, Any]], warned: int) -> None:
    """A split resource that keeps more than one parameter is reported, one cannot be a nonce alone."""
    warnings: list[str] = []
    detect_sections([_entry(url, body) for url, body in responses], "http", warnings, [])
    named = [w for w in warnings if "selected by" in w]
    assert len(named) == warned
    assert all("2 query parameters" in w for w in named)
