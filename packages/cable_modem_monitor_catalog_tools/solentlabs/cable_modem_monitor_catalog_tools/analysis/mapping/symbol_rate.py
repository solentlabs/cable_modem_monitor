"""symbol_rate unit resolution: firmware label first, DOCSIS magnitude fallback.

Core stores symbol_rate in Sym/s (PARSING_SPEC § ATDMA Upstream). Firmware
reports ksym/s, labelled or as a bare number, so the generator decides the
parser.yaml ``unit``/``scale`` once, at intake, from the captured samples.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from solentlabs.cable_modem_monitor_core.spec_conformance import MIN_SYMBOL_RATE_SYM_PER_S

from ...validation.har_utils import WARNING_PREFIX

# ksym/s spellings observed in the fleet: "Ksym/sec", "KSym/sec", "kSym/s".
_KSYM_UNIT = re.compile(r"k\s*sym\s*/\s*s(?:ec)?", re.IGNORECASE)
_KSYM_SUFFIX = re.compile(r"^\s*[\d.,]+\s*(" + _KSYM_UNIT.pattern + r")\s*$", re.IGNORECASE)
_NUMBER = re.compile(r"^\s*([\d.,]+)")


@dataclass(frozen=True)
class SymbolRateUnit:
    """The unit to strip, the scale to Sym/s, and any label/magnitude conflict."""

    unit: str
    scale: int | None
    conflict: str = ""


def resolve_symbol_rate_unit(samples: list[str], declared_unit: str = "") -> SymbolRateUnit:
    """Resolve a symbol_rate mapping's unit and scale from its samples."""
    # 1. Label: a unit the header declared, else a ksym suffix printed on the values.
    unit = declared_unit
    if not unit:
        for sample in samples:
            match = _KSYM_SUFFIX.match(sample)
            if match:
                unit = match.group(1)
                break
    labelled_ksym = bool(unit) and _KSYM_UNIT.fullmatch(unit.strip()) is not None

    # 2. Magnitude: DOCSIS upstream rates are 160 to 5120 ksym/s, so ksym and
    # Sym/s values never overlap. Zero placeholders carry no evidence.
    values = [v for v in (_parse_number(s) for s in samples) if v]
    below = [v < MIN_SYMBOL_RATE_SYM_PER_S for v in values]
    magnitude = "none" if not values else "ksym" if all(below) else "sym" if not any(below) else "mixed"

    # 3. Agreement sets the scale; disagreement is reported, never resolved.
    conflicts = magnitude == "mixed" or (labelled_ksym and magnitude == "sym")
    if conflicts:
        return SymbolRateUnit(
            unit=unit,
            scale=None,
            conflict=(
                f"symbol_rate: unit {unit or '(none)'!r} and sample values {sorted(set(values))} disagree "
                f"(ksym/s is below {MIN_SYMBOL_RATE_SYM_PER_S}); set unit and scale by hand"
            ),
        )
    if labelled_ksym or magnitude == "ksym":
        return SymbolRateUnit(unit=unit, scale=1000)
    return SymbolRateUnit(unit=unit, scale=None)


def _parse_number(sample: str) -> float:
    """Leading number of a sample, or 0 when there is none."""
    match = _NUMBER.match(sample)
    if not match:
        return 0
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return 0


def symbol_rate_unit_and_scale(samples: list[str], declared_unit: str, warnings: list[str]) -> tuple[str, int | None]:
    """Resolve unit and scale for a symbol_rate mapping, reporting a conflict as a warning."""
    resolved = resolve_symbol_rate_unit(samples, declared_unit)
    if resolved.conflict:
        warnings.append(f"{WARNING_PREFIX} {resolved.conflict}")
    return resolved.unit, resolved.scale
