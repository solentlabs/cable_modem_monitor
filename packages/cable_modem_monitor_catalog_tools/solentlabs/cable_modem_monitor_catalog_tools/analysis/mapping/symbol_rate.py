"""symbol_rate unit resolution: firmware label first, DOCSIS magnitude fallback.

Core stores symbol_rate in Sym/s (PARSING_SPEC § ATDMA Upstream). Firmware
reports ksym/s, labelled or as a bare number, or Msym/s with a printed label,
so the generator decides the parser.yaml ``unit``/``scale`` once, at intake,
from the captured samples.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from solentlabs.cable_modem_monitor_core.spec_conformance import MIN_SYMBOL_RATE_SYM_PER_S

from ...validation.har_utils import WARNING_PREFIX

# ksym/s spellings observed in the fleet: "Ksym/sec", "KSym/sec", "kSym/s".
_KSYM_PATTERN = r"(?i:k\s*sym\s*/\s*s(?:ec)?)"
_KSYM_UNIT = re.compile(_KSYM_PATTERN)
# Msym/s spelling observed in the fleet: "Msym/sec". The capital M is required:
# a lowercase "msym" would read as milli.
_MSYM_PATTERN = r"M(?i:\s*sym\s*/\s*s(?:ec)?)"
_MSYM_UNIT = re.compile(_MSYM_PATTERN)
_UNIT_SUFFIX = re.compile(r"^\s*[\d.,]+\s*(" + _KSYM_PATTERN + "|" + _MSYM_PATTERN + r")\s*$")
_NUMBER = re.compile(r"^\s*([\d.,]+)")


_MSYM_SCALE = 1_000_000


@dataclass(frozen=True)
class SymbolRateUnit:
    """The unit to strip, the scale to Sym/s, and any label/magnitude conflict."""

    unit: str
    scale: int | None
    conflict: str = ""


def resolve_symbol_rate_unit(samples: list[str], declared_unit: str = "") -> SymbolRateUnit:
    """Resolve a symbol_rate mapping's unit and scale from its samples."""
    # 1. Label: a unit the header declared, else a ksym or Msym suffix printed on the values.
    unit = declared_unit
    if not unit:
        for sample in samples:
            match = _UNIT_SUFFIX.match(sample)
            if match:
                unit = match.group(1)
                break
    labelled_scale = _labelled_scale(unit)

    # 2. Magnitude: DOCSIS upstream rates are 160 to 5120 ksym/s, so ksym and
    # Sym/s values never overlap. Zero placeholders carry no evidence.
    values = [v for v in (_parse_number(s) for s in samples) if v]
    below = [v < MIN_SYMBOL_RATE_SYM_PER_S for v in values]
    magnitude = "none" if not values else "ksym" if all(below) else "sym" if not any(below) else "mixed"

    # 3. Agreement sets the scale; disagreement is reported, never resolved.
    conflicts = magnitude == "mixed" or (labelled_scale is not None and magnitude == "sym")
    if conflicts:
        return SymbolRateUnit(
            unit=unit,
            scale=None,
            conflict=(
                f"symbol_rate: unit {unit or '(none)'!r} and sample values {sorted(set(values))} disagree "
                f"(ksym/s is below {MIN_SYMBOL_RATE_SYM_PER_S}); set unit and scale by hand"
            ),
        )
    if labelled_scale is not None:
        return SymbolRateUnit(unit=unit, scale=labelled_scale)
    if magnitude == "ksym":
        return SymbolRateUnit(unit=unit, scale=1000)
    return SymbolRateUnit(unit=unit, scale=None)


def _labelled_scale(unit: str) -> int | None:
    """Scale to Sym/s for a ksym or Msym unit label, or None when the label names neither."""
    if not unit:
        return None
    if _KSYM_UNIT.fullmatch(unit.strip()):
        return 1000
    if _MSYM_UNIT.fullmatch(unit.strip()):
        return _MSYM_SCALE
    return None


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


def symbol_rate_field_type(field_type: str, scale: int | None) -> str:
    """Float for an Msym/s scale: its values print fractions ("5.120") that an integer would truncate."""
    return "float" if scale == _MSYM_SCALE else field_type
