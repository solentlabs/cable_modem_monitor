"""Pytest fixtures for CGA2121 modem tests.

These fixtures provide MockModemServer instances configured for the CGA2121.

Uses:
- auth.strategy: form
- auth.form.password_encoding: plain
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest

from tests.integration.mock_modem_server import MockModemServer

# Path to this modem's directory (one level up from tests/)
MODEM_PATH = Path(__file__).parent.parent


@pytest.fixture
def cga2121_modem_server() -> Generator[MockModemServer, None, None]:
    """CGA2121 server using modem.yaml configuration."""
    with MockModemServer.from_modem_path(MODEM_PATH) as server:
        yield server
