"""Form-nonce auth handler for the HAR mock server.

Extends ``FormAuthHandler`` to serve the login page HTML on GET
and accept credential POSTs.  The test harness runner GETs the
login page to detect credential encoding (plain vs b64-packed)
before creating the auth manager — mirroring the HA config flow's
pre-fetch against a real modem.

Credentials are not validated — any POST to the login path is
accepted.  Real credential validation lives in the auth managers.
"""

from __future__ import annotations

import logging

from ..routes import RouteEntry, normalize_path
from .form import FormAuthHandler

_logger = logging.getLogger(__name__)


class FormNonceAuthHandler(FormAuthHandler):
    """Form-nonce auth handler that serves the login page on GET.

    Extends :class:`FormAuthHandler` to intercept GET requests to the
    login path and return stored login page HTML.  This mirrors the
    real modem behaviour where GET ``/cgi-bin/adv_pwd_cgi`` returns
    the login form and POST submits credentials.

    Args:
        login_path: Login endpoint path (``auth.action``).
        login_page_html: HTML body to serve on GET to ``login_path``.
        cookie_name: Session cookie name (empty for IP-based).
        logout_path: Logout endpoint path (empty if no logout).
        restart_path: Restart endpoint path (empty if no restart).
        restart_method: HTTP method for restart.
    """

    def __init__(
        self,
        login_path: str,
        login_page_html: str,
        cookie_name: str = "",
        logout_path: str = "",
        restart_path: str = "",
        restart_method: str = "POST",
    ) -> None:
        super().__init__(
            login_path=login_path,
            cookie_name=cookie_name,
            logout_path=logout_path,
            restart_path=restart_path,
            restart_method=restart_method,
        )
        self._login_page_html = login_page_html

    def is_login_request(self, method: str, path: str) -> bool:
        """GET to login page is also a login-flow request."""
        if method == "GET" and normalize_path(path) == self._login_path:
            return True
        return super().is_login_request(method, path)

    def handle_login(
        self,
        method: str,
        path: str,
        body: bytes,
        headers: dict[str, str],
    ) -> RouteEntry | None:
        """Serve login page on GET, accept credentials on POST.

        GET returns the stored login page HTML (for encoding detection).
        POST delegates to parent (sets authenticated flag, returns
        None so the route table response is used).
        """
        if method == "GET" and normalize_path(path) == self._login_path:
            _logger.debug("Mock server: serving login page for pre-fetch")
            return RouteEntry(
                status=200,
                headers=[("Content-Type", "text/html")],
                body=self._login_page_html,
            )

        # POST — delegate to parent (accepts login, returns None).
        return super().handle_login(method, path, body, headers)
