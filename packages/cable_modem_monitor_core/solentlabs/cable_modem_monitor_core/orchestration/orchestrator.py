"""Orchestrator — policy engine for modem data collection.

Coordinates ModemDataCollector, HealthMonitor, and RestartMonitor.
Delegates signal policy to SignalPolicy, status derivation to pure
functions, and restart actions to the actions module.

Consumers call get_modem_data() when they want data. The orchestrator
applies backoff and lockout protection regardless of why it was called.
No scheduling or threads — consumers manage their own cadence.

See ORCHESTRATION_SPEC.md for interface contracts and
RUNTIME_POLLING_SPEC.md for behavioral rules.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from .actions import execute_action
from .models import ModemSnapshot, OrchestratorDiagnostics, RestartResult
from .policy import SignalPolicy
from .restart import RestartMonitor
from .signals import CollectorSignal, ConnectionStatus, DocsisStatus, RestartPhase
from .status import derive_connection_status, derive_docsis_status

if TYPE_CHECKING:
    import threading

    from ..models.modem_config.config import ModemConfig
    from .collector import ModemDataCollector
    from .models import HealthInfo, ModemResult
    from .modem_health import HealthMonitor

_logger = logging.getLogger(__name__)


class RestartNotSupportedError(Exception):
    """Modem does not declare actions.restart in modem.yaml."""


class Orchestrator:
    """Policy engine for modem data collection.

    Coordinates the collector with backoff, circuit breaker, and status
    derivation. Exposes a synchronous API — consumers wrap it for their
    platform's scheduling model.

    Args:
        collector: ModemDataCollector instance (reused across polls).
        health_monitor: Optional health probe monitor. None if the
            modem doesn't support ICMP or HTTP HEAD probes.
        modem_config: Parsed modem.yaml config. Used for behaviors
            and actions.
    """

    AUTH_FAILURE_THRESHOLD: int = 6

    def __init__(
        self,
        collector: ModemDataCollector,
        health_monitor: HealthMonitor | None,
        modem_config: ModemConfig,
    ) -> None:
        self._collector = collector
        self._health_monitor = health_monitor
        self._modem_config = modem_config

        # Policy
        self._policy = SignalPolicy(collector, self.AUTH_FAILURE_THRESHOLD)
        self._is_restarting: bool = False
        self._last_status: ConnectionStatus | None = None

        # First-poll verbose logging — INFO on first poll and after
        # reset_auth(), DEBUG on steady-state
        self._first_poll_complete: bool = False

        # Diagnostics state
        self._last_poll_duration: float | None = None
        self._last_poll_timestamp: float | None = None

    def get_modem_data(self) -> ModemSnapshot:
        """Execute a data collection cycle.

        Sequence:
        1. If is_restarting, return UNREACHABLE immediately
        2. Check circuit breaker — if open, return AUTH_FAILED
        3. Check backoff — if active, decrement and return AUTH_FAILED
        4. Run ModemDataCollector
        5. If collection failed, apply signal policy
        6. On success: reset streak, derive statuses
        7. Detect state transitions
        8. Return ModemSnapshot

        Returns:
            ModemSnapshot with modem data, health info, and derived
            status fields.
        """
        start = time.monotonic()

        try:
            snapshot = self._execute_poll()
        finally:
            self._last_poll_duration = time.monotonic() - start
            self._last_poll_timestamp = start

        return snapshot

    def restart(
        self,
        cancel_event: threading.Event | None = None,
        response_timeout: int = 120,
        channel_stabilization_timeout: int = 300,
        probe_interval: int = 10,
    ) -> RestartResult:
        """Initiate a modem restart and monitor recovery.

        Sequence:
        1. Check is_restarting — if True, return error
        2. Set is_restarting = True
        3. Authenticate (session may have been cleared by logout)
        4. Execute restart action
        5. Clear session (old session is dead)
        5. Hand off to RestartMonitor for two-phase recovery
        6. Set is_restarting = False
        7. Return result

        Connection drop during the restart command is expected (the
        modem is rebooting) and already handled by the action layer.

        Args:
            cancel_event: Optional threading.Event for cooperative
                cancellation. Setting it causes the monitor to exit
                within one probe_interval.
            response_timeout: Max seconds to wait for modem to respond
                after restart.
            channel_stabilization_timeout: Max seconds to wait for
                stable channel counts after response. 0 to skip.
            probe_interval: Seconds between probes during recovery.

        Returns:
            RestartResult with recovery outcome.

        Raises:
            RestartNotSupportedError: If modem has no restart action.
        """
        actions = self._modem_config.actions
        if actions is None or actions.restart is None:
            raise RestartNotSupportedError("Modem does not declare actions.restart")

        if self._is_restarting:
            return RestartResult(
                success=False,
                phase_reached=RestartPhase.COMMAND_SENT,
                elapsed_seconds=0.0,
                error="Restart already in progress",
            )

        start = time.monotonic()
        self._is_restarting = True
        try:
            # Authenticate — session may have been cleared by logout
            self._collector.authenticate()

            # Send restart command
            execute_action(self._collector, self._modem_config, actions.restart)
            self._collector.clear_session()
            _logger.info(
                "Restart command sent — session cleared (%.1fs)",
                time.monotonic() - start,
            )

            # Two-phase recovery
            monitor = RestartMonitor(
                collector=self._collector,
                health_monitor=self._health_monitor,
                response_timeout=response_timeout,
                channel_stabilization_timeout=channel_stabilization_timeout,
                probe_interval=probe_interval,
            )
            return monitor.monitor_recovery(cancel_event)

        except Exception as exc:
            elapsed = time.monotonic() - start
            _logger.error("Restart failed: %s", exc)
            return RestartResult(
                success=False,
                phase_reached=RestartPhase.COMMAND_SENT,
                elapsed_seconds=elapsed,
                error=str(exc),
            )
        finally:
            self._is_restarting = False

    def reset_auth(self) -> None:
        """Reset auth state after credential reconfiguration.

        Called by the client after the user updates credentials.
        Clears all auth-related state so the next get_modem_data()
        starts with a clean slate.
        """
        self._policy.reset()
        self._collector.clear_session()
        self._first_poll_complete = False
        _logger.info("Auth state reset — next poll will attempt fresh login")

    def diagnostics(self) -> OrchestratorDiagnostics:
        """Return a read-only snapshot of operational diagnostics.

        No side effects — safe to call at any time.
        """
        return OrchestratorDiagnostics(
            poll_duration=self._last_poll_duration,
            auth_failure_streak=self._policy.auth_failure_streak,
            circuit_breaker_open=self._policy.circuit_open,
            session_is_valid=self._collector.session_is_valid,
            last_poll_timestamp=self._last_poll_timestamp,
        )

    @property
    def status(self) -> ConnectionStatus:
        """Current connection status from the last get_modem_data() call.

        Returns UNREACHABLE if never polled.
        """
        if self._last_status is None:
            return ConnectionStatus.UNREACHABLE
        return self._last_status

    @property
    def is_restarting(self) -> bool:
        """Whether a restart is currently in progress."""
        return self._is_restarting

    @property
    def supports_restart(self) -> bool:
        """Whether the modem declares a restart action in modem.yaml."""
        actions = self._modem_config.actions
        return actions is not None and actions.restart is not None

    # ------------------------------------------------------------------
    # Internal — poll execution
    # ------------------------------------------------------------------

    def _execute_poll(self) -> ModemSnapshot:
        """Run the collection pipeline with policy checks."""
        # Restart guard
        if self._is_restarting:
            return self._make_snapshot(
                ConnectionStatus.UNREACHABLE,
                DocsisStatus.UNKNOWN,
            )

        # Circuit breaker
        if self._policy.circuit_open:
            _logger.error("Circuit breaker is OPEN — polling stopped. " "Reconfigure credentials to resume.")
            return self._make_snapshot(
                ConnectionStatus.AUTH_FAILED,
                DocsisStatus.UNKNOWN,
                error="Circuit breaker open — reconfigure credentials",
            )

        # Backoff
        if self._policy.check_backoff():
            return self._make_snapshot(
                ConnectionStatus.AUTH_FAILED,
                DocsisStatus.UNKNOWN,
                error="Login backoff active",
            )

        # Log poll context — INFO on first poll, DEBUG on steady-state
        self._log_poll_context()

        # Run collector
        result = self._collector.execute()

        if not result.success:
            self._log_poll_result(result)
            return self._handle_failure(result)

        self._first_poll_complete = True
        self._log_poll_result(result)
        return self._handle_success(result)

    def _handle_failure(self, result: ModemResult) -> ModemSnapshot:
        """Apply signal policy for a failed collection."""
        status = self._policy.apply(result)
        self._detect_transition(status)
        return self._make_snapshot(
            status,
            DocsisStatus.UNKNOWN,
            collector_signal=result.signal,
            error=result.error,
        )

    def _handle_success(self, result: ModemResult) -> ModemSnapshot:
        """Process a successful collection result."""
        self._policy.clear_streak()

        # Notify health monitor
        if self._health_monitor is not None:
            self._health_monitor.update_from_collection(time.monotonic())

        modem_data = result.modem_data
        assert modem_data is not None  # guaranteed by success=True

        # Derive statuses
        connection_status = derive_connection_status(modem_data)
        docsis_status = derive_docsis_status(modem_data)

        # Read latest health info
        health_info: HealthInfo | None = None
        if self._health_monitor is not None:
            health_info = self._health_monitor.latest

        self._detect_transition(connection_status)

        return self._make_snapshot(
            connection_status,
            docsis_status,
            modem_data=modem_data,
            health_info=health_info,
            collector_signal=CollectorSignal.OK,
        )

    # ------------------------------------------------------------------
    # Internal — transition detection
    # ------------------------------------------------------------------

    def _detect_transition(self, new_status: ConnectionStatus) -> None:
        """Log status transitions for diagnostics."""
        old_status = self._last_status
        self._last_status = new_status

        if old_status is not None and old_status != new_status:
            _logger.info(
                "Status transition: %s → %s (session_valid: %s)",
                old_status.value,
                new_status.value,
                self._collector.session_is_valid,
            )

    # ------------------------------------------------------------------
    # Internal — first-poll verbose logging
    # ------------------------------------------------------------------

    def _log_poll_context(self) -> None:
        """Log auth context before poll. INFO on first poll, DEBUG after."""
        log = _logger.info if not self._first_poll_complete else _logger.debug

        auth = self._modem_config.auth
        strategy = type(auth).__name__ if auth is not None else "none"
        has_creds = bool(self._collector._username or self._collector._password)
        session_valid = self._collector.session_is_valid

        log(
            "Poll — auth: %s, url: %s, credentials: %s, session_valid: %s",
            strategy,
            self._collector._base_url,
            "yes" if has_creds else "no",
            session_valid,
        )

    def _log_poll_result(self, result: ModemResult) -> None:
        """Log poll outcome. INFO on first poll or failure, DEBUG after."""
        if not result.success:
            _logger.warning(
                "Poll failed — signal: %s, error: %s",
                result.signal.value,
                result.error,
            )
            return

        if not self._first_poll_complete:
            ds = len(result.modem_data.get("downstream", [])) if result.modem_data else 0
            us = len(result.modem_data.get("upstream", [])) if result.modem_data else 0
            _logger.info(
                "First poll succeeded — %d downstream, %d upstream channels",
                ds,
                us,
            )

    # ------------------------------------------------------------------
    # Internal — snapshot construction
    # ------------------------------------------------------------------

    def _make_snapshot(
        self,
        connection_status: ConnectionStatus,
        docsis_status: DocsisStatus,
        *,
        modem_data: dict[str, Any] | None = None,
        health_info: HealthInfo | None = None,
        collector_signal: CollectorSignal = CollectorSignal.OK,
        error: str = "",
    ) -> ModemSnapshot:
        """Build a ModemSnapshot with defaults."""
        return ModemSnapshot(
            connection_status=connection_status,
            docsis_status=docsis_status,
            modem_data=modem_data,
            health_info=health_info,
            collector_signal=collector_signal,
            error=error,
        )
