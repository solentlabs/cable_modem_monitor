"""The Cable Modem Monitor integration.

Home Assistant adapter layer for monitoring cable modem signal quality
and health.  Consumes Core (orchestration, parsing, auth) and Catalog
(modem configs, parsers) packages — all modem-specific logic lives
there.

Entry points:
    async_setup_entry: Called by HA when integration is configured.
    async_unload_entry: Called when integration is removed or reloaded.

See Also:
    HA_ADAPTER_SPEC.md for the full startup/unload specification.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import timedelta
from importlib.metadata import version as pkg_version
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from solentlabs.cable_modem_monitor_catalog import CATALOG_PATH
from solentlabs.cable_modem_monitor_core.config_loader import (
    load_modem_config,
    load_parser_config,
)
from solentlabs.cable_modem_monitor_core.orchestration import (
    HealthMonitor,
    ModemDataCollector,
    Orchestrator,
)
from solentlabs.cable_modem_monitor_core.orchestration.models import (
    HealthInfo,
    ModemIdentity,
    ModemSnapshot,
)
from solentlabs.cable_modem_monitor_core.orchestration.signals import HealthStatus
from solentlabs.cable_modem_monitor_core.test_harness.runner import (
    load_post_processor,
)

from .const import (
    CONF_ENTITY_PREFIX,
    CONF_HEALTH_CHECK_INTERVAL,
    CONF_LEGACY_SSL,
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_MODEM_DIR,
    CONF_PROTOCOL,
    CONF_SCAN_INTERVAL,
    CONF_SUPPORTS_HEAD,
    CONF_SUPPORTS_ICMP,
    CONF_VARIANT,
    DEFAULT_HEALTH_CHECK_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
    VERSION,
    get_device_name,
)
from .coordinator import CableModemConfigEntry, CableModemRuntimeData
from .core.log_buffer import setup_log_buffer
from .migrations import async_run_migrations
from .services import async_register_services, async_unregister_services

_LOGGER = logging.getLogger(__name__)

# Must match ConfigFlow.VERSION in config_flow.py
_CURRENT_VERSION = 2


def _get_package_versions() -> str:
    """Build package version string for the startup log.

    Uses importlib.metadata which does file I/O — call from executor.
    """
    parts = []
    for pkg, label in (
        ("solentlabs-cable-modem-monitor-core", "core"),
        ("solentlabs-cable-modem-monitor-catalog", "catalog"),
    ):
        try:
            parts.append(f"{label}: v{pkg_version(pkg)}")
        except Exception:  # noqa: BLE001
            parts.append(f"{label}: not installed")
    return ", ".join(parts)


async def async_migrate_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Migrate a config entry to the current version.

    Called by HA when entry.version < ConfigFlow.VERSION.  Delegates
    to the migration registry which chains handlers in sequence.
    """
    _LOGGER.info(
        "Migrating config entry %s from version %d to %d",
        entry.entry_id,
        entry.version,
        _CURRENT_VERSION,
    )
    return await async_run_migrations(hass, entry, _CURRENT_VERSION)


