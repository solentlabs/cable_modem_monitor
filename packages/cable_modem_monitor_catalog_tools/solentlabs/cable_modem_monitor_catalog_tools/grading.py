"""Shared grading taxonomy for intake capability dimensions.

Grades compare what the deterministic pipeline produced against what
the catalog committed, per dimension (actions today, auth next). The
taxonomy is dimension-agnostic so the regression baseline can ratchet
every dimension with the same severity ordering.
"""

from __future__ import annotations

from dataclasses import dataclass

# Ratchet ordering for baseline comparison: a grade moving to a higher
# severity is a regression. pipeline_only and committed_only tie — they
# are different findings, not better or worse than each other.
GRADE_SEVERITY: dict[str, int] = {
    "match": 0,
    "partial": 1,
    "pipeline_only": 2,
    "committed_only": 2,
    "mismatch": 3,
}


@dataclass(frozen=True)
class Grade:
    """Grade for one item: status plus a human-readable reason."""

    status: str  # key of GRADE_SEVERITY
    detail: str = ""
