#!/bin/bash
#
# Deploy Cable Modem Monitor to a Home Assistant instance for testing
#
# This script copies the integration files to a Home Assistant instance,
# either locally or via SSH. Useful for testing development branches.
#
# Usage:
#   ./scripts/deploy_updates.sh                    # Interactive mode
#   ./scripts/deploy_updates.sh --local /path      # Local HA config path
#   ./scripts/deploy_updates.sh --ssh user@host    # Remote HA via SSH
#   ./scripts/deploy_updates.sh --docker container # Local Docker container
#
# Examples:
#   ./scripts/deploy_updates.sh --local ~/homeassistant/config
#   ./scripts/deploy_updates.sh --ssh root@192.168.1.100 --path /root/config
#   ./scripts/deploy_updates.sh --docker homeassistant
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
INTEGRATION_SOURCE="$REPO_ROOT/custom_components/cable_modem_monitor"

# Default values
DEPLOY_MODE=""
TARGET_PATH=""
SSH_HOST=""
DOCKER_CONTAINER=""
RESTART_HA=false

usage() {
    echo "Deploy Cable Modem Monitor to a Home Assistant instance"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --local PATH       Deploy to local HA config directory"
    echo "  --ssh USER@HOST    Deploy to remote HA via SSH"
    echo "  --docker CONTAINER Deploy to local Docker container"
    echo "  --path PATH        Custom path inside HA (default: /config)"
    echo "  --restart          Restart Home Assistant after deployment"
    echo "  -h, --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --local ~/homeassistant/config"
    echo "  $0 --ssh root@192.168.1.100"
    echo "  $0 --ssh hassio@homeassistant.local --path /root/config --restart"
    echo "  $0 --docker homeassistant --restart"
    echo ""
    echo "Manual deployment (if this script doesn't work for your setup):"
    echo "  1. Copy the 'custom_components/cable_modem_monitor' folder from this repo"
    echo "  2. Paste it into your HA's 'config/custom_components/' directory"
    echo "  3. Restart Home Assistant"
    echo ""
    echo "See docs/TESTING_ON_HA.md for detailed instructions."
}

check_source() {
    if [[ ! -d "$INTEGRATION_SOURCE" ]]; then
        echo -e "${RED}Error: Integration source not found at $INTEGRATION_SOURCE${NC}"
        echo "Make sure you're running this from the repository root."
        exit 1
    fi

    if [[ ! -f "$INTEGRATION_SOURCE/manifest.json" ]]; then
        echo -e "${RED}Error: manifest.json not found - invalid integration source${NC}"
        exit 1
    fi

    echo -e "${GREEN}Found integration at: $INTEGRATION_SOURCE${NC}"
}

deploy_local() {
    local target="$1/custom_components/cable_modem_monitor"

    echo -e "${YELLOW}Deploying to local path: $target${NC}"

    # Create custom_components directory if it doesn't exist
    mkdir -p "$1/custom_components"

    # Remove existing installation
    if [[ -d "$target" ]]; then
        echo "Removing existing installation..."
        rm -rf "$target"
    fi

    # Copy integration
    cp -r "$INTEGRATION_SOURCE" "$target"

    echo -e "${GREEN}Successfully deployed to $target${NC}"
}

deploy_ssh() {
    local ssh_target="$1"
    local remote_path="${2:-/config}"
    local target="$remote_path/custom_components/cable_modem_monitor"

    echo -e "${YELLOW}Deploying to $ssh_target:$target${NC}"

    # Create custom_components directory
    ssh "$ssh_target" "mkdir -p $remote_path/custom_components"

    # Remove existing installation
    ssh "$ssh_target" "rm -rf $target" 2>/dev/null || true

    # Copy integration via scp
    scp -r "$INTEGRATION_SOURCE" "$ssh_target:$target"

    echo -e "${GREEN}Successfully deployed to $ssh_target:$target${NC}"

    if [[ "$RESTART_HA" == true ]]; then
        echo -e "${YELLOW}Restarting Home Assistant...${NC}"
        ssh "$ssh_target" "ha core restart" 2>/dev/null || \
        ssh "$ssh_target" "docker restart homeassistant" 2>/dev/null || \
        echo -e "${YELLOW}Could not auto-restart. Please restart HA manually.${NC}"
    fi
}

