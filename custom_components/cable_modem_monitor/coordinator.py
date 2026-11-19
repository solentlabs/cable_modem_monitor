"""Data and health coordinators, and the runtime data types they live in.

``CableModemDataCoordinator`` runs one poll through Core and the jobs
that follow it; ``CableModemHealthCoordinator`` runs the health probe.
``CableModemRuntimeData`` (stored on ``entry.runtime_data``) and the
``CableModemConfigEntry`` type alias are used by all platform modules.

These live here, not in ``__init__.py`` (circular import risk) or
``const.py`` (which should stay a leaf module with no heavy imports).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Literal, TypeAlias

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from solentlabs.cable_modem_monitor_core.orchestration.models import (
    HealthInfo,
    ModemIdentity,
    ModemSnapshot,
)
from solentlabs.cable_modem_monitor_core.orchestration.signals import (
    CollectorSignal,
    ConnectionStatus,
)

from .channel_bond_notifier import (
    ChannelTotals,
    evaluate,
    format_onboarding_message,
    format_verification_request,
    needs_verification_request,
    verification_issue_url,
)
from .channel_bond_storage import (
    BondState,
    async_load_bond_state,
    async_save_bond_state,
)
from .const import (
    CONF_CHANNEL_IDENTITY,
    CONF_CHANNEL_ONBOARDING_ELIGIBLE,
    CONF_MODEL,
    ChannelIdentity,
)
from .mapping_manager import ChannelMap, build_channel_map

if TYPE_CHECKING:
    from solentlabs.cable_modem_monitor_core.orchestration.modem_health import (
        HealthMonitor,
    )
    from solentlabs.cable_modem_monitor_core.orchestration.orchestrator import (
        Orchestrator,
    )

# The package logger, not __name__: poll lines kept this name when they
# moved here from __init__.py, and user log filters, the diagnostics log
# buffer and analyze_logs.py key on it.
_LOGGER = logging.getLogger(__package__)

# Name of a destructive button operation currently in progress, or
# None when nothing is running. Acts as a mutex between the Restart
# and Reset buttons — a second press while one is in flight is
# refused. Distinct from Core's ``recovery_active`` flag: that one
# is a cadence signal, this one is a short-lived handler gate.
ActiveOperation = Literal["restart", "reset"]


@dataclass
class CableModemRuntimeData:
    """All runtime state for one config entry.

    Stored on ``entry.runtime_data``, replacing the v3.13 pattern of
    ``hass.data[DOMAIN][entry.entry_id]``.  HA manages cleanup
    automatically on unload.
    """

    data_coordinator: DataUpdateCoordinator[ModemSnapshot]
    health_coordinator: DataUpdateCoordinator[HealthInfo] | None
    orchestrator: Orchestrator
    health_monitor: HealthMonitor | None
    modem_identity: ModemIdentity
    channel_map: ChannelMap = field(default_factory=ChannelMap)
    # Names of the auth strategy's setup params stored in entry.data.
    setup_param_keys: tuple[str, ...] = ()
    # Set while a destructive button handler (Restart, Reset) is
    # running; cleared in the handler's ``finally`` block. Read by
    # other buttons that must refuse overlapping presses.
    active_operation: ActiveOperation | None = None


CableModemConfigEntry: TypeAlias = ConfigEntry[CableModemRuntimeData]  # noqa: UP040 — mypy doesn't support PEP 695 yet


async def _check_channel_bond_onboarding(
    hass: HomeAssistant,
    entry: CableModemConfigEntry,
    snapshot: ModemSnapshot,
    orchestrator: Orchestrator,
    model: str,
    verification_url: str | None,
) -> None:
    """Fire the one-time onboarding notification, and the one-time verification request, once the modem is online.

    Silent on the first post-upgrade poll (no retroactive onboarding) and
    while a recovery window is open. Persists the baseline to a dedicated
    ``Store`` — not entry data — so writes don't trip the integration's
    update listener.

    Totals changing after onboarding is deliberately not reported; see
    HA_ADAPTER_SPEC.md § Notifications and #197. The counts stay on the
    DS and US Channel Count sensors every poll.
    """
    modem_data = snapshot.modem_data
    if not modem_data:
        return
    system_info = modem_data.get("system_info", {})
    ds = system_info.get("downstream_channel_count")
    us = system_info.get("upstream_channel_count")
    if not isinstance(ds, int) or not isinstance(us, int):
        return

    current = ChannelTotals(downstream=ds, upstream=us)
    stored = await async_load_bond_state(hass, entry.entry_id)
    onboarding_eligible = bool(entry.data.get(CONF_CHANNEL_ONBOARDING_ELIGIBLE, False))

    action = evaluate(
        current=current,
        stored=stored,
        onboarding_eligible=onboarding_eligible,
        recovery_active=orchestrator.recovery_active,
    )

    if action == "onboarding":
        # A fresh entry is asked to help confirm its model inside the onboarding message.
        state = BondState(current.downstream, current.upstream, verification_asked=verification_url is not None)
        await async_save_bond_state(hass, entry.entry_id, state)
        await hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "Cable Modem Monitor: Modem online",
                "message": format_onboarding_message(model=model, current=current, verification_url=verification_url),
                "notification_id": f"cable_modem_monitor_onboarding_{entry.entry_id}",
            },
        )
        return

    # An entry with no onboarding left to fire is asked once on its own (HA_ADAPTER_SPEC § Channel bond onboarding).
    recovery_active = orchestrator.recovery_active
    if action == "silent_init":
        baseline = BondState(current.downstream, current.upstream)
        if verification_url is not None and needs_verification_request(
            current=current, stored=baseline, recovery_active=recovery_active
        ):
            await _ask_for_verification(hass, entry, model, baseline, verification_url)
        else:
            await async_save_bond_state(hass, entry.entry_id, baseline)
        return

    if (
        stored is not None
        and verification_url is not None
        and needs_verification_request(current=current, stored=stored, recovery_active=recovery_active)
    ):
        await _ask_for_verification(hass, entry, model, stored, verification_url)


async def _ask_for_verification(
    hass: HomeAssistant,
    entry: CableModemConfigEntry,
    model: str,
    stored: BondState,
    verification_url: str,
) -> None:
    """Ask the entry to help confirm its model, then record that it was asked."""
    await hass.services.async_call(
        "persistent_notification",
        "create",
        {
            "title": "Cable Modem Monitor: Help confirm your modem",
            "message": format_verification_request(model=model, verification_url=verification_url),
            "notification_id": f"cable_modem_monitor_verification_{entry.entry_id}",
        },
    )
    # Recorded only after the notification landed: a failed call is retried on the next poll.
    await async_save_bond_state(hass, entry.entry_id, replace(stored, verification_asked=True))


def _rebuild_channel_map(
    entry: ConfigEntry,
    snapshot: ModemSnapshot,
    identity_mode: ChannelIdentity,
) -> None:
    """Rebuild channel map on runtime_data after a poll.

    No-op when runtime_data is not yet set (first poll, before Step 9)
    or when the snapshot has no modem_data.
    """
    runtime = getattr(entry, "runtime_data", None)
    if runtime is None or snapshot.modem_data is None:
        return
    runtime.channel_map = build_channel_map(
        snapshot.modem_data.get("downstream", []),
        snapshot.modem_data.get("upstream", []),
        identity_mode,
    )


async def _announce_auth_stop(
    hass: HomeAssistant,
    entry: ConfigEntry,
    snapshot: ModemSnapshot,
    orchestrator: Orchestrator,
    model: str,
    lockout_reported: list[bool],
) -> None:
    """Tell the user why polling stopped when the auth breaker opens."""
    # Reauth is HA's surface for a credential lockout: a
    # "Reauthentication required" notification with the fix form.
    # https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/reauthentication-flow/
    # Contract: HA_ADAPTER_SPEC.md § Reauth Flow, UC-81, UC-81a, UC-87.
    # Core integrations trigger this by raising ConfigEntryAuthFailed,
    # but that also flips every entity unavailable; our Status sensor is
    # the sole outage announcer (#178), so we call the API directly.
    if snapshot.connection_status is not ConnectionStatus.AUTH_FAILED:
        return
    # Breaker open — not a lone AUTH_FAILED poll — is the trigger:
    # definitive credential rejections trip it immediately (UC-87),
    # stale-session failures only after 6 in a row (UC-81), so
    # transient flakes never interrupt the user.
    diagnostics = orchestrator.diagnostics()
    if not diagnostics.circuit_breaker_open:
        return
    # SignalPolicy.apply collapses four signals into AUTH_FAILED, and
    # the blocked polls that follow carry no signal at all, so the
    # latched trip reason is the only thing that tells the routes apart
    # (UC-81a).
    if diagnostics.circuit_trip_signal is CollectorSignal.AUTH_LOCKOUT:
        await _notify_auth_lockout(hass, entry, model, lockout_reported)
        return
    # HA dedupes inside async_start_reauth too; this guard keeps the
    # WARNING to one line per lockout instead of one per poll.
    if any(entry.async_get_active_flows(hass, {SOURCE_REAUTH})):
        return
    _LOGGER.warning(
        "Auth circuit breaker open [%s] — starting reauthentication flow",
        model,
    )
    entry.async_start_reauth(hass)


async def _notify_auth_lockout(
    hass: HomeAssistant,
    entry: ConfigEntry,
    model: str,
    lockout_reported: list[bool],
) -> None:
    """Notify about a firmware lockout without inviting a login attempt."""
    # Never the reauth form: submitting it calls validate_connection, a
    # real login, and the config flow is stateless by design (UC-86), so
    # the open breaker does not stop it. Prompting a locked-out user
    # invites hand-fed attempts at a modem that locked itself to stop
    # them (#117). The message says nothing about credentials for the
    # same reason.
    if lockout_reported[0]:
        return
    _LOGGER.warning(
        "Auth circuit breaker open [%s] — firmware lockout, not prompting for credentials",
        model,
    )
    # Waiting alone never resumes polling: the breaker clears only by
    # orchestrator reconstruction (ORCHESTRATION_SPEC § Auth Circuit
    # Breaker, "Recovery paths"), so the reload is part of the remedy.
    await hass.services.async_call(
        "persistent_notification",
        "create",
        {
            "title": "Cable Modem Monitor: Modem locked out logins",
            "message": (
                f"{model} reported a login lockout, so polling has stopped. "
                f"Wait for the modem to clear it, or power cycle the modem, "
                f"then reload the integration to resume polling. If it keeps "
                f"happening, download diagnostics (Settings > Devices & "
                f"Services > Cable Modem Monitor > ...) and open an issue."
            ),
            "notification_id": f"cable_modem_monitor_auth_lockout_{entry.entry_id}",
        },
    )
    # Latch only after the notification landed — a failed call must be
    # retried on the next poll, not swallowed into permanent silence.
    lockout_reported[0] = True


def _log_availability_transition(
    snapshot: ModemSnapshot,
    model: str,
    reported_unavailable: list[bool],
) -> None:
    """Log one line per availability edge rather than one per poll."""
    # The coordinator never raises (Core returns snapshots carrying an
    # error field instead), so HA's built-in once-per-transition
    # unavailable logging never engages and we track the edge ourselves.
    if snapshot.error:
        if not reported_unavailable[0]:
            reported_unavailable[0] = True
            _LOGGER.warning(
                "Modem unavailable [%s] — %s",
                model,
                snapshot.connection_status.value,
            )
    elif reported_unavailable[0]:
        reported_unavailable[0] = False
        _LOGGER.info("Modem available again [%s]", model)


def _build_snapshot_payload(snapshot: ModemSnapshot) -> dict[str, Any]:
    """Build the event bus payload from a ModemSnapshot.

    Full snapshot — PII stripping is the consumer's responsibility (CMMT).
    """
    return snapshot.to_event_payload().model_dump()


def coordinator_label(entry: ConfigEntry) -> str:
    """Coordinator name suffix: model and host, or the host alone."""
    host = entry.data[CONF_HOST]
    model = entry.data.get(CONF_MODEL, host)
    return f"{model} ({host})" if model != host else host


class CableModemDataCoordinator(DataUpdateCoordinator[ModemSnapshot]):
    """Poll the modem through Core, then run the per-poll jobs."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: CableModemConfigEntry,
        orchestrator: Orchestrator,
        modem_identity: ModemIdentity,
        scan_interval: int,
    ) -> None:
        """Create the data coordinator; a scan interval of 0 means manual polling only."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"Cable Modem {coordinator_label(entry)}",
            update_interval=(timedelta(seconds=scan_interval) if scan_interval > 0 else None),
            config_entry=entry,
        )
        self._entry = entry
        self._orchestrator = orchestrator
        self._model = entry.data.get(CONF_MODEL, entry.data[CONF_HOST])
        self._identity_mode = ChannelIdentity(entry.data.get(CONF_CHANNEL_IDENTITY, ChannelIdentity.ID))
        self._verification_url = verification_issue_url(modem_identity)
        # Mutable cells so the edge survives across polls (Silver
        # log-when-unavailable); see _log_availability_transition. The
        # lockout cell resets on entry reload, which is also the only thing
        # that clears the breaker, so it tracks it exactly.
        self._reported_unavailable = [False]
        self._lockout_reported = [False]

    async def _async_update_data(self) -> ModemSnapshot:
        """Run one poll and the jobs that follow it."""
        hass, entry, model = self.hass, self._entry, self._model
        snapshot = await hass.async_add_executor_job(self._orchestrator.get_modem_data)
        _log_availability_transition(snapshot, model, self._reported_unavailable)
        await _announce_auth_stop(hass, entry, snapshot, self._orchestrator, model, self._lockout_reported)
        _rebuild_channel_map(entry, snapshot, self._identity_mode)
        await _check_channel_bond_onboarding(hass, entry, snapshot, self._orchestrator, model, self._verification_url)
        hass.bus.async_fire(
            "cable_modem_monitor_data_updated",
            _build_snapshot_payload(snapshot),
        )
        return snapshot


class CableModemHealthCoordinator(DataUpdateCoordinator[HealthInfo]):
    """Run the lightweight health probe on its own interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: CableModemConfigEntry,
        health_monitor: HealthMonitor,
        health_check_interval: int,
    ) -> None:
        """Create the health coordinator; an interval of 0 disables scheduled probes."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"Cable Modem {coordinator_label(entry)} Health",
            update_interval=(timedelta(seconds=health_check_interval) if health_check_interval > 0 else None),
            config_entry=entry,
        )
        self._health_monitor = health_monitor

    async def _async_update_data(self) -> HealthInfo:
        """Run one health probe."""
        return await self.hass.async_add_executor_job(self._health_monitor.ping)
