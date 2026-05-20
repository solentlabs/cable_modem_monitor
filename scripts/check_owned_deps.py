#!/usr/bin/env python3
"""Report outdated dependencies we declare directly.

Filters out the transitive HA and pytest-homeassistant-custom-component
dependency tree — those versions are controlled by upstream, not by us.
Only packages named in our requirements files and pyproject.toml
[project.dependencies] blocks are reported.

Exit 0 always — informational, not a build gate.
"""

import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).parent.parent

_INTERNAL_PREFIX = "solentlabs-"


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]", "-", name).lower()


def _names_from_requirements(path: Path) -> set[str]:
    names: set[str] = set()
    if not path.exists():
        return names
    for raw in path.read_text().splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_.-]+)", stripped)
        if m:
            names.add(_normalize(m.group(1)))
    return names


def _names_from_pyproject(path: Path) -> set[str]:
    names: set[str] = set()
    if not path.exists():
        return names
    try:
        data = tomllib.loads(path.read_text())
    except Exception:
        return names
    for dep in data.get("project", {}).get("dependencies", []):
        m = re.match(r"^([A-Za-z0-9_.-]+)", dep)
        if m:
            name = _normalize(m.group(1))
            if not name.startswith(_INTERNAL_PREFIX):
                names.add(name)
    return names


def _owned_packages() -> set[str]:
    owned: set[str] = set()
    owned |= _names_from_requirements(ROOT / "requirements-dev.txt")
    owned |= _names_from_requirements(ROOT / "tests" / "requirements.txt")
    for pyproject in ROOT.rglob("pyproject.toml"):
        owned |= _names_from_pyproject(pyproject)
    return owned


def main() -> int:
    owned = _owned_packages()

    result = subprocess.run(
        [sys.executable, "-m", "pip", "list", "--outdated", "--format=json"],
        capture_output=True,
        text=True,
    )
    try:
        all_outdated: list[dict[str, str]] = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return 0

    ours = [p for p in all_outdated if _normalize(p["name"]) in owned]

    if not ours:
        print("  All declared dependencies are current.")
        return 0

    noun = "dependency" if len(ours) == 1 else "dependencies"
    verb = "has" if len(ours) == 1 else "have"
    print(f"  {len(ours)} declared {noun} {verb} newer versions available:")
    w = max(len(p["name"]) for p in ours)
    print(f"  {'Package':<{w}}  {'Installed':<15}  Latest")
    print(f"  {'-' * w}  {'-' * 15}  ------")
    for p in sorted(ours, key=lambda x: x["name"].lower()):
        print(f"  {p['name']:<{w}}  {p['version']:<15}  {p['latest_version']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
