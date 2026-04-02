"""Tests for config_flow_helpers — validation pipeline protocol retry.

Tests the _run_validation() function directly (sync, no HA dependency).
All Core I/O is mocked: detect_protocol, config loaders, ModemDataCollector.

UC-85: Protocol fallback — HTTP reachable but auth requires HTTPS.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from solentlabs.cable_modem_monitor_core.connectivity import ConnectivityResult
from solentlabs.cable_modem_monitor_core.orchestration.models import ModemResult
from solentlabs.cable_modem_monitor_core.orchestration.signals import (
    CollectorSignal,
)

from custom_components.cable_modem_monitor.config_flow_helpers import (
    _run_validation,
)

# =====================================================================
# Helpers
# =====================================================================

_MODULE = "custom_components.cable_modem_monitor.config_flow_helpers"


def _ok_result() -> ModemResult:
    """Successful collection result."""
    return ModemResult(
        success=True,
        signal=CollectorSignal.OK,
        modem_data={"downstream": [], "upstream": []},
    )


def _auth_failed_result(error: str = "HNAP challenge response is not valid JSON") -> ModemResult:
    """Auth failure result (wrong protocol, bad credentials, etc.)."""
    return ModemResult(
        success=False,
        signal=CollectorSignal.AUTH_FAILED,
        error=error,
    )


def _load_auth_result() -> ModemResult:
    """LOAD_AUTH failure — 401/403 on data page after auth."""
    return ModemResult(
        success=False,
        signal=CollectorSignal.LOAD_AUTH,
        error="HTTP 401 on /status.html",
    )


def _connectivity_result() -> ModemResult:
    """Connectivity failure — modem unreachable."""
    return ModemResult(
        success=False,
        signal=CollectorSignal.CONNECTIVITY,
        error="Connection refused",
    )


def _parse_error_result() -> ModemResult:
    """Parse error — modem responded but data is malformed."""
    return ModemResult(
        success=False,
        signal=CollectorSignal.PARSE_ERROR,
        error="Unexpected HTML structure",
    )


def _setup_modem_dir(tmp_path: Path) -> Path:
    """Create a minimal modem directory with required files."""
    modem_dir = tmp_path / "test_mfr" / "test_model"
    modem_dir.mkdir(parents=True)
    (modem_dir / "modem.yaml").touch()
    (modem_dir / "parser.yaml").touch()
    (modem_dir / "parser.py").touch()
    return modem_dir


# =====================================================================
# Protocol retry — UC-85 scenarios
# =====================================================================
#
# ┌───┬────────────┬──────┬────────────┬──────────┬─────────┬────────────────┐
# │ # │ user proto │ det  │ first      │ https    │ legacy  │ expected       │
# ├───┼────────────┼──────┼────────────┼──────────┼─────────┼────────────────┤
# │ 1 │ auto       │ http │ AUTH_FAIL  │ OK       │ —       │ https, F       │
# │ 2 │ auto       │ http │ AUTH_FAIL  │ AUTH_FAIL│AUTH_FAIL│ PermError      │
# │ 3 │ "http"     │ —    │ AUTH_FAIL  │ —        │ —       │ PermError      │
# │ 4 │ auto       │https │ AUTH_FAIL  │ —        │ —       │ PermError      │
# │ 5 │ auto       │ http │ CONNECT    │ —        │ —       │ RuntimeError   │
# │ 6 │ auto       │ http │ AUTH_FAIL  │ AUTH_FAIL│ OK      │ https, T       │
# │ 7 │ auto       │ http │ LOAD_AUTH  │ OK       │ —       │ https, F       │
# │ 8 │ auto       │ http │ PARSE_ERR  │ —        │ —       │ RuntimeError   │
# │ 9 │ auto       │ http │ AUTH_FAIL  │ CONNECT  │ —       │ PermError      │
# │10 │ auto       │ http │ LOAD_AUTH  │ CONNECT  │ —       │ PermError      │
# └───┴────────────┴──────┴────────────┴──────────┴─────────┴────────────────┘

_RETRY_CASE = tuple[
    str | None,
    str,
    list[ModemResult],
    type[Exception] | None,
    str | None,
    bool | None,
    str,
]

# fmt: off
PROTOCOL_RETRY_CASES: list[_RETRY_CASE] = [
    # (user_proto, detected, results, exception, exp_proto, exp_legacy, desc)
    (None, "http",
     [_auth_failed_result(), _ok_result()],
     None, "https", False,
     "auto HTTP + auth fail -> HTTPS retry succeeds"),
    (None, "http",
     [_auth_failed_result(), _auth_failed_result(), _auth_failed_result()],
     PermissionError, None, None,
     "auto HTTP + all retries fail -> PermissionError"),
    ("http", "http",
     [_auth_failed_result()],
     PermissionError, None, None,
     "user-specified HTTP + auth fail -> no retry"),
    (None, "https",
     [_auth_failed_result()],
     PermissionError, None, None,
     "auto HTTPS + auth fail -> no retry"),
    (None, "http",
     [_connectivity_result()],
     RuntimeError, None, None,
     "auto HTTP + connectivity fail -> no retry"),
    (None, "http",
     [_auth_failed_result(), _auth_failed_result(), _ok_result()],
     None, "https", True,
     "auto HTTP + HTTPS fails + legacy SSL succeeds"),
    (None, "http",
     [_load_auth_result(), _ok_result()],
     None, "https", False,
     "auto HTTP + LOAD_AUTH -> HTTPS retry succeeds"),
    (None, "http",
     [_parse_error_result()],
     RuntimeError, None, None,
     "auto HTTP + parse error -> no retry"),
    (None, "http",
     [_auth_failed_result(), _connectivity_result()],
     PermissionError, None, None,
     "auto HTTP auth fail + HTTPS unreachable -> PermissionError (not RuntimeError)"),
    (None, "http",
     [_load_auth_result(), _connectivity_result()],
     PermissionError, None, None,
     "auto HTTP login page + HTTPS unreachable -> PermissionError (not RuntimeError)"),
]
# fmt: on


@pytest.mark.parametrize(
    "user_protocol, detected_protocol, collector_results, expected_exception, "
    "expected_protocol, expected_legacy_ssl, description",
    PROTOCOL_RETRY_CASES,
    ids=[c[-1] for c in PROTOCOL_RETRY_CASES],
)
class TestProtocolRetry:
    """UC-85: Protocol fallback when auth fails on auto-detected HTTP."""

    @patch(f"{_MODULE}.detect_probes")
    @patch(f"{_MODULE}.ModemDataCollector")
    @patch(f"{_MODULE}.load_post_processor")
    @patch(f"{_MODULE}.load_parser_config")
    @patch(f"{_MODULE}.load_modem_config")
    @patch(f"{_MODULE}.detect_protocol")
    def test_protocol_retry(
        self,
        mock_detect: MagicMock,
        mock_load_modem: MagicMock,
        mock_load_parser: MagicMock,
        mock_load_post: MagicMock,
        mock_collector_cls: MagicMock,
        mock_probes: MagicMock,
        tmp_path: Path,
        # parametrize args
        user_protocol: str | None,
        detected_protocol: str,
        collector_results: list[ModemResult],
        expected_exception: type[Exception] | None,
        expected_protocol: str | None,
        expected_legacy_ssl: bool | None,
        description: str,
    ) -> None:
        """Verify protocol retry behavior for each scenario."""
        modem_dir = _setup_modem_dir(tmp_path)

        # Protocol detection — only called when user_protocol is None
        mock_detect.return_value = ConnectivityResult(
            success=True,
            protocol=detected_protocol,
            working_url=f"{detected_protocol}://192.168.100.1",
        )

        # Config loaders — return mocks (content irrelevant for this test)
        mock_load_modem.return_value = MagicMock()
        mock_load_parser.return_value = MagicMock()
        mock_load_post.return_value = MagicMock()

        # Probes — always succeed (not under test)
        mock_probes.return_value = {"supports_icmp": True, "supports_head": True}

        # Collector — return results in order (one per retry attempt)
        mock_collectors = []
        for result in collector_results:
            collector_instance = MagicMock()
            collector_instance.execute.return_value = result
            mock_collectors.append(collector_instance)
        mock_collector_cls.side_effect = mock_collectors

        if expected_exception is not None:
            with pytest.raises(expected_exception):
                _run_validation(
                    host="192.168.100.1",
                    protocol=user_protocol,
                    username="admin",
                    password="password",
                    modem_dir=modem_dir,
                    variant=None,
                )
        else:
            result = _run_validation(
                host="192.168.100.1",
                protocol=user_protocol,
                username="admin",
                password="password",
                modem_dir=modem_dir,
                variant=None,
            )
            assert result["protocol"] == expected_protocol
            assert result["legacy_ssl"] == expected_legacy_ssl


class TestProtocolRetryCollectorArgs:
    """Verify the collector is created with correct args on each retry."""

    @patch(f"{_MODULE}.detect_probes")
    @patch(f"{_MODULE}.ModemDataCollector")
    @patch(f"{_MODULE}.load_post_processor")
    @patch(f"{_MODULE}.load_parser_config")
    @patch(f"{_MODULE}.load_modem_config")
    @patch(f"{_MODULE}.detect_protocol")
    def test_https_retry_uses_correct_base_url(
        self,
        mock_detect: MagicMock,
        mock_load_modem: MagicMock,
        mock_load_parser: MagicMock,
        mock_load_post: MagicMock,
        mock_collector_cls: MagicMock,
        mock_probes: MagicMock,
        tmp_path: Path,
    ) -> None:
        """HTTPS retry passes https:// base_url and legacy_ssl=False."""
        modem_dir = _setup_modem_dir(tmp_path)
        mock_detect.return_value = ConnectivityResult(success=True, protocol="http", working_url="http://192.168.100.1")
        mock_config = MagicMock()
        mock_load_modem.return_value = mock_config
        mock_load_parser.return_value = MagicMock()
        mock_load_post.return_value = MagicMock()
        mock_probes.return_value = {"supports_icmp": True, "supports_head": True}

        # First attempt: auth fails. Second (HTTPS): succeeds.
        http_collector = MagicMock()
        http_collector.execute.return_value = _auth_failed_result()
        https_collector = MagicMock()
        https_collector.execute.return_value = _ok_result()
        mock_collector_cls.side_effect = [http_collector, https_collector]

        _run_validation("192.168.100.1", None, "admin", "pw", modem_dir, None)

        # First call: HTTP
        first_call = mock_collector_cls.call_args_list[0]
        assert first_call.kwargs["base_url"] == "http://192.168.100.1"
        assert first_call.kwargs["legacy_ssl"] is False

        # Second call: HTTPS
        second_call = mock_collector_cls.call_args_list[1]
        assert second_call.kwargs["base_url"] == "https://192.168.100.1"
        assert second_call.kwargs["legacy_ssl"] is False

    @patch(f"{_MODULE}.detect_probes")
    @patch(f"{_MODULE}.ModemDataCollector")
    @patch(f"{_MODULE}.load_post_processor")
    @patch(f"{_MODULE}.load_parser_config")
    @patch(f"{_MODULE}.load_modem_config")
    @patch(f"{_MODULE}.detect_protocol")
    def test_legacy_ssl_retry_uses_correct_args(
        self,
        mock_detect: MagicMock,
        mock_load_modem: MagicMock,
        mock_load_parser: MagicMock,
        mock_load_post: MagicMock,
        mock_collector_cls: MagicMock,
        mock_probes: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Legacy SSL retry passes https:// base_url and legacy_ssl=True."""
        modem_dir = _setup_modem_dir(tmp_path)
        mock_detect.return_value = ConnectivityResult(success=True, protocol="http", working_url="http://192.168.100.1")
        mock_load_modem.return_value = MagicMock()
        mock_load_parser.return_value = MagicMock()
        mock_load_post.return_value = MagicMock()
        mock_probes.return_value = {"supports_icmp": True, "supports_head": True}

        # All three attempts: HTTP fails, HTTPS fails, legacy SSL succeeds
        collectors = []
        for result in [_auth_failed_result(), _auth_failed_result(), _ok_result()]:
            c = MagicMock()
            c.execute.return_value = result
            collectors.append(c)
        mock_collector_cls.side_effect = collectors

        _run_validation("192.168.100.1", None, "admin", "pw", modem_dir, None)

        # Third call: HTTPS + legacy SSL
        third_call = mock_collector_cls.call_args_list[2]
        assert third_call.kwargs["base_url"] == "https://192.168.100.1"
        assert third_call.kwargs["legacy_ssl"] is True

    @patch(f"{_MODULE}.detect_probes")
    @patch(f"{_MODULE}.ModemDataCollector")
    @patch(f"{_MODULE}.load_post_processor")
    @patch(f"{_MODULE}.load_parser_config")
    @patch(f"{_MODULE}.load_modem_config")
    @patch(f"{_MODULE}.detect_protocol")
    def test_health_probes_use_successful_protocol(
        self,
        mock_detect: MagicMock,
        mock_load_modem: MagicMock,
        mock_load_parser: MagicMock,
        mock_load_post: MagicMock,
        mock_collector_cls: MagicMock,
        mock_probes: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Health probes run against the protocol that succeeded, not the original."""
        modem_dir = _setup_modem_dir(tmp_path)
        mock_detect.return_value = ConnectivityResult(success=True, protocol="http", working_url="http://192.168.100.1")
        mock_config = MagicMock()
        mock_load_modem.return_value = mock_config
        mock_load_parser.return_value = MagicMock()
        mock_load_post.return_value = MagicMock()
        mock_probes.return_value = {"supports_icmp": True, "supports_head": True}

        http_collector = MagicMock()
        http_collector.execute.return_value = _auth_failed_result()
        https_collector = MagicMock()
        https_collector.execute.return_value = _ok_result()
        mock_collector_cls.side_effect = [http_collector, https_collector]

        _run_validation("192.168.100.1", None, "admin", "pw", modem_dir, None)

        # detect_probes called with HTTPS url, not HTTP
        probe_call = mock_probes.call_args
        assert probe_call.args[1] == "https://192.168.100.1"
        assert probe_call.kwargs["legacy_ssl"] is False


class TestProtocolRetryNotTriggered:
    """Verify retry does NOT happen for non-auth failures."""

    @patch(f"{_MODULE}.detect_probes")
    @patch(f"{_MODULE}.ModemDataCollector")
    @patch(f"{_MODULE}.load_post_processor")
    @patch(f"{_MODULE}.load_parser_config")
    @patch(f"{_MODULE}.load_modem_config")
    @patch(f"{_MODULE}.detect_protocol")
    def test_no_retry_on_success(
        self,
        mock_detect: MagicMock,
        mock_load_modem: MagicMock,
        mock_load_parser: MagicMock,
        mock_load_post: MagicMock,
        mock_collector_cls: MagicMock,
        mock_probes: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Successful first attempt — no retry, collector created once."""
        modem_dir = _setup_modem_dir(tmp_path)
        mock_detect.return_value = ConnectivityResult(success=True, protocol="http", working_url="http://192.168.100.1")
        mock_load_modem.return_value = MagicMock()
        mock_load_parser.return_value = MagicMock()
        mock_load_post.return_value = MagicMock()
        mock_probes.return_value = {"supports_icmp": True, "supports_head": True}

        collector = MagicMock()
        collector.execute.return_value = _ok_result()
        mock_collector_cls.return_value = collector

        result = _run_validation("192.168.100.1", None, "admin", "pw", modem_dir, None)

        assert result["protocol"] == "http"
        assert mock_collector_cls.call_count == 1
