"""E2E tests for config flow against mock modem servers.

Tests the known modem setup flow using MockModemServer to simulate
real modem behavior without hardware. These tests verify the path
users take when selecting their modem model from the dropdown.

Tests run on both HTTP and HTTPS protocols to ensure protocol detection
works correctly for all modems.
"""

from __future__ import annotations

import ssl
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from custom_components.cable_modem_monitor.core.auth.workflow import AUTH_TYPE_TO_STRATEGY
from custom_components.cable_modem_monitor.core.base_parser import ModemParser
from custom_components.cable_modem_monitor.core.parser_registry import get_parser_by_name
from custom_components.cable_modem_monitor.core.setup import setup_modem
from custom_components.cable_modem_monitor.modem_config import get_auth_adapter_for_parser

from .mock_modem_server import MockModemServer


def build_static_auth_config(parser: type[ModemParser], auth_type: str) -> dict[str, Any] | None:
    """Build static auth config for testing (sync version).

    Mimics _build_static_config_for_auth_type from config_flow_helpers.py
    but runs synchronously for testing.

    Args:
        parser: Parser class
        auth_type: Auth type (e.g., "none", "form", "url_token")

    Returns:
        Static auth config dict with keys matching AuthWorkflow expectations
    """
    adapter = get_auth_adapter_for_parser(parser.__name__)
    if not adapter:
        return None

    # Get strategy from auth type
    strategy = AUTH_TYPE_TO_STRATEGY.get(auth_type)
    if not strategy:
        return None

    # Get type-specific config from modem.yaml
    type_config = adapter.get_auth_config_for_type(auth_type)

    # Build config dict matching AuthWorkflow.authenticate_with_static_config() expectations
    return {
        "auth_strategy": strategy,
        "auth_form_config": type_config if auth_type == "form" else None,
        "auth_form_ajax_config": type_config if auth_type == "form_ajax" else None,
        "auth_hnap_config": type_config if auth_type == "hnap" else None,
        "auth_url_token_config": type_config if auth_type == "url_token" else None,
    }


MODEMS_DIR = Path(__file__).parent.parent.parent / "modems"


# =============================================================================
# PROTOCOL FIXTURES
# =============================================================================


@pytest.fixture(params=["http", "https"], ids=["http", "https"])
def protocol(request) -> str:
    """Parameterize tests to run on both HTTP and HTTPS."""
    return request.param


@pytest.fixture
def ssl_context_for_protocol(protocol, test_certs) -> ssl.SSLContext | None:
    """Provide SSL context for HTTPS, None for HTTP.

    Args:
        protocol: "http" or "https" from the protocol fixture
        test_certs: Certificate paths from conftest.py

    Returns:
        SSL context for HTTPS, None for HTTP
    """
    if protocol == "http":
        return None

    cert_path, key_path = test_certs
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)
    return context


def modem_path_to_display_name(modem_path: str) -> str:
    """Convert modem path to parser display name (e.g., arris/sb6190 -> ARRIS SB6190)."""
    parts = modem_path.split("/")
    manufacturer = parts[0]
    model = parts[1]
    # ARRIS uses all caps, others use title case
    if manufacturer.lower() == "arris":
        return f"ARRIS {model.upper()}"
    else:
        return f"{manufacturer.title()} {model.upper()}"


# =============================================================================
# TEST DATA
# =============================================================================

# fmt: off
# ┌─────────────────┬───────────────┬──────────────────┬─────────────────────┐
# │ modem           │ auth_type     │ needs_selection  │ expected_strategy   │
# ├─────────────────┼───────────────┼──────────────────┼─────────────────────┤
# │ arris/sb6190    │ none          │ True             │ no_auth             │
# │ arris/sb6190    │ form_ajax     │ True             │ form_ajax           │
# │ arris/sb8200    │ none          │ True             │ no_auth             │
# │ arris/sb8200    │ url_token     │ True             │ url_token_session   │
# │ motorola/mb7621 │ form          │ False            │ form_plain          │
# └─────────────────┴───────────────┴──────────────────┴─────────────────────┘
MULTI_AUTH_MODEMS = [
    ("arris/sb6190", "none", "no_auth"),
    ("arris/sb6190", "form_ajax", "form_ajax"),
    ("arris/sb8200", "none", "no_auth"),
    ("arris/sb8200", "url_token", "url_token_session"),
]

SINGLE_AUTH_MODEMS = [
    ("motorola/mb7621", "form", "form_plain"),
    ("arris/sb6141", "none", "no_auth"),
]
# fmt: on


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    # Make async_add_executor_job run synchronously for testing
    hass.async_add_executor_job = lambda fn, *args: fn(*args)
    return hass


# =============================================================================
# AUTH TYPE SELECTION TESTS
# =============================================================================


