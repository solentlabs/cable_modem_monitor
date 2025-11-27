***REMOVED***!/usr/bin/env python3
"""
Cross-platform Home Assistant test environment startup script.
Starts HA container with verification and clear error reporting.

Usage:
    python scripts/dev/ha-start.py [--fresh]

Options:
    --fresh    Remove volumes and start with clean state
"""

import argparse
import platform
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

***REMOVED*** Color codes
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
WARN = "\u26a0" if USE_UNICODE else "!"

CONTAINER_NAME = "ha-cable-modem-test"
COMPOSE_FILE = "docker-compose.test.yml"
HA_PORT = 8123


def print_header(message: str):
    """Print a header line."""
    print(f"\n{BLUE}{'━' * 60}{NC}")
    print(f"{BLUE}  {message}{NC}")
    print(f"{BLUE}{'━' * 60}{NC}\n")


def print_error_header(message: str):
    """Print an error header."""
    print(f"\n{RED}{'━' * 60}{NC}")
    print(f"{RED}  {CROSS} {message}{NC}")
    print(f"{RED}{'━' * 60}{NC}\n")


def print_success_header(message: str):
    """Print a success header."""
    print(f"\n{GREEN}{'━' * 60}{NC}")
    print(f"{GREEN}  {CHECK} {message}{NC}")
    print(f"{GREEN}{'━' * 60}{NC}\n")


def print_step(num: int, total: int, message: str):
    """Print a step indicator."""
    print(f"{YELLOW}Step {num}/{total}:{NC} {message}")


def print_success(message: str):
    """Print success message."""
    print(f"   {GREEN}{CHECK}{NC} {message}")


def print_error(message: str):
    """Print error message."""
    print(f"   {RED}{CROSS}{NC} {message}")


def print_warning(message: str):
    """Print warning message."""
    print(f"   {YELLOW}{WARN}{NC} {message}")


def print_info(message: str):
    """Print info message."""
    print(f"   {message}")


def get_project_dir() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


def run_command(cmd: list, capture: bool = False, check: bool = True, timeout: int = 60) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    try:
        return subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            check=check,
            timeout=timeout,
            cwd=get_project_dir(),
        )
    except subprocess.CalledProcessError as e:
        if capture:
            ***REMOVED*** Return a failed CompletedProcess for consistent return type
            return subprocess.CompletedProcess(args=e.args, returncode=e.returncode, stdout=e.stdout, stderr=e.stderr)
        raise


def check_port_in_use(port: int) -> tuple[bool, str]:
    """Check if a port is in use and try to identify what's using it."""
    ***REMOVED*** Quick socket check
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        in_use = s.connect_ex(("localhost", port)) == 0

    if not in_use:
        return False, ""

    ***REMOVED*** Try to identify what's using it
    process_info = ""
    system = platform.system()

    try:
        if system == "Windows":
            result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=10)
            for line in result.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    process_info = line.strip()
                    break
        elif system == "Darwin":  ***REMOVED*** macOS
            result = subprocess.run(["lsof", "-i", f":{port}"], capture_output=True, text=True, timeout=10)
            process_info = result.stdout.strip()
        else:  ***REMOVED*** Linux
            result = subprocess.run(["ss", "-tulpn"], capture_output=True, text=True, timeout=10)
            for line in result.stdout.splitlines():
                if f":{port}" in line:
                    process_info = line.strip()
                    break
    except (subprocess.SubprocessError, FileNotFoundError):
        process_info = "(could not identify process)"

    return True, process_info


def docker_compose_cmd() -> list:
    """Get the docker compose command (handles 'docker-compose' vs 'docker compose')."""
    ***REMOVED*** Try 'docker compose' first (newer)
    result = subprocess.run(["docker", "compose", "version"], capture_output=True, timeout=10)
    if result.returncode == 0:
        return ["docker", "compose"]

    ***REMOVED*** Fall back to 'docker-compose'
    if shutil.which("docker-compose"):
        return ["docker-compose"]

    return ["docker", "compose"]  ***REMOVED*** Default, will fail with clear error


