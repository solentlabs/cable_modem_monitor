"""Pytest fixtures for CM3500B modem tests.

These fixtures provide MockModemServer instances configured for the CM3500B.

Uses:
- auth.strategy: form
- session.cookie_name: credential
- pages.data: /cgi-bin/status_cgi, /cgi-bin/spectrum_cgi
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest

from tests.integration.mock_modem_server import MockModemServer

# Path to this modem's directory (one level up from tests/)
MODEM_PATH = Path(__file__).parent.parent


@pytest.fixture
def cm3500b_modem_server() -> Generator[MockModemServer, None, None]:
    """CM3500B server using modem.yaml configuration."""
    with MockModemServer.from_modem_path(MODEM_PATH) as server:
        yield server
