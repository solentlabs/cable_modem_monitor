"""Test configuration for loader tests.

Enables socket access for mock server integration tests.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _allow_sockets(socket_enabled: None) -> None:  # noqa: ARG001
    """Enable sockets for all tests in this directory."""
