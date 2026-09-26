"""SJCL-encrypted JSON login: salt and IV from the login page, token from a response header.

Wire format per AUTH_SJCL_SPEC.md § json_sjcl; crypto per § Crypto Library,
implemented once in ``protocol/sjcl.py``. Requires the ``[sjcl]`` extra.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import requests

from ..models.modem_config.auth import JsonSjclAuth
from ..protocol import sjcl
from ..protocol.sjcl import SjclSession
from .base import AuthContext, AuthResult, BaseAuthManager
from .response import matches_criteria, place_token_header, safe_preview

_logger = logging.getLogger(__name__)

# Double-quoted string assignments on the login page (login.php:248-253).
# Data pages ship the same assignments empty, so only a hex value counts.
_PAGE_VAR_RE = re.compile(r'sjclEncryptObj\.(salt|iv)\s*=\s*"([0-9a-fA-F]+)"')


def encrypt_payload(session: SjclSession, data: dict[str, Any]) -> dict[str, str]:
    """Wrap a JSON body in the firmware's envelope: ``{"EncryptedData": <hex>, "user": <user>}``."""
    # Compact separators and raw UTF-8 reproduce the page's JSON.stringify
    # byte for byte (login.php:306), which is what the firmware decrypts.
    plaintext = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    encrypted = sjcl.encrypt(session.key, session.iv_hex, plaintext, session.aad, session.tag_length)
    return {"EncryptedData": encrypted, "user": session.user}


class JsonSjclAuthManager(BaseAuthManager):
    """Encrypts the credentials under a page-supplied salt and IV, reads the session token from a header."""

    def __init__(self, config: JsonSjclAuth) -> None:
        self._config = config
        # The last successful login's SJCL parameters; the firmware encrypts
        # post-login bodies under them too. Held here, never in AuthContext,
        # so the key stays inside the strategy.
        self._sjcl_session: SjclSession | None = None

    def headers(self) -> frozenset[str]:
        """Headers this strategy puts on the wire."""
        return frozenset({"cookie", self._config.token_header.lower()})

    def session_cookie_name(self) -> str:
        """The declared ``cookie_name``."""
        return self._config.cookie_name

    def encode_action_body(self, body: dict[str, Any]) -> dict[str, Any] | None:
        """``body`` in the firmware's envelope under the last login's key; ``None`` before one succeeds."""
        if self._sjcl_session is None:
            return None
        return encrypt_payload(self._sjcl_session, body)

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
        # Checked before any network I/O so a missing extra never reaches the modem.
        try:
            sjcl.ensure_available()
        except ImportError:
            return AuthResult(
                success=False,
                error=(
                    "cryptography package required for json_sjcl auth. "
                    "Install with: pip install solentlabs-cable-modem-monitor-core[sjcl]"
                ),
            )

        config = self._config
        # A failed login must not leave the previous session's key usable.
        self._sjcl_session = None

        # Step 1: login page carries the per-session salt and IV.
        page = session.get(f"{base_url}{config.login_page}", timeout=timeout)
        if page.status_code >= 400:
            return AuthResult(success=False, error=f"Login page returned HTTP {page.status_code}", response=page)
        page_vars = _read_page_vars(page.text)
        if "salt" not in page_vars or "iv" not in page_vars:
            # Wrong device at the address, or firmware that moved the
            # assignments; only the page body tells them apart.
            return AuthResult(
                success=False,
                error="Login page missing sjclEncryptObj.salt or sjclEncryptObj.iv",
                response=page,
            )
        try:
            sjcl.decode_iv(page_vars["iv"], name="sjclEncryptObj.iv")
        except sjcl.SjclInputError as e:
            return AuthResult(success=False, error=str(e), response=page)

        # Steps 2-4: derive the key, encrypt the credentials, send them.
        # The page lowercases the user before both the plaintext and the body
        # (login.php:840), so a mixed-case entry still matches the account.
        user = username.lower()
        try:
            key = sjcl.derive_key(password, page_vars["salt"], config.pbkdf2_iterations, config.pbkdf2_key_length)
        except ValueError:
            # An odd-length hex salt passes the page pattern but not hex decoding.
            return AuthResult(success=False, error="sjclEncryptObj.salt is not valid hex", response=page)
        sjcl_session = SjclSession(
            key=key,
            iv_hex=page_vars["iv"],
            user=user,
            aad=config.aad,
            tag_length=config.ccm_tag_length,
        )
        body = encrypt_payload(sjcl_session, {"username": user, "password": password})

        _logger.log(log_level, "json_sjcl login: %s %s", config.method, config.login_endpoint)
        send = session.put if config.method == "PUT" else session.post
        response = send(f"{base_url}{config.login_endpoint}", json=body, timeout=timeout)
        if response.status_code >= 400:
            return AuthResult(success=False, error=f"Login returned HTTP {response.status_code}", response=response)

        # Step 5: busy before the token; the refusal carries none, and reading
        # it as a missing token would report a credential failure (UC-87a).
        if config.login_busy:
            decrypted = _decrypt_response(response, sjcl_session)
            if isinstance(decrypted, dict) and matches_criteria(decrypted, config.login_busy):
                return AuthResult(
                    success=False,
                    busy=True,
                    error=f"Login busy: {safe_preview(decrypted)}",
                    response=response,
                )

        # Step 6: the token arrives in a response header and goes back in one.
        token = response.headers.get(config.token_header, "")
        if not token:
            return AuthResult(
                success=False,
                error=f"token_header '{config.token_header}' not in login response",
                response=response,
            )
        place_token_header(session, config.token_header, token)
        _logger.log(log_level, "json_sjcl token obtained via %s", config.token_header)

        self._sjcl_session = sjcl_session

        # No response on success: the login answer is not a data page, so it
        # must not advertise auth-response reuse (RESOURCE_LOADING_SPEC).
        # The token also reaches action endpoints as {auth:token}, as bearer's does.
        return AuthResult(success=True, auth_context=AuthContext(token=token))


def _read_page_vars(text: str) -> dict[str, str]:
    """Return the first non-empty ``salt`` and ``iv`` assignments on the page."""
    found: dict[str, str] = {}
    for match in _PAGE_VAR_RE.finditer(text):
        found.setdefault(match.group(1), match.group(2))
    return found


def _decrypt_response(response: requests.Response, session: SjclSession) -> Any:
    """Decrypt the login response's ``EncryptedData`` to JSON; ``None`` when it does not."""
    try:
        body = response.json()
    except (ValueError, requests.exceptions.JSONDecodeError):
        return None
    encrypted = body.get("EncryptedData") if isinstance(body, dict) else None
    if not isinstance(encrypted, str):
        return None
    # A body that does not decrypt is not busy (AUTH_SJCL_SPEC Known Gaps:
    # one captured success body does not decrypt under its own key). The
    # failed tag check raises cryptography's InvalidTag, imported lazily, so
    # the catch is broad; nothing here is logged or re-raised.
    try:
        return json.loads(sjcl.decrypt(session.key, session.iv_hex, encrypted, session.aad, session.tag_length))
    except Exception:
        return None


def create_manager(config: JsonSjclAuth) -> JsonSjclAuthManager:
    """Entry point for dynamic auth factory dispatch."""
    return JsonSjclAuthManager(config)
