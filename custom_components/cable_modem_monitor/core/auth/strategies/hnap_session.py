"""HNAP/SOAP session-based authentication."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape as xml_escape

import requests

from ..base import AuthResult, AuthStrategy
from ..types import AuthErrorType

if TYPE_CHECKING:
    from ..configs import AuthConfig, HNAPSoapAuthConfig

_LOGGER = logging.getLogger(__name__)


class HNAPSessionAuthStrategy(AuthStrategy):
    """HNAP/SOAP session-based authentication."""

    def login(
        self,
        session: requests.Session,
        base_url: str,
        username: str | None,
        password: str | None,
        config: AuthConfig,
        verbose: bool = False,
    ) -> AuthResult:
        """Establish HNAP session."""
        if not username or not password:
            _LOGGER.warning(
                "HNAP authentication requires credentials. "
                "Username provided: %s, Password provided: %s. "
                "Please configure username and password in the integration settings.",
                bool(username),
                bool(password),
            )
            return AuthResult.fail(
                AuthErrorType.MISSING_CREDENTIALS,
                "HNAP authentication requires username and password",
            )

        from ..configs import HNAPSoapAuthConfig

        if not isinstance(config, HNAPSoapAuthConfig):
            _LOGGER.error("HNAPSessionAuthStrategy requires HNAPSoapAuthConfig")
            return AuthResult.fail(
                AuthErrorType.STRATEGY_NOT_CONFIGURED,
                "HNAPSessionAuthStrategy requires HNAPSoapAuthConfig",
            )

        try:
            # Build login SOAP envelope
            login_envelope = self._build_login_envelope(username, password, config)

            hnap_url = f"{base_url}{config.hnap_endpoint}"
            _LOGGER.debug(
                "HNAP login attempt: URL=%s, Username=%s (length=%d), Password length=%d",
                hnap_url,
                username,
                len(username) if username else 0,
                len(password) if password else 0,
            )

            response = session.post(
                hnap_url,
                data=login_envelope,
                headers={
                    "SOAPAction": f'"{config.soap_action_namespace}Login"',
                    "Content-Type": "text/xml; charset=utf-8",
                },
                timeout=10,
                verify=session.verify,
            )

            _LOGGER.debug(
                "HNAP login response: status=%d, response_length=%d bytes, content_type=%s",
                response.status_code,
                len(response.text),
                response.headers.get("Content-Type", "unknown"),
            )

            if response.status_code != 200:
                _LOGGER.error(
                    "HNAP login failed with HTTP status %s. Response preview: %s",
                    response.status_code,
                    response.text[:500] if response.text else "empty",
                )
                return AuthResult.fail(
                    AuthErrorType.INVALID_CREDENTIALS,
                    f"HNAP login failed with HTTP status {response.status_code}",
                    response_html=response.text,
                )

            # Check for session timeout indicator (means auth failed)
            if config.session_timeout_indicator in response.text:
                _LOGGER.warning(
                    "HNAP login failed: Found '%s' in response (authentication rejected). " "Response preview: %s",
                    config.session_timeout_indicator,
                    response.text[:500],
                )
                return AuthResult.fail(
                    AuthErrorType.INVALID_CREDENTIALS,
                    f"HNAP login rejected: {config.session_timeout_indicator}",
                    response_html=response.text,
                )

            # Check for JSON error responses (some MB8611 firmwares return JSON errors)
            error_indicators = [
                "SET_JSON_FORMAT_ERROR",
                "ERROR",
                '"LoginResult":"FAILED"',
                '"LoginResult": "FAILED"',
            ]
            for error_indicator in error_indicators:
                if error_indicator in response.text:
                    _LOGGER.warning(
                        "HNAP login failed: Found error indicator '%s' in response. "
                        "This may indicate the modem requires JSON-formatted HNAP requests "
                        "instead of XML/SOAP. Response preview: %s",
                        error_indicator,
                        response.text[:500],
                    )
                    return AuthResult.fail(
                        AuthErrorType.INVALID_CREDENTIALS,
                        f"HNAP login failed: {error_indicator}",
                        response_html=response.text,
                    )

            # Log success indicators
            _LOGGER.info(
                "HNAP login successful! Session established with modem. Response size: %d bytes",
                len(response.text),
            )
            _LOGGER.debug("HNAP login response preview: %s", response.text[:300])
            return AuthResult.ok(response.text)

        except requests.exceptions.Timeout as e:
            _LOGGER.error("HNAP login timeout - modem took too long to respond: %s", str(e))
            return AuthResult.fail(
                AuthErrorType.CONNECTION_FAILED,
                f"HNAP login timeout: {e}",
            )
        except requests.exceptions.ConnectionError as e:
            _LOGGER.error("HNAP login connection error - cannot reach modem: %s", str(e))
            return AuthResult.fail(
                AuthErrorType.CONNECTION_FAILED,
                f"HNAP connection error: {e}",
            )
        except Exception as e:
            _LOGGER.error("HNAP login exception: %s", str(e), exc_info=True)
            return AuthResult.fail(
                AuthErrorType.UNKNOWN_ERROR,
                f"HNAP login exception: {e}",
            )

    def _build_login_envelope(self, username: str, password: str, config: HNAPSoapAuthConfig) -> str:
        """Build SOAP login envelope for HNAP."""
        # Escape XML special characters in credentials to prevent malformed XML
        safe_username = xml_escape(username)
        safe_password = xml_escape(password)

        envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
  xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <Login xmlns="{config.soap_action_namespace}">
      <Username>{safe_username}</Username>
      <Password>{safe_password}</Password>
      <Captcha></Captcha>
    </Login>
  </soap:Body>
</soap:Envelope>"""
        _LOGGER.debug(
            "HNAP SOAP envelope built: namespace=%s, envelope_size=%d bytes",
            config.soap_action_namespace,
            len(envelope),
        )
        return envelope
