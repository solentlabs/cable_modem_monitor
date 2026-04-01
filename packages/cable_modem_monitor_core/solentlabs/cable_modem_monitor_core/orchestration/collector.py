"""ModemDataCollector — single data collection cycle.

Executes authenticate -> load resources -> parse -> post-parse filter
-> logout. Owns no scheduling, retry, or backoff policy. Runs once
and returns a ModemResult with signal classification.

See ORCHESTRATION_SPEC.md ModemDataCollector section.
"""

from __future__ import annotations

import logging
from typing import Any, Final

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
from ..parsers.coordinator import ModemParserCoordinator, filter_restart_window
from .actions import execute_action
from .models import ModemResult
from .signals import CollectorSignal

_logger = logging.getLogger(__name__)
_LOGOUT_LOG_LEVEL: Final[int] = logging.DEBUG
_DEFAULT_AUTH_LOG_LEVEL: Final[int] = logging.DEBUG


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

        # Persistent session — reused across execute() calls.
        # Created via create_session() so HTTPS modems with self-signed
        # certs get verify=False, and legacy firmware gets SECLEVEL=0.
        self._session = create_session(legacy_ssl=legacy_ssl)

        # Auth manager and context
        self._auth_manager: BaseAuthManager = create_auth_manager(modem_config)
        self._auth_context: AuthContext | None = None
        self._last_auth_result: AuthResult | None = None
        self._session_reused: bool = False

        # Configure session with static headers
        session_headers: dict[str, str] = {}
        if modem_config.session and modem_config.session.headers:
            session_headers = dict(modem_config.session.headers)
        self._auth_manager.configure_session(self._session, session_headers)

        # Parser coordinator (reused across polls)
        self._coordinator: ModemParserCoordinator | None = None
        if parser_config is not None:
            self._coordinator = ModemParserCoordinator(parser_config, post_processor)

        # Login page detection — enable for form-based auth strategies
        self._detect_login_pages = _should_detect_login_pages(modem_config)

    def execute(self) -> ModemResult:
        """Execute one data collection.

        Sequence:
        1. Auth Manager: validate session -> reuse or authenticate
        2. Resource Loader: fetch all resources (all-or-nothing)
        3. Parser: extract channels + system_info -> ModemData
        4. Post-parse filter: apply restart-window filter if configured
        5. Logout: execute actions.logout if single-session modem

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
            _logger.info("Connection failed during auth [%s]: %s", self._modem_config.model, exc)
            return ModemResult(
                success=False,
                signal=CollectorSignal.CONNECTIVITY,
                error=str(exc),
            )

        if not auth_result.success:
            _logger.info("Auth failed [%s]: %s", self._modem_config.model, auth_result.error)
            return ModemResult(
                success=False,
                signal=CollectorSignal.AUTH_FAILED,
                error=auth_result.error,
            )

        # Phase 2: Load resources
        try:
            resources = self._load_resources(auth_result)
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
            _logger.info("Resource load error [%s]: %s", self._modem_config.model, exc)
            return ModemResult(
                success=False,
                signal=CollectorSignal.LOAD_ERROR,
                error=str(exc),
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            _logger.info("Connection failed during resource loading [%s]: %s", self._modem_config.model, exc)
            return ModemResult(
                success=False,
                signal=CollectorSignal.CONNECTIVITY,
                error=str(exc),
            )

        # Phase 3: Parse
        try:
            data = self._parse(resources)
        except Exception as exc:
            _logger.error("Parse error [%s]: %s", self._modem_config.model, exc)
            return ModemResult(
                success=False,
                signal=CollectorSignal.PARSE_ERROR,
                error=str(exc),
            )

        # Phase 4: Post-parse filter
        data = self._apply_restart_window_filter(data)

        # Phase 5: Logout (best-effort, after successful collection)
        self._execute_logout_if_needed()

        ds_count = len(data.get("downstream", []))
        us_count = len(data.get("upstream", []))
        _logger.debug(
            "Collection complete: %d downstream, %d upstream channels",
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
            _logger.debug("Session valid — reusing")
            return self._last_auth_result or AuthResult(success=True)

        self._session_reused = False
        _logger.debug("No active session — authenticating")
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

        return result

    def _load_resources(self, auth_result: AuthResult) -> dict[str, Any]:
        """Fetch all resources using the authenticated session."""
        if self._parser_config is None:
            raise RuntimeError(
                "Modem requires custom parser.py — " "parser.yaml alone insufficient for resource loading"
            )

        if self._modem_config.transport == "hnap":
            return self._load_hnap_resources()

        return self._load_http_resources(auth_result)

    def _load_http_resources(self, auth_result: AuthResult) -> dict[str, Any]:
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

        loader = HTTPResourceLoader(
            session=self._session,
            base_url=self._base_url,
            timeout=self._modem_config.timeout,
            url_token=url_token,
            token_prefix=token_prefix,
            detect_login_pages=self._detect_login_pages,
        )

        # On session reuse, don't pass auth_result — there's no
        # login response to reuse.
        effective_auth = auth_result if self._auth_context else None
        return loader.fetch(targets, effective_auth)

    def _load_hnap_resources(self) -> dict[str, Any]:
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
        )
        return loader.fetch(self._parser_config)

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
            _logger.info(
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
        _logger.info(
            "HNAP load error [%s]: %s",
            self._modem_config.model,
            exc,
        )
        return ModemResult(
            success=False,
            signal=CollectorSignal.LOAD_ERROR,
            error=str(exc),
        )

    def _parse(self, resources: dict[str, Any]) -> dict[str, Any]:
        """Parse resources into ModemData."""
        if self._coordinator is None:
            raise RuntimeError("No parser coordinator configured")
        return self._coordinator.parse(resources)

    def _apply_restart_window_filter(self, data: dict[str, Any]) -> dict[str, Any]:
        """Filter zero-power channels during restart window if configured."""
        behaviors = self._modem_config.behaviors
        if behaviors and behaviors.zero_power_reported and behaviors.restart:
            return filter_restart_window(data, behaviors.restart.window_seconds)
        return data

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

        _logger.debug("Executing logout action")
        try:
            execute_action(self, self._modem_config, actions.logout, log_level=_LOGOUT_LOG_LEVEL)
        except Exception:
            _logger.debug("Logout failed (best-effort)", exc_info=True)
        else:
            # Session is dead server-side after logout — clear local
            # state so next poll re-authenticates instead of reusing
            # a stale session.
            self.clear_session()
            _logger.debug("Session cleared after logout")


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
