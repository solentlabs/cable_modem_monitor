"""CBN AES-256-CBC authentication handler.

Speaks the Compal Broadband Networks encrypted login protocol: serves
a login page with a deterministic ``sessionToken`` cookie, then decrypts
the AES-256-CBC encrypted password POST with the token it served and
returns a success response with a rotating session token and SID only
when the plaintext is the test password, the envelope carries the
entry's prefix, and the username is the placeholder the entry declares
or, without one, the test username encrypted the same way.

CBN-specific: login, logout, and restart all POST to the same setter
endpoint, discriminated by the ``fun=N`` parameter in the body. This
handler routes setter POSTs via body inspection in ``handle_login``.

Data requests (POST to getter endpoint) are served via
``get_route_override``, which dispatches by ``fun=N`` from the body.
This bypasses the route table (which can't differentiate POST requests
to the same URL). Each response includes a rotated session token.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import logging
import re
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote, urlparse

from ..routes import RouteEntry, normalize_path
from .form import FormAuthHandler

if TYPE_CHECKING:
    from ...models.modem_config import ModemConfig

_logger = logging.getLogger(__name__)

_FUN_RE = re.compile(rb"fun=(\d+)")
_FUN_TEXT_RE = re.compile(r"fun=(\d+)")
_PASSWORD_RE = re.compile(rb"(?:^|&)Password=([^&]*)")
_USERNAME_RE = re.compile(rb"(?:^|&)Username=([^&]*)")


class FormCbnAuthHandler(FormAuthHandler):
    """CBN AES-256-CBC auth handler — speaks the encrypted login protocol.

    The real ``FormCbnAuthManager`` does a multi-phase login:

    1. GET login page → receive ``sessionToken`` cookie.
    2. Optionally read the model from a getter ``fun`` (rotates the token).
    3. Encrypt via ``compal_encrypt(value, sessionToken, prefix)``.
    4. POST to setter endpoint with ``fun=<login_fun>``.
    5. Check response for ``"successful"`` and extract ``SID``.

    This handler serves a login page with a known session token,
    decrypts the login POST with the last token it served, and returns
    a success response with SID only when ``Password`` decrypts to
    ``_TEST_PASSWORD`` under the entry's prefix and ``Username`` is the
    entry's placeholder or, without one, ``_TEST_USERNAME`` encrypted
    the same way. Anything else gets a failed-login body.

    CBN-specific: All setter endpoint POSTs (login, logout, restart)
    share the same URL, discriminated by ``fun=N`` in the POST body.
    This handler routes them via body inspection in ``handle_login``.

    Data requests to the getter endpoint are served via
    ``get_route_override``, which builds a ``fun→response`` lookup
    from HAR entries.

    Args:
        login_page_path: Path the auth manager GETs for the login page.
        setter_endpoint: Path for all setter POSTs (login, logout, restart).
        getter_endpoint: Path for data GET POSTs (fun=N → XML response).
        session_cookie_name: Name of the rotating session token cookie.
        login_fun: ``fun`` parameter value for login POST.
        logout_fun: ``fun`` parameter value for logout POST (None if no logout).
        restart_fun: ``fun`` parameter value for restart POST (None if no restart).
        har_entries: HAR ``log.entries`` list for building getter responses.
        cipher_prefix: Envelope prefix the login must carry, placeholders filled.
        username_value: Placeholder ``Username`` the login must send verbatim;
            ``None`` expects the test username encrypted like the password.
        hw_model_fun: Getter ``fun`` the firmware answers before login.
    """

    _TEST_USERNAME = "admin"
    _TEST_PASSWORD = "pw"
    _INITIAL_SESSION_TOKEN = "mock-cbn-session-token-0000"
    _TEST_SID = "12345"

    def __init__(
        self,
        login_page_path: str,
        setter_endpoint: str,
        getter_endpoint: str,
        session_cookie_name: str,
        login_fun: int,
        logout_fun: int | None = None,
        restart_fun: int | None = None,
        har_entries: list[dict[str, Any]] | None = None,
        cipher_prefix: str = ":",
        username_value: str | None = None,
        hw_model_fun: int | None = None,
    ) -> None:
        super().__init__(
            login_path=setter_endpoint,
            cookie_name="",  # Session tracked by server flag, not cookie
        )
        self._login_page_path = normalize_path(login_page_path)
        self._setter_endpoint = normalize_path(setter_endpoint)
        self._getter_endpoint = normalize_path(getter_endpoint)
        self._session_cookie_name = session_cookie_name
        self._login_fun = login_fun
        self._logout_fun = logout_fun
        self._restart_fun = restart_fun
        self._cipher_prefix = cipher_prefix
        self._username_value = username_value
        self._hw_model_fun = hw_model_fun
        self._token_counter = 0
        self._served_token = self._INITIAL_SESSION_TOKEN

        # Build fun→response lookups from HAR entries for getter dispatch.
        # The firmware answers some funs differently inside a session (fun=1
        # before login carries only the model; after it, status and uptime),
        # so each side serves the reply the capture recorded in that state,
        # falling back to any reply for a fun recorded only on the other side.
        entries = har_entries or []
        outside, during = _split_by_session(entries, self._setter_endpoint, login_fun, logout_fun)
        everything = _build_getter_responses(entries, self._getter_endpoint)
        self._getter_responses = {**everything, **_build_getter_responses(during, self._getter_endpoint)}
        self._public_responses = {**everything, **_build_getter_responses(outside, self._getter_endpoint)}

    @property
    def current_token(self) -> str:
        """The most recently issued session token (deterministic)."""
        return self._served_token

    def _next_token(self) -> str:
        """Generate the next rotating session token."""
        self._token_counter += 1
        self._served_token = f"mock-cbn-token-{self._token_counter:04d}"
        return self._served_token

    def is_login_request(self, method: str, path: str) -> bool:
        """CBN login: GET login page, any POST to setter endpoint, and the pre-login model read.

        All setter POSTs are routed here so ``handle_login`` can
        inspect the body and dispatch by ``fun`` parameter. With a
        model read configured, getter POSTs come here too: ``handle_login``
        answers that ``fun`` and returns ``None`` for the rest, which the
        server then auth-checks, as it does for HNAP data calls.
        """
        norm = normalize_path(path)
        if method == "GET" and norm == self._login_page_path:
            return True
        if method == "POST" and norm == self._getter_endpoint:
            return self._hw_model_fun is not None
        return method == "POST" and norm == self._setter_endpoint

    def handle_login(
        self,
        method: str,
        path: str,
        body: bytes,
        headers: dict[str, str],
    ) -> RouteEntry | None:
        """Dispatch by method and ``fun`` parameter.

        GET login page → serve page with ``sessionToken`` cookie.
        POST setter with ``fun=login`` → accept login, return SID.
        POST setter with ``fun=logout`` → clear session.
        POST setter with ``fun=restart`` → clear session.
        Other → ``None`` (fall through to route table).
        """
        norm = normalize_path(path)

        if method == "GET" and norm == self._login_page_path:
            return self._login_page_response()

        if method == "POST" and norm == self._getter_endpoint:
            # The firmware's login page reads the model before anyone is
            # logged in (common_api.js loadGlobalValue); nothing else is public.
            # Inside a session the same fun is an ordinary data call.
            if (
                not self._authenticated
                and self._hw_model_fun is not None
                and self._parse_fun(body) == self._hw_model_fun
            ):
                return self._serve_getter(self._hw_model_fun, self._public_responses)
            return None

        if method == "POST" and norm == self._setter_endpoint:
            fun = self._parse_fun(body)
            if fun == self._login_fun:
                return self._handle_login_post(body)
            if fun is not None and fun == self._logout_fun:
                return self._handle_logout_post()
            if fun is not None and fun == self._restart_fun:
                return self._handle_restart_post()

        return None

    def _login_page_response(self) -> RouteEntry:
        """Serve login page HTML with initial ``sessionToken`` cookie."""
        html = "<html><body>CBN Login</body></html>"
        # The client keys its encryption on this cookie, so it is the
        # token the login POST is decrypted with.
        self._served_token = self._INITIAL_SESSION_TOKEN
        return RouteEntry(
            status=200,
            headers=[
                ("Content-Type", "text/html"),
                (
                    "Set-Cookie",
                    f"{self._session_cookie_name}={self._INITIAL_SESSION_TOKEN}; Path=/",
                ),
            ],
            body=html,
        )

    def _handle_login_post(self, body: bytes) -> RouteEntry:
        """Return success with SID if both credentials check out, else a failed login."""
        password = _decrypt_field(_PASSWORD_RE, body, self._served_token, self._cipher_prefix)
        if self._username_value is None:
            username_ok = (
                _decrypt_field(_USERNAME_RE, body, self._served_token, self._cipher_prefix) == self._TEST_USERNAME
            )
        else:
            username_ok = _field(_USERNAME_RE, body) == self._username_value
        if password != self._TEST_PASSWORD or not username_ok:
            _logger.debug("Mock server: CBN login rejected, credentials did not decrypt to the test credentials")
            # A body with none of the firmware's login tokens is its
            # wrong-password branch (AUTH_CBN_SPEC.md § Login Token Vocabulary).
            return RouteEntry(status=200, headers=[("Content-Type", "text/xml")], body="")
        self._authenticated = True
        new_token = self._next_token()
        _logger.debug("Mock server: CBN login accepted, SID=%s", self._TEST_SID)
        return RouteEntry(
            status=200,
            headers=[
                ("Content-Type", "text/xml"),
                (
                    "Set-Cookie",
                    f"{self._session_cookie_name}={new_token}; Path=/",
                ),
            ],
            body=f"successful SID={self._TEST_SID}",
        )

    def _handle_logout_post(self) -> RouteEntry:
        """Handle logout — clear session."""
        self._authenticated = False
        _logger.debug("Mock server: CBN logout — session cleared")
        # Recorded here rather than by the server: CBN addresses every
        # action at one setter endpoint and discriminates by ``fun``, so
        # the server's path matching never sees a logout.
        self.record_action("logout", 200)
        return RouteEntry(status=200, headers=[], body="OK")

    def _handle_restart_post(self) -> RouteEntry:
        """Handle restart — clear session."""
        self._authenticated = False
        _logger.debug("Mock server: CBN restart accepted — session cleared")
        self.record_action("restart", 200)
        return RouteEntry(status=200, headers=[], body="OK")

    def get_route_override(
        self,
        method: str,
        path: str,
        body: bytes,
        headers: dict[str, str],
    ) -> RouteEntry | None:
        """Serve CBN getter responses by ``fun`` parameter.

        All CBN data requests POST to the same getter endpoint with
        varying ``fun=N`` body parameters. The standard route table
        can't differentiate these, so this override dispatches by
        body content. Each response includes a rotated session token.
        """
        if method != "POST" or normalize_path(path) != self._getter_endpoint:
            return None

        fun = self._parse_fun(body)
        if fun is None:
            return None
        return self._serve_getter(fun, self._getter_responses)

    def _serve_getter(self, fun: int, responses: dict[int, RouteEntry]) -> RouteEntry | None:
        """The recorded reply for ``fun`` with a rotated session token, or ``None``."""
        base = responses.get(fun)
        if base is None:
            return None
        new_token = self._next_token()
        response_headers = list(base.headers)
        response_headers.append(
            (
                "Set-Cookie",
                f"{self._session_cookie_name}={new_token}; Path=/",
            )
        )
        return RouteEntry(
            status=base.status,
            headers=response_headers,
            body=base.body,
        )

    @staticmethod
    def _parse_fun(body: bytes) -> int | None:
        """Extract ``fun=N`` from URL-encoded POST body."""
        match = _FUN_RE.search(body)
        return int(match.group(1)) if match else None


def _field(pattern: re.Pattern[bytes], body: bytes) -> str | None:
    """A login POST field's URL-decoded value, or ``None`` if absent."""
    match = pattern.search(body)
    return unquote(match.group(1).decode("ascii")) if match else None


