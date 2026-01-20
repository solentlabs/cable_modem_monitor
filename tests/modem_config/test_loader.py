"""Tests for modem_config/loader.py.

Tests index-based lookup functions, config loading, discovery, and cache management.

Test Organization:
- TestGetDetectionHintsFromIndex: Table-driven tests for detection hint lookups
- TestGetAggregatedAuthPatterns: Table-driven tests for auth pattern aggregation
- TestLoadModemIndex: Index loading with error paths
- TestLoadModemConfig: Config file loading with error paths
- TestLoadModemConfigByParser: Index-based config loading
- TestDiscoverModems: Modem discovery with caching
- TestListModemFixtures: Fixture file listing
- TestLoadModemByPath: Manufacturer/model path lookup
- TestGetModemByModel: Model lookup with fallbacks
- TestClearCache: Cache clearing including _modem_index
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from custom_components.cable_modem_monitor.modem_config import loader


def _minimal_config(manufacturer: str = "Test", model: str = "M1000") -> dict:
    """Create minimal valid modem config for testing."""
    return {
        "manufacturer": manufacturer,
        "model": model,
        "auth": {"strategy": "none"},
    }


# =============================================================================
# DETECTION HINTS FROM INDEX TEST CASES
# =============================================================================
# Tests get_detection_hints_from_index() which retrieves detection hints
# directly from the cached index without loading modem.yaml files.
#
# ┌─────────────────┬──────────────────────────────────────────┬─────────────────────────┐
# │ test_id         │ index_data                               │ expected                │
# ├─────────────────┼──────────────────────────────────────────┼─────────────────────────┤
# │ found           │ parser with detection hints              │ detection dict          │
# │ parser_missing  │ parser not in index                      │ None                    │
# │ no_detection    │ parser exists, no detection key          │ None                    │
# │ invalid_entry   │ parser entry is not a dict               │ None                    │
# │ detection_empty │ detection key exists but is None/empty   │ None                    │
# └─────────────────┴──────────────────────────────────────────┴─────────────────────────┘
#
# fmt: off
_DETECTION = {"pre_auth": ["SB8200"], "post_auth": ["ARRIS"], "page_hint": "/status.html"}
DETECTION_HINTS_CASES: list[tuple[str, dict, str, dict | None]] = [
    # (test_id,          index_data,                                              parser_name,     expected)
    ("found",            {"modems": {"TestParser": {"detection": _DETECTION}}},   "TestParser",    _DETECTION),
    ("parser_missing",   {"modems": {}},                                          "TestParser",    None),
    ("no_detection",     {"modems": {"TestParser": {"path": "test/modem"}}},      "TestParser",    None),
    ("invalid_entry",    {"modems": {"TestParser": "not_a_dict"}},                "TestParser",    None),
    ("detection_empty",  {"modems": {"TestParser": {"detection": None}}},         "TestParser",    None),
]
# fmt: on


# =============================================================================
# AGGREGATED AUTH PATTERNS TEST CASES
# =============================================================================
# Tests get_aggregated_auth_patterns() which retrieves combined auth patterns
# from the index for use by core auth code.
#
# ┌─────────────────┬──────────────────────────────────────────┬─────────────────────────┐
# │ test_id         │ index_data                               │ expected_check          │
# ├─────────────────┼──────────────────────────────────────────┼─────────────────────────┤
# │ has_patterns    │ index with auth_patterns                 │ returns auth_patterns   │
# │ missing         │ index without auth_patterns              │ returns default struct  │
# └─────────────────┴──────────────────────────────────────────┴─────────────────────────┘
#
# fmt: off
_AUTH_PATTERNS = {
    "form": {"username_fields": ["user"], "password_fields": ["pass"], "actions": ["/login"], "encodings": []},
    "hnap": {"endpoints": ["/HNAP1/"], "namespaces": []},
    "url_token": {"indicators": []},
}
_DEFAULT_PATTERNS = {
    "form": {"username_fields": [], "password_fields": [], "actions": [], "encodings": []},
    "hnap": {"endpoints": [], "namespaces": []},
    "url_token": {"indicators": []},
}
AUTH_PATTERNS_CASES: list[tuple[str, dict, dict]] = [
    # (test_id,       index_data,                          expected)
    ("has_patterns",  {"auth_patterns": _AUTH_PATTERNS},   _AUTH_PATTERNS),
    ("missing",       {"modems": {}},                      _DEFAULT_PATTERNS),
]
# fmt: on


class TestGetDetectionHintsFromIndex:
    """Tests for get_detection_hints_from_index function."""

    @pytest.mark.parametrize(
        "test_id,index_data,parser_name,expected",
        DETECTION_HINTS_CASES,
        ids=[c[0] for c in DETECTION_HINTS_CASES],
    )
    def test_detection_hints_lookup(self, test_id: str, index_data: dict, parser_name: str, expected: dict | None):
        """Test detection hints are correctly retrieved from index."""
        with patch.object(loader, "load_modem_index", return_value=index_data):
            result = loader.get_detection_hints_from_index(parser_name)

        assert result == expected, f"{test_id}: expected {expected}, got {result}"


class TestGetAggregatedAuthPatterns:
    """Tests for get_aggregated_auth_patterns function."""

    @pytest.mark.parametrize(
        "test_id,index_data,expected",
        AUTH_PATTERNS_CASES,
        ids=[c[0] for c in AUTH_PATTERNS_CASES],
    )
    def test_auth_patterns_retrieval(self, test_id: str, index_data: dict, expected: dict):
        """Test auth patterns are correctly retrieved or defaulted."""
        with patch.object(loader, "load_modem_index", return_value=index_data):
            result = loader.get_aggregated_auth_patterns()

        assert result == expected, f"{test_id}: expected {expected}, got {result}"


class TestClearCache:
    """Tests for clear_cache function."""

    def test_clears_modem_index(self):
        """Test clear_cache resets _modem_index to None."""
        # Set up: populate the index cache
        loader._modem_index = {"modems": {"TestParser": {}}}
        loader._config_cache["test"] = "value"
        loader._discovered_modems = []

        # Act
        loader.clear_cache()

        # Assert: all caches cleared
        assert loader._modem_index is None
        assert loader._config_cache == {}
        assert loader._discovered_modems is None


# =============================================================================
# LOAD MODEM INDEX TEST CASES
# =============================================================================
# Tests load_modem_index() which loads and caches the index.yaml file.
#
# ┌─────────────────┬──────────────────────────────────────────┬─────────────────────────┐
# │ test_id         │ scenario                                 │ expected                │
# ├─────────────────┼──────────────────────────────────────────┼─────────────────────────┤
# │ cache_hit       │ _modem_index already populated           │ returns cached value    │
# │ index_missing   │ index.yaml doesn't exist                 │ returns {"modems": {}}  │
# │ parse_error     │ index.yaml has invalid YAML              │ returns {"modems": {}}  │
# └─────────────────┴──────────────────────────────────────────┴─────────────────────────┘


class TestLoadModemIndex:
    """Tests for load_modem_index function."""

    def setup_method(self):
        """Clear caches before each test."""
        loader.clear_cache()

    def test_returns_cached_value(self):
        """Test load_modem_index returns cached value if available."""
        cached = {"modems": {"CachedParser": {}}}
        loader._modem_index = cached

        result = loader.load_modem_index()

        assert result is cached

    def test_index_file_missing(self, tmp_path: Path):
        """Test load_modem_index handles missing index.yaml."""
        with patch.object(loader, "get_modems_root", return_value=tmp_path):
            result = loader.load_modem_index()

        assert result == {"modems": {}}

    def test_index_parse_error(self, tmp_path: Path):
        """Test load_modem_index handles YAML parse errors."""
        index_path = tmp_path / "index.yaml"
        index_path.write_text("invalid: yaml: content: [")

        with patch.object(loader, "get_modems_root", return_value=tmp_path):
            result = loader.load_modem_index()

        assert result == {"modems": {}}


# =============================================================================
# LOAD MODEM CONFIG TEST CASES
# =============================================================================
# Tests load_modem_config() which loads and validates modem.yaml files.
#
# ┌─────────────────┬──────────────────────────────────────────┬─────────────────────────┐
# │ test_id         │ scenario                                 │ expected                │
# ├─────────────────┼──────────────────────────────────────────┼─────────────────────────┤
# │ file_not_found  │ modem.yaml doesn't exist                 │ raises FileNotFoundError│
# │ empty_yaml      │ modem.yaml is empty                      │ raises ValueError       │
# │ invalid_yaml    │ modem.yaml fails pydantic validation     │ raises ValueError       │
# │ direct_path     │ path is modem.yaml file directly         │ loads correctly         │
# │ cache_hit       │ same path loaded twice                   │ returns cached value    │
# └─────────────────┴──────────────────────────────────────────┴─────────────────────────┘


class TestLoadModemConfig:
    """Tests for load_modem_config function."""

    def setup_method(self):
        """Clear caches before each test."""
        loader.clear_cache()

    def test_file_not_found(self, tmp_path: Path):
        """Test load_modem_config raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError, match="modem.yaml not found"):
            loader.load_modem_config(tmp_path / "nonexistent")

    def test_empty_yaml(self, tmp_path: Path):
        """Test load_modem_config raises ValueError for empty file."""
        modem_dir = tmp_path / "test_modem"
        modem_dir.mkdir()
        (modem_dir / "modem.yaml").write_text("")

        with pytest.raises(ValueError, match="Empty modem.yaml"):
            loader.load_modem_config(modem_dir)

    def test_invalid_yaml_schema(self, tmp_path: Path):
        """Test load_modem_config raises ValueError for invalid schema."""
        modem_dir = tmp_path / "test_modem"
        modem_dir.mkdir()
        # Missing required fields
        (modem_dir / "modem.yaml").write_text("foo: bar")

        with pytest.raises(ValueError, match="Invalid modem.yaml"):
            loader.load_modem_config(modem_dir)

    def test_direct_modem_yaml_path(self, tmp_path: Path):
        """Test load_modem_config accepts direct path to modem.yaml."""
        modem_dir = tmp_path / "test_modem"
        modem_dir.mkdir()
        (modem_dir / "modem.yaml").write_text(yaml.dump(_minimal_config()))

        # Pass direct path to modem.yaml
        result = loader.load_modem_config(modem_dir / "modem.yaml")

        assert result.manufacturer == "Test"
        assert result.model == "M1000"

    def test_cache_hit(self, tmp_path: Path):
        """Test load_modem_config returns cached config on second call."""
        modem_dir = tmp_path / "test_modem"
        modem_dir.mkdir()
        (modem_dir / "modem.yaml").write_text(yaml.dump(_minimal_config()))

        result1 = loader.load_modem_config(modem_dir)
        result2 = loader.load_modem_config(modem_dir)

        assert result1 is result2  # Same object (cached)


