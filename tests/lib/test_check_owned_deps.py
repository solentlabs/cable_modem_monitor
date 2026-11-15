"""Tests for scripts/check_owned_deps.py.

The validate-ci footer must list only declared versions that need a commit
(a pin or cap excluding the latest release, a hook, action or feature pin
behind its latest tag) and CVEs in our exact pins. The previous version
compared the local venv to PyPI, so it listed floors that needed nothing and
missed pins the venv had moved past.

Coverage breakdown per docs/CODE_REVIEW.md § Test File Standards:
- the comparison and parsing helpers: table-driven
- ``declared_python`` and ``pinned_other``: behavioural over a tmp_path tree
- ``main``: behavioural, network lookups replaced by fixed answers
"""

from __future__ import annotations

from pathlib import Path

import pytest
from packaging.specifiers import SpecifierSet

from tests.fixture_helpers import load_script

_mod = load_script("scripts/check_owned_deps.py")


# fmt: off
REQUIREMENTS = [
    pytest.param("black==26.1.0",                       ("black", "==26.1.0"),          id="pin"),
    pytest.param("pytest>=8.3.4   # pinned by harness",  ("pytest", ">=8.3.4"),          id="comment"),
    pytest.param("types-requests>=2.31.0,<2.33.0",      ("types-requests", ">=2.31.0,<2.33.0"), id="cap"),
    pytest.param("Foo_Bar[extra] >= 1.0 ; python_version<'4'", ("foo-bar", ">=1.0"),     id="extras-marker"),
    pytest.param("aiohttp",                             ("aiohttp", ""),                id="bare"),
]
# fmt: on


@pytest.mark.parametrize(("text", "expected"), REQUIREMENTS)
def test_parse_requirement(text: str, expected: tuple[str, str]) -> None:
    """Name is PEP 503 normalized; extras, markers and comments are dropped."""
    assert _mod._parse_requirement(text) == expected


# fmt: off
SPECS = [
    pytest.param("==26.1.0",          "26.10.1", True,  id="pin-behind"),
    pytest.param("==26.10.1",         "26.10.1", False, id="pin-current"),
    pytest.param(">=8.0",             "9.2.0",   False, id="floor-permits"),
    pytest.param(">=2.31.0,<2.33.0",  "2.33.0",  True,  id="cap-excludes"),
    pytest.param("~=0.16.1",          "0.19.0",  True,  id="compatible-excludes"),
    pytest.param("",                  "1.0",     False, id="no-spec"),
]
# fmt: on


@pytest.mark.parametrize(("spec", "latest", "expected"), SPECS)
def test_spec_excludes(spec: str, latest: str, expected: bool) -> None:
    """Only a spec that rules out the latest release needs a commit."""
    assert _mod.spec_excludes(spec, latest) is expected


# fmt: off
PINS = [
    pytest.param("v4",        "v4.9.0",    False, id="major-same"),
    pytest.param("v4",        "v6.0.2",    True,  id="major-behind"),
    pytest.param("v0.3",      "v0.3.9",    False, id="minor-precision-same"),
    pytest.param("v0.3",      "v0.4.0",    True,  id="minor-precision-behind"),
    pytest.param("26.1.0",    "26.10.1",   True,  id="full-precision-behind"),
    pytest.param("v3.13.1-1", "v3.14.1-1", True,  id="post-release-behind"),
    pytest.param("v3.14.1-1", "v3.14.1-1", False, id="post-release-current"),
    pytest.param("master",    "v2.0.0",    False, id="branch-ref"),
]
# fmt: on


@pytest.mark.parametrize(("pin", "latest", "expected"), PINS)
def test_pin_behind(pin: str, latest: str, expected: bool) -> None:
    """A pin compares at its own precision; a non-version ref is never behind."""
    assert _mod.pin_behind(pin, latest) is expected


# fmt: off
TAGS = [
    pytest.param(["v3.1.0", "v4.0.0-alpha.8"],        "v3.1.0", id="skips-prerelease"),
    pytest.param(["v1.2.0", "v1.10.0", "v1.9.0"],     "v1.10.0", id="numeric-order"),
    pytest.param(["latest", "4", "4.1.3", "3"],       "4.1.3",  id="skips-non-version"),
    pytest.param(["nightly"],                         None,     id="none-usable"),
]
# fmt: on


