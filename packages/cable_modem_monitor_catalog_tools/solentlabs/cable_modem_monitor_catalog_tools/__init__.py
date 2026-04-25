"""Cable Modem Monitor Catalog Tools — maintainer authoring pipeline.

Contains HAR analysis, YAML generation, golden-file construction,
verification ingest, fleet pattern scanning, and trial parsing.
Carved out from ``cable_modem_monitor_core.mcp`` in v3.14.

Never a runtime dependency. See
``core/docs/ARCHITECTURE_DECISIONS.md`` § "catalog_tools is a
developer accelerator, never a runtime dep."
"""

from __future__ import annotations
