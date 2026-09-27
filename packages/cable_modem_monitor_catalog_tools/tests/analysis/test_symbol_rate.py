"""Tests for resolve_symbol_rate_unit(): label first, DOCSIS magnitude fallback.

Table-driven: each case is the observed samples plus any unit the header
declared, and the unit, scale and conflict the resolver must return.
"""

from __future__ import annotations

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.analysis.mapping.symbol_rate import (
    resolve_symbol_rate_unit,
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
