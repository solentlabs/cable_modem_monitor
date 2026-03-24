"""Validation and serialization — Pydantic validation + YAML output.

Validates generated modem and parser dicts through the same Pydantic
models used for real config loading. Serializes validated dicts to YAML.

Per ONBOARDING_SPEC.md ``generate_config`` tool contract.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml
from pydantic import ValidationError

from ...config_loader import validate_modem_config, validate_parser_config

if TYPE_CHECKING:
    from ...models.modem_config import ModemConfig
    from ...models.parser_config.config import ParserConfig


def validate_modem(
    data: dict[str, Any],
    errors: list[str],
) -> ModemConfig | None:
    """Validate modem dict, appending errors on failure."""
    try:
        return validate_modem_config(data)
    except ValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"])
            errors.append(f"modem.yaml: {loc}: {err['msg']}")
        return None


def validate_parser(
    data: dict[str, Any],
    errors: list[str],
) -> ParserConfig | None:
    """Validate parser dict, appending errors on failure."""
    try:
        return validate_parser_config(data)
    except ValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"])
            errors.append(f"parser.yaml: {loc}: {err['msg']}")
        return None


def to_yaml(data: dict[str, Any]) -> str:
    """Serialize a dict to a YAML string."""
    result: str = yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return result
