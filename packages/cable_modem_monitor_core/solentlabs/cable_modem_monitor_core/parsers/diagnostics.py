"""Parser diagnostics — per-resource anchor fulfillment counts.

Surfaces extraction completeness alongside ModemData. The orchestrator
uses ``ParseDiagnostics.has_zero_fulfillment`` to detect stub-page
responses (HTTP 200 with valid HTML chrome but none of the parser's
declared anchors present in the body) and route them through the
LOAD_INTEGRITY signal path.

See PARSING_SPEC.md § Parser Diagnostics and
ORCHESTRATION_USE_CASES.md § UC-19a.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Cap for raw values captured on conversion failure. Field values are
# small; the cap guards against pathological responses landing whole
# in a diagnostics download.
MAX_FAILED_FIELD_VALUE_LEN = 200


def record_failed_field(failed: dict[str, str], field_name: str, raw_value: Any) -> None:
    """Record a conversion-rejected raw value, truncated to the cap."""
    failed[field_name] = str(raw_value)[:MAX_FAILED_FIELD_VALUE_LEN]


@dataclass(frozen=True)
class AnchorCount:
    """Anchor fulfillment for a single source or aggregate.

    Attributes:
        expected: Number of named extraction targets configured.
        fulfilled: Number of those targets the parser actually located
            in the response body.
    """

    expected: int = 0
    fulfilled: int = 0

    def __add__(self, other: AnchorCount) -> AnchorCount:
        """Sum two AnchorCounts — used to aggregate per-resource."""
        return AnchorCount(
            expected=self.expected + other.expected,
            fulfilled=self.fulfilled + other.fulfilled,
        )


@dataclass(frozen=True)
class ParseDiagnostics:
    """Per-resource anchor fulfillment for a single parse pass.

    Mapping of resource path → AnchorCount. Resources not referenced
    by parser config are absent from the mapping (no implicit zero).

    Attributes:
        by_resource: Mapping of resource path to its aggregate AnchorCount.
        system_info_fields_missing: Mapped system_info fields no configured
            source produced — the modem did not send the source key.
            Section-level, post-merge. See PARSING_SPEC § Field Outcomes.
        system_info_fields_failed: Mapped system_info fields whose located
            value was rejected by type conversion, mapped to the raw
            value (truncated to MAX_FAILED_FIELD_VALUE_LEN). The raw
            value is the repair datum for the catalog format string.
    """

    by_resource: dict[str, AnchorCount] = field(default_factory=dict)
    system_info_fields_missing: list[str] = field(default_factory=list)
    system_info_fields_failed: dict[str, str] = field(default_factory=dict)

    @property
    def has_zero_fulfillment(self) -> bool:
        """True if any resource has expected > 0 and fulfilled == 0.

        This is the stub-page indicator — a parser had declared
        anchors for a resource but located none of them in the
        response body. Triggers LOAD_INTEGRITY in the collector.
        """
        return any(c.expected > 0 and c.fulfilled == 0 for c in self.by_resource.values())

    @property
    def zero_fulfillment_resources(self) -> list[str]:
        """Resource paths where all expected anchors were missed.

        Used for diagnostic logging — the WARNING line names the
        affected paths so users can correlate with their HAR.
        """
        return [path for path, c in self.by_resource.items() if c.expected > 0 and c.fulfilled == 0]