# =============================================================================
# LOAD MODEM CONFIG BY PARSER TEST CASES
# =============================================================================
# Tests load_modem_config_by_parser() which uses index for fast lookup.
#
# ┌─────────────────┬──────────────────────────────────────────┬─────────────────────────┐
# │ test_id         │ scenario                                 │ expected                │
# ├─────────────────┼──────────────────────────────────────────┼─────────────────────────┤
# │ not_in_index    │ parser not in index                      │ returns None            │
# │ path_not_exists │ index path doesn't exist on disk         │ returns None            │
# │ load_error      │ config load throws exception             │ returns None            │
# └─────────────────┴──────────────────────────────────────────┴─────────────────────────┘


class TestLoadModemConfigByParser:
    """Tests for load_modem_config_by_parser function."""

    def setup_method(self):
        """Clear caches before each test."""
        loader.clear_cache()

    def test_parser_not_in_index(self):
        """Test returns None when parser not in index."""
        with patch.object(loader, "load_modem_index", return_value={"modems": {}}):
            result = loader.load_modem_config_by_parser("UnknownParser")

        assert result is None

    def test_path_not_exists(self, tmp_path: Path):
        """Test returns None when index path doesn't exist on disk."""
        index = {"modems": {"TestParser": {"path": "nonexistent/path"}}}

        with (
            patch.object(loader, "load_modem_index", return_value=index),
            patch.object(loader, "get_modems_root", return_value=tmp_path),
        ):
            result = loader.load_modem_config_by_parser("TestParser")

        assert result is None

    def test_load_exception(self, tmp_path: Path):
        """Test returns None when config load fails."""
        modem_dir = tmp_path / "test" / "modem"
        modem_dir.mkdir(parents=True)
        (modem_dir / "modem.yaml").write_text("invalid: [")  # Invalid YAML

        index = {"modems": {"TestParser": {"path": "test/modem"}}}

        with (
            patch.object(loader, "load_modem_index", return_value=index),
            patch.object(loader, "get_modems_root", return_value=tmp_path),
        ):
            result = loader.load_modem_config_by_parser("TestParser")

        assert result is None


