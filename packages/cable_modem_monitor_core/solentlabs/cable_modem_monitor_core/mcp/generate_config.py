"""Config Generation Tool — MCP tool.

Takes analysis result (from ``analyze_har``) plus metadata and produces
modem.yaml and parser.yaml content. Runs Pydantic validation and
cross-file consistency checks before returning.

Does NOT write files — returns content for the caller to review and place.

Per ONBOARDING_SPEC.md ``generate_config`` tool contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml
from pydantic import ValidationError

from ..config_loader import validate_modem_config, validate_parser_config
from ..validation.cross_file import validate_cross_file


@dataclass
class GenerateConfigResult:
    """Result of config generation."""

    modem_yaml: str
    parser_yaml: str | None
    parser_py: str | None
    validation: ValidationResult


@dataclass
class ValidationResult:
    """Validation outcome for generated configs."""

    valid: bool
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for MCP tool output."""
        return {"valid": self.valid, "errors": self.errors}


def generate_config(
    analysis: dict[str, Any],
    metadata: dict[str, Any],
) -> GenerateConfigResult:
    """Generate modem.yaml and parser.yaml from analysis output.

    Args:
        analysis: Dict from ``AnalysisResult.to_dict()`` — contains
            transport, auth, session, actions, and sections.
        metadata: Caller-provided metadata — manufacturer, model,
            hardware, status, attribution, isps, etc.

    Returns:
        GenerateConfigResult with YAML strings and validation outcome.
    """
    errors: list[str] = []

    # Build modem.yaml dict
    modem_dict = _build_modem_dict(analysis, metadata)

    # Build parser.yaml dict (None if no sections)
    sections = analysis.get("sections")
    parser_dict = _build_parser_dict(sections) if sections else None

    # Validate via Pydantic
    modem_config = _validate_modem(modem_dict, errors)
    parser_config = _validate_parser(parser_dict, errors) if parser_dict else None

    # Cross-file checks (only if both validated)
    if modem_config and parser_config:
        cross_errors = validate_cross_file(modem_config, parser_config)
        errors.extend(cross_errors)

    # Serialize to YAML
    modem_yaml = _to_yaml(modem_dict)
    parser_yaml = _to_yaml(parser_dict) if parser_dict else None

    return GenerateConfigResult(
        modem_yaml=modem_yaml,
        parser_yaml=parser_yaml,
        parser_py=None,
        validation=ValidationResult(valid=len(errors) == 0, errors=errors),
    )


# ---------------------------------------------------------------------------
# Modem dict assembly
# ---------------------------------------------------------------------------


