"""Pytest fixtures for modem-specific tests.

Imports fixtures from tests/ so they're available to tests
colocated with modem configuration.
"""

# Import socket restoration hooks from root conftest (enables socket operations)
# These are pytest hooks that get discovered automatically when in conftest.py
# This MUST be imported first to ensure socket is restored before other fixtures
from tests.conftest import pytest_configure, pytest_fixture_setup, pytest_runtest_setup

# Import all fixtures to make them available to modem tests
from tests.integration.conftest import *  # noqa: F401,F403
from tests.integration.har_replay.conftest import *  # noqa: F401,F403

# Re-export hooks explicitly for pytest discovery
__all__ = ["pytest_configure", "pytest_fixture_setup", "pytest_runtest_setup"]
