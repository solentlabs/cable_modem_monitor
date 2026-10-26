"""JavaScript ``encodeURIComponent`` for credentials packed by login page scripts.

Shared by the strategies that reproduce a login page's own packing:
``form`` (``packed_base64``) and ``form_nonce`` (``b64_packed``).
"""

from __future__ import annotations

import urllib.parse

# Characters that JavaScript's encodeURIComponent does NOT encode.
_JS_URI_SAFE = "-_.!~*'()"


def encode_uri_component(value: str) -> str:
    """Encode ``value`` exactly as JavaScript's ``encodeURIComponent`` does."""
    return urllib.parse.quote(value, safe=_JS_URI_SAFE)
