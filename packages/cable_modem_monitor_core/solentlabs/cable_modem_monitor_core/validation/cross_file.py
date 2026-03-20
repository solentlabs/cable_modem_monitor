"""Cross-file consistency checks between modem.yaml and parser.yaml.

Validates constraints that span both config files — transport vs format
compatibility, and aggregate field name collisions with system_info.

Individual file validation is handled by Pydantic model validators
(transport constraints, auth-session-action consistency, required
fields by status). This module handles what neither model can validate
alone.
"""

from __future__ import annotations

from ..models.modem_config import ModemConfig
from ..models.parser_config import ParserConfig
from ..models.parser_config.system_info import JSSystemInfoSource

# Formats valid per transport (same constraint table as MODEM_YAML_SPEC)
_VALID_FORMATS: dict[str, frozenset[str]] = {
    "hnap": frozenset({"hnap"}),
    "http": frozenset({"table", "table_transposed", "html_fields", "javascript", "json"}),
}


def validate_cross_file(modem: ModemConfig, parser: ParserConfig) -> list[str]:
    """Run cross-file consistency checks.

    Args:
        modem: Validated ModemConfig instance.
        parser: Validated ParserConfig instance.

    Returns:
        List of error messages. Empty list means all checks passed.
    """
    errors: list[str] = []
    _check_transport_format(modem, parser, errors)
    _check_aggregate_collisions(modem, parser, errors)
    return errors


def _check_transport_format(modem: ModemConfig, parser: ParserConfig, errors: list[str]) -> None:
    """Validate that parser.yaml formats are compatible with modem.yaml transport."""
    valid_formats = _VALID_FORMATS.get(modem.transport, frozenset())
    section_formats = _collect_section_formats(parser)

    for section_name, fmt in section_formats:
        if fmt not in valid_formats:
            errors.append(
                f"transport '{modem.transport}' does not support format "
                f"'{fmt}' in section '{section_name}' — "
                f"valid formats: {sorted(valid_formats)}"
            )


def _check_aggregate_collisions(modem: ModemConfig, parser: ParserConfig, errors: list[str]) -> None:
    """Validate that aggregate field names don't collide with system_info fields."""
    if not modem.aggregate or parser.system_info is None:
        return

    system_info_fields = _collect_system_info_fields(parser)
    for agg_name in modem.aggregate:
        if agg_name in system_info_fields:
            errors.append(f"aggregate field '{agg_name}' collides with system_info " f"field — one source per field")


def _collect_section_formats(parser: ParserConfig) -> list[tuple[str, str]]:
    """Collect (section_name, format) pairs from parser config.

    Returns format values for downstream, upstream, and system_info
    source formats.
    """
    results: list[tuple[str, str]] = []

    if parser.downstream is not None:
        results.append(("downstream", parser.downstream.format))

    if parser.upstream is not None:
        results.append(("upstream", parser.upstream.format))

    if parser.system_info is not None:
        for source in parser.system_info.sources:
            results.append(("system_info", source.format))

    return results


def _collect_system_info_fields(parser: ParserConfig) -> set[str]:
    """Collect all field names from system_info sources.

    Handles all source types: html_fields, hnap, json have a ``fields``
    list directly. javascript sources have ``functions`` containing
    ``fields`` lists.
    """
    fields: set[str] = set()

    if parser.system_info is None:
        return fields

    for source in parser.system_info.sources:
        if isinstance(source, JSSystemInfoSource):
            for func in source.functions:
                for js_field in func.fields:
                    fields.add(js_field.field)
        else:
            for mapping in source.fields:
                fields.add(mapping.field)

    return fields
