"""Modem configuration loader.

Loads modem.yaml files and the modem index for fast parser lookups.
Provides discovery of all configured modems and caching for performance.

This module handles all file I/O for modem configurations. For data
transformation and adapter logic, see:
- modem_config/schema.py - Pydantic models for modem.yaml structure
- modem_config/adapter.py - Config-to-parser adapters

Functions:
    Index Operations (fast path, no modem.yaml loading):
        load_modem_index: Load index.yaml with parser-to-path mappings
        get_modem_path_for_parser: Get modem path from index by parser name
        get_detection_hints_from_index: Get detection hints from index
        get_aggregated_auth_patterns: Get combined auth patterns from index

    Config Loading:
        load_modem_config: Load a single modem.yaml file
        load_modem_config_by_parser: Load config using index lookup
        load_modem_by_path: Load by manufacturer/model directory path

    Discovery:
        discover_modems: Scan filesystem for all modem.yaml files
        get_modem_by_model: Find modem config by manufacturer/model name

    Paths:
        get_modems_root: Get the modems/ directory path
        get_modem_fixtures_path: Get fixtures/ subdirectory for a modem
        list_modem_fixtures: List all fixture files for a modem

    Cache Management:
        clear_cache: Clear all caches (configs, discovery, index)

    Async Operations (for Home Assistant event loop):
        async_load_modem_config: Async wrapper for load_modem_config
        async_load_modem_config_by_parser: Async wrapper for load_modem_config_by_parser
        async_discover_modems: Async wrapper for discover_modems

Caching:
    Three separate caches are maintained for performance:
    - _config_cache: Individual modem.yaml files (keyed by path)
    - _discovered_modems: Full discovery scan results
    - _modem_index: The index.yaml file contents

    All caches are cleared together via clear_cache().
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml  # type: ignore[import-untyped]

from .schema import ModemConfig

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Cache for loaded configs
_config_cache: dict[Path, ModemConfig] = {}

# Cache for discovery results (populated on first call)
_discovered_modems: list[tuple[Path, ModemConfig]] | None = None

# Cache for modem index (loaded once on first use)
_modem_index: dict | None = None


def load_modem_index() -> dict:
    """Load the modem index for fast parser lookups.

    The index maps parser class names to modem paths, avoiding
    the need to scan all modem.yaml files at startup.

    Returns:
        Index dictionary with 'modems' key containing parser mappings.
    """
    global _modem_index

    if _modem_index is not None:
        return _modem_index

    modems_root = get_modems_root()
    index_path = modems_root / "index.yaml"

    if not index_path.exists():
        _LOGGER.warning("Modem index not found at %s, falling back to full discovery", index_path)
        _modem_index = {"modems": {}}
        return _modem_index

    try:
        with open(index_path, encoding="utf-8") as f:
            _modem_index = yaml.safe_load(f) or {"modems": {}}
        _LOGGER.debug("Loaded modem index with %d entries", len(_modem_index.get("modems", {})))
    except Exception as e:
        _LOGGER.warning("Failed to load modem index: %s", e)
        _modem_index = {"modems": {}}

    return _modem_index


def get_modem_path_for_parser(parser_class_name: str) -> str | None:
    """Get modem path from index by parser class name.

    This is the fast path - looks up in index without loading any modem.yaml files.

    Args:
        parser_class_name: Parser class name (e.g., "MotorolaMB7621Parser")

    Returns:
        Relative path to modem folder (e.g., "motorola/mb7621") or None if not found.
    """
    index = load_modem_index()
    entry = index.get("modems", {}).get(parser_class_name)
    if entry and isinstance(entry, dict):
        path = entry.get("path")
        return str(path) if path else None
    return None


def get_detection_hints_from_index(parser_class_name: str) -> dict[str, str | list[str] | None] | None:
    """Get detection hints directly from index (no modem.yaml loading).

    This is the fastest path for YAML-driven detection - reads pre-computed
    hints from the cached index without loading any modem.yaml files.

    Used by data_orchestrator Phase 0a for fast parser detection.

    Args:
        parser_class_name: Parser class name (e.g., "MotorolaMB7621Parser")

    Returns:
        Dict with pre_auth, post_auth (lists), and page_hint (str) keys,
        or None if not found.
    """
    index = load_modem_index()
    entry = index.get("modems", {}).get(parser_class_name)
    if entry and isinstance(entry, dict):
        detection = entry.get("detection")
        if detection and isinstance(detection, dict):
            result: dict[str, str | list[str] | None] = detection
            return result
    return None


def get_aggregated_auth_patterns() -> dict:
    """Get aggregated auth patterns from index (architecture).

    Returns auth patterns aggregated from ALL modem.yaml files, enabling
    core auth code to use collective knowledge without modem-specific logic.

    Returns:
        Dict with structure:
        {
            "form": {
                "username_fields": ["loginUsername", "username", ...],
                "password_fields": ["loginPassword", "password", ...],
                "actions": ["/goform/login", ...],
                "encodings": [{"detect": "pattern", "type": "base64"}, ...]
            },
            "hnap": {"endpoints": [...], "namespaces": [...]},
            "url_token": {"indicators": [...]}
        }
    """
    index = load_modem_index()
    default: dict[str, Any] = {
        "form": {
            "username_fields": [],
            "password_fields": [],
            "actions": [],
            "encodings": [],
        },
        "hnap": {"endpoints": [], "namespaces": []},
        "url_token": {"indicators": []},
    }
    result: dict[str, Any] = index.get("auth_patterns", default)
    return result


def load_modem_config_by_parser(parser_class_name: str) -> ModemConfig | None:
    """Load modem config directly using index lookup.

    This is the preferred method for known parsers - uses index to find
    the modem path, then loads just that one modem.yaml file.

    Args:
        parser_class_name: Parser class name (e.g., "MotorolaMB7621Parser")

    Returns:
        ModemConfig if found, None otherwise.
    """
    path = get_modem_path_for_parser(parser_class_name)
    if not path:
        _LOGGER.debug("Parser %s not found in index", parser_class_name)
        return None

    modems_root = get_modems_root()
    modem_path = modems_root / path

    if not modem_path.exists():
        _LOGGER.warning("Modem path %s from index does not exist", modem_path)
        return None

    try:
        return load_modem_config(modem_path)
    except Exception as e:
        _LOGGER.warning("Failed to load modem config from %s: %s", modem_path, e)
        return None


def get_modems_root() -> Path:
    """Get the root directory for modem configurations.

    Returns:
        Path to the modems/ directory containing modem.yaml files.

    The function checks two locations:
    1. custom_components/cable_modem_monitor/modems/ (deployed via sync)
    2. Repo root modems/ (development environment)
    """
    current = Path(__file__).resolve()
    # This file is at: custom_components/cable_modem_monitor/modem_config/loader.py
    component_root = current.parent.parent  # custom_components/cable_modem_monitor/

    # Primary: Check deployed location (synced from repo modems/)
    deployed_modems = component_root / "modems"
    if deployed_modems.exists():
        return deployed_modems

    # Fallback: Check repo root (for development)
    repo_root = component_root.parent.parent  # cable_modem_monitor/ repo root
    repo_modems = repo_root / "modems"
    if repo_modems.exists():
        return repo_modems

    _LOGGER.warning("Modems directory not found at %s", deployed_modems)
    return deployed_modems  # Return expected path for error messages


def load_modem_config(modem_path: Path | str) -> ModemConfig:
    """Load a modem configuration from a modem.yaml file.

    Args:
        modem_path: Path to the modem directory (containing modem.yaml)
                    or direct path to modem.yaml file.

    Returns:
        Parsed ModemConfig object.

    Raises:
        FileNotFoundError: If modem.yaml doesn't exist.
        ValueError: If modem.yaml is invalid.
    """
    path = Path(modem_path)

    # Handle both directory and file paths
    if path.name == "modem.yaml":
        yaml_path = path
    else:
        yaml_path = path / "modem.yaml"

    # Check cache
    if yaml_path in _config_cache:
        return _config_cache[yaml_path]

    if not yaml_path.exists():
        raise FileNotFoundError(f"modem.yaml not found at {yaml_path}")

    _LOGGER.debug("Loading modem config from %s", yaml_path)

    with open(yaml_path, encoding="utf-8") as f:
        raw_config = yaml.safe_load(f)

    if not raw_config:
        raise ValueError(f"Empty modem.yaml at {yaml_path}")

    try:
        config: ModemConfig = ModemConfig.model_validate(raw_config)
    except Exception as e:
        raise ValueError(f"Invalid modem.yaml at {yaml_path}: {e}") from e

    # Cache the config
    _config_cache[yaml_path] = config

    return config


def discover_modems(  # noqa: C901
    modems_root: Path | str | None = None, force_refresh: bool = False
) -> list[tuple[Path, ModemConfig]]:
    """Discover all modem configurations.

    Results are cached after first call. Use force_refresh=True to re-scan.

    Args:
        modems_root: Root directory to search. Defaults to repository modems/ dir.
        force_refresh: If True, bypass cache and re-scan directory.

    Returns:
        List of (path, config) tuples for each discovered modem.
    """
    global _discovered_modems

    # Return cached results if available (and not forcing refresh)
    if _discovered_modems is not None and not force_refresh and modems_root is None:
        return _discovered_modems

    if modems_root is None:
        root = get_modems_root()
    else:
        root = Path(modems_root)

    if not root.exists():
        _LOGGER.warning("Modems root directory not found: %s", root)
        return []

    discovered: list[tuple[Path, ModemConfig]] = []

    # Walk the directory structure: modems/{manufacturer}/{model}/modem.yaml
    for manufacturer_dir in root.iterdir():
        if not manufacturer_dir.is_dir():
            continue

        for model_dir in manufacturer_dir.iterdir():
            if not model_dir.is_dir():
                continue

            yaml_path = model_dir / "modem.yaml"
            if yaml_path.exists():
                try:
                    config = load_modem_config(model_dir)
                    discovered.append((model_dir, config))
                    _LOGGER.debug(
                        "Discovered modem: %s %s at %s",
                        config.manufacturer,
                        config.model,
                        model_dir,
                    )
                except Exception as e:
                    _LOGGER.error(
                        "Failed to load modem config at %s: %s",
                        model_dir,
                        e,
                    )

    _LOGGER.debug("Discovered %d modem configurations", len(discovered))

    # Cache results if using default root
    if modems_root is None:
        _discovered_modems = discovered

    return discovered


def get_modem_fixtures_path(modem_path: Path | str) -> Path:
    """Get the fixtures directory for a modem.

    Args:
        modem_path: Path to the modem directory.

    Returns:
        Path to the fixtures/ subdirectory.
    """
    path = Path(modem_path)
    return path / "fixtures"


def list_modem_fixtures(modem_path: Path | str) -> list[Path]:
    """List all fixture files for a modem.

    Args:
        modem_path: Path to the modem directory.

    Returns:
        List of fixture file paths (recursively searches subdirectories).
    """
    fixtures_dir = get_modem_fixtures_path(modem_path)

    if not fixtures_dir.exists():
        return []

    # Return all files except metadata.yaml (recursively)
    return [f for f in fixtures_dir.rglob("*") if f.is_file() and f.name != "metadata.yaml"]


def load_modem_by_path(manufacturer: str, model: str, modems_root: Path | str | None = None) -> ModemConfig | None:
    """Load modem config directly by manufacturer/model path.

    This is faster than discover_modems() when you know the manufacturer and model.
    Tries common directory name patterns (lowercase, as-is).

    Args:
        manufacturer: Modem manufacturer name.
        model: Modem model name.
        modems_root: Root directory to search. Defaults to repository modems/ dir.

    Returns:
        ModemConfig if found, None otherwise.
    """
    root = Path(modems_root) if modems_root else get_modems_root()
    if not root.exists():
        return None

    # Normalize manufacturer for directory lookup
    # Handle cases like "Arris/CommScope" -> try "arris", "commscope"
    manufacturer_variants = [
        manufacturer.lower(),
        manufacturer.lower().replace("/", "").replace(" ", ""),
        manufacturer.split("/", maxsplit=1)[0].lower() if "/" in manufacturer else None,
    ]

    model_lower = model.lower()

    for mfr in manufacturer_variants:
        if mfr is None:
            continue
        modem_path = root / mfr / model_lower / "modem.yaml"
        if modem_path.exists():
            try:
                return load_modem_config(modem_path.parent)
            except Exception as e:
                _LOGGER.debug("Failed to load modem at %s: %s", modem_path, e)

    return None


def get_modem_by_model(manufacturer: str, model: str, modems_root: Path | str | None = None) -> ModemConfig | None:
    """Get modem config by manufacturer and model name.

    Tries direct path lookup first, falls back to discovery scan.

    Args:
        manufacturer: Modem manufacturer (case-insensitive).
        model: Modem model (case-insensitive).
        modems_root: Root directory to search. Defaults to repository modems/ dir.
                     Results are cached only when using the default root.

    Returns:
        ModemConfig if found, None otherwise.
    """
    # Use cached version for default root
    if modems_root is None:
        return _get_modem_by_model_cached(manufacturer, model)

    # Non-cached version for custom root
    config = load_modem_by_path(manufacturer, model, modems_root)
    if config:
        return config

    for _, config in discover_modems(modems_root):
        if config.manufacturer.lower() == manufacturer.lower() and config.model.lower() == model.lower():
            return config
    return None


@lru_cache(maxsize=32)
def _get_modem_by_model_cached(manufacturer: str, model: str) -> ModemConfig | None:
    """Cached version of get_modem_by_model for default modems root."""
    config = load_modem_by_path(manufacturer, model)
    if config:
        return config

    for _, config in discover_modems():
        if config.manufacturer.lower() == manufacturer.lower() and config.model.lower() == model.lower():
            return config
    return None


def clear_cache() -> None:
    """Clear all configuration caches."""
    global _discovered_modems, _modem_index
    _config_cache.clear()
    _discovered_modems = None
    _modem_index = None
    _get_modem_by_model_cached.cache_clear()


# =============================================================================
# ASYNC WRAPPERS (for Home Assistant event loop)
# =============================================================================


async def async_load_modem_config(hass: HomeAssistant, modem_path: Path | str) -> ModemConfig:
    """Async wrapper for load_modem_config.

    Use this from async contexts (config_flow, __init__) to avoid blocking
    the Home Assistant event loop.

    Args:
        hass: Home Assistant instance
        modem_path: Path to the modem directory or modem.yaml file

    Returns:
        Parsed ModemConfig object.
    """
    result: ModemConfig = await hass.async_add_executor_job(load_modem_config, modem_path)
    return result


async def async_load_modem_config_by_parser(hass: HomeAssistant, parser_class_name: str) -> ModemConfig | None:
    """Async wrapper for load_modem_config_by_parser.

    Use this from async contexts to avoid blocking the event loop.

    Args:
        hass: Home Assistant instance
        parser_class_name: Parser class name (e.g., "MotorolaMB7621Parser")

    Returns:
        ModemConfig if found, None otherwise.
    """
    result: ModemConfig | None = await hass.async_add_executor_job(load_modem_config_by_parser, parser_class_name)
    return result


async def async_discover_modems(hass: HomeAssistant, force_refresh: bool = False) -> list[tuple[Path, ModemConfig]]:
    """Async wrapper for discover_modems.

    Use this from async contexts to avoid blocking the event loop.

    Args:
        hass: Home Assistant instance
        force_refresh: If True, bypass cache and re-scan directory.

    Returns:
        List of (path, config) tuples for each discovered modem.
    """
    result: list[tuple[Path, ModemConfig]] = await hass.async_add_executor_job(discover_modems, None, force_refresh)
    return result
