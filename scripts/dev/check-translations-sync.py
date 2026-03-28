#!/usr/bin/env python3
"""Pre-commit hook to verify translation files match strings.json structure.

HA custom components require strings.json (source of truth) and
translations/*.json (runtime). If they drift apart, field labels
show as raw key names in the UI.

Checks:
- translations/en.json must be an exact copy of strings.json
- All other language files must have the same key structure
  (same sections, steps, field names — values differ by language)

Exit codes:
- 0: All files in sync
- 1: Structural drift detected
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_COMPONENT_DIR = Path("custom_components/cable_modem_monitor")
_STRINGS = _COMPONENT_DIR / "strings.json"
_TRANSLATIONS_DIR = _COMPONENT_DIR / "translations"


def _extract_keys(obj: Any, prefix: str = "") -> set[str]:
    """Recursively extract all key paths from a nested dict.

    Returns paths like ``config.step.user.data.host``.
    """
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else k
            keys.add(path)
            keys.update(_extract_keys(v, path))
    return keys


def _check_en_exact(strings: dict[str, Any], trans: dict[str, Any], name: str) -> str | None:
    """Check that en.json is an exact copy of strings.json."""
    if trans == strings:
        return None
    diffs = [s for s in ("config", "options", "services") if strings.get(s) != trans.get(s)]
    sections = ", ".join(diffs) if diffs else "unknown"
    return (
        f"  {name}: content differs from strings.json ({sections})\n"
        f"    Fix: cp {_STRINGS} {_TRANSLATIONS_DIR / name}"
    )


def _check_key_structure(strings_keys: set[str], trans: dict[str, Any], name: str) -> list[str]:
    """Check that a language file has the same key structure as strings.json."""
    errors: list[str] = []
    trans_keys = _extract_keys(trans)
    missing = strings_keys - trans_keys
    extra = trans_keys - strings_keys

    if missing:
        top = sorted({k.split(".")[0] + "." + k.split(".")[1] for k in missing if "." in k})
        errors.append(f"  {name}: missing {len(missing)} keys (e.g., {', '.join(top[:3])})")
    if extra:
        top = sorted({k.split(".")[0] + "." + k.split(".")[1] for k in extra if "." in k})
        errors.append(f"  {name}: {len(extra)} extra keys (e.g., {', '.join(top[:3])})")
    return errors


def main() -> int:
    """Compare strings.json against all translation files."""
    if not _STRINGS.is_file():
        print(f"SKIP: {_STRINGS} not found")
        return 0

    strings = json.loads(_STRINGS.read_text(encoding="utf-8"))
    strings_keys = _extract_keys(strings)
    errors: list[str] = []

    if not _TRANSLATIONS_DIR.is_dir():
        print(f"SKIP: {_TRANSLATIONS_DIR} not found")
        return 0

    for trans_path in sorted(_TRANSLATIONS_DIR.glob("*.json")):
        trans = json.loads(trans_path.read_text(encoding="utf-8"))
        if trans_path.stem == "en":
            err = _check_en_exact(strings, trans, trans_path.name)
            if err:
                errors.append(err)
        else:
            errors.extend(_check_key_structure(strings_keys, trans, trans_path.name))

    if errors:
        print("FAIL: translation files out of sync with strings.json:")
        for e in errors:
            print(e)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
