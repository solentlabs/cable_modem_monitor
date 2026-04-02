"""Validation and serialization — Pydantic validation + YAML output.

Validates generated modem and parser dicts through the same Pydantic
models used for real config loading. Serializes validated dicts to YAML.

Per ONBOARDING_SPEC.md ``generate_config`` tool contract.
"""

from __future__ import annotations

from typing import Any

import yaml
from pydantic import ValidationError

from ...config_loader import validate_modem_config, validate_parser_config
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


# -----------------------------------------------------------------------
# Key ordering — derived from Pydantic model definitions
# -----------------------------------------------------------------------

# Top-level orders: derived from model field definition order.
# ModemConfig: identity → auth → session → actions → hardware → metadata.
# ParserConfig: downstream → upstream → system_info → aggregate.
MODEM_KEY_ORDER: list[str] = list(ModemConfig.model_fields.keys())
PARSER_KEY_ORDER: list[str] = list(ParserConfig.model_fields.keys())

# Context-specific field ordering for nested sections.
# These span discriminated unions (auth has 8 variants, parser sections
# have 6 formats) so they can't be derived from a single model.  They
# encode presentation choices: strategy before credentials, index before
# field name, github before contribution.
# fmt: off
CONTEXT_ORDERS: dict[str, list[str]] = {
    "auth":        ["strategy", "action", "login_page", "login_endpoint",
                    "login_prefix", "method", "username_field", "password_field"],
    "action":      ["type", "method", "endpoint", "action_name"],
    "hardware":    ["docsis_version"],
    "table_def":   ["selector", "row_start", "columns", "channel_type", "filter", "merge_by"],
    "column":      ["index", "offset", "key", "field", "type"],
    "contributor":  ["github", "contribution"],
    "section":     ["format", "resource"],
    "js_function": ["name", "delimiter", "fields_per_channel", "channel_type"],
}
# fmt: on


def detect_context(d: dict[str, Any]) -> str | None:
    """Detect which nested context a dict belongs to based on key signature."""
    if "strategy" in d:
        return "auth"
    if "endpoint" in d or "action_name" in d:
        return "action"
    if "docsis_version" in d:
        return "hardware"
    if "columns" in d:
        return "table_def"
    if "index" in d or "offset" in d or ("key" in d and "field" in d):
        return "column"
    if "github" in d:
        return "contributor"
    if "format" in d:
        return "section"
    if "name" in d and "delimiter" in d:
        return "js_function"
    return None


def _reorder_nested(value: Any) -> Any:
    """Recursively reorder nested dicts with context-aware field ordering."""
    if isinstance(value, dict):
        ctx = detect_context(value)
        leading = CONTEXT_ORDERS.get(ctx, []) if ctx else []
        result: dict[str, Any] = {}
        for key in leading:
            if key in value:
                result[key] = _reorder_nested(value[key])
        for key in sorted(value):
            if key not in result:
                result[key] = _reorder_nested(value[key])
        return result
    if isinstance(value, list):
        return [_reorder_nested(item) for item in value]
    return value


def normalize_key_order(data: dict[str, Any], key_order: list[str]) -> dict[str, Any]:
    """Reorder dict keys to canonical order for deterministic YAML output.

    Top-level keys follow *key_order* (derived from Pydantic model field
    definition order).  Nested dicts use context-aware ordering: the
    dict's key signature selects a leading-key list, then remaining keys
    are alphabetical.  Unknown top-level keys are appended alphabetically.

    Args:
        data: Raw config dict.
        key_order: Canonical key order for the top level.

    Returns:
        New dict with keys in canonical order at every level.
    """
    result: dict[str, Any] = {}
    for key in key_order:
        if key in data:
            result[key] = _reorder_nested(data[key])
    for key in sorted(data):
        if key not in result:
            result[key] = _reorder_nested(data[key])
    return result


# -----------------------------------------------------------------------
# YAML serialization — custom Dumper for readable output
# -----------------------------------------------------------------------


class _CatalogDumper(yaml.Dumper):
    """YAML dumper tuned for catalog config files.

    - Multi-line strings use ``|`` (literal block) style.
    - Sequences indent under their parent key (not flush).
    """

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        """Force sequences to indent under their parent key."""
        super().increase_indent(flow, False)


def _str_representer(dumper: yaml.Dumper, data: str) -> yaml.ScalarNode:
    """Use literal block style for multi-line strings."""
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_CatalogDumper.add_representer(str, _str_representer)


def to_yaml(data: dict[str, Any]) -> str:
    """Serialize a dict to a YAML string with catalog-standard formatting."""
    result: str = yaml.dump(
        data,
        Dumper=_CatalogDumper,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )
    return result
