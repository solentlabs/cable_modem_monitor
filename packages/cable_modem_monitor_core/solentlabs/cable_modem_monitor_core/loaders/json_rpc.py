"""JSON-RPC 2.0 resource loader: one call per method on the transport's endpoint.

Each resource on the fetch list is a method name. The loader POSTs the
call with the session token in the query and stores the reply's
``result`` under that name, the envelope stripped.

A fetch failure is surfaced, never skipped: connection and timeout
errors propagate for the collector to read as ``CONNECTIVITY``, a
non-2xx raises ``ResourceLoadError`` carrying its status, and the
entry's ``session_expired_code`` raises ``SessionExpiredError``. A call
that answered without data (another error code, or not an envelope) is
omitted and recorded in ``decode_errors``.

See RESOURCE_LOADING_SPEC.md § JSON-RPC Loading.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

from ..connectivity import is_connectivity_error
from ..fetch_list import ResourceTarget
from ..protocol.json_rpc import call_url, parse_reply, post_call
from .diagnostics import describe_request
from .http import ResourceLoadError, SessionExpiredError

_logger = logging.getLogger(__name__)

# Sentinel for a call that answered but served no data.
_OMITTED = object()


class JsonRpcLoader:
    """Fetch resources as JSON-RPC calls, keyed by method name."""

    def __init__(
        self,
        session: requests.Session,
        base_url: str,
        endpoint: str,
        token_prefix: str,
        url_token: str,
        session_expired_code: str,
        timeout: int,
        model: str,
        headers: frozenset[str] = frozenset(),
    ) -> None:
        self._session = session
        self._url = call_url(base_url, endpoint, token_prefix, url_token)
        # The token rides in the query, so failure logs mask it (describe_request).
        self._has_token = bool(token_prefix and url_token)
        self._expired_code = session_expired_code
        self._timeout = timeout
        self._model = model
        self._headers = headers
        self.resource_fetches: list[tuple[str, float, int, int, str]] = []
        # (method, format, reason) per omitted call; the collector logs them.
        self.decode_errors: list[tuple[str, str, str]] = []

    def fetch(self, targets: list[ResourceTarget]) -> dict[str, Any]:
        """Call every target's method in order and return the resource dict."""
        resources: dict[str, Any] = {}
        self.resource_fetches = []
        self.decode_errors = []
        for target in targets:
            value = self._fetch_one(target)
            if value is not _OMITTED:
                resources[target.path] = value
        return resources

    def _fetch_one(self, target: ResourceTarget) -> Any:
        """One call; its result, ``_OMITTED``, or a raised signal."""
        method = target.path
        start = time.monotonic()
        try:
            response = post_call(self._session, self._url, method, [], timeout=self._timeout)
        except requests.RequestException as exc:
            # RESOURCE_LOADING_SPEC § Error Signals: an unreachable modem is
            # CONNECTIVITY, so these propagate rather than shorten the dict.
            if is_connectivity_error(exc):
                raise
            raise ResourceLoadError(f"Failed to call {method}: {type(exc).__name__}: {exc}", path=method) from exc

        elapsed_ms = (time.monotonic() - start) * 1000

        if not 200 <= response.status_code < 300:
            raise ResourceLoadError(
                f"HTTP {response.status_code} on {method}",
                status_code=response.status_code,
                path=method,
                request_line=describe_request(response.request, headers=self._headers, mask_query=self._has_token),
                response_body=response.text,
                content_type=response.headers.get("Content-Type", ""),
            )

        _logger.debug(
            "JSON-RPC resource loaded: %s [%s] (%.0fms, %d bytes)",
            method,
            self._model,
            elapsed_ms,
            len(response.content),
        )
        self.resource_fetches.append(
            (
                method,
                round(elapsed_ms, 1),
                len(response.content),
                response.status_code,
                response.headers.get("Content-Type", ""),
            )
        )

        reply = parse_reply(response)
        if reply is None:
            self.decode_errors.append((method, target.format, "not a JSON-RPC response"))
            return _OMITTED
        if reply.is_error:
            code = reply.error_code or ""
            if self._expired_code and code == self._expired_code:
                raise SessionExpiredError(method, code)
            self.decode_errors.append((method, target.format, f"JSON-RPC error {code}"))
            return _OMITTED

        # Same rule as HTTP structured formats: parsers always receive a dict.
        result = reply.result
        return result if isinstance(result, dict) else {"_raw": result}
