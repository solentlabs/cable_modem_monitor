#!/usr/bin/env python3
"""Run a mock modem server for local development testing.

This script starts an HTTP server that emulates a cable modem,
including authentication flows and fixture responses.

Usage:
    # List available modems
    python scripts/mock_modem.py --list

    # Run by short name (auto-discovers manufacturer)
    python scripts/mock_modem.py g54
    python scripts/mock_modem.py mb7621

    # Run by full path
    python scripts/mock_modem.py arris/sb8200

    # Run on specific port
    python scripts/mock_modem.py g54 --port 8888

    # Simulate slow modem
    python scripts/mock_modem.py g54 --delay 15

    # Disable authentication (serve fixtures directly)
    python scripts/mock_modem.py g54 --no-auth

    # Override auth type
    python scripts/mock_modem.py sb6190 --auth-type form_ajax

Test credentials: admin / pw
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

MODEMS_DIR = PROJECT_ROOT / "modems"


def list_modems() -> list[tuple[str, str]]:
    """List available modem configurations.

    Returns list of (full_path, model_name) tuples.
    """
    available = []

    for manufacturer_dir in sorted(MODEMS_DIR.iterdir()):
        if not manufacturer_dir.is_dir():
            continue
        for model_dir in sorted(manufacturer_dir.iterdir()):
            if not model_dir.is_dir():
                continue
            modem_yaml = model_dir / "modem.yaml"
            if modem_yaml.exists():
                full_path = f"{manufacturer_dir.name}/{model_dir.name}"
                available.append((full_path, model_dir.name))

    return available


def find_modem_path(name: str) -> Path:
    """Find modem path by short name or full path.

    Args:
        name: Either short name (g54, mb7621) or full path (arris/g54)

    Returns:
        Path to modem directory

    Raises:
        ValueError: If modem not found
    """
    # Direct path: arris/g54, motorola/mb7621
    if "/" in name:
        path = MODEMS_DIR / name
        if path.exists() and (path / "modem.yaml").exists():
            return path
        raise ValueError(f"Modem not found: {name}")

    # Search by model name (case-insensitive)
    name_lower = name.lower()
    for manufacturer in MODEMS_DIR.iterdir():
        if not manufacturer.is_dir():
            continue
        for model in manufacturer.iterdir():
            if model.name.lower() == name_lower and (model / "modem.yaml").exists():
                return model

    raise ValueError(f"Modem not found: {name}")


def main() -> int:
    """Run the mock modem server."""
    parser = argparse.ArgumentParser(
        description="Run a mock modem server for development testing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --list                       List available modems
  %(prog)s g54                          Run by short name
  %(prog)s arris/sb8200                 Run by full path
  %(prog)s g54 --port 8888              Run on specific port
  %(prog)s g54 --delay 15               Simulate slow modem (15s delay)
  %(prog)s g54 --no-auth                Disable auth (serve fixtures directly)
  %(prog)s sb6190 --auth-type form_ajax Override auth type

Test credentials: admin / pw
""",
    )

    parser.add_argument(
        "modem",
        nargs="?",
        help="Modem name (short: g54, mb7621) or path (arris/g54)",
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
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0 for Docker access)",
    )
    parser.add_argument(
        "--no-auth",
        action="store_true",
        help="Disable authentication (serve fixtures directly)",
    )
    parser.add_argument(
        "--auth-type",
        type=str,
        help="Override auth type (e.g., 'form', 'none', 'form_ajax', 'url_token')",
    )
    parser.add_argument(
        "--auth-redirect",
        type=str,
        help="Override redirect URL after auth (simulates modems that redirect to non-data page)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Response delay in seconds (simulates slow modems)",
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

    # Validate delay
    if args.delay < 0:
        parser.error("--delay must be non-negative")

    # List modems if requested
    if args.list:
        print("Available modem configurations:\n")
        modems = list_modems()
        # Group by short name availability
        for full_path, model_name in modems:
            print(f"  {full_path:<30} (or: {model_name})")
        print(f"\nTotal: {len(modems)} modems")
        print("\nUsage: python scripts/mock_modem.py <modem>")
        return 0

    # Require modem argument
    if not args.modem:
        parser.error("the following arguments are required: modem (use --list to see available)")

    # Resolve modem path
    try:
        modem_path = find_modem_path(args.modem)
    except ValueError as e:
        print(f"Error: {e}")
        print("\nUse --list to see available modems")
        return 1

    # Start server
    server = MockModemServer(
        modem_path=modem_path,
        port=args.port,
        host=args.host,
        auth_enabled=not args.no_auth,
        auth_type=args.auth_type,
        auth_redirect=args.auth_redirect,
        response_delay=args.delay,
    )

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\nShutting down...")
        server.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    server.start()

    delay_str = f"{args.delay}s" if args.delay > 0 else "none"
    auth_status = "Disabled" if args.no_auth else "Enabled"

    print(f"""
{'='*60}
  Mock Modem Server Running
{'='*60}
  Modem:       {server.config.manufacturer} {server.config.model}
  Auth:        {auth_status} ({server.handler.__class__.__name__})
  Delay:       {delay_str}
{'='*60}
  URL (Docker): http://host.docker.internal:{args.port}
  URL (direct): {server.url}
{'='*60}
  Credentials:  admin / pw
{'='*60}
  Press Ctrl+C to stop
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
