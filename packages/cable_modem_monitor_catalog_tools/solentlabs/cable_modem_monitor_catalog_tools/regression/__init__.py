"""Intake regression machinery: results, baseline ratchet, scorecard.

The regression script (scripts/intake_pipeline_regression.py) supplies
discovery, pipeline stages, and printing; the gate logic lives here so
it is unit-tested.
"""

from .baseline import (
    BaselineEntry,
    compare_baseline,
    entries_from_results,
    load_baseline,
    save_baseline,
)
from .results import STATUS_SEVERITY, ModemResult, fleet_accuracy, result_key, result_status
from .scorecard import build_scorecard

__all__ = [
    "STATUS_SEVERITY",
    "BaselineEntry",
    "ModemResult",
    "build_scorecard",
    "compare_baseline",
    "entries_from_results",
    "fleet_accuracy",
    "load_baseline",
    "result_key",
    "result_status",
    "save_baseline",
]
