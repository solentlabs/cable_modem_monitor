"""Intake regression machinery: results and trend scorecard.

The regression script (scripts/intake_pipeline_regression.py) supplies
discovery, pipeline stages, and printing; the reusable pieces (result
classification and the trend scorecard) live here so they are
unit-tested.
"""

from .results import STATUS_SEVERITY, ModemResult, fleet_accuracy, result_key, result_status
from .scorecard import build_scorecard

__all__ = [
    "STATUS_SEVERITY",
    "ModemResult",
    "build_scorecard",
    "fleet_accuracy",
    "result_key",
    "result_status",
]
