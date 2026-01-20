#!/bin/bash
# Post-start message for dev container
# This runs every time the container starts

start_docker_daemon() {
    echo "Starting Docker daemon..."

    # Start docker-init.sh in background with nohup, log to file for debugging
    if [ -f /usr/local/share/docker-init.sh ]; then
        nohup /usr/local/share/docker-init.sh > /tmp/docker-init.log 2>&1 &
    else
        nohup dockerd > /tmp/dockerd.log 2>&1 &
    fi

    # Wait for docker to be ready (max 30 seconds)
    for i in {1..30}; do
        if docker info &> /dev/null 2>&1; then
            echo "✓ Docker daemon started"
            return 0
        fi
        sleep 1
    done

    echo "✗ Docker daemon failed to start after 30s"
    [ -f /tmp/docker-init.log ] && echo "Log:" && tail -5 /tmp/docker-init.log
    return 1
}

fix_docker_credentials() {
    # VS Code injects a credsStore that doesn't work inside docker-in-docker
    # Clear it preemptively on Windows (detected by the dev-containers pattern)
    if [ -f ~/.docker/config.json ]; then
        if grep -q "credsStore.*dev-containers" ~/.docker/config.json 2>/dev/null; then
            echo "{}" > ~/.docker/config.json
            echo "✓ Fixed Docker credential store for docker-in-docker"
        fi
    fi
}

# Main docker-in-docker setup
if command -v dockerd &> /dev/null; then
    # Fix credentials BEFORE starting daemon or pulling images
    fix_docker_credentials

    if ! docker info &> /dev/null 2>&1; then
        start_docker_daemon
    else
        echo "✓ Docker daemon already running"
    fi
fi

echo ""
echo "=========================================="
echo "🚀 Dev Container Ready!"
echo "=========================================="
echo ""
echo "Next steps to test the integration:"
echo ""
echo "1️⃣  Start Home Assistant:"
echo "   Ctrl+Shift+P → Tasks: Run Task → 'HA: Start (Fresh)'"
echo "   Wait ~1 minute for startup, then open: http://localhost:8123"
echo ""
echo "2️⃣  Create account and add integration:"
echo "   • Complete Home Assistant onboarding"
echo "   • Go to Settings → Devices & Services → Add Integration"
echo "   • Search for 'Cable Modem Monitor'"
echo ""
echo "3️⃣  Run tests:"
echo "   Ctrl+Shift+P → Tasks: Run Task → 'Run All Tests'"
echo ""
echo "📋 View all available tasks: Ctrl+Shift+P → Tasks: Run Task"
echo ""
