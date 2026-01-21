"""Tests for modem.yaml to auth adapter bridge.

Tests the ModemConfigAuthAdapter which converts modem.yaml config to auth formats.
Schema uses auth.types{} as the single source of truth.

Test Organization:
- TestSyntheticConfigs: Core adapter tests using synthetic modem.yaml data
- TestRealModemConfigs: Integration tests with real modem configs (skip if unavailable)
"""

import pytest

from custom_components.cable_modem_monitor.modem_config import (
    ModemConfigAuthAdapter,
    get_auth_adapter_for_parser,
    get_modem_config_for_parser,
    load_modem_config,
)
from custom_components.cable_modem_monitor.modem_config.schema import (
    AuthConfig,
    FormAuthConfig,
    FormSuccessConfig,
    HnapAuthConfig,
    ModemConfig,
    PasswordEncoding,
    UrlTokenAuthConfig,
)

# =============================================================================
# Synthetic Config Tests - Test adapter logic without real modem dependencies
# =============================================================================


class TestSyntheticFormAuthAdapter:
    """Test form auth adapter with synthetic config."""

    @pytest.fixture
    def form_auth_config(self):
        """Create a synthetic form auth config using types{}."""
        return ModemConfig(
            manufacturer="Synthetic",
            model="FormAuth-1000",
            auth=AuthConfig(
                types={
                    "form": FormAuthConfig(
                        action="/goform/login",
                        method="POST",
                        username_field="user",
                        password_field="pass",
                        password_encoding=PasswordEncoding.BASE64,
                        success=FormSuccessConfig(redirect="/status.html"),
                    ),
                },
            ),
        )

    def test_get_available_auth_types(self, form_auth_config):
        """Test get_available_auth_types returns types."""
        adapter = ModemConfigAuthAdapter(form_auth_config)
        auth_types = adapter.get_available_auth_types()
        assert auth_types == ["form"]

    def test_get_auth_config_for_type_form(self, form_auth_config):
        """Test form config extraction."""
        adapter = ModemConfigAuthAdapter(form_auth_config)
        config = adapter.get_auth_config_for_type("form")

        assert config["action"] == "/goform/login"
        assert config["method"] == "POST"
        assert config["username_field"] == "user"
        assert config["password_field"] == "pass"
        assert config["password_encoding"] == "base64"

    def test_get_default_auth_type(self, form_auth_config):
        """Test get_default_auth_type returns first type."""
        adapter = ModemConfigAuthAdapter(form_auth_config)
        assert adapter.get_default_auth_type() == "form"

    def test_has_multiple_auth_types_false(self, form_auth_config):
        """Test has_multiple_auth_types returns False for single type."""
        adapter = ModemConfigAuthAdapter(form_auth_config)
        assert adapter.has_multiple_auth_types() is False

    def test_get_static_auth_config(self, form_auth_config):
        """Test get_static_auth_config returns full config dict."""
        adapter = ModemConfigAuthAdapter(form_auth_config)
        static = adapter.get_static_auth_config()

        assert static["auth_strategy"] == "form_plain"
        assert static["auth_form_config"] is not None
        assert static["auth_form_config"]["action"] == "/goform/login"
        assert static["auth_hnap_config"] is None
        assert static["auth_url_token_config"] is None


class TestSyntheticHnapAdapter:
    """Test HNAP adapter with synthetic config."""

    @pytest.fixture
    def hnap_config(self):
        """Create a synthetic HNAP auth config using types{}."""
        return ModemConfig(
            manufacturer="Synthetic",
            model="HNAP-2000",
            auth=AuthConfig(
                types={
                    "hnap": HnapAuthConfig(
                        endpoint="/HNAP1/",
                        namespace="http://example.com/HNAP1/",
                        empty_action_value="",
                        hmac_algorithm="md5",
                    ),
                },
            ),
        )

    def test_get_available_auth_types(self, hnap_config):
        """Test get_available_auth_types returns types."""
        adapter = ModemConfigAuthAdapter(hnap_config)
        auth_types = adapter.get_available_auth_types()
        assert auth_types == ["hnap"]

    def test_get_auth_config_for_type_hnap(self, hnap_config):
        """Test HNAP config extraction."""
        adapter = ModemConfigAuthAdapter(hnap_config)
        config = adapter.get_auth_config_for_type("hnap")

        assert config["endpoint"] == "/HNAP1/"
        assert config["namespace"] == "http://example.com/HNAP1/"
        assert config["empty_action_value"] == ""
        assert config["hmac_algorithm"] == "md5"

    def test_get_static_auth_config(self, hnap_config):
        """Test get_static_auth_config returns HNAP config."""
        adapter = ModemConfigAuthAdapter(hnap_config)
        static = adapter.get_static_auth_config()

        assert static["auth_strategy"] == "hnap_session"
        assert static["auth_hnap_config"] is not None
        assert static["auth_hnap_config"]["endpoint"] == "/HNAP1/"
        assert static["auth_form_config"] is None


