"""JSON login auth manager: one round trip, token back on every request. See MODEM_YAML_SPEC.md § bearer."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import requests

from ..models.modem_config.auth import BearerAuth
from .base import AuthContext, AuthResult, BaseAuthManager
from .response import matches_criteria, safe_preview

_logger = logging.getLogger(__name__)

# The one placeholder extra_fields values may carry (ARCHITECTURE_DECISIONS
# § Token source and placement are values; encryption is a strategy).
_HOST_PLACEHOLDER = "{host}"

# Sentinel for a login body that did not parse; None is valid JSON.
_NOT_JSON = object()


class BearerAuthManager(BaseAuthManager):
    """Sends credentials as JSON, reads a token from the body or a header, sends it back as declared."""

    def __init__(self, config: BearerAuth) -> None:
        self._config = config

    def authenticate(
        self,
        session: requests.Session,
        base_url: str,
        username: str,
        password: str,
        *,
        timeout: int = 10,
        log_level: int = logging.DEBUG,
    ) -> AuthResult:
        config = self._config
        login_url = f"{base_url}{config.login_endpoint}"

        _logger.log(log_level, "Bearer login: %s %s", config.method, config.login_endpoint)

        # The default POST keeps the call it has always been, so the unset
        # request is the pre-extension request.
        send = session.put if config.method == "PUT" else session.post
        response = send(login_url, json=self._login_body(base_url, username, password), timeout=timeout)

        # Token creation legitimately answers 201; any 2xx that carries the
        # token is a successful login.
        if not 200 <= response.status_code < 300:
            return AuthResult(
                success=False,
                error=f"Login returned HTTP {response.status_code}",
                response=response,
            )

        body = _parse_json(response)

        # Busy before the token: the refusal body carries no token, and
        # reading it as a missing token would report a credential failure
        # for a slot the modem simply would not give up (UC-87a).
        if config.login_busy and isinstance(body, dict) and matches_criteria(body, config.login_busy):
            return AuthResult(
                success=False,
                busy=True,
                error=f"Login busy: {safe_preview(body)}",
                response=response,
            )

        token = self._read_token(response, body)
        if isinstance(token, AuthResult):
            return token

        url_token = self._place_token(session, token)
        source = config.token_header if config.token_source == "header" else config.token_path
        _logger.log(log_level, "Bearer token obtained via %s", source)

        # Both values reach action endpoints as {auth:token} / {auth:user_id}.
        # An unresolvable user_id_path is not a login failure; only actions
        # that name the placeholder care, and they degrade to a literal path.
        user_id = _extract_user_id(body, config.user_id_path) if config.user_id_path else ""
        if config.user_id_path and not user_id:
            _logger.log(
                log_level,
                "Bearer user_id_path '%s' did not resolve in the login response",
                config.user_id_path,
            )

        return AuthResult(
            success=True,
            auth_context=AuthContext(token=token, user_id=user_id, url_token=url_token),
        )

    def _login_body(self, base_url: str, username: str, password: str) -> dict[str, str]:
        """Build the JSON login body: credentials, then resolved extra_fields."""
        config = self._config
        # Password-only firmwares send no username key at all; an empty
        # username_field reproduces that body exactly.
        body: dict[str, str] = {"password": password}
        if config.username_field:
            body = {config.username_field: username, "password": password}
        if config.extra_fields:
            body.update(_resolve_extra_fields(config.extra_fields, base_url))
        return body

    def _read_token(self, response: requests.Response, body: Any) -> str | AuthResult:
        """Read the token from the declared source, or the failure that explains its absence."""
        config = self._config
        if config.token_source == "header":
            # A header-issued login may answer with an empty body, so the
            # body is never consulted for the token here.
            header_token = response.headers.get(config.token_header, "")
            if not header_token:
                return AuthResult(
                    success=False,
                    error=f"token_header '{config.token_header}' not in login response",
                    response=response,
                )
            return header_token
        if body is _NOT_JSON:
            return AuthResult(success=False, error="Login response is not valid JSON", response=response)
        token = _extract_token(body, config.token_path)
        if token is None:
            return AuthResult(
                success=False,
                error=f"token_path '{config.token_path}' not found in login response",
                response=response,
            )
        return token

    def _place_token(self, session: requests.Session, token: str) -> str:
        """Put the token where token_placement sends it; return it as url_token for query placement."""
        config = self._config
        if config.token_placement == "authorization":
            session.headers["Authorization"] = f"Bearer {token}"
        elif config.token_placement == "header":
            session.headers[config.token_header] = token
        else:
            # A query-placed token reaches data URLs through url_token and the
            # declared token_prefix, the same path url_token auth uses.
            return token
        return ""

    def headers(self) -> frozenset[str]:
        """Headers this strategy puts on the wire."""
        declared = {"authorization", "cookie"}
        if self._config.token_placement == "header":
            declared.add(self._config.token_header.lower())
        return frozenset(declared)


def _resolve_extra_fields(extra_fields: dict[str, str], base_url: str) -> dict[str, str]:
    """Substitute ``{host}`` with the base URL's hostname (the browser's location.hostname)."""
    host = urlparse(base_url).hostname or ""
    # location.hostname keeps an IPv6 literal's brackets; urlparse strips them.
    if ":" in host:
        host = f"[{host}]"
    return {key: value.replace(_HOST_PLACEHOLDER, host) for key, value in extra_fields.items()}


def _parse_json(response: requests.Response) -> Any:
    """Return the parsed login body, or ``_NOT_JSON`` when it does not parse."""
    try:
        return response.json()
    except (ValueError, requests.exceptions.JSONDecodeError):
        return _NOT_JSON


def _walk_path(body: Any, path: str) -> Any:
    """Walk a dot-separated path through a JSON dict; return the value at the leaf or None."""
    current: Any = body
    for key in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


def _extract_token(body: Any, token_path: str) -> str | None:
    """Walk a dot-separated path through a JSON dict; return the string value or None."""
    current = _walk_path(body, token_path)
    if not isinstance(current, str):
        return None
    return current


def _extract_user_id(body: Any, user_id_path: str) -> str:
    """Walk a dot-separated path to a user identifier; numbers are stored as their string form."""
    # Observed firmwares return the id as a JSON number (F3896LG: userId 3),
    # so unlike the token this accepts int as well as str. bool is an int
    # subclass and is never an identifier; reject it explicitly.
    current = _walk_path(body, user_id_path)
    if isinstance(current, str):
        return current
    if isinstance(current, int) and not isinstance(current, bool):
        return str(current)
    return ""


def create_manager(config: BearerAuth) -> BearerAuthManager:
    """Entry point for dynamic auth factory dispatch."""
    return BearerAuthManager(config)
