"""Every shipped variant file is reachable through catalog discovery.

HAR replay loads each config by path, so it passes for a file the setup
picker can never offer. This walks the path the picker takes (#213).
"""

from __future__ import annotations

from solentlabs.cable_modem_monitor_catalog import CATALOG_PATH
from solentlabs.cable_modem_monitor_core.catalog_manager import list_modems, list_variants


def test_every_variant_file_is_discoverable() -> None:
    """list_modems + list_variants reach every modem*.yaml in the catalog."""
    shipped = {p for p in CATALOG_PATH.rglob("modem*.yaml") if p.stem == "modem" or p.stem.startswith("modem-")}
    discovered = {
        variant.path
        for summary in list_modems(CATALOG_PATH)
        for variant in list_variants(summary.path, summary.sibling_dirs)
    }

    assert shipped, "catalog has no variant files"
    unreachable = sorted(str(p.relative_to(CATALOG_PATH)) for p in shipped - discovered)
    assert not unreachable, f"variant files the setup picker cannot offer: {unreachable}"
