#!/usr/bin/env python3
"""Release automation script for Cable Modem Monitor.

This script automates the complete release process by:
1. Validating the version format
2. Checking git working directory is clean
3. Running tests (pytest)
4. Running code quality checks (ruff, black, mypy)
5. Verifying translations/en.json matches strings.json
6. Syncing modem.yaml and parser.py files from modems/ to custom_components/
   (deployment bridge: modems/ is source of truth, ships modem.yaml + parser.py)
7. Updating version in all required files:
   - custom_components/cable_modem_monitor/manifest.json
   - custom_components/cable_modem_monitor/const.py
   - tests/components/test_version_and_startup.py
8. Updating CHANGELOG.md
9. Creating a git commit with all changes
10. Creating an annotated git tag
11. Pushing to remote (optional)
12. Creating a GitHub release (optional)

Usage:
    python scripts/release.py --sync-only              # Sync modem configs/parsers only
    python scripts/release.py 3.5.2                    # Full release
    python scripts/release.py 3.5.2 --no-push          # Test locally without pushing
    python scripts/release.py 3.5.2 --skip-tests       # Skip tests (not recommended)
    python scripts/release.py 3.5.2 --skip-quality     # Skip code quality checks
    python scripts/release.py 3.5.2 --skip-changelog   # Don't update changelog
"""

from __future__ import annotations

import argparse
import contextlib
import json
import re
import subprocess
import sys
from pathlib import Path


def print_error(msg: str) -> None:
    """Print error message in red."""
    print(f"\033[91m✗ {msg}\033[0m", file=sys.stderr)


def print_success(msg: str) -> None:
    """Print success message in green."""
    print(f"\033[92m✓ {msg}\033[0m")


def print_info(msg: str) -> None:
    """Print info message in blue."""
    print(f"\033[94mℹ {msg}\033[0m")


def print_warning(msg: str) -> None:
    """Print warning message in yellow."""
    print(f"\033[93m⚠ {msg}\033[0m")


def validate_version(version: str) -> bool:
    """Validate that version follows semantic versioning (X.Y.Z)."""
    pattern = r"^\d+\.\d+\.\d+$"
    return bool(re.match(pattern, version))


def get_repo_root() -> Path:
    """Get the repository root directory."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to get repository root: {e}")
        sys.exit(1)


def check_git_clean() -> bool:
    """Check if git working directory is clean."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )
        return not result.stdout.strip()
    except subprocess.CalledProcessError:
        return False


def update_manifest(repo_root: Path, version: str) -> bool:
    """Update version in manifest.json."""
    manifest_path = repo_root / "custom_components" / "cable_modem_monitor" / "manifest.json"

    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)

        old_version = manifest.get("version", "unknown")
        manifest["version"] = version

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
            f.write("\n")  # Add trailing newline

        print_success(f"Updated manifest.json: {old_version} → {version}")
        return True
    except Exception as e:
        print_error(f"Failed to update manifest.json: {e}")
        return False


