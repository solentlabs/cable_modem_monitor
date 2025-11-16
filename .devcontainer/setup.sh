#!/bin/bash
set -e

echo "Installing Python packages..."
pip install --upgrade pip
pip install pytest pytest-cov pytest-mock pytest-asyncio pytest-homeassistant-custom-component beautifulsoup4 requests aiohttp lxml defusedxml black

echo "Installing Docker CLI..."
apk add --no-cache docker-cli docker-cli-compose

echo "Verifying Home Assistant integration mount..."
ls -la /config/custom_components/cable_modem_monitor/ | head -5

echo "✓ Setup complete!"
