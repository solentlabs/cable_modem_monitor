"""Phase 6 - field mapping extraction for channel sections.

Public API: ``extract_section_mappings`` and ``extract_json_arrays``.
Implementation in ``dispatcher``.
"""

from .dispatcher import extract_json_arrays, extract_section_mappings

__all__ = ["extract_json_arrays", "extract_section_mappings"]
