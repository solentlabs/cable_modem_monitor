"""Signal policy — auth failure tracking, backoff, circuit breaker.

Maps CollectorSignal failures to ConnectionStatus with side effects:
auth failure streak tracking, login backoff, and circuit breaker
tripping after repeated auth failures.

See RUNTIME_POLLING_SPEC.md for behavioral rules.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .signals import CollectorSignal, ConnectionStatus

if TYPE_CHECKING:
    from .collector import ModemDataCollector
    from .models import ModemResult

_logger = logging.getLogger(__name__)


class SignalPolicy:
    """Auth failure tracking, backoff, and circuit breaker.

    Owns the auth_failure_streak counter, backoff_remaining counter,
    and circuit_open flag. Also tracks connectivity failures with
    exponential backoff — connectivity timeouts don't count toward
    the auth circuit breaker.

    Args:
        collector: ModemDataCollector for session clearing on LOAD_AUTH.
        auth_failure_threshold: Consecutive auth failures before tripping
            the circuit breaker.
        max_connectivity_backoff: Maximum polls to skip during
            connectivity backoff. Backoff grows as
            min(2^(streak-1), max).
    """

    def __init__(
        self,
        collector: ModemDataCollector,
        auth_failure_threshold: int = 6,
        max_connectivity_backoff: int = 6,
        model: str = "",
    ) -> None:
        self._collector = collector
        self._threshold = auth_failure_threshold
        self._max_connectivity_backoff = max_connectivity_backoff
        self._model = model

        self._auth_failure_streak: int = 0
        self._circuit_open: bool = False
        self._backoff_remaining: int = 0

        # Connectivity backoff — separate from auth
        self._connectivity_streak: int = 0
        self._connectivity_backoff: int = 0

    @property
    def circuit_open(self) -> bool:
        """Whether the circuit breaker is open (polling stopped)."""
        return self._circuit_open

    @property
    def backoff_remaining(self) -> int:
        """Number of polls remaining in the backoff window."""
        return self._backoff_remaining

    @property
    def auth_failure_streak(self) -> int:
        """Current consecutive auth failure count."""
        return self._auth_failure_streak

    @property
    def connectivity_streak(self) -> int:
        """Current consecutive connectivity failure count."""
        return self._connectivity_streak

    @property
    def connectivity_backoff_remaining(self) -> int:
        """Polls remaining in the connectivity backoff window."""
        return self._connectivity_backoff

    def check_connectivity_backoff(self) -> bool:
        """Check and decrement the connectivity backoff counter.

        Returns True if backoff is active (caller should skip collection).
        Returns False if backoff is cleared or was not active.
        """
        if self._connectivity_backoff <= 0:
            return False

        self._connectivity_backoff -= 1
        if self._connectivity_backoff > 0:
            _logger.info(
                "Connectivity backoff active [%s] (%d remaining), skipping poll",
                self._model,
                self._connectivity_backoff,
            )
        else:
            _logger.info("Connectivity backoff cleared [%s], retrying", self._model)
        return True

    def check_backoff(self) -> bool:
        """Check and decrement the backoff counter.

        Returns True if backoff is active (caller should skip collection).
        Returns False if backoff is cleared or was not active.
        """
        if self._backoff_remaining <= 0:
            return False

        self._backoff_remaining -= 1
        if self._backoff_remaining > 0:
            _logger.info(
                "Backoff active [%s] (%d remaining), skipping collection",
                self._model,
                self._backoff_remaining,
            )
        else:
            _logger.info("Backoff cleared [%s], resuming", self._model)
        return True

    def apply(self, result: ModemResult) -> ConnectionStatus:
        """Map a collector failure signal to connection status.

        Called only when result.success is False. Updates auth failure
        streak, backoff, and circuit breaker as side effects.

        Args:
            result: Failed collection result with signal and error.

        Returns:
            ConnectionStatus to use for the snapshot.
        """
        signal = result.signal

        # Any non-connectivity failure means the modem responded —
        # clear connectivity backoff since the network path works.
        if signal != CollectorSignal.CONNECTIVITY:
            self._connectivity_streak = 0
            self._connectivity_backoff = 0

        if signal == CollectorSignal.AUTH_FAILED:
            self._auth_failure_streak += 1
            self._log_auth_failure()
            self._maybe_trip_circuit_breaker()
            return ConnectionStatus.AUTH_FAILED

        if signal == CollectorSignal.AUTH_LOCKOUT:
            self._auth_failure_streak += 1
            self._backoff_remaining = 3
            _logger.warning(
                "Auth lockout [%s] — firmware anti-brute-force triggered, "
                "suppressing login for 3 polls (streak: %d/%d)",
                self._model,
                self._auth_failure_streak,
                self._threshold,
            )
            self._maybe_trip_circuit_breaker()
            return ConnectionStatus.AUTH_FAILED

        if signal == CollectorSignal.LOAD_AUTH:
            self._auth_failure_streak += 1
            self._collector.clear_session()
            _logger.info(
                "LOAD_AUTH [%s] — clearing session, reporting auth_failed " "(streak: %d/%d)",
                self._model,
                self._auth_failure_streak,
                self._threshold,
            )
            self._maybe_trip_circuit_breaker()
            return ConnectionStatus.AUTH_FAILED

        if signal == CollectorSignal.CONNECTIVITY:
            self._connectivity_streak += 1
            backoff = min(
                2 ** (self._connectivity_streak - 1),
                self._max_connectivity_backoff,
            )
            self._connectivity_backoff = backoff
            _logger.info(
                "Connection failure [%s] — unreachable (streak: %d, " "backoff: %d polls)",
                self._model,
                self._connectivity_streak,
                backoff,
            )
            return ConnectionStatus.UNREACHABLE

        if signal == CollectorSignal.LOAD_ERROR:
            _logger.info("Resource load error [%s] — reporting unreachable", self._model)
            return ConnectionStatus.UNREACHABLE

        if signal == CollectorSignal.PARSE_ERROR:
            _logger.warning("Parse error [%s] — reporting parser_issue", self._model)
            return ConnectionStatus.PARSER_ISSUE

        # Defensive — should never reach here
        _logger.warning("Unknown signal: %s", signal)
        return ConnectionStatus.UNREACHABLE

    def reset(self) -> None:
        """Reset all auth-related state.

        Called after credential reconfiguration or successful auth.
        """
        self._auth_failure_streak = 0
        self._circuit_open = False
        self._backoff_remaining = 0
        self._connectivity_streak = 0
        self._connectivity_backoff = 0

    def reset_connectivity(self) -> None:
        """Reset connectivity backoff state.

        Called when the user requests a manual refresh or when health
        status transitions back to responsive.
        """
        self._connectivity_streak = 0
        self._connectivity_backoff = 0

    def clear_streak(self) -> None:
        """Clear auth and connectivity streaks on successful collection."""
        self._auth_failure_streak = 0
        self._connectivity_streak = 0
        self._connectivity_backoff = 0

    def _log_auth_failure(self) -> None:
        """Log auth failure with streak context."""
        _logger.info(
            "Auth failed [%s] — wrong credentials or strategy mismatch " "(streak: %d/%d)",
            self._model,
            self._auth_failure_streak,
            self._threshold,
        )

    def _maybe_trip_circuit_breaker(self) -> None:
        """Trip the circuit breaker if threshold reached."""
        if self._auth_failure_streak >= self._threshold:
            self._circuit_open = True
            _logger.error(
                "Auth circuit breaker OPEN [%s] — %d consecutive auth failures. "
                "Polling stopped. Reconfigure credentials to resume.",
                self._model,
                self._auth_failure_streak,
            )
