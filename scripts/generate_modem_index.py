#!/usr/bin/env python3
"""Generate modem index from modem.yaml files.

Creates a lightweight index file for fast parser lookups without
loading all modem.yaml files at runtime.

v3.12+ Architecture: Aggregates auth knowledge from ALL modems so core
auth code can be completely generic (no modem-specific knowledge).

Usage:
    python scripts/generate_modem_index.py [--output PATH]
"""

from __future__ import annotations

import argparse
import contextlib
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _build_detection_entry(config: dict) -> dict:
    """Build detection entry preserving pre_auth/post_auth separation.

    Returns a dict with pre_auth, post_auth, and page_hint fields
    for the elimination-based detection model.
    """
    detection = config.get("detection", {})
    entry = {}

    # Pre-auth patterns (match on login/entry page)
    pre_auth = detection.get("pre_auth", [])
    if pre_auth:
        entry["pre_auth"] = pre_auth

    # Post-auth patterns (match on data pages after authentication)
    post_auth = detection.get("post_auth", [])
    # Add model name as fallback pattern for post_auth
    model = config.get("model")
    if model and model not in post_auth:
        post_auth = list(post_auth) + [model]
    if post_auth:
        entry["post_auth"] = post_auth

    # Page hint for where to fetch post_auth content
    if detection.get("page_hint"):
        entry["page_hint"] = detection["page_hint"]

    return entry


def _build_modem_entry(config: dict, path_str: str) -> dict:
    """Build modem index entry from config."""
    manufacturer = config.get("manufacturer", "Unknown")
    model = config.get("model", "Unknown")
    entry = {
        "path": path_str,
        "name": f"{manufacturer} {model}",  # Display name for direct lookup
        "manufacturer": manufacturer,
        "model": model,
    }

    # Verification status (for dropdown asterisk marking)
    status_info = config.get("status_info", {})
    status = status_info.get("status", "unverified")
    entry["verified"] = status == "verified"

    # Detection patterns with pre_auth/post_auth separation (v3.12+ architecture)
    detection_entry = _build_detection_entry(config)
    if detection_entry:
        entry["detection"] = detection_entry

    return entry


def _aggregate_auth_patterns(configs: list[dict]) -> dict:  # noqa: C901
    """Aggregate auth patterns from all modem configs.

    Collects ALL known field names, encodings, etc. so core auth
    code can use collective knowledge without modem-specific logic.
    """
    # Form auth patterns
    username_fields: set[str] = set()
    password_fields: set[str] = set()
    form_actions: set[str] = set()
    encodings: list[dict] = []
    encoding_patterns_seen: set[str] = set()

    # HNAP patterns
    hnap_endpoints: set[str] = set()
    hnap_namespaces: set[str] = set()

    # URL token patterns
    url_token_indicators: set[str] = set()

    for config in configs:
        auth = config.get("auth", {})
        # v3.12+ uses auth.types.{form,hnap,url_token}
        auth_types = auth.get("types", {})

        # Form auth - check auth.form (legacy), auth.types.form, and auth.types.form_dynamic
        form = auth.get("form", {}) or auth_types.get("form", {}) or auth_types.get("form_dynamic", {})
        if form:
            if uf := form.get("username_field"):
                username_fields.add(uf)
            if pf := form.get("password_field"):
                password_fields.add(pf)
            if action := form.get("action"):
                form_actions.add(action)

            # Track password encoding with detection pattern
            encoding = form.get("password_encoding", "plain")
            if encoding == "base64":
                # Add known base64 detection patterns
                base64_patterns = [
                    r"isEncryptPswd\s*=\s*1",
                    r'keyStr\s*=\s*["\']ABCDEFGHIJKLMNOPQRSTUVWXYZ',
                    r"btoa\s*\(",
                ]
                for pattern in base64_patterns:
                    if pattern not in encoding_patterns_seen:
                        encoding_patterns_seen.add(pattern)
                        encodings.append({"detect": pattern, "type": "base64"})

        # Also check strategies list for auth variations
        for strategy_entry in auth.get("strategies", []):
            if strategy_form := strategy_entry.get("form", {}):
                if uf := strategy_form.get("username_field"):
                    username_fields.add(uf)
                if pf := strategy_form.get("password_field"):
                    password_fields.add(pf)
                if action := strategy_form.get("action"):
                    form_actions.add(action)

        # HNAP auth - check both auth.hnap (legacy) and auth.types.hnap (v3.12+)
        hnap = auth.get("hnap", {}) or auth_types.get("hnap", {})
        if hnap:
            if endpoint := hnap.get("endpoint"):
                hnap_endpoints.add(endpoint)
            if namespace := hnap.get("namespace"):
                hnap_namespaces.add(namespace)

        # URL token auth - check both auth.url_token and auth.types.url_token
        url_token = auth.get("url_token", {}) or auth_types.get("url_token", {})
        if url_token:
            if prefix := url_token.get("login_prefix"):
                url_token_indicators.add(prefix)
            if cookie := url_token.get("session_cookie"):
                url_token_indicators.add(cookie)

    return {
        "form": {
            "username_fields": sorted(username_fields),
            "password_fields": sorted(password_fields),
            "actions": sorted(form_actions),
            "encodings": encodings,
        },
        "hnap": {
            "endpoints": sorted(hnap_endpoints),
            "namespaces": sorted(hnap_namespaces),
        },
        "url_token": {
            "indicators": sorted(url_token_indicators),
        },
    }