class TestSyntheticUrlTokenAdapter:
    """Test URL token adapter with synthetic config."""

    @pytest.fixture
    def url_token_config(self):
        """Create a synthetic URL token auth config using types{}."""
        return ModemConfig(
            manufacturer="Synthetic",
            model="URLToken-3000",
            auth=AuthConfig(
                types={
                    "url_token": UrlTokenAuthConfig(
                        login_page="/status.html",
                        login_prefix="login_",
                        token_prefix="ct_",
                        session_cookie="sessionId",
                        success_indicator="Channel Data",
                    ),
                },
            ),
        )

    def test_get_available_auth_types(self, url_token_config):
        """Test get_available_auth_types returns types."""
        adapter = ModemConfigAuthAdapter(url_token_config)
        auth_types = adapter.get_available_auth_types()
        assert auth_types == ["url_token"]

    def test_get_auth_config_for_type_url_token(self, url_token_config):
        """Test URL token config extraction."""
        adapter = ModemConfigAuthAdapter(url_token_config)
        config = adapter.get_auth_config_for_type("url_token")

        assert config["login_page"] == "/status.html"
        assert config["data_page"] == "/status.html"  # Defaults to login_page
        assert config["login_prefix"] == "login_"
        assert config["token_prefix"] == "ct_"
        assert config["session_cookie_name"] == "sessionId"

    def test_get_url_token_config_with_separate_data_page(self):
        """Test URL token config with explicit data_page."""
        config = ModemConfig(
            manufacturer="Synthetic",
            model="URLToken-DataPage",
            auth=AuthConfig(
                types={
                    "url_token": UrlTokenAuthConfig(
                        login_page="/login.html",
                        data_page="/data.html",
                        session_cookie="sessionId",
                    ),
                },
            ),
        )
        adapter = ModemConfigAuthAdapter(config)

        url_config = adapter.get_auth_config_for_type("url_token")
        assert url_config["login_page"] == "/login.html"
        assert url_config["data_page"] == "/data.html"

    def test_get_static_auth_config(self, url_token_config):
        """Test get_static_auth_config returns URL token config."""
        adapter = ModemConfigAuthAdapter(url_token_config)
        static = adapter.get_static_auth_config()

        assert static["auth_strategy"] == "url_token_session"
        assert static["auth_url_token_config"] is not None
        assert static["auth_url_token_config"]["login_page"] == "/status.html"


class TestSyntheticNoAuthAdapter:
    """Test no-auth adapter with synthetic config."""

    @pytest.fixture
    def no_auth_config(self):
        """Create a synthetic no-auth config using types{}."""
        return ModemConfig(
            manufacturer="Synthetic",
            model="NoAuth-4000",
            auth=AuthConfig(types={"none": None}),
        )

    def test_get_available_auth_types(self, no_auth_config):
        """Test get_available_auth_types returns none type."""
        adapter = ModemConfigAuthAdapter(no_auth_config)
        auth_types = adapter.get_available_auth_types()
        assert auth_types == ["none"]

    def test_get_auth_config_for_type_none(self, no_auth_config):
        """Test auth config for 'none' returns empty dict."""
        adapter = ModemConfigAuthAdapter(no_auth_config)
        config = adapter.get_auth_config_for_type("none")
        assert config == {}

    def test_get_static_auth_config(self, no_auth_config):
        """Test get_static_auth_config returns no_auth strategy."""
        adapter = ModemConfigAuthAdapter(no_auth_config)
        static = adapter.get_static_auth_config()

        assert static["auth_strategy"] == "no_auth"
        assert static["auth_form_config"] is None
        assert static["auth_hnap_config"] is None
        assert static["auth_url_token_config"] is None


class TestSyntheticMultiAuthAdapter:
    """Test multi-auth type adapter with synthetic config."""

    @pytest.fixture
    def multi_auth_config(self):
        """Create a config with multiple auth types (like SB8200)."""
        return ModemConfig(
            manufacturer="Synthetic",
            model="MultiAuth",
            auth=AuthConfig(
                types={
                    "none": None,  # No auth variant
                    "url_token": UrlTokenAuthConfig(
                        login_page="/status.html",
                        login_prefix="login_",
                        token_prefix="ct_",
                        session_cookie="sessionId",
                        success_indicator="Channel Data",
                    ),
                },
            ),
        )

    def test_get_available_auth_types_multi(self, multi_auth_config):
        """Test get_available_auth_types returns multiple types."""
        adapter = ModemConfigAuthAdapter(multi_auth_config)
        auth_types = adapter.get_available_auth_types()

        assert len(auth_types) == 2
        assert "none" in auth_types
        assert "url_token" in auth_types

    def test_has_multiple_auth_types_true(self, multi_auth_config):
        """Test has_multiple_auth_types returns True for multi-type modem."""
        adapter = ModemConfigAuthAdapter(multi_auth_config)
        assert adapter.has_multiple_auth_types() is True

    def test_get_default_auth_type_multi(self, multi_auth_config):
        """Test get_default_auth_type returns first type for multi-type modem."""
        adapter = ModemConfigAuthAdapter(multi_auth_config)
        default = adapter.get_default_auth_type()
        # First key in types dict
        assert default == "none"

    def test_get_auth_config_for_type_none(self, multi_auth_config):
        """Test get_auth_config_for_type returns empty dict for 'none'."""
        adapter = ModemConfigAuthAdapter(multi_auth_config)
        config = adapter.get_auth_config_for_type("none")
        assert config == {}

    def test_get_auth_config_for_type_url_token(self, multi_auth_config):
        """Test get_auth_config_for_type returns url_token config."""
        adapter = ModemConfigAuthAdapter(multi_auth_config)
        config = adapter.get_auth_config_for_type("url_token")

        assert config is not None
        assert config["login_page"] == "/status.html"
        assert config["login_prefix"] == "login_"
        assert config["token_prefix"] == "ct_"
        assert config["session_cookie_name"] == "sessionId"

    def test_get_auth_config_for_type_unknown(self, multi_auth_config):
        """Test get_auth_config_for_type returns None for unknown type."""
        adapter = ModemConfigAuthAdapter(multi_auth_config)
        config = adapter.get_auth_config_for_type("unknown_type")
        assert config is None

    def test_get_static_auth_config_for_specific_type(self, multi_auth_config):
        """Test get_static_auth_config with specific auth type."""
        adapter = ModemConfigAuthAdapter(multi_auth_config)

        # Get config for url_token type
        static = adapter.get_static_auth_config("url_token")
        assert static["auth_strategy"] == "url_token_session"
        assert static["auth_url_token_config"] is not None

        # Get config for none type
        static = adapter.get_static_auth_config("none")
        assert static["auth_strategy"] == "no_auth"
        assert static["auth_url_token_config"] is None


