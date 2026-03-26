"""Parser for Compal CH7465MT cable modem (Connect Box).

Parses XML responses from the modem's getter.xml API endpoints.
Each endpoint returns XML data identified by fun=N parameters.

Data sources:
    fun=1:   GlobalSettings (software version, model, operator)
    fun=2:   cm_system_info (DOCSIS mode, hardware version, uptime, MAC)
    fun=10:  downstream_table (24 SC-QAM channels with signal data)
    fun=11:  upstream_table (8 ATDMA channels with signal data)
    fun=144: cmstatus (provisioning status, service flows)
"""

from __future__ import annotations

import logging
from typing import Any

import defusedxml.ElementTree as ET

from custom_components.cable_modem_monitor.core.base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)


class CompalCH7465MTParser(ModemParser):
    """Parser for Compal CH7465MT XML API responses."""

    def parse_resources(self, resources: dict[str, Any]) -> dict:
        """Parse XML responses from getter.xml endpoints.

        Args:
            resources: Dict mapping fun parameter strings to raw XML text.
                Keys are like "fun=10", "fun=11", etc.

        Returns:
            Standard parser output dict with downstream, upstream, and system_info.
        """
        result: dict[str, Any] = {
            "downstream": [],
            "upstream": [],
            "system_info": {},
        }

        self._parse_global_settings(resources.get("fun=1"), result)
        self._parse_system_info(resources.get("fun=2"), result)
        self._parse_downstream(resources.get("fun=10"), result)
        self._parse_upstream(resources.get("fun=11"), result)
        self._parse_cm_status(resources.get("fun=144"), result)

        return result

    def _parse_global_settings(self, xml_str: str | None, result: dict) -> None:
        """Parse fun=1 GlobalSettings for software version and model."""
        if not xml_str:
            return
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError:
            _LOGGER.warning("Failed to parse GlobalSettings XML (fun=1)")
            return
        sw_version = root.findtext("SwVersion", "")
        if sw_version:
            result["system_info"]["software_version"] = sw_version
        model = root.findtext("ConfigVenderModel", "")
        if model:
            result["system_info"]["model_name"] = model
        operator = root.findtext("OperatorId", "")
        if operator:
            result["system_info"]["operator"] = operator

    def _parse_system_info(self, xml_str: str | None, result: dict) -> None:
        """Parse fun=2 cm_system_info for hardware details and uptime."""
        if not xml_str:
            return
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError:
            _LOGGER.warning("Failed to parse cm_system_info XML (fun=2)")
            return
        hw_version = root.findtext("cm_hardware_version", "")
        if hw_version:
            result["system_info"]["hardware_version"] = hw_version
        uptime = root.findtext("cm_system_uptime", "")
        if uptime:
            result["system_info"]["system_uptime"] = uptime
        docsis_mode = root.findtext("cm_docsis_mode", "")
        if docsis_mode:
            result["system_info"]["docsis_mode"] = docsis_mode
        network_access = root.findtext("cm_network_access", "")
        if network_access:
            result["system_info"]["network_access"] = network_access

    def _parse_downstream(self, xml_str: str | None, result: dict) -> None:
        """Parse fun=10 downstream_table for SC-QAM downstream channels."""
        if not xml_str:
            return
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError:
            _LOGGER.warning("Failed to parse downstream XML (fun=10)")
            return
        for ds in root.findall("downstream"):
            freq = int(ds.findtext("freq", "0"))
            # Skip disabled/empty channels
            if freq == 0:
                continue

            channel = {
                "channel_id": int(ds.findtext("chid", "0")),
                "frequency": freq,
                "power": float(ds.findtext("pow", "0")),
                "snr": float(ds.findtext("snr", "0")),
                "modulation": self._normalize_modulation(ds.findtext("mod", "")),
                "channel_type": "qam",
            }

            # Error counters (Pre/Post Reed-Solomon)
            pre_rs = ds.findtext("PreRs", "")
            if pre_rs:
                channel["corrected"] = int(pre_rs)
            post_rs = ds.findtext("PostRs", "")
            if post_rs:
                channel["uncorrected"] = int(post_rs)

            # Lock status
            is_locked = (
                ds.findtext("IsQamLocked", "0") == "1"
                and ds.findtext("IsFECLocked", "0") == "1"
                and ds.findtext("IsMpegLocked", "0") == "1"
            )
            channel["lock_status"] = "Locked" if is_locked else "Unlocked"

            result["downstream"].append(channel)

    def _parse_upstream(self, xml_str: str | None, result: dict) -> None:
        """Parse fun=11 upstream_table for ATDMA upstream channels."""
        if not xml_str:
            return
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError:
            _LOGGER.warning("Failed to parse upstream XML (fun=11)")
            return
        for us in root.findall("upstream"):
            freq = int(us.findtext("freq", "0"))
            if freq == 0:
                continue

            channel = {
                "channel_id": int(us.findtext("usid", "0")),
                "frequency": freq,
                "power": float(us.findtext("power", "0")),
                "modulation": self._normalize_modulation(us.findtext("mod", "")),
                "channel_type": "atdma",
            }

            srate = us.findtext("srate", "")
            if srate:
                channel["symbol_rate"] = f"{srate} Msym/s"

            result["upstream"].append(channel)

    def _parse_cm_status(self, xml_str: str | None, result: dict) -> None:
        """Parse fun=144 cmstatus for provisioning and connectivity status."""
        if not xml_str:
            return
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError:
            _LOGGER.warning("Failed to parse cmstatus XML (fun=144)")
            return
        prov_status = root.findtext("provisioning_st", "")
        if prov_status:
            result["system_info"]["provisioning_status"] = prov_status
        cm_comment = root.findtext("cm_comment", "")
        if cm_comment:
            result["system_info"]["connectivity_status"] = cm_comment

    @staticmethod
    def _normalize_modulation(mod: str) -> str:
        """Normalize modulation strings to a consistent format.

        Args:
            mod: Raw modulation string (e.g., "256qam", "16qam", "64qam")

        Returns:
            Normalized string (e.g., "256QAM", "16QAM", "64QAM")
        """
        if not mod:
            return ""
        return mod.upper()
