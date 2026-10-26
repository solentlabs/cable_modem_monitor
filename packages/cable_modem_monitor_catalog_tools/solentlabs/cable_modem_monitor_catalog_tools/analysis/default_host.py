"""Default host detection: the address a capture was taken on.

Feeds ``enrich_metadata``'s ``default_host``. ONBOARDING_SPEC.md § Phase 7.
"""

from __future__ import annotations

from collections import Counter
from typing import Any
from urllib.parse import urlsplit


def detect_default_host(entries: list[dict[str, Any]]) -> str:
    """Return the host most requests went to (ties go to the first seen), or "" when no request names one."""
    counts: Counter[str] = Counter()
    for entry in entries:
        try:
            host = urlsplit(entry.get("request", {}).get("url", "")).hostname
        except ValueError:
            continue
        if host:
            counts[host] += 1
    # Counter keeps insertion order, and max() returns the first of equal counts.
    return max(counts, key=counts.__getitem__, default="")
