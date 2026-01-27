"""Form-based authentication with dynamic action URL extraction.

This strategy extends FormPlainAuthStrategy to handle modems where the
login form's action attribute contains a dynamic parameter that changes
per page load (e.g., Netgear CM2000 uses /goform/Login?id=XXXXXXXXXX).

The strategy fetches the login page first, parses the <form> element,
and extracts the actual action URL before submitting credentials.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from .form_plain import FormPlainAuthStrategy

if TYPE_CHECKING:
    import requests

    from ..configs import FormAuthConfig, FormDynamicAuthConfig

_LOGGER = logging.getLogger(__name__)


class FormDynamicAuthStrategy(FormPlainAuthStrategy):
    """Form-based auth with action URL extracted from login page.

    Inherits all form submission logic from FormPlainAuthStrategy.
    Only overrides action URL resolution to scrape it from the actual page.
    """

    def _get_action_path(
        self,
        session: requests.Session,
        base_url: str,
        config: FormAuthConfig | FormDynamicAuthConfig,
        log,
    ) -> str:
        """Extract form action URL from login page.

        Fetches the login page, parses the HTML to find the form element,
        and extracts the action attribute which may contain dynamic parameters.

        Args:
            session: Requests session
            base_url: Modem base URL
            config: Form auth configuration (expects FormDynamicAuthConfig)
            log: Logger function

        Returns:
            Form action path extracted from the page, or fallback to config.login_url
        """
        # Get login page path from config (FormDynamicAuthConfig adds this field)
        login_page = getattr(config, "login_page", "/")
        form_selector = getattr(config, "form_selector", None)

        log("FormDynamic: fetching login page %s to extract form action", login_page)

        try:
            response = session.get(
                f"{base_url}{login_page}",
                timeout=config.timeout,
                verify=session.verify,
            )
            response.raise_for_status()
        except Exception as e:
            _LOGGER.warning(
                "FormDynamic: failed to fetch login page %s: %s, falling back to static action",
                login_page,
                e,
            )
            return config.login_url

        soup = BeautifulSoup(response.text, "html.parser")

        # Find form element
        if form_selector:
            # Use CSS selector if provided (e.g., "form[name='loginform']")
            form = soup.select_one(form_selector)
            if not form:
                _LOGGER.warning(
                    "FormDynamic: no form matching selector '%s', trying first <form>",
                    form_selector,
                )
                form = soup.find("form")
        else:
            # Default: find first form
            form = soup.find("form")

        if not form:
            _LOGGER.warning(
                "FormDynamic: no <form> element found on %s, using static action",
                login_page,
            )
            return config.login_url

        action = form.get("action")
        if not action:
            _LOGGER.warning("FormDynamic: form has no action attribute, using static action")
            return config.login_url

        action_str = str(action)
        log("FormDynamic: extracted action URL: %s", action_str)
        return action_str
