#!/usr/bin/env python3
"""Report declared versions that exclude the latest release, and known CVEs.

Runs at the end of ``make validate-ci``, so it is seen before every push.
It lists only what needs a commit:

- a Python spec (pin or cap) in a requirements file, a pyproject.toml or a
  workflow ``pip install`` line that excludes the latest PyPI release; a
  floor that already permits the latest is not listed, and neither is a
  latest release HA cannot install (see ``ha_supports``)
- a pre-commit hook ``rev:`` behind the repository's latest stable tag
- a GitHub Actions ``uses: owner/repo@vN`` ref behind the latest tag, at the
  ref's precision (``@v4`` compares majors)
- a dev container feature ``ghcr.io/...:N`` behind the latest tag, at the
  pin's precision

It also lists known vulnerabilities (OSV) in our exact ``==`` pins, the only
versions we fix; a floor installs the latest release, and the local venv's
versions are set by the HA test environment, not by us. Bumps go through the
ha-safe-deps-bump skill, gated by validate-ci and ha-compat-check.

Exit 0 always: informational, not a build gate. A check that cannot reach
the network is counted as skipped, not reported as current.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tomllib
import urllib.request
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

import yaml
from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

ROOT = Path(__file__).parent.parent

_INTERNAL_PREFIX = "solentlabs-"
_TIMEOUT = 10
_REQUIREMENTS = ("requirements-dev.txt", "requirements-security.txt", "tests/requirements.txt")
_REQ_LINE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)(?:\[[^\]]*\])?\s*(.*)$")
_PIP_TOKEN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)((?:==|~=|>=|<=|<|>|!=).+)$")
_ACTION_REF = re.compile(r"uses:\s*([\w.-]+/[\w.-]+)(?:/[\w./-]+)?@(v\d+(?:\.\d+)*)\s*$")
_FEATURE_PIN = re.compile(r"\"ghcr\.io/([\w./-]+):(\d+(?:\.\d+)*)\"")


@dataclass(frozen=True)
class Declared:
    """One declared Python requirement and the file it lives in."""

    where: str
    name: str
    spec: str


@dataclass(frozen=True)
class Pinned:
    """A version-pinned non-Python dependency (hook, action or feature)."""

    kind: str
    where: str
    source: str
    pin: str


@dataclass(frozen=True)
class Finding:
    """A declared version that excludes the latest release."""

    where: str
    name: str
    declared: str
    latest: str


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _parse_requirement(text: str) -> tuple[str, str] | None:
    """Split a requirement string into (normalized name, spec), dropping extras, markers and comments."""
    text = re.split(r"(?:^|\s)#", text, maxsplit=1)[0].split(";", 1)[0].strip()
    m = _REQ_LINE.match(text)
    if not m:
        return None
    return _normalize(m.group(1)), m.group(2).replace(" ", "")


def _from_requirements(path: Path, where: str) -> list[Declared]:
    out: list[Declared] = []
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith(("#", "-")):
            continue
        parsed = _parse_requirement(stripped)
        if parsed:
            out.append(Declared(where, *parsed))
    return out


def _from_pyproject(path: Path, where: str) -> list[Declared]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    project = data.get("project", {})
    groups: list[list[str]] = [project.get("dependencies", [])]
    groups += project.get("optional-dependencies", {}).values()
    groups += data.get("dependency-groups", {}).values()
    out: list[Declared] = []
    for group in groups:
        for dep in group:
            parsed = _parse_requirement(dep) if isinstance(dep, str) else None
            if parsed and not parsed[0].startswith(_INTERNAL_PREFIX):
                out.append(Declared(where, *parsed))
    return out


def _from_workflow(text: str, where: str) -> list[Declared]:
    """Specs on ``pip install`` lines; bare names carry no version and are skipped."""
    out: list[Declared] = []
    for line in text.splitlines():
        if "pip install" not in line:
            continue
        for token in line.split("pip install", 1)[1].split():
            m = _PIP_TOKEN.match(token.strip("\"'"))
            if m:
                out.append(Declared(where, _normalize(m.group(1)), m.group(2)))
    return out


def declared_python(root: Path) -> list[Declared]:
    """Every Python requirement we declare, with where it is declared."""
    out: list[Declared] = []
    for rel in _REQUIREMENTS:
        out += _from_requirements(root / rel, rel)
    for path in [root / "pyproject.toml", *sorted(root.glob("packages/*/pyproject.toml"))]:
        if path.exists():
            out += _from_pyproject(path, str(path.relative_to(root)))
    for path in sorted(root.glob(".github/workflows/*.y*ml")):
        out += _from_workflow(path.read_text(encoding="utf-8"), str(path.relative_to(root)))
    return out


def pinned_other(root: Path) -> list[Pinned]:
    """Pre-commit hook revs, GitHub Actions refs and dev container feature pins."""
    out: list[Pinned] = []
    precommit = root / ".pre-commit-config.yaml"
    if precommit.exists():
        config = yaml.safe_load(precommit.read_text(encoding="utf-8")) or {}
        for repo in config.get("repos", []):
            url = str(repo.get("repo", ""))
            if url.startswith("https://github.com/") and "rev" in repo:
                out.append(Pinned("hook", precommit.name, url.removeprefix("https://github.com/"), str(repo["rev"])))
    for path in sorted(root.glob(".github/workflows/*.y*ml")):
        for line in path.read_text(encoding="utf-8").splitlines():
            m = _ACTION_REF.search(line.strip())
            if m:
                out.append(Pinned("action", str(path.relative_to(root)), m.group(1), m.group(2)))
    devcontainer = root / ".devcontainer" / "devcontainer.json"
    if devcontainer.exists():
        for m in _FEATURE_PIN.finditer(devcontainer.read_text(encoding="utf-8")):
            out.append(Pinned("feature", ".devcontainer/devcontainer.json", m.group(1), m.group(2)))
    return list(dict.fromkeys(out))


def _version(text: str) -> Version | None:
    try:
        return Version(text.removeprefix("v"))
    except InvalidVersion:
        return None


def latest_stable(tags: Iterable[str]) -> str | None:
    """The highest non-prerelease tag, returned as spelled."""
    best: tuple[Version, str] | None = None
    for tag in tags:
        v = _version(tag)
        if v is not None and not v.is_prerelease and not v.is_devrelease and (best is None or v > best[0]):
            best = (v, tag)
    return best[1] if best else None


def pin_behind(pin: str, latest: str) -> bool:
    """Whether ``latest`` is newer than ``pin`` at the pin's precision (``v4`` compares majors only)."""
    p, n = _version(pin), _version(latest)
    if p is None or n is None:
        return False
    width = len(p.release)
    if width < len(n.release):
        return n.release[:width] > p.release
    return n > p


