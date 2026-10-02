"""Shared test fixtures for cable_modem_monitor_core."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests


def collect_fixtures(directory: Path) -> list[Path]:
    """Collect all JSON fixture files from a directory, sorted by name."""
    return sorted(directory.glob("*.json"))


def load_fixture(path: Path) -> dict[str, Any]:
    """Load a JSON fixture file and return the parsed dict."""
    data: dict[str, Any] = json.loads(path.read_text())
    return data


def write_har(tmp_path: Path, har_data: dict[str, Any]) -> Path:
    """Write a HAR dict to a temp file and return the path."""
    har_file = tmp_path / "test.har"
    har_file.write_text(json.dumps(har_data))
    return har_file


# ┌─────────────────────────┬───────────────┬──────────────────────────────────┐
# │ requests exception      │ connectivity  │ why                              │
# ├─────────────────────────┼───────────────┼──────────────────────────────────┤
# │ ConnectionError         │ yes           │ the rule itself                  │
# │ Timeout                 │ yes           │ the rule itself                  │
# │ ConnectTimeout          │ yes           │ subclasses both                  │
# │ ReadTimeout             │ yes           │ subclasses Timeout               │
# │ ProxyError              │ yes           │ subclasses ConnectionError       │
# │ SSLError                │ yes           │ subclasses ConnectionError       │
# │ RequestException        │ no            │ the base, not a subclass         │
# │ HTTPError               │ no            │ the modem answered               │
# │ TooManyRedirects        │ no            │ the modem answered               │
# │ ChunkedEncodingError    │ no            │ the modem answered, badly        │
# │ ContentDecodingError    │ no            │ the modem answered, badly        │
# │ InvalidURL              │ no            │ never sent                       │
# │ RetryError              │ no            │ not a ConnectionError subclass   │
# └─────────────────────────┴───────────────┴──────────────────────────────────┘
# Every requests exception a connectivity site can see, and whether it
# means the modem never answered (RESOURCE_LOADING_SPEC § Error Signals).
# fmt: off
REQUESTS_CONNECTIVITY_CASES: list[tuple[requests.RequestException, bool]] = [
    (requests.ConnectionError("refused"),                       True),
    (requests.Timeout("slow"),                                  True),
    (requests.ConnectTimeout("connect timed out"),              True),
    (requests.ReadTimeout("read timed out"),                    True),
    (requests.exceptions.ProxyError("proxy"),                   True),
    (requests.exceptions.SSLError("handshake"),                 True),
    (requests.RequestException("base"),                         False),
    (requests.HTTPError("500", response=requests.Response()),   False),
    (requests.TooManyRedirects("loop"),                         False),
    (requests.exceptions.ChunkedEncodingError("chunk"),         False),
    (requests.exceptions.ContentDecodingError("gzip"),          False),
    (requests.exceptions.InvalidURL("bad"),                     False),
    (requests.exceptions.RetryError("retries"),                 False),
]
# fmt: on


def requests_case_id(case: tuple[requests.RequestException, bool]) -> str:
    """Name a REQUESTS_CONNECTIVITY_CASES row by its exception type."""
    return type(case[0]).__name__
