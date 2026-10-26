#!/usr/bin/env python3
"""Write every catalog entry's ``detection.http_headers`` from its HARs; --check reports stale entries instead."""

from __future__ import annotations

import sys
from pathlib import Path

from solentlabs.cable_modem_monitor_catalog_tools.detection_headers import stale_entries, write_detection_headers
from solentlabs.cable_modem_monitor_core.catalog_manager import list_modems

CATALOG_ROOT = (
    Path(__file__).resolve().parents[2] / "cable_modem_monitor_catalog/solentlabs/cable_modem_monitor_catalog/modems"
)


def main() -> int:
    """Rewrite stale modem.yaml detection blocks, or with --check list them and fail."""
    summaries = list_modems(CATALOG_ROOT)
    if "--check" in sys.argv:
        stale = stale_entries(summaries)
        for path in stale:
            print(f"stale detection.http_headers: {path.relative_to(CATALOG_ROOT)}")
        return 1 if stale else 0
    for path in write_detection_headers(summaries):
        print(f"updated: {path.relative_to(CATALOG_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
