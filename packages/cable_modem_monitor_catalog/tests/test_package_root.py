"""Smoke tests for the catalog package root.

Verifies the package's single public symbol (``CATALOG_PATH``)
points at a real directory inside the installed package — covers
the import-time wiring that the runtime HA integration relies on.
"""

from __future__ import annotations


def test_catalog_path_exists() -> None:
    """CATALOG_PATH points at a real directory inside the installed package."""
    from solentlabs.cable_modem_monitor_catalog import CATALOG_PATH

    assert CATALOG_PATH.exists()
    assert CATALOG_PATH.is_dir()
    assert CATALOG_PATH.name == "modems"


def test_catalog_path_contains_modems() -> None:
    """CATALOG_PATH has at least one manufacturer subdirectory."""
    from solentlabs.cable_modem_monitor_catalog import CATALOG_PATH

    children = [p for p in CATALOG_PATH.iterdir() if p.is_dir()]
    assert len(children) > 0
