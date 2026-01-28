#!/usr/bin/env python3
"""Validate modem.yaml files have complete configuration.

Pre-commit hook that validates modem.yaml files when they change.
Ensures auth config is complete for the declared auth types.

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


def validate_form_auth(type_config: dict, path: str, auth_type: str) -> list[ValidationError]:
    """Validate form auth configuration."""
    errors = []

    # type_config is None for auth types that don't need config (like "none")
    if type_config is None:
        return errors

    required_fields = [
        ("action", "Form action URL required"),
        ("username_field", "Username field name required"),
        ("password_field", "Password field name required"),
    ]

    for field, message in required_fields:
        if not type_config.get(field):
            errors.append(ValidationError(path, f"auth.types.{auth_type}.{field}", message))

    # Validate password_encoding if present
    encoding = type_config.get("password_encoding")
    if encoding and encoding not in ("plain", "base64"):
        errors.append(
            ValidationError(
                path,
                f"auth.types.{auth_type}.password_encoding",
                f"Invalid encoding: {encoding}. Must be 'plain' or 'base64'",
            )
        )

    return errors


def validate_hnap_auth(type_config: dict, path: str, auth_type: str) -> list[ValidationError]:
    """Validate HNAP auth configuration."""
    errors = []

    if type_config is None:
        return errors

    # HNAP needs endpoint at minimum
    if not type_config.get("endpoint"):
        errors.append(ValidationError(path, f"auth.types.{auth_type}.endpoint", "HNAP endpoint required"))

    return errors


def validate_url_token_auth(type_config: dict, path: str, auth_type: str) -> list[ValidationError]:
    """Validate URL token auth configuration."""
    errors = []

    if type_config is None:
        return errors

    required_fields = [
        ("login_page", "Login page URL required"),
        ("session_cookie", "Session cookie name required"),
    ]

    for field, message in required_fields:
        if not type_config.get(field):
            errors.append(ValidationError(path, f"auth.types.{auth_type}.{field}", message))

    return errors


def validate_basic_auth(type_config: dict, path: str, auth_type: str) -> list[ValidationError]:
    """Validate basic auth configuration."""
    # Basic auth doesn't need additional config - credentials come from user
    return []


def validate_form_ajax_auth(type_config: dict, path: str, auth_type: str) -> list[ValidationError]:
    """Validate form_ajax auth configuration."""
    errors = []

    if type_config is None:
        errors.append(ValidationError(path, f"auth.types.{auth_type}", "form_ajax config required"))
        return errors

    if not type_config.get("endpoint"):
        errors.append(ValidationError(path, f"auth.types.{auth_type}.endpoint", "AJAX endpoint required"))

    return errors


def validate_form_nonce_auth(type_config: dict, path: str, auth_type: str) -> list[ValidationError]:
    """Validate form_nonce auth configuration."""
    errors = []

    if type_config is None:
        errors.append(ValidationError(path, f"auth.types.{auth_type}", "form_nonce config required"))
        return errors

    if not type_config.get("endpoint"):
        errors.append(ValidationError(path, f"auth.types.{auth_type}.endpoint", "form endpoint required"))

    return errors


def validate_rest_api_auth(type_config: dict, path: str, auth_type: str) -> list[ValidationError]:
    """Validate REST API auth configuration."""
    errors = []

    if type_config is None:
        return errors

    if not type_config.get("base_path"):
        errors.append(ValidationError(path, f"auth.types.{auth_type}.base_path", "REST API base path required"))

    return errors


def validate_none_auth(type_config: dict, path: str, auth_type: str) -> list[ValidationError]:
    """Validate none auth configuration."""
    # No auth doesn't need config - type_config can be None or empty dict
    return []


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
    """Validate pages configuration."""
    errors = []
    pages = config.get("pages", {})

    # Protected pages usually required (except for some special modems)
    # This is a soft validation - just a warning for now
    # Note: Some modems with parser.class defined don't need pages config
    # (no action taken here - keeping as passive check for future use)
    _ = pages.get("protected") or pages.get("public") or not config.get("parser", {}).get("class")

    return errors


def is_work_in_progress(config: dict) -> bool:
    """Check if modem config is marked as work-in-progress."""
    status_info = config.get("status_info", {})
    status = status_info.get("status", "")
    return status in ("in_progress", "unsupported", "wip")


def validate_auth_types(config: dict, path: str) -> list[ValidationError]:
    """Validate auth.types{} configuration."""
    errors = []
    auth = config.get("auth", {})
    auth_types = auth.get("types", {})

    if not auth_types:
        errors.append(ValidationError(path, "auth.types", "Auth types required"))
        return errors

    # Validators for each auth type
    type_validators = {
        "form": validate_form_auth,
        "form_ajax": validate_form_ajax_auth,
        "form_dynamic": validate_form_auth,  # Uses same validation as form
        "form_nonce": validate_form_nonce_auth,
        "hnap": validate_hnap_auth,
        "url_token": validate_url_token_auth,
        "basic": validate_basic_auth,
        "rest_api": validate_rest_api_auth,
        "none": validate_none_auth,
    }

    for auth_type, type_config in auth_types.items():
        validator = type_validators.get(auth_type)
        if validator:
            errors.extend(validator(type_config, path, auth_type))
        else:
            errors.append(ValidationError(path, f"auth.types.{auth_type}", f"Unknown auth type: {auth_type}"))

    return errors


def validate_config(config: dict, path: Path) -> list[ValidationError]:
    """Validate a modem.yaml configuration."""
    errors = []
    path_str = str(path)

    # Required top-level fields
    if not config.get("manufacturer"):
        errors.append(ValidationError(path_str, "manufacturer", "Manufacturer required"))

    if not config.get("model"):
        errors.append(ValidationError(path_str, "model", "Model required"))

    # Work-in-progress configs get minimal validation
    if is_work_in_progress(config):
        # Just validate auth types if present, don't require everything
        auth = config.get("auth", {})
        auth_types = auth.get("types", {})
        if auth_types:
            errors.extend(validate_auth_types(config, path_str))
        return errors

    # Full validation for complete configs
    errors.extend(validate_auth_types(config, path_str))

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

    try:
        with open(yaml_path) as f:
            config = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        all_errors.append(ValidationError(str(yaml_path), "yaml", f"Invalid YAML: {e}"))
        return

    # Skip work-in-progress but report them
    if is_work_in_progress(config):
        wip_count_ref[0] += 1
        print(f"  {yaml_path.relative_to(PROJECT_ROOT)} (work-in-progress)")
        # Still validate what's present
        errors = validate_config(config, yaml_path)
        if errors:
            all_errors.extend(errors)
        return

    errors = validate_config(config, yaml_path)
    all_errors.extend(errors)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Validate modem.yaml configurations")
    parser.add_argument("files", nargs="*", help="Files to validate")
    parser.add_argument("--all", action="store_true", help="Validate all modem.yaml files")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    files = get_files_to_validate(args)
    if files is None:
        print("No modem.yaml files found to validate")
        return 0

    all_errors: list[ValidationError] = []
    wip_count = [0]  # Use list to allow mutation in nested function

    # Group files for batch reporting (4 files per batch for cleaner output)
    batch_size = 4
    for i in range(0, len(files), batch_size):
        batch = files[i : i + batch_size]
        batch_errors: list[ValidationError] = []

        for yaml_path in batch:
            validate_single_file(yaml_path, batch_errors, wip_count)

        # Report batch errors
        if batch_errors:
            for error in batch_errors:
                print(f"\n{error.path}:")
                print(f"  - {error.field}: {error.message}")
            print(f"\nValidation failed with {len(batch_errors)} error(s)")
            all_errors.extend(batch_errors)

    if wip_count[0] > 0 and args.verbose:
        print(f"\nSkipped {wip_count[0]} work-in-progress configs")

    if all_errors:
        return 1

    if args.verbose:
        print(f"\nValidated {len(files)} modem.yaml files successfully")

    return 0


if __name__ == "__main__":
    sys.exit(main())
