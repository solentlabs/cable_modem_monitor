"""Inline ``$.ajax({...})`` call-site parsing for source-inferred action extraction.

Parses jQuery ajax options objects found in captured page source so
Phase 4 can extract method, endpoint, and data params for actions that
never fired during HAR capture. Only the options-object form is
supported — it is the only shape observed at action call sites across
the fleet HARs (XB10 restart, S33-family logout). ``$.post(url, {...})``
exists in fleet page source but never at an action endpoint, so it is
deliberately out of scope until a fleet HAR shows one.

Per docs/ONBOARDING_SPEC.md Phase 4 (source-inferred call sites).
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field

_AJAX_CALL_PATTERN = re.compile(r"\$\.ajax\s*\(\s*\{")

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_$][\w$]*$")

# Hard bound on how far one options object may span. Fleet call sites
# are well under 1 kB; anything larger is minified library noise.
_MAX_SPAN = 4000

_QUOTES = frozenset({'"', "'", "`"})
_OPENERS = frozenset({"{", "[", "("})
_CLOSERS = frozenset({"}", "]", ")"})


@dataclass
class AjaxCallsite:
    """One parsed ``$.ajax({...})`` options object."""

    url: str
    method: str = ""  # empty when the call site has no `type:` field
    params: dict[str, str] = field(default_factory=dict)  # string-literal values
    unresolved: dict[str, str] = field(default_factory=dict)  # name -> JS expression
    data_identifier: str = ""  # set when `data:` is a bare identifier


def find_ajax_callsites(body: str) -> list[AjaxCallsite]:
    """Parse all ajax options objects in a page body into call sites."""
    sites: list[AjaxCallsite] = []
    for match in _AJAX_CALL_PATTERN.finditer(body):
        open_idx = body.index("{", match.start())
        close_idx = _balanced_end(body, open_idx)
        if close_idx is None:
            continue
        site = _parse_options(body[open_idx + 1 : close_idx])
        if site is not None:
            sites.append(site)
    return sites


def _parse_options(options_text: str) -> AjaxCallsite | None:
    """Build a call site from the inner text of one options object."""
    url = ""
    method = ""
    data_text = ""
    for key, value in _split_object_fields(options_text):
        if key == "url":
            url = _string_literal(value) or ""
        elif key == "type":
            method = (_string_literal(value) or "").upper()
        elif key == "data":
            data_text = value
    if not url:
        return None

    site = AjaxCallsite(url=url, method=method)
    if data_text.startswith("{") and data_text.endswith("}"):
        for name, expr in _split_object_fields(data_text[1:-1]):
            literal = _string_literal(expr)
            if literal is not None:
                site.params[name] = literal
            else:
                site.unresolved[name] = expr
    elif _IDENTIFIER_PATTERN.match(data_text):
        site.data_identifier = data_text
    return site


def _significant_chars(text: str) -> Iterator[tuple[int, str]]:
    """Yield (index, char) for chars outside string literals, escape-aware."""
    quote = ""
    escaped = False
    for i, ch in enumerate(text):
        if escaped:
            escaped = False
        elif ch == "\\":
            escaped = True
        elif quote:
            if ch == quote:
                quote = ""
        elif ch in _QUOTES:
            quote = ch
        else:
            yield i, ch


def _balanced_end(text: str, open_idx: int) -> int | None:
    """Index of the brace closing ``text[open_idx]``, quote- and escape-aware."""
    depth = 0
    span = text[open_idx : open_idx + _MAX_SPAN]
    for i, ch in _significant_chars(span):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return open_idx + i
    return None


def _split_object_fields(text: str) -> list[tuple[str, str]]:
    """Split object-literal innards into (key, value-expression) pairs.

    Operates at nesting depth 0 only — commas and colons inside nested
    objects, arrays, calls, or strings do not split.
    """
    fields: list[tuple[str, str]] = []
    depth = 0
    segment_start = 0
    colon_idx = -1
    for i, ch in _significant_chars(text):
        if ch in _OPENERS:
            depth += 1
        elif ch in _CLOSERS:
            depth -= 1
        elif depth == 0 and ch == ":" and colon_idx < segment_start:
            colon_idx = i
        elif depth == 0 and ch == ",":
            _emit_field(text, segment_start, colon_idx, i, fields)
            segment_start = i + 1
    _emit_field(text, segment_start, colon_idx, len(text), fields)
    return fields


def _emit_field(text: str, start: int, colon_idx: int, end: int, fields: list[tuple[str, str]]) -> None:
    """Append one (key, value) pair when the segment contains a colon."""
    if colon_idx < start:
        return
    key = text[start:colon_idx].strip().strip("\"'")
    value = text[colon_idx + 1 : end].strip()
    if key:
        fields.append((key, value))


def _string_literal(expression: str) -> str | None:
    """Inner text when the expression is a plain quoted string, else None."""
    expression = expression.strip()
    if len(expression) >= 2 and expression[0] in _QUOTES and expression[-1] == expression[0]:
        inner = expression[1:-1]
        # A quote of the same kind inside means this is not one plain literal
        # (e.g. string concatenation) — refuse rather than misread.
        if expression[0] not in inner:
            return inner
    return None
