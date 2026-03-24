"""Test configuration for orchestration tests.

Enables socket access for mock server integration tests and
provides shared fixtures for modem configs and mock collectors.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _allow_sockets(socket_enabled: None) -> None:  # noqa: ARG001
    """Enable sockets for all tests in this directory.

    The ``socket_enabled`` fixture is provided by pytest-socket
    and re-enables socket operations for the test.
    """
