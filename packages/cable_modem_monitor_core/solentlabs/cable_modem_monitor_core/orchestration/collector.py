"""ModemDataCollector — single data collection cycle.

Executes authenticate -> load resources -> parse -> post-parse filter
-> logout. Owns no scheduling, retry, or backoff policy. Runs once
and returns a ModemResult with signal classification.

See ORCHESTRATION_SPEC.md ModemDataCollector section.
"""

from __future__ import annotations

import logging
from typing import Any, Final
from urllib.parse import urlparse, urlunparse

import requests

from ..auth.base import AuthContext, AuthResult, BaseAuthManager
from ..auth.factory import create_auth_manager
from ..connectivity import create_session
from ..loaders.fetch_list import collect_fetch_targets
from ..loaders.hnap import HNAPLoadError
from ..loaders.http import (
    HTTPResourceLoader,
    LoginPageDetectedError,
    ResourceLoadError,
)
from ..models.modem_config.auth import BasicAuth, NoneAuth
from ..parsers.coordinator import ModemParserCoordinator
from ..parsers.diagnostics import ParseDiagnostics
from .actions import execute_action
from .models import ModemResult, ResourceFetch
from .signals import CollectorSignal

_logger = logging.getLogger(__name__)
_LOGOUT_LOG_LEVEL: Final[int] = logging.DEBUG
_DEFAULT_AUTH_LOG_LEVEL: Final[int] = logging.DEBUG

# Maximum response body characters included in the auth-failure log.
_FAILURE_BODY_SNIPPET_MAX: Final[int] = 500
_REDACTED: Final[str] = "[REDACTED]"


class LoginLockoutError(Exception):
    """Firmware anti-brute-force triggered.

    Raised by HNAP auth strategies when the modem responds with
    ``LoginResult: "LOCKUP"`` or ``"REBOOT"``. The orchestrator
    catches this and applies backoff policy.
    """


