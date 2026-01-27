#!/usr/bin/env python3
"""
Sync modem configs and ensure Home Assistant is running.

This script:
1. Syncs modem configs from modems/ to custom_components/
2. Regenerates modem index (index.yaml)
3. Regenerates fixture index (modems/README.md)
4. If HA container is running -> restart it
5. If HA container is not running -> start it
6. Waits for HA to be ready
7. Verifies the integration is mounted

Usage:
    python scripts/dev/ha-sync-run.py
"""

import os
import platform
import shutil
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
WARN = "\u26a0" if USE_UNICODE else "!"
SYNC = "\U0001f504" if USE_UNICODE else "~"

CONTAINER_NAME = "ha-cable-modem-test"
COMPOSE_FILE = "docker-compose.test.yml"
HA_PORT = 8123

# Other HA test containers that might be using the same port
OTHER_HA_CONTAINERS = [
    "ha-internet-health-test",
]


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


def print_warning(message: str):
    """Print warning message."""
    print(f"   {YELLOW}{WARN}{NC} {message}")


def print_info(message: str):
    """Print info message."""
    print(f"   {message}")


def get_project_dir() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


def fix_paths_for_docker_in_docker():
    """Fix volume paths when running inside a devcontainer."""
    if os.path.exists("/.dockerenv") or os.environ.get("REMOTE_CONTAINERS"):
        os.environ.pop("HOST_WORKSPACE_FOLDER", None)


def docker_compose_cmd() -> list:
    """Get the docker compose command."""
    result = subprocess.run(["docker", "compose", "version"], capture_output=True, timeout=10)
    if result.returncode == 0:
        return ["docker", "compose"]
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    return ["docker", "compose"]


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