# =============================================================================
# DISCOVER MODEMS TESTS
# =============================================================================


class TestDiscoverModems:
    """Tests for discover_modems function."""

    def setup_method(self):
        """Clear caches before each test."""
        loader.clear_cache()

    def test_returns_cached_results(self, tmp_path: Path):
        """Test discover_modems returns cached results on second call."""
        # Create a valid modem
        modem_dir = tmp_path / "test" / "m1000"
        modem_dir.mkdir(parents=True)
        (modem_dir / "modem.yaml").write_text(yaml.dump(_minimal_config()))

        with patch.object(loader, "get_modems_root", return_value=tmp_path):
            result1 = loader.discover_modems()
            result2 = loader.discover_modems()

        assert result1 is result2  # Same list object (cached)
        assert len(result1) == 1

    def test_custom_root_not_cached(self, tmp_path: Path):
        """Test discover_modems with custom root doesn't use/update cache."""
        # Structure: custom_root / manufacturer / model / modem.yaml
        modem_dir = tmp_path / "custom" / "m1000"
        modem_dir.mkdir(parents=True)
        (modem_dir / "modem.yaml").write_text(yaml.dump(_minimal_config("Custom", "M1000")))

        result = loader.discover_modems(modems_root=tmp_path)

        assert len(result) == 1
        assert loader._discovered_modems is None  # Cache not updated

    def test_root_not_exists(self, tmp_path: Path):
        """Test discover_modems returns empty list when root doesn't exist."""
        result = loader.discover_modems(modems_root=tmp_path / "nonexistent")

        assert result == []

    def test_individual_modem_load_error(self, tmp_path: Path):
        """Test discover_modems skips modems that fail to load."""
        # Create one valid modem
        valid_dir = tmp_path / "valid" / "m1000"
        valid_dir.mkdir(parents=True)
        (valid_dir / "modem.yaml").write_text(yaml.dump(_minimal_config("Valid", "M1000")))

        # Create one invalid modem
        invalid_dir = tmp_path / "invalid" / "m2000"
        invalid_dir.mkdir(parents=True)
        (invalid_dir / "modem.yaml").write_text("not valid yaml: [")

        result = loader.discover_modems(modems_root=tmp_path)

        assert len(result) == 1
        assert result[0][1].manufacturer == "Valid"