deploy_docker() {
    local container="$1"
    local target="/config/custom_components/cable_modem_monitor"

    echo -e "${YELLOW}Deploying to Docker container: $container${NC}"

    # Check if container exists and is running
    if ! docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        echo -e "${RED}Error: Container '$container' is not running${NC}"
        echo "Available containers:"
        docker ps --format '  {{.Names}}'
        exit 1
    fi

    # Create custom_components directory
    docker exec "$container" mkdir -p /config/custom_components

    # Remove existing installation
    docker exec "$container" rm -rf "$target" 2>/dev/null || true

    # Copy integration
    docker cp "$INTEGRATION_SOURCE" "$container:$target"

    echo -e "${GREEN}Successfully deployed to container $container${NC}"

    if [[ "$RESTART_HA" == true ]]; then
        echo -e "${YELLOW}Restarting container...${NC}"
        docker restart "$container"
    fi
}

interactive_mode() {
    echo ""
    echo "Cable Modem Monitor - Deployment Script"
    echo "========================================"
    echo ""
    echo "How would you like to deploy?"
    echo "  1) Local path (e.g., ~/homeassistant/config)"
    echo "  2) Remote via SSH (e.g., root@192.168.1.100)"
    echo "  3) Docker container (e.g., homeassistant)"
    echo "  4) Show manual instructions"
    echo ""
    read -p "Select option [1-4]: " choice

    case $choice in
        1)
            read -p "Enter HA config path: " TARGET_PATH
            deploy_local "$TARGET_PATH"
            ;;
        2)
            read -p "Enter SSH target (user@host): " SSH_HOST
            read -p "Enter remote config path [/config]: " TARGET_PATH
            TARGET_PATH="${TARGET_PATH:-/config}"
            deploy_ssh "$SSH_HOST" "$TARGET_PATH"
            ;;
        3)
            read -p "Enter Docker container name: " DOCKER_CONTAINER
            deploy_docker "$DOCKER_CONTAINER"
            ;;
        4)
            echo ""
            echo "Manual Deployment Instructions"
            echo "=============================="
            echo ""
            echo "1. Copy ONLY the integration folder (not the whole repo):"
            echo "   Source: $INTEGRATION_SOURCE"
            echo ""
            echo "2. Paste into your HA config directory:"
            echo "   Target: <your-ha-config>/custom_components/cable_modem_monitor/"
            echo ""
            echo "3. The folder structure should look like:"
            echo "   custom_components/"
            echo "   └── cable_modem_monitor/"
            echo "       ├── __init__.py"
            echo "       ├── manifest.json"
            echo "       ├── config_flow.py"
            echo "       └── ..."
            echo ""
            echo "4. Restart Home Assistant"
            echo ""
            echo "Common mistake: Cloning the entire repo into custom_components/"
            echo "results in nested folders that HA cannot find."
            echo ""
            ;;
        *)
            echo "Invalid option"
            exit 1
            ;;
    esac
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --local)
            DEPLOY_MODE="local"
            TARGET_PATH="$2"
            shift 2
            ;;
        --ssh)
            DEPLOY_MODE="ssh"
            SSH_HOST="$2"
            shift 2
            ;;
        --docker)
            DEPLOY_MODE="docker"
            DOCKER_CONTAINER="$2"
            shift 2
            ;;
        --path)
            TARGET_PATH="$2"
            shift 2
            ;;
        --restart)
            RESTART_HA=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Main logic
check_source

if [[ -z "$DEPLOY_MODE" ]]; then
    interactive_mode
else
    case $DEPLOY_MODE in
        local)
            deploy_local "$TARGET_PATH"
            ;;
        ssh)
            deploy_ssh "$SSH_HOST" "$TARGET_PATH"
            ;;
        docker)
            deploy_docker "$DOCKER_CONTAINER"
            ;;
    esac
fi

echo ""
echo -e "${GREEN}Deployment complete!${NC}"
if [[ "$RESTART_HA" != true ]]; then
    echo -e "${YELLOW}Remember to restart Home Assistant to load the changes.${NC}"
fi
