#!/usr/bin/env python3
"""Run a mock modem server for manual testing.

Usage:
    python scripts/mock_server.py g54
    python scripts/mock_server.py mb7621 --port 8081
    python scripts/mock_server.py arris/sb8200
    python scripts/mock_server.py sb6190 --auth-type form_ajax

Credentials: admin / pw
"""

import argparse
import signal
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.integration.mock_modem_server import MockModemServer

MODEMS_DIR = Path(__file__).parent.parent / "modems"


def find_modem_path(name: str) -> Path:
    """Find modem path by short name or full path."""
    # Direct path: arris/g54, motorola/mb7621
    if "/" in name:
        path = MODEMS_DIR / name
        if path.exists():
            return path

    # Search by model name
    name_lower = name.lower()
    for manufacturer in MODEMS_DIR.iterdir():
        if not manufacturer.is_dir():
            continue
        for model in manufacturer.iterdir():
            if model.name.lower() == name_lower:
                return model

    raise ValueError(f"Modem not found: {name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("modem", help="Modem name (e.g., g54, mb7621, arris/sb8200)")
    parser.add_argument("--port", type=int, default=8080, help="Port (default: 8080)")
    parser.add_argument("--host", default="0.0.0.0", help="Host (default: 0.0.0.0)")
    parser.add_argument("--auth-type", help="Auth type override (e.g., none, form, form_ajax, url_token)")
    args = parser.parse_args()

    modem_path = find_modem_path(args.modem)
    server = MockModemServer(modem_path, port=args.port, host=args.host, auth_type=args.auth_type)
    server.start()

    auth_type = args.auth_type or next(iter(server.config.auth.types.keys()), "none")
    print(f"\n{'='*50}")
    print(f"Mock server: {server.config.manufacturer} {server.config.model}")
    print(f"Auth type: {auth_type}")
    print(f"URL: {server.url}")
    print(f"HA host: host.docker.internal:{args.port}")
    print("Credentials: admin / pw")
    print(f"{'='*50}\n")
    print("Press Ctrl+C to stop...")

    signal.signal(signal.SIGINT, lambda *_: (server.stop(), sys.exit(0)))
    signal.pause()


if __name__ == "__main__":
    main()
