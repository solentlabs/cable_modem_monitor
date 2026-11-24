"""Every user-facing raise renders from the exceptions section of strings.json.

HA shows the raw translation key when strings.json lacks it, and an
inline message bypasses translation entirely (Gold
``exception-translations``; HA_ADAPTER_SPEC § action failures).
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

_COMPONENT_DIR = Path(__file__).resolve().parents[2] / "custom_components" / "cable_modem_monitor"
_STRINGS = json.loads((_COMPONENT_DIR / "strings.json").read_text(encoding="utf-8"))
_EXCEPTIONS = _STRINGS["exceptions"]
_LANGUAGE_FILES = sorted(p.name for p in (_COMPONENT_DIR / "translations").glob("*.json"))

# Exception classes a user sees: action results, button presses, setup.
_USER_FACING = {"HomeAssistantError", "ServiceValidationError", "ConfigEntryError"}
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def _raises() -> list[tuple[str, int, ast.Call]]:
    """Every ``raise <UserFacingError>(...)`` in the integration's modules."""
    found = []
    for path in sorted(_COMPONENT_DIR.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
                name = getattr(node.exc.func, "id", None) or getattr(node.exc.func, "attr", None)
                if name in _USER_FACING:
                    found.append((path.name, node.lineno, node.exc))
    return found


def _literal_strings(node: ast.expr) -> set[str]:
    """String constants an expression can evaluate to (both arms of a conditional)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    if isinstance(node, ast.IfExp):
        return _literal_strings(node.body) | _literal_strings(node.orelse)
    return set()


def _keyword(call: ast.Call, name: str) -> ast.expr | None:
    return next((kw.value for kw in call.keywords if kw.arg == name), None)


def test_every_raise_carries_a_translation_key() -> None:
    """No user-facing raise passes an inline message."""
    inline = [f"{file}:{line}" for file, line, call in _raises() if _keyword(call, "translation_key") is None]

    assert _raises(), "no user-facing raises found"
    assert not inline, f"raises without translation_key: {inline}"


def test_raised_keys_match_declared_keys() -> None:
    """Every raised key is declared, and every declared key is raised."""
    raised: set[str] = set()
    for _, _, call in _raises():
        key = _keyword(call, "translation_key")
        if key is not None:
            raised |= _literal_strings(key)

    assert raised == set(_EXCEPTIONS)


@pytest.mark.parametrize("language_file", _LANGUAGE_FILES)
def test_translated_messages_keep_their_placeholders(language_file: str) -> None:
    """A translation that drops or renames {model} or {error} would render it raw."""
    messages = json.loads((_COMPONENT_DIR / "translations" / language_file).read_text(encoding="utf-8"))["exceptions"]

    for key, entry in _EXCEPTIONS.items():
        expected = set(_PLACEHOLDER.findall(entry["message"]))
        assert set(_PLACEHOLDER.findall(messages[key]["message"])) == expected, f"{language_file}: {key}"
