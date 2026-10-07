"""Tests for ``check_code_scanning_alerts`` in scripts/release.py.

The gate queries open code-scanning alerts on ``refs/heads/main`` and on
the release branch, each ref named explicitly: the alerts endpoint
defaults to the default branch, and an unanalysed ref returns an empty
list, so both would otherwise read as clean. Per docs/CODE_REVIEW.md
§ Gate Scripts Require Tests, every pass case has a live counterpart that
fires.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.fixture_helpers import load_script

_mod = load_script("scripts/release.py")

_REPO_ROOT = Path("/repo")
_MAIN = "refs/heads/main"
_BRANCH = "refs/heads/feature/v9.9.9-beta.1"
_ALERT = "#1 py/unused-local-variable (note) tests/x.py:10"
_HEAD_SHA = "a" * 40
_OLD_SHA = "b" * 40


class _FakeRun:
    """Stands in for ``subprocess.run``: git reports branch and HEAD, gh reports per-ref state."""

    def __init__(
        self,
        branch: str = "feature/v9.9.9-beta.1",
        alerts: dict[str, list[str]] | None = None,
        unanalysed: tuple[str, ...] = (),
        analysed_at: dict[str, str] | None = None,
        branch_instances: dict[int, list[str]] | None = None,
        gh_error: type[Exception] | None = None,
    ) -> None:
        self.branch = branch
        self.alerts = alerts or {}
        self.unanalysed = unanalysed
        self.analysed_at = analysed_at or {}
        self.branch_instances = branch_instances or {}
        self.gh_error = gh_error
        self.endpoints: list[str] = []

    def __call__(self, command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if command[0] == "git":
            stdout = self.branch if "--abbrev-ref" in command else _HEAD_SHA
            return subprocess.CompletedProcess(command, 0, stdout=f"{stdout}\n", stderr="")
        if self.gh_error is FileNotFoundError:
            raise FileNotFoundError("gh")
        if self.gh_error is subprocess.CalledProcessError:
            raise subprocess.CalledProcessError(1, command, output="", stderr="HTTP 403")
        endpoint = next(arg for arg in command if arg.startswith("repos/"))
        self.endpoints.append(endpoint)
        ref = endpoint.split("ref=")[1].split("&")[0]
        if "/analyses?" in endpoint:
            # The real query prints the newest analysis's commit_sha, or nothing.
            stdout = "" if ref in self.unanalysed else f"{self.analysed_at.get(ref, _HEAD_SHA)}\n"
        elif "/instances?" in endpoint:
            # The real query prints one state per instance of the alert on the ref.
            number = int(endpoint.split("/alerts/")[1].split("/")[0])
            states = self.branch_instances.get(number, []) if ref == _BRANCH else []
            stdout = "".join(f"{state}\n" for state in states)
        else:
            stdout = "".join(f"{line}\n" for line in self.alerts.get(ref, []))
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")


def _check(monkeypatch: pytest.MonkeyPatch, fake: _FakeRun) -> bool:
    monkeypatch.setattr(_mod.subprocess, "run", fake)
    return bool(_mod.check_code_scanning_alerts(_REPO_ROOT))


# =============================================================================
# Gate outcome
# =============================================================================
#
# ┌──────────────────────────────┬───────────────────────────────┬────────┐
# │ situation                    │ fake                          │ passes │
# ├──────────────────────────────┼───────────────────────────────┼────────┤
# │ both refs analysed at HEAD,  │ default                       │ True   │
# │ clean                        │                               │        │
# │ main clean, release branch   │ default, branch "main"        │ True   │
# │ open alert on main, no       │ alerts on main                │ False  │
# │ instance on release branch   │                               │        │
# │ open alert on main, fixed on │ main alert, branch instance   │ True   │
# │ the release branch           │ "fixed"                       │        │
# │ open alert on main, open on  │ main alert, branch instance   │ False  │
# │ the release branch           │ "open"                        │        │
# │ open alert on main, fixed in │ main alert, branch instances  │ False  │
# │ one branch place, open in    │ "fixed" and "open"            │        │
# │ another                      │                               │        │
# │ open alert on main, dismissed│ main alert, branch instance   │ False  │
# │ on the release branch        │ "dismissed"                   │        │
# │ open alert on release branch │ alerts on branch              │ False  │
# │ release branch not analysed  │ branch unanalysed             │ False  │
# │ main not analysed            │ main unanalysed               │ False  │
# │ branch analysed at an older  │ branch analysed at old SHA    │ False  │
# │ commit than HEAD             │                               │        │
# │ main analysed at any commit  │ main analysed at old SHA      │ True   │
# │ detached HEAD                │ branch "HEAD"                 │ False  │
# │ gh call fails                │ CalledProcessError            │ False  │
# │ gh not installed             │ FileNotFoundError             │ False  │
# └──────────────────────────────┴───────────────────────────────┴────────┘
#
# fmt: off
OUTCOME_CASES = [
    # (fake,                                                        passes, id)
    (_FakeRun(),                                                    True,   "both-clean"),
    (_FakeRun(branch="main"),                                       True,   "on-main-clean"),
    (_FakeRun(alerts={_MAIN: [_ALERT]}),                            False,  "main-open-no-branch-instance"),
    (_FakeRun(alerts={_MAIN: [_ALERT]}, branch_instances={1: ["fixed"]}),
                                                                    True,   "main-open-branch-fixed"),
    (_FakeRun(alerts={_MAIN: [_ALERT]}, branch_instances={1: ["open"]}),
                                                                    False,  "main-open-branch-open"),
    (_FakeRun(alerts={_MAIN: [_ALERT]}, branch_instances={1: ["fixed", "open"]}),
                                                                    False,  "main-open-branch-partly-fixed"),
    (_FakeRun(alerts={_MAIN: [_ALERT]}, branch_instances={1: ["dismissed"]}),
                                                                    False,  "main-open-branch-dismissed"),
    (_FakeRun(branch="main", alerts={_MAIN: [_ALERT]}),             False,  "on-main-alert"),
    (_FakeRun(alerts={_BRANCH: [_ALERT]}),                          False,  "alert-on-branch"),
    (_FakeRun(unanalysed=(_BRANCH,)),                               False,  "branch-unanalysed"),
    (_FakeRun(unanalysed=(_MAIN,)),                                 False,  "main-unanalysed"),
    (_FakeRun(analysed_at={_BRANCH: _OLD_SHA}),                     False,  "branch-analysed-before-head"),
    (_FakeRun(analysed_at={_MAIN: _OLD_SHA}),                       True,   "main-analysed-at-any-sha"),
    (_FakeRun(branch="HEAD"),                                       False,  "detached-head"),
    (_FakeRun(gh_error=subprocess.CalledProcessError),              False,  "gh-fails"),
    (_FakeRun(gh_error=FileNotFoundError),                          False,  "gh-missing"),
]
# fmt: on


@pytest.mark.parametrize(("fake", "passes"), [c[:2] for c in OUTCOME_CASES], ids=[c[2] for c in OUTCOME_CASES])
def test_gate_outcome(monkeypatch: pytest.MonkeyPatch, fake: _FakeRun, passes: bool) -> None:
    """Any open alert, missing analysis or failed query stops the release."""
    assert _check(monkeypatch, fake) is passes


def test_queries_both_refs_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """Main and the release branch are each named; the default-branch fallback is never used."""
    fake = _FakeRun()
    _check(monkeypatch, fake)
    alert_queries = [e for e in fake.endpoints if "/alerts?" in e]
    assert len(alert_queries) == 2
    assert f"ref={_MAIN}" in alert_queries[0]
    assert f"ref={_BRANCH}" in alert_queries[1]
    assert all("state=open" in e for e in alert_queries)


def test_main_alert_instance_read_on_the_release_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """A main alert's excuse is read from its instance on the release ref, named explicitly."""
    fake = _FakeRun(alerts={_MAIN: [_ALERT]}, branch_instances={1: ["fixed"]})
    _check(monkeypatch, fake)
    assert [e for e in fake.endpoints if "/instances?" in e] == [
        f"repos/solentlabs/cable_modem_monitor/code-scanning/alerts/1/instances?ref={_BRANCH}&per_page=100"
    ]


def test_main_queried_once_when_releasing_from_main(monkeypatch: pytest.MonkeyPatch) -> None:
    """On main itself the two refs are one."""
    fake = _FakeRun(branch="main")
    _check(monkeypatch, fake)
    assert [e for e in fake.endpoints if "/alerts?" in e] == [
        f"repos/solentlabs/cable_modem_monitor/code-scanning/alerts?state=open&ref={_MAIN}&per_page=100"
    ]


def test_release_stops_before_the_version_bump(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed gate exits before validate-ci runs or any version file is rewritten."""
    reached: list[str] = []

    def validate_ci(root: Path) -> bool:
        reached.append("validate-ci")
        return True

    monkeypatch.setattr(_mod, "validate_release_preconditions", lambda version, root: None)
    monkeypatch.setattr(_mod, "check_code_scanning_alerts", lambda root: False)
    monkeypatch.setattr(_mod, "run_validate_ci", validate_ci)
    monkeypatch.setattr(_mod, "update_all_files", lambda *args: reached.append("bump"))
    args = _mod.argparse.Namespace(version="9.9.9", skip_changelog=False)
    with pytest.raises(SystemExit):
        _mod._run_release(args, _REPO_ROOT)
    assert reached == []
