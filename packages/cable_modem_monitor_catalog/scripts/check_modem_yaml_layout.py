#!/usr/bin/env python3
"""Check every catalog modem*.yaml and parser.yaml against MODEM_YAML_SPEC § Layout; --fix rewrites spacing."""

from __future__ import annotations

import sys
from pathlib import Path

from solentlabs.cable_modem_monitor_core.validation.layout import (
    IDENTITY_KEYS,
    MODEM_KEY_ORDER,
    PARSER_KEY_ORDER,
    apply_section_spacing,
    order_errors,
)

ROOT = Path(__file__).resolve().parents[1] / "solentlabs" / "cable_modem_monitor_catalog" / "modems"


def main() -> int:
    """Report layout errors; with --fix, repair spacing (key order is a hand edit)."""
    fix = "--fix" in sys.argv
    failed = 0
    fixed = 0
    targets = [(p, MODEM_KEY_ORDER, IDENTITY_KEYS) for p in ROOT.rglob("modem*.yaml")]
    targets += [(p, PARSER_KEY_ORDER, frozenset[str]()) for p in ROOT.rglob("parser.yaml")]
    for path, order, contiguous in sorted(targets, key=lambda t: t[0]):
        text = path.read_text()
        rel = path.relative_to(ROOT)
        spaced = apply_section_spacing(text, contiguous=contiguous)
        errors = order_errors(text, order)
        if spaced != text:
            if fix:
                path.write_text(spaced)
                fixed += 1
                print(f"  fixed spacing: {rel}")
            else:
                errors.append("section spacing differs from the spec layout")
        for error in errors:
            failed += 1
            print(f"  {rel}: {error}")
    if fix:
        print(f"\n{fixed} file(s) respaced; {failed} order error(s) need a hand edit")
    else:
        print(f"\n{failed} layout error(s)" + ("; run with --fix to repair spacing" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
