"""Pytest configuration and fixtures for cable_modem_monitor tests."""

from __future__ import annotations

import socket

import pytest

# Store the original socket before pytest-socket patches it
try:
    import pytest_socket

    _original_socket = pytest_socket._true_socket
except (ImportError, AttributeError):
    _original_socket = socket.socket


def pytest_configure(config):
    """Configure pytest to allow socket operations.

    Restore the original socket class immediately during configuration,
    before any tests or fixtures run. This allows Home Assistant's event
    loop to create sockets for internal communication on both Windows and Linux.
    """
    socket.socket = _original_socket  # type: ignore[misc]


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """Restore socket before each test runs.

    pytest-socket re-patches socket.socket between tests, so we need to
    restore it before each test. This runs with tryfirst=True to ensure
    it executes before other plugins.
    """
    socket.socket = _original_socket  # type: ignore[misc]


@pytest.hookimpl(tryfirst=True)
def pytest_fixture_setup(fixturedef, request):
    """Restore socket before each fixture is set up.

    This ensures the socket is unblocked when the event_loop fixture
    is created, which happens during fixture setup.
    """
    socket.socket = _original_socket  # type: ignore[misc]
