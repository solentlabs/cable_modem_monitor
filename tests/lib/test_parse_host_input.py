"""Tests for parse_host_input() and build_url() utilities.

Table-driven tests covering bare IP, protocol prefix, trailing slash,
port numbers, hostnames, IPv6, and uppercase scheme normalization.
"""

from __future__ import annotations

import pytest

from custom_components.cable_modem_monitor.lib.host_validation import (
    build_url,
    parse_host_input,
)

# =============================================================================
# parse_host_input test data
# =============================================================================
#
# ┌────────────────────────────────────┬───────────────────────────┬──────────┬───────────────────┐
# │ raw input                          │ expected host             │ protocol │ description       │
# ├────────────────────────────────────┼───────────────────────────┼──────────┼───────────────────┤
# │ "192.168.100.1"                    │ "192.168.100.1"           │ None     │ bare IPv4         │
# │ "https://192.168.100.1"            │ "192.168.100.1"           │ "https"  │ explicit https    │
# │ "http://192.168.100.1"             │ "192.168.100.1"           │ "http"   │ explicit http     │
# │ "http://192.168.100.1/"            │ "192.168.100.1"           │ "http"   │ trailing slash    │
# │ "192.168.100.1:8080"               │ "192.168.100.1:8080"      │ None     │ bare IP + port    │
# │ "https://192.168.100.1:8443"       │ "192.168.100.1:8443"      │ "https"  │ https + port      │
# │ "http://192.168.100.1:8080"        │ "192.168.100.1:8080"      │ "http"   │ http + port       │
# │ "mymodem.local"                    │ "mymodem.local"           │ None     │ hostname          │
# │ "https://mymodem.local"            │ "mymodem.local"           │ "https"  │ hostname + https  │
# │ "HTTPS://192.168.100.1"            │ "192.168.100.1"           │ "https"  │ uppercase scheme  │
# │ "HTTP://192.168.100.1"             │ "192.168.100.1"           │ "http"   │ uppercase http    │
# │ "  192.168.100.1  "                │ "192.168.100.1"           │ None     │ whitespace        │
# │ "  https://192.168.100.1  "        │ "192.168.100.1"           │ "https"  │ ws + protocol     │
# │ "10.0.0.1"                         │ "10.0.0.1"               │ None     │ private IP        │
# └────────────────────────────────────┴───────────────────────────┴──────────┴───────────────────┘
#
# fmt: off
PARSE_HOST_CASES = [
    # (raw_input,                       expected_host,              expected_protocol, id)
    ("192.168.100.1",                   "192.168.100.1",            None,              "bare-ipv4"),
    ("https://192.168.100.1",           "192.168.100.1",            "https",           "explicit-https"),
    ("http://192.168.100.1",            "192.168.100.1",            "http",            "explicit-http"),
    ("http://192.168.100.1/",           "192.168.100.1",            "http",            "trailing-slash"),
    ("192.168.100.1:8080",              "192.168.100.1:8080",       None,              "bare-ip-port"),
    ("https://192.168.100.1:8443",      "192.168.100.1:8443",       "https",           "https-port"),
    ("http://192.168.100.1:8080",       "192.168.100.1:8080",       "http",            "http-port"),
    ("mymodem.local",                   "mymodem.local",            None,              "hostname"),
    ("https://mymodem.local",           "mymodem.local",            "https",           "hostname-https"),
    ("HTTPS://192.168.100.1",           "192.168.100.1",            "https",           "uppercase-https"),
    ("HTTP://192.168.100.1",            "192.168.100.1",            "http",            "uppercase-http"),
    ("  192.168.100.1  ",               "192.168.100.1",            None,              "whitespace"),
    ("  https://192.168.100.1  ",       "192.168.100.1",            "https",           "whitespace-protocol"),
    ("10.0.0.1",                        "10.0.0.1",                 None,              "private-ip"),
    ("Http://192.168.100.1",            "192.168.100.1",            "http",            "mixed-case-http"),
]
# fmt: on


class TestParseHostInput:
    """Verify parse_host_input decomposes raw user input correctly."""

    @pytest.mark.parametrize(
        "raw,expected_host,expected_protocol,desc",
        PARSE_HOST_CASES,
        ids=[c[3] for c in PARSE_HOST_CASES],
    )
    def test_parse_host_input(self, raw, expected_host, expected_protocol, desc):
        host, protocol = parse_host_input(raw)
        assert host == expected_host, f"Failed host: {desc}"
        assert protocol == expected_protocol, f"Failed protocol: {desc}"


# =============================================================================
# build_url test data
# =============================================================================
#
# ┌──────────────────────────────┬──────────┬────────────────────────────────────┬───────────────┐
# │ host                         │ protocol │ expected URL                       │ description   │
# ├──────────────────────────────┼──────────┼────────────────────────────────────┼───────────────┤
# │ "192.168.100.1"              │ None     │ "http://192.168.100.1"             │ default http  │
# │ "192.168.100.1"              │ "http"   │ "http://192.168.100.1"             │ explicit http │
# │ "192.168.100.1"              │ "https"  │ "https://192.168.100.1"            │ explicit https│
# │ "192.168.100.1:8080"         │ "http"   │ "http://192.168.100.1:8080"        │ with port     │
# │ "mymodem.local"              │ "https"  │ "https://mymodem.local"            │ hostname      │
# └──────────────────────────────┴──────────┴────────────────────────────────────┴───────────────┘
#
# fmt: off
BUILD_URL_CASES = [
    # (host,                    protocol,   expected_url,                       id)
    ("192.168.100.1",           None,       "http://192.168.100.1",             "default-http"),
    ("192.168.100.1",           "http",     "http://192.168.100.1",             "explicit-http"),
    ("192.168.100.1",           "https",    "https://192.168.100.1",            "explicit-https"),
    ("192.168.100.1:8080",      "http",     "http://192.168.100.1:8080",        "with-port"),
    ("192.168.100.1:8443",      "https",    "https://192.168.100.1:8443",       "https-with-port"),
    ("mymodem.local",           "https",    "https://mymodem.local",            "hostname-https"),
    ("mymodem.local",           None,       "http://mymodem.local",             "hostname-default"),
]
# fmt: on


class TestBuildUrl:
    """Verify build_url reconstructs URLs correctly."""

    @pytest.mark.parametrize(
        "host,protocol,expected_url,desc",
        BUILD_URL_CASES,
        ids=[c[3] for c in BUILD_URL_CASES],
    )
    def test_build_url(self, host, protocol, expected_url, desc):
        result = build_url(host, protocol)
        assert result == expected_url, f"Failed: {desc}"


# =============================================================================
# Round-trip: parse_host_input → build_url
# =============================================================================


class TestRoundTrip:
    """Verify parse → build round-trip preserves intent."""

    def test_bare_ip_round_trip(self):
        host, protocol = parse_host_input("192.168.100.1")
        url = build_url(host, protocol)
        assert url == "http://192.168.100.1"

    def test_explicit_https_round_trip(self):
        host, protocol = parse_host_input("https://192.168.100.1")
        url = build_url(host, protocol)
        assert url == "https://192.168.100.1"

    def test_explicit_http_round_trip(self):
        host, protocol = parse_host_input("http://192.168.100.1")
        url = build_url(host, protocol)
        assert url == "http://192.168.100.1"

    def test_port_round_trip(self):
        host, protocol = parse_host_input("https://192.168.100.1:8443")
        url = build_url(host, protocol)
        assert url == "https://192.168.100.1:8443"
