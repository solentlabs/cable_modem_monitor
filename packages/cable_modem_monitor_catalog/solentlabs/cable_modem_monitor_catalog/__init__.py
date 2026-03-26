"""Cable Modem Monitor Catalog — modem config files and parser overrides."""

from __future__ import annotations

from pathlib import Path

#: Root of the modem catalog directory tree.
#: Structure: ``modems/{manufacturer}/{model}/`` with ``modem.yaml``,
#: ``parser.yaml``, optional ``parser.py``, and ``tests/`` per modem.
CATALOG_PATH: Path = Path(__file__).parent / "modems"
