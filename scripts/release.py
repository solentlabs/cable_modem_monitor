***REMOVED***!/usr/bin/env python3
"""Release automation script for Cable Modem Monitor.

This script automates the complete release process by:
1. Validating the version format
2. Checking git working directory is clean
3. Running tests (pytest)
4. Running code quality checks (ruff, black, mypy)
5. Verifying translations/en.json matches strings.json
6. Updating version in all required files:
   - custom_components/cable_modem_monitor/manifest.json
   - custom_components/cable_modem_monitor/const.py
   - tests/components/test_version_and_startup.py
7. Updating CHANGELOG.md
8. Creating a git commit with all changes
9. Creating an annotated git tag
10. Pushing to remote (optional)
11. Creating a GitHub release (optional)

Usage:
    python scripts/release.py 3.5.2                    ***REMOVED*** Full release
    python scripts/release.py 3.5.2 --no-push          ***REMOVED*** Test locally without pushing
    python scripts/release.py 3.5.2 --skip-tests       ***REMOVED*** Skip tests (not recommended)
    python scripts/release.py 3.5.2 --skip-quality     ***REMOVED*** Skip code quality checks
    python scripts/release.py 3.5.2 --skip-changelog   ***REMOVED*** Don't update changelog
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
            f.write("\n")  ***REMOVED*** Add trailing newline

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

        ***REMOVED*** Find the current version
        version_match = re.search(r'VERSION = "([^"]+)"', content)
        if not version_match:
            print_error("Could not find VERSION constant in const.py")
            return False

        old_version = version_match.group(1)

        ***REMOVED*** Replace the version
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

        ***REMOVED*** Find the current version in the test
        version_match = re.search(r'assert VERSION == "([^"]+)"', content)
        if not version_match:
            print_error("Could not find version assertion in test file")
            return False

        old_version = version_match.group(1)

        ***REMOVED*** Replace the version
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

        ***REMOVED*** Check if there's an Unreleased section
        if "***REMOVED******REMOVED*** [Unreleased]" not in content:
            print_warning("No [Unreleased] section found in CHANGELOG.md")
            return True

        ***REMOVED*** Get today's date
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")

        ***REMOVED*** Replace ***REMOVED******REMOVED*** [Unreleased] with ***REMOVED******REMOVED*** [version] - date and add new [Unreleased]
        new_content = content.replace(
            "***REMOVED******REMOVED*** [Unreleased]",
            f"***REMOVED******REMOVED*** [Unreleased]\n\n***REMOVED******REMOVED*** [{version}] - {today}",
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
        ***REMOVED*** Stage the files
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

        ***REMOVED*** Create commit
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

        ***REMOVED*** Push commit
        cmd = ["git", "push", "origin", "main"]
        if skip_verify:
            cmd.append("--no-verify")

        subprocess.run(cmd, check=True)
        print_success("Pushed commit to origin/main")

        ***REMOVED*** Push tag
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

        ***REMOVED*** Extract release notes from CHANGELOG
        changelog_path = repo_root / "CHANGELOG.md"
        with open(changelog_path, encoding="utf-8") as f:
            content = f.read()

        ***REMOVED*** Find the section for this version
        version_pattern = rf"***REMOVED******REMOVED*** \[{re.escape(version)}\][^\n]*\n(.*?)(?=***REMOVED******REMOVED*** \[|$)"
        match = re.search(version_pattern, content, re.DOTALL)

        if match:
            release_notes = match.group(1).strip()
        else:
            release_notes = f"Release version {version}"

        ***REMOVED*** Create release
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

        ***REMOVED*** Run ruff - check entire repo (matches CI)
        print_info("Running ruff on entire repository...")
        subprocess.run(
            [venv_python, "-m", "ruff", "check", "."],
            cwd=repo_root,
            check=True,
        )
        print_success("Ruff checks passed")

        ***REMOVED*** Run black - check entire repo (matches CI)
        print_info("Running black on entire repository...")
        subprocess.run(
            [venv_python, "-m", "black", "--check", "."],
            cwd=repo_root,
            check=True,
        )
        print_success("Black formatting checks passed")

        ***REMOVED*** Run mypy - check entire repo with config (matches CI)
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


def verify_translations(repo_root: Path) -> bool:
    """Verify translations/en.json matches strings.json."""
    try:
        strings_path = repo_root / "custom_components" / "cable_modem_monitor" / "strings.json"
        translations_path = repo_root / "custom_components" / "cable_modem_monitor" / "translations" / "en.json"

        ***REMOVED*** Read both files
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
    ***REMOVED*** Validate version format
    if not validate_version(version):
        print_error(f"Invalid version format: {version}. Must be X.Y.Z (e.g., 3.5.1)")
        sys.exit(1)

    ***REMOVED*** Check git status
    if not check_git_clean():
        print_error("Git working directory is not clean. Commit or stash changes first.")
        sys.exit(1)

    ***REMOVED*** Check if version tag already exists
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

    ***REMOVED*** Check manifest.json
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

    ***REMOVED*** Check const.py
    const_path = repo_root / "custom_components" / "cable_modem_monitor" / "const.py"
    try:
        with open(const_path, encoding="utf-8") as f:
            content = f.read()
            if f'VERSION = "{version}"' not in content:
                print_error(f"const.py version mismatch: expected VERSION = \"{version}\"")
                all_correct = False
            else:
                print_success(f"const.py version correct: {version}")
    except Exception as e:
        print_error(f"Failed to read const.py: {e}")
        all_correct = False

    ***REMOVED*** Check test file
    test_path = repo_root / "tests" / "components" / "test_version_and_startup.py"
    try:
        with open(test_path, encoding="utf-8") as f:
            content = f.read()
            if f'assert VERSION == "{version}"' not in content:
                print_error(f"test_version_and_startup.py version mismatch: expected VERSION == \"{version}\"")
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
    ***REMOVED*** Create commit
    if not create_commit(version, skip_verify):
        sys.exit(1)

    ***REMOVED*** Create tag
    if not create_tag(version):
        sys.exit(1)

    ***REMOVED*** Push if requested
    if not no_push:
        if not push_changes(version, skip_verify):
            sys.exit(1)

        ***REMOVED*** Create GitHub release
        if not create_github_release(version, repo_root):
            print_warning("Release created but GitHub release failed")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Automate Cable Modem Monitor releases")
    parser.add_argument("version", help="Version to release (e.g., 3.5.1)")
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="Don't push to remote (for testing)",
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
    version = args.version

    print_info(f"Starting release process for version {version}")

    ***REMOVED*** Get repository root
    repo_root = get_repo_root()
    print_info(f"Repository root: {repo_root}")

    ***REMOVED*** Validate preconditions
    validate_release_preconditions(version, repo_root)

    ***REMOVED*** Run tests
    if not args.skip_tests:
        if not run_tests(repo_root):
            sys.exit(1)
    else:
        print_warning("Skipping tests (--skip-tests)")

    ***REMOVED*** Run code quality checks
    if not args.skip_quality:
        if not run_code_quality_checks(repo_root):
            sys.exit(1)
    else:
        print_warning("Skipping code quality checks (--skip-quality)")

    ***REMOVED*** Verify translations
    if not verify_translations(repo_root):
        sys.exit(1)

    ***REMOVED*** Update all version files
    update_all_files(repo_root, version, args.skip_changelog)

    ***REMOVED*** Verify version consistency (prevents CI tag/manifest mismatch error)
    if not verify_version_consistency(repo_root, version):
        sys.exit(1)

    ***REMOVED*** Stage translations if it was updated
    with contextlib.suppress(subprocess.CalledProcessError):
        subprocess.run(
            ["git", "add", "custom_components/cable_modem_monitor/translations/en.json"],
            check=False,  ***REMOVED*** Don't fail if file doesn't exist
        )

    ***REMOVED*** Perform git operations
    perform_git_operations(version, args.skip_verify, args.no_push, repo_root)

    ***REMOVED*** Success message
    print_success(f"\n🎉 Release {version} complete!")

    if args.no_push:
        print_info("\nChanges not pushed (--no-push). To push:")
        print_info("  git push origin main")
        print_info(f"  git push origin v{version}")
        print_info(f"  gh release create v{version}")


if __name__ == "__main__":
    main()