def generate_index(modems_root: Path) -> dict:
    """Generate modem index from modem.yaml files.

    Args:
        modems_root: Path to modems/ directory

    Returns:
        Index dictionary ready for YAML serialization
    """
    modems: dict[str, dict] = {}
    all_configs: list[dict] = []

    # Scan for modem.yaml files
    for yaml_path in sorted(modems_root.glob("*/*/modem.yaml")):
        try:
            with open(yaml_path) as f:
                config = yaml.safe_load(f)

            if not config:
                continue

            # Extract parser class name
            parser_info = config.get("parser", {})
            parser_class = parser_info.get("class")
            if not parser_class:
                print(f"  Skipping {yaml_path}: no parser.class defined")
                continue

            # Build relative path (e.g., "motorola/mb7621")
            rel_path = yaml_path.parent.relative_to(modems_root)
            path_str = str(rel_path).replace("\\", "/")  # Normalize for Windows

            entry = _build_modem_entry(config, path_str)
            modems[parser_class] = entry
            all_configs.append(config)
            print(f"  Indexed: {parser_class} -> {path_str}")

        except Exception as e:
            print(f"  Error processing {yaml_path}: {e}")

    # Aggregate auth patterns from all modems (v3.12+ architecture)
    auth_patterns = _aggregate_auth_patterns(all_configs)

    index: dict[str, object] = {
        "version": 1,
        "generated": datetime.now(UTC).isoformat(),
        "auth_patterns": auth_patterns,
        "modems": modems,
    }

    return index


def _get_committed_index(output_path: Path) -> dict | None:
    """Get the committed version of index.yaml from git.

    Returns None if file is not tracked or git command fails.
    """
    try:
        # Get path relative to git root
        rel_path = output_path.relative_to(PROJECT_ROOT)
        result = subprocess.run(
            ["git", "show", f"HEAD:{rel_path}"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            loaded: dict | None = yaml.safe_load(result.stdout)
            return loaded
    except (subprocess.SubprocessError, ValueError):
        pass
    return None


def write_index(index: dict, output_path: Path) -> None:
    """Write index to YAML file.

    Only writes if content has changed compared to the committed version.
    This prevents spurious changes when the script is run multiple times.

    Args:
        index: Index dictionary
        output_path: Path to write index file
    """
    # Compare against committed version (ignoring generated timestamp)
    committed = _get_committed_index(output_path)
    if committed:
        # Compare modems and auth_patterns only (not version or generated)
        modems_unchanged = committed.get("modems") == index["modems"]
        auth_unchanged = committed.get("auth_patterns") == index.get("auth_patterns")
        if modems_unchanged and auth_unchanged:
            print(f"\nNo content changes to {output_path}")
            print(f"Total modems indexed: {len(index['modems'])}")
            return

    # Custom YAML representer for cleaner output
    def str_representer(dumper, data):
        if "\n" in data:
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
        return dumper.represent_scalar("tag:yaml.org,2002:str", data)

    yaml.add_representer(str, str_representer)

    with open(output_path, "w") as f:
        f.write("# Modem Index - Generated file, do not edit manually\n")
        f.write("# Regenerate with: python scripts/generate_modem_index.py\n\n")
        yaml.dump(index, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    # Run prettier to ensure consistent formatting with pre-commit hooks
    with contextlib.suppress(subprocess.SubprocessError, FileNotFoundError):
        subprocess.run(
            ["npx", "prettier", "--write", str(output_path)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            check=False,
        )

    print(f"\nWrote index to {output_path}")
    print(f"Total modems indexed: {len(index['modems'])}")


def main():
    parser = argparse.ArgumentParser(description="Generate modem index")
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "custom_components" / "cable_modem_monitor" / "modems" / "index.yaml",
        help="Output path for index file",
    )
    parser.add_argument(
        "--modems-root",
        type=Path,
        default=PROJECT_ROOT / "modems",
        help="Root directory containing modem folders",
    )
    args = parser.parse_args()

    print(f"Scanning modems in: {args.modems_root}")
    index = generate_index(args.modems_root)

    if not index["modems"]:
        print("No modems found!")
        sys.exit(1)

    write_index(index, args.output)


if __name__ == "__main__":
    main()
