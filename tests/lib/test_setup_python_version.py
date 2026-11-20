"""Tests for scripts/setup.py's Python version gate.

setup.py must honor both ends of pyproject's requires-python: a Python
above the ceiling resolves a different Home Assistant line from the
unbounded dev requirement and type-checks against the wrong API.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.fixture_helpers import load_script

_mod = load_script("scripts/setup.py")

# ┌──────────────────────────────────────────┬────────────────────┬──────────────────────────┐
# │ requires-python                          │ (floor, ceiling)   │ description              │
# ├──────────────────────────────────────────┼────────────────────┼──────────────────────────┤
# │ ">=3.12,<3.13"                           │ (3,12), (3,13)     │ floor and ceiling        │
# │ ">=3.12, <3.14"                          │ (3,12), (3,14)     │ space after comma        │
# │ ">=3.12"                                 │ (3,12), None       │ floor only               │
# │ (missing)                                │ (3,11), None       │ fallback                 │
# └──────────────────────────────────────────┴────────────────────┴──────────────────────────┘
#
# fmt: off
BOUNDS_CASES = [
    # (pyproject line,                         floor,    ceiling, id)
    ('requires-python = ">=3.12,<3.13"',      (3, 12),  (3, 13), "floor_and_ceiling"),
    ('requires-python = ">=3.12, <3.14"',     (3, 12),  (3, 14), "space_after_comma"),
    ('requires-python = ">=3.12"',            (3, 12),  None,    "floor_only"),
    ("",                                      (3, 11),  None,    "missing"),
]
# fmt: on


@pytest.mark.parametrize(
    "line,floor,ceiling",
    [c[:3] for c in BOUNDS_CASES],
    ids=[c[3] for c in BOUNDS_CASES],
)
def test_python_version_bounds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    line: str,
    floor: tuple[int, int],
    ceiling: tuple[int, int] | None,
) -> None:
    """Both ends of requires-python are read; a missing spec falls back to 3.11."""
    (tmp_path / "pyproject.toml").write_text(f"[project]\n{line}\n")
    monkeypatch.chdir(tmp_path)
    assert _mod.get_python_version_bounds() == (floor, ceiling)


# ┌──────────┬─────────┬──────────┬──────────┬──────────────────────┐
# │ current  │ floor   │ ceiling  │ ok       │ description          │
# ├──────────┼─────────┼──────────┼──────────┼──────────────────────┤
# │ 3.12     │ 3.12    │ 3.13     │ yes      │ inside the range     │
# │ 3.11     │ 3.12    │ 3.13     │ no       │ below the floor      │
# │ 3.13     │ 3.12    │ 3.13     │ no       │ at the ceiling       │
# │ 3.14     │ 3.12    │ 3.13     │ no       │ above the ceiling    │
# │ 3.14     │ 3.12    │ —        │ yes      │ no ceiling declared  │
# └──────────┴─────────┴──────────┴──────────┴──────────────────────┘
#
# fmt: off
ACCEPT_CASES = [
    # (current,  floor,    ceiling,  ok,    id)
    ((3, 12),    (3, 12),  (3, 13),  True,  "inside"),
    ((3, 11),    (3, 12),  (3, 13),  False, "below_floor"),
    ((3, 13),    (3, 12),  (3, 13),  False, "at_ceiling"),
    ((3, 14),    (3, 12),  (3, 13),  False, "above_ceiling"),
    ((3, 14),    (3, 12),  None,     True,  "no_ceiling"),
]
# fmt: on


@pytest.mark.parametrize(
    "current,floor,ceiling,ok",
    [c[:4] for c in ACCEPT_CASES],
    ids=[c[4] for c in ACCEPT_CASES],
)
def test_python_version_ok(
    current: tuple[int, int],
    floor: tuple[int, int],
    ceiling: tuple[int, int] | None,
    ok: bool,
) -> None:
    """A Python is accepted when floor <= version < ceiling."""
    assert _mod.python_version_ok(current, floor, ceiling) is ok