@pytest.mark.parametrize(("tags", "expected"), TAGS)
def test_latest_stable(tags: list[str], expected: str | None) -> None:
    """The highest stable tag, returned as spelled."""
    assert _mod.latest_stable(tags) == expected


# fmt: off
WHERES = [
    pytest.param(["a.yml"],                         "a.yml",               id="one"),
    pytest.param(["a.yml", "a.yml", "b.yml"],       "a.yml, b.yml",        id="deduped"),
    pytest.param(["a.yml", "b.yml", "c.yml", "d"],  "a.yml, b.yml +2 more", id="counted"),
]
# fmt: on


@pytest.mark.parametrize(("places", "expected"), WHERES)
def test_short_where(places: list[str], expected: str) -> None:
    """A ref used across many workflows stays one line."""
    assert _mod.short_where(places) == expected


def test_exact_pins_keeps_single_equals_only() -> None:
    """Only single ``==`` pins are audited for CVEs: floors and caps are not versions we fix."""
    declared = [
        _mod.Declared("a", "black", "==26.10.1"),
        _mod.Declared("b", "black", "==26.10.1"),
        _mod.Declared("a", "pytest", ">=8.0"),
        _mod.Declared("a", "odd", "==1.0,!=1.1"),
    ]
    assert _mod.exact_pins(declared) == [("black", "26.10.1")]


def _tree(tmp_path: Path) -> Path:
    (tmp_path / "requirements-dev.txt").write_text("# dev\nblack==26.1.0\n-r other.txt\npytest>=8.0\n")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["requests>=2.32.3", "solentlabs-cable-modem-monitor-core"]\n'
        '[project.optional-dependencies]\ndev = ["ruff==0.15.12"]\n'
        '[dependency-groups]\ntest = ["pytest-socket>=0.7"]\n'
    )
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "tests.yml").write_text(
        "steps:\n"
        "  - uses: actions/checkout@v6\n"
        "  - uses: github/codeql-action/init@v4\n"
        "  - uses: home-assistant/actions/hassfest@master\n"
        '  - run: pip install ruff==0.15.12 types-requests "har-capture~=0.16.1"\n'
    )
    (tmp_path / ".pre-commit-config.yaml").write_text(
        "repos:\n" "  - repo: https://github.com/psf/black\n    rev: 26.1.0\n" "  - repo: local\n    hooks: []\n"
    )
    (tmp_path / ".devcontainer").mkdir()
    (tmp_path / ".devcontainer" / "devcontainer.json").write_text(
        '{"features": {"ghcr.io/devcontainers/features/docker-in-docker:2": {}}}'
    )
    return tmp_path


def test_declared_python_reads_every_source(tmp_path: Path) -> None:
    """Requirements, every pyproject section and workflow pip lines; internal and bare names skipped."""
    found = {(d.where, d.name, d.spec) for d in _mod.declared_python(_tree(tmp_path))}
    assert found == {
        ("requirements-dev.txt", "black", "==26.1.0"),
        ("requirements-dev.txt", "pytest", ">=8.0"),
        ("pyproject.toml", "requests", ">=2.32.3"),
        ("pyproject.toml", "ruff", "==0.15.12"),
        ("pyproject.toml", "pytest-socket", ">=0.7"),
        (".github/workflows/tests.yml", "ruff", "==0.15.12"),
        (".github/workflows/tests.yml", "har-capture", "~=0.16.1"),
    }


def test_pinned_other_reads_hooks_actions_and_features(tmp_path: Path) -> None:
    """GitHub hooks, version-tagged actions (subpaths folded to the repo) and ghcr features."""
    found = {(p.kind, p.source, p.pin) for p in _mod.pinned_other(_tree(tmp_path))}
    assert found == {
        ("hook", "psf/black", "26.1.0"),
        ("action", "actions/checkout", "v6"),
        ("action", "github/codeql-action", "v4"),
        ("feature", "devcontainers/features/docker-in-docker", "2"),
    }


