"""Tests for deriving ``detection.http_headers`` from HARs and writing it into modem.yaml.

Pins INTAKE_PIPELINE.md § Detection Headers. Entries and HARs are synthetic.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.detection_headers import (
    derive_detection_headers,
    set_detection_headers,
    stale_entries,
    write_detection_headers,
)
from solentlabs.cable_modem_monitor_core.catalog_manager import ModemSummary
from solentlabs.cable_modem_monitor_core.validation.layout import modem_layout_errors

MODEM_YAML = """\
manufacturer: Acme
model: AB600
transport: http
default_host: "192.168.100.1"

auth:
  strategy: none

health:
  http_probe: false

# Verification state.
status: confirmed
"""


def _har(server: str | None, *, path: str = "/") -> dict[str, Any]:
    headers = [{"name": "Server", "value": server}] if server else []
    entry = {
        "request": {"method": "GET", "url": f"http://192.168.100.1{path}"},
        "response": {"status": 200, "headers": headers, "content": {"text": "<html></html>"}},
    }
    return {"log": {"entries": [entry]}}


def _entry_dir(root: Path, name: str, hars: dict[str, dict[str, Any]], yaml_text: str = MODEM_YAML) -> Path:
    directory = root / name
    (directory / "test_data").mkdir(parents=True)
    (directory / "modem.yaml").write_text(yaml_text)
    for har_name, har in hars.items():
        (directory / "test_data" / har_name).write_text(json.dumps(har))
    return directory


def _summary(directory: Path, *siblings: Path) -> ModemSummary:
    return ModemSummary(manufacturer="Acme", model="AB600", path=directory, sibling_dirs=list(siblings))


# ---------------------------------------------------------------------------
# Derivation
# ---------------------------------------------------------------------------


def test_servers_are_the_products_of_every_landing_reply_each_once_in_file_order(tmp_path: Path) -> None:
    directory = _entry_dir(
        tmp_path,
        "a",
        {"a.har": _har("lighttpd/1.4.67"), "b.har": _har("ARRIS Server"), "c.har": _har("lighttpd/1.4.1")},
    )

    assert derive_detection_headers([directory]) == ["lighttpd", "ARRIS Server"]


def test_hars_without_a_landing_reply_or_a_server_add_nothing(tmp_path: Path) -> None:
    directory = _entry_dir(tmp_path, "a", {"a.har": _har(None), "b.har": _har("micro_httpd", path="/status.html")})

    assert derive_detection_headers([directory]) == []


def test_servers_span_the_sibling_directories(tmp_path: Path) -> None:
    first = _entry_dir(tmp_path, "a", {"a.har": _har("one")})
    second = _entry_dir(tmp_path, "b", {"a.har": _har("two")})

    assert derive_detection_headers([first, second]) == ["one", "two"]


# ---------------------------------------------------------------------------
# Writing the block
# ---------------------------------------------------------------------------


def test_block_is_inserted_before_status_and_above_its_comment() -> None:
    text = set_detection_headers(MODEM_YAML, ["micro_httpd", "ARRIS Server"])

    assert (
        "health:\n  http_probe: false\n\n"
        'detection:\n  http_headers:\n    - "micro_httpd"\n    - "ARRIS Server"\n\n'
        "# Verification state.\nstatus: confirmed\n"
    ) in text
    assert modem_layout_errors(text) == []


def test_setting_the_same_servers_is_a_no_op() -> None:
    once = set_detection_headers(MODEM_YAML, ["lighttpd"])

    assert set_detection_headers(once, ["lighttpd"]) == once


def test_a_changed_list_replaces_the_block() -> None:
    once = set_detection_headers(MODEM_YAML, ["old"])

    twice = set_detection_headers(once, ["new"])

    assert '"new"' in twice and '"old"' not in twice
    assert twice.count("detection:") == 1


def test_an_empty_list_drops_the_block_and_restores_the_original() -> None:
    assert set_detection_headers(set_detection_headers(MODEM_YAML, ["lighttpd"]), []) == MODEM_YAML


def test_an_empty_list_leaves_a_file_without_a_block_unchanged() -> None:
    assert set_detection_headers(MODEM_YAML, []) == MODEM_YAML


@pytest.mark.parametrize("server", ['Say "hi"', "a: b", "ünïcode"])
def test_awkward_server_text_round_trips_through_yaml(server: str) -> None:
    import yaml

    text = set_detection_headers(MODEM_YAML, [server])

    assert yaml.safe_load(text)["detection"]["http_headers"] == [server]


# ---------------------------------------------------------------------------
# Staleness
# ---------------------------------------------------------------------------


def test_stale_entries_names_the_modem_yaml_that_differs_from_its_hars(tmp_path: Path) -> None:
    stale = _entry_dir(tmp_path, "stale", {"a.har": _har("lighttpd")})
    fresh = _entry_dir(tmp_path, "fresh", {"a.har": _har("lighttpd")}, set_detection_headers(MODEM_YAML, ["lighttpd"]))

    assert stale_entries([_summary(stale), _summary(fresh)]) == [stale / "modem.yaml"]


def test_write_detection_headers_fixes_what_stale_entries_found(tmp_path: Path) -> None:
    directory = _entry_dir(tmp_path, "a", {"a.har": _har("lighttpd")})
    summaries = [_summary(directory)]

    changed = write_detection_headers(summaries)

    assert changed == [directory / "modem.yaml"]
    assert stale_entries(summaries) == []
    assert write_detection_headers(summaries) == []


def test_an_entry_with_only_named_variants_is_written_to_its_first_variant(tmp_path: Path) -> None:
    directory = _entry_dir(tmp_path, "a", {"a.har": _har("lighttpd")})
    (directory / "modem.yaml").rename(directory / "modem-v2.yaml")

    assert write_detection_headers([_summary(directory)]) == [directory / "modem-v2.yaml"]
