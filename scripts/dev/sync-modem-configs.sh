#!/usr/bin/env bash
# Pre-commit hook: sync modems/ -> custom_components/ and stage changes.
# Triggered when modems/.*/modem.yaml or modems/.*/parser.py changes.
set -e

make sync --quiet 2>/dev/null || make sync

# Stage any files that changed in custom_components/cable_modem_monitor/modems/
git add custom_components/cable_modem_monitor/modems/
