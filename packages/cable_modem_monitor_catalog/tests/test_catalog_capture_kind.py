"""Tests for the audit's capture-kind column: ``_capture_kind`` reads the HAR creator.

Vocabulary is MODEM_INTAKE_WORKFLOW.md § Assembled fixtures. An assembled
fixture takes the label of its weakest part, so a composite built on a
synthetic base reads ``synthetic``, not ``hybrid``.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_GENERATOR = Path(__file__).resolve().parents[1] / "scripts" / "generate_catalog_index.py"
_spec = importlib.util.spec_from_file_location("generate_catalog_index", _GENERATOR)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
_capture_kind = _module._capture_kind

# ┌───────────────────────────────────────────────────┬───────────────┬──────────────────────────────┐
# │ creator name                                      │ kind          │ description                  │
# ├───────────────────────────────────────────────────┼───────────────┼──────────────────────────────┤
# │ har-capture                                       │ real          │ capture tool                 │
# │ Firefox                                           │ real          │ browser export               │
# │ fixtures_to_har (synthetic)                       │ synthetic     │ synthetic producer           │
# │ composite (hybrid of two same-device captures)    │ hybrid        │ real captures, same unit     │
# │ composite (synthetic + har-capture)               │ synthetic     │ synthetic base wins          │
# │ reconstructed (xb7 template + diagnostics)        │ reconstructed │ sibling template             │
# │ (empty)                                           │ generated     │ no recorded producer         │
# └───────────────────────────────────────────────────┴───────────────┴──────────────────────────────┘
#
# fmt: off
CREATOR_CASES = [
    # (creator,                                          kind,            id)
    ("har-capture",                                      "real",          "capture_tool"),
    ("Firefox",                                          "real",          "browser_export"),
    ("fixtures_to_har (synthetic)",                      "synthetic",     "synthetic_producer"),
    ("composite (hybrid of two same-device captures)",   "hybrid",        "same_unit_composite"),
    ("composite (synthetic + har-capture)",              "synthetic",     "synthetic_base_composite"),
    ("reconstructed (xb7 template + diagnostics)",       "reconstructed", "reconstruction"),
    ("",                                                 "generated",     "no_producer"),
]
# fmt: on


@pytest.mark.parametrize("creator,kind", [c[:2] for c in CREATOR_CASES], ids=[c[2] for c in CREATOR_CASES])
def test_capture_kind_from_creator(tmp_path: Path, creator: str, kind: str) -> None:
    """The creator name maps to the audit's capture-kind label."""
    har = tmp_path / "modem.har"
    har.write_text(json.dumps({"log": {"version": "1.2", "creator": {"name": creator}, "entries": []}}))
    assert _capture_kind(har) == kind
