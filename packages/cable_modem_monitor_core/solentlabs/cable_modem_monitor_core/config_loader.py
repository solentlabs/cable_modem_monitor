"""YAML config loading and Pydantic validation glue.

Entry points for loading and validating modem.yaml and parser.yaml files.
Used by ``generate_config`` (validates before writing) and by Catalog's
dev-gate (validates existing files on disk).

File-based functions do ``yaml.safe_load()`` → Pydantic model.
Dict-based functions skip the YAML step (for in-memory validation).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models.modem_config import ModemConfig
from .models.parser_config import ParserConfig


def load_modem_config(path: Path) -> ModemConfig:
    """Load and validate a modem.yaml file.

    Args:
        path: Path to the modem.yaml (or modem-{variant}.yaml) file.

    Returns:
        Validated ModemConfig instance.

    Raises:
        FileNotFoundError: If path does not exist.
        yaml.YAMLError: If file is not valid YAML.
        pydantic.ValidationError: If content fails schema validation.
    """
    data = _load_yaml(path)
    return ModemConfig(**data)


def load_parser_config(path: Path) -> ParserConfig:
    """Load and validate a parser.yaml file.

    Args:
        path: Path to the parser.yaml file.

    Returns:
        Validated ParserConfig instance.

    Raises:
        FileNotFoundError: If path does not exist.
        yaml.YAMLError: If file is not valid YAML.
        pydantic.ValidationError: If content fails schema validation.
    """
    data = _load_yaml(path)
    return ParserConfig(**data)


def validate_modem_config(data: dict[str, Any]) -> ModemConfig:
    """Validate a modem config dict against the Pydantic schema.

    Args:
        data: Dict matching the modem.yaml structure.

    Returns:
        Validated ModemConfig instance.

    Raises:
        pydantic.ValidationError: If data fails schema validation.
    """
    return ModemConfig(**data)


def validate_parser_config(data: dict[str, Any]) -> ParserConfig:
    """Validate a parser config dict against the Pydantic schema.

    Args:
        data: Dict matching the parser.yaml structure.

    Returns:
        Validated ParserConfig instance.

    Raises:
        pydantic.ValidationError: If data fails schema validation.
    """
    return ParserConfig(**data)


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file and return the parsed dict.

    Raises:
        FileNotFoundError: If path does not exist.
        yaml.YAMLError: If file is not valid YAML.
        ValueError: If file parses to something other than a dict.
    """
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)

    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML dict in {path}, got {type(data).__name__}")

    return data
