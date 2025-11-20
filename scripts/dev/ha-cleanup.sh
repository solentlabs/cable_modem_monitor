#!/bin/bash
# Clean up any processes or containers blocking Home Assistant ports

set -e

echo "🧹 Cleaning up Home Assistant environment..."
echo ""

# Check if port 8123 is in use
if command -v lsof &> /dev/null && lsof -i :8123 &> /dev/null; then
    echo "⚠️  Port 8123 is in use. Finding and stopping processes..."

    # Get PIDs using port 8123 (works on both Linux and macOS)
    PIDS=$(lsof -ti :8123 2>/dev/null || true)

    if [ -n "$PIDS" ]; then
        echo "   Found processes: $PIDS"
        for PID in $PIDS; do
            echo "   Stopping process $PID..."
            kill -9 $PID 2>/dev/null || sudo kill -9 $PID 2>/dev/null || true
        done
        echo "✅ Stopped processes using port 8123"
    fi
elif command -v netstat &> /dev/null && netstat -tuln 2>/dev/null | grep -q ":8123 "; then
    echo "⚠️  Port 8123 is in use. Finding and stopping processes..."

    # Fallback for systems without lsof
    PID=$(sudo netstat -tulpn 2>/dev/null | grep ":8123 " | awk '{print $7}' | cut -d'/' -f1 | head -1)

    if [ -n "$PID" ]; then
        echo "   Found process: $PID"
        echo "   Stopping process $PID..."
        kill -9 $PID 2>/dev/null || sudo kill -9 $PID 2>/dev/null || true
        echo "✅ Stopped process using port 8123"
    fi
else
    echo "✅ Port 8123 is free"
fi

echo ""

# Stop any running HA containers
echo "🐳 Checking for running Home Assistant containers..."
HA_CONTAINERS=$(docker ps -q --filter "name=ha-cable-modem" 2>/dev/null || true)

if [ -n "$HA_CONTAINERS" ]; then
    echo "   Found running containers, stopping..."
    docker stop $HA_CONTAINERS
    docker rm -f $HA_CONTAINERS 2>/dev/null || true
    echo "✅ Stopped Home Assistant containers"
else
    echo "✅ No running containers found"
fi

echo ""

# Clean up any stopped HA containers
echo "🗑️  Removing stopped containers..."
STOPPED_CONTAINERS=$(docker ps -aq --filter "name=ha-cable-modem" 2>/dev/null || true)

if [ -n "$STOPPED_CONTAINERS" ]; then
    docker rm -f $STOPPED_CONTAINERS 2>/dev/null || true
    echo "✅ Removed stopped containers"
else
    echo "✅ No stopped containers to remove"
fi

echo ""
echo "✅ Cleanup complete! Port 8123 and containers are ready."
echo ""
