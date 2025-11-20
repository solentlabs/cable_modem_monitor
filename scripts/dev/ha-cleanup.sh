#!/bin/bash
# Clean up any processes or containers blocking Home Assistant ports

set -e

echo "🧹 Cleaning up Home Assistant environment..."
echo ""

# Function to check if port 8123 is in use
check_port_in_use() {
    # Try multiple methods to check port usage
    if command -v lsof &> /dev/null; then
        if lsof -i :8123 &> /dev/null || sudo lsof -i :8123 &> /dev/null 2>&1; then
            return 0
        fi
    fi

    if command -v netstat &> /dev/null; then
        if netstat -tuln 2>/dev/null | grep -q ":8123 " || sudo netstat -tulpn 2>/dev/null | grep -q ":8123 "; then
            return 0
        fi
    fi

    if command -v ss &> /dev/null; then
        if ss -tuln 2>/dev/null | grep -q ":8123 " || sudo ss -tulpn 2>/dev/null | grep -q ":8123 "; then
            return 0
        fi
    fi

    return 1
}

# Function to kill processes using port 8123
kill_port_processes() {
    local killed=0

    # Try lsof first
    if command -v lsof &> /dev/null; then
        PIDS=$(lsof -ti :8123 2>/dev/null || sudo lsof -ti :8123 2>/dev/null || true)
        if [ -n "$PIDS" ]; then
            echo "   Found processes: $PIDS"
            for PID in $PIDS; do
                echo "   Killing process $PID..."
                kill -9 $PID 2>/dev/null || sudo kill -9 $PID 2>/dev/null || true
                killed=1
            done
        fi
    fi

    # Try netstat as fallback
    if [ $killed -eq 0 ] && command -v netstat &> /dev/null; then
        PIDS=$(sudo netstat -tulpn 2>/dev/null | grep ":8123 " | awk '{print $7}' | cut -d'/' -f1 | sort -u || true)
        if [ -n "$PIDS" ]; then
            echo "   Found processes: $PIDS"
            for PID in $PIDS; do
                if [ "$PID" != "-" ] && [ -n "$PID" ]; then
                    echo "   Killing process $PID..."
                    kill -9 $PID 2>/dev/null || sudo kill -9 $PID 2>/dev/null || true
                    killed=1
                fi
            done
        fi
    fi

    # Try ss as last resort
    if [ $killed -eq 0 ] && command -v ss &> /dev/null; then
        PIDS=$(sudo ss -tulpn 2>/dev/null | grep ":8123 " | awk -F'pid=' '{print $2}' | awk '{print $1}' | cut -d',' -f1 | sort -u || true)
        if [ -n "$PIDS" ]; then
            echo "   Found processes: $PIDS"
            for PID in $PIDS; do
                if [ "$PID" != "-" ] && [ -n "$PID" ]; then
                    echo "   Killing process $PID..."
                    kill -9 $PID 2>/dev/null || sudo kill -9 $PID 2>/dev/null || true
                    killed=1
                fi
            done
        fi
    fi

    return $killed
}

# Check if port 8123 is in use
if check_port_in_use; then
    echo "⚠️  Port 8123 is in use. Finding and stopping processes..."

    if kill_port_processes; then
        echo "✅ Stopped processes using port 8123"
        # Give the OS a moment to fully release the port
        sleep 1
    else
        echo "❌ Could not find/kill processes using port 8123"
        echo "   Attempting to continue anyway..."
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

# Clean up ALL HA containers (running, stopped, created, etc.)
echo "🗑️  Removing all Home Assistant containers..."
ALL_CONTAINERS=$(docker ps -aq --filter "name=ha-cable-modem" 2>/dev/null || true)

if [ -n "$ALL_CONTAINERS" ]; then
    docker rm -f $ALL_CONTAINERS 2>/dev/null || true
    echo "✅ Removed all Home Assistant containers"
    # Give Docker a moment to fully release ports
    sleep 1
else
    echo "✅ No containers to remove"
fi

echo ""
echo "✅ Cleanup complete! Port 8123 and containers are ready."
echo ""
