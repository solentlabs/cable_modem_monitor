"""Resource loaders — fetch data from modems.

HTTP loader for standard web interfaces. HNAP loader deferred
to Step 3b.

See RESOURCE_LOADING_SPEC.md.
"""

from __future__ import annotations

from .fetch_list import ResourceTarget, collect_fetch_targets
from .http import HTTPResourceLoader, LoginPageDetectedError, ResourceLoadError

__all__ = [
    "HTTPResourceLoader",
    "LoginPageDetectedError",
    "ResourceLoadError",
    "ResourceTarget",
    "collect_fetch_targets",
]
