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
    """

    by_resource: dict[str, AnchorCount] = field(default_factory=dict)

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
