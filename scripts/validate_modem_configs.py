#!/usr/bin/env python3
"""Validate modem.yaml files have complete configuration.

Pre-commit hook that validates modem.yaml files when they change.
Ensures auth config is complete for the declared strategy.

Usage:
    python scripts/validate_modem_configs.py [file1.yaml file2.yaml ...]
    python scripts/validate_modem_configs.py --all
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class ValidationError:
    """Represents a validation error."""

    def __init__(self, path: str, field: str, message: str):
        self.path = path
        self.field = field
        self.message = message

    def __str__(self) -> str:
        return f"{self.path}: {self.field} - {self.message}"


def validate_form_auth(config: dict, path: str) -> list[ValidationError]:
    """Validate form auth configuration."""
    errors = []
    form = config.get("auth", {}).get("form", {})

    required_fields = [
        ("action", "Form action URL required"),
        ("username_field", "Username field name required"),
        ("password_field", "Password field name required"),
    ]

    for field, message in required_fields:
        if not form.get(field):
            errors.append(ValidationError(path, f"auth.form.{field}", message))

    # Validate password_encoding if present
    encoding = form.get("password_encoding")
    if encoding and encoding not in ("plain", "base64"):
        errors.append(
            ValidationError(
                path, "auth.form.password_encoding", f"Invalid encoding: {encoding}. Must be 'plain' or 'base64'"
            )
        )

    return errors


def validate_hnap_auth(config: dict, path: str) -> list[ValidationError]:
    """Validate HNAP auth configuration."""
    errors = []
    hnap = config.get("auth", {}).get("hnap", {})

    # HNAP needs endpoint at minimum
    if not hnap.get("endpoint"):
        errors.append(ValidationError(path, "auth.hnap.endpoint", "HNAP endpoint required"))

    return errors


def validate_url_token_auth(config: dict, path: str) -> list[ValidationError]:
    """Validate URL token auth configuration."""
    errors = []
    url_token = config.get("auth", {}).get("url_token", {})

    required_fields = [
        ("login_page", "Login page URL required"),
        ("session_cookie", "Session cookie name required"),
    ]

    for field, message in required_fields:
        if not url_token.get(field):
            errors.append(ValidationError(path, f"auth.url_token.{field}", message))

    return errors


def validate_basic_auth(config: dict, path: str) -> list[ValidationError]:
    """Validate basic auth configuration."""
    # Basic auth doesn't need additional config - credentials come from user
    return []


def validate_rest_api_auth(config: dict, path: str) -> list[ValidationError]:
    """Validate REST API auth configuration."""
    errors = []
    rest_api = config.get("auth", {}).get("rest_api", {})

    if not rest_api.get("base_path"):
        errors.append(ValidationError(path, "auth.rest_api.base_path", "REST API base path required"))

    return errors


def validate_detection(config: dict, path: str) -> list[ValidationError]:
    """Validate detection configuration."""
    errors = []
    detection = config.get("detection", {})

    # Must have at least one detection method (v3.12+ uses pre_auth/post_auth)
    has_pre_auth = bool(detection.get("pre_auth"))
    has_post_auth = bool(detection.get("post_auth"))
    has_json = bool(detection.get("json_markers"))

    if not (has_pre_auth or has_post_auth or has_json):
        errors.append(
            ValidationError(
                path,
                "detection",
                "At least one detection method required (pre_auth, post_auth, or json_markers)",
            )
        )

    return errors


def validate_parser(config: dict, path: str) -> list[ValidationError]:
    """Validate parser configuration."""
    errors = []
    parser = config.get("parser", {})

    if not parser.get("class"):
        errors.append(ValidationError(path, "parser.class", "Parser class name required"))

    if not parser.get("module"):
        errors.append(ValidationError(path, "parser.module", "Parser module path required"))

    return errors


def validate_pages(config: dict, path: str) -> list[ValidationError]:
    """Validate pages configuration for non-REST modems."""
    errors: list[ValidationError] = []

    # REST API modems don't need pages config
    if config.get("paradigm") == "rest_api":
        return errors

    # HNAP modems don't need pages config (they use HNAP actions)
    if config.get("auth", {}).get("strategy") == "hnap":
        return errors

    pages = config.get("pages", {})

    # Should have at least public or protected pages defined
    has_public = bool(pages.get("public"))
    has_protected = bool(pages.get("protected"))

    if not (has_public or has_protected):
        errors.append(ValidationError(path, "pages", "At least public or protected pages should be defined"))

    return errors


def is_work_in_progress(config: dict) -> bool:
    """Check if this is a work-in-progress config (no parser yet)."""
    # No parser class = work in progress
    parser = config.get("parser", {})
    if not parser.get("class"):
        return True

    # Explicit in_progress status
    status_info = config.get("status_info", {})
    return bool(status_info.get("status") == "in_progress")


def validate_modem_config(yaml_path: Path) -> list[ValidationError]:
    """Validate a single modem.yaml file."""
    errors = []
    path_str = str(yaml_path)

    try:
        with open(yaml_path) as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return [ValidationError(path_str, "yaml", f"Invalid YAML: {e}")]

    if not config:
        return [ValidationError(path_str, "root", "Empty configuration")]

    # Required top-level fields (always required)
    if not config.get("manufacturer"):
        errors.append(ValidationError(path_str, "manufacturer", "Manufacturer required"))

    if not config.get("model"):
        errors.append(ValidationError(path_str, "model", "Model required"))

    # Work-in-progress configs get minimal validation
    if is_work_in_progress(config):
        # Just validate what's present, don't require everything
        auth = config.get("auth", {})
        strategy = auth.get("strategy")
        if strategy:
            strategy_validators = {
                "form": validate_form_auth,
                "hnap": validate_hnap_auth,
                "url_token": validate_url_token_auth,
                "basic": validate_basic_auth,
                "rest_api": validate_rest_api_auth,
                "none": lambda c, p: [],
            }
            validator = strategy_validators.get(strategy)
            if validator:
                errors.extend(validator(config, path_str))
        return errors

    # Full validation for complete configs
    auth = config.get("auth", {})
    strategy = auth.get("strategy")

    if not strategy:
        errors.append(ValidationError(path_str, "auth.strategy", "Auth strategy required"))
    else:
        strategy_validators = {
            "form": validate_form_auth,
            "hnap": validate_hnap_auth,
            "url_token": validate_url_token_auth,
            "basic": validate_basic_auth,
            "rest_api": validate_rest_api_auth,
            "none": lambda c, p: [],  # No auth needs no config
        }

        validator = strategy_validators.get(strategy)
        if validator:
            errors.extend(validator(config, path_str))
        else:
            errors.append(ValidationError(path_str, "auth.strategy", f"Unknown strategy: {strategy}"))

    # Detection validation
    errors.extend(validate_detection(config, path_str))

    # Parser validation
    errors.extend(validate_parser(config, path_str))

    # Pages validation
    errors.extend(validate_pages(config, path_str))

    return errors


def find_all_modem_configs() -> list[Path]:
    """Find all modem.yaml files in the modems/ directory."""
    modems_dir = PROJECT_ROOT / "modems"
    if not modems_dir.exists():
        return []
    return list(modems_dir.glob("*/*/modem.yaml"))


def get_files_to_validate(args) -> list[Path] | None:
    """Get list of files to validate based on args."""
    if args.all:
        files = find_all_modem_configs()
        return files if files else None
    elif args.files:
        return [Path(f).resolve() for f in args.files]
    else:
        files = find_all_modem_configs()
        return files if files else None


def validate_single_file(yaml_path: Path, all_errors: list, wip_count_ref: list) -> None:
    """Validate a single file and update error/wip counts."""
    if not yaml_path.exists():
        all_errors.append(ValidationError(str(yaml_path), "file", "File not found"))
        return

    # Check if WIP before validation
    try:
        with open(yaml_path) as f:
            config = yaml.safe_load(f) or {}
        is_wip = is_work_in_progress(config)
    except Exception:
        is_wip = False

    errors = validate_modem_config(yaml_path)
    all_errors.extend(errors)

    try:
        rel_path = yaml_path.relative_to(PROJECT_ROOT)
    except ValueError:
        rel_path = yaml_path

    if errors:
        print(f"\n{yaml_path}:")
        for error in errors:
            print(f"  - {error.field}: {error.message}")
    elif is_wip:
        wip_count_ref[0] += 1
        print(f"  {rel_path} (work-in-progress)")
    else:
        print(f"  {rel_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate modem.yaml configurations")
    parser.add_argument("files", nargs="*", help="modem.yaml files to validate")
    parser.add_argument("--all", action="store_true", help="Validate all modem.yaml files")
    args = parser.parse_args()

    files = get_files_to_validate(args)
    if not files:
        print("No modem.yaml files found")
        return 0

    all_errors: list[ValidationError] = []
    wip_count_ref = [0]  # Use list as mutable reference

    for yaml_path in files:
        validate_single_file(yaml_path, all_errors, wip_count_ref)

    if all_errors:
        print(f"\nValidation failed with {len(all_errors)} error(s)")
        return 1

    wip_count = wip_count_ref[0]
    complete_count = len(files) - wip_count
    print(f"\nValidated {len(files)} modem.yaml file(s): {complete_count} complete, {wip_count} work-in-progress")
    return 0


if __name__ == "__main__":
    sys.exit(main())
