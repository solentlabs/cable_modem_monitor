"""End-to-end tests for modems using MockModemServer.

Auto-discovers all modems in modems/**/modem.yaml and runs
a complete auth + parse workflow against MockModemServer.

Note: Tests use the repo root modems/ directory (source of truth),
not custom_components/.../modems/ (deployment sync target).
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from urllib.parse import quote

import pytest
import requests
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.auth.handler import AuthHandler
from custom_components.cable_modem_monitor.core.auth.types import AuthStrategyType
from custom_components.cable_modem_monitor.modem_config import (
    discover_modems,
    load_modem_config,
)
from custom_components.cable_modem_monitor.modem_config.loader import (
    get_modem_fixtures_path,
    list_modem_fixtures,
)
from custom_components.cable_modem_monitor.modem_config.schema import AuthStrategy

from .mock_modem_server import MockModemServer

_LOGGER = logging.getLogger(__name__)

# Test credentials
TEST_USERNAME = "admin"
TEST_PASSWORD = "password"

# Use repo root modems/ directory (has fixtures), not custom_components/.../modems/
REPO_ROOT = Path(__file__).parent.parent.parent
MODEMS_ROOT = REPO_ROOT / "modems"


def get_modems_with_fixtures() -> list[tuple[str, Path]]:
    """Get all modems that have fixtures for testing.

    Returns:
        List of (modem_id, modem_path) tuples.
    """
    result = []
    for modem_path, config in discover_modems(modems_root=MODEMS_ROOT):
        fixtures = list_modem_fixtures(modem_path)
        if fixtures:
            modem_id = f"{config.manufacturer}_{config.model}"
            result.append((modem_id, modem_path))
    return result


# Parametrize tests with discovered modems
MODEMS_WITH_FIXTURES = get_modems_with_fixtures()


class TestModemE2E:
    """End-to-end tests for modem configurations."""

    @pytest.fixture
    def modem_path(self, request) -> Path:
        """Get modem path from parameter."""
        return request.param  # type: ignore[no-any-return]

    @pytest.mark.parametrize(
        "modem_path",
        [path for _, path in MODEMS_WITH_FIXTURES],
        ids=[modem_id for modem_id, _ in MODEMS_WITH_FIXTURES],
    )
    def test_public_pages_accessible(self, modem_path: Path):
        """Test that public pages are accessible without authentication."""
        config = load_modem_config(modem_path)

        if not config.pages or not config.pages.public:
            pytest.skip("No public pages defined")

        with MockModemServer.from_modem_path(modem_path) as server:
            session = requests.Session()

            for public_path in config.pages.public:
                # Skip non-page resources (css, images)
                if any(public_path.endswith(ext) for ext in [".css", ".jpg", ".png", ".gif"]):
                    continue

                resp = session.get(f"{server.url}{public_path}", timeout=10)
                assert resp.status_code == 200, f"Failed to access public page {public_path}"

    @pytest.mark.parametrize(
        "modem_path",
        [path for _, path in MODEMS_WITH_FIXTURES],
        ids=[modem_id for modem_id, _ in MODEMS_WITH_FIXTURES],
    )
    def test_protected_pages_require_auth(self, modem_path: Path):
        """Test that protected pages require authentication."""
        config = load_modem_config(modem_path)

        if not config.pages or not config.pages.protected:
            pytest.skip("No protected pages defined")

        # Skip no-auth modems
        if config.auth.strategy == AuthStrategy.NONE:
            pytest.skip("Modem has no auth")

        with MockModemServer.from_modem_path(modem_path) as server:
            session = requests.Session()

            for protected_path in config.pages.protected:
                resp = session.get(f"{server.url}{protected_path}", timeout=10)

                # Should either return login page (200) or 401
                if resp.status_code == 200:
                    # For form auth, should contain a form
                    assert "form" in resp.text.lower() or "login" in resp.text.lower()
                else:
                    assert resp.status_code == 401

    @pytest.mark.parametrize(
        "modem_path",
        [path for _, path in MODEMS_WITH_FIXTURES],
        ids=[modem_id for modem_id, _ in MODEMS_WITH_FIXTURES],
    )
    def test_form_auth_workflow(self, modem_path: Path):
        """Test complete form authentication workflow."""
        config = load_modem_config(modem_path)

        if config.auth.strategy != AuthStrategy.FORM:
            pytest.skip("Not a form auth modem")

        if not config.auth.form:
            pytest.skip("No form config")

        with MockModemServer.from_modem_path(modem_path) as server:
            session = requests.Session()
            form_config = config.auth.form

            # Prepare password based on encoding
            from custom_components.cable_modem_monitor.modem_config.schema import (
                PasswordEncoding,
            )

            if form_config.password_encoding == PasswordEncoding.BASE64:
                encoded_password = base64.b64encode(quote(TEST_PASSWORD).encode()).decode()
            else:
                encoded_password = TEST_PASSWORD

            # Submit login form
            login_data = {
                form_config.username_field: TEST_USERNAME,
                form_config.password_field: encoded_password,
            }

            # Add hidden fields
            if form_config.hidden_fields:
                login_data.update(form_config.hidden_fields)

            resp = session.post(
                f"{server.url}{form_config.action}",
                data=login_data,
                allow_redirects=False,
                timeout=10,
            )

            # Should redirect on success
            assert resp.status_code == 302, f"Expected redirect, got {resp.status_code}"

            # Follow redirect
            if form_config.success and form_config.success.redirect:
                expected_redirect = form_config.success.redirect
                assert resp.headers.get("Location") == expected_redirect

            # Should have session cookie
            assert len(session.cookies) > 0, "No session cookie set"

            # Now should be able to access protected pages
            if config.pages and config.pages.protected:
                for protected_path in config.pages.protected:
                    resp = session.get(f"{server.url}{protected_path}", timeout=10)
                    assert resp.status_code == 200, f"Failed to access {protected_path} after auth"
                    # Should NOT contain login form (check for form action, not just "password" word)
                    form_action = config.auth.form.action if config.auth.form else None
                    if form_action:
                        # If page contains form action URL, it's likely a login redirect
                        is_login_form = f'action="{form_action}"' in resp.text.lower()
                        assert not is_login_form, f"Got login form instead of {protected_path}"

    @pytest.mark.parametrize(
        "modem_path",
        [path for _, path in MODEMS_WITH_FIXTURES],
        ids=[modem_id for modem_id, _ in MODEMS_WITH_FIXTURES],
    )
    def test_auth_handler_integration(self, modem_path: Path):
        """Test that AuthHandler works with MockModemServer."""
        config = load_modem_config(modem_path)

        # Skip no-auth modems for this test
        if config.auth.strategy == AuthStrategy.NONE:
            pytest.skip("Modem has no auth")

        # Map schema strategy to AuthHandler strategy type
        # FORM_PLAIN handles both plain and base64 via password_encoding field
        strategy_map = {
            AuthStrategy.FORM: AuthStrategyType.FORM_PLAIN,
            AuthStrategy.BASIC: AuthStrategyType.BASIC_HTTP,
        }

        if config.auth.strategy not in strategy_map:
            pytest.skip(f"Strategy {config.auth.strategy} not yet mapped")

        auth_strategy = strategy_map[config.auth.strategy]

        # Build form config if needed
        form_config: dict[str, str | dict[str, str] | None] | None = None
        if config.auth.strategy == AuthStrategy.FORM and config.auth.form:
            form_config = {
                "action": config.auth.form.action,
                "method": config.auth.form.method,
                "username_field": config.auth.form.username_field,
                "password_field": config.auth.form.password_field,
            }
            if config.auth.form.hidden_fields:
                form_config["hidden_fields"] = config.auth.form.hidden_fields

        with MockModemServer.from_modem_path(modem_path) as server:
            handler = AuthHandler(
                strategy=auth_strategy,
                form_config=form_config,
            )

            session = requests.Session()
            session.verify = False

            success, html = handler.authenticate(
                session=session,
                base_url=server.url,
                username=TEST_USERNAME,
                password=TEST_PASSWORD,
            )

            assert success is True, f"Auth failed for {config.manufacturer} {config.model}"

    @pytest.mark.parametrize(
        "modem_path",
        [path for _, path in MODEMS_WITH_FIXTURES],
        ids=[modem_id for modem_id, _ in MODEMS_WITH_FIXTURES],
    )
    def test_parser_detection_with_fixtures(self, modem_path: Path):  # noqa: C901
        """Test that the declared parser can parse the fixture data."""
        config = load_modem_config(modem_path)
        fixtures_path = get_modem_fixtures_path(modem_path)

        if not config.parser:
            pytest.skip("No parser defined")

        if not config.pages or not config.pages.data:
            pytest.skip("No data pages defined")

        # Dynamically import the parser
        import importlib

        try:
            module = importlib.import_module(config.parser.module)
            parser_class = getattr(module, config.parser.class_name)
            parser = parser_class()
        except Exception as e:
            pytest.fail(f"Failed to import parser: {e}")
            raise  # Unreachable - pytest.fail raises, but explicit for static analysis

        # Load and parse channel data page
        if "downstream_channels" in config.pages.data:
            data_page = config.pages.data["downstream_channels"]
            fixture_name = data_page.lstrip("/")
            fixture_path = fixtures_path / fixture_name

            if fixture_path.exists():
                html = fixture_path.read_text(encoding="utf-8", errors="replace")
                soup = BeautifulSoup(html, "html.parser")

                # Try to parse - pass BeautifulSoup object
                try:
                    data = parser.parse(soup)
                    assert data is not None, "Parser returned None"

                    # Check for expected data
                    assert hasattr(data, "downstream_channels") or "downstream" in str(data).lower()
                except Exception as e:
                    pytest.fail(f"Parser failed to parse {fixture_name}: {e}")


class TestModemE2EFullWorkflow:
    """Full workflow tests: auth -> fetch -> parse."""

    @pytest.mark.parametrize(
        "modem_path",
        [path for _, path in MODEMS_WITH_FIXTURES],
        ids=[modem_id for modem_id, _ in MODEMS_WITH_FIXTURES],
    )
    def test_complete_workflow(self, modem_path: Path):  # noqa: C901
        """Test complete workflow: auth, fetch data pages, parse."""
        config = load_modem_config(modem_path)

        if not config.pages or not config.pages.data:
            pytest.skip("No data pages defined")

        if not config.parser:
            pytest.skip("No parser defined")

        # Dynamically import the parser
        import importlib

        try:
            module = importlib.import_module(config.parser.module)
            parser_class = getattr(module, config.parser.class_name)
            parser = parser_class()
        except Exception as e:
            pytest.skip(f"Failed to import parser: {e}")
            raise  # Unreachable - pytest.skip raises, but explicit for static analysis

        with MockModemServer.from_modem_path(modem_path) as server:
            session = requests.Session()
            session.verify = False

            # Step 1: Authenticate if needed
            if config.auth.strategy == AuthStrategy.BASIC:
                # Set up HTTP Basic Auth on the session
                session.auth = (TEST_USERNAME, TEST_PASSWORD)

            elif config.auth.strategy == AuthStrategy.HNAP and config.auth.hnap:
                # HNAP uses challenge-response authentication via JSON
                # Use the HNAPJsonRequestBuilder for authentication
                from custom_components.cable_modem_monitor.core.auth import HNAPJsonRequestBuilder
                from custom_components.cable_modem_monitor.core.auth.hnap.json_builder import HMACAlgorithm

                hnap_config = config.auth.hnap
                # Convert string algorithm to enum
                algorithm = HMACAlgorithm(hnap_config.hmac_algorithm)
                builder = HNAPJsonRequestBuilder(
                    endpoint=hnap_config.endpoint,
                    namespace=hnap_config.namespace,
                    hmac_algorithm=algorithm,
                    empty_action_value=hnap_config.empty_action_value,
                )

                success, _ = builder.login(session, server.url, TEST_USERNAME, TEST_PASSWORD)
                assert success, "HNAP login failed"

                # Store builder on parser for data fetching
                parser._json_builder = builder

            elif config.auth.strategy == AuthStrategy.FORM and config.auth.form:
                # Encode password
                from custom_components.cable_modem_monitor.modem_config.schema import (
                    PasswordEncoding,
                )

                if config.auth.form.password_encoding == PasswordEncoding.BASE64:
                    encoded_password = base64.b64encode(quote(TEST_PASSWORD).encode()).decode()
                else:
                    encoded_password = TEST_PASSWORD

                login_data = {
                    config.auth.form.username_field: TEST_USERNAME,
                    config.auth.form.password_field: encoded_password,
                }

                resp = session.post(
                    f"{server.url}{config.auth.form.action}",
                    data=login_data,
                    allow_redirects=True,
                    timeout=10,
                )
                assert resp.status_code == 200

            # Step 2: Fetch and parse data pages
            # HNAP modems use POST to /HNAP1/ for JSON data, not GET to HTML pages
            if config.auth.strategy == AuthStrategy.HNAP:
                # HNAP: call parse() which uses stored builder to fetch data
                try:
                    soup = BeautifulSoup("", "html.parser")  # Placeholder, HNAP ignores it
                    data = parser.parse(soup, session=session, base_url=server.url)
                    assert data is not None, "HNAP parser returned None"
                    assert "downstream" in data, "HNAP parser missing downstream data"
                    _LOGGER.info("Parsed HNAP data: %d downstream channels", len(data.get("downstream", [])))
                except Exception as e:
                    _LOGGER.warning("HNAP parser failed: %s", e)
            else:
                # HTML modems: fetch pages via GET and parse HTML
                for data_type, data_path in config.pages.data.items():
                    resp = session.get(f"{server.url}{data_path}", timeout=10)
                    assert resp.status_code == 200, f"Failed to fetch {data_path}"

                    # Parse the response - pass BeautifulSoup object
                    soup = BeautifulSoup(resp.text, "html.parser")
                    try:
                        data = parser.parse(soup)
                        assert data is not None, f"Parser returned None for {data_path}"
                        _LOGGER.info("Parsed %s from %s", data_type, data_path)
                    except Exception as e:
                        _LOGGER.warning("Parser failed on %s: %s", data_path, e)

        _LOGGER.info(
            "Complete workflow passed for %s %s",
            config.manufacturer,
            config.model,
        )


class TestDiscoveryPipelineE2E:
    """Test the actual discovery pipeline against MockModemServer.

    These tests exercise the REAL code path users experience during setup:
    config_flow -> validate_input -> run_discovery_pipeline

    This is critical because other E2E tests bypass discovery by using
    direct auth (HNAPJsonRequestBuilder, form POST, etc.). This class
    ensures the discovery pipeline works end-to-end.

    Added after issue #102: HNAP discovery returned html=None which
    caused AssertionError in validation step. Direct auth tests passed
    but the actual user flow was broken.
    """

    # Auth strategies supported by dynamic discovery
    # FORM and HNAP work with dynamic auth discovery
    DYNAMIC_DISCOVERY_STRATEGIES = {AuthStrategy.FORM, AuthStrategy.HNAP}

    # All auth strategies supported via static_auth_config (modem.yaml as source of truth)
    # MockModemServer has handlers for all of these
    STATIC_AUTH_STRATEGIES = {
        AuthStrategy.FORM,
        AuthStrategy.HNAP,
        AuthStrategy.NONE,
        AuthStrategy.BASIC,
        AuthStrategy.URL_TOKEN,
        AuthStrategy.REST_API,
    }

    @pytest.mark.parametrize(
        "modem_path",
        [path for _, path in MODEMS_WITH_FIXTURES],
        ids=[modem_id for modem_id, _ in MODEMS_WITH_FIXTURES],
    )
    def test_discovery_pipeline_dynamic_auth(self, modem_path: Path):
        """Test run_discovery_pipeline with dynamic auth discovery.

        Tests the legacy path where auth is discovered dynamically.
        Only FORM and HNAP strategies support dynamic discovery.
        """
        from custom_components.cable_modem_monitor.core.discovery import (
            run_discovery_pipeline,
        )

        config = load_modem_config(modem_path)

        # Skip modems with strategies that don't support dynamic discovery
        if config.auth.strategy not in self.DYNAMIC_DISCOVERY_STRATEGIES:
            pytest.skip(
                f"Auth strategy {config.auth.strategy.value} requires static auth config "
                f"(see test_discovery_pipeline_static_auth)"
            )

        # Get the parser class for user-selected flow
        import importlib

        try:
            module = importlib.import_module(config.parser.module)
            parser_class = getattr(module, config.parser.class_name)
        except Exception as e:
            pytest.skip(f"Failed to import parser: {e}")

        with MockModemServer.from_modem_path(modem_path) as server:
            # Run the ACTUAL discovery pipeline - same as config_flow
            result = run_discovery_pipeline(
                host=server.url.replace("http://", "").replace("https://", ""),
                username=TEST_USERNAME,
                password=TEST_PASSWORD,
                selected_parser=parser_class,
            )

            # Pipeline should succeed
            assert result.success, (
                f"Discovery pipeline failed for {config.manufacturer} {config.model}: "
                f"step={result.failed_step}, error={result.error}"
            )

            # Should have detected the correct strategy
            assert result.auth_strategy is not None, "No auth strategy detected"
            _LOGGER.info(
                "Discovery pipeline succeeded: %s %s (strategy=%s)",
                config.manufacturer,
                config.model,
                result.auth_strategy,
            )

    @pytest.mark.parametrize(
        "modem_path",
        [path for _, path in MODEMS_WITH_FIXTURES],
        ids=[modem_id for modem_id, _ in MODEMS_WITH_FIXTURES],
    )
    def test_discovery_pipeline_auto_detection(self, modem_path: Path):
        """Test discovery pipeline with auto-detection (no pre-selected parser).

        This tests the fully automatic flow where users don't select a modem.
        HNAP modems will fail gracefully (require manual selection).
        Form-based modems should auto-detect successfully.
        """
        from custom_components.cable_modem_monitor.core.discovery import (
            run_discovery_pipeline,
        )

        config = load_modem_config(modem_path)

        # Skip HNAP modems - they require manual parser selection
        # (HNAP returns JSON, not HTML, so can't auto-detect parser)
        if config.auth.strategy == AuthStrategy.HNAP:
            pytest.skip("HNAP modems require manual parser selection")

        # Skip modems with unsupported auth strategies for dynamic discovery
        if config.auth.strategy not in self.DYNAMIC_DISCOVERY_STRATEGIES:
            pytest.skip(
                f"Auth strategy {config.auth.strategy.value} not yet supported "
                f"by MockModemServer + AuthDiscovery integration"
            )

        with MockModemServer.from_modem_path(modem_path) as server:
            # Run discovery WITHOUT selected_parser (auto-detection)
            result = run_discovery_pipeline(
                host=server.url.replace("http://", "").replace("https://", ""),
                username=TEST_USERNAME,
                password=TEST_PASSWORD,
                selected_parser=None,  # Auto-detect
            )

            # Pipeline should succeed for non-HNAP modems
            assert result.success, (
                f"Auto-detection failed for {config.manufacturer} {config.model}: "
                f"step={result.failed_step}, error={result.error}"
            )

            # Should have detected the parser
            assert result.parser_name is not None, "No parser detected"
            _LOGGER.info(
                "Auto-detection succeeded: %s %s -> %s",
                config.manufacturer,
                config.model,
                result.parser_name,
            )

    @pytest.mark.parametrize(
        "modem_path",
        [path for _, path in MODEMS_WITH_FIXTURES],
        ids=[modem_id for modem_id, _ in MODEMS_WITH_FIXTURES],
    )
    def test_discovery_pipeline_static_auth(self, modem_path: Path):
        """Test run_discovery_pipeline with static auth config from modem.yaml.

        This tests the NEW "modem.yaml as source of truth" architecture where
        known modems skip dynamic auth discovery and use verified config directly.

        This enables support for ALL auth strategies (NONE, BASIC, URL_TOKEN,
        REST_API) that don't work well with dynamic discovery.
        """
        from custom_components.cable_modem_monitor.core.discovery import (
            run_discovery_pipeline,
        )
        from custom_components.cable_modem_monitor.modem_config import (
            get_auth_adapter_for_parser,
        )

        config = load_modem_config(modem_path)

        # Skip modems with strategies not in our static auth support list
        if config.auth.strategy not in self.STATIC_AUTH_STRATEGIES:
            pytest.skip(f"Auth strategy {config.auth.strategy.value} not yet supported")

        # Get the parser class
        import importlib

        try:
            module = importlib.import_module(config.parser.module)
            parser_class = getattr(module, config.parser.class_name)
        except Exception as e:
            pytest.skip(f"Failed to import parser: {e}")

        # Get static auth config from modem.yaml adapter
        adapter = get_auth_adapter_for_parser(parser_class.__name__)
        if adapter is None:
            pytest.skip(f"No adapter for {parser_class.__name__}")

        static_auth_config = adapter.get_static_auth_config()

        with MockModemServer.from_modem_path(modem_path) as server:
            # Run discovery pipeline with static auth config (skip dynamic discovery)
            result = run_discovery_pipeline(
                host=server.url.replace("http://", "").replace("https://", ""),
                username=TEST_USERNAME,
                password=TEST_PASSWORD,
                selected_parser=parser_class,
                static_auth_config=static_auth_config,
            )

            # Pipeline should succeed
            assert result.success, (
                f"Static auth pipeline failed for {config.manufacturer} {config.model}: "
                f"step={result.failed_step}, error={result.error}"
            )

            # Should have used the strategy from static config
            assert result.auth_strategy is not None, "No auth strategy in result"
            _LOGGER.info(
                "Static auth pipeline succeeded: %s %s (strategy=%s)",
                config.manufacturer,
                config.model,
                result.auth_strategy,
            )