def _build_modem_dict(analysis: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    """Assemble a modem.yaml dict from analysis output and metadata."""
    result: dict[str, Any] = {}
    _add_identity(result, analysis, metadata)
    _add_analysis_blocks(result, analysis)
    _add_metadata_fields(result, metadata)
    return result


def _add_identity(result: dict[str, Any], analysis: dict[str, Any], metadata: dict[str, Any]) -> None:
    """Add identity fields from metadata and analysis."""
    result["manufacturer"] = metadata.get("manufacturer", "")
    result["model"] = metadata.get("model", "")
    if metadata.get("model_aliases"):
        result["model_aliases"] = metadata["model_aliases"]
    if metadata.get("brands"):
        result["brands"] = metadata["brands"]
    result["transport"] = metadata.get("transport") or analysis.get("transport", "http")
    result["default_host"] = metadata.get("default_host", "")


def _add_analysis_blocks(result: dict[str, Any], analysis: dict[str, Any]) -> None:
    """Add auth, session, and actions blocks from analysis output."""
    auth_block = _build_auth_block(analysis.get("auth", {}))
    if auth_block:
        result["auth"] = auth_block

    session_block = _build_session_block(analysis.get("session", {}))
    if session_block:
        result["session"] = session_block

    actions_block = _build_actions_block(analysis.get("actions", {}))
    if actions_block:
        result["actions"] = actions_block


def _add_metadata_fields(result: dict[str, Any], metadata: dict[str, Any]) -> None:
    """Add hardware, status, attribution, and other metadata fields."""
    if metadata.get("aggregate"):
        result["aggregate"] = metadata["aggregate"]
    if metadata.get("hardware"):
        result["hardware"] = metadata["hardware"]
    if metadata.get("timeout"):
        result["timeout"] = metadata["timeout"]

    result["status"] = metadata.get("status", "in_progress")
    if metadata.get("sources"):
        result["sources"] = metadata["sources"]
    if metadata.get("attribution"):
        result["attribution"] = metadata["attribution"]
    if metadata.get("isps"):
        result["isps"] = metadata["isps"]
    if metadata.get("notes"):
        result["notes"] = metadata["notes"]
    if metadata.get("references"):
        result["references"] = metadata["references"]


def _build_auth_block(auth: dict[str, Any]) -> dict[str, Any] | None:
    """Build auth config from analysis auth detail."""
    strategy = auth.get("strategy")
    if not strategy:
        return None

    result: dict[str, Any] = {"strategy": strategy}
    # Merge strategy-specific fields
    for key, value in auth.get("fields", {}).items():
        result[key] = value
    return result


def _build_session_block(session: dict[str, Any]) -> dict[str, Any] | None:
    """Build session config from analysis session detail.

    Omits empty/default values so the config stays clean.
    """
    result: dict[str, Any] = {}

    if session.get("cookie_name"):
        result["cookie_name"] = session["cookie_name"]
    if session.get("max_concurrent"):
        result["max_concurrent"] = session["max_concurrent"]
    if session.get("token_prefix"):
        result["token_prefix"] = session["token_prefix"]
    if session.get("headers"):
        result["headers"] = session["headers"]

    return result if result else None


def _build_actions_block(actions: dict[str, Any]) -> dict[str, Any] | None:
    """Build actions config from analysis actions detail."""
    result: dict[str, Any] = {}

    for action_name in ("logout", "restart"):
        action = actions.get(action_name)
        if action:
            result[action_name] = _build_single_action(action)

    return result if result else None


def _build_single_action(action: dict[str, Any]) -> dict[str, Any]:
    """Build a single action config dict."""
    result: dict[str, Any] = {"type": action["type"]}

    if action["type"] == "http":
        result["method"] = action.get("method", "GET")
        result["endpoint"] = action.get("endpoint", "")
        if action.get("params"):
            result["params"] = action["params"]
    elif action["type"] == "hnap":
        result["action_name"] = action.get("action_name", "")
        if action.get("params"):
            result["params"] = action["params"]

    return result


# ---------------------------------------------------------------------------
# Parser dict assembly
# ---------------------------------------------------------------------------


def _build_parser_dict(sections: dict[str, Any]) -> dict[str, Any] | None:
    """Transform analysis sections into parser.yaml dict."""
    result: dict[str, Any] = {}

    for section_name in ("downstream", "upstream"):
        section = sections.get(section_name)
        if section:
            transformed = _transform_channel_section(section)
            if transformed:
                result[section_name] = transformed

    # system_info passes through (already matches parser.yaml structure)
    system_info = sections.get("system_info")
    if system_info:
        result["system_info"] = system_info

    return result if result else None


def _transform_channel_section(section: dict[str, Any]) -> dict[str, Any] | None:
    """Transform a channel section from analysis format to parser.yaml format.

    Dispatches to format-specific transformers based on the ``format`` field.
    """
    fmt = section.get("format", "")

    if fmt == "table":
        return _transform_table(section)
    if fmt == "table_transposed":
        return _transform_transposed(section)
    if fmt == "javascript":
        return _transform_javascript(section)
    if fmt == "hnap":
        return _transform_hnap(section)
    if fmt == "json":
        return _transform_json(section)

    return None


def _transform_table(section: dict[str, Any]) -> dict[str, Any]:
    """Transform table format from analysis to parser.yaml structure."""
    columns = [_mapping_to_column(m) for m in section.get("mappings", [])]

    table_def: dict[str, Any] = {}
    if section.get("selector"):
        table_def["selector"] = section["selector"]
    if section.get("row_start"):
        table_def["skip_rows"] = section["row_start"]
    table_def["columns"] = columns
    if section.get("channel_type"):
        table_def["channel_type"] = section["channel_type"]
    if section.get("filter"):
        table_def["filter"] = section["filter"]

    return {
        "format": "table",
        "resource": section.get("resource", ""),
        "tables": [table_def],
    }


def _transform_transposed(section: dict[str, Any]) -> dict[str, Any]:
    """Transform transposed table from analysis to parser.yaml structure."""
    rows = [_mapping_to_row(m) for m in section.get("mappings", [])]

    result: dict[str, Any] = {
        "format": "table_transposed",
        "resource": section.get("resource", ""),
    }

    if section.get("selector"):
        result["selector"] = section["selector"]
    result["rows"] = rows
    if section.get("channel_type"):
        result["channel_type"] = section["channel_type"]

    return result


def _transform_javascript(section: dict[str, Any]) -> dict[str, Any]:
    """Transform JS format from analysis to parser.yaml structure."""
    channels = [_mapping_to_channel(m) for m in section.get("mappings", [])]
    channel_type = section.get("channel_type", {})

    func_def: dict[str, Any] = {
        "name": section.get("function_name", ""),
        "channel_type": channel_type.get("fixed", "qam") if channel_type else "qam",
        "delimiter": section.get("delimiter", "|"),
        "fields_per_channel": section.get("fields_per_record", 0),
        "channels": channels,
    }
    if section.get("filter"):
        func_def["filter"] = section["filter"]

    return {
        "format": "javascript",
        "resource": section.get("resource", ""),
        "functions": [func_def],
    }


def _transform_hnap(section: dict[str, Any]) -> dict[str, Any]:
    """Transform HNAP format from analysis to parser.yaml structure."""
    channels = [_mapping_to_channel(m) for m in section.get("mappings", [])]

    result: dict[str, Any] = {
        "format": "hnap",
        "response_key": section.get("response_key", ""),
        "data_key": section.get("data_key", ""),
        "record_delimiter": section.get("record_delimiter", "|+|"),
        "field_delimiter": section.get("field_delimiter", "^"),
        "channels": channels,
    }
    if section.get("channel_type"):
        result["channel_type"] = section["channel_type"]
    if section.get("filter"):
        result["filter"] = section["filter"]

    return result


def _transform_json(section: dict[str, Any]) -> dict[str, Any]:
    """Transform JSON format from analysis to parser.yaml structure."""
    channels = [_mapping_to_json_channel(m) for m in section.get("mappings", [])]

    result: dict[str, Any] = {
        "format": "json",
        "resource": section.get("resource", ""),
        "array_path": section.get("array_path", ""),
        "channels": channels,
    }
    if section.get("channel_type"):
        result["channel_type"] = section["channel_type"]
    if section.get("filter"):
        result["filter"] = section["filter"]

    return result


# ---------------------------------------------------------------------------
# Mapping conversion helpers
# ---------------------------------------------------------------------------


def _mapping_to_column(mapping: dict[str, Any]) -> dict[str, Any]:
    """Convert analysis FieldMapping to table ColumnMapping dict."""
    result: dict[str, Any] = {
        "index": mapping.get("index", 0),
        "field": mapping["field"],
        "type": mapping["type"],
    }
    if mapping.get("unit"):
        result["unit"] = mapping["unit"]
    return result


def _mapping_to_row(mapping: dict[str, Any]) -> dict[str, Any]:
    """Convert analysis FieldMapping to transposed RowMapping dict."""
    result: dict[str, Any] = {
        "label": mapping.get("label", ""),
        "field": mapping["field"],
        "type": mapping["type"],
    }
    if mapping.get("unit"):
        result["unit"] = mapping["unit"]
    return result


def _mapping_to_channel(mapping: dict[str, Any]) -> dict[str, Any]:
    """Convert analysis FieldMapping to HNAP/JS ChannelMapping dict."""
    result: dict[str, Any] = {"field": mapping["field"], "type": mapping["type"]}
    if mapping.get("offset") is not None:
        result["offset"] = mapping["offset"]
    elif mapping.get("index") is not None:
        result["index"] = mapping["index"]
    if mapping.get("unit"):
        result["unit"] = mapping["unit"]
    return result


def _mapping_to_json_channel(mapping: dict[str, Any]) -> dict[str, Any]:
    """Convert analysis FieldMapping to JSON JsonChannelMapping dict."""
    result: dict[str, Any] = {
        "key": mapping.get("key", ""),
        "field": mapping["field"],
        "type": mapping["type"],
    }
    if mapping.get("unit"):
        result["unit"] = mapping["unit"]
    return result


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_modem(data: dict[str, Any], errors: list[str]) -> Any:
    """Validate modem dict, appending errors on failure.

    Returns the ModemConfig on success, None on failure.
    """
    try:
        return validate_modem_config(data)
    except ValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"])
            errors.append(f"modem.yaml: {loc}: {err['msg']}")
        return None


def _validate_parser(data: dict[str, Any], errors: list[str]) -> Any:
    """Validate parser dict, appending errors on failure.

    Returns the ParserConfig on success, None on failure.
    """
    try:
        return validate_parser_config(data)
    except ValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"])
            errors.append(f"parser.yaml: {loc}: {err['msg']}")
        return None


# ---------------------------------------------------------------------------
# YAML serialization
# ---------------------------------------------------------------------------


def _to_yaml(data: dict[str, Any]) -> str:
    """Serialize a dict to a YAML string."""
    result: str = yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return result
