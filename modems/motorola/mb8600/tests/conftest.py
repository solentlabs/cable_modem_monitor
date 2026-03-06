"""Pytest fixtures for MB8600 modem tests."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest

from tests.integration.mock_modem_server import MockModemServer

MODEM_PATH = Path(__file__).parent.parent


@pytest.fixture
def mb8600_modem_server() -> Generator[MockModemServer, None, None]:
    """MB8600 server using modem.yaml configuration."""
    with MockModemServer.from_modem_path(MODEM_PATH) as server:
        yield server
