"""Pattern tests for the README generator's variant-title disambiguation (#124).

These exercise ``build_model_display_names`` with synthetic variant rows, not
real catalog modems — per-modem correctness is covered by the HAR + golden
files. The rule under test: hardware version is never the primary qualifier;
it appears only to break a tie that the variant name and auth strategy cannot.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

# generate_catalog_index lives in the catalog package's scripts/ directory, not
# as an installed module, so load it by file path. This keeps a clean top-level
# import with no sys.path mutation and no import-resolution suppressions.
_GENERATOR = Path(__file__).resolve().parents[1] / "scripts" / "generate_catalog_index.py"
_spec = importlib.util.spec_from_file_location("generate_catalog_index", _GENERATOR)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
build_model_display_names = _module.build_model_display_names


def _row(model: str, *, variant: str | None = None, auth: str = "none", hw: str | None = None) -> dict:
    return {"model": model, "variant_name": variant, "auth_strategy": auth, "hw_version": hw}


# Each case: a set of rows that share a model, and the title expected per row.
DISPLAY_CASES = [
    pytest.param(
        [_row("A", auth="none")],
        ["A"],
        id="single_variant_no_qualifier",
    ),
    pytest.param(
        [_row("A", auth="none", hw="v2")],
        ["A"],
        id="single_variant_hw_version_not_shown",
    ),
    pytest.param(
        [_row("A", variant="body-token", auth="url_token")],
        ["A (body-token)"],
        id="variant_name_is_the_qualifier",
    ),
    pytest.param(
        [_row("A", auth="none"), _row("A", auth="hnap"), _row("A", auth="form_cbn")],
        ["A (No Authentication)", "A (HNAP)", "A (Form Login CBN)"],
        id="collision_distinct_auth_uses_auth_label",
    ),
    pytest.param(
        [_row("A", auth="hnap"), _row("A", auth="hnap", hw="v2"), _row("A", auth="hnap", hw="v3")],
        ["A", "A (v2)", "A (v3)"],
        id="collision_same_auth_uses_hw_primary_stays_bare",
    ),
]


@pytest.mark.parametrize("rows,expected", DISPLAY_CASES)
def test_build_model_display_names(rows: list[dict], expected: list[str]) -> None:
    names = build_model_display_names(rows)
    assert [names[id(r)] for r in rows] == expected
