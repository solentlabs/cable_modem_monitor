"""Tests for standalone mock server entry point (``__main__.py``).

Verifies the server starts, serves HAR responses, handles auth gating,
and reports errors for invalid input. Uses fixture files for all test
data — no inline JSON or YAML.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import requests
from solentlabs.cable_modem_monitor_core.test_harness.__main__ import main
from solentlabs.cable_modem_monitor_core.test_harness.loader import (
    load_server_from_modem_dir,
)
from solentlabs.cable_modem_monitor_core.test_harness.server import HARMockServer

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _build_modem_dir(
    root: Path,
    *,
    modem_yaml: str = "modem_minimal.yaml",
    har_file: str = "har_minimal.json",
) -> Path:
    """Build a temporary modem directory from fixture files."""
    modem_dir = root / "solentlabs" / "t100"
    modem_dir.mkdir(parents=True)
    shutil.copy(FIXTURES_DIR / modem_yaml, modem_dir / "modem.yaml")
    test_data = modem_dir / "test_data"
    test_data.mkdir()
    shutil.copy(FIXTURES_DIR / har_file, test_data / "modem.har")
    return modem_dir


# ---------------------------------------------------------------------------
# Tests — integration with real HTTP server
# ---------------------------------------------------------------------------


class TestServeIntegration:
    """Start the mock server and verify HTTP responses."""

    @pytest.mark.allow_hosts(["127.0.0.1"])
    def test_serves_har_responses(self, tmp_path: Path) -> None:
        """Server started via loader serves HAR responses."""
        modem_dir = _build_modem_dir(tmp_path)
        config = load_server_from_modem_dir(modem_dir)
        with HARMockServer(
            config.har_entries,
            modem_config=config.modem_config,
            port=0,
        ) as server:
            resp = requests.get(f"{server.base_url}/status.html")
            assert resp.status_code == 200
            assert resp.text == "<html>data</html>"

    @pytest.mark.allow_hosts(["127.0.0.1"])
    def test_custom_port_binding(self, tmp_path: Path) -> None:
        """Server binds to a custom port."""
        modem_dir = _build_modem_dir(tmp_path)
        config = load_server_from_modem_dir(modem_dir)
        with HARMockServer(
            config.har_entries,
            modem_config=config.modem_config,
            host="127.0.0.1",
            port=0,
        ) as server:
            port = server.server_address[1]
            assert port > 0
            resp = requests.get(f"http://127.0.0.1:{port}/status.html")
            assert resp.status_code == 200

    @pytest.mark.allow_hosts(["127.0.0.1"])
    def test_form_auth_gating(self, tmp_path: Path) -> None:
        """Server with form auth gates data pages behind login."""
        modem_dir = _build_modem_dir(
            tmp_path,
            modem_yaml="modem_form_auth.yaml",
            har_file="har_form_auth_minimal.json",
        )
        config = load_server_from_modem_dir(modem_dir)
        with HARMockServer(
            config.har_entries,
            modem_config=config.modem_config,
            port=0,
        ) as server:
            # Before login: 401
            resp = requests.get(f"{server.base_url}/status.html")
            assert resp.status_code == 401

            # Login
            login_resp = requests.post(
                f"{server.base_url}/goform/login",
                data="username=admin&password=pw",
            )
            assert login_resp.status_code == 200

            # After login: 200
            data_resp = requests.get(f"{server.base_url}/status.html")
            assert data_resp.status_code == 200
            assert data_resp.text == "<html>data</html>"


# ---------------------------------------------------------------------------
# Tests — main() argument handling and error cases
# ---------------------------------------------------------------------------


class TestMainFunction:
    """Test the CLI main() function's argument parsing and error handling."""

    def test_missing_modem_dir(self, tmp_path: Path) -> None:
        """Returns exit code 1 for a non-existent modem directory."""
        result = main([str(tmp_path / "nonexistent")])
        assert result == 1

    def test_missing_test_data(self, tmp_path: Path) -> None:
        """Returns exit code 1 when test_data/ is missing."""
        modem_dir = tmp_path / "solentlabs" / "t100"
        modem_dir.mkdir(parents=True)
        shutil.copy(FIXTURES_DIR / "modem_minimal.yaml", modem_dir / "modem.yaml")
        result = main([str(modem_dir)])
        assert result == 1
