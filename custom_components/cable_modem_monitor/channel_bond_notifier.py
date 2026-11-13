"""Channel-bond onboarding detection — pure logic.

Decides whether a poll should fire the one-time onboarding notification,
based on whether any state has been stored for this entry yet and whether
the entry was set up after this feature landed (eligible for onboarding)
or upgraded from an older version (not eligible — silent init only).

HA-free so tests can run without mocks. Persistence is handled by
:mod:`channel_bond_storage`; the coordinator wires both together and
fires the HA ``persistent_notification.create`` service.

Tracks bonded channel totals only (downstream + upstream). Changes to
those totals do not notify; they are published on the DS and US Channel
Count sensors every poll instead. Reasoning:
``docs/HA_ADAPTER_SPEC.md`` § Notifications (#197).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import quote

from solentlabs.cable_modem_monitor_core.orchestration.models import ModemIdentity

from .channel_bond_storage import BondState

NotifierAction = Literal["none", "silent_init", "onboarding"]


@dataclass(frozen=True)
class ChannelTotals:
    downstream: int
    upstream: int


def evaluate(
    *,
    current: ChannelTotals,
    stored: BondState | None,
    onboarding_eligible: bool,
    recovery_active: bool,
) -> NotifierAction:
    """Decide what the coordinator should do with the current totals.

    Args:
        current: Totals from this poll's ``system_info``.
        stored: Persisted baseline, or ``None`` if no state has ever
            been saved for this entry.
        onboarding_eligible: ``True`` for entries created after this
            feature shipped (config flow sets the entry-data flag);
            ``False`` for entries upgraded from an older version.
        recovery_active: Orchestrator's recovery flag. Counts flux
            during a recovery window is expected and suppressed.

    ``stored`` is still read even though the totals are no longer
    compared: its presence is what distinguishes an already-onboarded
    entry from a fresh one, so the onboarding notification fires exactly
    once per config entry.
    """
    # A zero-channel reading means "no data yet" (booting / no_signal page),
    # never a real bond — an operational modem always reports channels. Don't
    # act on it and (since the call site only persists when action != "none")
    # don't let it become the stored baseline. This is the primary guard:
    # recovery_active is time-boxed and a real outage can outlive the window.
    if current.downstream == 0 and current.upstream == 0:
        return "none"

    if recovery_active:
        return "none"

    if stored is None:
        return "onboarding" if onboarding_eligible else "silent_init"

    # Totals differing from the stored baseline is deliberately not an
    # action; bonded totals were the wrong signal in both directions.
    # Reasoning: HA_ADAPTER_SPEC.md § Notifications (#197).
    return "none"


_VERIFICATION_ISSUE_URL = "https://github.com/solentlabs/cable_modem_monitor/issues/new?template=modem_verification.yml"


def verification_issue_url(identity: ModemIdentity) -> str | None:
    """Link to a Verify Working Modem issue for an unconfirmed model; ``None`` once it is confirmed."""
    if identity.status == "confirmed":
        return None
    title = quote(f"[Verification] {identity.manufacturer} {identity.model}")
    return f"{_VERIFICATION_ISSUE_URL}&title={title}"


def format_onboarding_message(*, model: str, current: ChannelTotals, verification_url: str | None) -> str:
    """Body text for the one-time onboarding notification."""
    message = (
        f"{model} is online with {current.downstream} downstream and "
        f"{current.upstream} upstream bonded channels. To add a card for this "
        f"modem, refresh your browser, open a dashboard, choose Edit → Add card, and "
        f"pick Cable Modem."
    )
    if verification_url is None:
        return message
    return (
        f"{message}\n\n"
        f"This model has not been confirmed on real hardware yet. If the readings look "
        f"right, you can help confirm it: Download diagnostics (Settings > Devices & "
        f"Services > Cable Modem Monitor > ...) and attach the file to a "
        f"[Verify Working Modem issue]({verification_url})."
    )
