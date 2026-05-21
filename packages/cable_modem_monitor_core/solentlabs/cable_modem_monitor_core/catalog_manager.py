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
        transport: Network transport protocol (``"http"`` or ``"hnap"``).
        path: Filesystem path to the modem directory in the catalog.
        sibling_dirs: Paths of other catalog directories that share this
            modem's ``(manufacturer, model)`` identity. Populated by
            ``list_modems()`` when multiple directories represent the
            same hardware under different transports.
    """

    manufacturer: str
    model: str
    model_aliases: list[str] = field(default_factory=list)
    brands: list[str] = field(default_factory=list)
    docsis_version: str | None = None
    status: str = "awaiting_verification"
    default_host: str = "192.168.100.1"
    auth_strategy: str = "none"
    transport: str = "http"
    path: Path = field(default_factory=lambda: Path("."))
    sibling_dirs: list[Path] = field(default_factory=list)


def list_modems(catalog_path: Path) -> list[ModemSummary]:
    """Walk the catalog and return summaries of all modems.

    Reads identity fields from each ``modem.yaml`` in the catalog
    directory. Returns a flat list suitable for config flow dropdowns,
    search, or filtering.

    Directories that share the same ``(manufacturer, model)`` identity
    (case-insensitive) are collapsed into a single summary — the first
    found (alphabetically by path) becomes the primary entry, and the
    rest are listed in its ``sibling_dirs``. The config flow uses
    ``sibling_dirs`` to surface transport as a variant dimension in
    Step 2 (see CONFIG_FLOW_SPEC.md § Known Gap).

    The consumer owns the UI pattern — dropdowns, typeahead, flat list.
    This API returns everything; the consumer filters client-side.

    Skips and logs modems with invalid YAML to prevent a single bad
    file from breaking the entire config flow.

    Args:
        catalog_path: Root of the catalog modems directory
            (e.g., ``catalog/modems/``).

    Returns:
        List of ModemSummary, one per unique (manufacturer, model) pair.
    """
    raw_results: list[ModemSummary] = []

    if not catalog_path.is_dir():
        _logger.warning("Catalog path does not exist: %s", catalog_path)
        return raw_results

    for modem_yaml in sorted(catalog_path.rglob("modem.yaml")):
        try:
            summary = _load_summary(modem_yaml)
            if summary is not None:
                raw_results.append(summary)
        except Exception:
            _logger.warning("Skipping invalid modem.yaml: %s", modem_yaml, exc_info=True)

    # Group directories that share the same (manufacturer, model) identity.
    # First occurrence (alphabetical path order) becomes the primary entry.
    seen: dict[tuple[str, str], int] = {}
    grouped: list[ModemSummary] = []

    for s in raw_results:
        key = (s.manufacturer.lower(), s.model.lower())
        if key not in seen:
            seen[key] = len(grouped)
            grouped.append(s)
        else:
            grouped[seen[key]].sibling_dirs.append(s.path)

    # Post-grouping: recompute status as aggregate across all variant files in
    # the primary directory and every sibling directory. A model is confirmed
    # when at least one variant anywhere is confirmed; otherwise the base status
    # from modem.yaml is preserved.
    for summary in grouped:
        all_dirs = [summary.path] + summary.sibling_dirs
        if _any_variant_confirmed(all_dirs):
            summary.status = "confirmed"

    _logger.info(
        "Catalog discovery: %d modems found (%d directories)",
        len(grouped),
        len(raw_results),
    )
    return grouped


def _any_variant_confirmed(dirs: list[Path]) -> bool:
    """Return True if any modem*.yaml file in the given directories has status: confirmed."""
    for d in dirs:
        for yaml_path in d.glob("modem*.yaml"):
            try:
                raw: dict[str, Any] = yaml.safe_load(yaml_path.read_text())
                if isinstance(raw, dict) and raw.get("status") == "confirmed":
                    return True
            except Exception:
                pass
    return False


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
        hw_version: Hardware version label shown in the variant dropdown
            (e.g., ``"HW v6"``). Users can verify this against the sticker
            on the modem. Used when multiple variants share the same auth
            strategy and hw_version is the clearest user-facing discriminator.
        isps: ISP names associated with this variant.
        notes: Free-text notes from the YAML (may be multi-line).
        path: Filesystem path to the variant YAML file.
    """

    name: str | None
    auth_strategy: str = "none"
    hw_version: str | None = None
    isps: list[str] = field(default_factory=list)
    notes: str | None = None
    path: Path = field(default_factory=lambda: Path("."))
    status: str = "awaiting_verification"


def list_variants(
    modem_dir: Path,
    sibling_dirs: list[Path] | None = None,
) -> list[VariantInfo]:
    """List all variants for a modem, including sibling transport directories.

    Scans *modem_dir* (and any *sibling_dirs*) for ``modem.yaml``
    (default variant) and ``modem-*.yaml`` (named variants). Returns a
    combined flat list suitable for the config flow variant dropdown.

    When sibling directories are present, each directory contributes its
    variants to the list. This surfaces transport as a variant dimension
    (see CONFIG_FLOW_SPEC.md § Known Gap): a user selecting "Arris SB8200"
    sees all firmware variants from the ``http`` directory AND the HNAP
    directory in a single dropdown.

    Single-variant modems return a list with one entry whose ``name``
    is ``None``. The ``path`` field on each entry points to the variant
    YAML file; ``path.parent`` is the directory to use for loading.

    Args:
        modem_dir: Path to the primary modem directory in the catalog.
        sibling_dirs: Additional directories that share the same
            ``(manufacturer, model)`` identity under a different transport.

    Returns:
        List of :class:`VariantInfo`, sorted with default variants first.
    """
    results: list[VariantInfo] = []

    for d in [modem_dir] + (sibling_dirs or []):
        if not d.is_dir():
            _logger.warning("Modem directory does not exist: %s", d)
            continue

        for yaml_path in sorted(d.glob("modem*.yaml")):
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

    # Default variants (name=None) first, then alphabetical by name.
    # Stable sort preserves the primary-before-sibling insertion order
    # within tied groups, so the primary directory's defaults come first.
    results.sort(key=lambda v: (v.name is not None, v.name or ""))
    return results


def _load_variant(yaml_path: Path, name: str | None) -> VariantInfo | None:
    """Load a single variant YAML and extract display fields."""
    raw: dict[str, Any] = yaml.safe_load(yaml_path.read_text())
    if not isinstance(raw, dict):
        _logger.warning("Unexpected YAML content in %s", yaml_path)
        return None

    auth = raw.get("auth") or {}
    hardware = raw.get("hardware") or {}
    return VariantInfo(
        name=name,
        auth_strategy=auth.get("strategy", "none"),
        hw_version=hardware.get("hw_version"),
        isps=raw.get("isps", []),
        notes=raw.get("notes"),
        path=yaml_path,
        status=raw.get("status", "awaiting_verification"),
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
        transport=raw.get("transport", "http"),
        path=modem_yaml.parent,
    )
