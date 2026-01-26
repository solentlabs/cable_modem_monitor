"""Tests for MockModemServer response delay feature.

Verifies that response_delay parameter correctly delays responses
for timeout testing scenarios.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
import requests

from .mock_modem_server import MockModemServer

# Use repo root modems/ directory
REPO_ROOT = Path(__file__).parent.parent.parent
MODEMS_ROOT = REPO_ROOT / "modems"


def get_test_modem_path() -> Path:
    """Get a modem path for testing (MB7621 has good fixture coverage)."""
    modem_path = MODEMS_ROOT / "motorola" / "mb7621"
    if modem_path.exists():
        return modem_path
    # Fallback to any modem with fixtures
    for mfr in MODEMS_ROOT.iterdir():
        if not mfr.is_dir():
            continue
        for model in mfr.iterdir():
            if (model / "fixtures").exists():
                return model
    pytest.skip("No modem with fixtures available")


class TestResponseDelay:
    """Test response_delay parameter."""

    def test_no_delay_by_default(self):
        """Responses should be fast when no delay configured."""
        modem_path = get_test_modem_path()

        with MockModemServer.from_modem_path(modem_path, auth_enabled=False) as server:
            start = time.time()
            response = requests.get(f"{server.url}/", timeout=5)
            elapsed = time.time() - start

            assert response.status_code in (200, 302, 401)
            assert elapsed < 1.0, f"Response took {elapsed:.2f}s without delay configured"

    def test_delay_applied_to_responses(self):
        """Responses should be delayed when response_delay is set."""
        modem_path = get_test_modem_path()
        delay_seconds = 0.5

        with MockModemServer.from_modem_path(
            modem_path,
            auth_enabled=False,
            response_delay=delay_seconds,
        ) as server:
            start = time.time()
            response = requests.get(f"{server.url}/", timeout=5)
            elapsed = time.time() - start

            assert response.status_code in (200, 302, 401)
            assert elapsed >= delay_seconds, f"Response took {elapsed:.2f}s, expected >= {delay_seconds}s"

    def test_delay_applied_to_multiple_requests(self):
        """Each request should be delayed independently."""
        modem_path = get_test_modem_path()
        delay_seconds = 0.3

        with MockModemServer.from_modem_path(
            modem_path,
            auth_enabled=False,
            response_delay=delay_seconds,
        ) as server:
            # Make two requests
            start = time.time()
            requests.get(f"{server.url}/", timeout=5)
            requests.get(f"{server.url}/", timeout=5)
            elapsed = time.time() - start

            # Should take at least 2x the delay (one per request)
            expected_min = delay_seconds * 2
            assert elapsed >= expected_min, f"Two requests took {elapsed:.2f}s, expected >= {expected_min}s"

    def test_zero_delay_is_valid(self):
        """Zero delay should work (no-op)."""
        modem_path = get_test_modem_path()

        with MockModemServer.from_modem_path(
            modem_path,
            auth_enabled=False,
            response_delay=0.0,
        ) as server:
            start = time.time()
            response = requests.get(f"{server.url}/", timeout=5)
            elapsed = time.time() - start

            assert response.status_code in (200, 302, 401)
            assert elapsed < 1.0, "Zero delay should not slow down responses"
