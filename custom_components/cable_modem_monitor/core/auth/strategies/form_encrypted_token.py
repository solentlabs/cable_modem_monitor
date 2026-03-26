"""AES-encrypted token authentication for Compal modems.

This strategy handles authentication for Compal CH7465MT (and similar) modems
that use AES-256-CBC encrypted passwords derived from a session token cookie.

Pattern (from CBN_Encrypt in encrypt_cryptoJS.js):
1. GET login page -> server sets sessionToken cookie
2. Derive AES key from token: key=SHA256(token), iv=MD5(token)
3. Encrypt password with AES-256-CBC + PKCS7 padding
4. Encode as base64(":" + hex(ciphertext))
5. POST to setter.xml with fun=15, Username=NULL, Password=encrypted, token=sessionToken
6. Response: "successful SID=NNNNN" -> store SID as cookie
"""

from __future__ import annotations

import base64
import hashlib
import logging
import re
from typing import TYPE_CHECKING
from urllib.parse import urljoin

from ..base import AuthResult, AuthStrategy, get_cookie_safe
from ..types import AuthErrorType

if TYPE_CHECKING:
    import requests

    from ..configs import FormEncryptedTokenAuthConfig

_LOGGER = logging.getLogger(__name__)


class FormEncryptedTokenStrategy(AuthStrategy):
    """AES-encrypted token auth for Compal cable modems.

    Used by Compal CH7465MT (Magenta/UPC/Ziggo Connect Box) and similar
    modems that implement CBN_Encrypt JavaScript-based authentication.
    """

    def login(
        self,
        session: requests.Session,
        base_url: str,
        username: str | None,
        password: str | None,
        config,
        verbose: bool = False,
    ) -> AuthResult:
        """Authenticate with AES-encrypted password."""
        log = _LOGGER.info if verbose else _LOGGER.debug

        if not password:
            _LOGGER.warning("FormEncryptedToken auth requires a password")
            return AuthResult.fail(
                AuthErrorType.MISSING_CREDENTIALS,
                "FormEncryptedToken auth requires a password",
            )

        from ..configs import FormEncryptedTokenAuthConfig

        if not isinstance(config, FormEncryptedTokenAuthConfig):
            _LOGGER.error("FormEncryptedTokenStrategy requires FormEncryptedTokenAuthConfig")
            return AuthResult.fail(
                AuthErrorType.STRATEGY_NOT_CONFIGURED,
                "FormEncryptedTokenStrategy requires FormEncryptedTokenAuthConfig",
            )

        return self._execute_login(session, base_url, password, config, log)

    def _execute_login(
        self,
        session: requests.Session,
        base_url: str,
        password: str,
        config: FormEncryptedTokenAuthConfig,
        log,
    ) -> AuthResult:
        """Execute the encrypted token login flow."""
        try:
            # Step 1: GET login page to obtain sessionToken cookie
            login_url = self._resolve_url(base_url, config.login_page)
            log("FormEncryptedToken: fetching login page %s", login_url)

            response = session.get(
                login_url,
                timeout=config.timeout,
                verify=session.verify,
            )

            # Store login page HTML for the orchestrator
            login_page_html = response.text

            if not response.ok:
                _LOGGER.warning(
                    "FormEncryptedToken: login page returned HTTP %d",
                    response.status_code,
                )
                return AuthResult.fail(
                    AuthErrorType.CONNECTION_FAILED,
                    f"Login page returned HTTP {response.status_code}",
                )

            # Step 2: Read sessionToken from cookie
            session_token = get_cookie_safe(session, config.session_cookie_name)
            if not session_token:
                _LOGGER.warning("FormEncryptedToken: no %s cookie received", config.session_cookie_name)
                return AuthResult.fail(
                    AuthErrorType.UNKNOWN_ERROR,
                    f"No {config.session_cookie_name} cookie received from login page",
                )

            log("FormEncryptedToken: got session token cookie")

            # Step 3: Encrypt password
            encrypted_password = self._cbn_encrypt(password, session_token)
            log("FormEncryptedToken: password encrypted")

            # Step 4: POST login credentials to setter.xml
            setter_url = self._resolve_url(base_url, config.setter_endpoint)
            form_data = {
                "token": session_token,
                "fun": str(config.login_fun),
                "Username": config.username_value,
                "Password": encrypted_password,
            }

            log("FormEncryptedToken: posting login to %s", setter_url)
            login_response = session.post(
                setter_url,
                data=form_data,
                headers={"Referer": login_url},
                timeout=config.timeout,
                verify=session.verify,
                allow_redirects=False,
            )

            response_text = login_response.text.strip()
            log(
                "FormEncryptedToken: setter.xml status=%d, size=%d, body=%s",
                login_response.status_code, len(response_text), response_text[:100],
            )

            # Step 5: Parse response - must be 200 with "successful;SID=NNNNN"
            # CRITICAL: Don't just check text content - a 302 redirect followed to
            # the login page would contain "successful" in JS templates (id="successful")
            if login_response.status_code != 200 or "successful" not in response_text:
                _LOGGER.warning("FormEncryptedToken: login failed: %s", response_text[:200])
                return AuthResult.fail(
                    AuthErrorType.INVALID_CREDENTIALS,
                    f"Login failed: {response_text[:200]}",
                )

            # Extract SID from response
            sid_match = re.search(r"SID=(\d+)", response_text)
            if sid_match:
                sid = sid_match.group(1)
                # Domain must match the modem's hostname, otherwise requests
                # won't send the cookie (empty domain doesn't match IP addresses)
                from urllib.parse import urlparse
                domain = urlparse(base_url).hostname or ""
                session.cookies.set(config.sid_cookie_name, sid, path="/", domain=domain)
                log("FormEncryptedToken: stored SID cookie (domain=%s)", domain)
            else:
                _LOGGER.warning("FormEncryptedToken: login successful but no SID found in response")

            log("FormEncryptedToken: login successful")
            return AuthResult.ok(response_html=login_page_html, session_token=session_token)

        except Exception as e:
            _LOGGER.warning("FormEncryptedToken: login failed with error: %s", e)
            return AuthResult.fail(
                AuthErrorType.CONNECTION_FAILED,
                f"Login failed: {e}",
            )

    @staticmethod
    def _cbn_encrypt(password: str, session_token: str) -> str:
        """Replicate CBN_Encrypt from Compal encrypt_cryptoJS.js.

        JavaScript equivalent:
            var key = CryptoJS.SHA256(sessionToken);
            var iv = CryptoJS.MD5(sessionToken);
            var ciphertext = CryptoJS.AES.encrypt(
                CryptoJS.enc.Utf8.parse(password), key, {iv: iv, mode: CBC, padding: Pkcs7}
            ).toString();
            ciphertext = CryptoJS.enc.Base64.parse(ciphertext);
            return $.base64.encode(":" + ciphertext.toString());

        Args:
            password: Plain text password
            session_token: Value of the sessionToken cookie

        Returns:
            Encrypted password string for the login POST
        """
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import pad

        # Derive key and IV from session token
        key = hashlib.sha256(session_token.encode("utf-8")).digest()  # 32 bytes
        iv = hashlib.md5(session_token.encode("utf-8")).digest()  # 16 bytes

        # AES-256-CBC encrypt with PKCS7 padding
        cipher = AES.new(key, AES.MODE_CBC, iv)
        ciphertext = cipher.encrypt(pad(password.encode("utf-8"), AES.block_size))

        # Convert to hex string, prepend ":", then base64 encode
        hex_ciphertext = ciphertext.hex()
        return base64.b64encode((":" + hex_ciphertext).encode("utf-8")).decode("utf-8")

    def _resolve_url(self, base_url: str, path: str) -> str:
        """Resolve relative URL against base."""
        if path.startswith("http"):
            return path
        return urljoin(base_url + "/", path)
