"""Form-based authentication with configurable password encoding.

This strategy handles all form-based authentication variants:
- Plain password (default)
- Base64-encoded password
- Combined credential mode (single field with formatted value)

The password_encoding field in FormAuthConfig controls encoding behavior.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, urljoin

from ..base import AuthResult, AuthStrategy
from ..detection import is_login_page
from ..types import AuthErrorType

if TYPE_CHECKING:
    import requests

    from ..configs import AuthConfig, FormAuthConfig, FormDynamicAuthConfig

_LOGGER = logging.getLogger(__name__)


class FormPlainAuthStrategy(AuthStrategy):
    """Form-based authentication with configurable encoding.

    Supports:
    - Traditional mode: Separate username/password fields
    - Combined mode: Single field with formatted credentials
    - Password encoding: plain or base64
    - Hidden fields for CSRF tokens etc.
    - GET or POST submission
    """

    def login(
        self,
        session: requests.Session,
        base_url: str,
        username: str | None,
        password: str | None,
        config: AuthConfig,
        verbose: bool = False,
    ) -> AuthResult:
        """Submit form with configured encoding and fields."""
        log = _LOGGER.info if verbose else _LOGGER.debug

        if not username or not password:
            _LOGGER.warning("Form auth configured but no credentials provided")
            return AuthResult.fail(
                AuthErrorType.MISSING_CREDENTIALS,
                "Form auth requires username and password",
            )

        from ..configs import FormAuthConfig, FormDynamicAuthConfig

        if not isinstance(config, FormAuthConfig | FormDynamicAuthConfig):
            _LOGGER.error("FormPlainAuthStrategy requires FormAuthConfig or FormDynamicAuthConfig")
            return AuthResult.fail(
                AuthErrorType.STRATEGY_NOT_CONFIGURED,
                "FormPlainAuthStrategy requires FormAuthConfig or FormDynamicAuthConfig",
            )

        if not config.login_url:
            _LOGGER.warning("Form auth configured but no login_url provided")
            return AuthResult.fail(
                AuthErrorType.STRATEGY_NOT_CONFIGURED,
                "Form auth requires form_config (login URL, field names)",
            )

        return self._execute_form_login(session, base_url, username, password, config, log)

    def _execute_form_login(
        self,
        session: requests.Session,
        base_url: str,
        username: str,
        password: str,
        config: FormAuthConfig | FormDynamicAuthConfig,
        log,
    ) -> AuthResult:
        """Execute the form login request and evaluate response."""
        form_data = self._build_form_data(config, username, password, log)
        action_path = self._get_action_path(session, base_url, config, log)
        action_url = self._resolve_url(base_url, action_path)

        # Technicolor API login flow expects a bootstrap probe password first.
        if self._is_api_login_endpoint(action_url):
            self._prepare_api_login_session(session, base_url, config.timeout, log)
            form_data = dict(form_data)
            form_data[config.password_field] = "seeksalthash"

        log("Form auth: submitting to %s (method=%s, timeout=%d)", action_url, config.method, config.timeout)

        try:
            response = self._submit_form(session, action_url, form_data, base_url, config.method, config.timeout)
            self._log_response(response, session, log)
            bootstrap_result = self._maybe_retry_with_salt_bootstrap(
                session=session,
                base_url=base_url,
                action_url=action_url,
                config=config,
                form_data=form_data,
                response=response,
                log=log,
            )
            if isinstance(bootstrap_result, AuthResult):
                return bootstrap_result
            if bootstrap_result is not None:
                response = bootstrap_result
            challenge_result = self._maybe_complete_salt_challenge(
                session=session,
                base_url=base_url,
                action_url=action_url,
                username=username,
                password=password,
                config=config,
                response=response,
                log=log,
            )
            if isinstance(challenge_result, AuthResult):
                return challenge_result
            if challenge_result is not None:
                response = challenge_result
            return self._evaluate_response(session, base_url, action_url, response, config, log)
        except Exception as e:
            _LOGGER.warning("Form auth failed: %s", e)
            return AuthResult.fail(AuthErrorType.CONNECTION_FAILED, f"Form submission failed: {e}")

    def _get_action_path(
        self,
        session: requests.Session,
        base_url: str,
        config: FormAuthConfig | FormDynamicAuthConfig,
        log,
    ) -> str:
        """Get the form action path.

        Override in subclasses (e.g., FormDynamicAuthStrategy) to extract
        the action URL from the login page instead of using the static config value.

        Args:
            session: Requests session
            base_url: Modem base URL
            config: Form auth configuration
            log: Logger function

        Returns:
            Form action path (relative or absolute URL)
        """
        return config.login_url

    def _submit_form(
        self,
        session: requests.Session,
        action_url: str,
        form_data: dict,
        base_url: str,
        method: str,
        timeout: int,
    ) -> requests.Response:
        """Submit the form via POST or GET."""
        headers = self._build_form_headers(session, base_url, action_url)

        if method.upper() == "POST":
            return session.post(
                action_url,
                data=form_data,
                headers=headers,
                timeout=timeout,
                allow_redirects=True,
                verify=session.verify,
            )
        return session.get(
            action_url,
            params=form_data,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
            verify=session.verify,
        )

    def _log_response(self, response: requests.Response, session: requests.Session, log) -> None:
        """Log response details for debugging."""
        try:
            cookies_after = list(session.cookies.keys()) if session.cookies else []
        except (AttributeError, TypeError):
            cookies_after = []
        log(
            "Form submission: HTTP %d, %d bytes, cookies=%s",
            response.status_code,
            len(response.text),
            cookies_after if cookies_after else "none",
        )

    def _evaluate_response(
        self,
        session: requests.Session,
        base_url: str,
        action_url: str,
        response: requests.Response,
        config: FormAuthConfig | FormDynamicAuthConfig,
        log,
    ) -> AuthResult:
        """Evaluate response to determine if login succeeded."""
        if response.status_code >= 400:
            _LOGGER.warning("Form login failed: HTTP %d", response.status_code)
            return AuthResult.fail(
                AuthErrorType.INVALID_CREDENTIALS if response.status_code in (401, 403) else AuthErrorType.CONNECTION_FAILED,
                f"Form login failed: HTTP {response.status_code}",
                response_html=response.text,
            )

        json_payload = self._try_parse_json(response)
        if json_payload and str(json_payload.get("error", "")).lower() not in ("", "ok"):
            message = str(json_payload.get("message") or "Invalid credentials")
            _LOGGER.warning("Form login failed: %s", message)
            return AuthResult.fail(
                AuthErrorType.INVALID_CREDENTIALS,
                f"Invalid credentials - {message}",
                response_html=response.text,
            )

        if self._is_api_login_endpoint(action_url):
            already_verified = bool(getattr(session, "_cmm_api_session_verified", False))
            if not already_verified and not self._prime_api_session(session, base_url, config.timeout, log):
                return AuthResult.fail(
                    AuthErrorType.INVALID_CREDENTIALS,
                    "Invalid credentials - modem session not authorized after login",
                    response_html=response.text,
                )

        # Check success_redirect first (URL path validation)
        if config.success_redirect:
            if config.success_redirect in response.url:
                log("Form auth successful - redirected to expected URL: %s", config.success_redirect)
                return AuthResult.ok(response.text)
            # Redirect URL expected but not matched - log warning and fall back to is_login_page()
            # This is a soft-fail: modem.yaml redirect configs may be incorrect guesses.
            # Log at INFO so we capture this in diagnostics for future correction.
            _LOGGER.info(
                "Form auth: expected redirect to '%s' but got '%s' - falling back to login page detection",
                config.success_redirect,
                response.url,
            )
            # Fall through to is_login_page() check below

        # Check success_indicator (content/size validation - legacy)
        if config.success_indicator:
            return self._check_success_indicator(response, config)

        # No success criteria matched - check if response is a login page
        if is_login_page(response.text):
            return self._verify_with_base_url(session, base_url, log, config.timeout)

        # If response is NOT a login page, consider login successful
        # Return the HTML for discovery validation (parser detection, validation step)
        log("Form auth successful - form response is not a login page")
        return AuthResult.ok(response.text)

    def _check_success_indicator(
        self, response: requests.Response, config: FormAuthConfig | FormDynamicAuthConfig
    ) -> AuthResult:
        """Check if success indicator is present in response.

        Legacy method for content/size checks. Prefer success_redirect for URL validation.
        """
        indicator = config.success_indicator
        if not indicator:
            return AuthResult.ok(response.text)

        # Content string check (indicator appears in response body or URL)
        if indicator in response.text or indicator in response.url:
            _LOGGER.debug("Form login successful (success indicator '%s' found)", indicator)
            return AuthResult.ok(response.text)

        # Size check (indicator is a number = minimum response size)
        if indicator.isdigit() and len(response.text) > int(indicator):
            _LOGGER.debug("Form login successful (response size %d > %s)", len(response.text), indicator)
            return AuthResult.ok(response.text)

        _LOGGER.warning("Form login failed: success indicator '%s' not found", indicator)
        return AuthResult.fail(
            AuthErrorType.INVALID_CREDENTIALS,
            f"Form login failed: success indicator '{indicator}' not found",
            response_html=response.text,
        )

    def _verify_with_base_url(self, session: requests.Session, base_url: str, log, timeout: int) -> AuthResult:
        """Verify login by fetching base URL (for cookie-based auth)."""
        headers = {"Referer": base_url}
        data_response = session.get(base_url, headers=headers, timeout=timeout, verify=session.verify)
        log(
            "Post-login base URL: HTTP %d, %d bytes, is_login=%s",
            data_response.status_code,
            len(data_response.text),
            is_login_page(data_response.text),
        )

        if data_response.status_code == 200:
            if is_login_page(data_response.text):
                _LOGGER.warning("Form auth failed - still on login page after submission")
                return AuthResult.fail(
                    AuthErrorType.INVALID_CREDENTIALS,
                    "Invalid credentials - login form returned after submission",
                )
            log("Form auth successful - base URL has no login form")
            return AuthResult.ok(data_response.text)

        return AuthResult.ok()

    def _build_form_data(
        self, config: FormAuthConfig | FormDynamicAuthConfig, username: str, password: str, log
    ) -> dict:
        """Build form data based on configuration mode."""
        hidden_fields = dict(config.hidden_fields) if config.hidden_fields else {}

        # Check for combined credential mode
        if config.credential_field and config.credential_format:
            return self._build_combined_form_data(config, username, password, hidden_fields, log)

        return self._build_traditional_form_data(config, username, password, hidden_fields, log)

    def _build_combined_form_data(
        self,
        config: FormAuthConfig | FormDynamicAuthConfig,
        username: str,
        password: str,
        hidden_fields: dict,
        log,
    ) -> dict:
        """Build form data for combined credential mode."""
        # credential_format is guaranteed non-None when this method is called
        assert config.credential_format is not None
        credential_string = config.credential_format.format(username=username, password=password)
        url_encoded = quote(credential_string, safe="@*_+-./")
        encoded_value = base64.b64encode(url_encoded.encode("utf-8")).decode("utf-8")

        log("Combined credential auth: field=%s, format=%s", config.credential_field, config.credential_format)
        return {config.credential_field: encoded_value, **hidden_fields}

    def _build_traditional_form_data(
        self,
        config: FormAuthConfig | FormDynamicAuthConfig,
        username: str,
        password: str,
        hidden_fields: dict,
        log,
    ) -> dict:
        """Build form data for traditional username/password fields."""
        encoded_password = password
        password_was_encoded = False

        if config.password_encoding == "base64" and password:
            url_encoded = quote(password, safe="@*_+-./")
            encoded_password = base64.b64encode(url_encoded.encode("utf-8")).decode("utf-8")
            password_was_encoded = True
            log("Password encoded: URL-escape then base64 (password_encoding=base64)")

        log(
            "Form auth: encoded=%s, user_field=%s, pass_field=%s",
            password_was_encoded,
            config.username_field,
            config.password_field,
        )
        return {config.username_field: username, config.password_field: encoded_password, **hidden_fields}

    def _resolve_url(self, base_url: str, path: str) -> str:
        """Resolve relative URL against base."""
        if path.startswith("http"):
            return path
        return urljoin(base_url + "/", path)

    def _is_api_login_endpoint(self, action_url: str) -> bool:
        """Check if action URL is the Technicolor-style API login endpoint."""
        return "/api/v1/session/login" in action_url

    def _prepare_api_login_session(
        self,
        session: requests.Session,
        base_url: str,
        timeout: int,
        log,
    ) -> None:
        """Prime pre-login API session to mirror browser flow."""
        self._set_api_session_cookies(session)
        setattr(session, "_cmm_api_session_verified", False)

        timestamp = int(time.time() * 1000)
        preflight_calls = [
            (f"{base_url}/api/v1/session/language?_={timestamp}", "*/*"),
            (f"{base_url}/api/v1/session/menu?_={timestamp + 1}", "*/*"),
            (f"{base_url}/views/login.html?_={timestamp + 2}", "text/html, */*; q=0.01"),
        ]

        for url, accept in preflight_calls:
            try:
                response = session.get(
                    url,
                    headers={
                        "Referer": f"{base_url}/",
                        "X-Requested-With": "XMLHttpRequest",
                        "Accept": accept,
                    },
                    timeout=timeout,
                    verify=session.verify,
                )
                log("Form auth: preflight %s returned HTTP %d", url.rsplit("/", 1)[-1], response.status_code)
            except Exception as e:
                # Best-effort only: some firmware may not expose all preflight endpoints.
                log("Form auth: preflight call failed for %s (%s)", url.rsplit("/", 1)[-1], e)

    def _build_form_headers(
        self,
        session: requests.Session,
        base_url: str,
        action_url: str,
        *,
        ajax: bool = False,
    ) -> dict[str, str]:
        """Build request headers for form submissions."""
        referer = base_url if base_url.endswith("/") else f"{base_url}/"
        headers: dict[str, str] = {"Referer": referer}

        if ajax or "/api/" in action_url:
            headers["Origin"] = base_url
            headers["X-Requested-With"] = "XMLHttpRequest"
            headers["Accept"] = "*/*"
            csrf = self._get_session_header(session, "X-CSRF-TOKEN")
            if csrf:
                headers["X-CSRF-TOKEN"] = csrf

        return headers

    def _get_session_header(self, session: requests.Session, name: str) -> str | None:
        """Safely read a header from session.headers."""
        headers = getattr(session, "headers", None)
        if headers is None:
            return None
        try:
            value = headers.get(name)
        except Exception:
            return None
        return str(value) if value else None

    def _try_parse_json(self, response: requests.Response) -> dict[str, Any] | None:
        """Parse JSON payload from response when present."""
        content_type = ""
        try:
            content_type = str(response.headers.get("Content-Type", "")).lower()
        except Exception:
            pass

        text = response.text if isinstance(response.text, str) else ""
        if "json" not in content_type and not text.strip().startswith("{"):
            return None

        parsed: Any
        try:
            parsed = response.json()
        except Exception:
            try:
                parsed = json.loads(text)
            except Exception:
                return None

        return parsed if isinstance(parsed, dict) else None

    def _maybe_retry_with_salt_bootstrap(
        self,
        session: requests.Session,
        base_url: str,
        action_url: str,
        config: FormAuthConfig | FormDynamicAuthConfig,
        form_data: dict[str, Any],
        response: requests.Response,
        log,
    ) -> requests.Response | AuthResult | None:
        """Retry login probe with placeholder password to obtain salt challenge."""
        if not self._is_api_login_endpoint(action_url):
            return None

        payload = self._try_parse_json(response)
        if not payload:
            return None

        if str(payload.get("error", "")).lower() == "ok":
            return None

        message = str(payload.get("message") or "")
        if message != "MSG_LOGIN_150":
            _LOGGER.warning("Form login failed after bootstrap probe: %s", message or "Invalid credentials")
            return AuthResult.fail(
                AuthErrorType.INVALID_CREDENTIALS,
                f"Invalid credentials - {message or 'Invalid credentials'}",
                response_html=response.text,
            )

        log("Form auth: modem reports active session, retrying bootstrap with logout=true")

        try:
            bootstrap_response = self._submit_bootstrap_probe(
                session=session,
                base_url=base_url,
                action_url=action_url,
                config=config,
                form_data=form_data,
                logout_existing_session=True,
                log=log,
            )
        except Exception as e:
            _LOGGER.warning("Form auth bootstrap probe failed: %s", e)
            return AuthResult.fail(AuthErrorType.CONNECTION_FAILED, f"Bootstrap probe failed: {e}")

        bootstrap_payload = self._try_parse_json(bootstrap_response)
        bootstrap_error = str((bootstrap_payload or {}).get("error", "")).lower()
        if bootstrap_error in ("", "ok"):
            return bootstrap_response

        bootstrap_message = str((bootstrap_payload or {}).get("message") or "Invalid credentials")

        _LOGGER.warning("Form login failed after bootstrap probe: %s", bootstrap_message)
        return AuthResult.fail(
            AuthErrorType.INVALID_CREDENTIALS,
            f"Invalid credentials - {bootstrap_message}",
            response_html=bootstrap_response.text,
        )

    def _submit_bootstrap_probe(
        self,
        session: requests.Session,
        base_url: str,
        action_url: str,
        config: FormAuthConfig | FormDynamicAuthConfig,
        form_data: dict[str, Any],
        *,
        logout_existing_session: bool,
        log,
    ) -> requests.Response:
        """Send bootstrap probe (`password=seeksalthash`) for API login flow."""
        bootstrap_data = dict(form_data)
        bootstrap_data[config.password_field] = "seeksalthash"
        if logout_existing_session:
            bootstrap_data["logout"] = "true"

        bootstrap_response = session.post(
            action_url,
            data=bootstrap_data,
            headers=self._build_form_headers(session, base_url, action_url, ajax=True),
            timeout=config.timeout,
            allow_redirects=True,
            verify=session.verify,
        )
        self._log_response(bootstrap_response, session, log)

        return bootstrap_response

    def _maybe_complete_salt_challenge(
        self,
        session: requests.Session,
        base_url: str,
        action_url: str,
        username: str,
        password: str,
        config: FormAuthConfig | FormDynamicAuthConfig,
        response: requests.Response,
        log,
    ) -> requests.Response | AuthResult | None:
        """Complete Technicolor-style 2-step salted PBKDF2 login when prompted."""
        payload = self._try_parse_json(response)
        if not payload:
            return None
        if str(payload.get("error", "")).lower() not in ("", "ok"):
            return None

        salt = payload.get("salt")
        saltwebui = payload.get("saltwebui")
        if not isinstance(salt, str) or not isinstance(saltwebui, str):
            return None

        log("Form auth: detected salt challenge in login response")

        challenge_password = password
        if salt.lower() != "none":
            first_hash = self._pbkdf2_sha256_hex(password, salt)
            challenge_password = self._pbkdf2_sha256_hex(first_hash, saltwebui)

        hidden_fields = dict(config.hidden_fields) if config.hidden_fields else {}
        challenge_form_data = self._build_traditional_form_data(
            config,
            username,
            challenge_password,
            hidden_fields,
            log,
        )

        try:
            challenge_response = session.post(
                action_url,
                data=challenge_form_data,
                headers=self._build_form_headers(session, base_url, action_url, ajax=True),
                timeout=config.timeout,
                allow_redirects=True,
                verify=session.verify,
            )
            self._log_response(challenge_response, session, log)
        except Exception as e:
            _LOGGER.warning("Form auth salt challenge failed: %s", e)
            return AuthResult.fail(AuthErrorType.CONNECTION_FAILED, f"Salt challenge failed: {e}")

        challenge_payload = self._try_parse_json(challenge_response)
        if challenge_payload and str(challenge_payload.get("error", "")).lower() not in ("", "ok"):
            message = str(challenge_payload.get("message") or "Invalid credentials")
            _LOGGER.warning("Salt challenge login failed: %s", message)
            return AuthResult.fail(
                AuthErrorType.INVALID_CREDENTIALS,
                f"Invalid credentials - {message}",
                response_html=challenge_response.text,
            )

        # Prime API session to mimic browser boot sequence and verify auth is active.
        if not self._prime_api_session(session, base_url, config.timeout, log):
            return AuthResult.fail(
                AuthErrorType.INVALID_CREDENTIALS,
                "Invalid credentials - modem session not authorized after salt challenge",
                response_html=challenge_response.text,
            )

        return challenge_response

    def _pbkdf2_sha256_hex(self, password: str, salt: str) -> str:
        """Mirror Technicolor login script: sjcl.pbkdf2(pass, salt, 1000, 128) as hex."""
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            1000,
            dklen=16,
        )
        return derived.hex()

    def _set_api_session_cookies(self, session: requests.Session) -> None:
        """Ensure browser-like cookies exist for API requests."""
        session.cookies.set("theme-value", "css/theme/dark/", path="/")
        session.cookies.set("time", str(int(time.time())), path="/")

    def _prime_api_session(self, session: requests.Session, base_url: str, timeout: int, log) -> bool:
        """Warm up API session and verify protected menu endpoint is authorized."""
        self._set_api_session_cookies(session)
        setattr(session, "_cmm_api_session_verified", False)

        try:
            timestamp = int(time.time() * 1000)
            language_url = f"{base_url}/api/v1/session/language?_={timestamp}"
            language_response = session.get(
                language_url,
                headers={"Referer": f"{base_url}/", "X-Requested-With": "XMLHttpRequest", "Accept": "*/*"},
                timeout=timeout,
                verify=session.verify,
            )
            log(
                "Form auth: API warmup /api/v1/session/language returned HTTP %d",
                language_response.status_code,
            )

            menu_url = f"{base_url}/api/v1/session/menu?_={timestamp + 1}"
            menu_response = session.get(
                menu_url,
                headers={"Referer": f"{base_url}/", "X-Requested-With": "XMLHttpRequest", "Accept": "*/*"},
                timeout=timeout,
                verify=session.verify,
            )
            log("Form auth: API warmup /api/v1/session/menu returned HTTP %d", menu_response.status_code)
            if menu_response.status_code != 200:
                return False

            menu_payload = self._try_parse_json(menu_response)
            if menu_payload and str(menu_payload.get("error", "")).lower() not in ("", "ok"):
                log("Form auth: API warmup menu unauthorized (%s)", menu_payload.get("message"))
                return False

            model_url = f"{base_url}/api/v1/system/ModelName?_={timestamp + 2}"
            model_response = session.get(
                model_url,
                headers={"Referer": f"{base_url}/", "X-Requested-With": "XMLHttpRequest", "Accept": "*/*"},
                timeout=timeout,
                verify=session.verify,
            )
            log("Form auth: API warmup /api/v1/system/ModelName returned HTTP %d", model_response.status_code)

            model_payload = self._try_parse_json(model_response)
            token = str((model_payload or {}).get("token") or "")
            if token:
                try:
                    session.headers["X-CSRF-TOKEN"] = token
                except Exception:
                    pass

            setattr(session, "_cmm_api_session_verified", True)
            return True
        except Exception as e:
            log("Form auth: API warmup request failed (%s)", e)
            return False