# =============================================================================
# Real Modem Config Integration Tests - Validate adapter works with real configs
# These tests skip gracefully when modem configs aren't available.
# =============================================================================


def _get_modems_root():
    """Get modems root directory."""
    from custom_components.cable_modem_monitor.modem_config.loader import get_modems_root

    return get_modems_root()


class TestRealFormAuthModems:
    """Integration tests for form auth modems."""

    def test_form_auth_with_base64_encoding(self):
        """Test form auth extraction from a modem with base64 password encoding."""
        modem_path = _get_modems_root() / "motorola" / "mb7621"
        if not modem_path.exists():
            pytest.skip("Form auth modem config not available")

        config = load_modem_config(modem_path)
        adapter = ModemConfigAuthAdapter(config)

        # Get form config via types{}
        form_config = adapter.get_auth_config_for_type("form")
        assert form_config is not None
        assert "username_field" in form_config
        assert "password_field" in form_config
        assert form_config.get("password_encoding") == "base64"

    def test_form_config_for_auth_handler(self):
        """Test form config format for AuthHandler."""
        modem_path = _get_modems_root() / "motorola" / "mb7621"
        if not modem_path.exists():
            pytest.skip("Form auth modem config not available")

        config = load_modem_config(modem_path)
        adapter = ModemConfigAuthAdapter(config)

        form_config = adapter.get_auth_config_for_type("form")
        assert form_config is not None
        assert "action" in form_config
        assert "method" in form_config
        assert "username_field" in form_config
        assert "password_field" in form_config


class TestRealHnapModems:
    """Integration tests for HNAP modems."""

    def test_hnap_config_extraction(self):
        """Test HNAP config extraction from a real HNAP modem."""
        modem_path = _get_modems_root() / "arris" / "s33"
        if not modem_path.exists():
            pytest.skip("HNAP modem config not available")

        config = load_modem_config(modem_path)
        adapter = ModemConfigAuthAdapter(config)

        hnap_config = adapter.get_auth_config_for_type("hnap")
        assert hnap_config is not None
        assert hnap_config["endpoint"] == "/HNAP1/"
        assert "namespace" in hnap_config

    def test_hnap_static_config(self):
        """Test HNAP static auth config."""
        modem_path = _get_modems_root() / "arris" / "s33"
        if not modem_path.exists():
            pytest.skip("HNAP modem config not available")

        config = load_modem_config(modem_path)
        adapter = ModemConfigAuthAdapter(config)

        static = adapter.get_static_auth_config()
        assert static["auth_strategy"] == "hnap_session"
        assert static["auth_hnap_config"] is not None
        assert "endpoint" in static["auth_hnap_config"]


class TestRealUrlTokenModems:
    """Integration tests for URL token modems."""

    def test_url_token_config_extraction(self):
        """Test URL token config extraction from real modem."""
        modem_path = _get_modems_root() / "arris" / "sb8200"
        if not modem_path.exists():
            pytest.skip("URL token modem config not available")

        config = load_modem_config(modem_path)
        adapter = ModemConfigAuthAdapter(config)

        # SB8200 has multiple auth types - check if url_token is available
        if "url_token" in adapter.get_available_auth_types():
            url_token_config = adapter.get_auth_config_for_type("url_token")
            assert url_token_config is not None
            assert "login_page" in url_token_config
            assert "login_prefix" in url_token_config


class TestRealNoAuthModems:
    """Integration tests for no-auth modems."""

    def test_no_auth_returns_empty_config(self):
        """Test that no-auth modems return empty config."""
        modem_path = _get_modems_root() / "arris" / "sb6141"
        if not modem_path.exists():
            pytest.skip("No-auth modem config not available")

        config = load_modem_config(modem_path)
        adapter = ModemConfigAuthAdapter(config)

        # No-auth modems should have "none" in auth types
        auth_types = adapter.get_available_auth_types()
        assert "none" in auth_types

        # Get config for none type
        none_config = adapter.get_auth_config_for_type("none")
        assert none_config == {}


# =============================================================================
# Parser Lookup Tests
# =============================================================================


class TestGetModemConfigForParser:
    """Tests for get_modem_config_for_parser lookup."""

    def test_lookup_form_auth_parser(self):
        """Test lookup by parser class name for form auth."""
        config = get_modem_config_for_parser("MotorolaMB7621Parser")
        if config is None:
            pytest.skip("Form auth modem config not available")

        assert config.manufacturer == "Motorola"
        # Auth config should have types{}
        assert "form" in config.auth.types

    def test_lookup_hnap_parser(self):
        """Test lookup for HNAP parser."""
        config = get_modem_config_for_parser("ArrisS33HnapParser")
        if config is None:
            pytest.skip("HNAP modem config not available")

        assert "hnap" in config.auth.types

    def test_lookup_nonexistent_parser(self):
        """Test lookup for non-existent parser returns None."""
        config = get_modem_config_for_parser("NonExistentParser")
        assert config is None

    def test_lookup_is_cached(self):
        """Test that lookup results are cached."""
        # First call
        config1 = get_modem_config_for_parser("MotorolaMB7621Parser")
        # Second call should hit cache
        config2 = get_modem_config_for_parser("MotorolaMB7621Parser")

        if config1 is not None:
            assert config1 is config2  # Same object from cache


