"""Catalog manager — lightweight modem discovery for config flows.

Walks the catalog directory and returns summaries of all available
modems and their variants.  Designed for consumer config flows
(manufacturer/model/variant dropdowns) without loading full configs.

See ORCHESTRATION_SPEC.md § Catalog Manager.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_logger = logging.getLogger(__name__)


@dataclass
class ModemSummary:
    """Lightweight modem summary for catalog browsing.

    Returned by ``list_modems()``. Contains enough for config flow
    display and filtering — not the full modem config.

    Attributes:
        manufacturer: Modem manufacturer.
        model: Model name.
        model_aliases: Alternative model names (e.g., "Surfboard").
        brands: ISP brand names (e.g., "Xfinity").
        docsis_version: DOCSIS version string. None if unknown.
        status: Verification status.
        default_host: Default IP for this modem (e.g., "192.168.100.1").
        auth_strategy: Auth strategy of the default variant. For
            multi-variant modems, the config flow loads variant-specific
            auth strategy in Step 2.
        path: Filesystem path to the modem directory in the catalog.
    """

    manufacturer: str
    model: str
    model_aliases: list[str] = field(default_factory=list)
    brands: list[str] = field(default_factory=list)
    docsis_version: str | None = None
    status: str = "awaiting_verification"
    default_host: str = "192.168.100.1"
    auth_strategy: str = "none"
    path: Path = field(default_factory=lambda: Path("."))


def list_modems(catalog_path: Path) -> list[ModemSummary]:
    """Walk the catalog and return summaries of all modems.

    Reads identity fields from each ``modem.yaml`` in the catalog
    directory. Returns a flat list suitable for config flow dropdowns,
    search, or filtering.

    The consumer owns the UI pattern — dropdowns, typeahead, flat list.
    This API returns everything; the consumer filters client-side.

    Skips and logs modems with invalid YAML to prevent a single bad
    file from breaking the entire config flow.

    Args:
        catalog_path: Root of the catalog modems directory
            (e.g., ``catalog/modems/``).

    Returns:
        List of ModemSummary, one per modem (default variant).
    """
    results: list[ModemSummary] = []

    if not catalog_path.is_dir():
        _logger.warning("Catalog path does not exist: %s", catalog_path)
        return results

    for modem_yaml in sorted(catalog_path.rglob("modem.yaml")):
        try:
            summary = _load_summary(modem_yaml)
            if summary is not None:
                results.append(summary)
        except Exception:
            _logger.warning("Skipping invalid modem.yaml: %s", modem_yaml, exc_info=True)

    _logger.info("Catalog discovery: %d modems found", len(results))
    return results


@dataclass
class VariantInfo:
    """Description of a single modem variant.

    Returned by :func:`list_variants`.  Contains fields the config
    flow needs to build a human-readable dropdown entry.

    Attributes:
        name: Variant identifier.  ``None`` for the default variant
            (``modem.yaml``), otherwise the suffix after ``modem-``
            (e.g., ``"form-nonce"`` for ``modem-form-nonce.yaml``).
        auth_strategy: Auth strategy string from the YAML file.
        isps: ISP names associated with this variant.
        notes: Free-text notes from the YAML (may be multi-line).
        path: Filesystem path to the variant YAML file.
    """

    name: str | None
    auth_strategy: str = "none"
    isps: list[str] = field(default_factory=list)
    notes: str | None = None
    path: Path = field(default_factory=lambda: Path("."))


def list_variants(modem_dir: Path) -> list[VariantInfo]:
    """List all variants for a modem directory.

    Scans *modem_dir* for ``modem.yaml`` (default variant) and
    ``modem-*.yaml`` (named variants).  Reads only the fields needed
    for config flow display.

    Single-variant modems return a list with one entry whose
    ``name`` is ``None``.

    Args:
        modem_dir: Path to a modem directory in the catalog
            (e.g., ``catalog/modems/arris/sb6190/``).

    Returns:
        List of :class:`VariantInfo`, sorted with default first.
    """
    results: list[VariantInfo] = []

    if not modem_dir.is_dir():
        _logger.warning("Modem directory does not exist: %s", modem_dir)
        return results

    for yaml_path in sorted(modem_dir.glob("modem*.yaml")):
        stem = yaml_path.stem
        if stem == "modem":
            variant_name: str | None = None
        elif stem.startswith("modem-"):
            variant_name = stem[len("modem-") :]
        else:
            continue

        try:
            info = _load_variant(yaml_path, variant_name)
            if info is not None:
                results.append(info)
        except Exception:
            _logger.warning(
                "Skipping invalid variant file: %s",
                yaml_path,
                exc_info=True,
            )

    # Default variant first, then alphabetical
    results.sort(key=lambda v: (v.name is not None, v.name or ""))
    return results


def _load_variant(yaml_path: Path, name: str | None) -> VariantInfo | None:
    """Load a single variant YAML and extract display fields."""
    raw: dict[str, Any] = yaml.safe_load(yaml_path.read_text())
    if not isinstance(raw, dict):
        _logger.warning("Unexpected YAML content in %s", yaml_path)
        return None

    auth = raw.get("auth") or {}
    return VariantInfo(
        name=name,
        auth_strategy=auth.get("strategy", "none"),
        isps=raw.get("isps", []),
        notes=raw.get("notes"),
        path=yaml_path,
    )


def _load_summary(modem_yaml: Path) -> ModemSummary | None:
    """Load a single modem.yaml and extract a summary.

    Returns None if the file cannot be parsed or is missing required
    fields. Logs warnings for skipped files.
    """
    raw: dict[str, Any] = yaml.safe_load(modem_yaml.read_text())
    if not isinstance(raw, dict):
        _logger.warning("Unexpected YAML content in %s", modem_yaml)
        return None

    manufacturer = raw.get("manufacturer")
    model = raw.get("model")
    if not manufacturer or not model:
        _logger.warning("Missing manufacturer/model in %s", modem_yaml)
        return None

    auth = raw.get("auth") or {}
    hardware = raw.get("hardware") or {}

    return ModemSummary(
        manufacturer=manufacturer,
        model=model,
        model_aliases=raw.get("model_aliases", []),
        brands=raw.get("brands", []),
        docsis_version=hardware.get("docsis_version"),
        status=raw.get("status", "awaiting_verification"),
        default_host=raw.get("default_host", "192.168.100.1"),
        auth_strategy=auth.get("strategy", "none"),
        path=modem_yaml.parent,
    )
