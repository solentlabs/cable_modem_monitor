#!/usr/bin/env python3
"""
Sync modem configs and reload Home Assistant.

This script:
1. Syncs modem configs from modems/ to custom_components/
2. Regenerates modem index (index.yaml)
3. Regenerates fixture index (modems/README.md)
4. Restarts the HA container
5. Waits for HA to be ready
6. Verifies the integration is mounted

Usage:
    python scripts/dev/ha-reload.py
"""

import socket
import subprocess
import sys
import time
from pathlib import Path

# Color codes
GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
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
SYNC = "\U0001f504" if USE_UNICODE else "~"

CONTAINER_NAME = "ha-cable-modem-test"
HA_PORT = 8123


def print_header(message: str):
    """Print a header line."""
    print(f"\n{BLUE}{'━' * 60}{NC}")
    print(f"{BLUE}  {message}{NC}")
    print(f"{BLUE}{'━' * 60}{NC}\n")


def print_success_header(message: str):
    """Print a success header."""
    print(f"\n{GREEN}{'━' * 60}{NC}")
    print(f"{GREEN}  {CHECK} {message}{NC}")
    print(f"{GREEN}{'━' * 60}{NC}\n")


def print_error_header(message: str):
    """Print an error header."""
    print(f"\n{RED}{'━' * 60}{NC}")
    print(f"{RED}  {CROSS} {message}{NC}")
    print(f"{RED}{'━' * 60}{NC}\n")


def print_step(num: int, total: int, message: str):
    """Print a step indicator."""
    print(f"{YELLOW}Step {num}/{total}:{NC} {message}")


def print_success(message: str):
    """Print success message."""
    print(f"   {GREEN}{CHECK}{NC} {message}")


def print_error(message: str):
    """Print error message."""
    print(f"   {RED}{CROSS}{NC} {message}")


def print_info(message: str):
    """Print info message."""
    print(f"   {message}")


def get_project_dir() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


def is_container_running() -> bool:
    """Check if the HA container is running."""
    try:
        result = subprocess.run(
            ["docker", "inspect", CONTAINER_NAME, "--format", "{{.State.Running}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0 and result.stdout.strip().lower() == "true"
    except subprocess.SubprocessError:
        return False


def wait_for_http(port: int, timeout: int = 60) -> bool:
    """Wait for HTTP to respond on the given port."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                s.connect(("localhost", port))
                s.send(b"GET / HTTP/1.0\r\n\r\n")
                response = s.recv(100)
                if b"HTTP" in response:
                    return True
        except (TimeoutError, OSError):
            pass
        time.sleep(1)
        print(".", end="", flush=True)
    return False


def check_integration_mounted() -> bool:
    """Check if the cable modem integration is mounted in the container."""
    try:
        result = subprocess.run(
            ["docker", "exec", CONTAINER_NAME, "ls", "/config/custom_components/cable_modem_monitor/__init__.py"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except subprocess.SubprocessError:
        return False


def main() -> int:
    print_header(f"{SYNC} Sync & Reload Home Assistant")

    # Step 1: Check container is running
    print_step(1, 6, "Checking container status...")
    if not is_container_running():
        print_error_header("CONTAINER NOT RUNNING")
        print("   The Home Assistant container is not running.")
        print(f"   Run {YELLOW}HA: Start (Keep Data){NC} first.\n")
        return 1
    print_success("Container is running")

    # Step 2: Sync modem configs
    print()
    print_step(2, 6, "Syncing modem configs...")
    result = subprocess.run(
        ["python3", "scripts/release.py", "--sync-only"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=get_project_dir(),
    )
    if result.returncode != 0:
        print_error_header("SYNC FAILED")
        print(result.stderr or result.stdout)
        return 1
    print_success("Modem configs synced")

    # Step 3: Regenerate modem index
    print()
    print_step(3, 6, "Regenerating modem index...")
    result = subprocess.run(
        ["python3", "scripts/generate_modem_index.py"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=get_project_dir(),
    )
    if result.returncode != 0:
        print_error_header("INDEX GENERATION FAILED")
        print(result.stderr or result.stdout)
        return 1
    print_success("Modem index regenerated")

    # Step 4: Regenerate fixture index (modems/README.md)
    print()
    print_step(4, 6, "Regenerating fixture index...")
    result = subprocess.run(
        ["python3", "scripts/generate_fixture_index.py"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=get_project_dir(),
    )
    if result.returncode != 0:
        print_error_header("FIXTURE INDEX GENERATION FAILED")
        print(result.stderr or result.stdout)
        return 1
    print_success("Fixture index regenerated")

    # Step 5: Restart container
    print()
    print_step(5, 6, "Restarting Home Assistant...")
    result = subprocess.run(
        ["docker", "restart", CONTAINER_NAME],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        print_error_header("RESTART FAILED")
        print(result.stderr)
        return 1
    print_success("Container restarted")

    # Step 6: Wait for HA to be ready
    print()
    print_step(6, 6, "Waiting for Home Assistant...")
    print("   ", end="")

    if wait_for_http(HA_PORT, timeout=60):
        print()
        print_success("HTTP responding")
    else:
        print()
        print_error("HTTP not responding after 60s")
        print_info("Check logs: docker logs -f ha-cable-modem-test")
        return 1

    # Verify integration
    if check_integration_mounted():
        print_success("Cable Modem Monitor integration mounted")
    else:
        print_error("Integration not found in container")

    # Success
    print_success_header("RELOAD COMPLETE")
    print(f"   URL: {BLUE}http://localhost:{HA_PORT}{NC}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