class TestGetAuthAdapterForParser:
    """Tests for get_auth_adapter_for_parser convenience function."""

    def test_get_adapter_for_form_auth_parser(self):
        """Test getting adapter for form auth parser."""
        adapter = get_auth_adapter_for_parser("MotorolaMB7621Parser")
        if adapter is None:
            pytest.skip("Form auth modem config not available")

        config = adapter.get_auth_config_for_type("form")
        assert config is not None
        assert "username_field" in config

    def test_get_adapter_nonexistent(self):
        """Test getting adapter for non-existent parser returns None."""
        adapter = get_auth_adapter_for_parser("NonExistentParser")
        assert adapter is None


# =============================================================================
# AuthHandler Integration Tests
# =============================================================================


class TestUrlPatternPrioritization:
    """Tests for URL pattern prioritization based on pages.data."""

    def test_data_page_prioritized_first(self):
        """Test that downstream_channels page is first in URL patterns."""
        from custom_components.cable_modem_monitor.modem_config.schema import PagesConfig

        config = ModemConfig(
            manufacturer="Test",
            model="DataPriority-1000",
            auth=AuthConfig(types={"none": None}),
            pages=PagesConfig(
                protected=["/secondary.html", "/primary.html"],
                data={"downstream_channels": "/primary.html"},
            ),
        )
        adapter = ModemConfigAuthAdapter(config)
        patterns = adapter.get_url_patterns()

        # Data page should be first despite being second in protected list
        protected_patterns = [p for p in patterns if p["auth_required"]]
        assert len(protected_patterns) == 2
        assert protected_patterns[0]["path"] == "/primary.html"
        assert protected_patterns[1]["path"] == "/secondary.html"

    def test_no_data_section_preserves_order(self):
        """Test that original order is preserved when no pages.data defined."""
        from custom_components.cable_modem_monitor.modem_config.schema import PagesConfig

        config = ModemConfig(
            manufacturer="Test",
            model="NoData-1000",
            auth=AuthConfig(types={"none": None}),
            pages=PagesConfig(
                protected=["/first.html", "/second.html"],
            ),
        )
        adapter = ModemConfigAuthAdapter(config)
        patterns = adapter.get_url_patterns()

        protected_patterns = [p for p in patterns if p["auth_required"]]
        assert protected_patterns[0]["path"] == "/first.html"
        assert protected_patterns[1]["path"] == "/second.html"

    def test_tc4400_data_page_first(self):
        """Test TC4400 has cmconnectionstatus.html first (regression test for #94)."""
        modem_path = _get_modems_root() / "technicolor" / "tc4400"
        if not modem_path.exists():
            pytest.skip("TC4400 modem config not available")

        config = load_modem_config(modem_path)
        adapter = ModemConfigAuthAdapter(config)
        patterns = adapter.get_url_patterns()

        protected_patterns = [p for p in patterns if p["auth_required"]]
        assert len(protected_patterns) >= 1
        assert protected_patterns[0]["path"] == "/cmconnectionstatus.html"


class TestAuthHandlerFromModemConfig:
    """Tests for AuthHandler.from_modem_config factory method."""

    def test_from_modem_config_form_auth(self):
        """Test creating AuthHandler from form auth modem.yaml."""
        from custom_components.cable_modem_monitor.core.auth.handler import AuthHandler
        from custom_components.cable_modem_monitor.core.auth.types import AuthStrategyType

        modem_path = _get_modems_root() / "motorola" / "mb7621"
        if not modem_path.exists():
            pytest.skip("Form auth modem config not available")

        config = load_modem_config(modem_path)
        handler = AuthHandler.from_modem_config(config)

        # Form auth with base64 encoding (controlled by password_encoding field)
        assert handler.strategy == AuthStrategyType.FORM_PLAIN
        assert "action" in handler.form_config
        assert "username_field" in handler.form_config
        assert handler.form_config.get("password_encoding") == "base64"

    def test_from_modem_config_hnap_auth(self):
        """Test creating AuthHandler from HNAP modem.yaml."""
        from custom_components.cable_modem_monitor.core.auth.handler import AuthHandler
        from custom_components.cable_modem_monitor.core.auth.types import AuthStrategyType

        modem_path = _get_modems_root() / "arris" / "s33"
        if not modem_path.exists():
            pytest.skip("HNAP modem config not available")

        config = load_modem_config(modem_path)
        handler = AuthHandler.from_modem_config(config)

        assert handler.strategy == AuthStrategyType.HNAP_SESSION
        assert handler.hnap_config["endpoint"] == "/HNAP1/"

    def test_from_parser_class_name(self):
        """Test creating AuthHandler from parser class name."""
        from custom_components.cable_modem_monitor.core.auth.handler import AuthHandler
        from custom_components.cable_modem_monitor.core.auth.types import AuthStrategyType

        handler = AuthHandler.from_parser("ArrisS33HnapParser")
        if handler is None:
            pytest.skip("HNAP modem config not available")

        assert handler.strategy == AuthStrategyType.HNAP_SESSION

    def test_from_parser_nonexistent(self):
        """Test from_parser returns None for non-existent parser."""
        from custom_components.cable_modem_monitor.core.auth.handler import AuthHandler

        handler = AuthHandler.from_parser("NonExistentParser")
        assert handler is None


# =============================================================================
# Metadata Accessor Tests - Table-Driven
# =============================================================================


