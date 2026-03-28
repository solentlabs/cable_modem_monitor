"""Constants for the Cable Modem Monitor integration."""

from __future__ import annotations

from homeassistant.const import Platform

# IMPORTANT: Do not edit VERSION manually!
# Use: python scripts/release.py <version>
VERSION = "3.14.0-beta.1"

DOMAIN = "cable_modem_monitor"
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]

# Config entry keys — user selections (config flow Steps 1-3)
CONF_MANUFACTURER = "manufacturer"
CONF_MODEL = "model"
CONF_VARIANT = "variant"
CONF_USER_SELECTED_MODEM = "user_selected_modem"
CONF_ENTITY_PREFIX = "entity_prefix"
CONF_MODEM_DIR = "modem_dir"

# Config entry keys — derived during validation (config flow Step 4)
CONF_PROTOCOL = "protocol"
CONF_LEGACY_SSL = "legacy_ssl"
CONF_SUPPORTS_ICMP = "supports_icmp"
CONF_SUPPORTS_HEAD = "supports_head"

# Polling configuration (options flow)
CONF_SCAN_INTERVAL = "scan_interval"
CONF_HEALTH_CHECK_INTERVAL = "health_check_interval"

# Defaults — data polling
DEFAULT_SCAN_INTERVAL = 600  # 10 minutes
MIN_SCAN_INTERVAL = 30
MAX_SCAN_INTERVAL = 86400  # 24 hours

# Defaults — health checks
DEFAULT_HEALTH_CHECK_INTERVAL = 30
MIN_HEALTH_CHECK_INTERVAL = 10
MAX_HEALTH_CHECK_INTERVAL = 86400  # 24 hours

# Entity prefix options
ENTITY_PREFIX_NONE = "none"
ENTITY_PREFIX_MODEL = "model"
ENTITY_PREFIX_IP = "ip"

# SSL certificate verification — disabled for consumer cable modems.
# Consumer modems universally use self-signed certificates on private LANs.
# Enabling verification would break 99%+ of installations.
VERIFY_SSL = False


def get_device_name(entity_prefix: str, *, model: str = "", host: str = "") -> str:
    """Compute the HA device name from entity prefix setting.

    Used by entity base classes (DeviceInfo) and _update_device_registry.
    Must be called consistently so entities link to the correct device.
    """
    if entity_prefix == ENTITY_PREFIX_MODEL:
        return f"Cable Modem {model}"
    if entity_prefix == ENTITY_PREFIX_IP:
        return f"Cable Modem {host}"
    return "Cable Modem"
