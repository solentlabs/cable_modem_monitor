"""json_sjcl crypto parameters, read from the scripts the capture loaded.

The PBKDF2 iterations and key length are constants in the modem's SJCL
wrapper script; the aad is the string literal every encrypt call passes.
A value the scripts do not state, or state two ways, is left out with a
warning: no default stands in for evidence.

Per docs/ONBOARDING_SPEC.md Phase 2 (HTTP transport, JSON login).
"""

from __future__ import annotations

import re
from typing import Any

from ...validation.har_utils import WARNING_PREFIX, path_from_url
from ..ambiguity import Evidence
from .patterns import get_json_sjcl_encrypt_calls, get_json_sjcl_script_constants

_CONSTANTS = get_json_sjcl_script_constants()
_ENCRYPT_CALLS = get_json_sjcl_encrypt_calls()
_AAD_ARGUMENT = 3
# A call's arguments end well inside this; the bound keeps a stray open paren cheap.
_MAX_CALL_LENGTH = 2000
_LITERAL = re.compile(r"""(["'])([^"'\\]*)\1""")
_SNIPPET_LENGTH = 120


def read_sjcl_params(entries: list[dict[str, Any]], warnings: list[str]) -> tuple[dict[str, Any], list[Evidence]]:
    """The crypto fields the capture's scripts state, with the evidence for each."""
    texts = [
        (path_from_url(entry["request"].get("url", "")), text)
        for entry in entries
        if (text := entry["response"].get("content", {}).get("text") or "")
    ]
    fields: dict[str, Any] = {}
    found: list[Evidence] = []
    for field, constant in _CONSTANTS.items():
        pattern = re.compile(rf"\b{re.escape(constant)}\s*=\s*(\d+)")
        seen: dict[int, Evidence] = {}
        for source, text in texts:
            if match := pattern.search(text):
                seen.setdefault(int(match.group(1)), Evidence(source=source, snippet=match.group(0)))
        _take(field, constant, {str(v): e for v, e in seen.items()}, fields, found, warnings, number=True)

    literals: dict[str, Evidence] = {}
    for source, text in texts:
        for call in _ENCRYPT_CALLS:
            for match in re.finditer(rf"\b{re.escape(call)}\s*\(", text):
                args = _call_arguments(text, match.end())
                if len(args) > _AAD_ARGUMENT and (literal := _LITERAL.fullmatch(args[_AAD_ARGUMENT].strip())):
                    snippet = text[match.start() : match.end() + _SNIPPET_LENGTH].split("\n")[0]
                    literals.setdefault(literal.group(2), Evidence(source=source, snippet=snippet))
    _take("aad", ", ".join(_ENCRYPT_CALLS), literals, fields, found, warnings, number=False)
    return fields, found


def _take(
    field: str,
    declared_by: str,
    seen: dict[str, Evidence],
    fields: dict[str, Any],
    found: list[Evidence],
    warnings: list[str],
    *,
    number: bool,
) -> None:
    """Record the one value seen; with none or several, warn and leave the field out."""
    if len(seen) == 1:
        value, evidence = next(iter(seen.items()))
        fields[field] = int(value) if number else value
        found.append(evidence)
        return
    said = f"the scripts give {', '.join(sorted(seen))}" if seen else "no loaded script states it"
    warnings.append(f"{WARNING_PREFIX} json_sjcl {field} (from {declared_by}): {said}; set it from the modem's script.")


def _call_arguments(text: str, start: int) -> list[str]:
    """Split a call's arguments at top-level commas, honoring quotes and nesting; empty if unterminated."""
    args: list[str] = []
    current: list[str] = []
    depth = 1
    quote = ""
    index = start
    end = min(len(text), start + _MAX_CALL_LENGTH)
    while index < end:
        char = text[index]
        if quote:
            current.append(char)
            if char == "\\" and index + 1 < end:
                index += 1
                current.append(text[index])
            elif char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
            current.append(char)
        elif char in "([{":
            depth += 1
            current.append(char)
        elif char in ")]}":
            depth -= 1
            if depth == 0:
                args.append("".join(current))
                return args
            current.append(char)
        elif char == "," and depth == 1:
            args.append("".join(current))
            current = []
        else:
            current.append(char)
        index += 1
    return []
