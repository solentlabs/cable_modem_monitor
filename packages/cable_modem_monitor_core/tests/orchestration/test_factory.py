"""Tests for ``orchestration/factory.py`` entry points.

Covers ``create_orchestrator``'s HealthMonitor wiring.
"""

from __future__ import annotations

from typing import Any

from solentlabs.cable_modem_monitor_core.orchestration.factory import create_orchestrator

# ---------------------------------------------------------------------------
# create_orchestrator HealthMonitor wiring
# ---------------------------------------------------------------------------


def _none_auth_modem_config() -> Any:
    """Build a minimal ModemConfig with NoneAuth for factory tests.

    Uses ``model_validate`` so all defaults are applied — same as
    production loading from modem.yaml.
    """
    from solentlabs.cable_modem_monitor_core.models.modem_config import ModemConfig

    return ModemConfig.model_validate(
        {
            "manufacturer": "Solent Labs",
            "model": "T100",
            "transport": "http",
            "default_host": "192.168.100.1",
            "status": "unsupported",
            "auth": {"strategy": "none"},
        }
    )


class TestCreateOrchestratorHealthMonitor:
    """``create_orchestrator`` wires HealthMonitor conditionally on probe flags."""

    def test_health_monitor_created_when_icmp_supported(self) -> None:
        """``supports_icmp=True`` triggers HealthMonitor instantiation."""
        orchestrator, health_monitor, identity = create_orchestrator(
            modem_config=_none_auth_modem_config(),
            parser_config=None,
            post_processor=None,
            base_url="http://192.168.100.1",
            supports_icmp=True,
            http_probe=False,
        )
        assert orchestrator is not None
        assert health_monitor is not None
        assert identity.model == "T100"

    def test_health_monitor_created_when_http_probe_enabled(self) -> None:
        """``http_probe=True`` alone (without ICMP) also triggers instantiation."""
        _, health_monitor, _ = create_orchestrator(
            modem_config=_none_auth_modem_config(),
            parser_config=None,
            post_processor=None,
            base_url="http://192.168.100.1",
            supports_icmp=False,
            http_probe=True,
        )
        assert health_monitor is not None

    def test_health_monitor_omitted_when_no_probes(self) -> None:
        """Neither probe enabled → ``health_monitor`` is None.

        Matches the path a modem with no health surface uses — the
        orchestrator runs without a health coordinator.
        """
        orchestrator, health_monitor, _ = create_orchestrator(
            modem_config=_none_auth_modem_config(),
            parser_config=None,
            post_processor=None,
            base_url="http://192.168.100.1",
            supports_icmp=False,
            http_probe=False,
        )
        assert orchestrator is not None
        assert health_monitor is None
