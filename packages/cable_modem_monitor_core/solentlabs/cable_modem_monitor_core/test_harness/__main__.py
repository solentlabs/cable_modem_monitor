"""Standalone mock server for integration testing.

Start a persistent HTTP server that replays HAR-captured modem
responses with auth simulation. Point a Home Assistant instance
(or any HTTP client) at it to verify the integration works with
real response data.

Usage::

    python -m solentlabs.cable_modem_monitor_core.test_harness \\
        /path/to/modems/{manufacturer}/{model} \\
        --host 0.0.0.0 --port 8080

The server prints its base URL and test credentials, then blocks
until interrupted (Ctrl+C).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .loader import ServerConfig, load_server_from_modem_dir
from .server import HARMockServer

_logger = logging.getLogger(__name__)

_W = 64  # banner width (interior)


def _print_banner(config: ServerConfig, server: HARMockServer) -> None:
    """Print a formatted startup banner with modem config details."""
    mc = config.modem_config
    auth_strategy = mc.auth.strategy if mc.auth is not None else "none"
    transport = mc.transport
    default_host = mc.default_host
    docsis = getattr(mc.hardware, "docsis_version", "unknown") if mc.hardware else "unknown"
    status = mc.status if hasattr(mc, "status") else "unknown"
    cookie = getattr(mc.auth, "cookie_name", "")
    route_count = len(server.routes)

    def _row(label: str, value: str) -> str:
        content = f"  {label:<16}{value}"
        return f"\u2551{content:<{_W}}\u2551"

    print()
    print(f"\u2554{'=' * _W}\u2557")
    print(f"\u2551{'  Mock Modem Server':<{_W}}\u2551")
    print(f"\u2560{'=' * _W}\u2563")
    print(_row("Manufacturer:", mc.manufacturer))
    print(_row("Model:", mc.model))
    print(_row("Transport:", transport))
    print(_row("Auth:", auth_strategy))
    if cookie:
        print(_row("Session:", cookie))
    print(_row("DOCSIS:", docsis))
    print(_row("Status:", status))
    print(_row("Default Host:", default_host))
    print(f"\u2560{'-' * _W}\u2563")
    print(_row("URL:", server.base_url))
    print(_row("Routes:", str(route_count)))
    if auth_strategy != "none":
        print(f"\u2560{'-' * _W}\u2563")
        print(_row("Username:", "admin"))
        print(_row("Password:", "pw"))
    print(f"\u2560{'-' * _W}\u2563")
    print(f"\u2551{'  Press Ctrl+C to stop':<{_W}}\u2551")
    print(f"\u255a{'=' * _W}\u255d")
    print()


def main(argv: list[str] | None = None) -> int:
    """Entry point for the standalone mock server.

    Args:
        argv: Command-line arguments. Defaults to ``sys.argv[1:]``.

    Returns:
        Exit code (0 for clean shutdown, 1 for errors).
    """
    parser = argparse.ArgumentParser(
        prog="python -m solentlabs.cable_modem_monitor_core.test_harness",
        description="Start a mock modem server that replays HAR responses.",
    )
    parser.add_argument(
        "modem_dir",
        type=Path,
        help="Path to modem directory (e.g., modems/arris/sb8200)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Bind address (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Bind port (default: 8080)",
    )
    parser.add_argument(
        "--har",
        dest="har_name",
        default=None,
        help="HAR file name in test_data/ (default: first found)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )

    # Load modem directory
    try:
        config = load_server_from_modem_dir(args.modem_dir, args.har_name)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Start server
    server = HARMockServer(
        config.har_entries,
        modem_config=config.modem_config,
        host=args.host,
        port=args.port,
    )

    _print_banner(config, server)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        server.server_close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