def container_exists() -> bool:
    """Check if the HA container exists (running or stopped)."""
    try:
        result = subprocess.run(
            ["docker", "inspect", CONTAINER_NAME],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
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


def check_port_in_use(port: int) -> tuple[bool, str]:
    """Check if a port is in use and try to identify what's using it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        in_use = s.connect_ex(("localhost", port)) == 0

    if not in_use:
        return False, ""

    process_info = ""
    system = platform.system()

    try:
        if system == "Windows":
            result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=10)
            for line in result.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    process_info = line.strip()
                    break
        elif system == "Darwin":
            result = subprocess.run(["lsof", "-i", f":{port}"], capture_output=True, text=True, timeout=10)
            process_info = result.stdout.strip()
        else:
            result = subprocess.run(["ss", "-tulpn"], capture_output=True, text=True, timeout=10)
            for line in result.stdout.splitlines():
                if f":{port}" in line:
                    process_info = line.strip()
                    break
    except (subprocess.SubprocessError, FileNotFoundError):
        process_info = "(could not identify process)"

    return True, process_info


def stop_other_ha_containers() -> list[str]:
    """Stop other HA test containers that might be using port 8123."""
    stopped = []
    for container in OTHER_HA_CONTAINERS:
        result = subprocess.run(
            ["docker", "inspect", container, "--format", "{{.State.Running}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip().lower() == "true":
            print_info(f"Stopping {container} (30s grace period)...")
            subprocess.run(["docker", "stop", "-t", "30", container], capture_output=True, timeout=60)
            stopped.append(container)
    return stopped


def ensure_dev_config() -> None:
    """Ensure test-ha-config has a dev-friendly configuration.yaml."""
    config_dir = get_project_dir() / "test-ha-config"
    config_file = config_dir / "configuration.yaml"

    config_dir.mkdir(exist_ok=True)

    needs_update = True
    if config_file.exists():
        try:
            content = config_file.read_text()
            if "logger:" in content and "cable_modem_monitor" in content:
                needs_update = False
        except PermissionError:
            pass

    if needs_update:
        config_content = """\
# Development configuration for Cable Modem Monitor

# Logger configuration - quiet HA core, verbose for our integration
logger:
  default: warning
  logs:
    custom_components.cable_modem_monitor: info

# Loads default set of integrations. Do not remove.
default_config:

# Load frontend themes from the themes folder
frontend:
  themes: !include_dir_merge_named themes

automation: !include automations.yaml
script: !include scripts.yaml
scene: !include scenes.yaml
"""
        try:
            config_file.write_text(config_content)
            print_success("Created configuration.yaml with dev-friendly logger settings")
        except PermissionError:
            print_info("Updating configuration.yaml via docker (root-owned file)...")
            subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    f"{config_dir}:/config",
                    "alpine",
                    "sh",
                    "-c",
                    f"cat > /config/configuration.yaml << 'EOFCONFIG'\n{config_content}EOFCONFIG",
                ],
                capture_output=True,
                timeout=30,
            )
            print_success("Updated configuration.yaml with dev-friendly logger settings")


def start_container() -> bool:
    """Start the HA container from scratch."""
    fix_paths_for_docker_in_docker()
    compose_cmd = docker_compose_cmd()
    compose_file = str(get_project_dir() / COMPOSE_FILE)

    # Check for port conflicts
    port_in_use, process_info = check_port_in_use(HA_PORT)
    if port_in_use:
        print_warning(f"Port {HA_PORT} is in use")
        if process_info:
            print_info(f"Process: {process_info}")

        # Try stopping other HA containers
        stopped = stop_other_ha_containers()
        if stopped:
            print_info(f"Stopped: {', '.join(stopped)}")

    # Clean up any existing container
    if container_exists():
        print_info("Removing existing container...")
        subprocess.run(["docker", "stop", "-t", "30", CONTAINER_NAME], capture_output=True, timeout=60)
        subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True, timeout=30)

    # Ensure dev config exists
    ensure_dev_config()

    # Start container
    result = subprocess.run(
        compose_cmd + ["-f", compose_file, "up", "-d"],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=get_project_dir(),
    )

    if result.returncode != 0:
        print_error("Docker compose failed")
        if result.stderr:
            print(result.stderr)
        return False

    # Give it a moment to start
    time.sleep(2)
    return is_container_running()


def restart_container() -> bool:
    """Restart the existing HA container."""
    result = subprocess.run(
        ["docker", "restart", CONTAINER_NAME],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.returncode == 0


def main() -> int:
    print_header(f"{SYNC} Sync & Run Home Assistant")

    total_steps = 5

    # Step 1: Sync modem configs
    print_step(1, total_steps, "Syncing modem configs...")
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

    # Step 2: Regenerate modem index
    print()
    print_step(2, total_steps, "Regenerating modem index...")
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

    # Step 3: Regenerate fixture index
    print()
    print_step(3, total_steps, "Regenerating fixture index...")
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

    # Step 4: Start or restart container
    print()
    if is_container_running():
        print_step(4, total_steps, "Restarting Home Assistant...")
        if not restart_container():
            print_error_header("RESTART FAILED")
            return 1
        print_success("Container restarted")
    else:
        print_step(4, total_steps, "Starting Home Assistant...")
        if not start_container():
            print_error_header("START FAILED")
            print_info("Check Docker Desktop is running")
            return 1
        print_success("Container started")

    # Step 5: Wait for HA to be ready
    print()
    print_step(5, total_steps, "Waiting for Home Assistant...")
    print("   ", end="")

    if wait_for_http(HA_PORT, timeout=60):
        print()
        print_success("HTTP responding")
    else:
        print()
        print_warning("HTTP not responding after 60s (may still be initializing)")
        print_info("Check logs: docker logs -f ha-cable-modem-test")

    # Verify integration
    if check_integration_mounted():
        print_success("Cable Modem Monitor integration mounted")
    else:
        print_warning("Integration not found in container")

    # Success
    print_success_header("READY")
    print(f"   URL: {BLUE}http://localhost:{HA_PORT}{NC}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