def _build_full_config():
    """Build config with all metadata fields populated."""
    from custom_components.cable_modem_monitor.modem_config.schema import (
        BrandAlias,
        Capability,
        DetectionConfig,
        DocsisVersion,
        FixturesMetadata,
        HardwareConfig,
        PagesConfig,
        ParserConfig,
        ParserStatus,
        SessionConfig,
        StatusMetadata,
    )

    return ModemConfig(
        manufacturer="TestMfr",
        model="TestModel",
        parser=ParserConfig(**{"class": "TestParser", "module": "test.parser"}),
        auth=AuthConfig(
            types={
                "form": FormAuthConfig(
                    action="/login",
                    username_field="user",
                    password_field="pass",
                ),
            },
            session=SessionConfig(logout_endpoint="/logout.asp"),
        ),
        status_info=StatusMetadata(
            status=ParserStatus.VERIFIED,
            verification_source="https://github.com/example/issue/1",
        ),
        capabilities=[Capability.SCQAM_DOWNSTREAM, Capability.SCQAM_UPSTREAM],
        hardware=HardwareConfig(
            docsis_version=DocsisVersion.V31,
            release_date="2020-01",
            end_of_life="2025-12",
        ),
        detection=DetectionConfig(
            pre_auth=["TestMfr", "TestModel"],
            post_auth=["Channel Data"],
            model_aliases=["TM-1000", "TestModel Pro"],
        ),
        brands=[
            BrandAlias(manufacturer="AltBrand", model="AltModel"),
        ],
        fixtures=FixturesMetadata(path="modems/testmfr/testmodel/fixtures"),
        pages=PagesConfig(
            public=["/public.html"],
            protected=["/data.html", "/status.html"],
            data={"downstream_channels": "/data.html"},
        ),
    )


def _build_minimal_config():
    """Build config with minimal fields (no optional metadata)."""
    return ModemConfig(
        manufacturer="Test",
        model="Minimal",
        auth=AuthConfig(types={"none": None}),
    )


# ┌─────────────────────────┬───────────────┬──────────────────────────────────────────┬─────────────────────────┐
# │ method                  │ use_full      │ expected                                 │ description             │
# ├─────────────────────────┼───────────────┼──────────────────────────────────────────┼─────────────────────────┤
# │ get_logout_endpoint     │ True          │ "/logout.asp"                            │ configured logout       │
# │ get_logout_endpoint     │ False         │ None                                     │ no session config       │
# │ get_status              │ True          │ "verified"                               │ configured status       │
# │ get_status              │ False         │ "awaiting_verification"                  │ default status          │
# │ get_verification_source │ True          │ "https://github.com/example/issue/1"    │ configured source       │
# │ get_verification_source │ False         │ None                                     │ no status_info          │
# │ get_release_date        │ True          │ "2020-01"                                │ configured date         │
# │ get_release_date        │ False         │ None                                     │ no hardware             │
# │ get_end_of_life         │ True          │ "2025-12"                                │ configured eol          │
# │ get_end_of_life         │ False         │ None                                     │ no hardware             │
# │ get_docsis_version      │ True          │ "3.1"                                    │ configured version      │
# │ get_docsis_version      │ False         │ None                                     │ no hardware             │
# └─────────────────────────┴───────────────┴──────────────────────────────────────────┴─────────────────────────┘
#
# fmt: off
METADATA_ACCESSOR_CASES = [
    # (method,                  use_full, expected,                                  description)
    ("get_logout_endpoint",     True,     "/logout.asp",                             "configured logout"),
    ("get_logout_endpoint",     False,    None,                                      "no session config"),
    ("get_status",              True,     "verified",                                "configured status"),
    ("get_status",              False,    "awaiting_verification",                   "default status"),
    ("get_verification_source", True,     "https://github.com/example/issue/1",      "configured source"),
    ("get_verification_source", False,    None,                                      "no status_info"),
    ("get_release_date",        True,     "2020-01",                                 "configured date"),
    ("get_release_date",        False,    None,                                      "no hardware"),
    ("get_end_of_life",         True,     "2025-12",                                 "configured eol"),
    ("get_end_of_life",         False,    None,                                      "no hardware"),
    ("get_docsis_version",      True,     "3.1",                                     "configured version"),
    ("get_docsis_version",      False,    None,                                      "no hardware"),
]
# fmt: on


class TestMetadataAccessors:
    """Tests for metadata accessor methods using table-driven approach."""

    @pytest.mark.parametrize("method,use_full,expected,desc", METADATA_ACCESSOR_CASES)
    def test_metadata_accessor(self, method, use_full, expected, desc):
        """Table-driven test for metadata accessors."""
        config = _build_full_config() if use_full else _build_minimal_config()
        adapter = ModemConfigAuthAdapter(config)
        result = getattr(adapter, method)()
        assert result == expected, f"{method}: {desc}"

    def test_get_capabilities(self):
        """Test get_capabilities returns capability list (special case - list check)."""
        adapter = ModemConfigAuthAdapter(_build_full_config())
        caps = adapter.get_capabilities()
        assert "scqam_downstream" in caps
        assert "scqam_upstream" in caps