def _attach_health_recovery_listener(
    hass: HomeAssistant,
    health_coordinator: DataUpdateCoordinator[HealthInfo],
    data_coordinator: DataUpdateCoordinator[ModemSnapshot],
    model: str,
) -> None:
    """Register a listener that triggers an immediate poll on health recovery.

    When health transitions from UNRESPONSIVE/UNKNOWN to RESPONSIVE,
    schedules an immediate data poll so recovery latency is bounded by
    the health check interval (~30s) rather than the scan interval (~10m).

    The Core orchestrator independently clears connectivity backoff when
    it sees RESPONSIVE health — this listener just ensures the poll
    happens promptly rather than waiting for the next scheduled scan.
    """
    previous: list[HealthStatus] = [HealthStatus.UNKNOWN]

    @callback
    def _on_health_update() -> None:
        if health_coordinator.data is None:
            return
        current = health_coordinator.data.health_status
        was_down = previous[0] in (HealthStatus.UNRESPONSIVE, HealthStatus.UNKNOWN)
        previous[0] = current
        if was_down and current == HealthStatus.RESPONSIVE:
            _LOGGER.info("Health recovery [%s] — scheduling immediate poll", model)
            hass.async_create_task(data_coordinator.async_request_refresh())

    health_coordinator.async_add_listener(_on_health_update)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CableModemConfigEntry,
) -> bool:
    """Set up Cable Modem Monitor from a config entry.

    Follows the 12-step startup sequence defined in HA_ADAPTER_SPEC.md.
    Steps 1-5 (config loading, Core component creation) run in an
    executor thread because they involve file I/O.
    """
    pkg_versions = await hass.async_add_executor_job(_get_package_versions)
    _LOGGER.info(
        "Cable Modem Monitor v%s starting [%s %s] — %s",
        VERSION,
        entry.data.get(CONF_MANUFACTURER, ""),
        entry.data.get(CONF_MODEL, ""),
        pkg_versions,
    )

    # Initialize log buffer before any Core calls so auth, parsing,
    # action, and health logs are captured from the first poll.
    setup_log_buffer(hass)

    # Resolve effective polling intervals (options override data)
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )
    health_check_interval = entry.options.get(
        CONF_HEALTH_CHECK_INTERVAL,
        entry.data.get(CONF_HEALTH_CHECK_INTERVAL, DEFAULT_HEALTH_CHECK_INTERVAL),
    )

    # Steps 1-5: Load config and create Core components (sync I/O)
    try:
        orchestrator, health_monitor, modem_identity = await hass.async_add_executor_job(
            _create_core_components, entry.data
        )
    except Exception:
        _LOGGER.exception("Failed to load modem configuration from catalog")
        return False

    # Step 6: Create data DataUpdateCoordinator
    host = entry.data[CONF_HOST]

    async def _async_update_data() -> ModemSnapshot:
        return await hass.async_add_executor_job(orchestrator.get_modem_data)

    data_coordinator = DataUpdateCoordinator[ModemSnapshot](
        hass,
        _LOGGER,
        name=f"Cable Modem {host}",
        update_method=_async_update_data,
        update_interval=(timedelta(seconds=scan_interval) if scan_interval > 0 else None),
        config_entry=entry,
    )

    # Step 7: Create health DataUpdateCoordinator (conditional)
    health_coordinator: DataUpdateCoordinator[HealthInfo] | None = None
    if health_monitor is not None:

        async def _async_update_health() -> HealthInfo:
            return await hass.async_add_executor_job(health_monitor.ping)

        health_coordinator = DataUpdateCoordinator[HealthInfo](
            hass,
            _LOGGER,
            name=f"Cable Modem {host} Health",
            update_method=_async_update_health,
            update_interval=(timedelta(seconds=health_check_interval) if health_check_interval > 0 else None),
            config_entry=entry,
        )

    # Model name for logging (used by recovery listener and step 8+)
    model = entry.data.get(CONF_MODEL, host)

    # Step 7b: Health recovery listener — trigger immediate poll on recovery
    if health_coordinator is not None:
        _attach_health_recovery_listener(hass, health_coordinator, data_coordinator, model)

    # Step 8: First poll (always runs, even when polling is disabled)
    await data_coordinator.async_config_entry_first_refresh()
    if health_coordinator is not None:
        await health_coordinator.async_config_entry_first_refresh()
        _LOGGER.info("Health monitoring started [%s] — every %ds", model, health_check_interval)

    # Step 9: Store runtime data
    entry.runtime_data = CableModemRuntimeData(
        data_coordinator=data_coordinator,
        health_coordinator=health_coordinator,
        orchestrator=orchestrator,
        health_monitor=health_monitor,
        cancel_event=None,
        modem_identity=modem_identity,
    )

    # Step 10: Forward platform setup
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Step 11: Update device registry
    _update_device_registry(hass, entry)

    # Step 12: Register services (if first entry)
    if not hass.services.has_service(DOMAIN, "generate_dashboard"):
        async_register_services(hass)

    # Log operational summary — after this, per-poll details are DEBUG only
    _log_operational_summary(scan_interval, health_check_interval, model)

    # Register update listener (options flow changes trigger reload)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


def _log_operational_summary(
    scan_interval: int,
    health_check_interval: int,
    model: str,
) -> None:
    """Log a one-time summary after startup completes.

    Tells the user the polling cadence and how to enable detailed
    logging. After this message, per-poll details are DEBUG only.
    """
    if scan_interval > 0:
        poll_msg = f"every {scan_interval // 60}m" if scan_interval >= 60 else f"every {scan_interval}s"
    else:
        poll_msg = "manual only"

    if health_check_interval > 0:
        health_msg = f"every {health_check_interval}s"
    else:
        health_msg = "disabled"

    _LOGGER.info(
        "Initialized [%s] — polling %s, health checks %s. " "Enable debug logging for per-poll details.",
        model,
        poll_msg,
        health_msg,
    )


