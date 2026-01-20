#!/usr/bin/env python3
"""
Docker status checker for Linux/macOS.
Verifies Docker is installed and running before executing Docker commands.

Note: Windows users should run this inside WSL2. See docs/setup/WSL2_SETUP.md.
"""

import contextlib
import os
import platform
import shutil
import subprocess
import sys
import time

# Color codes
GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"
NC = "\033[0m"


def supports_unicode():
    """Check if the terminal supports Unicode output."""
    try:
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


def is_running_in_container():
    """Check if we're running inside a Docker container."""
    # Check for .dockerenv file (Linux containers)
    if os.path.exists("/.dockerenv"):
        return True
    # Check for container environment variables
    if os.environ.get("REMOTE_CONTAINERS") or os.environ.get("CODESPACES"):
        return True
    # Check cgroup for docker/container indicators (Linux only)
    try:
        with open("/proc/1/cgroup") as f:
            content = f.read()
            return "docker" in content or "container" in content
    except (FileNotFoundError, PermissionError):
        pass
    return False


def cleanup_stale_docker_files():
    """Remove stale PID and socket files from crashed docker.

    Note: This function uses Linux-specific paths and commands.
    It's only called when running inside a container (always Linux).
    """
    stale_files = [
        "/var/run/docker.pid",
        "/var/run/docker.sock",
        "/var/run/containerd/containerd.pid",
    ]
    for f in stale_files:
        with contextlib.suppress(FileNotFoundError, PermissionError):
            os.remove(f)

    # Kill any zombie docker processes
    subprocess.run(["pkill", "-9", "dockerd"], capture_output=True)
    subprocess.run(["pkill", "-9", "containerd"], capture_output=True)
    time.sleep(1)


def try_start_docker_in_docker():
    """Try to start the Docker daemon inside a container (docker-in-docker).

    Note: This function uses Linux-specific paths and commands.
    It's only called when running inside a container (always Linux).
    """
    print_info("Attempting to start Docker daemon inside container...")
    print("")

    # Clean up stale files from previous crashed docker
    cleanup_stale_docker_files()

    # Common locations for docker-in-docker startup scripts
    startup_commands = [
        # devcontainers docker-in-docker feature uses this
        ["/usr/local/share/docker-init.sh"],
        # Alternative: start dockerd directly
        ["dockerd", "--host=unix:///var/run/docker.sock"],
        # Some setups use service
        ["service", "docker", "start"],
    ]

    for cmd in startup_commands:
        # Check if command exists (which() for PATH, exists() for absolute paths)
        cmd_path = cmd[0]
        if not (shutil.which(cmd_path) or os.path.exists(cmd_path)):
            continue
        try:
            # docker-init.sh and dockerd run forever, so background them
            if cmd_path in ("dockerd", "/usr/local/share/docker-init.sh"):
                subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                # Wait for daemon to start (can take 20-30s on slow systems)
                print("   Waiting for Docker daemon", end="", flush=True)
                for _ in range(30):
                    time.sleep(1)
                    print(".", end="", flush=True)
                    result = subprocess.run(
                        ["docker", "info"],
                        capture_output=True,
                        timeout=5,
                    )
                    if result.returncode == 0:
                        print()
                        return True
                print()
            else:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    # Verify docker is now working
                    check = subprocess.run(
                        ["docker", "info"],
                        capture_output=True,
                        timeout=10,
                    )
                    if check.returncode == 0:
                        return True
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            continue

    return False


def get_docker_install_instructions(system):
    """Get platform-specific Docker installation instructions."""
    if system == "Darwin":
        return [
            "  Download: https://desktop.docker.com/mac/main/amd64/Docker.dmg",
            "",
            "  Or install via Homebrew:",
            f"    {CYAN}brew install --cask docker{NC}",
        ]
    # Linux
    return [
        "  Ubuntu/Debian: sudo apt install docker.io",
        "  Fedora/RHEL: sudo dnf install docker",
        "  Or download Docker Desktop: https://docs.docker.com/desktop/install/linux-install/",
    ]


