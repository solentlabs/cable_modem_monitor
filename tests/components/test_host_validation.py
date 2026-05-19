"""Tests for lib/host_validation.py — parse_host_input and build_url."""

from __future__ import annotations

import pytest

from custom_components.cable_modem_monitor.lib.host_validation import build_url, parse_host_input

# fmt: off
# ┌──────────────────────────────┬──────────────────────┬──────────┬──────────────────────────────────┐
# │ raw                          │ expected_host        │ expected │ description                      │
# │                              │                      │ protocol │                                  │
# ├──────────────────────────────┼──────────────────────┼──────────┼──────────────────────────────────┤
PARSE_HOST_CASES = [
    ("192.168.100.1",             "192.168.100.1",       None,     "bare_ip"),
    ("  192.168.100.1  ",         "192.168.100.1",       None,     "bare_ip_whitespace"),
    ("192.168.100.1:8080",        "192.168.100.1:8080",  None,     "bare_ip_with_port"),
    ("https://192.168.100.1",     "192.168.100.1",       "https",  "https_url"),
    ("http://192.168.100.1/",     "192.168.100.1",       "http",   "http_url_trailing_slash"),
    ("HTTPS://192.168.100.1",     "192.168.100.1",       "https",  "https_uppercase_scheme"),
    ("https://192.168.100.1:443", "192.168.100.1:443",  "https",  "https_with_port"),
    ("https://",                  "https://",            None,     "malformed_url_no_host"),
]
# └──────────────────────────────┴──────────────────────┴──────────┴──────────────────────────────────┘
# fmt: on


@pytest.mark.parametrize(
    "raw,expected_host,expected_protocol,_desc",
    PARSE_HOST_CASES,
    ids=[c[3] for c in PARSE_HOST_CASES],
)
def test_parse_host_input(raw: str, expected_host: str, expected_protocol: str | None, _desc: str) -> None:
    host, protocol = parse_host_input(raw)
    assert host == expected_host
    assert protocol == expected_protocol


# fmt: off
# ┌───────────────────┬──────────┬───────────────────────────────┐
# │ host              │ protocol │ expected                      │
# ├───────────────────┼──────────┼───────────────────────────────┤
BUILD_URL_CASES = [
    ("192.168.100.1",      None,      "http://192.168.100.1"),
    ("192.168.100.1",      "http",    "http://192.168.100.1"),
    ("192.168.100.1",      "https",   "https://192.168.100.1"),
    ("192.168.100.1:8080", "http",    "http://192.168.100.1:8080"),
]
# └───────────────────┴──────────┴───────────────────────────────┘
# fmt: on


@pytest.mark.parametrize("host,protocol,expected", BUILD_URL_CASES)
def test_build_url(host: str, protocol: str | None, expected: str) -> None:
    assert build_url(host, protocol) == expected
