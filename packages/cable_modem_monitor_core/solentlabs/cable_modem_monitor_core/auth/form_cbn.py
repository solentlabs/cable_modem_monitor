"""CBN (Compal Broadband Networks) AES-256-CBC encrypted form auth manager.

Replicates the browser-side login flow from Compal modem firmware:

1. **GET login page** — receive ``sessionToken`` cookie.
2. **Encrypt password** — ``compal_encrypt(password, sessionToken)``
   using AES-256-CBC with key=SHA256(token), IV=MD5(token).
3. **POST login** — send to ``setter_endpoint`` with
   ``token=<tok>&fun=<login_fun>&Username=<username>&Password=<encrypted>``.
4. **Check response** — body contains ``"successful"`` and ``SID=<N>``.
5. **Set SID cookie** — extracted from response body, stored on session.

Requires the ``cryptography`` package: install Core with ``[cbn]``.

See MODEM_YAML_SPEC.md ``form_cbn`` strategy.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import requests

from ..models.modem_config.auth import FormCbnAuth
from ..protocol.cbn import compal_encrypt
from .base import AuthContext, AuthResult, BaseAuthManager

_logger = logging.getLogger(__name__)

_SID_RE = re.compile(r"SID=(\d+)")


class FormCbnAuthManager(BaseAuthManager):
    """CBN AES-256-CBC encrypted form auth.

    Args:
        config: Validated ``FormCbnAuth`` config from modem.yaml.
    """

    def __init__(self, config: FormCbnAuth) -> None:
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
        """Execute the CBN encrypted login flow.

        Args:
            session: Session to configure with auth state.
            base_url: Modem base URL.
            username: Username credential (ignored — CBN uses username_value).
            password: Password credential.
            timeout: Per-request timeout in seconds.
            log_level: Logging level for non-error messages.

        Returns:
            AuthResult with success flag.
        """
        log = _logger.log
        config = self._config

        # Step 1: GET login page to receive sessionToken cookie
        login_page_url = f"{base_url}{config.login_page}"
        log(log_level, "CBN auth: fetching login page %s", login_page_url)
        try:
            response = session.get(login_page_url, timeout=timeout)
        except requests.RequestException as exc:
            return AuthResult(
                success=False,
                error=f"Failed to fetch login page: {exc}",
            )

        if not response.ok:
            return AuthResult(
                success=False,
                error=f"Login page returned HTTP {response.status_code}",
            )

        # Step 2: Read sessionToken from cookies
        session_token = session.cookies.get(config.session_cookie_name)
        if not session_token:
            return AuthResult(
                success=False,
                error=f"Login page did not set '{config.session_cookie_name}' cookie",
            )

        # Step 3: Encrypt password
        try:
            encrypted = compal_encrypt(password, session_token)
        except ImportError as exc:
            return AuthResult(success=False, error=str(exc))

        # Step 4: POST login — token must be first parameter
        setter_url = f"{base_url}{config.setter_endpoint}"
        post_body = (
            f"token={session_token}"
            f"&fun={config.login_fun}"
            f"&Username={config.username_value}"
            f"&Password={encrypted}"
        )
        log(log_level, "CBN auth: posting login to %s", setter_url)
        try:
            login_response = session.post(
                setter_url,
                data=post_body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=timeout,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            return AuthResult(
                success=False,
                error=f"Login POST failed: {exc}",
            )

        # Step 5: Check response for success + extract SID
        # Status must be 200 — a 302 redirect to the login page would
        # contain "successful" in JS templates, causing false-positive.
        if login_response.status_code != 200:
            return AuthResult(
                success=False,
                error=f"Login POST returned HTTP {login_response.status_code}",
            )

        body = login_response.text
        if "successful" not in body.lower():
            return AuthResult(
                success=False,
                error=f"Login failed: {body[:200]}",
            )

        sid_match = _SID_RE.search(body)
        if not sid_match:
            return AuthResult(
                success=False,
                error="Login successful but SID not found in response",
            )

        # Step 6: Set SID cookie on session
        sid_value = sid_match.group(1)
        hostname = urlparse(base_url).hostname or ""
        session.cookies.set(config.sid_cookie_name, sid_value, domain=hostname)
        log(log_level, "CBN auth: SID=%s set on session", sid_value)

        return AuthResult(
            success=True,
            auth_context=AuthContext(),
            response=login_response,
            response_url=config.setter_endpoint,
        )