# =============================================================================
# LIST MODEM FIXTURES TESTS
# =============================================================================


class TestListModemFixtures:
    """Tests for list_modem_fixtures function."""

    def test_fixtures_exist(self, tmp_path: Path):
        """Test list_modem_fixtures returns fixture files."""
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "status.html").write_text("<html>")
        (fixtures_dir / "data.json").write_text("{}")
        (fixtures_dir / "metadata.yaml").write_text("skip: true")  # Should be excluded

        result = loader.list_modem_fixtures(tmp_path)

        assert len(result) == 2
        names = {f.name for f in result}
        assert names == {"status.html", "data.json"}

    def test_fixtures_dir_missing(self, tmp_path: Path):
        """Test list_modem_fixtures returns empty list when fixtures/ missing."""
        result = loader.list_modem_fixtures(tmp_path)

        assert result == []


# =============================================================================
# LOAD MODEM BY PATH TESTS
# =============================================================================


class TestLoadModemByPath:
    """Tests for load_modem_by_path function."""

    def setup_method(self):
        """Clear caches before each test."""
        loader.clear_cache()

    def test_finds_lowercase_manufacturer(self, tmp_path: Path):
        """Test finds modem with lowercase manufacturer directory."""
        modem_dir = tmp_path / "arris" / "sb8200"
        modem_dir.mkdir(parents=True)
        (modem_dir / "modem.yaml").write_text(yaml.dump(_minimal_config("ARRIS", "SB8200")))

        result = loader.load_modem_by_path("ARRIS", "SB8200", modems_root=tmp_path)

        assert result is not None
        assert result.model == "SB8200"

    def test_handles_slash_in_manufacturer(self, tmp_path: Path):
        """Test handles manufacturer with slash (e.g., Arris/CommScope)."""
        modem_dir = tmp_path / "arris" / "s33"
        modem_dir.mkdir(parents=True)
        (modem_dir / "modem.yaml").write_text(yaml.dump(_minimal_config("Arris/CommScope", "S33")))

        result = loader.load_modem_by_path("Arris/CommScope", "S33", modems_root=tmp_path)

        assert result is not None
        assert result.model == "S33"

    def test_root_not_exists(self, tmp_path: Path):
        """Test returns None when root doesn't exist."""
        result = loader.load_modem_by_path("Test", "M1000", modems_root=tmp_path / "nonexistent")

        assert result is None

    def test_modem_not_found(self, tmp_path: Path):
        """Test returns None when modem not found."""
        tmp_path.mkdir(exist_ok=True)

        result = loader.load_modem_by_path("Unknown", "Model", modems_root=tmp_path)

        assert result is None


