"""Tests for resolve_symbol_rate_unit(): label first, DOCSIS magnitude fallback.

Table-driven: each case is the observed samples plus any unit the header
declared, and the unit, scale and conflict the resolver must return.
"""

from __future__ import annotations

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.analysis.mapping.symbol_rate import (
    resolve_symbol_rate_unit,
    symbol_rate_field_type,
)

# =============================================================================
# resolve_symbol_rate_unit test data
# =============================================================================
#
# ┌──────────────────────────────────────┬──────────────┬──────────────┬───────┬──────────┬─────────────────────────┐
# │ samples                              │ declared     │ unit         │ scale │ conflict │ description             │
# ├──────────────────────────────────────┼──────────────┼──────────────┼───────┼──────────┼─────────────────────────┤
# │ ["5120", "2560"]                     │ "Ksym/sec"   │ "Ksym/sec"   │ 1000  │ no       │ header label            │
# │ ["5120 Ksym/sec", "2560 Ksym/sec"]   │ ""           │ "Ksym/sec"   │ 1000  │ no       │ suffix on the values    │
# │ ["5120 kSym/s"]                      │ ""           │ "kSym/s"     │ 1000  │ no       │ suffix, other spelling  │
# │ ["5120", "2560"]                     │ ""           │ ""           │ 1000  │ no       │ bare ksym magnitude     │
# │ ["0", "5120"]                        │ ""           │ ""           │ 1000  │ no       │ zero placeholder skip   │
# │ ["5120000", "2560000"]               │ ""           │ ""           │ None  │ no       │ already Sym/s           │
# │ ["0", "0"]                           │ ""           │ ""           │ None  │ no       │ no evidence             │
# │ []                                   │ ""           │ ""           │ None  │ no       │ no samples              │
# │ ["5120000"]                          │ "Ksym/sec"   │ "Ksym/sec"   │ None  │ yes      │ label vs magnitude      │
# │ ["5120", "5120000"]                  │ ""           │ ""           │ None  │ yes      │ mixed magnitudes        │
# │ ["5.120 Msym/sec", "2.560 Msym/sec"] │ ""           │ "Msym/sec"   │ 1e6   │ no       │ Msym suffix on values   │
# │ ["5.120", "2.560"]                   │ "Msym/sec"   │ "Msym/sec"   │ 1e6   │ no       │ Msym header label       │
# │ ["5.120 Msym/s"]                     │ ""           │ "Msym/s"     │ 1e6   │ no       │ Msym suffix, spelling   │
# │ ["5120000"]                          │ "Msym/sec"   │ "Msym/sec"   │ None  │ yes      │ Msym label vs Sym/s     │
# └──────────────────────────────────────┴──────────────┴──────────────┴───────┴──────────┴─────────────────────────┘
#
# fmt: off
RESOLVE_CASES = [
    # (samples,                           declared,    unit,        scale, conflict, id)
    (["5120", "2560"],                    "Ksym/sec",  "Ksym/sec",  1000,  False,    "header-label"),
    (["5120 Ksym/sec", "2560 Ksym/sec"],  "",          "Ksym/sec",  1000,  False,    "value-suffix"),
    (["5120 kSym/s"],                     "",          "kSym/s",    1000,  False,    "value-suffix-spelling"),
    (["5120", "2560"],                    "",          "",          1000,  False,    "bare-ksym"),
    (["0", "5120"],                       "",          "",          1000,  False,    "zero-placeholder"),
    (["5120000", "2560000"],              "",          "",          None,  False,    "already-sym-per-s"),
    (["0", "0"],                          "",          "",          None,  False,    "no-evidence"),
    ([],                                  "",          "",          None,  False,    "no-samples"),
    (["5120000"],                         "Ksym/sec",  "Ksym/sec",  None,  True,     "label-contradicts-magnitude"),
    (["5120", "5120000"],                 "",          "",          None,  True,     "mixed-magnitudes"),
    (["5.120 Msym/sec", "2.560 Msym/sec"], "",         "Msym/sec",  1_000_000, False, "msym-value-suffix"),
    (["5.120", "2.560"],                  "Msym/sec",  "Msym/sec",  1_000_000, False, "msym-header-label"),
    (["5.120 Msym/s"],                    "",          "Msym/s",    1_000_000, False, "msym-suffix-spelling"),
    (["5120000"],                         "Msym/sec",  "Msym/sec",  None,  True,     "msym-label-vs-magnitude"),
]
# fmt: on


@pytest.mark.parametrize(
    "samples,declared,unit,scale,conflict",
    [c[:5] for c in RESOLVE_CASES],
    ids=[c[5] for c in RESOLVE_CASES],
)
def test_resolve_symbol_rate_unit(
    samples: list[str],
    declared: str,
    unit: str,
    scale: int | None,
    conflict: bool,
) -> None:
    """Label evidence wins; magnitude decides bare numbers; disagreement is a conflict, not a guess."""
    result = resolve_symbol_rate_unit(samples, declared)
    assert result.unit == unit
    assert result.scale == scale
    assert bool(result.conflict) == conflict


# ┌─────────────────┬───────────┬───────────┬─────────────────────────────────────┐
# │ registry type   │ scale     │ type      │ description                         │
# ├─────────────────┼───────────┼───────────┼─────────────────────────────────────┤
# │ "integer"       │ 1_000_000 │ "float"   │ Msym/s prints "5.120"; int truncates │
# │ "integer"       │ 1000      │ "integer" │ ksym/s prints whole numbers          │
# │ "integer"       │ None      │ "integer" │ already Sym/s                        │
# └─────────────────┴───────────┴───────────┴─────────────────────────────────────┘
TYPE_CASES = [
    # (registry type, scale,     expected,  id)
    ("integer", 1_000_000, "float", "msym-keeps-fraction"),
    ("integer", 1000, "integer", "ksym-whole-numbers"),
    ("integer", None, "integer", "already-sym-per-s"),
]


@pytest.mark.parametrize(
    "field_type,scale,expected",
    [c[:3] for c in TYPE_CASES],
    ids=[c[3] for c in TYPE_CASES],
)
def test_symbol_rate_field_type(field_type: str, scale: int | None, expected: str) -> None:
    """An Msym/s scale needs a float so the fraction survives until it is scaled."""
    assert symbol_rate_field_type(field_type, scale) == expected
