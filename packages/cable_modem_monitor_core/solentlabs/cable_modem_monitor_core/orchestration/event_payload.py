"""HA event bus payload models for cable_modem_monitor_data_updated.

Defines the schema fired by the CMM HA integration after every poll.
Consumers (e.g., CMMT) validate incoming events with:

    SnapshotEventPayload.model_validate(event.data)

PII stripping is the consumer's responsibility — CMM fires the full
snapshot. See HA_ADAPTER_SPEC.md § Event Bus.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

# Increment when the payload shape changes in a breaking way.
# Consumers branch on this field to handle migrations.
SCHEMA_VERSION = 1


class HealthInfoPayload(BaseModel):
    """Health probe results from the most recent health check cycle."""

    health_status: str
    icmp_latency_ms: float | None = None
    tcp_latency_ms: float | None = None
    http_latency_ms: float | None = None


class ChannelPayload(BaseModel):
    """Single channel entry from the modem's channel table.

    Parsers emit sparse dicts — all fields except channel_number are
    optional. See FIELD_REGISTRY.md for canonical field definitions.
    """

    channel_number: int
    lock_status: str | None = None
    channel_type: str | None = None
    channel_id: int | None = None
    source_channel_number: int | None = None
    frequency: int | None = None
    power: float | None = None
    modulation: str | None = None
    snr: float | None = None
    corrected: int | None = None
    uncorrected: int | None = None
    symbol_rate: int | None = None


class ModemDataPayload(BaseModel):
    """Parsed modem channel and system data."""

    downstream: list[ChannelPayload] = []
    upstream: list[ChannelPayload] = []
    system_info: dict[str, Any] = {}


class SnapshotEventPayload(BaseModel):
    """Payload for the cable_modem_monitor_data_updated HA event bus event.

    Fired after every poll — success or failure. Coordinator state is a
    data field, not a gate: a degraded or errored CMM state is itself a
    signal worth capturing.
    """

    schema_version: int
    connection_status: str
    docsis_status: str
    collector_signal: str
    error: str = ""
    stats_last_reset: str | None = None
    health_info: HealthInfoPayload | None = None
    modem_data: ModemDataPayload | None = None
