"""HTML normalization — fix known malformed HTML patterns before BS4 parsing.

Applied at the input boundary (loaders and HAR extraction) so all parsers
receive normalized HTML. Centralizing normalization here means parser-level
workarounds stay out of format-specific code.
"""

from __future__ import annotations

import re

# Firmware emits <th>Label</td><td>val</td>... where <th> is closed with
# </td> instead of </th>. html.parser (via BS4) nests the following <td>
# elements inside the unclosed <th>, so recursive=False on the row returns
# 1 cell with all values concatenated. Fix: replace the mismatched closing
# tag so html.parser receives well-formed input.
# Only fires on <th>plain-text</td> (never valid HTML), so cannot corrupt
# well-formed tables.
_UNCLOSED_TH_RE = re.compile(r"(<th\b[^>]*>)([^<]*)(</td>)", re.IGNORECASE)


def normalize_html(text: str) -> str:
    """Normalize known malformed HTML patterns before passing to BS4."""
    return _UNCLOSED_TH_RE.sub(r"\1\2</th>", text)
