#!/usr/bin/env python3
"""Cross-platform pre-commit validation script.

Works on Linux, macOS, and Windows without requiring a venv.
Auto-installs missing tools (ruff, black) if needed.

Usage:
    python scripts/dev/validate.py              # Run all checks
    python scripts/dev/validate.py --lint       # Lint only
    python scripts/dev/validate.py --format     # Format check only
    python scripts/dev/validate.py --commit-msg "feat: add feature"  # Validate message
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Conventional commit types (must match .github/workflows/commit-lint.yml)
VALID_TYPES = [
    "feat",  # New feature
    "fix",  # Bug fix
    "docs",  # Documentation changes
    "style",  # Code style changes
    "refactor",  # Code refactoring
    "perf",  # Performance improvements
    "test",  # Adding or updating tests
    "build",  # Build system changes
    "ci",  # CI/CD changes
    "chore",  # Other changes
    "revert",  # Revert a previous commit
    "deps",  # Dependency updates
]

# Conventional commit regex: type(optional-scope): description
COMMIT_PATTERN = re.compile(r"^(" + "|".join(VALID_TYPES) + r")(\([a-zA-Z0-9_-]+\))?: .+$")


def run_command(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def tool_exists(name: str) -> bool:
    """Check if a tool is available via python -m."""
    try:
        result = run_command([sys.executable, "-m", name, "--version"], check=False)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def install_tool(package: str) -> bool:
    """Install a Python package using pip."""
    print(f"  Installing {package}...")
    try:
        result = run_command(
            [sys.executable, "-m", "pip", "install", package, "--quiet"],
            check=False,
        )
        return result.returncode == 0
    except Exception as e:
        print(f"  Failed to install {package}: {e}")
        return False


def ensure_tool(name: str, package: str | None = None) -> bool:
    """Ensure a tool is available, installing if necessary."""
    if tool_exists(name):
        return True

    pkg = package or name
    print(f"⚠️  {name} not found, installing...")

    if install_tool(pkg):
        # Verify installation worked
        if tool_exists(name):
            print(f"  ✓ {name} installed successfully")
            return True
        else:
            # Tool installed but not in PATH - try running via python -m
            print(f"  ✓ {name} installed (will use via python -m)")
            return True

    print(f"  ✗ Failed to install {name}")
    return False


def run_tool(name: str, args: list[str]) -> tuple[int, str, str]:
    """Run a tool via python -m (most reliable cross-platform)."""
    # Always prefer python -m to avoid PATH/shim issues
    result = run_command([sys.executable, "-m", name] + args, check=False)
    return result.returncode, result.stdout, result.stderr


def check_lint() -> bool:
    """Run ruff linter."""
    print("🔍 Running ruff linter...")

    if not ensure_tool("ruff"):
        return False

    returncode, stdout, stderr = run_tool("ruff", ["check", "."])

    if returncode != 0:
        print(stderr or stdout)
        print("  ✗ Linting failed")
        return False

    print("  ✓ Linting passed")
    return True


def check_format() -> bool:
    """Check black formatting."""
    print("🎨 Checking code formatting (black)...")

    if not ensure_tool("black"):
        return False

    returncode, stdout, stderr = run_tool("black", ["--check", "."])

    if returncode != 0:
        print(stderr or stdout)
        print("  ✗ Formatting check failed")
        print("  Run 'black .' to fix formatting")
        return False

    print("  ✓ Formatting check passed")
    return True


def check_commit_message(message: str) -> bool:
    """Validate commit message follows conventional commits format."""
    print("📝 Checking commit message format...")

    # Get first line (subject)
    subject = message.split("\n")[0].strip()

    if not subject:
        print("  ✗ Commit message is empty")
        return False

    if COMMIT_PATTERN.match(subject):
        print("  ✓ Commit message format is valid")
        return True

    print(f"  ✗ Invalid commit message: {subject}")
    print("")
    print("  Expected format: <type>(<scope>): <description>")
    print(f"  Valid types: {', '.join(VALID_TYPES)}")
    print("")
    print("  Examples:")
    print("    feat: add support for new modem")
    print("    fix(parser): resolve timeout issue")
    print("    docs: update installation guide")
    return False


def get_staged_commit_message() -> str | None:
    """Get the commit message from git (for commit-msg hook)."""
    # Check if we're in a git repo
    try:
        result = run_command(["git", "rev-parse", "--git-dir"], check=False)
        if result.returncode != 0:
            return None

        # Try to read .git/COMMIT_EDITMSG
        git_dir = Path(result.stdout.strip())
        commit_msg_file = git_dir / "COMMIT_EDITMSG"

        if commit_msg_file.exists():
            return commit_msg_file.read_text()
    except Exception:
        pass

    return None


def main() -> int:
    """Run validation checks."""
    parser = argparse.ArgumentParser(description="Pre-commit validation")
    parser.add_argument("--lint", action="store_true", help="Run lint check only")
    parser.add_argument("--format", action="store_true", help="Run format check only")
    parser.add_argument("--commit-msg", type=str, help="Validate commit message")
    parser.add_argument("--commit-msg-file", type=str, help="Read commit message from file")
    args = parser.parse_args()

    # Determine which checks to run
    run_all = not (args.lint or args.format or args.commit_msg or args.commit_msg_file)

    results = []

    # Lint check
    if run_all or args.lint:
        results.append(("Lint", check_lint()))

    # Format check
    if run_all or args.format:
        results.append(("Format", check_format()))

    # Commit message check
    if args.commit_msg:
        results.append(("Commit Message", check_commit_message(args.commit_msg)))
    elif args.commit_msg_file:
        msg = Path(args.commit_msg_file).read_text()
        results.append(("Commit Message", check_commit_message(msg)))

    # Summary
    print("")
    failed = [name for name, passed in results if not passed]

    if failed:
        print(f"❌ Validation failed: {', '.join(failed)}")
        return 1

    print("✅ All checks passed - ready to commit!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
