"""Test configuration for auth manager tests.

Provides socket access for mock server integration tests and
a fixture loader for HAR entry data files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import requests

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _allow_sockets(socket_enabled: None) -> None:  # noqa: ARG001
    """Enable sockets for all tests in this directory."""


@pytest.fixture
def session() -> requests.Session:
    """Fresh requests.Session for each test."""
    return requests.Session()


def load_auth_fixture(
    name: str,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Load a HAR fixture file and return entries and optional modem config.

    Args:
        name: Fixture filename (e.g. ``"har_form_login.json"``).

    Returns:
        Tuple of ``(entries, modem_config)`` where ``modem_config``
        is ``None`` when the fixture has no ``_modem_config`` key.
    """
    path = FIXTURES_DIR / name
    data = json.loads(path.read_text())
    entries: list[dict[str, Any]] = data["_entries"]
    modem_config: dict[str, Any] | None = data.get("_modem_config")
    return entries, modem_config
