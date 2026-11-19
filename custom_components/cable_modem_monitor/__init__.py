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
import os
from collections.abc import Mapping
from importlib.metadata import version as pkg_version
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from solentlabs.cable_modem_monitor_catalog import CATALOG_PATH
from solentlabs.cable_modem_monitor_core.config_loader import (
    load_modem_config,
    load_parser_config,
)
from solentlabs.cable_modem_monitor_core.orchestration import (
    HealthMonitor,
    Orchestrator,
    apply_setup_params,
    create_orchestrator,
    setup_param_keys,
)
from solentlabs.cable_modem_monitor_core.orchestration.models import (
    HealthInfo,
    ModemIdentity,
    ModemSnapshot,
)
from solentlabs.cable_modem_monitor_core.orchestration.signals import (
    ConnectionStatus,
    HealthStatus,
)
from solentlabs.cable_modem_monitor_core.post_processor import (
    load_post_processor,
)

from .card import async_register_card
from .channel_bond_storage import async_remove_bond_state
from .const import (
    CONF_CHANNEL_IDENTITY,
    CONF_CUSTOM_MODEM_YAML,
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
    ChannelIdentity,
)
from .coordinator import (
    CableModemConfigEntry,
    CableModemDataCoordinator,
    CableModemHealthCoordinator,
    CableModemRuntimeData,
)
from .core.log_buffer import setup_log_buffer
from .custom_config import parse_modem_yaml
from .lib.utils import get_device_name
from .mapping_manager import ChannelMap, build_channel_map
from .migrations import async_run_migrations, v2_2_frequency_statistics
from .recovery_adapter import attach_recovery_cadence_listener
from .repairs import async_sync_with_catalog
from .services import async_register_services

_LOGGER = logging.getLogger(__name__)

# Must match ConfigFlow.VERSION in config_flow.py
_CURRENT_VERSION = 2


