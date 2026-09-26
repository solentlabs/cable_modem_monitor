"""SJCL-encrypted JSON login handler.

Serves the login page Core reads the salt and IV from (the captured one
when the capture holds it), and accepts a login only when its body
decrypts, under the key derived from the test password, to the exact
compact plaintext the firmware expects with the lowercased test user.
Anything else is answered ``471 "Parameter decryption failed"``, the
firmware's refusal. A good login answers with the session token in the
``token_header`` response header and the session cookie.

Data requests are gated by session state, as for ``form_sjcl``: in the
capture page GETs carry only the session cookie while AJAX calls add the
token header, so the header cannot be required on every request.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

from ...protocol import sjcl
from ..routes import RouteEntry, extract_har_response_text, normalize_path
from .base import extract_action_config
from .form import FormAuthHandler

if TYPE_CHECKING:
    from ...models.modem_config import ModemConfig

_logger = logging.getLogger(__name__)

# The modem knows its own salt and IV; the harness learns a captured
# page's from the page itself.
_PAGE_VAR_RE = re.compile(r'sjclEncryptObj\.(salt|iv)\s*=\s*"([0-9a-fA-F]+)"')

# Body of the firmware's refusal (response [56] in the #210 capture).
_REJECTED = RouteEntry(
    status=471,
    headers=[("Content-Type", "application/json")],
    body=json.dumps("Parameter decryption failed"),
)


class JsonSjclAuthHandler(FormAuthHandler):
    """Decrypts the login body to verify Core's envelope; issues a header token and session cookie."""

    _TEST_USERNAME = "admin"
    _TEST_PASSWORD = "pw"
    _TEST_TOKEN = "mock-sjcl-token"
    _TEST_SALT = "1122334455667788"
    _TEST_IV_HEX = "aabbccddeeff0011"

    def __init__(
        self,
        login_page: str,
        login_endpoint: str,
        *,
        method: str,
        pbkdf2_iterations: int,
        pbkdf2_key_length: int,
        ccm_tag_length: int,
        aad: str,
        token_header: str,
        cookie_name: str = "",
        login_page_html: str = "",
    ) -> None:
        page_html = login_page_html or self._synthesized_page()
        super().__init__(
            login_path=login_endpoint,
            cookie_name=cookie_name,
            login_page=login_page,
            login_page_html=page_html,
        )
        self._method = method
        self._aad = aad
        self._tag_length = ccm_tag_length
        self._token_header = token_header
        page_vars: dict[str, str] = {}
        for match in _PAGE_VAR_RE.finditer(page_html):
            page_vars.setdefault(match.group(1), match.group(2))
        self._iv_hex = page_vars.get("iv", "")
        # A captured page without usable assignments leaves nothing to decrypt
        # with, so every login is refused, as Core's own login would fail.
        self._key = b""
        salt = page_vars.get("salt", "")
        if salt and len(salt) % 2 == 0:
            self._key = sjcl.derive_key(self._TEST_PASSWORD, salt, pbkdf2_iterations, pbkdf2_key_length)

    def _synthesized_page(self) -> str:
        """Login page with the firmware's assignments, for captures that never recorded it."""
        return (
            "<script>function addUserInfoToEncryptObj(user, password) {\n"
            f'  sjclEncryptObj.salt = "{self._TEST_SALT}";\n'
            f'  sjclEncryptObj.iv = "{self._TEST_IV_HEX}";\n'
            "}</script>"
        )

    def is_login_request(self, method: str, path: str) -> bool:
        """The declared method to the login endpoint, or a GET of the login page."""
        if method == self._method and normalize_path(path) == self._login_path:
            return True
        return self._is_login_page_get(method, path)

    def handle_login(
        self,
        method: str,
        path: str,
        body: bytes,
        headers: dict[str, str],
    ) -> RouteEntry | None:
        """Serve the login page, or verify the encrypted login and issue the session."""
        if self._is_login_page_get(method, path):
            return RouteEntry(status=200, headers=[("Content-Type", "text/html")], body=self._login_page_html)
        if not self.is_login_request(method, path):
            return None
        if not self._decrypts_to_expected_login(body):
            _logger.debug("Mock server: json_sjcl login refused at %s", path)
            return _REJECTED

        self._authenticated = True
        _logger.debug("Mock server: json_sjcl login accepted at %s", path)
        response_headers = [("Content-Type", "application/json"), (self._token_header, self._TEST_TOKEN)]
        if self._cookie_name:
            response_headers.append(("Set-Cookie", f"{self._cookie_name}={self._SESSION_TOKEN}; Path=/"))
        # The success body is encrypted like the firmware's; its content is
        # never relied on beyond the busy check, so it carries nothing.
        encrypted = sjcl.encrypt(self._key, self._iv_hex, "{}", self._aad, self._tag_length)
        return RouteEntry(status=200, headers=response_headers, body=json.dumps({"EncryptedData": encrypted}))

    def handle_restart(self, *, body: bytes = b"") -> RouteEntry:
        """Accept only a restart encrypted under the session key; the check is what proves Core encrypted it."""
        # The content is not compared to Core's own config: that would
        # certify Core against Core. Decrypting under the key is the proof.
        if self._open_envelope(body) is None:
            _logger.debug("Mock server: json_sjcl restart refused, body is not the session's envelope")
            return RouteEntry(status=400, headers=[], body="Bad Request")
        return super().handle_restart(body=body)

    def _decrypts_to_expected_login(self, body: bytes) -> bool:
        """True when the body is the envelope of the test credentials under this page's key."""
        expected = json.dumps(
            {"username": self._TEST_USERNAME, "password": self._TEST_PASSWORD}, separators=(",", ":")
        ).encode()
        return self._open_envelope(body) == expected

    def _open_envelope(self, body: bytes) -> bytes | None:
        """Plaintext of an exact ``{EncryptedData, user}`` envelope from the test user, or ``None``."""
        if not self._key:
            return None
        try:
            envelope = json.loads(body)
            if not isinstance(envelope, dict) or set(envelope) != {"EncryptedData", "user"}:
                return None
            if envelope["user"] != self._TEST_USERNAME:
                return None
            return sjcl.decrypt(self._key, self._iv_hex, envelope["EncryptedData"], self._aad, self._tag_length)
        except Exception:
            # Malformed JSON, bad hex or a failed tag check (cryptography's
            # InvalidTag) are all a refusal.
            return None


def create_handler(
    modem_config: ModemConfig,
    har_entries: list[dict[str, Any]] | None = None,
) -> JsonSjclAuthHandler:
    """Entry point for dynamic auth handler dispatch."""
    from ...models.modem_config.auth import JsonSjclAuth

    auth = modem_config.auth
    assert isinstance(auth, JsonSjclAuth)
    # The first captured GET of the page is the pre-auth one.
    login_page_html = extract_har_response_text(har_entries, "GET", auth.login_page) if har_entries else ""
    handler = JsonSjclAuthHandler(
        login_page=auth.login_page,
        login_endpoint=auth.login_endpoint,
        method=auth.method,
        pbkdf2_iterations=auth.pbkdf2_iterations,
        pbkdf2_key_length=auth.pbkdf2_key_length,
        ccm_tag_length=auth.ccm_tag_length,
        aad=auth.aad,
        token_header=auth.token_header,
        cookie_name=extract_action_config(modem_config).cookie_name,
        login_page_html=login_page_html,
    )
    handler.login_page = auth.login_page
    handler.login_action = auth.login_endpoint
    return handler
