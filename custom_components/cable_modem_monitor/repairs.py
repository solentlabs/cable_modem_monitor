"""Repairs for Cable Modem Monitor: a custom config entry whose catalog file changed.

At startup a custom config entry compares the installed catalog file
with its own modem.yaml. An identical catalog file is adopted with a
notification; a changed one raises a fixable repair whose fix tests the
catalog file once before switching to it.

See CONFIG_FLOW_SPEC.md § Custom Config Setup.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from solentlabs.cable_modem_monitor_catalog import CATALOG_PATH

from .config_flow_helpers import read_variant_yaml, run_custom_attempt
from .const import (
    CONF_CUSTOM_BASE_VERSION,
    CONF_CUSTOM_BASE_YAML,
    CONF_CUSTOM_MODEM_YAML,
    CONF_MODEM_DIR,
    CONF_PROTOCOL,
    CONF_VARIANT,
    DOMAIN,
    VERSION,
)
from .custom_config import build_report, catalog_sync_action

_LOGGER = logging.getLogger(__name__)

_ISSUE_PREFIX = "custom_config_catalog_changed_"
_CUSTOM_KEYS = (CONF_CUSTOM_MODEM_YAML, CONF_CUSTOM_BASE_YAML, CONF_CUSTOM_BASE_VERSION)


def _issue_id(entry: ConfigEntry) -> str:
    """The repair issue id for one entry."""
    return f"{_ISSUE_PREFIX}{entry.entry_id}"


def _catalog_file_label(data: Any) -> str:
    """The entry's variant file, relative to the catalog."""
    variant = data.get(CONF_VARIANT)
    return f"{data[CONF_MODEM_DIR]}/{f'modem-{variant}.yaml' if variant else 'modem.yaml'}"


async def _read_catalog_text(hass: HomeAssistant, entry: ConfigEntry) -> str:
    """The installed catalog text for the entry's variant (executor)."""
    return await hass.async_add_executor_job(
        read_variant_yaml, CATALOG_PATH / entry.data[CONF_MODEM_DIR], entry.data.get(CONF_VARIANT)
    )


def _drop_custom_config(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Return the entry to the catalog file by removing its custom fields."""
    data = {k: v for k, v in entry.data.items() if k not in _CUSTOM_KEYS}
    hass.config_entries.async_update_entry(entry, data=data)


async def async_sync_with_catalog(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Adopt an identical catalog file, raise a repair for a changed one, or keep the user's text."""
    if CONF_CUSTOM_MODEM_YAML not in entry.data:
        return
    try:
        catalog_text = await _read_catalog_text(hass, entry)
    except FileNotFoundError:
        # The catalog dropped or renamed this variant file; the user's text
        # still works on its own, so it stays.
        _LOGGER.info("Catalog file for %s not found; keeping its custom config", entry.title)
        return
    action = catalog_sync_action(
        catalog_text=catalog_text,
        user_text=entry.data[CONF_CUSTOM_MODEM_YAML],
        base_text=entry.data.get(CONF_CUSTOM_BASE_YAML, ""),
    )
    if action == "adopt":
        # Runs before the update listener is registered, so this does not reload.
        _drop_custom_config(hass, entry)
        ir.async_delete_issue(hass, DOMAIN, _issue_id(entry))
        _LOGGER.info("Custom config for %s matches the catalog file; now following the catalog", entry.title)
        await hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "Cable Modem Monitor: Custom config retired",
                "message": (
                    f"The project's config for **{entry.title}** now matches your custom config, "
                    "so this modem follows the project's config from now on and gets its future fixes."
                ),
                "notification_id": f"cable_modem_monitor_custom_config_{entry.entry_id}",
            },
        )
        return
    if action == "repair":
        ir.async_create_issue(
            hass,
            DOMAIN,
            _issue_id(entry),
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="custom_config_catalog_changed",
            translation_placeholders={"title": entry.title},
            data={"entry_id": entry.entry_id},
        )
        return
    ir.async_delete_issue(hass, DOMAIN, _issue_id(entry))


class CustomConfigCatalogChangedFlow(RepairsFlow):
    """Test the changed catalog file once; switch to it only when the test passes."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Hold the entry the repair is for."""
        self._entry = entry

    async def async_step_init(self, user_input: dict[str, str] | None = None) -> data_entry_flow.FlowResult:
        """Start at the confirm step."""
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, str] | None = None) -> data_entry_flow.FlowResult:
        """Ask, then test the catalog file against the modem."""
        entry = self._entry
        if user_input is None:
            return self.async_show_form(
                step_id="confirm",
                data_schema=vol.Schema({}),
                description_placeholders={"title": entry.title},
            )

        catalog_text = await _read_catalog_text(self.hass, entry)
        data = entry.data
        host = f"{data.get(CONF_PROTOCOL, 'http')}://{data[CONF_HOST]}"
        attempt = await run_custom_attempt(
            self.hass,
            host=host,
            username=data.get(CONF_USERNAME, ""),
            password=data.get(CONF_PASSWORD, ""),
            modem_dir=CATALOG_PATH / data[CONF_MODEM_DIR],
            variant=data.get(CONF_VARIANT),
            modem_yaml_text=catalog_text,
        )
        if attempt.validation is None:
            _LOGGER.warning(
                "%s",
                build_report(
                    version=VERSION,
                    catalog_file=_catalog_file_label(data),
                    host=host,
                    outcome=f"catalog file failed: {type(attempt.error).__name__}: {attempt.error}",
                    records=attempt.records,
                    scrub=attempt.scrub,
                ),
            )
            return self.async_show_form(
                step_id="confirm",
                data_schema=vol.Schema({}),
                description_placeholders={"title": entry.title},
                errors={"base": "catalog_test_failed"},
            )

        _drop_custom_config(self.hass, entry)  # the update listener reloads the entry
        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create the fix flow for a custom config repair."""
    entry_id = str((data or {}).get("entry_id", ""))
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None:
        raise ValueError(f"Unknown config entry for repair {issue_id}")
    return CustomConfigCatalogChangedFlow(entry)