def _local_dev_suffix() -> str:
    """Startup-log marker for local dev installs (CMM_LOCAL_DEV env var)."""
    # The manifest version only bumps at release time, so a bind-mounted
    # dev tree otherwise logs itself as the previous beta and reads as a
    # released install. docker-compose.test.yml sets the variable; HACS
    # installs never have it.
    return " (local dev)" if os.getenv("CMM_LOCAL_DEV") else ""


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

    Called by HA when the entry's version differs from ConfigFlow.VERSION
    or MINOR_VERSION.  Delegates the major version to the migration
    registry, which chains handlers in sequence, then runs the minor step.
    """
    _LOGGER.info(
        "Migrating config entry %s from version %d.%d to %d.%d",
        entry.entry_id,
        entry.version,
        entry.minor_version,
        _CURRENT_VERSION,
        v2_2_frequency_statistics.MINOR_VERSION,
    )
    if not await async_run_migrations(hass, entry, _CURRENT_VERSION):
        return False
    if entry.minor_version < v2_2_frequency_statistics.MINOR_VERSION:
        return await v2_2_frequency_statistics.async_migrate(hass, entry)
    return True


def _attach_health_sync_listeners(
    hass: HomeAssistant,
    health_coordinator: DataUpdateCoordinator[HealthInfo],
    data_coordinator: DataUpdateCoordinator[ModemSnapshot],
    model: str,
) -> None:
    """Keep the health and data coordinators from outvoting each other with stale state.

    Two directions, one shared piece of state:

    Health → data: when health transitions from data-path-down to
    data-path-up (``HealthStatus.data_path_up``), schedules an
    immediate data poll so recovery latency is bounded by the
    health-check interval rather than the scan interval (~10m). The
    edge is a boolean derived per reading, not a pair of enumerated
    states — enumerating transitions missed DEGRADED (2026-06-29) and
    then a transitional ICMP_BLOCKED that laundered the down state
    (2026-07-12). Up→up steps (RESPONSIVE ↔ ICMP_BLOCKED) never fire,
    so ping-blocking setups get no spurious polls. The Core
    orchestrator independently clears connectivity backoff on
    data-path-up health — this listener just ensures the poll happens
    promptly rather than waiting for the next scan.

    Data → health: when a poll succeeds while health still reads
    UNRESPONSIVE or DEGRADED, schedules an immediate health refresh. A
    completed collection is live proof the data path is up; without
    the refresh, the stale probe result tops the Status cascade for up
    to a full health interval, displaying "Unresponsive" over a modem
    that is actively serving polls (UC-59a's principle — stale
    evidence must not outvote a live signal — in reverse). The refresh
    runs the full probe set; a live TCP failure then keeps health down,
    because the probe is newer evidence than the poll.

    The shared flag: that health refresh flips down → RESPONSIVE,
    which would trip the health → data direction into forcing a poll
    seconds after the successful poll that started the exchange — a
    redundant login on session-limited modems. The data listener marks
    the recovery as poll-proven; the next probe result consumes the
    mark, suppressing exactly that one forced poll.
    """
    # Start "up" so the first successful health check is not
    # misinterpreted as a recovery — avoids a spurious immediate poll
    # right after the initial data fetch.
    previous_up: list[bool] = [True]
    # True while the current down state has been contradicted by a
    # successful poll — the recovery is already proven, data is fresh.
    poll_proven: list[bool] = [False]

    @callback
    def _on_health_update() -> None:
        if health_coordinator.data is None:
            return
        current_up = health_coordinator.data.health_status.data_path_up
        was_up = previous_up[0]
        previous_up[0] = current_up
        # Any live probe result supersedes the poll-proven mark; it may
        # suppress only the recovery edge of the probe that follows it.
        proven = poll_proven[0]
        poll_proven[0] = False
        if not was_up and current_up:
            if proven:
                _LOGGER.debug(
                    "Health recovery [%s] — poll already succeeded, skipping forced poll",
                    model,
                )
                return
            _LOGGER.info("Health recovery [%s] — scheduling immediate poll", model)
            hass.async_create_task(data_coordinator.async_request_refresh())

    @callback
    def _on_data_update() -> None:
        snapshot = data_coordinator.data
        if snapshot is None or health_coordinator.data is None:
            return
        if snapshot.connection_status is not ConnectionStatus.ONLINE:
            return
        # Only a data-path-down claim is contradicted by a successful
        # poll. UNKNOWN is excluded — probes are not applicable, so a
        # refresh adds no information and would fire on every poll for
        # probe-less configurations.
        health_status = health_coordinator.data.health_status
        if health_status.data_path_up or health_status is HealthStatus.UNKNOWN:
            return
        poll_proven[0] = True
        _LOGGER.info(
            "Health refresh [%s] — successful poll contradicts stale %s reading",
            model,
            health_coordinator.data.health_status.value,
        )
        hass.async_create_task(health_coordinator.async_request_refresh())

    health_coordinator.async_add_listener(_on_health_update)
    data_coordinator.async_add_listener(_on_data_update)


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register integration-global services at component load.

    Bronze action-setup: services are registered once here, not per
    config entry, so they exist even before any entry is set up (and a
    re-added entry keeps them). Handlers resolve their target config
    entry at call time. See HA_ADAPTER_SPEC.md § Services.
    """
    async_register_services(hass)
    await async_register_card(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CableModemConfigEntry,
) -> bool:
    """Set up Cable Modem Monitor from a config entry.

    Follows the startup sequence defined in HA_ADAPTER_SPEC.md.
    Steps 1-5 (config loading, Core component creation) run in an
    executor thread because they involve file I/O.
    """
    pkg_versions = await hass.async_add_executor_job(_get_package_versions)
    _LOGGER.info(
        "Cable Modem Monitor v%s%s starting [%s %s] — %s",
        VERSION,
        _local_dev_suffix(),
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

    # Step 0: a custom config entry may return to the catalog file first.
    await async_sync_with_catalog(hass, entry)

    # Steps 1-5: Load config and create Core components (sync I/O)
    try:
        orchestrator, health_monitor, modem_identity, setup_keys = await hass.async_add_executor_job(
            _create_core_components, entry.data
        )
    except Exception as err:
        # A missing or corrupt catalog config is a permanent
        # misconfiguration — HA's retry won't fix it — so raise
        # ConfigEntryError (not ConfigEntryNotReady). The modem being
        # unreachable is a different case: the first poll never raises
        # and setup proceeds with deferred entities (see § Data Coordinator).
        source = "custom config" if CONF_CUSTOM_MODEM_YAML in entry.data else "catalog"
        _LOGGER.exception("Failed to load modem configuration from %s", source)
        raise ConfigEntryError(f"Failed to load modem configuration from {source}: {err}") from err

    # Step 6: Create the data coordinator (CableModemDataCoordinator)
    model = entry.data.get(CONF_MODEL, entry.data[CONF_HOST])
    identity_mode = ChannelIdentity(entry.data.get(CONF_CHANNEL_IDENTITY, ChannelIdentity.ID))
    data_coordinator = CableModemDataCoordinator(hass, entry, orchestrator, modem_identity, scan_interval)

    # Step 6a: Install the recovery cadence listener — switches the
    # data coordinator's interval to 30s while a recovery window is
    # open, and back to the configured interval when the window
    # closes. Single point of HA-side contact for Core's recovery
    # observer; other modules don't subscribe.
    attach_recovery_cadence_listener(hass, entry, orchestrator, data_coordinator)

    # Step 7: Create the health coordinator (conditional)
    health_coordinator: CableModemHealthCoordinator | None = None
    if health_monitor is not None:
        health_coordinator = CableModemHealthCoordinator(hass, entry, health_monitor, health_check_interval)

    # Step 7b: Health sync listeners — immediate poll on health recovery,
    # immediate health refresh when a successful poll contradicts stale health
    if health_coordinator is not None:
        _attach_health_sync_listeners(hass, health_coordinator, data_coordinator, model)

    # Step 8: First poll (always runs, even when polling is disabled)
    await data_coordinator.async_config_entry_first_refresh()

    # Log first-poll result at HA level (Core logs parse details under solentlabs.*)
    snapshot = data_coordinator.data
    if snapshot and snapshot.modem_data:
        _LOGGER.info("First poll complete [%s] — data received", model)
    else:
        status = snapshot.connection_status.value if snapshot else "unknown"
        _LOGGER.info("First poll complete [%s] — no data (%s)", model, status)

    if health_coordinator is not None:
        await health_coordinator.async_config_entry_first_refresh()
        _LOGGER.info("Health monitoring started [%s] — %s", model, _format_interval(health_check_interval))

    # Step 9: Store runtime data (with initial channel map from first poll)
    modem_data = snapshot.modem_data if snapshot else None
    initial_channel_map = (
        build_channel_map(
            modem_data.get("downstream", []),
            modem_data.get("upstream", []),
            identity_mode,
        )
        if modem_data
        else ChannelMap()
    )

    entry.runtime_data = CableModemRuntimeData(
        data_coordinator=data_coordinator,
        health_coordinator=health_coordinator,
        orchestrator=orchestrator,
        health_monitor=health_monitor,
        modem_identity=modem_identity,
        channel_map=initial_channel_map,
        setup_param_keys=setup_keys,
    )

    # Step 10: Forward platform setup
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Step 11: Update device registry
    _update_device_registry(hass, entry)

    # Services are registered in async_setup (integration-global), not
    # here — see § Services.

    # Log operational summary — after this, per-poll details are DEBUG only
    _log_operational_summary(scan_interval, health_check_interval, model)

    # Register update listener (options flow changes trigger reload)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


def _format_interval(seconds: int) -> str:
    """Format a polling interval as a human-readable string."""
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs:
        parts.append(f"{secs}s")
    return f"every {' '.join(parts)}" if parts else "every 0s"


def _log_operational_summary(
    scan_interval: int,
    health_check_interval: int,
    model: str,
) -> None:
    """Log a one-time summary after startup completes.

    Tells the user the polling cadence and how to enable detailed
    logging. After this message, per-poll details are DEBUG only.
    """
    poll_msg = _format_interval(scan_interval) if scan_interval > 0 else "manual only"
    health_msg = _format_interval(health_check_interval) if health_check_interval > 0 else "disabled"

    _LOGGER.info(
        "Initialized [%s] — Polling %s, health checks %s. Enable debug logging for per-poll details.",
        model,
        poll_msg,
        health_msg,
    )


async def async_unload_entry(
    hass: HomeAssistant,
    entry: CableModemConfigEntry,
) -> bool:
    """Unload a config entry.

    Unloads platforms; ``runtime_data`` is auto-cleaned by HA. There
    is no long-running work to cancel — ``orchestrator.restart()`` is
    one-shot and returns in a few seconds.
    """
    model = entry.data.get("model", "unknown")

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Log out any live modem session and release the socket pool now
        # rather than leaving a lock / lingering to GC — matters on reload
        # so the fresh orchestrator doesn't collide with a dying one. Both
        # steps are blocking network/socket work, hence the executor.
        await hass.async_add_executor_job(entry.runtime_data.orchestrator.close)

    # Services are integration-global (registered in async_setup); they
    # outlive the entry and are not unregistered here.

    _LOGGER.info("Unloaded [%s]", model)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clean up per-entry Store state when the config entry is deleted.

    Called by HA after ``async_unload_entry``. Entry data and options are
    managed by HA; Store payloads (e.g. the channel-bond baseline) are not.
    """
    await async_remove_bond_state(hass, entry.entry_id)


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
) -> tuple[Orchestrator, HealthMonitor | None, ModemIdentity, tuple[str, ...]]:
    """Load modem config and create Core components.

    Implements startup Steps 1-5 from HA_ADAPTER_SPEC.md.  Runs in an
    executor thread because config loading reads YAML files from the
    catalog package.

    Config loading stays here (catalog path is HA-specific).  Assembly
    delegates to the Core factory.

    Args:
        data: Config entry data (user selections + validation results).
    """
    # Step 1: Load configs from catalog
    modem_dir = CATALOG_PATH / data[CONF_MODEM_DIR]
    variant = data.get(CONF_VARIANT)

    modem_yaml = modem_dir / f"modem-{variant}.yaml" if variant else modem_dir / "modem.yaml"
    parser_yaml = modem_dir / "parser.yaml"
    parser_py = modem_dir / "parser.py"

    # A custom config entry's own modem.yaml replaces the variant file
    # (CONFIG_FLOW_SPEC § Custom Config Setup).
    custom_text = data.get(CONF_CUSTOM_MODEM_YAML)
    modem_config = parse_modem_yaml(custom_text) if custom_text is not None else load_modem_config(modem_yaml)
    parser_config = load_parser_config(parser_yaml) if parser_yaml.exists() else None
    post_processor = load_post_processor(parser_py) if parser_py.exists() else None

    # Step 1a: Re-apply setup params detected at config time (Core concern).
    # Core reads only its strategy's keys; the rest of entry.data is ignored.
    apply_setup_params(modem_config, data)

    # Steps 2-5: Delegate assembly to Core factory
    protocol = data.get(CONF_PROTOCOL, "http")
    host = data[CONF_HOST]
    base_url = f"{protocol}://{host}"

    # Resolve health probe defaults from modem.yaml, apply config entry overrides
    health_cfg = modem_config.health
    http_probe = health_cfg.http_probe if health_cfg else True
    default_icmp = health_cfg.supports_icmp if health_cfg else True
    default_head = health_cfg.supports_head if health_cfg else True

    orchestrator, health_monitor, identity = create_orchestrator(
        modem_config=modem_config,
        parser_config=parser_config,
        post_processor=post_processor,
        base_url=base_url,
        username=data.get(CONF_USERNAME, ""),
        password=data.get(CONF_PASSWORD, ""),
        legacy_ssl=data.get(CONF_LEGACY_SSL, False),
        supports_icmp=data.get(CONF_SUPPORTS_ICMP, default_icmp),
        supports_head=data.get(CONF_SUPPORTS_HEAD, default_head),
        http_probe=http_probe,
        model=modem_config.model,
    )
    # Diagnostics reports the stored setup params by these names.
    return orchestrator, health_monitor, identity, setup_param_keys(modem_config)


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

    # Version identity lives on the device card, not in the entity list
    # (#178). software_version also stays a sensor — the sensor is the
    # firmware-change timeline; this field is display-only and refreshes
    # at entry setup. Empty when the first poll returned no data.
    snapshot = entry.runtime_data.data_coordinator.data
    system_info: dict[str, Any] = {}
    if snapshot is not None and snapshot.modem_data is not None:
        system_info = snapshot.modem_data.get("system_info", {})

    # model vs model_id: the catalog model is the name the user bought
    # ("XB7"), the modem's reported model_name is the manufacturer's
    # identifier for the same box ("CGM4331COM"). HA has a field for each,
    # so neither has to lose. Reported must not take over `model` — on the
    # Technicolor and Sagemcom entries it is the OEM board code, and
    # promoting it would replace a name users recognize with one they do
    # not. Device name is deliberately not derived from either: entities
    # build their DeviceInfo before the first poll, so a name from
    # system_info would disagree with the registry and break the device
    # link.
    registry = dr.async_get(hass)
    registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=device_name,
        manufacturer=identity.manufacturer,
        model=identity.model,
        model_id=system_info.get("model_name") or None,
        configuration_url=f"{protocol}://{host}",
        sw_version=system_info.get("software_version"),
        hw_version=system_info.get("hardware_version"),
    )
