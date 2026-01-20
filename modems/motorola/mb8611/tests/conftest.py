"""Pytest fixtures for MB8611 modem tests.

These fixtures provide MockModemServer instances configured for the MB8611.

Uses:
- auth.strategy: hnap
- HNAP SOAP authentication (similar to S33)
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest

from tests.integration.mock_modem_server import MockModemServer

# Path to this modem's directory (one level up from tests/)
MODEM_PATH = Path(__file__).parent.parent


@pytest.fixture
def mb8611_modem_server() -> Generator[MockModemServer, None, None]:
    """MB8611 server using modem.yaml configuration."""
    with MockModemServer.from_modem_path(MODEM_PATH) as server:
        yield server
