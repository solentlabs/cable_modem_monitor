***REMOVED***!/usr/bin/env python3
"""Release automation script for Cable Modem Monitor.

This script automates the release process by:
1. Validating the version format
2. Updating version in all required files:
   - custom_components/cable_modem_monitor/manifest.json
   - custom_components/cable_modem_monitor/const.py
   - tests/components/test_version_and_startup.py
3. Updating CHANGELOG.md
4. Creating a git commit
5. Creating an annotated git tag
6. Pushing to remote
7. Creating a GitHub release

Usage:
    python scripts/release.py 3.5.1
    python scripts/release.py 3.5.1 --no-push  ***REMOVED*** Don't push to remote
    python scripts/release.py 3.5.1 --skip-changelog  ***REMOVED*** Don't update changelog
"""

from __future__ import annotations

import argparse
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
    manifest_path = (
        repo_root / "custom_components" / "cable_modem_monitor" / "manifest.json"
    )

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        old_version = manifest.get("version", "unknown")
        manifest["version"] = version

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
            f.write("\n")  ***REMOVED*** Add trailing newline

        print_success(
            f"Updated manifest.json: {old_version} → {version}"
        )
        return True
    except Exception as e:
        print_error(f"Failed to update manifest.json: {e}")
        return False


def update_const_py(repo_root: Path, version: str) -> bool:
    """Update VERSION constant in const.py."""
    const_path = (
        repo_root / "custom_components" / "cable_modem_monitor" / "const.py"
    )

    try:
        with open(const_path, "r", encoding="utf-8") as f:
            content = f.read()

        ***REMOVED*** Find the current version
        version_match = re.search(r'VERSION = "([^"]+)"', content)
        if not version_match:
            print_error("Could not find VERSION constant in const.py")
            return False

        old_version = version_match.group(1)

        ***REMOVED*** Replace the version
        new_content = re.sub(
            r'VERSION = "[^"]+"', f'VERSION = "{version}"', content, count=1
        )

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
        with open(test_path, "r", encoding="utf-8") as f:
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

        print_success(
            f"Updated test_version_and_startup.py: {old_version} → {version}"
        )
        return True
    except Exception as e:
        print_error(f"Failed to update version test: {e}")
        return False


def update_changelog(repo_root: Path, version: str) -> bool:
    """Update CHANGELOG.md to move Unreleased to new version."""
    changelog_path = repo_root / "CHANGELOG.md"

    try:
        with open(changelog_path, "r", encoding="utf-8") as f:
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

        subprocess.run(
            ["git", "tag", "-a", tag_name, "-m", tag_msg], check=True
        )

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
        with open(changelog_path, "r", encoding="utf-8") as f:
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


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Automate Cable Modem Monitor releases"
    )
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

    args = parser.parse_args()
    version = args.version

    print_info(f"Starting release process for version {version}")

    ***REMOVED*** Validate version format
    if not validate_version(version):
        print_error(
            f"Invalid version format: {version}. Must be X.Y.Z (e.g., 3.5.1)"
        )
        sys.exit(1)

    ***REMOVED*** Get repository root
    repo_root = get_repo_root()
    print_info(f"Repository root: {repo_root}")

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

    ***REMOVED*** Update files
    success = True
    success = update_manifest(repo_root, version) and success
    success = update_const_py(repo_root, version) and success
    success = update_version_test(repo_root, version) and success

    if not args.skip_changelog:
        success = update_changelog(repo_root, version) and success

    if not success:
        print_error("Failed to update all files")
        sys.exit(1)

    ***REMOVED*** Create commit
    if not create_commit(version, args.skip_verify):
        sys.exit(1)

    ***REMOVED*** Create tag
    if not create_tag(version):
        sys.exit(1)

    ***REMOVED*** Push if requested
    if not args.no_push:
        if not push_changes(version, args.skip_verify):
            sys.exit(1)

        ***REMOVED*** Create GitHub release
        if not create_github_release(version, repo_root):
            print_warning("Release created but GitHub release failed")

    print_success(f"\n🎉 Release {version} complete!")

    if args.no_push:
        print_info("\nChanges not pushed (--no-push). To push:")
        print_info(f"  git push origin main")
        print_info(f"  git push origin v{version}")
        print_info(f"  gh release create v{version}")


if __name__ == "__main__":
    main()
