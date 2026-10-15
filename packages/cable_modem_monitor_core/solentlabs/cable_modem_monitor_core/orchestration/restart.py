"""Restart action — one-shot command dispatch.

``run_restart`` sends the reboot instruction, clears the collector
session, and triggers a recovery window. It does not wait for the
modem to come back, probe for liveness, or observe the reboot —
post-reboot polling cadence belongs to the recovery module.

See ORCHESTRATION_SPEC.md § Restart Action for the full contract.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from .actions import execute_action
from .events import RestartCommandFailed, RestartCommandSent, RestartSessionRetry
from .logging import log_event
from .models import RestartResult

if TYPE_CHECKING:
    from ..models.modem_config.config import ModemConfig
    from .actions.base import ActionResult
    from .collector import ModemDataCollector
    from .recovery import Recovery

_logger = logging.getLogger(__name__)


class RestartNotSupportedError(Exception):
    """Modem does not declare actions.restart in modem.yaml."""


def _has_action_auth(restart_action: object) -> bool:
    """Return True if the restart action is an HttpAction with action_auth set."""
    from ..models.modem_config.actions import HttpAction

    return isinstance(restart_action, HttpAction) and restart_action.action_auth is not None


def _authenticate(collector: ModemDataCollector, model: str, start: float) -> RestartResult | None:
    """Establish the monitoring session; a failed result when the login failed, else None."""
    # Bypass the circuit breaker: the user asked for a restart, so a recent
    # bad-credentials streak shouldn't block the command.
    auth_result = collector.authenticate()
    if auth_result.success:
        return None
    log_event(_logger, RestartCommandFailed(model=model, reason=f"auth failed — {auth_result.error}"))
    return RestartResult(success=False, elapsed_seconds=time.monotonic() - start, error="command_failed")


def _refused_stale_session(collector: ModemDataCollector, restart_action: object, result: ActionResult) -> bool:
    """A refusal on the reused monitoring session: the modem expired it since the last poll (UC-21a)."""
    return (
        not result.success
        and result.session_refused
        and not _has_action_auth(restart_action)
        and collector.session_reused
    )


def run_restart(
    collector: ModemDataCollector,
    modem_config: ModemConfig,
    recovery: Recovery,
) -> RestartResult:
    """Send the reboot command and trigger a recovery window.

    Procedure:

    1. Raise ``RestartNotSupportedError`` if ``actions.restart`` is
       None.
    2. Establish the monitoring session via ``collector.authenticate()``
       — unless ``actions.restart`` has ``action_auth`` set, in which
       case ``execute_action`` authenticates on a separate fresh session
       and the monitoring session is not needed for the restart command.
    3. Execute the restart action. A refusal on the reused monitoring
       session clears it, logs in fresh and executes the action once
       more. Stop if the result is still a failure.
    4. Clear the collector session (forces fresh auth on the next
       poll — some firmware invalidates sessions after a reboot).
    5. Call ``recovery.begin("restart_command")`` so subsequent polls
       run at recovery cadence.
    6. Return a ``RestartResult``.

    Typical duration: 2–5 seconds. The caller does not block on the
    reboot itself. Any exception between steps 2 and 4, or a failed
    ``ActionResult`` from step 3, yields
    ``RestartResult(success=False, error="command_failed")`` — the
    only error token this function emits.
    """
    # Step 1 — capability guard. Buttons that can't exist as HA
    # entities still reach here via service calls and tests.
    actions = modem_config.actions
    if actions is None or actions.restart is None:
        raise RestartNotSupportedError("Modem does not declare actions.restart")

    start = time.monotonic()
    model = modem_config.model

    # Steps 2–4 are wrapped in one try/except. Any raise inside maps
    # to the single ``command_failed`` token; the reboot didn't
    # dispatch cleanly and the caller should see it as a failed
    # command, not as a nuanced taxonomy of why.
    try:
        # Step 2 — authenticate.
        #
        # Skip when action_auth is set — execute_action will authenticate
        # on a separate fresh session for the action. Establishing the
        # monitoring session here is unnecessary: it is not used for the
        # restart command (e.g., Hub 5 has no monitoring auth at all).
        if not _has_action_auth(actions.restart):
            auth_failure = _authenticate(collector, model, start)
            if auth_failure is not None:
                return auth_failure

        # Step 3 — execute the reboot action. Connection errors /
        # timeouts inside the HTTP executor are already swallowed
        # there (the modem IS rebooting during the POST); anything
        # that surfaces here is a genuine dispatch failure.
        #
        # A returned failure is one too: per-action auth can be refused,
        # or the modem can answer the command 401/404. Neither raises,
        # and neither rebooted anything (#82).
        action_result = execute_action(collector, modem_config, actions.restart)

        # A reused session the modem now refuses is stale, as in polling
        # (UC-21): clear it, log in fresh, send once more. Only a refusal
        # retries, so a modem that rebooted is never asked twice.
        if _refused_stale_session(collector, actions.restart, action_result):
            log_event(
                _logger,
                RestartSessionRetry(
                    model=model,
                    reason=action_result.message,
                    session_age_seconds=collector.session_age_seconds,
                ),
            )
            collector.clear_session()
            auth_failure = _authenticate(collector, model, start)
            if auth_failure is not None:
                return auth_failure
            action_result = execute_action(collector, modem_config, actions.restart)

        if not action_result.success:
            elapsed = time.monotonic() - start
            # Session age tells a refusal on a long-held session from one
            # on a fresh login (#218). action_auth never used this session.
            session_age = None if _has_action_auth(actions.restart) else collector.session_age_seconds
            log_event(
                _logger,
                RestartCommandFailed(model=model, reason=action_result.message, session_age_seconds=session_age),
            )
            # No command reached the modem, so there is no reboot for
            # recovery to watch. A session refused after the retry is the
            # fresh login's; one that was not refused is still good.
            return RestartResult(
                success=False,
                elapsed_seconds=elapsed,
                error="command_failed",
            )

        # Step 4 — clear the session locally. MB7621-class firmware
        # invalidates sessions server-side during the reboot while
        # our cookie still looks valid; clearing now forces the next
        # poll to re-auth fresh instead of tripping LOAD_AUTH.
        collector.clear_session()
    except Exception as exc:  # noqa: BLE001
        elapsed = time.monotonic() - start
        log_event(_logger, RestartCommandFailed(model=model, reason=str(exc)))
        return RestartResult(
            success=False,
            elapsed_seconds=elapsed,
            error="command_failed",
        )

    elapsed = time.monotonic() - start
    log_event(_logger, RestartCommandSent(model=model, elapsed_seconds=elapsed))

    # Step 5 — hand off to Recovery. begin() fires the observer so
    # HA's cadence listener drops the data-coordinator interval;
    # from here on, post-reboot observation is polling's job.
    recovery.begin("restart_command")

    # Step 6 — report. success=True iff steps 2–4 all completed. A lost
    # connection is a reboot or a stalled web server; Core cannot tell
    # which, so it reports the command unacknowledged.
    return RestartResult(
        success=True,
        elapsed_seconds=elapsed,
        acknowledged=not action_result.connection_lost,
    )