class TestIdentityAccessors:
    """Tests for identity accessor methods."""

    @pytest.fixture
    def config_with_detection(self):
        """Create config with detection and brand aliases."""
        from custom_components.cable_modem_monitor.modem_config.schema import (
            BrandAlias,
            DetectionConfig,
        )

        return ModemConfig(
            manufacturer="TestMfr",
            model="TestModel",
            auth=AuthConfig(types={"none": None}),
            detection=DetectionConfig(
                pre_auth=["pre_pattern"],
                post_auth=["post_pattern"],
                model_aliases=["Alias1", "Alias2"],
            ),
            brands=[
                BrandAlias(manufacturer="Brand1", model="Model1"),
                BrandAlias(manufacturer="Brand2", model="Model2"),
            ],
        )

    def test_get_name(self, config_with_detection):
        """Test get_name returns formatted display name."""
        adapter = ModemConfigAuthAdapter(config_with_detection)
        assert adapter.get_name() == "TestMfr TestModel"

    def test_get_manufacturer(self, config_with_detection):
        """Test get_manufacturer returns manufacturer."""
        adapter = ModemConfigAuthAdapter(config_with_detection)
        assert adapter.get_manufacturer() == "TestMfr"

    def test_get_model(self, config_with_detection):
        """Test get_model returns model."""
        adapter = ModemConfigAuthAdapter(config_with_detection)
        assert adapter.get_model() == "TestModel"

    def test_get_models_with_aliases(self, config_with_detection):
        """Test get_models returns model plus aliases."""
        adapter = ModemConfigAuthAdapter(config_with_detection)
        models = adapter.get_models()
        assert models == ["TestModel", "Alias1", "Alias2"]

    def test_get_models_without_detection(self):
        """Test get_models returns just primary model when no detection."""
        config = ModemConfig(
            manufacturer="Test",
            model="SingleModel",
            auth=AuthConfig(types={"none": None}),
        )
        adapter = ModemConfigAuthAdapter(config)
        assert adapter.get_models() == ["SingleModel"]

    def test_get_detection_hints_with_config(self, config_with_detection):
        """Test get_detection_hints returns all hints."""
        adapter = ModemConfigAuthAdapter(config_with_detection)
        hints = adapter.get_detection_hints()
        assert hints["pre_auth"] == ["pre_pattern"]
        assert hints["post_auth"] == ["post_pattern"]
        assert hints["model_aliases"] == ["Alias1", "Alias2"]

    def test_get_detection_hints_without_config(self):
        """Test get_detection_hints returns empty lists when no detection."""
        config = ModemConfig(
            manufacturer="Test",
            model="NoDetection",
            auth=AuthConfig(types={"none": None}),
        )
        adapter = ModemConfigAuthAdapter(config)
        hints = adapter.get_detection_hints()
        assert hints == {"pre_auth": [], "post_auth": [], "model_aliases": []}

    def test_get_brands(self, config_with_detection):
        """Test get_brands returns brand alias dicts."""
        adapter = ModemConfigAuthAdapter(config_with_detection)
        brands = adapter.get_brands()
        assert len(brands) == 2
        assert brands[0] == {"manufacturer": "Brand1", "model": "Model1"}
        assert brands[1] == {"manufacturer": "Brand2", "model": "Model2"}

    def test_get_all_names(self, config_with_detection):
        """Test get_all_names returns primary and brand names."""
        adapter = ModemConfigAuthAdapter(config_with_detection)
        names = adapter.get_all_names()
        assert names == ["TestMfr TestModel", "Brand1 Model1", "Brand2 Model2"]


class TestFixturesAccessor:
    """Tests for fixtures accessor."""

    def test_get_fixtures_path_configured(self):
        """Test get_fixtures_path returns path when configured."""
        from custom_components.cable_modem_monitor.modem_config.schema import FixturesMetadata

        config = ModemConfig(
            manufacturer="Test",
            model="WithFixtures",
            auth=AuthConfig(types={"none": None}),
            fixtures=FixturesMetadata(path="modems/test/withfixtures/fixtures"),
        )
        adapter = ModemConfigAuthAdapter(config)
        assert adapter.get_fixtures_path() == "modems/test/withfixtures/fixtures"

    def test_get_fixtures_path_none(self):
        """Test get_fixtures_path returns None when not configured."""
        config = ModemConfig(
            manufacturer="Test",
            model="NoFixtures",
            auth=AuthConfig(types={"none": None}),
        )
        adapter = ModemConfigAuthAdapter(config)
        assert adapter.get_fixtures_path() is None


class TestUrlPatternsWithPublic:
    """Tests for URL patterns with public pages."""

    def test_url_patterns_with_public_pages(self):
        """Test URL patterns includes public pages without auth."""
        from custom_components.cable_modem_monitor.modem_config.schema import PagesConfig

        config = ModemConfig(
            manufacturer="Test",
            model="PublicPages",
            auth=AuthConfig(types={"none": None}),
            pages=PagesConfig(
                public=["/public1.html", "/public2.html"],
                protected=["/protected.html"],
            ),
        )
        adapter = ModemConfigAuthAdapter(config)
        patterns = adapter.get_url_patterns()

        public_patterns = [p for p in patterns if not p["auth_required"]]
        assert len(public_patterns) == 2
        assert public_patterns[0]["path"] == "/public1.html"
        assert public_patterns[0]["auth_method"] == "none"
        assert public_patterns[1]["path"] == "/public2.html"


# =============================================================================
# Helper Function Tests - Table-Driven
# =============================================================================

# ┌────────────────────────────────┬─────────────────────────┬──────────────────────┐
# │ function                       │ parser                  │ expected_none        │
# ├────────────────────────────────┼─────────────────────────┼──────────────────────┤
# │ get_url_patterns_for_parser    │ NonExistentParser       │ True                 │
# │ get_capabilities_for_parser    │ NonExistentParser       │ True                 │
# │ get_docsis_version_for_parser  │ NonExistentParser       │ True                 │
# │ get_detection_hints_for_parser │ NonExistentParser       │ True                 │
# └────────────────────────────────┴─────────────────────────┴──────────────────────┘
#
# fmt: off
HELPER_NOT_FOUND_CASES = [
    # (function_name,                   parser_name,       description)
    ("get_url_patterns_for_parser",     "NonExistentParser", "unknown parser returns None"),
    ("get_capabilities_for_parser",     "NonExistentParser", "unknown parser returns None"),
    ("get_docsis_version_for_parser",   "NonExistentParser", "unknown parser returns None"),
    ("get_detection_hints_for_parser",  "NonExistentParser", "unknown parser returns None"),
]
# fmt: on


