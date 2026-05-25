"""Status derivation — connection and DOCSIS status from modem data.

Pure functions that derive ConnectionStatus from a successful collection
result.  ``enrich_docsis_status`` enriches ``system_info`` in-place
when the parser does not provide ``docsis_status``.

See RUNTIME_POLLING_SPEC.md Status Derivation and UC-07.
"""

from __future__ import annotations

import logging
from typing import Any

from .events import ZeroChannelsNoSystemInfo
from .logging import log_event
from .signals import ConnectionStatus, DocsisStatus

_logger = logging.getLogger(__name__)


def derive_connection_status(modem_data: dict[str, Any], model: str = "") -> ConnectionStatus:
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

    log_event(_logger, ZeroChannelsNoSystemInfo(model=model))
    return ConnectionStatus.NO_SIGNAL


def enrich_docsis_status(modem_data: dict[str, Any]) -> None:
    """Enrich ``system_info`` with ``docsis_status`` when absent.

    Same enrichment pattern as error totals and channel counts: the
    parser provides the field when the modem exposes a native value;
    this function fills it in from channel ``lock_status`` when the
    parser did not.  A parser-provided value is never overwritten.

    Writes directly into ``modem_data["system_info"]``.

    See RUNTIME_POLLING_SPEC.md Status Derivation.
    """
    system_info = modem_data.setdefault("system_info", {})

    if "docsis_status" in system_info:
        return  # parser provided it — don't overwrite

    downstream = modem_data.get("downstream", [])
    upstream = modem_data.get("upstream", [])

    # Can't derive without downstream channels that have lock_status.
    # Same sparse-dict rule as other system_info fields: if the data
    # isn't available, the field stays absent (no sensor created).
    if not downstream:
        return

    has_lock_status = any("lock_status" in ch for ch in downstream)
    if not has_lock_status:
        return

    locked_count = sum(1 for ch in downstream if ch.get("lock_status") == "locked")

    if locked_count == 0:
        system_info["docsis_status"] = DocsisStatus.NOT_LOCKED
    elif locked_count == len(downstream) and len(upstream) > 0:
        system_info["docsis_status"] = DocsisStatus.OPERATIONAL
    else:
        system_info["docsis_status"] = DocsisStatus.PARTIAL_LOCK
