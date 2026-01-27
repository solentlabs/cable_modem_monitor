#!/bin/bash
# Smoke test for devcontainer setup
# Run this inside the devcontainer to verify everything works

set -e

echo "=== Devcontainer Smoke Test ==="
echo ""

# Check Docker daemon
echo -n "Docker daemon... "
if docker info &>/dev/null; then
    echo "OK"
else
    echo "FAILED"
    exit 1
fi

# Check Docker pull works
echo -n "Docker pull... "
if docker pull --quiet alpine:latest &>/dev/null; then
    echo "OK"
    docker rmi alpine:latest &>/dev/null || true
else
    echo "FAILED (credential issue?)"
    exit 1
fi

# Check pytest
echo -n "Pytest discovery... "
if pytest --collect-only -q 2>/dev/null | tail -1 | grep -q "tests collected"; then
    echo "OK"
else
    echo "FAILED"
    exit 1
fi

# Check ruff
echo -n "Ruff installed... "
if ruff --version &>/dev/null; then
    echo "OK"
else
    echo "FAILED"
    exit 1
fi

# Check HA sync-run script
echo -n "HA sync-run script... "
if python scripts/dev/ha-sync-run.py --help &>/dev/null; then
    echo "OK"
else
    echo "FAILED"
    exit 1
fi

echo ""
echo "=== All checks passed ==="
