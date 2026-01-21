#!/usr/bin/env python3
"""Run a mock modem server for local development testing.

This script starts an HTTP server that emulates a cable modem,
including authentication flows and fixture responses.

Usage:
    # List available modems
    python scripts/mock_modem.py --list

    # Run MB8611 HNAP mock on default port (8080)
    python scripts/mock_modem.py motorola/mb8611

    # Run on specific port
    python scripts/mock_modem.py motorola/mb8611 --port 8888

    # Disable authentication (serve fixtures directly)
    python scripts/mock_modem.py motorola/mb8611 --no-auth

    # Run with verbose logging
    python scripts/mock_modem.py motorola/mb8611 -v

Then configure Home Assistant integration to connect to:
    http://127.0.0.1:8080

Test credentials:
    Username: admin
    Password: password
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.integration.mock_modem_server import MockModemServer  # noqa: E402


def list_modems() -> list[str]:
    """List available modem configurations."""
    modems_dir = PROJECT_ROOT / "modems"
    available = []

    for manufacturer_dir in sorted(modems_dir.iterdir()):
        if not manufacturer_dir.is_dir():
            continue
        for model_dir in sorted(manufacturer_dir.iterdir()):
            if not model_dir.is_dir():
                continue
            modem_yaml = model_dir / "modem.yaml"
            if modem_yaml.exists():
                available.append(f"{manufacturer_dir.name}/{model_dir.name}")

    return available


def main() -> int:
    """Run the mock modem server."""
    parser = argparse.ArgumentParser(
        description="Run a mock modem server for development testing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --list                    List available modems
  %(prog)s motorola/mb8611           Run MB8611 HNAP mock
  %(prog)s arris/s33 --port 8888     Run S33 on port 8888
  %(prog)s arris/sb6190 --no-auth    Run SB6190 without auth

Test credentials: admin / password
""",
    )

    parser.add_argument(
        "modem",
        nargs="?",
        help="Modem path (manufacturer/model), e.g., motorola/mb8611",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available modem configurations",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to listen on (default: 8080)",
    )
    parser.add_argument(
        "--no-auth",
        action="store_true",
        help="Disable authentication (serve fixtures directly)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # List modems if requested
    if args.list:
        print("Available modem configurations:\n")
        for modem in list_modems():
            print(f"  {modem}")
        print("\nUsage: python scripts/mock_modem.py <modem>")
        return 0

    # Require modem argument
    if not args.modem:
        parser.error("the following arguments are required: modem")

    # Resolve modem path
    modem_path = PROJECT_ROOT / "modems" / args.modem
    if not modem_path.exists():
        print(f"Error: Modem not found: {args.modem}")
        print("\nAvailable modems:")
        for modem in list_modems():
            print(f"  {modem}")
        return 1

    modem_yaml = modem_path / "modem.yaml"
    if not modem_yaml.exists():
        print(f"Error: modem.yaml not found in {modem_path}")
        return 1

    # Start server
    server = MockModemServer(
        modem_path=modem_path,
        port=args.port,
        auth_enabled=not args.no_auth,
    )

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\nShutting down...")
        server.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    server.start()

    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║  Mock Modem Server Running                                       ║
╠══════════════════════════════════════════════════════════════════╣
║  Modem:      {server.config.manufacturer} {server.config.model:<30} ║
║  Strategy:   {server.config.auth.strategy.value:<42} ║
║  URL:        {server.url:<44} ║
║  Auth:       {'Enabled' if args.no_auth is False else 'Disabled':<44} ║
╠══════════════════════════════════════════════════════════════════╣
║  Test Credentials:                                               ║
║    Username: admin                                               ║
║    Password: password                                            ║
╠══════════════════════════════════════════════════════════════════╣
║  Press Ctrl+C to stop                                            ║
╚══════════════════════════════════════════════════════════════════╝
""")

    # Keep running until interrupted
    try:
        signal.pause()
    except AttributeError:
        # signal.pause() not available on Windows
        import time

        while True:
            time.sleep(1)

    return 0


if __name__ == "__main__":
    sys.exit(main())