async def async_unload_entry(
    hass: HomeAssistant,
    entry: CableModemConfigEntry,
) -> bool:
    """Unload a config entry.

    Cancels any in-progress restart (cooperative via cancel_event),
    then unloads platforms.  ``runtime_data`` is auto-cleaned by HA.
    """
    # Cancel restart if in progress
    if entry.runtime_data.cancel_event is not None:
        entry.runtime_data.cancel_event.set()

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Unregister services if last entry
    if unload_ok and not hass.config_entries.async_entries(DOMAIN):
        async_unregister_services(hass)

    return unload_ok


async def _async_update_listener(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Reload integration when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


# ------------------------------------------------------------------
# Sync helpers — run in executor (file I/O)
# ------------------------------------------------------------------


def _create_core_components(
    data: Mapping[str, Any],
) -> tuple[Orchestrator, HealthMonitor | None, ModemIdentity]:
    """Load modem config and create Core components.

    Implements startup Steps 1-5 from HA_ADAPTER_SPEC.md.  Runs in an
    executor thread because config loading reads YAML files from the
    catalog package.

    Args:
        data: Config entry data (user selections + validation results).
    """
    # Step 1: Resolve modem config from catalog
    modem_dir = CATALOG_PATH / data[CONF_MODEM_DIR]
    variant = data.get(CONF_VARIANT)

    modem_yaml = modem_dir / f"modem-{variant}.yaml" if variant else modem_dir / "modem.yaml"
    parser_yaml = modem_dir / "parser.yaml"
    parser_py = modem_dir / "parser.py"

    modem_config = load_modem_config(modem_yaml)
    parser_config = load_parser_config(parser_yaml) if parser_yaml.exists() else None
    post_processor = load_post_processor(parser_py) if parser_py.exists() else None

    # Step 2: Extract ModemIdentity
    hw = modem_config.hardware
    modem_identity = ModemIdentity(
        manufacturer=modem_config.manufacturer,
        model=modem_config.model,
        docsis_version=hw.docsis_version if hw else None,
        release_date=hw.release_date if hw else None,
        status=modem_config.status,
    )

    # Step 3: Create ModemDataCollector
    protocol = data.get(CONF_PROTOCOL, "http")
    host = data[CONF_HOST]
    base_url = f"{protocol}://{host}"

    collector = ModemDataCollector(
        modem_config=modem_config,
        parser_config=parser_config,
        post_processor=post_processor,
        base_url=base_url,
        username=data.get(CONF_USERNAME, ""),
        password=data.get(CONF_PASSWORD, ""),
        legacy_ssl=data.get(CONF_LEGACY_SSL, False),
    )

    # Step 4: Create HealthMonitor (conditional)
    # modem.yaml health config provides defaults, config entry overrides
    health_cfg = modem_config.health
    http_probe = health_cfg.http_probe if health_cfg else True
    default_icmp = health_cfg.supports_icmp if health_cfg else True
    default_head = health_cfg.supports_head if health_cfg else True
    supports_icmp = data.get(CONF_SUPPORTS_ICMP, default_icmp)
    supports_head = data.get(CONF_SUPPORTS_HEAD, default_head)

    health_monitor: HealthMonitor | None = None
    if supports_icmp or http_probe:
        health_monitor = HealthMonitor(
            base_url=base_url,
            model=modem_config.model,
            supports_icmp=supports_icmp,
            supports_head=supports_head,
            http_probe=http_probe,
            legacy_ssl=data.get(CONF_LEGACY_SSL, False),
        )

    # Step 5: Create Orchestrator
    orchestrator = Orchestrator(
        collector=collector,
        health_monitor=health_monitor,
        modem_config=modem_config,
    )

    return orchestrator, health_monitor, modem_identity


# ------------------------------------------------------------------
# Device registry
# ------------------------------------------------------------------


def _update_device_registry(
    hass: HomeAssistant,
    entry: CableModemConfigEntry,
) -> None:
    """Register or update the HA device for this config entry.

    Device name depends on the entity_prefix setting chosen during
    config flow.  See ENTITY_MODEL_SPEC.md Device Model section.
    """
    data = entry.data
    identity = entry.runtime_data.modem_identity

    device_name = get_device_name(
        data.get(CONF_ENTITY_PREFIX, "default"),
        model=identity.model,
        host=data.get(CONF_HOST, ""),
    )

    protocol = data.get(CONF_PROTOCOL, "http")
    host = data[CONF_HOST]

    registry = dr.async_get(hass)
    registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=device_name,
        manufacturer=identity.manufacturer,
        model=identity.model,
        configuration_url=f"{protocol}://{host}",
    )