# fmt: off
HA_SUPPORT = [
    pytest.param("ruff",           "0.17.5",  (),                                 True,  id="unconstrained"),
    pytest.param("requests",       "2.34.2",  (),                                 False, id="ha-pins-package"),
    pytest.param("aiohttp",        "3.11.11", (),                                 True,  id="ha-pin-matches"),
    pytest.param("types-requests", "2.33.0",  ("urllib3>=2",),                    False, id="requirement-outside-ha"),
    pytest.param("semgrep",        "1.0",     ("urllib3>=1.26",),                 True,  id="requirement-inside-ha"),
    pytest.param("tool",           "1.0",     ('urllib3>=2; extra == "fast"',),   True,  id="extra-only-requirement"),
]
# fmt: on

_HA = _mod.HaEnv(
    specs={"requests": SpecifierSet("==2.32.3"), "aiohttp": SpecifierSet("==3.11.11")},
    installed={"requests": "2.32.3", "aiohttp": "3.11.11", "urllib3": "1.26.20"},
)


@pytest.mark.parametrize(("name", "version", "requires", "expected"), HA_SUPPORT)
def test_ha_supports(name: str, version: str, requires: tuple[str, ...], expected: bool) -> None:
    """A release HA cannot install, directly or through a requirement, is never suggested."""
    assert _mod.ha_supports(name, _mod.Release(version, requires), _HA) is expected


def test_main_reports_only_what_needs_a_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Behind pins, hooks, actions and features are listed; current floors and HA-blocked releases are not."""
    monkeypatch.setattr(_mod, "ROOT", _tree(tmp_path))
    pypi = {
        "black": _mod.Release("26.10.1"),
        "pytest": _mod.Release("9.2.0"),
        "requests": _mod.Release("2.34.2"),
        "ruff": _mod.Release("0.17.5"),
        "pytest-socket": _mod.Release("0.8.1"),
        "har-capture": _mod.Release("0.19.0", ("urllib3>=2",)),
    }
    tags = {
        "psf/black": ["26.1.0", "26.10.1"],
        "actions/checkout": ["v6.0.0", "v7.0.1"],
        "github/codeql-action": ["v4.2.0"],
    }
    monkeypatch.setattr(_mod, "_pypi_latest", pypi.get)
    monkeypatch.setattr(_mod, "_git_tags", tags.get)
    monkeypatch.setattr(_mod, "_ghcr_tags", lambda image: ["2", "4", "4.1.3", "latest"])
    monkeypatch.setattr(_mod, "_osv_advisories", lambda packages: {"black 26.1.0": ["GHSA-x"]})
    monkeypatch.setattr(_mod, "_ha_env", lambda: _HA)

    assert _mod.main() == 0
    out = capsys.readouterr().out

    for listed in ("black", "ruff", "actions/checkout", "docker-in-docker", "psf/black"):
        assert listed in out
    for omitted in ("requests", "pytest-socket", "codeql-action", "har-capture"):
        assert omitted not in out
    assert "black 26.1.0: 1 advisory(ies)" in out


def test_main_counts_unreachable_lookups_as_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Offline is reported as skipped, never as current."""
    monkeypatch.setattr(_mod, "ROOT", _tree(tmp_path))
    for name in ("_pypi_latest", "_git_tags", "_ghcr_tags", "_osv_advisories"):
        monkeypatch.setattr(_mod, name, lambda _arg: None)
    monkeypatch.setattr(_mod, "_ha_env", lambda: _HA)

    assert _mod.main() == 0
    out = capsys.readouterr().out

    assert "could not be checked" in out
    assert "No known vulnerabilities" not in out


def test_main_without_homeassistant_says_ha_was_not_checked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """With no HA installed nothing is filtered, and the report says so."""
    monkeypatch.setattr(_mod, "ROOT", _tree(tmp_path))
    monkeypatch.setattr(_mod, "_pypi_latest", lambda name: _mod.Release("0.19.0", ("urllib3>=2",)))
    monkeypatch.setattr(_mod, "_git_tags", lambda repo: [])
    monkeypatch.setattr(_mod, "_ghcr_tags", lambda image: [])
    monkeypatch.setattr(_mod, "_osv_advisories", lambda packages: {})
    monkeypatch.setattr(_mod, "_ha_env", lambda: None)

    assert _mod.main() == 0
    out = capsys.readouterr().out

    assert "har-capture" in out
    assert "HA support of these releases was not checked" in out