class TestHelperFunctions:
    """Tests for module-level helper functions."""

    @pytest.mark.parametrize("func_name,parser,desc", HELPER_NOT_FOUND_CASES)
    def test_helper_not_found(self, func_name, parser, desc):
        """Table-driven test: helper functions return None for unknown parsers."""
        from custom_components.cable_modem_monitor.modem_config import adapter

        func = getattr(adapter, func_name)
        result = func(parser)
        assert result is None, f"{func_name}: {desc}"

    def test_get_url_patterns_for_parser_found(self):
        """Test get_url_patterns_for_parser returns patterns for known parser."""
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_url_patterns_for_parser,
        )

        patterns = get_url_patterns_for_parser("TechnicolorTC4400Parser")
        if patterns is None:
            pytest.skip("TC4400 modem config not available")
        assert len(patterns) > 0
        assert all("path" in p for p in patterns)

    def test_get_capabilities_for_parser_found(self):
        """Test get_capabilities_for_parser returns list for known parser."""
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_capabilities_for_parser,
        )

        caps = get_capabilities_for_parser("ArrisS33HnapParser")
        if caps is None:
            pytest.skip("S33 modem config not available")
        assert isinstance(caps, list)

    def test_get_docsis_version_for_parser_found(self):
        """Test get_docsis_version_for_parser returns version for known parser."""
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_docsis_version_for_parser,
        )

        version = get_docsis_version_for_parser("ArrisS33HnapParser")
        if version is None:
            pytest.skip("S33 modem config not available or no hardware config")
        assert version in ("3.0", "3.1", "4.0")

    def test_get_detection_hints_for_parser_found(self):
        """Test get_detection_hints_for_parser returns hints for known parser."""
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_detection_hints_for_parser,
        )

        hints = get_detection_hints_for_parser("MotorolaMB7621Parser")
        if hints is None:
            pytest.skip("MB7621 modem config not available")
        assert "pre_auth" in hints
        assert "post_auth" in hints

    def test_clear_cache(self):
        """Test clear_cache clears the lookup cache."""
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            clear_cache,
            get_modem_config_for_parser,
        )

        # Populate cache
        get_modem_config_for_parser("MotorolaMB7621Parser")

        # Clear and verify no exception
        clear_cache()

        # Cache should work again after clear
        get_modem_config_for_parser("MotorolaMB7621Parser")

    def test_fallback_parser_skipped(self):
        """Test that FallbackParser names skip discovery fallback."""
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_modem_config_for_parser,
        )

        # Should return None without triggering discovery
        config = get_modem_config_for_parser("SomeFallbackParser")
        assert config is None


# =============================================================================
# Static Auth Config Tests - For "modem.yaml as source of truth" architecture
# =============================================================================


class TestStaticAuthConfigSynthetic:
    """Tests for get_static_auth_config() with synthetic configs."""

    def test_no_auth_type(self):
        """Test no-auth modem returns no_auth strategy with all None configs."""
        config = ModemConfig(
            manufacturer="Synthetic",
            model="NoAuth",
            auth=AuthConfig(types={"none": None}),
        )
        adapter = ModemConfigAuthAdapter(config)
        static = adapter.get_static_auth_config()

        assert static["auth_strategy"] == "no_auth"
        assert static["auth_form_config"] is None
        assert static["auth_hnap_config"] is None
        assert static["auth_url_token_config"] is None

    def test_form_auth_type(self):
        """Test form auth modem returns form_plain strategy with form config."""
        config = ModemConfig(
            manufacturer="Synthetic",
            model="FormAuth",
            auth=AuthConfig(
                types={
                    "form": FormAuthConfig(
                        action="/goform/login",
                        method="POST",
                        username_field="user",
                        password_field="pass",
                        password_encoding=PasswordEncoding.BASE64,
                        hidden_fields={"csrf": "token123"},
                    ),
                },
            ),
        )
        adapter = ModemConfigAuthAdapter(config)
        static = adapter.get_static_auth_config()

        assert static["auth_strategy"] == "form_plain"
        assert static["auth_form_config"] is not None
        assert static["auth_form_config"]["action"] == "/goform/login"
        assert static["auth_form_config"]["username_field"] == "user"
        assert static["auth_form_config"]["password_field"] == "pass"
        assert static["auth_form_config"]["password_encoding"] == "base64"
        assert static["auth_hnap_config"] is None
        assert static["auth_url_token_config"] is None

    def test_hnap_auth_type(self):
        """Test HNAP modem returns hnap_session strategy with hnap config."""
        config = ModemConfig(
            manufacturer="Synthetic",
            model="HnapAuth",
            auth=AuthConfig(
                types={
                    "hnap": HnapAuthConfig(
                        endpoint="/HNAP1/",
                        namespace="http://purenetworks.com/HNAP1/",
                        hmac_algorithm="md5",
                    ),
                },
            ),
        )
        adapter = ModemConfigAuthAdapter(config)
        static = adapter.get_static_auth_config()

        assert static["auth_strategy"] == "hnap_session"
        assert static["auth_hnap_config"] is not None
        assert static["auth_hnap_config"]["endpoint"] == "/HNAP1/"
        assert static["auth_hnap_config"]["hmac_algorithm"] == "md5"
        assert static["auth_form_config"] is None
        assert static["auth_url_token_config"] is None

    def test_url_token_auth_type(self):
        """Test URL token modem returns url_token_session strategy."""
        config = ModemConfig(
            manufacturer="Synthetic",
            model="UrlTokenAuth",
            auth=AuthConfig(
                types={
                    "url_token": UrlTokenAuthConfig(
                        login_page="/status.html",
                        data_page="/status.html",
                        login_prefix="login_",
                        token_prefix="ct_",
                        session_cookie="credential",
                        success_indicator="Channel",
                    ),
                },
            ),
        )
        adapter = ModemConfigAuthAdapter(config)
        static = adapter.get_static_auth_config()

        assert static["auth_strategy"] == "url_token_session"
        assert static["auth_url_token_config"] is not None
        assert static["auth_url_token_config"]["login_page"] == "/status.html"
        assert static["auth_url_token_config"]["login_prefix"] == "login_"
        assert static["auth_form_config"] is None
        assert static["auth_hnap_config"] is None


