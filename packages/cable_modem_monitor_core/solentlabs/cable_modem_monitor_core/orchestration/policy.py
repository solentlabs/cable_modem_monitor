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
    """Auth failure tracking and circuit breaker.

    Owns the auth_failure_streak counter and circuit_open flag. Also
    tracks connectivity failures with exponential backoff —
    connectivity timeouts don't count toward the auth circuit breaker.

    Circuit breaker trip modes:
    - AUTH_FAILED / AUTH_LOCKOUT: trip immediately (credentials rejected).
    - LOAD_AUTH: trip at threshold (session issue, may self-correct).

    Args:
        collector: ModemDataCollector for session clearing on LOAD_AUTH.
        auth_failure_threshold: Consecutive LOAD_AUTH failures before
            tripping the circuit breaker. AUTH_FAILED and AUTH_LOCKOUT
            trip immediately regardless of this value.
        max_connectivity_backoff: Maximum polls to skip during
            connectivity backoff. Backoff grows as
            min(2^(streak-1), max).
    """

    def __init__(
        self,
        collector: ModemDataCollector,
        auth_failure_threshold: int = 6,
        max_connectivity_backoff: int = 6,
        stale_recovery_threshold: int = 2,
        model: str = "",
    ) -> None:
        self._collector = collector
        self._threshold = auth_failure_threshold
        self._max_connectivity_backoff = max_connectivity_backoff
        self._stale_recovery_threshold = stale_recovery_threshold
        self._model = model

        self._auth_failure_streak: int = 0
        self._circuit_open: bool = False
        self._stale_session_recovery_streak: int = 0
        self._session_reuse_disabled: bool = False

        # Connectivity backoff — separate from auth
        self._connectivity_streak: int = 0
        self._connectivity_backoff: int = 0

    @property
    def circuit_open(self) -> bool:
        """Whether the circuit breaker is open (polling stopped)."""
        return self._circuit_open

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

    @property
    def stale_session_recovery_streak(self) -> int:
        """Current consecutive recovered stale-session streak."""
        return self._stale_session_recovery_streak

    @property
    def session_reuse_disabled(self) -> bool:
        """Whether session reuse is disabled for the current runtime."""
        return self._session_reuse_disabled

    def should_attempt_session_reuse(self) -> bool:
        """Whether the next poll should try the cached session first."""
        return not self._session_reuse_disabled

    def record_stale_session_recovery(self) -> None:
        """Record a consecutive same-poll stale-session recovery.

        After repeated consecutive recovered LOAD_AUTH events, disable
        session reuse for the rest of the runtime to avoid burning the
        first request of each poll on firmware with chronically short
        session TTLs.
        """
        if self._session_reuse_disabled:
            return

        self._stale_session_recovery_streak += 1
        if self._stale_session_recovery_streak < self._stale_recovery_threshold:
            return

        self._session_reuse_disabled = True
        _logger.info(
            "Recovered stale-session streak reached threshold [%s] — "
            "disabling session reuse for this runtime "
            "(%d consecutive recoveries)",
            self._model,
            self._stale_session_recovery_streak,
        )

    def reset_stale_session_recovery_streak(self) -> None:
        """Reset the consecutive stale-session recovery streak.

        A normal successful poll or any unrecovered failure breaks the
        pattern. Once session reuse is disabled, the threshold-reaching
        streak is left intact for diagnostics until reset_auth() or
        process restart.
        """
        if self._session_reuse_disabled:
            return

        self._stale_session_recovery_streak = 0

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
            return True

        _logger.info("Connectivity backoff cleared [%s], retrying", self._model)
        return False

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
            self._trip_circuit_breaker()
            return ConnectionStatus.AUTH_FAILED

        if signal == CollectorSignal.AUTH_LOCKOUT:
            self._auth_failure_streak += 1
            _logger.warning(
                "Auth lockout [%s] — firmware anti-brute-force triggered, stopping immediately (streak: %d)",
                self._model,
                self._auth_failure_streak,
            )
            self._trip_circuit_breaker()
            return ConnectionStatus.AUTH_FAILED

        if signal == CollectorSignal.LOAD_AUTH:
            self._auth_failure_streak += 1
            self._collector.clear_session()
            _logger.info(
                "LOAD_AUTH [%s] — retry failed, reporting auth_failed (streak: %d/%d)",
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
            _logger.warning(
                "Connection failure [%s] — unreachable (streak: %d, backoff: %d polls)",
                self._model,
                self._connectivity_streak,
                backoff,
            )
            return ConnectionStatus.UNREACHABLE

        if signal == CollectorSignal.LOAD_ERROR:
            _logger.warning("Resource load error [%s] — reporting unreachable", self._model)
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
        self._stale_session_recovery_streak = 0
        self._session_reuse_disabled = False
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
            "Auth failed [%s] — wrong credentials or strategy mismatch (streak: %d)",
            self._model,
            self._auth_failure_streak,
        )

    def _trip_circuit_breaker(self) -> None:
        """Trip the circuit breaker immediately.

        Used for AUTH_FAILED and AUTH_LOCKOUT — credentials are known
        bad, retrying is pointless and risks modem anti-brute-force.
        """
        self._circuit_open = True
        _logger.error(
            "Auth circuit breaker OPEN [%s] — credentials rejected. "
            "Polling stopped. Reconfigure credentials to resume.",
            self._model,
        )

    def _maybe_trip_circuit_breaker(self) -> None:
        """Trip the circuit breaker if threshold reached.

        Used for LOAD_AUTH — session issues that may self-correct.
        """
        if self._auth_failure_streak >= self._threshold:
            self._circuit_open = True
            _logger.error(
                "Auth circuit breaker OPEN [%s] — %d consecutive auth failures. "
                "Polling stopped. Reconfigure credentials to resume.",
                self._model,
                self._auth_failure_streak,
            )
