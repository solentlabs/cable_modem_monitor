#!/bin/bash
# Custom entrypoint for HA dev container.
# Installs Core and Catalog packages BEFORE HA starts, so the integration
# never sees "package not found" errors on any boot.

set -e

echo "=== Installing solentlabs packages ==="

if [ -d /workspace/packages/cable_modem_monitor_core ]; then
    pip install --quiet -e /workspace/packages/cable_modem_monitor_core
    echo "  Core installed"
else
    echo "  WARNING: Core package not found at /workspace/packages/cable_modem_monitor_core"
fi

if [ -d /workspace/packages/cable_modem_monitor_catalog ]; then
    pip install --quiet -e /workspace/packages/cable_modem_monitor_catalog
    echo "  Catalog installed"
else
    echo "  WARNING: Catalog package not found at /workspace/packages/cable_modem_monitor_catalog"
fi

echo "=== Starting Home Assistant ==="

# Hand off to the original HA entrypoint
exec /init
