#!/usr/bin/env python3
"""
Cross-platform Docker status checker.
Verifies Docker is installed and running before executing Docker commands.
"""

import platform
import shutil
import subprocess
import sys

# Color codes
GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"
NC = "\033[0m"


# Check if terminal supports Unicode (use ASCII fallback for Windows)
def supports_unicode():
    """Check if the terminal supports Unicode output."""
    try:
        # Try to encode a checkmark - if it fails, we don't have Unicode support
        "\u2713".encode(sys.stdout.encoding or "utf-8")
        return True
    except (UnicodeEncodeError, AttributeError):
        return False


USE_UNICODE = supports_unicode()
CHECK = "\u2713" if USE_UNICODE else "OK"
CROSS = "\u2717" if USE_UNICODE else "X"
INFO = "\u2139" if USE_UNICODE else "i"


def print_error(message):
    """Print error message in red."""
    print(f"{RED}{CROSS}{NC} {message}", file=sys.stderr)


def print_success(message):
    """Print success message in green."""
    print(f"{GREEN}{CHECK}{NC} {message}")


def print_info(message):
    """Print info message in cyan."""
    print(f"{CYAN}{INFO}{NC} {message}")


def get_platform_instructions():
    """Get platform-specific instructions for starting Docker."""
    system = platform.system()

    if system == "Windows":
        return [
            "Windows:",
            "  1. Open Start Menu",
            "  2. Search for 'Docker Desktop'",
            "  3. Launch Docker Desktop",
            "  4. Wait for the Docker icon in system tray to stop animating",
        ]
    elif system == "Darwin":  # macOS
        return [
            "macOS:",
            "  1. Open Applications folder",
            "  2. Launch Docker Desktop",
            "  3. Wait for the Docker whale icon in menu bar to show 'Running'",
        ]
    else:  # Linux and others
        return [
            "Linux:",
            "  Option 1 (Docker Desktop):",
            "    - Launch Docker Desktop application",
            "  Option 2 (Docker Engine):",
            "    - sudo systemctl start docker",
            "    - Or: sudo service docker start",
        ]


def check_docker():
    """
    Check if Docker is installed and running.
    Returns 0 if Docker is ready, 1 otherwise.
    """
    # Check if Docker is installed
    if not shutil.which("docker"):
        print_error("Docker is not installed")
        print("")
        print("Please install Docker:")
        system = platform.system()
        if system == "Windows":
            print("  Download: https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe")
        elif system == "Darwin":
            print("  Download: https://desktop.docker.com/mac/main/amd64/Docker.dmg")
        else:
            print("  Ubuntu/Debian: sudo apt install docker.io")
            print("  Fedora/RHEL: sudo dnf install docker")
            print("  Or download Docker Desktop: https://docs.docker.com/desktop/install/linux-install/")
        print("")
        return 1

    # Check if Docker daemon is running
    try:
        # Run 'docker info' to check if daemon is accessible
        subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=10,
        )
        print_success("Docker is running")
        return 0

    except subprocess.TimeoutExpired:
        print_error("Docker command timed out")
        print("")
        print("Docker may be starting up. Please wait a moment and try again.")
        print("")
        return 1

    except subprocess.CalledProcessError:
        print_error("Docker is not running")
        print("")
        print("Please start Docker Desktop:")
        print("")
        for line in get_platform_instructions():
            print(f"  {line}")
        print("")
        print("Then try your command again.")
        print("")
        return 1

    except FileNotFoundError:
        # This shouldn't happen since we checked with shutil.which, but just in case
        print_error("Docker command not found in PATH")
        print("")
        return 1


def main():
    """Main entry point."""
    sys.exit(check_docker())


if __name__ == "__main__":
    main()
