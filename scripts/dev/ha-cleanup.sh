#!/bin/bash
# Clean up any processes or containers blocking Home Assistant ports
# Designed to work without sudo in WSL2/Linux environments

set -e

echo "🧹 Cleaning up Home Assistant environment..."
echo ""

# Stop any running HA containers first (most common case)
echo "🐳 Checking for running Home Assistant containers..."
HA_CONTAINERS=$(docker ps -q --filter "name=ha-cable-modem" 2>/dev/null || true)

if [ -n "$HA_CONTAINERS" ]; then
    echo "   Found running containers, stopping gracefully (30s timeout)..."
    docker stop -t 30 $HA_CONTAINERS 2>/dev/null || true
    docker rm -f $HA_CONTAINERS 2>/dev/null || true
    echo "✅ Stopped Home Assistant containers"
else
    echo "✅ No running containers found"
fi

echo ""

# Clean up ALL HA containers (stopped, created, etc.)
echo "🗑️  Removing all Home Assistant containers..."
ALL_CONTAINERS=$(docker ps -aq --filter "name=ha-cable-modem" 2>/dev/null || true)

if [ -n "$ALL_CONTAINERS" ]; then
    docker rm -f $ALL_CONTAINERS 2>/dev/null || true
    echo "✅ Removed all Home Assistant containers"
else
    echo "✅ No containers to remove"
fi

echo ""

# Quick port check (no sudo needed)
echo "🔍 Checking port 8123..."
if ss -tuln 2>/dev/null | grep -q ":8123 "; then
    echo "⚠️  Port 8123 still in use (may be another process)"
    echo "   If startup fails, check what's using port 8123:"
    echo "   ss -tulpn | grep 8123"
else
    echo "✅ Port 8123 is free"
fi

echo ""
echo "✅ Cleanup complete!"
echo ""
