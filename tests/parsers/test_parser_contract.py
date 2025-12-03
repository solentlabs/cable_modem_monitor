"""Tests to validate all parsers meet the detection contract.

These tests ensure that parsers are correctly configured for auto-detection
and that the detection contract is consistently applied across all parsers.

Detection Contract:
1. Every URL pattern must explicitly declare auth_required (True or False)
2. Parsers that can be auto-detected need at least one auth_required=False URL
3. Parsers requiring credentials can only be detected via manual selection

See: Journal entry 2025-12-03 - Auto-Detection Lessons Learned
"""

from __future__ import annotations

import pytest

from custom_components.cable_modem_monitor.parsers import get_parsers
from custom_components.cable_modem_monitor.parsers.universal.fallback import UniversalFallbackParser


class TestParserDetectionContract:
    """Validate all parsers meet the detection contract."""

    @pytest.fixture
    def all_parsers(self):
        """Get all registered parsers."""
        return get_parsers()

    def test_all_url_patterns_have_explicit_auth_required(self, all_parsers):
        """Every URL pattern must explicitly declare auth_required.

        Relying on implicit defaults (auth_required defaulting to True) has
        caused auto-detection bugs. Making this explicit prevents such issues.
        """
        violations = []

        for parser_class in all_parsers:
            for i, pattern in enumerate(parser_class.url_patterns):
                if "auth_required" not in pattern:
                    violations.append(
                        f"{parser_class.name} url_patterns[{i}] ({pattern.get('path', '?')}) "
                        f"missing explicit 'auth_required'"
                    )

        assert not violations, (
            "The following URL patterns are missing explicit 'auth_required':\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nAdd 'auth_required': True or False to each pattern."
        )

    def test_parsers_have_url_patterns(self, all_parsers):
        """Every parser should have at least one URL pattern defined."""
        missing = []

        for parser_class in all_parsers:
            if not parser_class.url_patterns:
                missing.append(parser_class.name)

        assert not missing, (
            f"The following parsers have no url_patterns defined: {missing}\n"
            "Every parser needs at least one URL pattern to fetch data."
        )

    def test_anonymous_detection_coverage(self, all_parsers):
        """Report which parsers can be auto-detected vs require manual selection.

        This is informational - parsers requiring credentials cannot be
        auto-detected, which is expected behavior for some modems.
        """
        auto_detectable = []
        manual_only = []

        for parser_class in all_parsers:
            # Skip fallback parser - it's a special case
            if parser_class == UniversalFallbackParser:
                continue

            anon_patterns = [p for p in parser_class.url_patterns if not p.get("auth_required", True)]

            if anon_patterns:
                auto_detectable.append(parser_class.name)
            else:
                manual_only.append(parser_class.name)

        # This test always passes - it's just reporting
        # Uncomment the assertion below if you want to enforce auto-detection
        print(f"\nAuto-detectable parsers ({len(auto_detectable)}): {auto_detectable}")
        print(f"Manual selection only ({len(manual_only)}): {manual_only}")

        # Optional: Enforce that most parsers are auto-detectable
        # assert len(auto_detectable) >= len(manual_only), (
        #     f"Too many parsers require manual selection: {manual_only}"
        # )

    def test_first_url_pattern_is_detection_url_when_anonymous(self, all_parsers):
        """If a parser has anonymous URLs, the first one should be for detection.

        The first URL pattern is often used for initial probing. If a parser
        supports anonymous access, the detection page should come first.
        """
        warnings = []

        for parser_class in all_parsers:
            if parser_class == UniversalFallbackParser:
                continue

            anon_patterns = [p for p in parser_class.url_patterns if not p.get("auth_required", True)]

            if anon_patterns and parser_class.url_patterns:
                first_pattern = parser_class.url_patterns[0]
                if first_pattern.get("auth_required", True):
                    warnings.append(
                        f"{parser_class.name}: First URL pattern requires auth, "
                        f"but parser has anonymous URLs. Consider reordering so "
                        f"detection page comes first."
                    )

        # This is a warning, not a failure
        if warnings:
            print("\n⚠️  URL ordering suggestions:")
            for w in warnings:
                print(f"  - {w}")


class TestParserMetadata:
    """Validate parser metadata is complete."""

    @pytest.fixture
    def all_parsers(self):
        """Get all registered parsers."""
        return get_parsers()

    def test_all_parsers_have_name(self, all_parsers):
        """Every parser must have a name."""
        missing = [p for p in all_parsers if not p.name or p.name == "Unknown"]
        # Filter out fallback which is expected to be "Unknown"
        missing = [p for p in missing if p != UniversalFallbackParser]

        assert not missing, f"Parsers missing name: {[p.__name__ for p in missing]}"

    def test_all_parsers_have_manufacturer(self, all_parsers):
        """Every parser must have a manufacturer."""
        missing = [p for p in all_parsers if not p.manufacturer or p.manufacturer == "Unknown"]
        # Filter out fallback which is expected to be "Unknown"
        missing = [p for p in missing if p != UniversalFallbackParser]

        assert not missing, f"Parsers missing manufacturer: {[p.__name__ for p in missing]}"

    def test_all_parsers_have_models(self, all_parsers):
        """Every parser must list supported models."""
        missing = [p for p in all_parsers if not p.models]
        # Filter out fallback
        missing = [p for p in missing if p != UniversalFallbackParser]

        assert not missing, f"Parsers missing models: {[p.__name__ for p in missing]}"

    def test_all_parsers_have_capabilities(self, all_parsers):
        """Every parser (except fallback) should declare capabilities."""
        missing = []

        for parser_class in all_parsers:
            if parser_class == UniversalFallbackParser:
                continue
            if not parser_class.capabilities:
                missing.append(parser_class.name)

        assert not missing, (
            f"Parsers missing capabilities: {missing}\n"
            "Declare what data this parser can provide using ModemCapability enum."
        )