class TestAuthTypeSelection:
    """Test that auth type dropdown appears for correct modems."""

    @pytest.mark.parametrize("modem_path,auth_type,expected_strategy", MULTI_AUTH_MODEMS)
    def test_multi_auth_modem_needs_selection(self, modem_path: str, auth_type: str, expected_strategy: str):
        """Modems with multiple auth types should show dropdown."""
        parser_name = modem_path_to_display_name(modem_path)
        parser = get_parser_by_name(parser_name)
        assert parser is not None, f"Parser not found for {parser_name}"

        adapter = get_auth_adapter_for_parser(parser.__name__)
        assert adapter is not None, f"Adapter not found for {parser.__name__}"

        auth_types = adapter.get_available_auth_types()
        assert len(auth_types) > 1, f"Expected multiple auth types, got {auth_types}"

    @pytest.mark.parametrize("modem_path,auth_type,expected_strategy", SINGLE_AUTH_MODEMS)
    def test_single_auth_modem_no_selection(self, modem_path: str, auth_type: str, expected_strategy: str):
        """Modems with single auth type should not show dropdown."""
        parser_name = modem_path_to_display_name(modem_path)
        parser = get_parser_by_name(parser_name)
        assert parser is not None, f"Parser not found for {parser_name}"

        adapter = get_auth_adapter_for_parser(parser.__name__)
        assert adapter is not None, f"Adapter not found for {parser.__name__}"

        auth_types = adapter.get_available_auth_types()
        assert len(auth_types) == 1, f"Expected single auth type, got {auth_types}"


# =============================================================================
# STATIC AUTH CONFIG TESTS
# =============================================================================


class TestStaticAuthConfig:
    """Test that static auth config is built correctly from modem.yaml."""

    @pytest.mark.parametrize("modem_path,auth_type,expected_strategy", MULTI_AUTH_MODEMS + SINGLE_AUTH_MODEMS)
    def test_build_static_auth_config(self, mock_hass, modem_path: str, auth_type: str, expected_strategy: str):
        """Static auth config should have correct strategy."""
        parser_name = modem_path_to_display_name(modem_path)
        parser = get_parser_by_name(parser_name)
        assert parser is not None

        config = build_static_auth_config(parser, auth_type)
        assert config is not None, f"Failed to build config for {parser_name} with {auth_type}"
        actual = config.get("auth_strategy")
        assert actual == expected_strategy, f"Expected {expected_strategy}, got {actual}"


# =============================================================================
# E2E KNOWN MODEM SETUP TESTS
# =============================================================================


class TestKnownModemSetupE2E:
    """E2E tests running known modem setup against mock servers.

    These tests verify the path where users select their modem model from
    the dropdown and we use modem.yaml as the source of truth for auth config.

    Tests run on both HTTP and HTTPS protocols to ensure protocol detection
    and connectivity work correctly regardless of transport.
    """

    @pytest.mark.parametrize("modem_path,auth_type,expected_strategy", MULTI_AUTH_MODEMS)
    def test_setup_with_static_auth(
        self,
        modem_path: str,
        auth_type: str,
        expected_strategy: str,
        protocol: str,
        ssl_context_for_protocol: ssl.SSLContext | None,
    ):
        """Known modem setup should succeed with static auth config from modem.yaml.

        Runs on both HTTP and HTTPS to verify protocol-agnostic behavior.
        """
        modem_dir = MODEMS_DIR / modem_path

        with MockModemServer.from_modem_path(
            modem_dir, auth_type=auth_type, ssl_context=ssl_context_for_protocol
        ) as server:
            # Build static auth config
            parser_name = modem_path_to_display_name(modem_path)
            parser = get_parser_by_name(parser_name)
            static_config = build_static_auth_config(parser, auth_type)

            # Run known modem setup - pass just host:port so protocol detection runs
            result = setup_modem(
                host=f"127.0.0.1:{server.port}",
                parser_class=parser,
                static_auth_config=static_config,
                username="admin",
                password="pw",
            )

            # Verify success
            assert result.success, f"Setup failed on {protocol}: {result.error}"
            actual = result.auth_strategy
            assert actual == expected_strategy, f"Expected {expected_strategy}, got {actual}"


# =============================================================================
# FORM AUTH E2E TESTS
# =============================================================================


class TestFormAuthE2E:
    """E2E tests for form-based authentication.

    Tests run on both HTTP and HTTPS protocols.
    """

    def test_sb6190_form_ajax_auth(self, protocol: str, ssl_context_for_protocol: ssl.SSLContext | None):
        """SB6190 form_ajax auth should authenticate and parse."""
        modem_dir = MODEMS_DIR / "arris/sb6190"

        with MockModemServer.from_modem_path(
            modem_dir, auth_type="form_ajax", ssl_context=ssl_context_for_protocol
        ) as server:
            parser = get_parser_by_name("ARRIS SB6190")
            static_config = build_static_auth_config(parser, "form_ajax")

            result = setup_modem(
                host=f"127.0.0.1:{server.port}",
                parser_class=parser,
                static_auth_config=static_config,
                username="admin",
                password="pw",
            )

            assert result.success, f"Form AJAX auth failed on {protocol}: {result.error}"
            assert result.auth_strategy == "form_ajax"

    def test_sb6190_wrong_credentials(self, protocol: str, ssl_context_for_protocol: ssl.SSLContext | None):
        """SB6190 form_ajax auth should fail with wrong credentials."""
        modem_dir = MODEMS_DIR / "arris/sb6190"

        with MockModemServer.from_modem_path(
            modem_dir, auth_type="form_ajax", ssl_context=ssl_context_for_protocol
        ) as server:
            parser = get_parser_by_name("ARRIS SB6190")
            static_config = build_static_auth_config(parser, "form_ajax")

            result = setup_modem(
                host=f"127.0.0.1:{server.port}",
                parser_class=parser,
                static_auth_config=static_config,
                username="wrong",
                password="wrong",
            )

            assert not result.success, "Should fail with wrong credentials"
            assert "credentials" in result.error.lower() or "login" in result.error.lower()


