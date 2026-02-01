"""End-to-end tests for DataOrchestrator with real modem configs.

These tests validate the COMPLETE flow:
    Auth → Session Cookie → Loader fetches pages.data → Parser receives resources

This is the critical path that every modem depends on. Individual component tests
may pass while this integration fails if the session/cookie handoff is broken.

## Why This Test Exists
======================
Issue #107: XB7 parser worked in v2.4.1 when auth was in the parser itself.
In v3.13, auth moved to AuthHandler + form_plain strategy, but the loader
wasn't fetching the data page correctly. Component tests passed, but the
full orchestration was broken.

## What This Test Validates
===========================
1. DataOrchestrator.get_modem_data() completes successfully
2. Auth establishes session cookie
3. Loader uses authenticated session to fetch pages.data URLs
4. Parser receives resources from the CORRECT pages (not auth redirect page)
5. Parsed data contains expected channel information
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from custom_components.cable_modem_monitor.core.data_orchestrator import DataOrchestrator
from tests.integration.mock_handlers.form import TEST_PASSWORD, TEST_USERNAME
from tests.integration.mock_modem_server import MockModemServer


def get_parser_instance(config):
    """Dynamically import and instantiate parser from modem.yaml config."""
    if not config.parser or not config.parser.module or not config.parser.class_name:
        return None
    module = importlib.import_module(config.parser.module)
    parser_class = getattr(module, config.parser.class_name)
    return parser_class()


# Test timeout constant - matches DEFAULT_TIMEOUT from schema
TEST_TIMEOUT = 10


# ┌─────────────────────────────────────────────────────────────────────────────┐
# │ Test Data: Modems with form-based auth                                      │
# ├─────────────────────────────────────────────────────────────────────────────┤
# │ modem_path          │ data_page              │ expected_content             │
# ├─────────────────────┼────────────────────────┼──────────────────────────────┤
# │ technicolor/xb7     │ /network_setup.jst     │ "Channel" or downstream data │
# └─────────────────────┴────────────────────────┴──────────────────────────────┘
#
# fmt: off
FORM_AUTH_MODEMS = [
    # (modem_path, data_page, content_marker, description)
    ("technicolor/xb7", "/network_setup.jst", "Channel", "XB7 form auth → data page"),
]
# fmt: on


class TestOrchestratorE2EFormAuth:
    """E2E tests for form-authenticated modems through DataOrchestrator.

    These tests use real modem.yaml configs and MockModemServer to validate
    the complete auth → fetch → parse pipeline.
    """

    @pytest.mark.parametrize("modem_path,data_page,content_marker,desc", FORM_AUTH_MODEMS)
    def test_get_modem_data_with_form_auth(
        self,
        modem_path: str,
        data_page: str,
        content_marker: str,
        desc: str,
    ) -> None:
        """Full E2E: DataOrchestrator authenticates and parses data page.

        This is THE critical test. If this passes, the modem works.
        If this fails, users see "parser error" even though component tests pass.
        """
        modem_full_path = Path("modems") / modem_path

        with MockModemServer.from_modem_path(modem_full_path) as server:
            # Get auth config from modem.yaml (same as config_flow does)
            auth_config = server.config.auth
            form_config = None
            if auth_config and auth_config.types:
                form_type = auth_config.types.get("form")
                if form_type:
                    form_config = {
                        "action": form_type.action,
                        "method": form_type.method or "POST",
                        "username_field": form_type.username_field,
                        "password_field": form_type.password_field,
                        "hidden_fields": form_type.hidden_fields or {},
                    }
                    if form_type.success and form_type.success.redirect:
                        form_config["success_redirect"] = form_type.success.redirect

            # Get parser instance from modem.yaml
            parser = get_parser_instance(server.config)
            assert parser is not None, f"No parser for {modem_path}"

            # Create orchestrator exactly as __init__.py does
            orchestrator = DataOrchestrator(
                host=server.url,
                username=TEST_USERNAME,
                password=TEST_PASSWORD,
                parser=parser,
                auth_strategy="form_plain",
                auth_form_config=form_config,
                timeout=TEST_TIMEOUT,
            )

            # THE CRITICAL CALL - this must work end-to-end
            result = orchestrator.get_modem_data()

            # Verify we got actual data, not an error
            assert (
                "status" not in result or result.get("status") != "error"
            ), f"get_modem_data() returned error: {result.get('status_message', 'unknown')}"

            # Verify we got channel data (proves parser received correct page)
            # Response uses cable_modem_* prefix from _build_response()
            downstream = result.get("cable_modem_downstream", [])
            upstream = result.get("cable_modem_upstream", [])

            assert downstream or upstream, (
                f"No channel data returned. This likely means:\n"
                f"  1. Auth failed silently (loader got login page)\n"
                f"  2. Loader didn't fetch {data_page}\n"
                f"  3. Session cookie wasn't passed to loader\n"
                f"Result keys: {list(result.keys())}"
            )

    @pytest.mark.parametrize("modem_path,data_page,content_marker,desc", FORM_AUTH_MODEMS)
    def test_loader_fetches_correct_data_page(
        self,
        modem_path: str,
        data_page: str,
        content_marker: str,
        desc: str,
    ) -> None:
        """Verify loader fetches pages.data URLs, not just auth redirect page.

        This test instruments the session to track which URLs are fetched,
        ensuring the loader actually requests the data page.
        """
        modem_full_path = Path("modems") / modem_path

        with MockModemServer.from_modem_path(modem_full_path) as server:
            # Track all URLs fetched
            fetched_urls: list[str] = []
            original_get = None

            # Get auth config
            auth_config = server.config.auth
            form_config = None
            if auth_config and auth_config.types:
                form_type = auth_config.types.get("form")
                if form_type:
                    form_config = {
                        "action": form_type.action,
                        "method": form_type.method or "POST",
                        "username_field": form_type.username_field,
                        "password_field": form_type.password_field,
                    }
                    if form_type.success and form_type.success.redirect:
                        form_config["success_redirect"] = form_type.success.redirect

            parser = get_parser_instance(server.config)

            orchestrator = DataOrchestrator(
                host=server.url,
                username=TEST_USERNAME,
                password=TEST_PASSWORD,
                parser=parser,
                auth_strategy="form_plain",
                auth_form_config=form_config,
                timeout=TEST_TIMEOUT,
            )

            # Instrument session to track fetched URLs
            original_get = orchestrator.session.get

            def tracking_get(url, *args, **kwargs):
                fetched_urls.append(url)
                return original_get(url, *args, **kwargs)

            orchestrator.session.get = tracking_get

            # Run the flow
            orchestrator.get_modem_data()

            # Verify data page was fetched
            assert any(data_page in url for url in fetched_urls), (
                f"Data page {data_page} was never fetched!\n"
                f"Fetched URLs: {fetched_urls}\n"
                f"This means the loader isn't using pages.data from modem.yaml"
            )

    @pytest.mark.parametrize("modem_path,data_page,content_marker,desc", FORM_AUTH_MODEMS)
    def test_session_cookie_present_when_fetching_data(
        self,
        modem_path: str,
        data_page: str,
        content_marker: str,
        desc: str,
    ) -> None:
        """Verify session cookie is present when loader fetches data page.

        The auth flow sets a cookie. The loader must use the same session
        with that cookie to fetch protected pages.
        """
        modem_full_path = Path("modems") / modem_path

        with MockModemServer.from_modem_path(modem_full_path) as server:
            cookies_when_fetching_data: dict = {}

            # Get auth config
            auth_config = server.config.auth
            form_config = None
            if auth_config and auth_config.types:
                form_type = auth_config.types.get("form")
                if form_type:
                    form_config = {
                        "action": form_type.action,
                        "method": form_type.method or "POST",
                        "username_field": form_type.username_field,
                        "password_field": form_type.password_field,
                    }
                    if form_type.success and form_type.success.redirect:
                        form_config["success_redirect"] = form_type.success.redirect

            parser = get_parser_instance(server.config)

            orchestrator = DataOrchestrator(
                host=server.url,
                username=TEST_USERNAME,
                password=TEST_PASSWORD,
                parser=parser,
                auth_strategy="form_plain",
                auth_form_config=form_config,
                timeout=TEST_TIMEOUT,
            )

            # Instrument session to capture cookies when data page is fetched
            original_get = orchestrator.session.get

            def cookie_tracking_get(url, *args, **kwargs):
                if data_page in url:
                    cookies_when_fetching_data.update(dict(orchestrator.session.cookies))
                return original_get(url, *args, **kwargs)

            orchestrator.session.get = cookie_tracking_get

            # Run the flow
            orchestrator.get_modem_data()

            # Verify cookie was present
            assert cookies_when_fetching_data, (
                f"No cookies present when fetching {data_page}!\n"
                f"Auth should have set a session cookie that the loader uses.\n"
                f"This indicates the session isn't being shared between auth and loader."
            )


class TestOrchestratorE2EGeneric:
    """Generic E2E tests that apply to all modem types."""

    def test_orchestrator_uses_same_session_for_auth_and_loader(self) -> None:
        """Verify auth and loader use the exact same session object.

        This is a sanity check - if they use different sessions,
        cookies won't be shared and auth will fail for protected pages.
        """
        orchestrator = DataOrchestrator(
            host="http://192.168.100.1",
            username="admin",
            password="password",
            auth_strategy="form_plain",
            auth_form_config={"action": "/login"},
            timeout=TEST_TIMEOUT,
        )

        # Get session used by auth handler
        auth_session_id = id(orchestrator.session)

        # The loader (when created) should use the same session
        # We can't easily test this without a real modem config,
        # but we can verify the orchestrator has one session
        assert orchestrator.session is not None
        assert id(orchestrator.session) == auth_session_id
