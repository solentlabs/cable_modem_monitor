***REMOVED***!/usr/bin/env python3
***REMOVED*** Cable Modem Monitor - Automated Development Environment Setup (Python)
***REMOVED*** This script consolidates the setup logic for all platforms.

import os
import platform
import shutil
import subprocess
import sys

***REMOVED*** ========================================
***REMOVED*** Color Codes
***REMOVED*** ========================================
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
CYAN = "\033[0;36m"
NC = "\033[0m"


***REMOVED*** ========================================
***REMOVED*** Helper Functions
***REMOVED*** ========================================
def print_step(message):
    print(f"{CYAN}➜{NC} {message}")


def print_success(message):
    print(f"{GREEN}✓{NC} {message}")


def print_error(message):
    print(f"{RED}✗{NC} {message}", file=sys.stderr)


def print_warning(message):
    print(f"{YELLOW}⚠{NC} {message}")


def run_command(command, quiet=False):
    """Runs a command and returns its output."""
    try:
        process = subprocess.run(
            command,
            shell=True,
            check=True,
            capture_output=True,
            text=True,
        )
        if not quiet:
            print(process.stdout)
        return process.stdout.strip()
    except subprocess.CalledProcessError as e:
        if not quiet:
            print_error(f"Command failed: {command}")
            print(e.stderr, file=sys.stderr)
        raise


def is_privacy_safe_email(email: str) -> bool:
    """Check if an email is a privacy-safe (noreply) address."""
    if not email:
        return False
    email = email.lower()
    return (
        email.endswith("@users.noreply.github.com") or email == "noreply@anthropic.com" or email == "noreply@github.com"
    )


def configure_git_email_privacy():
    """Check and configure git email for privacy protection."""
    try:
        current_email = run_command("git config user.email", quiet=True)
    except Exception:
        current_email = ""

    if is_privacy_safe_email(current_email):
        print_success(f"Git email is privacy-safe: {current_email}")
        return

    if current_email:
        print_warning(f"Personal email detected: {current_email}")
    else:
        print_warning("No git email configured")

    print("")
    print("  To protect your privacy, this project recommends using GitHub's noreply email.")
    print("  Personal emails in git history are permanently public.")
    print("")
    print("  Setup instructions:")
    print("    1. Go to: https://github.com/settings/emails")
    print("    2. Check 'Keep my email addresses private'")
    print("    3. Copy your noreply email (e.g., 12345+user@users.noreply.github.com)")
    print("")

    ***REMOVED*** Try to prompt for email (works in interactive terminals)
    try:
        new_email = input("  Paste your GitHub noreply email (or press Enter to skip): ").strip()
        if new_email:
            if is_privacy_safe_email(new_email):
                run_command(f'git config user.email "{new_email}"', quiet=True)
                print_success(f"Git email configured: {new_email}")
            else:
                print_warning("That doesn't look like a noreply email, skipping")
                print("  You can configure it later with: ./scripts/dev/setup-git-email.sh")
        else:
            print_warning("Skipped - you can configure later with: ./scripts/dev/setup-git-email.sh")
    except (EOFError, KeyboardInterrupt):
        ***REMOVED*** Non-interactive mode (CI, piped input, etc.)
        print_warning("Non-interactive mode - configure later with: ./scripts/dev/setup-git-email.sh")


