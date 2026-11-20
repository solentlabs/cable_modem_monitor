"""Every download carries the MIT notice, the license's one condition: the PyPI packages and the release zip."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REPO_LICENSE = (ROOT / "LICENSE").read_text(encoding="utf-8")

PACKAGES = ["cable_modem_monitor_core", "cable_modem_monitor_catalog"]


@pytest.mark.parametrize("package", PACKAGES)
def test_package_license_matches_the_repository(package: str) -> None:
    """The copy hatchling puts in the package's wheel and source distribution is the root LICENSE."""
    assert (ROOT / "packages" / package / "LICENSE").read_text(encoding="utf-8") == REPO_LICENSE


def test_release_zip_includes_the_license() -> None:
    """release.yml adds the repository's LICENSE to the integration zip it publishes."""
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert 'zip -j "$GITHUB_WORKSPACE/cable_modem_monitor.zip" "$GITHUB_WORKSPACE/LICENSE"' in workflow