def spec_excludes(spec: str, latest: str) -> bool:
    """Whether a non-empty spec rules out the latest release."""
    if not spec:
        return False
    try:
        return not SpecifierSet(spec).contains(Version(latest), prereleases=True)
    except (InvalidSpecifier, InvalidVersion):
        return False


@dataclass(frozen=True)
class Release:
    """A package's latest PyPI release and the requirements it declares."""

    version: str
    requires: tuple[str, ...] = ()


@dataclass(frozen=True)
class HaEnv:
    """HA's package_constraints.txt specs, and the versions installed under them."""

    specs: dict[str, SpecifierSet]
    installed: dict[str, str]


def ha_supports(name: str, release: Release, ha: HaEnv) -> bool:
    """Whether HA can install ``release``: HA's spec admits it, and its requirements admit HA's versions.

    A requirement on a package HA constrains is checked against the version
    installed under HA's constraints (e.g. types-requests 2.33 needs
    urllib3>=2 while HA 2025.1 holds urllib3<2).
    """
    own = ha.specs.get(name)
    if own is not None and not own.contains(release.version, prereleases=True):
        return False
    for text in release.requires:
        try:
            req = Requirement(text)
        except InvalidRequirement:
            continue
        if req.marker is not None and not req.marker.evaluate({"extra": ""}):
            continue
        held = ha.installed.get(_normalize(req.name))
        if held is not None and not req.specifier.contains(held, prereleases=True):
            return False
    return True


