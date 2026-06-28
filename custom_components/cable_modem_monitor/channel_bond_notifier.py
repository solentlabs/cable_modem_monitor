"""Channel-bond change detection — pure logic.

Decides whether a poll should fire a persistent notification based on
prior/current totals, recovery state, and whether the entry was set
up after this feature landed (eligible for onboarding) or upgraded
from an older version (not eligible — silent init only).

HA-free so tests can run without mocks. Persistence is handled by
:mod:`channel_bond_storage`; the coordinator wires both together and
fires the HA ``persistent_notification.create`` service.

Tracks bonded channel totals only (downstream + upstream). Per-type
reshuffles at equal totals (e.g. QAM −1, OFDM +1) are not detected;
this is a known gap documented in HA_ADAPTER_SPEC.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .channel_bond_storage import BondState

NotifierAction = Literal["none", "silent_init", "onboarding", "change"]


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
    """
    # A zero-channel reading means "no data yet" (booting / no_signal page),
    # never a real bond — an operational modem always reports channels. Don't
    # act on it and (since the call site only persists when action != "none")
    # don't let it become the stored baseline. This is the primary guard:
    # recovery_active is time-boxed and a real outage can outlive the window,
    # at which point a transient 0 would otherwise be read as a 24 → 0 change.
    if current.downstream == 0 and current.upstream == 0:
        return "none"

    if recovery_active:
        return "none"

    if stored is None:
        return "onboarding" if onboarding_eligible else "silent_init"

    if current.downstream != stored.baseline_downstream or current.upstream != stored.baseline_upstream:
        return "change"

    return "none"


def format_onboarding_message(*, model: str, current: ChannelTotals) -> str:
    """Body text for the one-time onboarding notification."""
    return (
        f"{model} is online with {current.downstream} downstream and "
        f"{current.upstream} upstream bonded channels. You can auto-generate "
        f"a Lovelace dashboard for this modem via Developer Tools → Actions → "
        f"`cable_modem_monitor.generate_dashboard`."
    )


def format_change_message(
    *,
    model: str,
    prior: BondState,
    current: ChannelTotals,
) -> str:
    """Body text describing which totals changed."""
    deltas: list[str] = []
    if prior.baseline_downstream != current.downstream:
        deltas.append(f"downstream {prior.baseline_downstream} → {current.downstream}")
    if prior.baseline_upstream != current.upstream:
        deltas.append(f"upstream {prior.baseline_upstream} → {current.upstream}")
    delta_text = ", ".join(deltas)
    return (
        f"{model} channel bond changed: {delta_text}. Your generated "
        f"dashboard may be out of date — re-run Developer Tools → Actions → "
        f"`cable_modem_monitor.generate_dashboard` to refresh."
    )
