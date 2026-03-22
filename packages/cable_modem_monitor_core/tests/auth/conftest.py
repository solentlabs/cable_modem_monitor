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


_MODEM_DEFAULTS: dict[str, Any] = {
    "manufacturer": "Solent Labs",
    "model": "T100",
    "transport": "http",
    "default_host": "192.168.100.1",
    "status": "unsupported",
    "auth": {"strategy": "none"},
}


def load_auth_fixture(
    name: str,
) -> tuple[list[dict[str, Any]], Any]:
    """Load a HAR fixture file and return entries and optional modem config.

    Args:
        name: Fixture filename (e.g. ``"har_form_login.json"``).

    Returns:
        Tuple of ``(entries, modem_config)`` where ``modem_config``
        is a validated ``ModemConfig`` instance or ``None`` when the
        fixture has no ``_modem_config`` key.
    """
    from solentlabs.cable_modem_monitor_core.config_loader import validate_modem_config

    path = FIXTURES_DIR / name
    data = json.loads(path.read_text())
    entries: list[dict[str, Any]] = data["_entries"]
    raw_config: dict[str, Any] | None = data.get("_modem_config")
    if raw_config is None:
        return entries, None
    # Merge fixture auth config with defaults so minimal fixture
    # dicts (just auth/session) pass full ModemConfig validation.
    merged = {**_MODEM_DEFAULTS, **raw_config}
    # HNAP strategy requires transport: hnap
    auth = merged.get("auth", {})
    if isinstance(auth, dict) and auth.get("strategy") == "hnap":
        merged["transport"] = "hnap"
    return entries, validate_modem_config(merged)