class ModemDataCollector:
    """Execute a single data collection cycle.

    Wires together auth manager, resource loader, parser coordinator,
    and optional logout action. The collector is reusable across polls
    -- the auth manager maintains session state between calls.

    Args:
        modem_config: Parsed modem.yaml config.
        parser_config: Parsed parser.yaml config. None if parser.py
            handles all extraction.
        post_processor: Optional PostProcessor from parser.py.
        base_url: Modem URL (e.g., "http://192.168.100.1").
        username: Login credential.
        password: Login credential.
        legacy_ssl: Whether HTTPS requires legacy (SECLEVEL=0)
            ciphers. Discovered during setup by detect_protocol().
            Passed to create_session(). Defaults to False.
    """

    def __init__(
        self,
        modem_config: Any,
        parser_config: Any,
        post_processor: Any,
        base_url: str,
        username: str,
        password: str,
        *,
        legacy_ssl: bool = False,
    ) -> None:
        self._modem_config = modem_config
        self._parser_config = parser_config
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._legacy_ssl = legacy_ssl

        # Auth manager and context
        self._auth_manager: BaseAuthManager = create_auth_manager(modem_config)
        self._auth_context: AuthContext | None = None
        self._last_auth_result: AuthResult | None = None
        self._session_reused: bool = False

        # Persistent session — reused across execute() calls.
        # Created via create_session() so HTTPS modems with self-signed
        # certs get verify=False, and legacy firmware gets SECLEVEL=0.
        self._session = self._build_session()

        # Parser coordinator (reused across polls)
        self._coordinator: ModemParserCoordinator | None = None
        if parser_config is not None:
            self._coordinator = ModemParserCoordinator(parser_config, post_processor)

        # Login page detection — enable for form-based auth strategies
        self._detect_login_pages = _should_detect_login_pages(modem_config)

        # Per-resource timing from last successful collection
        self._last_resource_fetches: list[ResourceFetch] = []

    def execute(self) -> ModemResult:
        """Execute one data collection.

        Sequence:
        1. Auth Manager: validate session -> reuse or authenticate
        2. Resource Loader: fetch all resources (all-or-nothing)
        3. Parser: extract channels + system_info -> ModemData
        4. Logout: execute actions.logout if single-session modem

        Returns:
            ModemResult with modem data or failure signal.
        """
        # Phase 1: Auth
        try:
            auth_result = self.authenticate()
        except LoginLockoutError as exc:
            _logger.warning("Auth lockout [%s] — firmware anti-brute-force triggered", self._modem_config.model)
            return ModemResult(
                success=False,
                signal=CollectorSignal.AUTH_LOCKOUT,
                error=str(exc),
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            error_with_type = f"{type(exc).__name__}: {exc}"
            _log_auth_failure_detail(
                model=self._modem_config.model,
                strategy=_strategy_name(self._modem_config),
                response=None,
                error=error_with_type,
                password=self._password,
            )
            return ModemResult(
                success=False,
                signal=CollectorSignal.CONNECTIVITY,
                error=error_with_type,
            )

        if not auth_result.success:
            _log_auth_failure_detail(
                model=self._modem_config.model,
                strategy=_strategy_name(self._modem_config),
                response=auth_result.response,
                error=auth_result.error,
                password=self._password,
            )
            return ModemResult(
                success=False,
                signal=CollectorSignal.AUTH_FAILED,
                error=auth_result.error,
            )

        # Phase 2: Load resources
        try:
            resources, fetches = self._load_resources(auth_result)
        except LoginPageDetectedError as exc:
            return ModemResult(
                success=False,
                signal=CollectorSignal.LOAD_AUTH,
                error=str(exc),
            )
        except HNAPLoadError as exc:
            return self._classify_hnap_error(exc)
        except ResourceLoadError as exc:
            if exc.status_code in (401, 403):
                hint = _auth_failure_hint(self._modem_config)
                _logger.warning(
                    "%s on %s [%s] — %s",
                    exc.status_code,
                    exc.path,
                    self._modem_config.model,
                    hint,
                )
                return ModemResult(
                    success=False,
                    signal=CollectorSignal.LOAD_AUTH,
                    error=f"{exc.status_code} on {exc.path} — {hint}",
                )
            _logger.warning("Resource load error [%s]: %s", self._modem_config.model, exc)
            return ModemResult(
                success=False,
                signal=CollectorSignal.LOAD_ERROR,
                error=str(exc),
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            _logger.warning("Connection failed during resource loading [%s]", self._modem_config.model)
            return ModemResult(
                success=False,
                signal=CollectorSignal.CONNECTIVITY,
                error=str(exc),
            )

        # Phase 3: Parse + stub-page integrity check (UC-19a)
        parse_outcome = self._run_parse_phase(resources)
        if isinstance(parse_outcome, ModemResult):
            return parse_outcome
        data = parse_outcome

        # Phase 4: Logout (best-effort, after successful collection)
        self._execute_logout_if_needed()

        self._last_resource_fetches = fetches

        ds_count = len(data.get("downstream", []))
        us_count = len(data.get("upstream", []))
        _logger.debug(
            "Collection complete [%s]: %d downstream, %d upstream channels",
            self._modem_config.model,
            ds_count,
            us_count,
        )

        return ModemResult(
            success=True,
            modem_data=data,
            signal=CollectorSignal.OK,
        )

    @property
    def session_is_valid(self) -> bool:
        """Whether the Auth Manager believes the current session is usable.

        Strategy-specific local check: HNAP verifies uid cookie +
        private key (the private key is also set as a PrivateKey
        cookie by the auth manager); cookie-based strategies verify
        the session cookie is present; basic and none are always valid
        after first auth.

        This is a local check -- the server may have expired the session
        even if this returns True.
        """
        # Never authenticated — only NoneAuth can skip authenticate()
        # entirely. BasicAuth is stateless per-request but still needs
        # the initial authenticate() call to set session.auth.
        if self._auth_context is None:
            if self._modem_config.auth is None:
                return True
            return isinstance(self._modem_config.auth, NoneAuth)

        # HNAP: verify session cookies and private key
        if self._modem_config.transport == "hnap":
            has_uid = "uid" in self._session.cookies
            has_key = bool(self._auth_context.private_key)
            return has_uid and has_key

        # Cookie-based: verify session cookie (cookie_name is on auth config)
        cookie_name = getattr(self._modem_config.auth, "cookie_name", "")
        if cookie_name:
            return cookie_name in self._session.cookies

        # URL token: verify token exists
        if self._auth_context.url_token:
            return True

        # Already authenticated — assume valid until server rejects
        return True

    @property
    def last_resource_fetches(self) -> list[ResourceFetch]:
        """Per-resource timing from the last successful collection."""
        return self._last_resource_fetches

    @property
    def session(self) -> requests.Session:
        """The underlying ``requests.Session`` used for auth and loading."""
        return self._session

    def clear_session(self) -> None:
        """Invalidate the current session.

        Called by the orchestrator when it has external evidence that
        the session is dead: LOAD_AUTH signal or connectivity transition.
        """
        self._session.cookies.clear()
        self._auth_context = None
        self._last_auth_result = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_session(self) -> requests.Session:
        """Build a ``requests.Session`` configured for this modem.

        Applies the modem's legacy-SSL setting, copies session-scoped
        headers from modem.yaml, and runs the auth manager's
        ``configure_session`` hook. Called once during ``__init__``
        for the polling session, and once per diagnostic capture
        attempt via :meth:`run_capture_attempt` for isolation.
        """
        session = create_session(legacy_ssl=self._legacy_ssl)
        session_headers: dict[str, str] = {}
        if self._modem_config.session and self._modem_config.session.headers:
            session_headers = self._modem_config.session.resolved_headers(base_url=self._base_url)
        self._auth_manager.configure_session(session, session_headers)
        return session

    def authenticate(
        self,
        *,
        log_level: int = _DEFAULT_AUTH_LOG_LEVEL,
    ) -> AuthResult:
        """Authenticate the session if not already valid.

        Short-circuits if the session is already valid. Called internally
        before data collection and externally by the orchestrator before
        restart actions.

        Args:
            log_level: Log level for auth manager non-error messages.
                Config flow passes ``logging.INFO`` for visibility;
                polling uses the default ``logging.DEBUG``.
        """
        if self.session_is_valid:
            self._session_reused = True
            _logger.debug("Session valid [%s] — reusing", self._modem_config.model)
            return self._last_auth_result or AuthResult(success=True)

        self._session_reused = False
        _logger.debug("No active session [%s] — Authenticating", self._modem_config.model)
        result = self._auth_manager.authenticate(
            self._session,
            self._base_url,
            self._username,
            self._password,
            timeout=self._modem_config.timeout,
            log_level=log_level,
        )

        if result.success:
            self._auth_context = result.auth_context
            self._last_auth_result = result
            _logger.debug(
                "Auth succeeded [%s]: status=%d, url=%s",
                self._modem_config.model,
                result.response.status_code if result.response is not None else 0,
                result.response_url or "(none)",
            )

        return result

    def _load_resources(
        self,
        auth_result: AuthResult,
    ) -> tuple[dict[str, Any], list[ResourceFetch]]:
        """Fetch all resources using the authenticated session."""
        if self._parser_config is None:
            raise RuntimeError(
                "Modem requires custom parser.py — " "parser.yaml alone insufficient for resource loading"
            )

        if self._modem_config.transport == "hnap":
            return self._load_hnap_resources()

        if self._modem_config.transport == "cbn":
            return self._load_cbn_resources()

        return self._load_http_resources(auth_result)

    def _load_http_resources(
        self,
        auth_result: AuthResult,
    ) -> tuple[dict[str, Any], list[ResourceFetch]]:
        """Fetch HTTP resources."""
        targets = collect_fetch_targets(self._parser_config)

        # Prefer body-derived token from auth_context; fall back to cookie
        url_token = ""
        token_prefix = getattr(self._modem_config.auth, "token_prefix", "")
        if token_prefix:
            if self._auth_context and self._auth_context.url_token:
                url_token = self._auth_context.url_token
            else:
                cookie_name = getattr(self._modem_config.auth, "cookie_name", "")
                if cookie_name:
                    url_token = self._session.cookies.get(cookie_name, "") or ""

        query_params: dict[str, str] = {}
        if self._modem_config.session and self._modem_config.session.query_params:
            query_params = dict(self._modem_config.session.query_params)

        loader = HTTPResourceLoader(
            session=self._session,
            base_url=self._base_url,
            timeout=self._modem_config.timeout,
            url_token=url_token,
            token_prefix=token_prefix,
            detect_login_pages=self._detect_login_pages,
            model=self._modem_config.model,
            query_params=query_params,
            headers=self._auth_manager.headers(),
        )

        # On session reuse, don't pass auth_result — there's no
        # login response to reuse.
        effective_auth = auth_result if self._auth_context else None
        resources = loader.fetch(targets, effective_auth)
        return resources, _to_resource_fetches(loader.resource_fetches)

    def _load_hnap_resources(self) -> tuple[dict[str, Any], list[ResourceFetch]]:
        """Fetch HNAP resources via batched SOAP request."""
        from ..loaders.hnap import HNAPLoader

        hmac_algorithm = "md5"
        if hasattr(self._modem_config.auth, "hmac_algorithm"):
            hmac_algorithm = self._modem_config.auth.hmac_algorithm

        private_key = ""
        if self._auth_context:
            private_key = self._auth_context.private_key

        loader = HNAPLoader(
            session=self._session,
            base_url=self._base_url,
            private_key=private_key,
            hmac_algorithm=hmac_algorithm,
            timeout=self._modem_config.timeout,
            headers=self._auth_manager.headers(),
        )
        resources = loader.fetch(self._parser_config)
        return resources, _to_resource_fetches(loader.resource_fetches)

    def _load_cbn_resources(self) -> tuple[dict[str, Any], list[ResourceFetch]]:
        """Fetch CBN resources via XML POST with fun parameters.

        Logout is NOT done by the loader — the collector handles it
        via ``_execute_logout_if_needed()`` using ``actions.logout``.
        """
        from ..loaders.cbn import CBNLoader
        from ..models.modem_config.auth import FormCbnAuth

        targets = collect_fetch_targets(self._parser_config)

        auth = self._modem_config.auth
        assert isinstance(auth, FormCbnAuth)

        loader = CBNLoader(
            session=self._session,
            base_url=self._base_url,
            getter_endpoint=auth.getter_endpoint,
            session_cookie_name=auth.session_cookie_name,
            timeout=self._modem_config.timeout,
            model=self._modem_config.model,
            headers=self._auth_manager.headers(),
        )
        resources = loader.fetch(targets)
        return resources, _to_resource_fetches(loader.resource_fetches)

    def _classify_hnap_error(self, exc: HNAPLoadError) -> ModemResult:
        """Route an HNAP load failure to the correct signal.

        HNAP uses a single fixed endpoint (/HNAP1/) so HTTP errors
        are never "page not found." The session-reuse context determines
        whether the error is a stale session (LOAD_AUTH) or a genuine
        server problem (LOAD_ERROR). See UC-21 and UC-22.
        """
        cause = exc.__cause__

        # Connection/timeout — modem unreachable (UC-30/UC-31)
        if exc.status_code is None and isinstance(cause, requests.ConnectionError | requests.Timeout):
            _logger.warning(
                "HNAP connection failed [%s]: %s",
                self._modem_config.model,
                exc,
            )
            return ModemResult(
                success=False,
                signal=CollectorSignal.CONNECTIVITY,
                error=str(exc),
            )

        # HTTP error on reused session — stale (UC-21)
        if exc.status_code is not None and self._session_reused:
            _logger.warning(
                "HNAP HTTP %s on reused session [%s] — session likely expired",
                exc.status_code,
                self._modem_config.model,
            )
            return ModemResult(
                success=False,
                signal=CollectorSignal.LOAD_AUTH,
                error=f"HNAP HTTP {exc.status_code} — session expired",
            )

        # Fresh session HTTP error or JSON parse — genuine problem (UC-22)
        _logger.warning(
            "HNAP load error [%s]: %s",
            self._modem_config.model,
            exc,
        )
        return ModemResult(
            success=False,
            signal=CollectorSignal.LOAD_ERROR,
            error=str(exc),
        )

    def _parse(self, resources: dict[str, Any]) -> tuple[dict[str, Any], ParseDiagnostics]:
        """Parse resources into ModemData with diagnostics."""
        if self._coordinator is None:
            raise RuntimeError("No parser coordinator configured")
        return self._coordinator.parse(resources)

    def _run_parse_phase(self, resources: dict[str, Any]) -> dict[str, Any] | ModemResult:
        """Run parse + stub-page integrity check.

        Returns ModemData on success or a failure ModemResult for
        PARSE_ERROR / LOAD_INTEGRITY paths. Keeps execute() readable.
        """
        try:
            data, diagnostics = self._parse(resources)
        except Exception as exc:
            _logger.warning("Parse error [%s]: %s", self._modem_config.model, exc)
            return ModemResult(
                success=False,
                signal=CollectorSignal.PARSE_ERROR,
                error=str(exc),
            )
        if diagnostics.has_zero_fulfillment:
            return self._build_load_integrity_result(diagnostics)
        return data

    def _build_load_integrity_result(self, diagnostics: ParseDiagnostics) -> ModemResult:
        """Build a LOAD_INTEGRITY result for a stub-page response.

        Triggered when the parser found 0 of N expected anchors on any
        resource — the response arrived as HTTP 200 but is structurally
        not a data page. The orchestrator clears the session and
        re-authenticates per UC-19a.
        """
        affected = ", ".join(diagnostics.zero_fulfillment_resources)
        counts = "; ".join(
            f"{path} ({c.fulfilled}/{c.expected})"
            for path, c in diagnostics.by_resource.items()
            if c.expected > 0 and c.fulfilled == 0
        )
        _logger.warning(
            "Stub response on %s [%s] — 0 of N expected parser anchors found, "
            "treating as session integrity failure (%s)",
            affected,
            self._modem_config.model,
            counts,
        )
        return ModemResult(
            success=False,
            signal=CollectorSignal.LOAD_INTEGRITY,
            error=f"0 of N expected anchors on {affected} — stub response",
        )

    def _execute_logout_if_needed(self) -> None:
        """Execute logout action for single-session modems.

        Best-effort — logout failure does not affect the collection
        result. The session is released so users can access the
        modem's web UI between polls.
        """
        actions = self._modem_config.actions
        if actions is None or actions.logout is None:
            return

        if self._modem_config.session is None or self._modem_config.session.max_concurrent != 1:
            return

        _logger.debug("Executing logout [%s]", self._modem_config.model)
        try:
            execute_action(self, self._modem_config, actions.logout, log_level=_LOGOUT_LOG_LEVEL)
        except Exception:
            _logger.debug("Logout failed (best-effort) [%s]", self._modem_config.model, exc_info=True)
        else:
            # Session is dead server-side after logout — clear local
            # state so next poll re-authenticates instead of reusing
            # a stale session.
            self.clear_session()
            _logger.debug("Session cleared after logout [%s]", self._modem_config.model)


def _auth_failure_hint(modem_config: Any) -> str:
    """Return a context-appropriate hint for a 401/403 during resource loading."""
    if modem_config.auth is None or isinstance(modem_config.auth, NoneAuth):
        return "modem requires authentication (check config)"
    if isinstance(modem_config.auth, BasicAuth):
        return "credentials rejected"
    return "session expired"


def _should_detect_login_pages(modem_config: Any) -> bool:
    """Determine if login page detection should be enabled.

    Only applicable to form-based HTTP auth strategies where the
    modem may silently serve a login page at data URLs when the
    session expires. Not applicable to none, basic, or hnap.
    """
    if modem_config.auth is None:
        return False
    if isinstance(modem_config.auth, NoneAuth | BasicAuth):
        return False
    return bool(modem_config.transport != "hnap")


def _to_resource_fetches(
    raw: list[tuple[str, float, int, int, str]],
) -> list[ResourceFetch]:
    """Convert loader timing tuples to ResourceFetch objects."""
    return [
        ResourceFetch(
            path=r[0],
            duration_ms=r[1],
            size_bytes=r[2],
            status_code=r[3],
            content_type=r[4],
        )
        for r in raw
    ]


# ---------------------------------------------------------------------------
# Auth-failure detail log
# ---------------------------------------------------------------------------


def _log_auth_failure_detail(
    model: str,
    strategy: str,
    response: requests.Response | None,
    error: str,
    password: str,
) -> None:
    """Emit one WARNING with sanitized wire detail for an auth failure.

    Replaces the older session-adapter capture machinery: a
    maintainer triaging a stuck-setup user only needs to see what
    the modem returned. Here it is in one log line — strategy,
    request line, response status + Content-Type, and a short body
    snippet with the user's password scrubbed if it appears
    literally.

    The URL has its query string stripped (some strategies — Arris
    ``url_token`` notably — put credentials in the query). The body
    snippet is truncated to keep logs tractable.
    """
    if response is None:
        # ConnectionError / Timeout — no response to dump.
        _logger.warning("Auth failed [%s] strategy=%s — %s", model, strategy, error)
        return

    method = response.request.method if response.request else "?"
    url = _strip_url_query(response.url)
    status = response.status_code
    content_type = response.headers.get("Content-Type", "")
    body_snippet = _scrub_password(response.text[:_FAILURE_BODY_SNIPPET_MAX], password)
    if len(response.text) > _FAILURE_BODY_SNIPPET_MAX:
        body_snippet = body_snippet + "... (truncated)"

    _logger.warning(
        "Auth failed [%s] strategy=%s\n" "  request: %s %s\n" "  response: %d %s\n" "  body: %s",
        model,
        strategy,
        method,
        url,
        status,
        content_type,
        body_snippet,
    )


def _strip_url_query(url: str) -> str:
    """Replace any URL query string with ``?<redacted>``.

    URL-token strategies put base64-encoded credentials directly in
    the query (``?<base64(user:password)>``). Stripping the query
    wholesale is conservative — non-credential queries lose
    visibility, but they're rare in modem auth and not worth the
    field-name guessing it would take to differentiate.
    """
    parsed = urlparse(url)
    if not parsed.query:
        return url
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, "<redacted>", parsed.fragment))


def _strategy_name(modem_config: Any) -> str:
    """Return the auth strategy name for the failure log (e.g., ``"form"``)."""
    auth = getattr(modem_config, "auth", None)
    return getattr(auth, "strategy", "none") if auth is not None else "none"


def _scrub_password(text: str, password: str) -> str:
    """Replace literal occurrences of the user's password with ``[REDACTED]``.

    Catches the common cases:

    - Modem error pages that echo the submitted password back.
    - Form-encoded request bodies that some modems include in their
      response (rare but observed).

    Does not attempt to scrub derived forms (PBKDF2 hashes, encrypted
    blobs) — those are protocol-shaped credentials, not the user's
    secret, and reversing them isn't trivial enough to leak useful
    info from a body snippet.
    """
    if not password:
        return text
    return text.replace(password, _REDACTED)
