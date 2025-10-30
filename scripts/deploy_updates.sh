***REMOVED***!/bin/bash
***REMOVED*** Deploy cable modem monitor updates to Home Assistant

echo "Creating deployment package..."
tar czf /tmp/cable_modem_deploy.tar.gz \
    -C custom_components \
    cable_modem_monitor/

echo "Copying to Home Assistant..."
cat /tmp/cable_modem_deploy.tar.gz | ssh homeassistant "cat > /tmp/cable_modem_deploy.tar.gz"

echo "Extracting on Home Assistant (may require password)..."
ssh homeassistant "cd /config/custom_components && sudo tar xzf /tmp/cable_modem_deploy.tar.gz && sudo chown -R root:root cable_modem_monitor && rm /tmp/cable_modem_deploy.tar.gz"

echo "Cleaning up local temp file..."
rm /tmp/cable_modem_deploy.tar.gz

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Next steps:"
echo "1. Go to Home Assistant"
echo "2. Settings → System → Restart Home Assistant"
echo "3. Wait for restart to complete"
echo "4. Test the new modular parser architecture!"
echo ""
echo "What's new:"
echo "  - Parser-owned URL patterns"
echo "  - 3-tier selection strategy (manual/cached/auto)"
echo "  - Modem model dropdown in config"
echo "  - Performance improvements with parser caching"
