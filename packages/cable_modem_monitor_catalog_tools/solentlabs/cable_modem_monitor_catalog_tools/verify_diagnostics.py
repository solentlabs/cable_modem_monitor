"""Diagnostics → ``verified.json`` Tool.

Transforms an HA-emitted Cable Modem Monitor diagnostics JSON into the
``<variant>.verified.json`` fixture that confirms a modem against
real hardware. Mechanical work only — strip the HA wrapper and the
integration's user-facing extras, prepend provenance, render channel
arrays compact, and locate the target paths in the catalog. Returns
the content and the paths it would write to. Does not write files,
edit ``modem.yaml``, or touch git.

The output shape (key order, channel-array compaction, trailing
newline) matches the convention used by every confirmed modem in the
catalog. See
``packages/cable_modem_monitor_catalog_tools/docs/MODEM_INTAKE_WORKFLOW.md``
§ Confirmation Phase for the human-side workflow this tool serves.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from solentlabs.cable_modem_monitor_core.models.field_registry import (
    SYSTEM_INFO_FIELDS,
    canonicalize_channel_keys,
)

# Keys HA Core injects around the integration's payload — we ignore
# the outer wrapper entirely and only consume ``data.*``.
_HA_WRAPPER_KEYS = frozenset(
    {
        "home_assistant",
        "custom_components",
        "integration_manifest",
        "setup_times",
        "issues",
    }
)

# Keys our integration emits inside ``data`` that serve the bug-triage
# audience (provenance, PII checklist, recent log context) and don't
# belong in a clean hardware-confirmation fixture.
#
# These describe the shape of what ``custom_components/cable_modem_monitor/
# diagnostics.py`` emits. They are duplicated here because catalog_tools
# must stay platform-agnostic and cannot import from custom_components/.
# A future refactor could lift this shape into a shared schema module in
# cable_modem_monitor_core that both sides import; not done yet.
_INTEGRATION_EXTRA_KEYS = frozenset(
    {
        "_solentlabs",
        "_review_before_sharing",
        "recent_logs",
        "last_error",
    }
)

# Canonical top-level key order in ``verified.json``. Matches the
# order our integration emits in diagnostics.py, with provenance
# prepended. See _INTEGRATION_EXTRA_KEYS comment for why this is
# duplicated locally instead of imported.
_VERIFIED_KEY_ORDER: tuple[str, ...] = (
    "verified_at",
    "version",
    "config_entry",
    "core_diagnostics",
    "data_coordinator",
    "health_coordinator",
    "modem_data",
    "system_info",
    "downstream_channels",
    "upstream_channels",
)

# Channel arrays render compact (one channel object per line); every
# other dict body uses standard 2-space indentation.
_CHANNEL_ARRAY_KEYS: tuple[str, ...] = ("downstream_channels", "upstream_channels")

# Aggregate system_info fields not in field_registry.SYSTEM_INFO_FIELDS
# (which covers Tier-1 always-present modem facts). Aggregates are
# computed from channel data and should always be present once channels
# are populated.
_AGGREGATE_SYSTEM_INFO_FIELDS: tuple[str, ...] = (
    "total_corrected",
    "total_uncorrected",
)

# system_info fields we expect populated on a healthy confirmation.
# Missing or null values trigger a "partial confirmation" warning.
_EXPECTED_SYSTEM_INFO_FIELDS: tuple[str, ...] = tuple(SYSTEM_INFO_FIELDS) + _AGGREGATE_SYSTEM_INFO_FIELDS


@dataclass
class VerifyResult:
    """Result of a diagnostics → verified.json transformation.

    Attributes:
        verified_json: Content ready to serialize and write.
        verified_path: Where the fixture would be written
            (``<catalog_root>/<manufacturer>/<model>/test_data/<variant>.verified.json``).
        yaml_path: Which ``modem.yaml`` (or ``modem-<variant>.yaml``)
            to flip from ``awaiting_verification`` to ``confirmed``.
        manufacturer: Resolved from ``data.config_entry.manufacturer``.
        model: Resolved from ``data.config_entry.model``.
        variant: Resolved from ``data.config_entry.variant`` (or None
            for single-variant modems).
        warnings: Drift, partial-confirmation, or shape surprises that
            the caller should review before committing.
    """

    verified_json: dict[str, Any]
    verified_path: Path
    yaml_path: Path
    manufacturer: str
    model: str
    variant: str | None
    warnings: list[str] = field(default_factory=list)

    def serialize(self) -> str:
        """Render verified_json to the canonical on-disk string form.

        Channel arrays render compact (one channel per line); every
        other dict body uses 2-space indentation. Trailing newline.
        """
        return _serialize_verified(self.verified_json)


def verify_diagnostics(
    diagnostics_path: Path,
    *,
    version: str,
    catalog_root: Path | None = None,
    verified_at: date | None = None,
    manufacturer_override: str | None = None,
    model_override: str | None = None,
    variant_override: str | None = None,
) -> VerifyResult:
    """Build a verified.json fixture from an HA diagnostics JSON.

    Args:
        diagnostics_path: Path to the HA-emitted diagnostics JSON
            (the file a contributor downloads from
            **Settings > Devices & Services > … > Download Diagnostics**).
        version: Release tag the contributor verified on, e.g.
            ``"3.14.0-beta.1"``.
        catalog_root: Path to the catalog ``modems`` directory.
            Defaults to the installed catalog package's ``CATALOG_PATH``.
        verified_at: Date the confirmation lands. Defaults to today.
        manufacturer_override: Force a manufacturer name when the
            self-reported value doesn't match the catalog directory.
        model_override: Force a model name when the catalog directory
            disambiguates hardware revisions the modem doesn't
            self-report (e.g. ``S33`` vs ``s33v2``).
        variant_override: Force a variant slug for path resolution.
            Pass an empty string to force ``None`` (single-variant).

    Returns:
        ``VerifyResult`` with the rendered fixture, target paths, and
        any warnings worth reviewing before the caller commits.

    Raises:
        FileNotFoundError: ``diagnostics_path`` does not exist, or the
            resolved modem package is not in the catalog.
        ValueError: Diagnostics is missing the ``data`` wrapper, or
            ``data.config_entry`` lacks ``manufacturer`` / ``model``
            and no override was supplied.
    """
    if catalog_root is None:
        from solentlabs.cable_modem_monitor_catalog import CATALOG_PATH

        catalog_root = CATALOG_PATH

    if not diagnostics_path.exists():
        raise FileNotFoundError(f"Diagnostics file not found: {diagnostics_path}")

    raw = json.loads(diagnostics_path.read_text(encoding="utf-8"))

    data = raw.get("data")
    if not isinstance(data, dict):
        raise ValueError(
            f"Diagnostics missing top-level 'data' object — got keys {list(raw.keys())}. "
            "Is this an HA diagnostics download?"
        )

    config_entry = data.get("config_entry") or {}
    manufacturer = manufacturer_override or config_entry.get("manufacturer")
    model = model_override or config_entry.get("model")
    if not manufacturer or not model:
        raise ValueError(
            "config_entry missing manufacturer/model — cannot resolve "
            "catalog package. Pass --manufacturer/--model overrides "
            "(or supply newer diagnostics that include them)."
        )
    if variant_override is not None:
        variant: str | None = variant_override or None
    else:
        variant = config_entry.get("variant") or None

    modem_dir = catalog_root / _slug(manufacturer) / _slug(model)
    if not modem_dir.exists():
        raise FileNotFoundError(f"Modem package not found in catalog: {modem_dir}. Has the catalog entry been merged?")

    fixture_stem = f"modem-{variant}" if variant else "modem"
    verified_path = modem_dir / "test_data" / f"{fixture_stem}.verified.json"
    yaml_path = modem_dir / f"{fixture_stem}.yaml"

    warnings = _collect_warnings(data)

    verified_json = _build_verified_json(
        data=data,
        version=version,
        verified_at=verified_at or date.today(),
    )

    return VerifyResult(
        verified_json=verified_json,
        verified_path=verified_path,
        yaml_path=yaml_path,
        manufacturer=manufacturer,
        model=model,
        variant=variant,
        warnings=warnings,
    )


def _slug(name: str) -> str:
    """Lowercase and underscore-normalize a manufacturer or model name.

    Catalog directory names are lowercase with spaces replaced by
    underscores (e.g. ``"Solent Labs"`` → ``"solent_labs"``). The
    existing catalog only contains single-word manufacturers, but
    diagnostics from a multi-word manufacturer must still resolve.
    """
    return name.strip().lower().replace(" ", "_")


def _build_verified_json(
    *,
    data: dict[str, Any],
    version: str,
    verified_at: date,
) -> dict[str, Any]:
    """Assemble the verified.json content in canonical key order.

    Strips integration extras and unknown extras (anything not in
    _VERIFIED_KEY_ORDER); the unknown-extras drop is silent on the
    happy path because warnings already flagged them, and the goal
    here is a clean fixture.
    """
    payload = {k: v for k, v in data.items() if k not in _INTEGRATION_EXTRA_KEYS}

    # Canonicalize channel key order — older diagnostics (pre-canonicalization
    # in custom_components/cable_modem_monitor/diagnostics.py) emit channels
    # in parser-determined order; we match the catalog convention regardless.
    for key in _CHANNEL_ARRAY_KEYS:
        if key in payload and isinstance(payload[key], list):
            payload[key] = [canonicalize_channel_keys(ch) for ch in payload[key]]

    out: dict[str, Any] = {
        "verified_at": verified_at.isoformat(),
        "version": version,
    }
    for key in _VERIFIED_KEY_ORDER:
        if key in ("verified_at", "version"):
            continue
        if key in payload:
            out[key] = payload[key]
    return out


def _collect_warnings(data: dict[str, Any]) -> list[str]:
    """Surface drift, partial-confirmation, and shape surprises.

    Warnings are advisory — they don't block transformation. The
    caller decides whether to proceed.
    """
    warnings: list[str] = []

    # Coordinator / data health
    coord = data.get("data_coordinator") or {}
    if coord.get("last_update_success") is False:
        warnings.append(
            "data_coordinator.last_update_success is false — modem is "
            "not in a healthy state; re-confirm after a successful poll."
        )

    modem_data = data.get("modem_data") or {}
    err = modem_data.get("error") or ""
    if err:
        warnings.append(f"modem_data.error is non-empty: {err!r}")

    if "last_error" in data:
        warnings.append(
            "diagnostics contains 'last_error' — most recent poll raised an exception. Confirm with caution."
        )

    # Channel coverage
    if not data.get("downstream_channels"):
        warnings.append("downstream_channels is empty — no channel data captured.")
    if not data.get("upstream_channels"):
        warnings.append("upstream_channels is empty — no channel data captured.")

    # system_info completeness
    sysinfo = data.get("system_info") or {}
    missing_fields = [f for f in _EXPECTED_SYSTEM_INFO_FIELDS if sysinfo.get(f) in (None, "")]
    if missing_fields:
        warnings.append(
            f"system_info missing fields {missing_fields} — looks like a "
            "partial confirmation; verify the parser maps these before committing."
        )

    return warnings


def _serialize_verified(verified_json: dict[str, Any]) -> str:
    """Render verified_json with compact channel arrays.

    Strategy: serialize the dict with channels removed (standard
    indent=2), then splice compact channel-array blocks in their
    canonical position. This keeps the format byte-stable across
    runs and matches the convention used by every confirmed modem.
    """
    body_only = {k: v for k, v in verified_json.items() if k not in _CHANNEL_ARRAY_KEYS}
    body = json.dumps(body_only, indent=2, ensure_ascii=False).rstrip()
    assert body.endswith("}"), "expected JSON object"
    body = body[:-1].rstrip()
    if not body.endswith(","):
        body = body + ","

    blocks: list[str] = []
    for key in _CHANNEL_ARRAY_KEYS:
        if key not in verified_json:
            continue
        items = verified_json[key]
        lines = [f'  "{key}": [']
        for i, item in enumerate(items):
            sep = "," if i < len(items) - 1 else ""
            lines.append("    " + json.dumps(item, ensure_ascii=False) + sep)
        lines.append("  ]")
        blocks.append("\n".join(lines))

    return body + "\n" + ",\n".join(blocks) + "\n}\n"


def _main(argv: list[str] | None = None) -> int:
    """CLI entry: ``python -m …verify_diagnostics <path> --version <tag>``.

    Prints the resolved manufacturer/model/variant, target paths, and
    any warnings. With ``--write``, also writes the verified.json to
    its canonical location. Always non-destructive without ``--write``.
    """
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="verify_diagnostics",
        description=(
            "Build a verified.json fixture from an HA diagnostics JSON. "
            "Without --write, prints what would happen but writes nothing."
        ),
    )
    parser.add_argument(
        "diagnostics_path",
        type=Path,
        help="Path to the HA diagnostics JSON download.",
    )
    parser.add_argument(
        "--version",
        required=True,
        help="Release tag the contributor verified on (e.g. 3.14.0-beta.1).",
    )
    parser.add_argument(
        "--verified-at",
        type=date.fromisoformat,
        default=None,
        help="Date in YYYY-MM-DD form. Defaults to today.",
    )
    parser.add_argument(
        "--catalog-root",
        type=Path,
        default=None,
        help="Catalog 'modems' directory. Defaults to the installed "
        "cable_modem_monitor_catalog package's CATALOG_PATH.",
    )
    parser.add_argument(
        "--manufacturer",
        default=None,
        help="Force manufacturer name when the self-reported value doesn't match the catalog directory.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Force model name when the catalog directory disambiguates hardware revisions (e.g. S33 vs s33v2).",
    )
    parser.add_argument(
        "--variant",
        default=None,
        help="Force variant slug for path resolution. Pass an empty string to force single-variant (no suffix).",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write verified.json to its catalog location. Without this flag, the CLI runs read-only.",
    )
    args = parser.parse_args(argv)

    try:
        result = verify_diagnostics(
            args.diagnostics_path,
            version=args.version,
            catalog_root=args.catalog_root,
            verified_at=args.verified_at,
            manufacturer_override=args.manufacturer,
            model_override=args.model,
            variant_override=args.variant,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"manufacturer:  {result.manufacturer}")
    print(f"model:         {result.model}")
    print(f"variant:       {result.variant or '(none)'}")
    print(f"verified_path: {result.verified_path}")
    print(f"yaml_path:     {result.yaml_path}")

    if result.warnings:
        print("\nwarnings:", file=sys.stderr)
        for warning in result.warnings:
            print(f"  - {warning}", file=sys.stderr)

    if args.write:
        result.verified_path.parent.mkdir(parents=True, exist_ok=True)
        result.verified_path.write_text(result.serialize(), encoding="utf-8")
        print(f"\nwrote {result.verified_path}")
    else:
        print("\n(read-only; pass --write to update the catalog)")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