***REMOVED*** ========================================
***REMOVED*** Main Setup Logic
***REMOVED*** ========================================
def main():  ***REMOVED*** noqa: C901
    print("")
    print("==========================================")
    print("Cable Modem Monitor - Development Setup")
    print("==========================================")
    print("")

    ***REMOVED*** 1. Check if in project root
    print_step("Checking if in project root directory...")
    if not os.path.exists("custom_components/cable_modem_monitor/__init__.py"):
        print_error("Not in project root directory")
        print("\nPlease run this script from the cable_modem_monitor/ directory:")
        print("  cd /path/to/cable_modem_monitor")
        print("  python3 scripts/setup.py\n")
        sys.exit(1)
    print_success("Running from project root")
    print("")

    ***REMOVED*** 2. Check Python version
    print_step("Checking Python version...")
    major, minor = sys.version_info[:2]
    if major == 3 and minor >= 11:
        print_success(f"Python {major}.{minor} found (requirement: 3.11+)")
    else:
        print_error(f"Python {major}.{minor} found, but 3.11+ required")
        print("Please install Python 3.11 or newer")
        sys.exit(1)
    print("")

    ***REMOVED*** 3. Check for venv module
    print_step("Checking for venv module...")
    import importlib.util

    if importlib.util.find_spec("venv") is not None:
        print_success("venv module available")
    else:
        print_error("venv module not installed")
        print("\nInstall it with:")
        print(f"  Linux/macOS: sudo apt install python{major}.{minor}-venv")
        print("  Windows: venv is included with Python\n")
        sys.exit(1)
    print("")

    ***REMOVED*** 4. Clean up old venv
    if os.path.isdir("venv"):
        print_warning("Found venv/ directory, removing it in favor of .venv/")
        shutil.rmtree("venv")
        print_success("Removed venv/ directory")
        print("")

    ***REMOVED*** 5. Create virtual environment
    is_windows = platform.system() == "Windows"
    pip_cmd = os.path.join(".venv", "Scripts", "pip.exe") if is_windows else os.path.join(".venv", "bin", "pip")
    precommit_cmd = (
        os.path.join(".venv", "Scripts", "pre-commit.exe") if is_windows else os.path.join(".venv", "bin", "pre-commit")
    )
    python_cmd = (
        os.path.join(".venv", "Scripts", "python.exe") if is_windows else os.path.join(".venv", "bin", "python")
    )

    print_step("Creating virtual environment...")
    if os.path.exists(".venv") and os.path.exists(pip_cmd):
        print_success("Virtual environment already exists")
    elif os.path.exists(".venv"):
        print_warning("Virtual environment is incomplete, recreating...")
        try:
            shutil.rmtree(".venv")
            print_success("Removed incomplete venv")
        except OSError:
            print_error("Cannot remove .venv (files are locked)")
            print("")
            print("This happens when VS Code or another process is using the venv.")
            print("")
            print("Solutions:")
            if is_windows:
                print("  1. Close ALL VS Code windows")
                print("  2. Open PowerShell/Command Prompt (NOT VS Code)")
                print("  3. Run: Remove-Item -Recurse -Force .venv")
                print("  4. Run this setup again")
            else:
                print("  1. Close VS Code")
                print("  2. Run: rm -rf .venv")
                print("  3. Run this setup again")
            print("")
            sys.exit(1)
        run_command(f"{sys.executable} -m venv .venv")
        print_success("Virtual environment created")
    else:
        run_command(f"{sys.executable} -m venv .venv")
        print_success("Virtual environment created")
    print("")

    ***REMOVED*** 6. Upgrade pip
    print_step("Upgrading pip...")
    try:
        run_command(f"{pip_cmd} install --upgrade pip", quiet=True)
        print_success("pip ready")
    except Exception:
        print_warning("pip upgrade skipped (will work next run)")
    print("")

    ***REMOVED*** 7. Install dependencies
    print_step("Installing development dependencies...")
    print("  (This may take a few minutes...)")
    if os.path.exists("requirements-dev.txt"):
        run_command(f"{pip_cmd} install --quiet -r requirements-dev.txt")
        print_success("Development dependencies installed from requirements-dev.txt")
    else:
        print_warning("requirements-dev.txt not found, using fallback installation")
        ***REMOVED*** Install packages manually (less ideal)
        packages = [
            "homeassistant>=2024.1.0",
            "beautifulsoup4",
            "lxml",
            "pytest",
            "pytest-cov",
            "pytest-asyncio",
            "pytest-mock",
            "pytest-homeassistant-custom-component",
            "ruff",
            "black",
            "pre-commit",
            "pylint",
            "mypy",
            "types-requests",
            "bandit",
            "defusedxml",
            "freezegun",
            "responses",
            "pytest-socket",
        ]
        run_command(f"{pip_cmd} install --quiet {' '.join(packages)}")
        run_command(f"{pip_cmd} install --quiet --upgrade requests aiohttp")
        print_success("Development dependencies installed")
    print("")

    ***REMOVED*** 8. Install pre-commit hooks
    print_step("Setting up pre-commit hooks...")
    try:
        run_command(f"{pip_cmd} show pre-commit", quiet=True)
        run_command(f"{precommit_cmd} install --install-hooks", quiet=True)
        print_success("Pre-commit hooks installed")
    except Exception:
        print_warning("Pre-commit not installed (optional)")
    print("")

    ***REMOVED*** 9. Check Docker
    print_step("Checking Docker...")
    if shutil.which("docker"):
        try:
            docker_version = run_command("docker --version", quiet=True).split(" ")[2].strip(",")
            run_command("docker ps", quiet=True)
            print_success(f"Docker {docker_version} is running")
        except Exception:
            print_warning("Docker installed but not running")
            print("  Start Docker Desktop to use dev containers")
    else:
        print_warning("Docker not installed")
        print("  Optional: Install Docker Desktop for containerized development")
    print("")

    ***REMOVED*** 10. Configure git email privacy
    print_step("Checking git email privacy...")
    configure_git_email_privacy()
    print("")

    ***REMOVED*** 11. Check VS Code extensions (renumbered from 10)
    print_step("Checking VS Code...")
    if shutil.which("code"):
        try:
            code_version = run_command("code --version", quiet=True).splitlines()[0]
            print_success(f"VS Code {code_version} installed")

            ***REMOVED*** Check for required extensions
            extensions = run_command("code --list-extensions", quiet=True)
            required_extensions = {
                "ms-python.python": "Python extension",
                "ms-vscode-remote.remote-containers": "Dev Containers extension",
            }

            missing_extensions = []
            for ext_id, _ext_name in required_extensions.items():
                if ext_id not in extensions:
                    missing_extensions.append(ext_id)

            if missing_extensions:
                print_warning("Some recommended VS Code extensions are missing:")
                for ext in missing_extensions:
                    print(f"    - {ext}")
                print("")
                print("  Install them with:")
                for ext in missing_extensions:
                    print(f"    code --install-extension {ext}")
            else:
                print_success("All recommended VS Code extensions installed")
        except Exception:
            print_warning("Could not check VS Code extensions")
    else:
        print_warning("VS Code not installed")
        print("  Optional: Install VS Code for better development experience")
    print("")

    ***REMOVED*** 12. Run a quick test
    print_step("Running quick test to verify setup...")
    try:
        run_command(f"{python_cmd} -m pytest tests/parsers/netgear/test_cm600.py::test_fixtures_exist -q", quiet=True)
        print_success("Tests can run successfully")
    except Exception:
        print_warning("Test execution had issues (may need additional setup)")
    print("")

    ***REMOVED*** 13. Create .python-version file
    if not os.path.exists(".python-version"):
        print_step("Creating .python-version file...")
        with open(".python-version", "w") as f:
            f.write("3.11.0\n")
        print_success("Created .python-version file")
        print("")

    ***REMOVED*** Final message
    print("==========================================")
    print("Setup Complete!")
    print("==========================================")
    print("")
    print(f"{GREEN}✓ Your development environment is ready!{NC}")
    print("")
    print("What's installed:")
    print("  • Python virtual environment (.venv/)")
    print("  • All development dependencies")
    print("  • Pre-commit hooks (including email privacy check)")
    print("  • Code formatters and linters")
    print("  • Git email privacy protection")
    print("")
    print("Next steps:")
    print("")
    print(f"  {CYAN}1. Run tests:{NC}")
    print("     make test")
    print("     ***REMOVED*** or: .venv/bin/pytest tests/")
    print("")
    print(f"  {CYAN}2. Run code quality checks:{NC}")
    print("     make lint")
    print("     make format")
    print("")
    print(f"  {CYAN}3. Start Docker development environment:{NC}")
    print("     make docker-start")
    print("     ***REMOVED*** Then open http://localhost:8123")
    print("")
    print(f"  {CYAN}4. Open in VS Code:{NC}")
    print("     code .")
    print("     ***REMOVED*** Press F1 → 'Dev Containers: Reopen in Container'")
    print("")
    print(f"  {CYAN}5. Verify your setup:{NC}")
    print("     ./scripts/verify-setup.sh")
    print("")
    print("Documentation:")
    print("  • Quick Start:  docs/DEVELOPER_QUICKSTART.md")
    print("  • Contributing: CONTRIBUTING.md")
    print("  • Architecture: docs/ARCHITECTURE_ROADMAP.md")
    print("")
    print("Happy coding! 🚀")
    print("")


if __name__ == "__main__":
    main()
