"""Pytest fixtures for SB8200 modem tests.

These fixtures provide MockModemServer instances configured for the SB8200,
supporting both firmware variants:
- No-auth (older firmware)
- URL token auth (firmware 1.01.009.47+)
- HTTPS + auth (full Travis scenario)
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest

from tests.integration.mock_modem_server import MockModemServer

# Path to this modem's directory (one level up from tests/)
MODEM_PATH = Path(__file__).parent.parent


@pytest.fixture
def sb8200_modem_server() -> Generator[MockModemServer, None, None]:
    """SB8200 server using modem.yaml configuration.

    Uses:
    - auth.strategy: url_token
    - URL token session authentication
    """
    with MockModemServer.from_modem_path(MODEM_PATH) as server:
        yield server


@pytest.fixture
def sb8200_modem_server_noauth() -> Generator[MockModemServer, None, None]:
    """SB8200 server with auth disabled (Tim's firmware variant).

    Simulates older firmware that doesn't require login.
    """
    with MockModemServer.from_modem_path(MODEM_PATH, auth_enabled=False) as server:
        yield server


@pytest.fixture
def sb8200_modem_server_auth() -> Generator[MockModemServer, None, None]:
    """SB8200 server with auth enabled (Travis's firmware variant).

    Simulates newer firmware that requires URL token authentication.
    """
    with MockModemServer.from_modem_path(MODEM_PATH, auth_enabled=True) as server:
        yield server


@pytest.fixture
def sb8200_modem_server_auth_https(test_certs) -> Generator[MockModemServer, None, None]:
    """SB8200 server with HTTPS + auth (full Travis scenario).

    Simulates HTTPS with self-signed cert + URL token auth.
    """
    import ssl

    cert_path, key_path = test_certs
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)

    with MockModemServer.from_modem_path(MODEM_PATH, auth_enabled=True, ssl_context=context) as server:
        yield server
