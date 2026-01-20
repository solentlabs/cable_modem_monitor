"""Tests for modem.yaml to auth adapter bridge.

Tests the ModemConfigAuthAdapter which converts modem.yaml config to legacy auth hint formats.

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
    AuthStrategy,
    FormAuthConfig,
    FormSuccessConfig,
    HnapAuthConfig,
    ModemConfig,
    UrlTokenAuthConfig,
)

# =============================================================================
# Synthetic Config Tests - Test adapter logic without real modem dependencies
# =============================================================================


class TestSyntheticFormAuthAdapter:
    """Test form auth adapter with synthetic config."""

    @pytest.fixture
    def form_auth_config(self):
        """Create a synthetic form auth config."""
        return ModemConfig(
            manufacturer="Synthetic",
            model="FormAuth-1000",
            auth=AuthConfig(
                strategy=AuthStrategy.FORM,
                form=FormAuthConfig(
                    action="/goform/login",
                    method="POST",
                    username_field="user",
                    password_field="pass",
                    password_encoding="base64",
                    success=FormSuccessConfig(redirect="/status.html"),
                ),
            ),
        )

    def test_get_auth_form_hints(self, form_auth_config):
        """Test form hints extraction."""
        adapter = ModemConfigAuthAdapter(form_auth_config)
        hints = adapter.get_auth_form_hints()

        assert hints["username_field"] == "user"
        assert hints["password_field"] == "pass"
        assert hints["password_encoding"] == "base64"
        assert hints["login_url"] == "/goform/login"
        assert hints["success_redirect"] == "/status.html"

    def test_get_form_config(self, form_auth_config):
        """Test form config for AuthHandler."""
        adapter = ModemConfigAuthAdapter(form_auth_config)
        config = adapter.get_form_config()

        assert config["action"] == "/goform/login"
        assert config["method"] == "POST"
        assert config["username_field"] == "user"
        assert config["password_field"] == "pass"

    def test_js_auth_hints_returns_empty(self, form_auth_config):
        """Test JS auth hints returns empty dict for form auth."""
        adapter = ModemConfigAuthAdapter(form_auth_config)
        assert adapter.get_js_auth_hints() == {}


class TestSyntheticHnapAdapter:
    """Test HNAP adapter with synthetic config."""

    @pytest.fixture
    def hnap_config(self):
        """Create a synthetic HNAP auth config."""
        return ModemConfig(
            manufacturer="Synthetic",
            model="HNAP-2000",
            auth=AuthConfig(
                strategy=AuthStrategy.HNAP,
                hnap=HnapAuthConfig(
                    endpoint="/HNAP1/",
                    namespace="http://example.com/HNAP1/",
                    login_action="Login",
                    empty_action_value="",
                    hmac_algorithm="md5",
                ),
            ),
        )

    def test_get_hnap_hints(self, hnap_config):
        """Test HNAP hints extraction."""
        adapter = ModemConfigAuthAdapter(hnap_config)
        hints = adapter.get_hnap_hints()

        assert hints["endpoint"] == "/HNAP1/"
        assert hints["namespace"] == "http://example.com/HNAP1/"
        assert hints["empty_action_value"] == ""
        assert hints["hmac_algorithm"] == "md5"

    def test_get_hnap_config(self, hnap_config):
        """Test HNAP config for AuthHandler."""
        adapter = ModemConfigAuthAdapter(hnap_config)
        config = adapter.get_hnap_config()

        assert config["endpoint"] == "/HNAP1/"
        assert config["namespace"] == "http://example.com/HNAP1/"

    def test_form_hints_returns_empty(self, hnap_config):
        """Test form hints returns empty dict for HNAP auth."""
        adapter = ModemConfigAuthAdapter(hnap_config)
        assert adapter.get_auth_form_hints() == {}


class TestSyntheticUrlTokenAdapter:
    """Test URL token adapter with synthetic config."""

    @pytest.fixture
    def url_token_config(self):
        """Create a synthetic URL token auth config."""
        return ModemConfig(
            manufacturer="Synthetic",
            model="URLToken-3000",
            auth=AuthConfig(
                strategy=AuthStrategy.URL_TOKEN,
                url_token=UrlTokenAuthConfig(
                    login_page="/status.html",
                    login_prefix="login_",
                    token_prefix="ct_",
                    session_cookie="sessionId",
                    success_indicator="Channel Data",
                ),
            ),
        )

    def test_get_js_auth_hints(self, url_token_config):
        """Test JS auth hints extraction."""
        adapter = ModemConfigAuthAdapter(url_token_config)
        hints = adapter.get_js_auth_hints()

        assert hints  # Non-empty dict
        assert hints["pattern"] == "url_token_session"
        assert hints["login_prefix"] == "login_"
        assert hints["token_prefix"] == "ct_"
        assert hints["session_cookie_name"] == "sessionId"

    def test_get_url_token_config(self, url_token_config):
        """Test URL token config extraction."""
        adapter = ModemConfigAuthAdapter(url_token_config)
        config = adapter.get_url_token_config()

        assert config["login_page"] == "/status.html"
        assert config["data_page"] == "/status.html"  # Defaults to login_page
        assert config["login_prefix"] == "login_"
        assert config["token_prefix"] == "ct_"

    def test_get_url_token_config_with_separate_data_page(self):
        """Test URL token config with explicit data_page."""
        config = ModemConfig(
            manufacturer="Synthetic",
            model="URLToken-DataPage",
            auth=AuthConfig(
                strategy=AuthStrategy.URL_TOKEN,
                url_token=UrlTokenAuthConfig(
                    login_page="/login.html",
                    data_page="/data.html",
                    session_cookie="sessionId",
                ),
            ),
        )
        adapter = ModemConfigAuthAdapter(config)

        url_config = adapter.get_url_token_config()
        assert url_config["login_page"] == "/login.html"
        assert url_config["data_page"] == "/data.html"

        hints = adapter.get_js_auth_hints()
        assert hints["login_page"] == "/login.html"
        assert hints["data_page"] == "/data.html"


class TestSyntheticNoAuthAdapter:
    """Test no-auth adapter with synthetic config."""

    @pytest.fixture
    def no_auth_config(self):
        """Create a synthetic no-auth config."""
        return ModemConfig(
            manufacturer="Synthetic",
            model="NoAuth-4000",
            auth=AuthConfig(strategy=AuthStrategy.NONE),
        )

    def test_form_hints_returns_empty(self, no_auth_config):
        """Test form hints returns empty for no-auth."""
        adapter = ModemConfigAuthAdapter(no_auth_config)
        assert adapter.get_auth_form_hints() == {}

    def test_js_auth_hints_returns_empty(self, no_auth_config):
        """Test JS auth hints returns empty dict for no-auth."""
        adapter = ModemConfigAuthAdapter(no_auth_config)
        assert adapter.get_js_auth_hints() == {}


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

        hints = adapter.get_auth_form_hints()

        assert "username_field" in hints
        assert "password_field" in hints
        assert hints.get("password_encoding") == "base64"

    def test_form_config_for_auth_handler(self):
        """Test form config format for AuthHandler."""
        modem_path = _get_modems_root() / "motorola" / "mb7621"
        if not modem_path.exists():
            pytest.skip("Form auth modem config not available")

        config = load_modem_config(modem_path)
        adapter = ModemConfigAuthAdapter(config)

        form_config = adapter.get_form_config()

        assert "action" in form_config
        assert "method" in form_config
        assert "username_field" in form_config
        assert "password_field" in form_config


class TestRealHnapModems:
    """Integration tests for HNAP modems."""

    def test_hnap_hints_extraction(self):
        """Test HNAP hints extraction from a real HNAP modem."""
        modem_path = _get_modems_root() / "arris" / "s33"
        if not modem_path.exists():
            pytest.skip("HNAP modem config not available")

        config = load_modem_config(modem_path)
        adapter = ModemConfigAuthAdapter(config)

        hints = adapter.get_hnap_hints()

        assert hints["endpoint"] == "/HNAP1/"
        assert "namespace" in hints

    def test_hnap_config_for_auth_handler(self):
        """Test HNAP config format for AuthHandler."""
        modem_path = _get_modems_root() / "arris" / "s33"
        if not modem_path.exists():
            pytest.skip("HNAP modem config not available")

        config = load_modem_config(modem_path)
        adapter = ModemConfigAuthAdapter(config)

        hnap_config = adapter.get_hnap_config()

        assert "endpoint" in hnap_config
        assert "namespace" in hnap_config


class TestRealUrlTokenModems:
    """Integration tests for URL token modems."""

    def test_js_auth_hints_extraction(self):
        """Test JS auth hints extraction from a real URL token modem."""
        modem_path = _get_modems_root() / "arris" / "sb8200"
        if not modem_path.exists():
            pytest.skip("URL token modem config not available")

        config = load_modem_config(modem_path)
        adapter = ModemConfigAuthAdapter(config)

        hints = adapter.get_js_auth_hints()

        assert hints  # Non-empty dict
        assert hints["pattern"] == "url_token_session"
        assert "login_prefix" in hints
        assert "token_prefix" in hints

    def test_url_token_config_extraction(self):
        """Test URL token config extraction from real modem."""
        modem_path = _get_modems_root() / "arris" / "sb8200"
        if not modem_path.exists():
            pytest.skip("URL token modem config not available")

        config = load_modem_config(modem_path)
        adapter = ModemConfigAuthAdapter(config)

        url_token_config = adapter.get_url_token_config()

        assert "login_page" in url_token_config
        assert "login_prefix" in url_token_config


class TestRealNoAuthModems:
    """Integration tests for no-auth modems."""

    def test_no_auth_returns_empty_hints(self):
        """Test that no-auth modems return empty hints."""
        modem_path = _get_modems_root() / "arris" / "sb6141"
        if not modem_path.exists():
            pytest.skip("No-auth modem config not available")

        config = load_modem_config(modem_path)
        adapter = ModemConfigAuthAdapter(config)

        # No-auth modems should return empty form hints
        form_hints = adapter.get_auth_form_hints()
        assert form_hints == {}

        # No-auth modems should return empty dict for JS hints
        js_hints = adapter.get_js_auth_hints()
        assert js_hints == {}


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
        assert config.auth.strategy in (AuthStrategy.FORM, AuthStrategy.NONE)

    def test_lookup_hnap_parser(self):
        """Test lookup for HNAP parser."""
        config = get_modem_config_for_parser("ArrisS33HnapParser")
        if config is None:
            pytest.skip("HNAP modem config not available")

        assert config.auth.strategy == AuthStrategy.HNAP

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

        hints = adapter.get_auth_form_hints()
        assert "username_field" in hints

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
            auth=AuthConfig(strategy=AuthStrategy.BASIC),
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
            auth=AuthConfig(strategy=AuthStrategy.BASIC),
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

# ┌─────────────────────────┬───────────────┬──────────────────────────────────────────┬─────────────────────────┐
# │ method                  │ use_full      │ expected                                 │ description             │
# ├─────────────────────────┼───────────────┼──────────────────────────────────────────┼─────────────────────────┤
# │ get_auth_strategy       │ True          │ AuthStrategy.FORM                        │ returns strategy enum   │
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
    ("get_auth_strategy",       True,     AuthStrategy.FORM,                         "returns strategy enum"),
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
            strategy=AuthStrategy.FORM,
            form=FormAuthConfig(
                action="/login",
                username_field="user",
                password_field="pass",
            ),
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
        auth=AuthConfig(strategy=AuthStrategy.NONE),
    )


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
            auth=AuthConfig(strategy=AuthStrategy.NONE),
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
            auth=AuthConfig(strategy=AuthStrategy.NONE),
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
            auth=AuthConfig(strategy=AuthStrategy.NONE),
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
            auth=AuthConfig(strategy=AuthStrategy.NONE),
            fixtures=FixturesMetadata(path="modems/test/withfixtures/fixtures"),
        )
        adapter = ModemConfigAuthAdapter(config)
        assert adapter.get_fixtures_path() == "modems/test/withfixtures/fixtures"

    def test_get_fixtures_path_none(self):
        """Test get_fixtures_path returns None when not configured."""
        config = ModemConfig(
            manufacturer="Test",
            model="NoFixtures",
            auth=AuthConfig(strategy=AuthStrategy.NONE),
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
            auth=AuthConfig(strategy=AuthStrategy.BASIC),
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


# ┌──────────────────────┬───────────────────┬────────────────────────────────────────┐
# │ method               │ strategy          │ description                            │
# ├──────────────────────┼───────────────────┼────────────────────────────────────────┤
# │ get_hnap_hints       │ FORM              │ HNAP hints empty for form auth         │
# │ get_hnap_hints       │ NONE              │ HNAP hints empty for no auth           │
# │ get_url_token_config │ NONE              │ URL token config empty for no auth     │
# │ get_url_token_config │ FORM              │ URL token config empty for form auth   │
# │ get_form_config      │ NONE              │ Form config empty for no auth          │
# │ get_form_config      │ HNAP              │ Form config empty for HNAP auth        │
# │ get_js_auth_hints    │ FORM              │ JS hints empty for form auth           │
# │ get_js_auth_hints    │ NONE              │ JS hints empty for no auth             │
# └──────────────────────┴───────────────────┴────────────────────────────────────────┘
#
# fmt: off
WRONG_STRATEGY_RETURNS_EMPTY_CASES = [
    # (method,               strategy,            description)
    ("get_hnap_hints",       AuthStrategy.FORM,   "HNAP hints empty for form auth"),
    ("get_hnap_hints",       AuthStrategy.NONE,   "HNAP hints empty for no auth"),
    ("get_url_token_config", AuthStrategy.NONE,   "URL token config empty for no auth"),
    ("get_url_token_config", AuthStrategy.FORM,   "URL token config empty for form auth"),
    ("get_form_config",      AuthStrategy.NONE,   "Form config empty for no auth"),
    ("get_form_config",      AuthStrategy.HNAP,   "Form config empty for HNAP auth"),
    ("get_js_auth_hints",    AuthStrategy.FORM,   "JS hints empty for form auth"),
    ("get_js_auth_hints",    AuthStrategy.NONE,   "JS hints empty for no auth"),
]
# fmt: on


class TestEdgeCases:
    """Tests for edge cases and empty return paths."""

    @pytest.mark.parametrize("method,strategy,desc", WRONG_STRATEGY_RETURNS_EMPTY_CASES)
    def test_wrong_strategy_returns_empty(self, method, strategy, desc):
        """Table-driven: calling hint getter with wrong strategy returns empty dict."""
        config = ModemConfig(
            manufacturer="Test",
            model="WrongStrategy",
            auth=AuthConfig(strategy=strategy),
        )
        adapter = ModemConfigAuthAdapter(config)
        result = getattr(adapter, method)()
        assert result == {}, f"{method} with {strategy}: {desc}"

    def test_js_auth_hints_minimal_url_token(self):
        """Test JS auth hints with URL_TOKEN but no url_token config."""
        config = ModemConfig(
            manufacturer="Test",
            model="MinimalUrlToken",
            auth=AuthConfig(strategy=AuthStrategy.URL_TOKEN),
        )
        adapter = ModemConfigAuthAdapter(config)
        hints = adapter.get_js_auth_hints()
        assert hints == {"pattern": "url_token_session"}


# =============================================================================
# Helper Function Tests - Table-Driven
# =============================================================================

# ┌────────────────────────────────┬─────────────────────────┬──────────────────────┐
# │ function                       │ parser                  │ expected_none        │
# ├────────────────────────────────┼─────────────────────────┼──────────────────────┤
# │ get_url_patterns_for_parser    │ TechnicolorTC4400Parser │ False (returns list) │
# │ get_url_patterns_for_parser    │ NonExistentParser       │ True                 │
# │ get_capabilities_for_parser    │ ArrisS33HnapParser      │ False (returns list) │
# │ get_capabilities_for_parser    │ NonExistentParser       │ True                 │
# │ get_docsis_version_for_parser  │ ArrisS33HnapParser      │ False (returns str)  │
# │ get_docsis_version_for_parser  │ NonExistentParser       │ True                 │
# │ get_detection_hints_for_parser │ MotorolaMB7621Parser    │ False (returns dict) │
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