# ┌──────────────────────────┬───────────────────┬──────────────────────────────────────────┐
# │ parser_name              │ expected_strategy │ description                              │
# ├──────────────────────────┼───────────────────┼──────────────────────────────────────────┤
# │ MotorolaMB7621Parser     │ form_plain        │ Form auth with base64 encoding           │
# │ MotorolaMB8611HnapParser │ hnap_session      │ HNAP/SOAP with HMAC-MD5                  │
# │ ArrisS33HnapParser       │ hnap_session      │ HNAP/SOAP with HMAC-MD5                  │
# │ ArrisSB6141Parser        │ no_auth           │ No authentication required               │
# │ ArrisG54Parser           │ form_plain        │ Basic form authentication                │
# │ TechnicolorCGA2121Parser │ form_plain        │ Form auth with base64 encoding           │
# └──────────────────────────┴───────────────────┴──────────────────────────────────────────┘
#
# fmt: off
STATIC_AUTH_CONFIG_INTEGRATION_CASES = [
    # (parser_name,              expected_strategy,    description)
    ("MotorolaMB7621Parser",     "form_plain",        "form auth with base64"),
    ("MotorolaMB8611HnapParser", "hnap_session",      "HNAP auth"),
    ("ArrisS33HnapParser",       "hnap_session",      "HNAP auth"),
    ("ArrisSB6141Parser",        "no_auth",           "no auth"),
    ("ArrisG54Parser",           "form_plain",        "form plain"),
    ("TechnicolorCGA2121Parser", "form_plain",        "form auth with base64"),
]
# fmt: on


class TestStaticAuthConfigIntegration:
    """Integration tests for get_static_auth_config() with real modem configs."""

    @pytest.mark.parametrize("parser_name,expected_strategy,desc", STATIC_AUTH_CONFIG_INTEGRATION_CASES)
    def test_static_auth_config_for_parser(self, parser_name, expected_strategy, desc):
        """Table-driven test: verify static auth config matches expected strategy."""
        adapter = get_auth_adapter_for_parser(parser_name)
        if adapter is None:
            pytest.skip(f"{parser_name} modem config not available")

        static = adapter.get_static_auth_config()

        assert static["auth_strategy"] == expected_strategy, f"Failed for {parser_name}: {desc}"

        # Verify the appropriate config is populated
        if expected_strategy == "form_plain":
            assert static["auth_form_config"] is not None, f"{parser_name} should have form config"
            assert "action" in static["auth_form_config"]
            assert "username_field" in static["auth_form_config"]
        elif expected_strategy == "hnap_session":
            assert static["auth_hnap_config"] is not None, f"{parser_name} should have HNAP config"
            assert "endpoint" in static["auth_hnap_config"]
            assert "hmac_algorithm" in static["auth_hnap_config"]
        elif expected_strategy == "url_token_session":
            assert static["auth_url_token_config"] is not None, f"{parser_name} should have URL token config"
            assert "login_page" in static["auth_url_token_config"]
        elif expected_strategy == "no_auth":
            # No auth - all configs should be None
            assert static["auth_form_config"] is None
            assert static["auth_hnap_config"] is None
            assert static["auth_url_token_config"] is None

    def test_fallback_parser_has_no_adapter(self):
        """Verify fallback parser returns None adapter (triggers dynamic discovery)."""
        adapter = get_auth_adapter_for_parser("UniversalFallbackParser")
        assert adapter is None, "Fallback parser should not have a modem.yaml"


# =============================================================================
# Auth Types Integration Tests - For modems with user-selectable auth variants
# =============================================================================


class TestAuthTypesIntegration:
    """Integration tests for auth.types{} with real modem configs."""

    def test_sb8200_has_multiple_auth_types(self):
        """Test SB8200 has multiple auth types (none, url_token)."""
        adapter = get_auth_adapter_for_parser("ArrisSB8200Parser")
        if adapter is None:
            pytest.skip("SB8200 modem config not available")

        # SB8200 should have auth.types{} with none and url_token
        auth_types = adapter.get_available_auth_types()

        # If auth.types{} is configured, should have both
        if adapter.has_multiple_auth_types():
            assert "none" in auth_types
            assert "url_token" in auth_types
        else:
            # Fallback to single strategy
            assert len(auth_types) == 1

    def test_sb6190_has_multiple_auth_types(self):
        """Test SB6190 has multiple auth types (none, form)."""
        adapter = get_auth_adapter_for_parser("ArrisSB6190Parser")
        if adapter is None:
            pytest.skip("SB6190 modem config not available")

        auth_types = adapter.get_available_auth_types()

        # If auth.types{} is configured, should have both
        if adapter.has_multiple_auth_types():
            assert "none" in auth_types
            assert "form" in auth_types
        else:
            # Fallback to single strategy (none)
            assert len(auth_types) == 1

    def test_mb7621_single_auth_type(self):
        """Test MB7621 has single auth type (form)."""
        adapter = get_auth_adapter_for_parser("MotorolaMB7621Parser")
        if adapter is None:
            pytest.skip("MB7621 modem config not available")

        # MB7621 should have single auth type
        assert adapter.has_multiple_auth_types() is False
        auth_types = adapter.get_available_auth_types()
        assert len(auth_types) == 1
        assert auth_types[0] == "form"
