***REMOVED***!/bin/bash
***REMOVED*** Deploy Cable Modem Monitor to Home Assistant
***REMOVED*** Usage: ./deploy_to_ha.sh [ha_host] [ha_user] [ha_port]

***REMOVED*** Configuration
HA_HOST="${1:-192.168.5.2}"
HA_USER="${2:-claude}"
HA_PORT="${3:-22}"
HA_CONFIG_PATH="/config/custom_components/cable_modem_monitor"

echo "========================================="
echo "Cable Modem Monitor Deployment Script"
echo "========================================="
echo "Target: ${HA_USER}@${HA_HOST}:${HA_PORT}"
echo "Path: ${HA_CONFIG_PATH}"
echo ""

***REMOVED*** Check if we can connect
echo "Testing SSH connection..."
if ! ssh -p "${HA_PORT}" -i ~/.ssh/id_ed25519_homeassistant -o ConnectTimeout=5 "${HA_USER}@${HA_HOST}" "echo 'Connection successful'"; then
    echo "ERROR: Cannot connect to Home Assistant at ${HA_USER}@${HA_HOST}:${HA_PORT}"
    echo "Please check your SSH settings and try again."
    exit 1
fi

echo ""
echo "Creating backup of existing installation..."
ssh -p "${HA_PORT}" -i ~/.ssh/id_ed25519_homeassistant "${HA_USER}@${HA_HOST}" "if [ -d '${HA_CONFIG_PATH}' ]; then cp -r '${HA_CONFIG_PATH}' '${HA_CONFIG_PATH}.backup-$(date +%Y%m%d-%H%M%S)'; echo 'Backup created'; else echo 'No existing installation found'; fi"

echo ""
echo "Creating directory structure..."
ssh -p "${HA_PORT}" -i ~/.ssh/id_ed25519_homeassistant "${HA_USER}@${HA_HOST}" "mkdir -p '${HA_CONFIG_PATH}'"

echo ""
echo "Copying integration files..."
scp -P "${HA_PORT}" -i ~/.ssh/id_ed25519_homeassistant -r custom_components/cable_modem_monitor/* "${HA_USER}@${HA_HOST}:${HA_CONFIG_PATH}/"

if [ $? -eq 0 ]; then
    echo ""
    echo "========================================="
    echo "Deployment successful!"
    echo "========================================="
    echo ""
    echo "Next steps:"
    echo "1. Restart Home Assistant to load the updated integration"
    echo "2. Check Home Assistant logs for any warnings about invalid data"
    echo "3. Download diagnostics from the integration settings page"
    echo "4. Review cleanup_zero_values.md to remove existing bad data"
    echo ""
    echo "To restart Home Assistant, run:"
    echo "  ssh -p ${HA_PORT} ${HA_USER}@${HA_HOST} 'ha core restart'"
    echo ""
else
    echo ""
    echo "ERROR: Deployment failed!"
    echo "Please check the error messages above."
    exit 1
fi