def _ha_env() -> HaEnv | None:
    """HA's constraints and installed versions; None when homeassistant is not installed."""
    spec = importlib.util.find_spec("homeassistant")
    if spec is None or not spec.submodule_search_locations:
        return None
    path = Path(list(spec.submodule_search_locations)[0]) / "package_constraints.txt"
    if not path.exists():
        return None
    specs: dict[str, SpecifierSet] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_requirement(raw.strip()) if raw.strip() and not raw.startswith("#") else None
        if parsed:
            try:
                specs[parsed[0]] = SpecifierSet(parsed[1])
            except InvalidSpecifier:
                continue
    installed: dict[str, str] = {}
    for name in specs:
        try:
            installed[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            continue
    return HaEnv(specs, installed)


# ---------------------------------------------------------------------------
# Network lookups: each returns None when unreachable, counted as skipped.
# ---------------------------------------------------------------------------


def _get_json(url: str, headers: dict[str, str] | None = None, body: bytes | None = None) -> object:
    request = urllib.request.Request(url, data=body, headers=headers or {})
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
        return json.loads(response.read())


def _pypi_latest(name: str) -> Release | None:
    try:
        data = _get_json(f"https://pypi.org/pypi/{name}/json")
    except (OSError, ValueError):
        return None
    info = data.get("info", {}) if isinstance(data, dict) else {}
    version = info.get("version")
    return Release(str(version), tuple(info.get("requires_dist") or ())) if version else None


def _git_tags(repo: str) -> list[str] | None:
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--tags", "--refs", f"https://github.com/{repo}"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT * 3,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return [line.rsplit("refs/tags/", 1)[-1] for line in result.stdout.splitlines() if "refs/tags/" in line]


def _ghcr_tags(image: str) -> list[str] | None:
    try:
        token = _get_json(f"https://ghcr.io/token?scope=repository:{image}:pull")
        if not isinstance(token, dict):
            return None
        data = _get_json(
            f"https://ghcr.io/v2/{image}/tags/list", headers={"Authorization": f"Bearer {token.get('token', '')}"}
        )
    except (OSError, ValueError):
        return None
    return [str(t) for t in data.get("tags", [])] if isinstance(data, dict) else None


def exact_pins(declared: Iterable[Declared]) -> list[tuple[str, str]]:
    """(name, version) for each single ``==`` pin, deduplicated."""
    pins = {(d.name, d.spec[2:]) for d in declared if d.spec.startswith("==") and "," not in d.spec}
    return sorted(pins)


def _osv_advisories(packages: list[tuple[str, str]]) -> dict[str, list[str]] | None:
    """Vulnerability IDs per ``name version`` for the given pinned packages."""
    if not packages:
        return {}
    queries = [{"package": {"name": n, "ecosystem": "PyPI"}, "version": v} for n, v in packages]
    try:
        data = _get_json(
            "https://api.osv.dev/v1/querybatch",
            headers={"Content-Type": "application/json"},
            body=json.dumps({"queries": queries}).encode(),
        )
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    out: dict[str, list[str]] = {}
    for (name, version), result in zip(packages, data.get("results", []), strict=False):
        ids = [str(v["id"]) for v in result.get("advisories", []) if "id" in v]
        if ids:
            out[f"{name} {version}"] = ids
    return out


def _lookup_all(keys: list[str], fetch: Callable[[str], object]) -> dict[str, object]:
    with ThreadPoolExecutor(max_workers=16) as pool:
        return dict(zip(keys, pool.map(fetch, keys), strict=True))


def short_where(places: list[str]) -> str:
    """The first two files, then a count, so a ref used across every workflow stays one line."""
    unique = list(dict.fromkeys(places))
    if len(unique) <= 2:
        return ", ".join(unique)
    return f"{unique[0]}, {unique[1]} +{len(unique) - 2} more"


def _print_table(rows: list[Finding]) -> None:
    headers = ("Name", "Declared", "Latest", "Where")
    cells = [(r.name, r.declared, r.latest, r.where) for r in rows]
    widths = [max(len(h), *(len(c[i]) for c in cells)) for i, h in enumerate(headers)]
    print("  " + "  ".join(h.ljust(w) for h, w in zip(headers, widths, strict=True)).rstrip())
    print("  " + "  ".join("-" * w for w in widths))
    for c in cells:
        print("  " + "  ".join(v.ljust(w) for v, w in zip(c, widths, strict=True)).rstrip())


def _findings(
    python: list[Declared], other: list[Pinned], pypi: dict[str, object], tags: dict[str, object], ha: HaEnv | None
) -> list[Finding]:
    """Declared versions that exclude a latest release HA can install, and pins behind their latest tag."""
    found: dict[tuple[str, str, str], list[str]] = {}
    for d in python:
        release = pypi.get(d.name)
        if not isinstance(release, Release) or not spec_excludes(d.spec, release.version):
            continue
        if ha is None or ha_supports(d.name, release, ha):
            found.setdefault((d.name, d.spec, release.version), []).append(d.where)
    for p in other:
        available = tags.get(p.source)
        latest = latest_stable(available) if isinstance(available, list) else None
        if latest and pin_behind(p.pin, latest):
            found.setdefault((p.source, p.pin, latest), []).append(p.where)
    return [Finding(short_where(w), n, s, lat) for (n, s, lat), w in sorted(found.items())]


def _print_report(rows: list[Finding], advisories: dict[str, list[str]] | None, ha: HaEnv | None, skipped: int) -> None:
    if rows:
        print(f"  {len(rows)} declared version(s) exclude the latest release (bump via the ha-safe-deps-bump skill):")
        _print_table(rows)
    else:
        print("  Every declared version admits the latest release.")
    if advisories:
        print(f"  Known vulnerabilities in {len(advisories)} pinned package(s) (OSV):")
        for package, ids in sorted(advisories.items()):
            name = package.split(" ", 1)[0]
            print(f"    {package}: {len(ids)} advisory(ies), https://osv.dev/list?ecosystem=PyPI&q={name}")
    elif advisories is not None:
        print("  No known vulnerabilities in pinned packages (OSV).")
    if ha is None:
        print("  homeassistant is not installed: HA support of these releases was not checked.")
    if skipped:
        print(f"  {skipped} lookup(s) could not be checked (network or registry error).")


def main() -> int:
    python = declared_python(ROOT)
    other = pinned_other(ROOT)

    pypi = _lookup_all(sorted({d.name for d in python}), _pypi_latest)
    git = _lookup_all(sorted({p.source for p in other if p.kind != "feature"}), _git_tags)
    ghcr = _lookup_all(sorted({p.source for p in other if p.kind == "feature"}), _ghcr_tags)
    advisories = _osv_advisories(exact_pins(python))
    ha = _ha_env()

    skipped = sum(v is None for v in [*pypi.values(), *git.values(), *ghcr.values()]) + (advisories is None)
    _print_report(_findings(python, other, pypi, {**git, **ghcr}, ha), advisories, ha, skipped)
    return 0


if __name__ == "__main__":
    sys.exit(main())
