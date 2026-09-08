"""Catalog YAML text layout: top-level key order and section spacing."""

from __future__ import annotations

import re

from ..models.modem_config import ModemConfig
from ..models.parser_config import ParserConfig

# Model field order is the canonical key order for each file;
# MODEM_YAML_SPEC § Layout is the rule's home.
MODEM_KEY_ORDER: tuple[str, ...] = tuple(ModemConfig.model_fields)
PARSER_KEY_ORDER: tuple[str, ...] = tuple(ParserConfig.model_fields)

# modem.yaml identity block: every key before auth reads as one unit (what
# the modem is and how to reach it), so no blank lines separate them.
# Every other top-level key, in either file, starts a section and gets a
# blank line before it.
IDENTITY_KEYS: frozenset[str] = frozenset(MODEM_KEY_ORDER[: MODEM_KEY_ORDER.index("auth")])

_TOP_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):")


def top_level_keys(text: str) -> list[str]:
    """Top-level mapping keys in file order."""
    return [m.group(1) for line in text.split("\n") if (m := _TOP_KEY.match(line))]


def order_errors(text: str, order: tuple[str, ...]) -> list[str]:
    """Report top-level keys that are unknown to the model or out of its order."""
    keys = top_level_keys(text)
    unknown = [k for k in keys if k not in order]
    if unknown:
        return [f"top-level keys not in the model: {unknown}"]
    expected = [k for k in order if k in keys]
    if keys == expected:
        return []
    return [f"top-level keys out of order: found {keys}, expected {expected}"]


def apply_section_spacing(text: str, *, contiguous: frozenset[str] = frozenset()) -> str:
    """Return text with contiguous keys packed together and a blank line before every other top-level key."""
    out: list[str] = []
    # Column-zero comments belong to the key that follows them, so a
    # section's blank line goes above its comment, not between them.
    pending_comments: list[str] = []
    seen_key = False
    for line in text.split("\n"):
        if line.startswith("#"):
            pending_comments.append(line)
            continue
        match = _TOP_KEY.match(line)
        if match and seen_key:
            if match.group(1) in contiguous:
                while out and out[-1] == "":
                    out.pop()
            elif out and out[-1] != "":
                out.append("")
        seen_key = seen_key or match is not None
        out.extend(pending_comments)
        pending_comments.clear()
        out.append(line)
    out.extend(pending_comments)
    return "\n".join(out)


def _layout_errors(text: str, order: tuple[str, ...], contiguous: frozenset[str]) -> list[str]:
    errors = order_errors(text, order)
    if apply_section_spacing(text, contiguous=contiguous) != text:
        errors.append("section spacing differs from the spec layout")
    return errors


def modem_layout_errors(text: str) -> list[str]:
    """Report every layout rule a modem.yaml text breaks."""
    return _layout_errors(text, MODEM_KEY_ORDER, IDENTITY_KEYS)


def parser_layout_errors(text: str) -> list[str]:
    """Report every layout rule a parser.yaml text breaks."""
    return _layout_errors(text, PARSER_KEY_ORDER, frozenset())
