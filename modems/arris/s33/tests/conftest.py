"""Pytest fixtures for S33 modem tests.

These fixtures provide MockModemServer instances configured for the S33.

Uses:
- auth.strategy: hnap
- HNAP SOAP authentication
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest

from tests.integration.mock_modem_server import MockModemServer

# Path to this modem's directory (one level up from tests/)
MODEM_PATH = Path(__file__).parent.parent


@pytest.fixture
def s33_modem_server() -> Generator[MockModemServer, None, None]:
    """S33 server using modem.yaml configuration."""
    with MockModemServer.from_modem_path(MODEM_PATH) as server:
        yield server