def _install_docker_macos():
    """Install Docker Desktop on macOS using Homebrew."""
    print("")
    print("Installing Docker Desktop via Homebrew...")
    print("")
    result = subprocess.run(["brew", "install", "--cask", "docker"], check=False)
    if result.returncode == 0:
        print("")
        print(f"{GREEN}{CHECK}{NC} Docker Desktop installed!")
        print(f"{YELLOW}Please start Docker Desktop from Applications.{NC}")
        print("")


def prompt_docker_install(system):
    """Prompt user to install Docker and launch installer if confirmed."""
    if system != "Darwin":
        return False

    print("")
    print(f"{CYAN}Would you like to install Docker Desktop now? (uses Homebrew){NC}")
    print("")
    try:
        response = input("Install Docker Desktop? [y/N]: ").strip().lower()
        if response in ("y", "yes"):
            _install_docker_macos()
            return True
    except (EOFError, KeyboardInterrupt):
        print("")
    except FileNotFoundError:
        print(f"{YELLOW}Homebrew not found. Please install Docker Desktop manually.{NC}")
        print("")
    return False


def get_docker_start_instructions(system):
    """Get platform-specific instructions for starting Docker."""
    if system == "Darwin":
        return [
            "macOS:",
            "  1. Open Applications folder",
            "  2. Launch Docker Desktop",
            "  3. Wait for the Docker whale icon in menu bar to show 'Running'",
        ]
    # Linux
    return [
        "Linux:",
        "  Option 1 (Docker Desktop):",
        "    - Launch Docker Desktop application",
        "  Option 2 (Docker Engine):",
        "    - sudo systemctl start docker",
        "    - Or: sudo service docker start",
    ]


def prompt_start_docker(system):
    """Prompt user to start Docker Desktop automatically."""
    if system == "Darwin":
        print("")
        print(f"{CYAN}Would you like to start Docker Desktop now?{NC}")
        print("")
        try:
            response = input("Start Docker Desktop? [Y/n]: ").strip().lower()
            if response in ("", "y", "yes"):
                print("")
                print("Starting Docker Desktop...")
                subprocess.Popen(
                    ["open", "-a", "Docker"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                print(f"{YELLOW}Docker Desktop is starting. This may take 30-60 seconds.{NC}")
                print("")
                return True
        except (EOFError, KeyboardInterrupt):
            print("")
    return False


def check_docker_installed(system):
    """Check if Docker is installed. Returns True if installed."""
    if shutil.which("docker"):
        return True

    print_error("Docker is not installed")
    print("")
    print("Please install Docker Desktop:")
    print("")
    for line in get_docker_install_instructions(system):
        print(line)

    # Offer to install Docker automatically
    prompt_docker_install(system)
    return False


def check_docker_running(system):
    """Check if Docker daemon is running. Returns 0 if running, 1 otherwise."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            print_success("Docker is running")
            return 0

        # Docker command failed
        raise subprocess.CalledProcessError(result.returncode, "docker info")

    except subprocess.TimeoutExpired:
        print_error("Docker command timed out")
        print("")
        print("Docker may be starting up. Please wait a moment and try again.")
        print("")
        return 1

    except subprocess.CalledProcessError:
        print_error("Docker is not running")
        print("")

        # Different guidance for container vs host environment
        if is_running_in_container():
            # Try to start docker-in-docker daemon
            if try_start_docker_in_docker():
                print_success("Docker daemon started inside container")
                return 0
            print("You're running inside a Dev Container.")
            print("")
            print("The Docker daemon inside the container failed to start.")
            print("Try rebuilding the container:")
            print("")
            print(f"  {CYAN}Ctrl+Shift+P → 'Dev Containers: Rebuild Container'{NC}")
            print("")
        elif not prompt_start_docker(system):
            print("Please start Docker Desktop:")
            print("")
            for line in get_docker_start_instructions(system):
                print(line)
            print("")
            print("Then try your command again.")
            print("")
        return 1

    except FileNotFoundError:
        print_error("Docker command not found in PATH")
        print("")
        return 1


def check_docker():
    """Check if Docker is installed and running.

    Returns 0 if Docker is ready, 1 otherwise.
    """
    system = platform.system()

    # Check if Docker is installed
    if not check_docker_installed(system):
        return 1

    # Check if Docker daemon is running
    return check_docker_running(system)


def main():
    """Main entry point."""
    sys.exit(check_docker())


if __name__ == "__main__":
    main()
