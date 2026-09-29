"""JSON-RPC 2.0 login: one call on the transport's endpoint, token back in the query. See AUTH_JSONRPC_SPEC.md."""

from __future__ import annotations

import logging

import requests

from ..models.modem_config.auth import JsonrpcAuth
from ..protocol.jsonrpc import call_url, parse_reply, post_call
from .base import AuthContext, AuthResult, BaseAuthManager, LoginLockoutError
from .response import extract_token

_logger = logging.getLogger(__name__)


class JsonrpcAuthManager(BaseAuthManager):
    """Logs in with the entry's login method and sends the token as ``?<token_param>=``."""

    def __init__(self, config: JsonrpcAuth) -> None:
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
        _logger.log(log_level, "JSON-RPC login: %s %s", config.login_method, config.endpoint)

        # The login call carries no token; one does not exist yet.
        credentials = {config.username_field: username, config.password_field: password}
        response = post_call(
            session,
            call_url(base_url, config.endpoint, "", ""),
            config.login_method,
            [credentials],
            timeout=timeout,
        )

        # Every reply below attaches the response for the collector's failure
        # log, and none offers it for reuse: a login reply is not a data page.
        if not 200 <= response.status_code < 300:
            return AuthResult(success=False, error=f"Login returned HTTP {response.status_code}", response=response)

        reply = parse_reply(response)
        if reply is None:
            return AuthResult(success=False, error="Login reply is not a JSON-RPC response", response=response)

        if reply.is_error:
            if config.lockout_code and reply.error_code == config.lockout_code:
                raise LoginLockoutError(f"JSON-RPC firmware anti-brute-force triggered: {reply.error_code}")
            # The firmware's own login form shows any other code as a login
            # error and clears the password field (AUTH_JSONRPC_SPEC § Error Codes).
            return AuthResult(success=False, error=f"Login rejected: {reply.error_code}", response=response)

        token = extract_token(reply.result, config.token_path)
        if not token:
            return AuthResult(
                success=False,
                error=f"token_path '{config.token_path}' not found in login result",
                response=response,
            )

        _logger.log(log_level, "JSON-RPC token obtained via result.%s", config.token_path)
        return AuthResult(success=True, auth_context=AuthContext(token=token, url_token=token))

    def loader_url_token(self, session: requests.Session, context: AuthContext | None) -> tuple[str, str]:
        """``(<token_param>=, token)`` once a login produced one; empty before."""
        if context is None or not context.url_token:
            return ("", "")
        return (f"{self._config.token_param}=", context.url_token)


def create_manager(config: JsonrpcAuth) -> JsonrpcAuthManager:
    """Entry point for dynamic auth factory dispatch."""
    return JsonrpcAuthManager(config)