def update_const_py(repo_root: Path, version: str) -> bool:
    """Update VERSION constant in const.py."""
    const_path = repo_root / "custom_components" / "cable_modem_monitor" / "const.py"

    try:
        with open(const_path, encoding="utf-8") as f:
            content = f.read()

        # Find the current version
        version_match = re.search(r'VERSION = "([^"]+)"', content)
        if not version_match:
            print_error("Could not find VERSION constant in const.py")
            return False

        old_version = version_match.group(1)

        # Replace the version
        new_content = re.sub(r'VERSION = "[^"]+"', f'VERSION = "{version}"', content, count=1)

        with open(const_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        print_success(f"Updated const.py: {old_version} → {version}")
        return True
    except Exception as e:
        print_error(f"Failed to update const.py: {e}")
        return False


def update_version_test(repo_root: Path, version: str) -> bool:
    """Update version test in test_version_and_startup.py."""
    test_path = repo_root / "tests" / "components" / "test_version_and_startup.py"

    try:
        with open(test_path, encoding="utf-8") as f:
            content = f.read()

        # Find the current version in the test
        version_match = re.search(r'assert VERSION == "([^"]+)"', content)
        if not version_match:
            print_error("Could not find version assertion in test file")
            return False

        old_version = version_match.group(1)

        # Replace the version
        new_content = re.sub(
            r'assert VERSION == "[^"]+"',
            f'assert VERSION == "{version}"',
            content,
            count=1,
        )

        with open(test_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        print_success(f"Updated test_version_and_startup.py: {old_version} → {version}")
        return True
    except Exception as e:
        print_error(f"Failed to update version test: {e}")
        return False


def update_changelog(repo_root: Path, version: str) -> bool:
    """Update CHANGELOG.md to move Unreleased to new version."""
    changelog_path = repo_root / "CHANGELOG.md"

    try:
        with open(changelog_path, encoding="utf-8") as f:
            content = f.read()

        # Check if there's an Unreleased section
        if "## [Unreleased]" not in content:
            print_warning("No [Unreleased] section found in CHANGELOG.md")
            return True

        # Get today's date
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")

        # Replace ## [Unreleased] with ## [version] - date and add new [Unreleased]
        new_content = content.replace(
            "## [Unreleased]",
            f"## [Unreleased]\n\n## [{version}] - {today}",
            1,
        )

        with open(changelog_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        print_success(f"Updated CHANGELOG.md for version {version}")
        return True
    except Exception as e:
        print_error(f"Failed to update CHANGELOG.md: {e}")
        return False


def create_commit(version: str, skip_verify: bool = False) -> bool:
    """Create a git commit with version changes."""
    try:
        # Stage the files
        subprocess.run(
            [
                "git",
                "add",
                "custom_components/cable_modem_monitor/manifest.json",
                "custom_components/cable_modem_monitor/const.py",
                "tests/components/test_version_and_startup.py",
                "CHANGELOG.md",
            ],
            check=True,
        )

        # Create commit
        commit_msg = f"chore: bump version to {version}"
        cmd = ["git", "commit", "-m", commit_msg]
        if skip_verify:
            cmd.append("--no-verify")

        subprocess.run(cmd, check=True)

        print_success(f"Created commit: {commit_msg}")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to create commit: {e}")
        return False


def create_tag(version: str) -> bool:
    """Create an annotated git tag."""
    try:
        tag_name = f"v{version}"
        tag_msg = f"Release v{version}"

        subprocess.run(["git", "tag", "-a", tag_name, "-m", tag_msg], check=True)

        print_success(f"Created tag: {tag_name}")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to create tag: {e}")
        return False


def push_changes(version: str, skip_verify: bool = False) -> bool:
    """Push commit and tag to remote."""
    try:
        tag_name = f"v{version}"

        # Push commit
        cmd = ["git", "push", "origin", "main"]
        if skip_verify:
            cmd.append("--no-verify")

        subprocess.run(cmd, check=True)
        print_success("Pushed commit to origin/main")

        # Push tag
        cmd = ["git", "push", "origin", tag_name]
        if skip_verify:
            cmd.append("--no-verify")

        subprocess.run(cmd, check=True)
        print_success(f"Pushed tag {tag_name} to origin")

        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to push changes: {e}")
        return False


def create_github_release(version: str, repo_root: Path) -> bool:
    """Create a GitHub release using gh CLI."""
    try:
        tag_name = f"v{version}"

        # Extract release notes from CHANGELOG
        changelog_path = repo_root / "CHANGELOG.md"
        with open(changelog_path, encoding="utf-8") as f:
            content = f.read()

        # Find the section for this version
        version_pattern = rf"## \[{re.escape(version)}\][^\n]*\n(.*?)(?=## \[|$)"
        match = re.search(version_pattern, content, re.DOTALL)

        if match:
            release_notes = match.group(1).strip()
        else:
            release_notes = f"Release version {version}"

        # Create release
        subprocess.run(
            [
                "gh",
                "release",
                "create",
                tag_name,
                "--title",
                f"Version {version}",
                "--notes",
                release_notes,
            ],
            check=True,
        )

        print_success(f"Created GitHub release: {tag_name}")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to create GitHub release: {e}")
        print_info("You can create it manually using: gh release create")
        return False


def run_tests(repo_root: Path) -> bool:
    """Run the full test suite."""
    try:
        print_info("Running tests...")
        subprocess.run(
            [str(repo_root / ".venv" / "bin" / "python"), "-m", "pytest", "-v"],
            cwd=repo_root,
            check=True,
        )
        print_success("All tests passed")
        return True
    except subprocess.CalledProcessError:
        print_error("Tests failed! Fix issues before releasing.")
        return False


def run_code_quality_checks(repo_root: Path) -> bool:
    """Run code quality checks (ruff, black, mypy).

    Matches CI configuration exactly to catch issues before push.
    """
    try:
        venv_python = str(repo_root / ".venv" / "bin" / "python")

        # Run ruff - check entire repo (matches CI)
        print_info("Running ruff on entire repository...")
        subprocess.run(
            [venv_python, "-m", "ruff", "check", "."],
            cwd=repo_root,
            check=True,
        )
        print_success("Ruff checks passed")

        # Run black - check entire repo (matches CI)
        print_info("Running black on entire repository...")
        subprocess.run(
            [venv_python, "-m", "black", "--check", "."],
            cwd=repo_root,
            check=True,
        )
        print_success("Black formatting checks passed")

        # Run mypy - check entire repo with config (matches CI)
        print_info("Running mypy with config file...")
        subprocess.run(
            [venv_python, "-m", "mypy", ".", "--config-file=mypy.ini"],
            cwd=repo_root,
            check=True,
        )
        print_success("Mypy type checks passed")

        return True
    except subprocess.CalledProcessError:
        print_error("Code quality checks failed!")
        return False


def _get_sync_disclaimer(source_rel_path: str, file_ext: str) -> str:
    """Generate disclaimer header for synced files.

    Args:
        source_rel_path: Relative path from repo root (e.g., modems/arris/s34/parser.py)
        file_ext: File extension (.py or .yaml)

    Returns:
        Disclaimer header string with appropriate comment syntax
    """
    if file_ext == ".py" or file_ext in (".yaml", ".yml"):
        return f"""# =============================================================================
# AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY
#
# Source: {source_rel_path}
# This file is synced from modems/ during build. Edit the source file, then run:
#     make sync
# =============================================================================

"""
    return ""


def _create_package_init_files(dest_root: Path) -> None:
    """Create __init__.py files to make directories importable Python packages."""
    init_count = 0
    for dir_path in dest_root.rglob("*"):
        if dir_path.is_dir():
            init_file = dir_path / "__init__.py"
            if not init_file.exists():
                init_file.write_text("", encoding="utf-8")
                init_count += 1
    # Also create one for the root modems directory
    root_init = dest_root / "__init__.py"
    if not root_init.exists():
        root_init.write_text("", encoding="utf-8")
        init_count += 1
    if init_count > 0:
        print_success(f"Created {init_count} __init__.py files")


def sync_modem_configs(repo_root: Path) -> bool:
    """Sync modem.yaml and parser.py files from modems/ to custom_components/.

    This is the deployment bridge: modems/ is the source of truth for developer
    ergonomics (fixtures, tests, modem.yaml, parser.py together), but only
    modem.yaml and parser.py ship to users via custom_components/.

    This keeps deployed integration small (no fixtures/tests) while maintaining
    good developer experience.

    Files are synced with a disclaimer header indicating they are auto-generated
    and should not be edited directly.
    """
    source_root = repo_root / "modems"
    dest_root = repo_root / "custom_components" / "cable_modem_monitor" / "modems"

    if not source_root.exists():
        print_warning("modems/ directory not found, skipping sync")
        return True

    try:
        # Sync both modem.yaml and parser.py files
        files_to_sync = ["modem.yaml", "parser.py"]
        synced_count = 0

        for filename in files_to_sync:
            for file_path in source_root.glob(f"**/{filename}"):
                # Get relative path (e.g., arris/s33/modem.yaml)
                rel_path = file_path.relative_to(source_root)
                dest_path = dest_root / rel_path

                # Create parent directories if needed
                dest_path.parent.mkdir(parents=True, exist_ok=True)

                # Read source content
                source_content = file_path.read_text(encoding="utf-8")

                # Generate disclaimer with source path relative to repo root
                source_rel_to_repo = f"modems/{rel_path}"
                disclaimer = _get_sync_disclaimer(source_rel_to_repo, file_path.suffix)

                # Write with disclaimer prepended
                dest_path.write_text(disclaimer + source_content, encoding="utf-8")
                synced_count += 1

        if synced_count == 0:
            print_warning("No modem.yaml or parser.py files found in modems/")
        else:
            print_success(f"Synced {synced_count} files to custom_components/modems/")

        # Create __init__.py files to make directories importable Python packages
        _create_package_init_files(dest_root)

        # Generate modem index for fast parser lookups
        _generate_modem_index(repo_root)

        return True
    except Exception as e:
        print_error(f"Failed to sync modem configs: {e}")
        return False


def _generate_modem_index(repo_root: Path) -> None:
    """Generate modem index for fast parser lookups.

    The index maps parser class names to modem paths, avoiding
    full directory scans at runtime.
    """
    try:
        import subprocess

        result = subprocess.run(
            [sys.executable, str(repo_root / "scripts" / "generate_modem_index.py")],
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
        if result.returncode != 0:
            print_warning(f"Index generation warning: {result.stderr}")
    except Exception as e:
        print_warning(f"Could not generate modem index: {e}")


def verify_translations(repo_root: Path) -> bool:
    """Verify translations/en.json matches strings.json."""
    try:
        strings_path = repo_root / "custom_components" / "cable_modem_monitor" / "strings.json"
        translations_path = repo_root / "custom_components" / "cable_modem_monitor" / "translations" / "en.json"

        # Read both files
        with open(strings_path, encoding="utf-8") as f:
            strings_content = json.load(f)

        if not translations_path.exists():
            print_warning("translations/en.json not found, creating from strings.json...")
            translations_path.parent.mkdir(parents=True, exist_ok=True)
            with open(translations_path, "w", encoding="utf-8") as f:
                json.dump(strings_content, f, indent=2)
                f.write("\n")
            print_success("Created translations/en.json")
            return True

        with open(translations_path, encoding="utf-8") as f:
            translations_content = json.load(f)

        if strings_content != translations_content:
            print_warning("translations/en.json differs from strings.json, updating...")
            with open(translations_path, "w", encoding="utf-8") as f:
                json.dump(strings_content, f, indent=2)
                f.write("\n")
            print_success("Updated translations/en.json")
        else:
            print_success("translations/en.json matches strings.json")

        return True
    except Exception as e:
        print_error(f"Failed to verify translations: {e}")
        return False


def validate_release_preconditions(version: str, repo_root: Path) -> None:
    """Validate all preconditions for creating a release."""
    # Validate version format
    if not validate_version(version):
        print_error(f"Invalid version format: {version}. Must be X.Y.Z (e.g., 3.5.1)")
        sys.exit(1)

    # Check if pre-commit is installed
    try:
        result = subprocess.run(
            ["git", "config", "--get", "core.hooksPath"],
            capture_output=True,
            text=True,
            check=False,
        )
        hooks_path = result.stdout.strip() or ".git/hooks"
        pre_commit_hook = (
            repo_root / hooks_path / "pre-commit" if not hooks_path.startswith("/") else Path(hooks_path) / "pre-commit"
        )

        if not pre_commit_hook.exists():
            print_warning("Pre-commit hooks not installed!")
            print_warning("This may cause CI failures due to formatting/linting issues.")
            print_warning("Install with: .venv/bin/pre-commit install")
            print_warning("Continuing anyway...")
    except Exception as e:
        print_warning(f"Could not check pre-commit installation: {e}")

    # Check git status
    if not check_git_clean():
        print_error("Git working directory is not clean. Commit or stash changes first.")
        sys.exit(1)

    # Check if version tag already exists
    try:
        result = subprocess.run(
            ["git", "tag", "-l", f"v{version}"],
            capture_output=True,
            text=True,
            check=True,
        )
        if result.stdout.strip():
            print_error(f"Tag v{version} already exists!")
            sys.exit(1)
    except subprocess.CalledProcessError:
        pass


def update_all_files(repo_root: Path, version: str, skip_changelog: bool) -> None:
    """Update all version files."""
    success = True
    success = update_manifest(repo_root, version) and success
    success = update_const_py(repo_root, version) and success
    success = update_version_test(repo_root, version) and success

    if not skip_changelog:
        success = update_changelog(repo_root, version) and success

    if not success:
        print_error("Failed to update all files")
        sys.exit(1)


def verify_version_consistency(repo_root: Path, version: str) -> bool:
    """Verify that all version files have been updated correctly.

    This prevents the CI error where tag version doesn't match manifest.json.
    """
    import json

    print_info("Verifying version consistency across all files...")

    all_correct = True

    # Check manifest.json
    manifest_path = repo_root / "custom_components" / "cable_modem_monitor" / "manifest.json"
    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
            manifest_version = manifest.get("version", "")
            if manifest_version != version:
                print_error(f"manifest.json version mismatch: expected {version}, got {manifest_version}")
                all_correct = False
            else:
                print_success(f"manifest.json version correct: {version}")
    except Exception as e:
        print_error(f"Failed to read manifest.json: {e}")
        all_correct = False

    # Check const.py
    const_path = repo_root / "custom_components" / "cable_modem_monitor" / "const.py"
    try:
        with open(const_path, encoding="utf-8") as f:
            content = f.read()
            if f'VERSION = "{version}"' not in content:
                print_error(f'const.py version mismatch: expected VERSION = "{version}"')
                all_correct = False
            else:
                print_success(f"const.py version correct: {version}")
    except Exception as e:
        print_error(f"Failed to read const.py: {e}")
        all_correct = False

    # Check test file
    test_path = repo_root / "tests" / "components" / "test_version_and_startup.py"
    try:
        with open(test_path, encoding="utf-8") as f:
            content = f.read()
            if f'assert VERSION == "{version}"' not in content:
                print_error(f'test_version_and_startup.py version mismatch: expected VERSION == "{version}"')
                all_correct = False
            else:
                print_success(f"test_version_and_startup.py version correct: {version}")
    except Exception as e:
        print_error(f"Failed to read test_version_and_startup.py: {e}")
        all_correct = False

    if all_correct:
        print_success("All version files are consistent!")
        return True
    else:
        print_error("Version consistency check failed!")
        print_error("This would cause CI to fail with: 'Tag version does not match manifest.json version'")
        return False


def perform_git_operations(version: str, skip_verify: bool, no_push: bool, repo_root: Path) -> None:
    """Perform git commit, tag, push, and release operations."""
    # Create commit
    if not create_commit(version, skip_verify):
        sys.exit(1)

    # Only create tag and push if --no-push is not set
    # With branch protection, use --no-push for PR workflow, then tag manually after merge
    if no_push:
        print_info("Skipping tag creation (--no-push). After PR merges, run:")
        print_info("  git checkout main && git pull")
        print_info(f"  git tag -a v{version} -m 'Release v{version}'")
        print_info(f"  git push origin v{version}")
        return

    # Create tag
    if not create_tag(version):
        sys.exit(1)

    # Push commit and tag
    if not push_changes(version, skip_verify):
        sys.exit(1)

    # Create GitHub release
    if not create_github_release(version, repo_root):
        print_warning("Release created but GitHub release failed")


def _run_release(args: argparse.Namespace, repo_root: Path) -> None:
    """Execute the release workflow steps."""
    version = args.version

    print_info(f"Starting release process for version {version}")
    print_info(f"Repository root: {repo_root}")

    # Validate preconditions
    validate_release_preconditions(version, repo_root)

    # Run tests (unless skipped)
    _run_optional_step(
        not args.skip_tests,
        lambda: run_tests(repo_root),
        skip_msg="Skipping tests (--skip-tests)",
    )

    # Run code quality checks (unless skipped)
    _run_optional_step(
        not args.skip_quality,
        lambda: run_code_quality_checks(repo_root),
        skip_msg="Skipping code quality checks (--skip-quality)",
    )

    # Verify translations and sync configs
    _exit_on_failure(verify_translations(repo_root))
    _exit_on_failure(sync_modem_configs(repo_root))

    # Update all version files
    update_all_files(repo_root, version, args.skip_changelog)

    # Verify version consistency (prevents CI tag/manifest mismatch error)
    _exit_on_failure(verify_version_consistency(repo_root, version))

    # Stage translations if it was updated
    with contextlib.suppress(subprocess.CalledProcessError):
        subprocess.run(
            ["git", "add", "custom_components/cable_modem_monitor/translations/en.json"],
            check=False,
        )

    # Stage synced modem configs
    with contextlib.suppress(subprocess.CalledProcessError):
        subprocess.run(
            ["git", "add", "custom_components/cable_modem_monitor/modems/"],
            check=False,
        )

    # Perform git operations
    perform_git_operations(version, args.skip_verify, args.no_push, repo_root)

    # Success message
    if args.no_push:
        print_success(f"\n🎉 Version {version} prepared! Create PR, then tag after merge.")
    else:
        print_success(f"\n🎉 Release {version} complete!")


def _run_optional_step(should_run: bool, step_fn, skip_msg: str) -> None:
    """Run an optional step or print skip message."""
    if should_run:
        _exit_on_failure(step_fn())
    else:
        print_warning(skip_msg)


def _exit_on_failure(success: bool) -> None:
    """Exit if the step failed."""
    if not success:
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Automate Cable Modem Monitor releases")
    parser.add_argument("version", nargs="?", help="Version to release (e.g., 3.5.1)")
    parser.add_argument(
        "--sync-only",
        action="store_true",
        help="Only sync modem configs and parsers from modems/ to custom_components/, skip release",
    )
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="Don't create tag or push (for PR workflow with branch protection)",
    )
    parser.add_argument(
        "--skip-changelog",
        action="store_true",
        help="Skip updating CHANGELOG.md",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip git hooks (--no-verify)",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip running tests (not recommended)",
    )
    parser.add_argument(
        "--skip-quality",
        action="store_true",
        help="Skip code quality checks (not recommended)",
    )

    args = parser.parse_args()
    repo_root = get_repo_root()

    # Handle --sync-only mode
    if args.sync_only:
        print_info("Running sync-only mode...")
        _exit_on_failure(sync_modem_configs(repo_root))
        print_success("Sync complete!")
        return

    # Regular release mode requires version
    if not args.version:
        parser.error("version is required for release (use --sync-only for sync without release)")

    _run_release(args, repo_root)


if __name__ == "__main__":
    main()
