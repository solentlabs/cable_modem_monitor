"""Tests for url_matches_endpoint(): does a captured URL address a declared endpoint.

Table-driven. The cases pin the matching rule, not any modem: path
segments compare exactly, queries on either side are ignored, and
``{...}`` placeholder segments match anything.
"""

from __future__ import annotations

import pytest
from solentlabs.cable_modem_monitor_core.test_harness.endpoint_match import url_matches_endpoint

MATCH_CASES = [
    # (declared endpoint, captured url, expected, id)
    ("/reset.htm", "http://192.168.100.1/reset.htm", True, "exact-path"),
    ("/reset.htm", "https://192.168.100.1:8443/reset.htm", True, "scheme-and-port-ignored"),
    ("/reset.htm", "http://192.168.100.1/reset.htm?a=1", True, "captured-query-ignored"),
    ("/reset.htm?a=1", "http://192.168.100.1/reset.htm", True, "declared-query-ignored"),
    ("reset.htm", "http://192.168.100.1/reset.htm", True, "declared-without-leading-slash"),
    ("/api/v1/session/login", "http://192.168.100.1/api/v1/session/login", True, "nested-path"),
    ("/status.htm", "http://192.168.100.1/reset.htm", False, "path-differs"),
    ("/api/v1/session", "http://192.168.100.1/api/v1/session/login", False, "prefix-is-not-a-match"),
    ("/api/v1/session/login", "http://192.168.100.1/api/v1/session", False, "shorter-capture"),
    ("/rest/v1/user/{auth:user_id}/token", "http://192.168.100.1/rest/v1/user/7/token", True, "placeholder-wild"),
    (
        "/rest/v1/user/{auth:user_id}/token",
        "http://192.168.100.1/rest/v1/user/7/other",
        False,
        "placeholder-rest-differs",
    ),
    ("/", "http://192.168.100.1/", True, "root"),
]


@pytest.mark.parametrize(
    "endpoint, url, expected, case_id",
    MATCH_CASES,
    ids=[c[3] for c in MATCH_CASES],
)
def test_url_matches_endpoint(endpoint: str, url: str, expected: bool, case_id: str) -> None:
    """A captured URL matches a declared endpoint by path, per the table."""
    assert url_matches_endpoint(endpoint, url) is expected