# =============================================================================
# GET MODEM BY MODEL TESTS
# =============================================================================


class TestGetModemByModel:
    """Tests for get_modem_by_model function."""

    def setup_method(self):
        """Clear caches before each test."""
        loader.clear_cache()

    def test_custom_root_uses_discovery_fallback(self, tmp_path: Path):
        """Test custom root falls back to discovery when path lookup fails."""
        # Create modem in non-standard location (discovery will find it)
        modem_dir = tmp_path / "mfr" / "model"
        modem_dir.mkdir(parents=True)
        (modem_dir / "modem.yaml").write_text(yaml.dump(_minimal_config("Different", "Name")))

        result = loader.get_modem_by_model("Different", "Name", modems_root=tmp_path)

        assert result is not None
        assert result.manufacturer == "Different"

    def test_custom_root_not_found(self, tmp_path: Path):
        """Test returns None when modem not found in custom root."""
        tmp_path.mkdir(exist_ok=True)

        result = loader.get_modem_by_model("Unknown", "Model", modems_root=tmp_path)

        assert result is None


# =============================================================================
# GET MODEM PATH FOR PARSER TESTS
# =============================================================================


class TestGetModemPathForParser:
    """Tests for get_modem_path_for_parser function."""

    def test_returns_path_when_found(self):
        """Test returns path when parser is in index."""
        index = {"modems": {"TestParser": {"path": "test/modem"}}}

        with patch.object(loader, "load_modem_index", return_value=index):
            result = loader.get_modem_path_for_parser("TestParser")

        assert result == "test/modem"

    def test_returns_none_when_missing(self):
        """Test returns None when parser not in index."""
        with patch.object(loader, "load_modem_index", return_value={"modems": {}}):
            result = loader.get_modem_path_for_parser("UnknownParser")

        assert result is None

    def test_returns_none_for_invalid_entry(self):
        """Test returns None when entry is not a dict."""
        index = {"modems": {"TestParser": "not_a_dict"}}

        with patch.object(loader, "load_modem_index", return_value=index):
            result = loader.get_modem_path_for_parser("TestParser")

        assert result is None

    def test_returns_none_when_path_missing(self):
        """Test returns None when entry has no path key."""
        index = {"modems": {"TestParser": {"detection": {}}}}

        with patch.object(loader, "load_modem_index", return_value=index):
            result = loader.get_modem_path_for_parser("TestParser")

        assert result is None


# =============================================================================
# GET MODEM FIXTURES PATH TESTS
# =============================================================================


class TestGetModemFixturesPath:
    """Tests for get_modem_fixtures_path function."""

    def test_returns_fixtures_subdir(self, tmp_path: Path):
        """Test returns path to fixtures/ subdirectory."""
        result = loader.get_modem_fixtures_path(tmp_path / "modem")

        assert result == tmp_path / "modem" / "fixtures"