def _decrypt_field(pattern: re.Pattern[bytes], body: bytes, session_token: str, prefix: str) -> str | None:
    """Decrypt a login POST field under ``prefix``, or ``None`` if it does not decode."""
    # Written against the cryptography library directly, not protocol/cbn.py:
    # a harness sharing Core's crypto code passes any error the two share (#86).
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.padding import PKCS7

    value = _field(pattern, body)
    if value is None:
        return None
    try:
        decoded = base64.b64decode(value, validate=True).decode("ascii")
        if not decoded.startswith(prefix):
            return None
        ciphertext = bytes.fromhex(decoded[len(prefix) :])
        token_bytes = session_token.encode("utf-8")
        key = hashlib.sha256(token_bytes).digest()
        iv = hashlib.md5(token_bytes).digest()  # noqa: S324
        decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        padded = decryptor.update(ciphertext) + decryptor.finalize()
        unpadder = PKCS7(128).unpadder()
        plain: bytes = unpadder.update(padded) + unpadder.finalize()
        return plain.decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None


def _split_by_session(
    har_entries: list[dict[str, Any]],
    setter_endpoint: str,
    login_fun: int,
    logout_fun: int | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split entries into (outside a session, inside it) at the accepted login and the logout."""
    start: int | None = None
    end = len(har_entries)
    for index, entry in enumerate(har_entries):
        request = entry.get("request", {})
        if request.get("method", "").upper() != "POST":
            continue
        if normalize_path(urlparse(request.get("url", "")).path) != setter_endpoint:
            continue
        match = _FUN_TEXT_RE.search((request.get("postData") or {}).get("text", ""))
        fun = int(match.group(1)) if match else None
        body = str((entry.get("response", {}).get("content") or {}).get("text", ""))
        if start is None and fun == login_fun and "successful" in body.lower():
            start = index
        elif start is not None and logout_fun is not None and fun == logout_fun:
            end = index
            break
    if start is None:
        return har_entries, []
    return har_entries[:start] + har_entries[end + 1 :], har_entries[start + 1 : end]


def _build_getter_responses(
    har_entries: list[dict[str, Any]],
    getter_endpoint: str,
) -> dict[int, RouteEntry]:
    """Build ``fun→response`` lookup from HAR getter entries.

    Filters HAR entries for POST requests to the getter endpoint,
    extracts the ``fun=N`` parameter from the request body, and maps
    it to the response. For duplicate fun values, the last 200-status
    response wins (matching ``build_routes`` behavior).

    Response headers are preserved except Content-Length (HAR redaction
    may have changed body size) and Set-Cookie (handler adds its own
    rotating token).
    """
    responses: dict[int, RouteEntry] = {}

    for entry in har_entries:
        request = entry.get("request", {})
        response = entry.get("response", {})

        if request.get("method", "").upper() != "POST":
            continue

        url = request.get("url", "")
        path = normalize_path(urlparse(url).path)
        if path != getter_endpoint:
            continue

        # Extract fun from request body
        post_data = request.get("postData", {})
        body_text = post_data.get("text", "")
        match = _FUN_TEXT_RE.search(body_text)
        if not match:
            continue
        fun = int(match.group(1))

        # Extract response
        status = response.get("status", 0)
        body = str(response.get("content", {}).get("text", ""))
        resp_headers: list[tuple[str, str]] = []
        for h in response.get("headers", []):
            name = h.get("name", "")
            lower = name.lower()
            if lower in ("content-length", "set-cookie"):
                continue
            if name:
                resp_headers.append((name, h.get("value", "")))

        # Prefer 200 responses; for non-200, only store if no entry yet
        existing = responses.get(fun)
        if existing is None or status == 200:
            responses[fun] = RouteEntry(
                status=status,
                headers=resp_headers,
                body=body,
            )

    _logger.debug(
        "CBN mock: built getter lookup with %d fun values: %s",
        len(responses),
        sorted(responses.keys()),
    )
    return responses


def _hw_model_from_har(har_entries: list[dict[str, Any]], getter_endpoint: str, fun: int, element: str) -> str:
    """The model text in the capture's reply to ``fun``; raises when the capture lacks it."""
    import defusedxml.ElementTree as DefusedET

    reply = _build_getter_responses(har_entries, getter_endpoint).get(fun)
    found = DefusedET.fromstring(reply.body).find(f".//{element}") if reply and reply.body else None
    if found is None or not (found.text or "").strip():
        raise ValueError(f"capture has no getter fun={fun} reply carrying <{element}>")
    return (found.text or "").strip()


def create_handler(
    modem_config: ModemConfig,
    har_entries: list[dict[str, Any]] | None = None,
) -> FormCbnAuthHandler:
    """Entry point for dynamic auth handler dispatch."""
    from ...models.modem_config.actions import CbnAction
    from ...models.modem_config.auth import CBN_HW_MODEL_PLACEHOLDER, FormCbnAuth

    auth = modem_config.auth
    assert isinstance(auth, FormCbnAuth)

    logout_fun: int | None = None
    restart_fun: int | None = None
    if modem_config.actions:
        if modem_config.actions.logout and isinstance(modem_config.actions.logout, CbnAction):
            logout_fun = modem_config.actions.logout.fun
        if modem_config.actions.restart and isinstance(modem_config.actions.restart, CbnAction):
            restart_fun = modem_config.actions.restart.fun

    prefix = auth.cipher_prefix
    if auth.hw_model_fun is not None:
        # The model comes from the capture's own reply, the one this handler
        # serves the auth manager, so both sides read the same value.
        hw_model = _hw_model_from_har(
            har_entries or [], normalize_path(auth.getter_endpoint), auth.hw_model_fun, auth.hw_model_element
        )
        prefix = prefix.replace(CBN_HW_MODEL_PLACEHOLDER, hw_model)

    handler = FormCbnAuthHandler(
        login_page_path=auth.login_page,
        setter_endpoint=auth.setter_endpoint,
        getter_endpoint=auth.getter_endpoint,
        session_cookie_name=auth.session_cookie_name,
        login_fun=auth.login_fun,
        logout_fun=logout_fun,
        restart_fun=restart_fun,
        har_entries=har_entries,
        cipher_prefix=prefix,
        username_value=auth.username_value,
        hw_model_fun=auth.hw_model_fun,
    )
    handler.login_page = auth.login_page
    return handler
