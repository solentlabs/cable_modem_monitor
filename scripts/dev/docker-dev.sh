***REMOVED***!/bin/bash
***REMOVED*** Docker development environment management script for Cable Modem Monitor
***REMOVED*** Simplifies running Home Assistant with the integration for local testing

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.test.yml"
CONTAINER_NAME="ha-cable-modem-test"
TEST_CONFIG_DIR="$PROJECT_ROOT/test-ha-config"

***REMOVED*** Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' ***REMOVED*** No Color

print_header() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  Cable Modem Monitor - Docker Development Environment${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        echo "Visit: https://docs.docker.com/get-docker/"
        exit 1
    fi

    if ! docker ps &> /dev/null; then
        print_error "Docker daemon is not running. Please start Docker."
        exit 1
    fi

    print_success "Docker is installed and running"
}

setup_config_dir() {
    if [ ! -d "$TEST_CONFIG_DIR" ]; then
        mkdir -p "$TEST_CONFIG_DIR"
        print_success "Created test config directory: $TEST_CONFIG_DIR"
    else
        print_info "Test config directory already exists"
    fi
}

start_container() {
    print_header
    print_info "Starting Home Assistant development environment..."
    echo ""

    check_docker
    setup_config_dir

    cd "$PROJECT_ROOT"

    ***REMOVED*** Check if container is already running
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        print_warning "Container is already running"
        print_info "Use '$0 restart' to restart or '$0 logs' to view logs"
        return
    fi

    ***REMOVED*** Start the container
    docker compose -f "$COMPOSE_FILE" up -d

    echo ""
    print_success "Home Assistant is starting..."
    echo ""
    print_info "Container name: $CONTAINER_NAME"
    print_info "Web UI: http://localhost:8123"
    print_info "Config directory: $TEST_CONFIG_DIR"
    echo ""
    print_warning "First-time startup takes 1-2 minutes to initialize"
    print_info "Run '$0 logs' to view startup progress"
    echo ""
    print_info "To configure the integration:"
    print_info "  1. Go to http://localhost:8123"
    print_info "  2. Settings → Devices & Services"
    print_info "  3. Add Integration → Cable Modem Monitor"
}

stop_container() {
    print_info "Stopping Home Assistant development environment..."

    cd "$PROJECT_ROOT"
    docker compose -f "$COMPOSE_FILE" down

    print_success "Container stopped"
}

restart_container() {
    print_info "Restarting Home Assistant development environment..."

    stop_container
    echo ""
    start_container
}

show_logs() {
    print_info "Showing logs (Ctrl+C to exit)..."
    echo ""

    docker logs -f "$CONTAINER_NAME" 2>&1 | grep -v "^\[" || true
}

show_status() {
    print_header

    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        print_success "Container is running"
        echo ""
        docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        echo ""
        print_info "Web UI: http://localhost:8123"
    else
        print_warning "Container is not running"
        echo ""
        print_info "Run '$0 start' to start the development environment"
    fi
}

clean_all() {
    print_warning "This will remove the container and all test data"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Cleaning up..."

        cd "$PROJECT_ROOT"
        docker compose -f "$COMPOSE_FILE" down -v

        if [ -d "$TEST_CONFIG_DIR" ]; then
            rm -rf "$TEST_CONFIG_DIR"
            print_success "Removed test config directory"
        fi

        print_success "Clean up complete"
    else
        print_info "Cancelled"
    fi
}

shell_access() {
    print_info "Opening shell in container..."

    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        print_error "Container is not running. Start it first with '$0 start'"
        exit 1
    fi

    docker exec -it "$CONTAINER_NAME" /bin/bash
}

show_help() {
    print_header
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  start      Start the Home Assistant development environment"
    echo "  stop       Stop the development environment"
    echo "  restart    Restart the development environment"
    echo "  logs       Show container logs (follow mode)"
    echo "  status     Show container status"
    echo "  shell      Open a shell in the container"
    echo "  clean      Remove container and all test data"
    echo "  help       Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start          ***REMOVED*** Start Home Assistant"
    echo "  $0 logs           ***REMOVED*** Watch the logs"
    echo "  $0 restart        ***REMOVED*** Restart after making changes"
    echo "  $0 clean          ***REMOVED*** Clean up everything"
    echo ""
    echo "URLs:"
    echo "  Home Assistant UI: http://localhost:8123"
    echo ""
}

***REMOVED*** Main script logic
case "${1:-help}" in
    start)
        start_container
        ;;
    stop)
        stop_container
        ;;
    restart)
        restart_container
        ;;
    logs)
        show_logs
        ;;
    status)
        show_status
        ;;
    shell)
        shell_access
        ;;
    clean)
        clean_all
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
