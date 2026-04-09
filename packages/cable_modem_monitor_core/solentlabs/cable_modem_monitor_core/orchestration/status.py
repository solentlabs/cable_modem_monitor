"""Status derivation — connection and DOCSIS status from modem data.

Pure functions that derive ConnectionStatus and DocsisStatus from
a successful collection result. No side effects, no state.

See RUNTIME_POLLING_SPEC.md Status Derivation and UC-07.
"""

from __future__ import annotations

import logging
from typing import Any

from .signals import ConnectionStatus, DocsisStatus

_logger = logging.getLogger(__name__)


def derive_connection_status(modem_data: dict[str, Any]) -> ConnectionStatus:
    """Derive connection status from a successful collection.

    Maps channel data and system_info to a ConnectionStatus value.

    Args:
        modem_data: Dict with downstream, upstream, and system_info keys.

    Returns:
        ConnectionStatus based on channel and system_info presence.
    """
    has_channels = len(modem_data.get("downstream", [])) > 0 or len(modem_data.get("upstream", [])) > 0

    if has_channels:
        return ConnectionStatus.ONLINE

    system_info = modem_data.get("system_info", {})
    if system_info:
        return ConnectionStatus.NO_SIGNAL

    _logger.warning(
        "Zero channels and no system_info — cannot confirm parser "
        "health. Verify modem model matches the configured parser."
    )
    return ConnectionStatus.NO_SIGNAL


def derive_docsis_status(modem_data: dict[str, Any]) -> str:
    """Derive DOCSIS status from downstream channel lock_status fields.

    Returns a ``DOCSIS_*`` constant for the well-known lock-based
    states (``operational``, ``partial_lock``, ``not_locked``).  When
    channels lack ``lock_status``, falls back to the raw
    ``system_info.docsis_status`` string so modem-reported diagnostics
    (e.g. ``"Ranging"``) pass through instead of being collapsed to
    ``"unknown"``.

    See RUNTIME_POLLING_SPEC.md Status Derivation and UC-07.
    """
    downstream = modem_data.get("downstream", [])
    upstream = modem_data.get("upstream", [])

    if not downstream:
        return DocsisStatus.NOT_LOCKED

    # Check if lock_status field exists on any channel
    has_lock_status = any("lock_status" in ch for ch in downstream)
    if not has_lock_status:
        return _fallback_from_system_info(modem_data)

    locked_count = sum(1 for ch in downstream if ch.get("lock_status") == "locked")

    if locked_count == 0:
        return DocsisStatus.NOT_LOCKED

    if locked_count == len(downstream) and len(upstream) > 0:
        return DocsisStatus.OPERATIONAL

    return DocsisStatus.PARTIAL_LOCK


def _fallback_from_system_info(modem_data: dict[str, Any]) -> str:
    """Fall back to system_info when channels lack lock_status.

    Returns the raw ``system_info.docsis_status`` string so modem-
    reported diagnostics pass through.  Returns ``"unknown"`` only
    when the field is absent or empty.
    """
    system_info = modem_data.get("system_info", {})
    reported = system_info.get("docsis_status") or ""
    value = reported.strip()
    return value if value else DocsisStatus.UNKNOWN
