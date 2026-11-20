#!/usr/bin/env python3
"""Render the HA quality scale progress table in the GitHub README.

``custom_components/cable_modem_monitor/quality_scale.yaml`` is the
single source for each rule's status. This script renders it into the
marked region of ``.github/README.md`` so the published progress cannot
drift from the graded file.

Freshness is gated by ``tests/lib/test_generate_quality_scale_table.py``,
which runs in the integration suite. There is no separate CI job.

Usage:
    python scripts/generate_quality_scale_table.py            # rewrite in place
    python scripts/generate_quality_scale_table.py --check    # exit 1 if stale

Re-grading (run after a dependency bump; ha-safe-deps-bump step 5a):
    1. Compare TIERS with ALL_RULES in HA core's current
       script/hassfest/quality_scale.py; add or drop rules in both TIERS
       and quality_scale.yaml.
    2. Run ``make test`` and compare per-module coverage with the
       test-coverage (>95% per module) and config-flow-test-coverage
       (100%) grades.
    3. Re-check each rule the change touched against HA's rule text;
       update its status and comment in quality_scale.yaml.
    4. Run this script and stage the README with the yaml.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
QUALITY_SCALE = REPO_ROOT / "custom_components" / "cable_modem_monitor" / "quality_scale.yaml"
README = REPO_ROOT / ".github" / "README.md"
REGION = "quality-scale"

# Rule → tier, copied from HA core's script/hassfest/quality_scale.py
# (ALL_RULES). The yaml cannot carry the tier: hassfest's schema rejects
# extra keys.
TIERS: dict[str, list[str]] = {
    "Bronze": [
        "action-setup",
        "appropriate-polling",
        "brands",
        "common-modules",
        "config-flow",
        "config-flow-test-coverage",
        "dependency-transparency",
        "docs-actions",
        "docs-conditions",
        "docs-high-level-description",
        "docs-installation-instructions",
        "docs-removal-instructions",
        "docs-triggers",
        "entity-event-setup",
        "entity-unique-id",
        "has-entity-name",
        "runtime-data",
        "test-before-configure",
        "test-before-setup",
        "unique-config-entry",
    ],
    "Silver": [
        "action-exceptions",
        "config-entry-unloading",
        "docs-configuration-parameters",
        "docs-installation-parameters",
        "entity-unavailable",
        "integration-owner",
        "log-when-unavailable",
        "parallel-updates",
        "reauthentication-flow",
        "test-coverage",
    ],
    "Gold": [
        "devices",
        "diagnostics",
        "discovery",
        "discovery-update-info",
        "docs-data-update",
        "docs-examples",
        "docs-known-limitations",
        "docs-supported-devices",
        "docs-supported-functions",
        "docs-troubleshooting",
        "docs-use-cases",
        "dynamic-devices",
        "entity-category",
        "entity-device-class",
        "entity-disabled-by-default",
        "entity-translations",
        "exception-translations",
        "icon-translations",
        "reconfiguration-flow",
        "repair-issues",
        "stale-devices",
    ],
    "Platinum": [
        "async-dependency",
        "inject-websession",
        "strict-typing",
    ],
}

MEDALS = {"Bronze": "🥉", "Silver": "🥈", "Gold": "🥇", "Platinum": "🏆"}
RULE_URL = "https://contributors.home-assistant.io/core/quality-scale/{rule}/"


def load_statuses(path: Path = QUALITY_SCALE) -> dict[str, str]:
    """Return ``{rule: status}`` from a quality_scale.yaml file."""
    rules: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))["rules"]
    return {name: value["status"] if isinstance(value, dict) else value for name, value in rules.items()}


def render_table(statuses: dict[str, str]) -> str:
    """Render the per-tier progress table; ``done`` and ``exempt`` count as met."""
    known = {rule for rules in TIERS.values() for rule in rules}
    if set(statuses) != known:
        missing = sorted(known - set(statuses))
        extra = sorted(set(statuses) - known)
        raise SystemExit(f"quality_scale.yaml rules differ from TIERS: missing {missing}, extra {extra}")

    lines = ["| Tier | Rules met | Open rules |", "| ---- | --------- | ---------- |"]
    for tier, rules in TIERS.items():
        open_rules = [rule for rule in rules if statuses[rule] not in ("done", "exempt")]
        met = len(rules) - len(open_rules)
        links = ", ".join(f"[`{rule}`]({RULE_URL.format(rule=rule)})" for rule in open_rules) or "None"
        lines.append(f"| {MEDALS[tier]} {tier} | {met} / {len(rules)} | {links} |")
    return "\n".join(lines)


def _region_pattern() -> re.Pattern[str]:
    """Match the BEGIN/END marker pair and everything between it."""
    return re.compile(
        rf"(<!-- BEGIN GENERATED: {REGION}[^>]*-->\n).*?(\n<!-- END GENERATED: {REGION} -->)",
        re.DOTALL,
    )


def replace_region(text: str, body: str) -> str:
    """Return ``text`` with the marked region's contents replaced by ``body``."""
    pattern = _region_pattern()
    if not pattern.search(text):
        raise SystemExit(f"no '{REGION}' generated region found — markers missing or malformed")
    # Lambda replacement: the body is literal text, not a template.
    return pattern.sub(lambda m: m.group(1) + body + m.group(2), text)


def render_readme() -> str:
    """Return the README's full expected text."""
    return replace_region(README.read_text(encoding="utf-8"), render_table(load_statuses()))


def main() -> int:
    """Rewrite the README region, or report staleness under --check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 if the README is stale")
    args = parser.parse_args()

    expected = render_readme()
    if README.read_text(encoding="utf-8") == expected:
        return 0
    if args.check:
        print(f"stale quality scale table: {README}", file=sys.stderr)
        print("run: python scripts/generate_quality_scale_table.py", file=sys.stderr)
        return 1
    README.write_text(expected, encoding="utf-8")
    print(f"updated {README.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
