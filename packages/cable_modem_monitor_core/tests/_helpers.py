"""Shared test fixtures for cable_modem_monitor_core."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


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
