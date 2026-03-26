"""XML POST loader for Compal cable modems.

Handles fetching data from Compal modems that expose an XML API via POST
requests to getter.xml with fun=N parameters.

Used by: Compal CH7465MT (Magenta/UPC/Ziggo Connect Box)
"""

from __future__ import annotations

import logging
from typing import Any

from .base import ResourceLoader

_LOGGER = logging.getLogger(__name__)


class XMLPostLoader(ResourceLoader):
    """Loader for modems using XML POST API.

    Data is fetched via POST to getter.xml with fun=N parameters.
    The sessionToken must be included as 'token' field in every POST.

    pages.data maps logical names to fun parameter strings:
        downstream_channels: "fun=10"
        upstream_channels: "fun=11"
        system_info: "fun=2"
        global_settings: "fun=1"
        cm_status: "fun=144"
    """

    def __init__(
        self,
        session,
        base_url: str,
        modem_config: dict[str, Any],
        verify_ssl: bool = False,
        session_token: str | None = None,
    ):
        """Initialize the XML POST loader.

        Args:
            session: Authenticated requests.Session
            base_url: Modem base URL
            modem_config: Modem configuration from modem.yaml
            verify_ssl: Whether to verify SSL certificates
            session_token: Session token for authentication
        """
        super().__init__(session, base_url, modem_config, verify_ssl)
        self._session_token = session_token
        # Resolve getter endpoint from auth config or use default
        auth_types = modem_config.get("auth", {}).get("types", {})
        encrypted_token_config = auth_types.get("form_encrypted_token", {})
        if isinstance(encrypted_token_config, dict):
            self._getter_endpoint = encrypted_token_config.get(
                "getter_endpoint", "/xml/getter.xml"
            )
        else:
            self._getter_endpoint = getattr(
                encrypted_token_config, "getter_endpoint", "/xml/getter.xml"
            )

    def fetch(self) -> dict[str, Any]:
        """Fetch all XML endpoints via POST.

        Returns:
            Dict mapping fun parameter strings to raw XML text, e.g.:
            {
                "fun=10": "<downstream_table>...</downstream_table>",
                "fun=11": "<upstream_table>...</upstream_table>",
            }
        """
        resources: dict[str, Any] = {}
        timeout = self._get_timeout()
        url = f"{self.base_url}{self._getter_endpoint}"

        cookie_name = self._get_session_cookie_name()

        for data_type, fun_param in self._get_pages_data().items():
            # fun_param is like "fun=10" - extract the number
            fun_num = fun_param.split("=")[1] if "=" in fun_param else fun_param

            # Read token FRESH before each request (token rotates after every response)
            session_token = self.session.cookies.get(cookie_name) or self._session_token

            # Token MUST be first parameter (modem's embedded web server
            # requires this order, matching the browser's cbnAjax behavior)
            form_data: dict[str, str] = {}
            if session_token:
                form_data["token"] = session_token
            form_data["fun"] = fun_num

            try:
                response = self.session.post(
                    url,
                    data=form_data,
                    headers={"Accept-Encoding": "gzip, deflate, br"},
                    timeout=timeout,
                    verify=self.verify_ssl,
                    allow_redirects=False,
                )

                if response.status_code == 200 and response.text.strip():
                    resources[fun_param] = response.text
                    _LOGGER.debug("XMLPostLoader fetched %s: %d bytes", fun_param, len(response.text))
                else:
                    _LOGGER.warning(
                        "XMLPostLoader failed to fetch %s: status %d",
                        fun_param,
                        response.status_code,
                    )
            except Exception as e:
                _LOGGER.warning("XMLPostLoader error fetching %s: %s", fun_param, e)

        # Logout to release the single-session slot so the browser can access
        # the modem between polling intervals (modem allows max 1 concurrent session)
        self._logout(cookie_name, timeout)

        return resources

    def _logout(self, cookie_name: str, timeout: int) -> None:
        """Send logout to release the modem session."""
        auth_types = self.modem_config.get("auth", {}).get("types", {})
        encrypted_token_config = auth_types.get("form_encrypted_token", {})
        if isinstance(encrypted_token_config, dict):
            setter_endpoint = encrypted_token_config.get("setter_endpoint", "/xml/setter.xml")
            logout_fun = str(encrypted_token_config.get("logout_fun", 16))
        else:
            setter_endpoint = getattr(encrypted_token_config, "setter_endpoint", "/xml/setter.xml")
            logout_fun = str(getattr(encrypted_token_config, "logout_fun", 16))

        session_token = self.session.cookies.get(cookie_name) or self._session_token
        if not session_token:
            return

        try:
            self.session.post(
                f"{self.base_url}{setter_endpoint}",
                data={"token": session_token, "fun": logout_fun},
                headers={"Accept-Encoding": "gzip, deflate, br"},
                timeout=timeout,
                verify=self.verify_ssl,
                allow_redirects=False,
            )
            _LOGGER.debug("XMLPostLoader: logout sent (session released)")
        except Exception:
            _LOGGER.debug("XMLPostLoader: logout failed (non-critical)")

    def _get_session_cookie_name(self) -> str:
        """Get session cookie name from modem config."""
        auth_types = self.modem_config.get("auth", {}).get("types", {})
        encrypted_token_config = auth_types.get("form_encrypted_token", {})
        if isinstance(encrypted_token_config, dict):
            return encrypted_token_config.get("session_cookie_name", "sessionToken")
        return getattr(encrypted_token_config, "session_cookie_name", "sessionToken")
