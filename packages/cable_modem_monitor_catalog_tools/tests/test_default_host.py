"""Tests for detect_default_host() and its place in the analysis result.

Pins ONBOARDING_SPEC.md § Phase 7: ``default_host`` comes from the HAR's
request URLs. Hosts and captures are synthetic.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.analysis.default_host import detect_default_host
from solentlabs.cable_modem_monitor_catalog_tools.analyze_har import analyze_har


def _entries(*urls: str) -> list[dict[str, Any]]:
    return [{"request": {"method": "GET", "url": url}, "response": {"status": 200}} for url in urls]


DEVICE = "http://10.0.0.1"

# (urls, expected host, id)
HOST_CASES = [
    ([], "", "no-entries"),
    ([f"{DEVICE}/a.html"], "10.0.0.1", "single-request"),
    ([f"{DEVICE}/a", f"{DEVICE}/b", "https://cdn.example.com/x.js"], "10.0.0.1", "most-requested-host-wins"),
    (["https://cdn.example.com/x.js", f"{DEVICE}/a", f"{DEVICE}/b"], "10.0.0.1", "order-does-not-decide"),
    ([f"{DEVICE}/a", "http://192.168.0.1/b"], "10.0.0.1", "tie-goes-to-first-seen"),
    (["https://10.0.0.1:8443/a", "http://10.0.0.1/b"], "10.0.0.1", "port-and-scheme-ignored"),
    (["http://MyModem.Local/a"], "mymodem.local", "hostname-lowercased"),
    (["http://[fe80::1]/a"], "fe80::1", "ipv6"),
    (["not a url", f"{DEVICE}/a"], "10.0.0.1", "unparseable-url-skipped"),
    (["http://[::1/a", f"{DEVICE}/a"], "10.0.0.1", "malformed-bracket-skipped"),
    (["/relative/only"], "", "no-host-at-all"),
]


@pytest.mark.parametrize(("urls", "expected", "case_id"), HOST_CASES, ids=[c[-1] for c in HOST_CASES])
def test_detect_default_host(urls: list[str], expected: str, case_id: str) -> None:
    assert detect_default_host(_entries(*urls)) == expected


def test_analysis_result_carries_the_host_the_har_was_captured_on(tmp_path: Path) -> None:
    fixture = next((Path(__file__).parent / "fixtures" / "analyze_har" / "valid").glob("*.json"))
    har = json.loads(fixture.read_text())["_har"]
    expected = urlparse(har["log"]["entries"][0]["request"]["url"]).hostname
    har_file = tmp_path / "test.har"
    har_file.write_text(json.dumps(har))

    result = analyze_har(har_file)

    assert result.default_host == expected
    assert result.to_dict()["default_host"] == expected
