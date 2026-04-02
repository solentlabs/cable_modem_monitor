#!/usr/bin/env python3
"""MCP pipeline regression sweep.

Tests the MCP intake pipeline by treating each catalog HAR as a fresh
submission. For each modem:

1. Run HAR through validate_har -> analyze_har -> generate_config
2. Overwrite committed modem.yaml + parser.yaml with generated versions
3. Run generate_golden_file with the generated parser.yaml
4. Compare generated golden file against committed golden file
5. Restore original files

Golden file drift = pipeline can't reproduce what was manually crafted.
Zero drift = pipeline is production-ready for contributor onboarding.

Baseline mode (--baseline):
    Compares results against a recorded baseline. Fails only on
    regressions (status got worse). Use --update-baseline to record
    the current state after pipeline improvements.

Usage:
    .venv/bin/python packages/cable_modem_monitor_catalog/scripts/mcp_pipeline_regression.py
    .venv/bin/python packages/cable_modem_monitor_catalog/scripts/mcp_pipeline_regression.py --modem arris/sb8200
    .venv/bin/python packages/cable_modem_monitor_catalog/scripts/mcp_pipeline_regression.py -v
    .venv/bin/python .../mcp_pipeline_regression.py --baseline baseline.json
    .venv/bin/python .../mcp_pipeline_regression.py --update-baseline baseline.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CATALOG_ROOT = Path(__file__).resolve().parent.parent / ("solentlabs/cable_modem_monitor_catalog/modems")

CONFIG_FILES = ("modem.yaml", "parser.yaml", "parser.py")


@dataclass
class ModemResult:
    """Result of running the full pipeline regression on one modem HAR."""

    modem: str
    har_file: str
    stage_failed: str = ""
    error: str = ""
    golden_diffs: list[str] = field(default_factory=list)
    config_diffs: list[str] = field(default_factory=list)
    channel_counts: dict[str, int] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """No stage failures and no golden file drift."""
        return not self.stage_failed and not self.golden_diffs


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def discover_modems(
    filter_modem: str | None = None,
) -> list[tuple[str, Path, Path]]:
    """Discover catalog modems with HAR files."""
    results = []
    for mfr_dir in sorted(CATALOG_ROOT.iterdir()):
        if not mfr_dir.is_dir():
            continue
        for model_dir in sorted(mfr_dir.iterdir()):
            if not model_dir.is_dir():
                continue
            modem_id = f"{mfr_dir.name}/{model_dir.name}"
            if filter_modem and filter_modem != modem_id:
                continue
            test_data = model_dir / "test_data"
            if not test_data.exists():
                continue
            for har in sorted(test_data.glob("*.har")):
                results.append((modem_id, har, model_dir))
    return results


# ---------------------------------------------------------------------------
# File backup / restore
# ---------------------------------------------------------------------------


def _backup_files(modem_dir: Path) -> dict[str, bytes | None]:
    """Save original config files."""
    backups: dict[str, bytes | None] = {}
    for name in CONFIG_FILES:
        path = modem_dir / name
        backups[name] = path.read_bytes() if path.exists() else None
    return backups


def _restore_files(modem_dir: Path, backups: dict[str, bytes | None]) -> None:
    """Restore original config files from backup."""
    for name, content in backups.items():
        path = modem_dir / name
        if content is not None:
            path.write_bytes(content)
        elif path.exists():
            path.unlink()


# ---------------------------------------------------------------------------
# Diffing
# ---------------------------------------------------------------------------


def _diff_channel_list(
    section: str,
    gen_list: list[Any],
    com_list: list[Any],
) -> list[str]:
    """Diff two lists of channel dicts."""
    diffs: list[str] = []
    if len(gen_list) != len(com_list):
        diffs.append(f"{section}: channel count {len(gen_list)} " f"vs committed {len(com_list)}")
        return diffs
    for i, (g, c) in enumerate(zip(gen_list, com_list, strict=True)):
        if not isinstance(g, dict) or not isinstance(c, dict):
            continue
        for key in sorted(set(g.keys()) | set(c.keys())):
            if g.get(key) != c.get(key):
                diffs.append(f"{section}[{i}].{key}: " f"{g.get(key)!r} vs {c.get(key)!r}")
    return diffs


def _diff_section(
    section: str,
    gen_val: Any,
    com_val: Any,
) -> list[str]:
    """Diff a single section (list, dict, or missing)."""
    if isinstance(gen_val, list) and isinstance(com_val, list):
        return _diff_channel_list(section, gen_val, com_val)

    if isinstance(gen_val, dict) and isinstance(com_val, dict):
        diffs: list[str] = []
        for key in sorted(set(gen_val.keys()) | set(com_val.keys())):
            if gen_val.get(key) != com_val.get(key):
                diffs.append(f"{section}.{key}: " f"{gen_val.get(key)!r} vs {com_val.get(key)!r}")
        return diffs

    if gen_val is None and com_val is not None:
        return [f"{section}: missing in generated"]
    if gen_val is not None and com_val is None:
        return [f"{section}: extra in generated"]
    if gen_val != com_val:
        return [f"{section}: type mismatch"]
    return []


def _diff_golden_files(
    generated: dict[str, Any],
    committed_path: Path,
) -> list[str]:
    """Compare generated golden file against committed expected.json."""
    if not committed_path.exists():
        return ["no committed golden file to compare"] if generated else []

    committed = json.loads(committed_path.read_text())
    diffs: list[str] = []
    for section in ("downstream", "upstream", "system_info"):
        diffs.extend(_diff_section(section, generated.get(section), committed.get(section)))
    return diffs


def _diff_config_files(
    generated_yaml: str | None,
    committed_path: Path,
    label: str,
) -> list[str]:
    """Compare generated config YAML against committed config."""
    if not committed_path.exists():
        return []

    committed = yaml.safe_load(committed_path.read_text())
    generated = yaml.safe_load(generated_yaml) if generated_yaml else None

    if generated is None and committed is not None:
        return [f"{label}: pipeline produced nothing, committed exists"]
    if generated is not None and committed is None:
        return [f"{label}: pipeline produced content, committed is empty"]
    if generated == committed:
        return []

    diffs: list[str] = []
    gen_keys = set(generated.keys()) if generated else set()
    com_keys = set(committed.keys()) if committed else set()
    missing = com_keys - gen_keys
    extra = gen_keys - com_keys
    if missing:
        diffs.append(f"{label}: missing keys {sorted(missing)}")
    if extra:
        diffs.append(f"{label}: extra keys {sorted(extra)}")
    for key in sorted(gen_keys & com_keys):
        if generated[key] != committed[key]:  # type: ignore[index]
            diffs.append(f"{label}.{key}: differs")
    return diffs


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------


def _run_validate(har_path: Path, result: ModemResult) -> bool:
    """Run validate_har. Returns True if passed."""
    from solentlabs.cable_modem_monitor_core.mcp.validate_har import (
        validate_har,
    )

    val = validate_har(str(har_path))
    if not val.valid:
        result.stage_failed = "validate_har"
        result.error = "; ".join(val.issues)
        return False
    return True


def _run_analyze(har_path: Path, result: ModemResult) -> dict[str, Any] | None:
    """Run analyze_har. Returns analysis dict or None on failure."""
    from solentlabs.cable_modem_monitor_core.mcp.analyze_har import (
        analyze_har,
    )

    analysis = analyze_har(str(har_path))
    if analysis.hard_stops:
        result.stage_failed = "analyze_har"
        result.error = "; ".join(analysis.hard_stops)
        return None
    return analysis.to_dict()


def _run_generate(
    analysis_data: dict[str, Any],
    modem_dir: Path,
    result: ModemResult,
) -> tuple[str | None, str | None]:
    """Run generate_config. Returns (modem_yaml, parser_yaml) or (None, None)."""
    from solentlabs.cable_modem_monitor_core.mcp.enrich_metadata import (
        enrich_metadata,
    )
    from solentlabs.cable_modem_monitor_core.mcp.generate_config import (
        generate_config,
    )

    user_meta = _extract_metadata(modem_dir)
    enriched = enrich_metadata(analysis_data, user_input=user_meta)
    config = generate_config(analysis_data, enriched.metadata)
    if config.validation and not config.validation.valid:
        result.stage_failed = "generate_config"
        result.error = "; ".join(config.validation.errors)
        return None, None
    return config.modem_yaml, config.parser_yaml


def _run_golden_comparison(
    har_path: Path,
    parser_yaml: str,
    modem_dir: Path,
    result: ModemResult,
) -> None:
    """Overwrite configs, generate golden file, compare, restore."""
    from solentlabs.cable_modem_monitor_core.mcp.generate_golden_file import (
        generate_golden_file,
    )

    golden_result = generate_golden_file(str(har_path), parser_yaml)
    if golden_result.errors:
        result.stage_failed = "generate_golden_file"
        result.error = "; ".join(golden_result.errors)
        return

    result.channel_counts = golden_result.channel_counts

    stem = har_path.stem
    expected_path = har_path.parent / f"{stem}.expected.json"
    result.golden_diffs = _diff_golden_files(golden_result.golden_file, expected_path)


def _extract_metadata(modem_dir: Path) -> dict[str, Any]:
    """Extract identity metadata from committed modem.yaml."""
    modem_yaml = modem_dir / "modem.yaml"
    if not modem_yaml.exists():
        return {}
    with open(modem_yaml) as f:
        cfg = yaml.safe_load(f) or {}
    return {
        "manufacturer": cfg.get("manufacturer", ""),
        "model": cfg.get("model", ""),
    }


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


def run_modem(
    modem_id: str,
    har_path: Path,
    modem_dir: Path,
    verbose: bool = False,
) -> ModemResult:
    """Run the full pipeline regression for one modem HAR."""
    result = ModemResult(modem=modem_id, har_file=har_path.name)

    try:
        if not _run_validate(har_path, result):
            return result

        analysis_data = _run_analyze(har_path, result)
        if analysis_data is None:
            return result

        modem_yaml, parser_yaml = _run_generate(analysis_data, modem_dir, result)
        if modem_yaml is None:
            return result

        # Config diffs (informational)
        result.config_diffs.extend(_diff_config_files(modem_yaml, modem_dir / "modem.yaml", "modem.yaml"))
        result.config_diffs.extend(_diff_config_files(parser_yaml, modem_dir / "parser.yaml", "parser.yaml"))

        # Golden file comparison
        if parser_yaml:
            _run_golden_comparison(har_path, parser_yaml, modem_dir, result)
        else:
            result.stage_failed = "generate_golden_file"
            result.error = "no parser.yaml generated"

    except Exception as e:
        result.stage_failed = result.stage_failed or "unknown"
        result.error = str(e)

    if verbose:
        _print_result(result)

    return result


def _print_result(result: ModemResult) -> None:
    """Print verbose output for a single modem result."""
    if result.stage_failed:
        print(f"    FAIL {result.stage_failed}: {result.error}")
        return

    ds = result.channel_counts.get("downstream", 0)
    us = result.channel_counts.get("upstream", 0)
    if result.golden_diffs:
        print(f"    DRIFT ds={ds} us={us}: {len(result.golden_diffs)} diffs")
        for d in result.golden_diffs[:5]:
            print(f"      {d}")
        if len(result.golden_diffs) > 5:
            print(f"      ... and {len(result.golden_diffs) - 5} more")
    else:
        print(f"    OK    ds={ds} us={us}: golden file matches")

    if result.config_diffs:
        print(f"    CONFIG diffs: {len(result.config_diffs)}")
        for d in result.config_diffs[:3]:
            print(f"      {d}")


def _print_summary(results: list[ModemResult]) -> None:
    """Print the final summary."""
    passed = [r for r in results if r.passed]
    failed_stage = [r for r in results if r.stage_failed]
    drifted = [r for r in results if r.golden_diffs and not r.stage_failed]

    print(f"\n{'=' * 60}")
    print(
        f"RESULTS: {len(passed)} clean, " f"{len(drifted)} with golden drift, " f"{len(failed_stage)} pipeline failures"
    )
    print(f"{'=' * 60}\n")

    if failed_stage:
        print("PIPELINE FAILURES:")
        for r in failed_stage:
            print(f"  {r.modem} ({r.har_file}): " f"{r.stage_failed} — {r.error}")
        print()

    if drifted:
        print("GOLDEN FILE DRIFT:")
        total_diffs = 0
        for r in drifted:
            total_diffs += len(r.golden_diffs)
            print(f"  {r.modem} ({r.har_file}): " f"{len(r.golden_diffs)} diffs")
            for d in r.golden_diffs[:3]:
                print(f"    {d}")
            if len(r.golden_diffs) > 3:
                print(f"    ... and {len(r.golden_diffs) - 3} more")
        print(f"\n  Total golden file diffs: {total_diffs}")
        print()

    if passed:
        print(f"CLEAN ({len(passed)}):")
        for r in passed:
            ds = r.channel_counts.get("downstream", 0)
            us = r.channel_counts.get("upstream", 0)
            print(f"  {r.modem}: ds={ds} us={us}")
        print()


# ---------------------------------------------------------------------------
# Baseline comparison
# ---------------------------------------------------------------------------

# Severity ordering: clean < drift < failure
_STATUS_SEVERITY = {"clean": 0, "drift": 1, "failure": 2}


def _result_status(result: ModemResult) -> str:
    """Classify a result as clean, drift, or failure."""
    if result.stage_failed:
        return "failure"
    if result.golden_diffs:
        return "drift"
    return "clean"


def _result_key(result: ModemResult) -> str:
    """Unique key for a result: modem_id:har_filename."""
    return f"{result.modem}:{result.har_file}"


def _load_baseline(path: Path) -> dict[str, str]:
    """Load baseline file. Returns {key: status}."""
    data = json.loads(path.read_text())
    return data.get("results", {})


def _save_baseline(path: Path, results: list[ModemResult]) -> None:
    """Write current results as the new baseline."""
    baseline = {_result_key(r): _result_status(r) for r in results}
    data = {
        "_comment": "MCP pipeline regression baseline. Update with --update-baseline.",
        "results": dict(sorted(baseline.items())),
    }
    path.write_text(json.dumps(data, indent=2) + "\n")


def _compare_baseline(
    results: list[ModemResult],
    baseline: dict[str, str],
) -> tuple[list[str], list[str]]:
    """Compare results against baseline.

    Returns (regressions, improvements) as human-readable messages.
    A regression is when a modem's status gets worse (higher severity).
    """
    regressions: list[str] = []
    improvements: list[str] = []

    for r in results:
        key = _result_key(r)
        current = _result_status(r)
        expected = baseline.get(key)

        if expected is None:
            # New modem not in baseline — not a regression, but flag it
            if current != "clean":
                regressions.append(f"  NEW {key}: {current} (not in baseline)")
            continue

        cur_sev = _STATUS_SEVERITY[current]
        exp_sev = _STATUS_SEVERITY[expected]

        if cur_sev > exp_sev:
            regressions.append(f"  REGRESSED {key}: {expected} -> {current}")
        elif cur_sev < exp_sev:
            improvements.append(f"  IMPROVED  {key}: {expected} -> {current}")

    # Modems removed from catalog (in baseline but not in results)
    result_keys = {_result_key(r) for r in results}
    for key in sorted(baseline):
        if key not in result_keys:
            improvements.append(f"  REMOVED   {key}: was {baseline[key]}")

    return regressions, improvements


def _print_baseline_comparison(
    regressions: list[str],
    improvements: list[str],
) -> None:
    """Print baseline comparison results."""
    if improvements:
        print(f"\nIMPROVEMENTS ({len(improvements)}):")
        for msg in improvements:
            print(msg)
        print("\n  Run with --update-baseline to lock in improvements.")

    if regressions:
        print(f"\nREGRESSIONS ({len(regressions)}):")
        for msg in regressions:
            print(msg)
        print("\n  Pipeline changes made things worse. Fix before merging.")
    elif not improvements:
        print("\nBASELINE: No changes detected.")
    else:
        print("\nBASELINE: No regressions. Pipeline improved!")


def main() -> None:
    """Run the regression sweep."""
    parser = argparse.ArgumentParser(description="MCP pipeline regression — golden file drift test")
    parser.add_argument("--modem", help="Run only this modem (e.g., arris/sb8200)")
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show per-modem details",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        help="Compare against baseline file (fail only on regressions)",
    )
    parser.add_argument(
        "--update-baseline",
        type=Path,
        metavar="PATH",
        help="Run sweep and write results as new baseline",
    )
    args = parser.parse_args()

    modems = discover_modems(args.modem)
    if not modems:
        print("No modems found.")
        sys.exit(1)

    print(f"Running pipeline regression on {len(modems)} HAR files...\n")

    results: list[ModemResult] = []
    for modem_id, har_path, modem_dir in modems:
        print(f"  {modem_id} ({har_path.name})")
        r = run_modem(modem_id, har_path, modem_dir, verbose=args.verbose)
        results.append(r)

    _print_summary(results)

    # Update baseline mode — write and exit
    if args.update_baseline:
        _save_baseline(args.update_baseline, results)
        print(f"Baseline written to {args.update_baseline}")
        sys.exit(0)

    # Baseline comparison mode — fail only on regressions
    if args.baseline:
        if not args.baseline.exists():
            print(f"Baseline file not found: {args.baseline}")
            sys.exit(1)
        baseline = _load_baseline(args.baseline)
        regressions, improvements = _compare_baseline(results, baseline)
        _print_baseline_comparison(regressions, improvements)
        sys.exit(1 if regressions else 0)

    # Default mode — fail on any failure or drift
    has_failures = any(r.stage_failed for r in results)
    has_drift = any(r.golden_diffs and not r.stage_failed for r in results)
    sys.exit(1 if has_failures or has_drift else 0)


if __name__ == "__main__":
    main()