# =============================================================================
# NO AUTH E2E TESTS
# =============================================================================


class TestNoAuthE2E:
    """E2E tests for modems without authentication.

    Tests run on both HTTP and HTTPS protocols.
    """

    def test_sb6190_no_auth(self, protocol: str, ssl_context_for_protocol: ssl.SSLContext | None):
        """SB6190 no-auth variant should work without credentials."""
        modem_dir = MODEMS_DIR / "arris/sb6190"

        with MockModemServer.from_modem_path(
            modem_dir, auth_type="none", ssl_context=ssl_context_for_protocol
        ) as server:
            parser = get_parser_by_name("ARRIS SB6190")
            static_config = build_static_auth_config(parser, "none")

            result = setup_modem(
                host=f"127.0.0.1:{server.port}",
                parser_class=parser,
                static_auth_config=static_config,
                username="",
                password="",
            )

            assert result.success, f"No-auth failed on {protocol}: {result.error}"
            assert result.auth_strategy == "no_auth"


# =============================================================================
# WORKING URL FORMAT TESTS
# =============================================================================


class TestWorkingUrlFormat:
    """Tests to verify working_url is always a base URL without path.

    The working_url returned by setup_modem should only contain
    protocol://host:port, never a path like /st_docsis.html.

    Related to: Issue #75 (CGA2121 getting HTTPS with path in working_url)
    """

    def test_cga2121_working_url_is_base_url(self, protocol: str, ssl_context_for_protocol: ssl.SSLContext | None):
        """CGA2121 setup should return base URL without page path.

        Regression test for Issue #75: working_url was including
        /st_docsis.html path, causing protocol/auth issues.
        """
        modem_dir = MODEMS_DIR / "technicolor/cga2121"
        if not modem_dir.exists():
            pytest.skip("CGA2121 modem not found")

        with MockModemServer.from_modem_path(
            modem_dir, auth_type="form", ssl_context=ssl_context_for_protocol
        ) as server:
            parser = get_parser_by_name("Technicolor CGA2121")
            if not parser:
                pytest.skip("CGA2121 parser not registered")

            static_config = build_static_auth_config(parser, "form")

            result = setup_modem(
                host=f"127.0.0.1:{server.port}",
                parser_class=parser,
                static_auth_config=static_config,
                username="admin",
                password="pw",
            )

            assert result.success, f"Setup failed on {protocol}: {result.error}"

            # Key assertion: working_url should be base URL only
            working_url = result.working_url
            assert working_url is not None, "working_url should not be None"

            # Parse the URL - should not have a path beyond "/"
            from urllib.parse import urlparse

            parsed = urlparse(working_url)
            assert parsed.path in ("", "/"), (
                f"working_url should be base URL without path, " f"got path='{parsed.path}' in URL: {working_url}"
            )

    def test_mb7621_working_url_is_base_url(self, protocol: str, ssl_context_for_protocol: ssl.SSLContext | None):
        """MB7621 setup should return base URL without page path."""
        modem_dir = MODEMS_DIR / "motorola/mb7621"
        if not modem_dir.exists():
            pytest.skip("MB7621 modem not found")

        with MockModemServer.from_modem_path(
            modem_dir, auth_type="form", ssl_context=ssl_context_for_protocol
        ) as server:
            parser = get_parser_by_name("Motorola MB7621")
            if not parser:
                pytest.skip("MB7621 parser not registered")

            static_config = build_static_auth_config(parser, "form")

            result = setup_modem(
                host=f"127.0.0.1:{server.port}",
                parser_class=parser,
                static_auth_config=static_config,
                username="admin",
                password="pw",
            )

            assert result.success, f"Setup failed on {protocol}: {result.error}"
            self._assert_base_url_only(result.working_url)

    def _assert_base_url_only(self, working_url: str | None):
        """Assert that working_url is a base URL without path."""
        from urllib.parse import urlparse

        assert working_url is not None, "working_url should not be None"
        parsed = urlparse(working_url)
        assert parsed.path in ("", "/"), (
            f"working_url should be base URL without path, " f"got path='{parsed.path}' in URL: {working_url}"
        )
