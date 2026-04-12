"""Core component factory — assembles the orchestration graph.

Owns the YAML-to-running-components path.  Consumers supply *what*
(loaded configs, credentials, protocol settings), Core handles *how*
(credential encoding, collector creation, health monitor, orchestrator).

Two entry points:

- ``create_collector`` — single-shot validation (config flow).
- ``create_orchestrator`` — full graph for runtime polling.

See ORCHESTRATION_SPEC.md § Factory API.
"""

from __future__ import annotations

from typing import Any

from .collector import ModemDataCollector
from .models import ModemIdentity
from .modem_health import HealthMonitor
from .orchestrator import Orchestrator


def apply_credential_encoding(
    modem_config: Any,
    credential_encoding: str = "plain",
    credential_field: str = "",
) -> None:
    """Inject credential encoding into form_nonce config.

    At setup time (HA config flow or test harness), the login page
    form structure is inspected to determine whether credentials are
    sent as plain form fields or base64-packed into a hidden field.
    The detected encoding is stored and re-applied here at runtime.

    No-op for non-form_nonce strategies.

    Args:
        modem_config: Loaded ``ModemConfig`` instance.
        credential_encoding: Detected encoding (``"plain"`` or
            ``"b64_packed"``).
        credential_field: Hidden field name for packed credentials.
            Empty for plain encoding.
    """
    from ..models.modem_config.auth import FormNonceAuth

    if not isinstance(modem_config.auth, FormNonceAuth):
        return

    if credential_encoding == "b64_packed":
        modem_config.auth.credential_encoding = "b64_packed"
        modem_config.auth.credential_field = credential_field
    else:
        modem_config.auth.credential_encoding = "plain"


def create_collector(
    modem_config: Any,
    parser_config: Any,
    post_processor: Any,
    base_url: str,
    username: str = "",
    password: str = "",
    *,
    legacy_ssl: bool = False,
) -> ModemDataCollector:
    """Create a ``ModemDataCollector`` for single-shot validation.

    Used by the config flow to test data collection during setup.
    Does not create a ``HealthMonitor`` or ``Orchestrator``.

    Args:
        modem_config: Loaded ``ModemConfig`` instance.
        parser_config: Loaded ``ParserConfig`` instance (or ``None``).
        post_processor: ``PostProcessor`` instance (or ``None``).
        base_url: Full URL including protocol
            (e.g., ``"https://192.168.100.1"``).
        username: Login credential (empty string for no-auth).
        password: Login credential (empty string for no-auth).
        legacy_ssl: Whether to use legacy SSL ciphers.

    Returns:
        Configured ``ModemDataCollector`` ready for ``execute()``.
    """
    return ModemDataCollector(
        modem_config=modem_config,
        parser_config=parser_config,
        post_processor=post_processor,
        base_url=base_url,
        username=username,
        password=password,
        legacy_ssl=legacy_ssl,
    )


def create_orchestrator(
    modem_config: Any,
    parser_config: Any,
    post_processor: Any,
    base_url: str,
    username: str = "",
    password: str = "",
    *,
    legacy_ssl: bool = False,
    supports_icmp: bool = True,
    supports_head: bool = True,
    http_probe: bool = True,
    model: str = "",
) -> tuple[Orchestrator, HealthMonitor | None, ModemIdentity]:
    """Create the full orchestration graph.

    Assembles ``ModemDataCollector``, ``HealthMonitor`` (conditional),
    ``Orchestrator``, and ``ModemIdentity`` from loaded configs and
    runtime parameters.

    Used by the HA adapter (runtime polling) and the test harness
    (orchestrated regression tests).

    Args:
        modem_config: Loaded ``ModemConfig`` instance.
        parser_config: Loaded ``ParserConfig`` instance (or ``None``).
        post_processor: ``PostProcessor`` instance (or ``None``).
        base_url: Full URL including protocol.
        username: Login credential.
        password: Login credential.
        legacy_ssl: Whether to use legacy SSL ciphers.
        supports_icmp: Whether ICMP probes are supported. Consumers
            resolve modem.yaml defaults vs config entry overrides
            before calling.
        supports_head: Whether HTTP HEAD probes are supported.
        http_probe: Whether HTTP probes are enabled (from
            modem.yaml ``health.http_probe``).
        model: Model name for log messages.

    Returns:
        3-tuple of ``(Orchestrator, HealthMonitor | None, ModemIdentity)``.
    """
    collector = create_collector(
        modem_config=modem_config,
        parser_config=parser_config,
        post_processor=post_processor,
        base_url=base_url,
        username=username,
        password=password,
        legacy_ssl=legacy_ssl,
    )

    health_monitor: HealthMonitor | None = None
    if supports_icmp or http_probe:
        health_monitor = HealthMonitor(
            base_url=base_url,
            model=model,
            supports_icmp=supports_icmp,
            supports_head=supports_head,
            http_probe=http_probe,
            legacy_ssl=legacy_ssl,
        )

    orchestrator = Orchestrator(
        collector=collector,
        health_monitor=health_monitor,
        modem_config=modem_config,
    )

    identity = _build_identity(modem_config)

    return orchestrator, health_monitor, identity


def _build_identity(modem_config: Any) -> ModemIdentity:
    """Extract ``ModemIdentity`` from modem config.

    Pure function — no I/O. Reads identity fields from the loaded
    ``ModemConfig`` instance.
    """
    hw = modem_config.hardware
    return ModemIdentity(
        manufacturer=modem_config.manufacturer,
        model=modem_config.model,
        docsis_version=hw.docsis_version if hw else None,
        release_date=hw.release_date if hw else None,
        status=modem_config.status,
    )