def get_container_status() -> tuple[str, bool]:
    """Get container status and running state."""
    try:
        result = subprocess.run(
            ["docker", "inspect", CONTAINER_NAME, "--format", "{{.State.Status}} {{.State.Running}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split()
            return parts[0], parts[1].lower() == "true"
    except (subprocess.SubprocessError, IndexError):
        pass
    return "not_found", False


def get_port_mapping() -> str:
    """Get the port mapping for the container."""
    try:
        result = subprocess.run(
            ["docker", "port", CONTAINER_NAME, str(HA_PORT)], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip().split("\n")[0]
    except subprocess.SubprocessError:
        pass
    return ""


def wait_for_http(port: int, timeout: int = 60) -> bool:
    """Wait for HTTP to respond on the given port."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                s.connect(("localhost", port))
                ***REMOVED*** Try a simple HTTP request
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


def run_cleanup():
    """Run the cleanup script if it exists, otherwise do basic cleanup."""
    cleanup_script = get_project_dir() / "scripts" / "dev" / "ha-cleanup.sh"

    if cleanup_script.exists() and platform.system() != "Windows":
        subprocess.run(["bash", str(cleanup_script)], cwd=get_project_dir())
    else:
        ***REMOVED*** Basic cleanup - just stop containers
        subprocess.run(["docker", "stop", CONTAINER_NAME], capture_output=True, timeout=30)
        subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True, timeout=30)


def main():  ***REMOVED*** noqa: C901
    parser = argparse.ArgumentParser(description="Start Home Assistant test environment")
    parser.add_argument("--fresh", action="store_true", help="Remove volumes and start fresh")
    args = parser.parse_args()

    compose_cmd = docker_compose_cmd()
    compose_file = str(get_project_dir() / COMPOSE_FILE)

    print_header("Home Assistant Test Environment Startup")

    ***REMOVED*** Step 1: Pre-flight port check
    print_step(1, 4, "Checking port availability...")
    port_in_use, process_info = check_port_in_use(HA_PORT)

    if port_in_use:
        ***REMOVED*** Check if it's our container
        status, running = get_container_status()
        if running:
            print_info(f"Port {HA_PORT} is in use by existing HA container")
            print_info("Stopping existing container...")
        else:
            print_warning(f"Port {HA_PORT} is already in use!")
            if process_info:
                print_info(f"Process: {process_info}")
            print_info("Will attempt cleanup...")
    else:
        print_success(f"Port {HA_PORT} is available")

    ***REMOVED*** Step 2: Cleanup
    print()
    print_step(2, 4, "Cleaning up existing containers...")
    run_cleanup()

    ***REMOVED*** Stop compose services
    down_cmd = compose_cmd + ["-f", compose_file, "down"]
    if args.fresh:
        down_cmd.append("-v")
        print_info("Removing volumes (fresh start)")

    subprocess.run(down_cmd, capture_output=True, timeout=60)
    print_success("Cleanup complete")

    ***REMOVED*** Step 3: Start container
    print()
    print_step(3, 4, "Starting Home Assistant container...")

    result = subprocess.run(
        compose_cmd + ["-f", compose_file, "up", "-d"],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=get_project_dir(),
    )

    if result.returncode != 0:
        print_error_header("STARTUP FAILED")
        print("Docker compose failed to start the container.\n")

        ***REMOVED*** Show the error
        if result.stderr:
            print(f"{YELLOW}Error output:{NC}")
            print(result.stderr)

        ***REMOVED*** Check for common issues
        if "port is already allocated" in result.stderr.lower() or "address already in use" in result.stderr.lower():
            print(f"\n{YELLOW}This is a port conflict.{NC}")
            print("Another process is using a required port.\n")
            print("To fix:")
            print("  1. Find what's using the port (see error above)")
            print("  2. Stop that process or change the port")
            print("  3. Try again")

        return 1

    print_success("Container created")

    ***REMOVED*** Step 4: Verify startup
    print()
    print_step(4, 4, "Verifying container started successfully...")
    time.sleep(2)

    status, running = get_container_status()

    if not running:
        print_error_header("CONTAINER FAILED TO START")
        print(f"Container status: {YELLOW}{status}{NC}\n")

        ***REMOVED*** Show logs
        print(f"{YELLOW}Container logs:{NC}")
        subprocess.run(["docker", "logs", CONTAINER_NAME, "--tail", "30"], timeout=10)

        print(f"\n{YELLOW}To fix:{NC}")
        print("  1. Check the logs above for errors")
        print(f"  2. Run: docker compose -f {COMPOSE_FILE} down -v")
        print("  3. Try again")
        return 1

    print_success("Container running")

    ***REMOVED*** Check port mapping
    port_mapping = get_port_mapping()
    if not port_mapping:
        print_error_header("PORT MAPPING FAILED")
        print("Container is running but port is not mapped.\n")

        port_in_use, process_info = check_port_in_use(HA_PORT)
        if port_in_use:
            print(f"{YELLOW}Port {HA_PORT} is in use by:{NC}")
            print(f"  {process_info}\n")

        print(f"{YELLOW}To fix:{NC}")
        print(f"  1. Stop the process using port {HA_PORT}")
        print(f"  2. Run: docker compose -f {COMPOSE_FILE} down")
        print("  3. Try again")
        return 1

    print_success(f"Port mapped: {port_mapping}")

    ***REMOVED*** Wait for HTTP
    print()
    print_info(
        "Waiting for Home Assistant to initialize",
    )
    print("   ", end="")

    if wait_for_http(HA_PORT, timeout=60):
        print()
        print_success("HTTP responding")
    else:
        print()
        print_warning("HTTP not responding after 60s (may still be initializing)")

    ***REMOVED*** Success!
    print_success_header("HOME ASSISTANT STARTED SUCCESSFULLY")

    print(f"   URL: {BLUE}http://localhost:{HA_PORT}{NC}\n")

    print(f"   {YELLOW}Useful commands:{NC}")
    print(f"   - View logs:  docker logs -f {CONTAINER_NAME}")
    print(f"   - Restart:    docker restart {CONTAINER_NAME}")
    print(f"   - Stop:       docker compose -f {COMPOSE_FILE} down")
    print()

    if check_integration_mounted():
        print_success("Cable Modem Monitor integration mounted")
    else:
        print_warning("Cable Modem Monitor integration not found")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
