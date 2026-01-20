"""Pytest fixtures for MB7621 modem tests.

These fixtures provide MockModemServer instances configured for the MB7621.

Uses:
- auth.strategy: form
- auth.form.password_encoding: base64
- auth.form.success.redirect: /MotoHome.asp
- pages.public includes "/" (shows login even after auth)
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest

from tests.integration.mock_modem_server import MockModemServer

# Path to this modem's directory (one level up from tests/)
MODEM_PATH = Path(__file__).parent.parent


@pytest.fixture
def mb7621_modem_server() -> Generator[MockModemServer, None, None]:
    """MB7621 server using modem.yaml configuration."""
    with MockModemServer.from_modem_path(MODEM_PATH) as server:
        yield server
